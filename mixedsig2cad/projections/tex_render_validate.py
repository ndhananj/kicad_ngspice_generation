from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import tempfile

import cv2
import fitz
import numpy as np

from mixedsig2cad.compiled import compile_schematic
from mixedsig2cad.design import ExampleDesign, circuit_of
from mixedsig2cad.exporters.tex import DOCUMENT_PACKAGES, _pt, _tikz_safe_name, _visible_readable_labels, export_circuitikz
from mixedsig2cad.intent import build_schematic_intent
from mixedsig2cad.models import BoundingBox, CompiledSchematic, TextPlacement
from mixedsig2cad.projections.kicad_render_validate import build_symbol_probe_geometry
from mixedsig2cad.spec import CircuitSpec

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEX_SYMBOL_GOLDEN_DIR = ROOT / "tests" / "fixtures" / "tex_symbol_goldens"


@dataclass(frozen=True, slots=True)
class RenderedPdfText:
    text: str
    bounds: BoundingBox


@dataclass(frozen=True, slots=True)
class RenderedTexLabelComparison:
    schematic_name: str
    label_text: str
    role: str
    rendered_bounds: BoundingBox | None
    passed: bool
    notes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RenderedTexClipComparison:
    schematic_name: str
    page_bounds: BoundingBox
    content_bounds: BoundingBox | None
    passed: bool
    notes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RenderedTexTransistorComparison:
    schematic_name: str
    ref: str
    shape: str
    macro_name: str
    passed: bool
    notes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RenderedTexSymbolGoldenComparison:
    shape: str
    orientation: str
    fixture_path: Path
    mismatch_ratio: float | None
    passed: bool
    notes: tuple[str, ...]


def validate_rendered_tex_examples(
    specs: list[ExampleDesign | CircuitSpec],
    *,
    tex_dir: str | Path,
) -> tuple[list[RenderedTexLabelComparison], list[RenderedTexClipComparison]]:
    label_results: list[RenderedTexLabelComparison] = []
    clip_results: list[RenderedTexClipComparison] = []
    for source in specs:
        geometry = _compiled_geometry(source)
        tex_path = Path(tex_dir) / f"{geometry.name}.circuitikz.tex"
        pdf_path = _compile_readable_tex_pdf(tex_path)
        image = _pdf_page_to_image(pdf_path, dpi=300)
        observed_texts = _extract_pdf_texts(pdf_path)
        label_results.extend(_compare_rendered_tex_labels(geometry, observed_texts))
        clip_results.append(_compare_tex_page_clipping(geometry.name, image))
    failures = [result for result in [*label_results, *clip_results] if not result.passed]
    if failures:
        details = "\n".join(_failure_note(result) for result in failures)
        raise AssertionError(f"rendered TeX validation failed:\n{details}")
    return label_results, clip_results


def validate_rendered_tex_transistors(
    specs: list[ExampleDesign | CircuitSpec],
    *,
    tex_dir: str | Path,
) -> list[RenderedTexTransistorComparison]:
    results: list[RenderedTexTransistorComparison] = []
    for source in specs:
        geometry = _compiled_geometry(source)
        tex_path = Path(tex_dir) / f"{geometry.name}.circuitikz.tex"
        text = tex_path.read_text(encoding="utf-8")
        results.extend(_compare_tex_transistors(geometry, text))
    failures = [result for result in results if not result.passed]
    if failures:
        details = "\n".join(_failure_note(result) for result in failures)
        raise AssertionError(f"rendered TeX transistor validation failed:\n{details}")
    return results


def validate_rendered_tex_symbol_goldens(
    *,
    fixtures_dir: str | Path = DEFAULT_TEX_SYMBOL_GOLDEN_DIR,
    mismatch_threshold: float = 0.012,
) -> list[RenderedTexSymbolGoldenComparison]:
    fixture_root = Path(fixtures_dir)
    expected_pairs = set(_supported_tex_symbol_goldens())
    actual_pairs = {_parse_fixture_name(path) for path in fixture_root.glob("*.png")}
    results: list[RenderedTexSymbolGoldenComparison] = []
    missing_pairs = sorted(expected_pairs - actual_pairs)
    for shape, orientation in missing_pairs:
        results.append(
            RenderedTexSymbolGoldenComparison(
                shape=shape,
                orientation=orientation,
                fixture_path=fixture_root / _fixture_name(shape, orientation),
                mismatch_ratio=None,
                passed=False,
                notes=("missing golden image fixture",),
            )
        )
    for fixture_path in sorted(fixture_root.glob("*.png")):
        shape, orientation = _parse_fixture_name(fixture_path)
        rendered = render_tex_symbol_probe_image(shape, orientation)
        expected = cv2.imread(str(fixture_path), cv2.IMREAD_GRAYSCALE)
        if expected is None:
            results.append(
                RenderedTexSymbolGoldenComparison(
                    shape=shape,
                    orientation=orientation,
                    fixture_path=fixture_path,
                    mismatch_ratio=None,
                    passed=False,
                    notes=("failed to load golden image",),
                )
            )
            continue
        normalized_rendered = _normalize_symbol_image(rendered)
        normalized_expected = _normalize_symbol_image(expected)
        mismatch_ratio = _binary_image_mismatch_ratio(normalized_rendered, normalized_expected)
        notes: list[str] = []
        if mismatch_ratio > mismatch_threshold:
            notes.append(
                f"rendered symbol drifted from golden image ({mismatch_ratio:.4f} > {mismatch_threshold:.4f})"
            )
        results.append(
            RenderedTexSymbolGoldenComparison(
                shape=shape,
                orientation=orientation,
                fixture_path=fixture_path,
                mismatch_ratio=mismatch_ratio,
                passed=not notes,
                notes=tuple(notes),
            )
        )
    failures = [result for result in results if not result.passed]
    if failures:
        details = "\n".join(_failure_note(result) for result in failures)
        raise AssertionError(f"rendered TeX symbol golden validation failed:\n{details}")
    return results


def refresh_rendered_tex_symbol_goldens(
    *,
    output_dir: str | Path = DEFAULT_TEX_SYMBOL_GOLDEN_DIR,
) -> list[Path]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for shape, orientation in _supported_tex_symbol_goldens():
        image = render_tex_symbol_probe_image(shape, orientation)
        normalized = _normalize_symbol_image(image)
        target = destination / _fixture_name(shape, orientation)
        cv2.imwrite(str(target), normalized)
        written.append(target)
    return written


def _compiled_geometry(source: ExampleDesign | CircuitSpec) -> CompiledSchematic:
    if isinstance(source, CircuitSpec):
        return compile_schematic(build_schematic_intent(source))
    return compile_schematic(build_schematic_intent(circuit_of(source)))


def _compile_readable_tex_pdf(tex_path: Path) -> Path:
    snippet = tex_path.read_text(encoding="utf-8")
    return _compile_tex_snippet_pdf(snippet, stem=tex_path.stem)


def _compile_tex_snippet_pdf(snippet: str, *, stem: str) -> Path:
    with tempfile.TemporaryDirectory(prefix=f"mixedsig2cad-tex-{stem}-") as tmp_dir:
        tmp = Path(tmp_dir)
        wrapper = tmp / "snippet.tex"
        wrapper.write_text(_standalone_tex_document(snippet), encoding="utf-8")
        result = subprocess.run(
            [
                "pdflatex",
                "-interaction=nonstopmode",
                "-halt-on-error",
                f"-output-directory={tmp}",
                wrapper.name,
            ],
            cwd=tmp,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise AssertionError(
                f"pdflatex failed for {stem}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
        pdf_path = tmp / "snippet.pdf"
        handle = tempfile.NamedTemporaryFile(prefix=f"{stem}-", suffix=".pdf", delete=False)
        try:
            stable_pdf = Path(handle.name)
        finally:
            handle.close()
        stable_pdf.write_bytes(pdf_path.read_bytes())
        return stable_pdf


def _standalone_tex_document(snippet: str) -> str:
    lines = [
        r"\documentclass[11pt]{article}",
        *DOCUMENT_PACKAGES,
        r"\pagestyle{empty}",
        r"\begin{document}",
        r"\thispagestyle{empty}",
        snippet.strip(),
        r"\end{document}",
    ]
    return "\n".join(lines) + "\n"


def _pdf_page_to_image(path: Path, *, dpi: int) -> np.ndarray:
    with fitz.open(path) as document:
        page = document.load_page(0)
        pixmap = page.get_pixmap(dpi=dpi, alpha=False)
    data = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, pixmap.n)
    if pixmap.n == 4:
        return cv2.cvtColor(data, cv2.COLOR_RGBA2RGB)
    return data


def _extract_pdf_texts(path: Path) -> list[RenderedPdfText]:
    texts: list[RenderedPdfText] = []
    with fitz.open(path) as document:
        page = document.load_page(0)
        for left, top, right, bottom, text, *_ in page.get_text("words"):
            texts.append(
                RenderedPdfText(
                    text=text.strip(),
                    bounds=BoundingBox(float(left), float(top), float(right), float(bottom)),
                )
            )
    return texts


def _compare_rendered_tex_labels(
    geometry: CompiledSchematic,
    observed_texts: list[RenderedPdfText],
) -> list[RenderedTexLabelComparison]:
    labels = _visible_example_labels(geometry)
    unmatched = list(observed_texts)
    accepted: list[BoundingBox] = []
    results: list[RenderedTexLabelComparison] = []
    for label in labels:
        match = _nearest_rendered_text(label, unmatched)
        if match is None:
            results.append(
                RenderedTexLabelComparison(
                    schematic_name=geometry.name,
                    label_text=label.text,
                    role=label.role,
                    rendered_bounds=None,
                    passed=False,
                    notes=("missing OCR label in TeX render",),
                )
            )
            continue
        unmatched.remove(match)
        notes: list[str] = []
        for existing in accepted:
            if _boxes_overlap(match.bounds, existing):
                notes.append("rendered OCR text overlaps another label")
                break
        accepted.append(match.bounds)
        results.append(
            RenderedTexLabelComparison(
                schematic_name=geometry.name,
                label_text=label.text,
                role=label.role,
                rendered_bounds=match.bounds,
                passed=not notes,
                notes=tuple(notes),
            )
        )
    return results


def _compare_tex_page_clipping(name: str, image: np.ndarray) -> RenderedTexClipComparison:
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    _, mask = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)
    coords = cv2.findNonZero(mask)
    page_bounds = BoundingBox(0.0, 0.0, float(image.shape[1]), float(image.shape[0]))
    if coords is None:
        return RenderedTexClipComparison(
            schematic_name=name,
            page_bounds=page_bounds,
            content_bounds=None,
            passed=False,
            notes=("no rendered content found on TeX page",),
        )
    x, y, w, h = cv2.boundingRect(coords)
    content_bounds = BoundingBox(float(x), float(y), float(x + w), float(y + h))
    margin = 1
    notes: list[str] = []
    if content_bounds.left <= margin:
        notes.append("rendered content touches left page edge")
    if content_bounds.top <= margin:
        notes.append("rendered content touches top page edge")
    if content_bounds.right >= image.shape[1] - margin:
        notes.append("rendered content touches right page edge")
    if content_bounds.bottom >= image.shape[0] - margin:
        notes.append("rendered content touches bottom page edge")
    return RenderedTexClipComparison(
        schematic_name=name,
        page_bounds=page_bounds,
        content_bounds=content_bounds,
        passed=not notes,
        notes=tuple(notes),
    )


def _compare_tex_transistors(
    geometry: CompiledSchematic,
    text: str,
) -> list[RenderedTexTransistorComparison]:
    symbol_by_shape = {
        "npn_bjt": "npn",
        "nmos": "nmos",
        "pmos": "pmos",
    }
    legacy_macro_by_shape = {
        "npn_bjt": "msCircuitMixedSigNpnBjtSymbol",
        "nmos": "msCircuitMixedSigNmosSymbol",
        "pmos": "msCircuitMixedSigPmosSymbol",
    }
    results: list[RenderedTexTransistorComparison] = []
    for shape in geometry.shapes:
        symbol_name = symbol_by_shape.get(shape.shape)
        if symbol_name is None:
            continue
        legacy_macro_name = legacy_macro_by_shape[shape.shape]
        notes: list[str] = []
        node_name = _tikz_safe_name(shape.ref)
        if rf"\node[{symbol_name}] ({node_name})" not in text:
            notes.append(f"missing native circuitikz {symbol_name} node")
        if rf"\providecommand{{\{legacy_macro_name}}}[4]" in text:
            notes.append("legacy custom transistor macro should not be emitted")
        if shape.shape == "npn_bjt":
            expected_anchors = {
                "base": "B",
                "collector": "C",
                "emitter": "E",
            }
        else:
            expected_anchors = {
                "gate": "G",
                "drain": "D",
                "source": "S",
                "body": "B",
            }
        for terminal in shape.terminals:
            anchor = expected_anchors.get(terminal.name)
            if anchor is None:
                continue
            expected_wire = rf"\draw {_pt(terminal.point)} -- ({node_name}.{anchor});"
            if expected_wire not in text:
                notes.append(f"missing transistor terminal wire for {terminal.name}")
        if rf"\node[font=\scriptsize,align=center] at ({node_name}.text)" not in text:
            notes.append("missing transistor label at native node text anchor")
        results.append(
            RenderedTexTransistorComparison(
                schematic_name=geometry.name,
                ref=shape.ref,
                shape=shape.shape,
                macro_name=symbol_name,
                passed=not notes,
                notes=tuple(notes),
            )
        )
    return results


def _visible_example_labels(geometry: CompiledSchematic) -> list[TextPlacement]:
    return _visible_readable_labels(geometry)


def _nearest_rendered_text(label: TextPlacement, observed_texts: list[RenderedPdfText]) -> RenderedPdfText | None:
    normalized_label = label.text.strip().lower()
    candidates = [item for item in observed_texts if item.text.strip().lower() == normalized_label]
    if not candidates:
        return None
    return min(candidates, key=lambda item: (item.bounds.top, item.bounds.left, item.text))


def _boxes_overlap(first: BoundingBox, second: BoundingBox) -> bool:
    overlap_left = max(first.left, second.left)
    overlap_top = max(first.top, second.top)
    overlap_right = min(first.right, second.right)
    overlap_bottom = min(first.bottom, second.bottom)
    if overlap_right <= overlap_left or overlap_bottom <= overlap_top:
        return False
    overlap_area = (overlap_right - overlap_left) * (overlap_bottom - overlap_top)
    first_area = max(1.0, (first.right - first.left) * (first.bottom - first.top))
    second_area = max(1.0, (second.right - second.left) * (second.bottom - second.top))
    return overlap_area / min(first_area, second_area) >= 0.5


def _failure_note(
    result: RenderedTexLabelComparison | RenderedTexClipComparison | RenderedTexTransistorComparison | RenderedTexSymbolGoldenComparison,
) -> str:
    if isinstance(result, RenderedTexClipComparison):
        return f"{result.schematic_name}:clip: {'; '.join(result.notes)}"
    if isinstance(result, RenderedTexTransistorComparison):
        return f"{result.schematic_name}:{result.ref}:{result.shape}: {'; '.join(result.notes)}"
    if isinstance(result, RenderedTexSymbolGoldenComparison):
        return f"{result.shape}/{result.orientation}: {'; '.join(result.notes)}"
    return f"{result.schematic_name}:{result.role}:{result.label_text}: {'; '.join(result.notes)}"


def render_tex_symbol_probe_image(shape: str, orientation: str, *, dpi: int = 300) -> np.ndarray:
    geometry = build_symbol_probe_geometry(shape, orientation)
    snippet = export_circuitikz(geometry)
    pdf_path = _compile_tex_snippet_pdf(snippet, stem=f"probe_{shape}_{orientation}")
    return _pdf_page_to_image(pdf_path, dpi=dpi)


def _supported_tex_symbol_goldens() -> list[tuple[str, str]]:
    return [
        ("capacitor", "horizontal"),
        ("capacitor", "vertical"),
        ("current_source", "vertical_up"),
        ("diode", "horizontal"),
        ("diode", "vertical"),
        ("ground", "down"),
        ("inductor", "horizontal"),
        ("nmos", "right"),
        ("npn_bjt", "right"),
        ("opamp", "right"),
        ("pmos", "right"),
        ("power", "down"),
        ("power", "left"),
        ("power", "right"),
        ("power", "up"),
        ("resistor", "horizontal"),
        ("resistor", "horizontal_flipped"),
        ("resistor", "vertical"),
        ("voltage_source", "vertical_up"),
    ]


def _fixture_name(shape: str, orientation: str) -> str:
    return f"{shape}__{orientation}.png"


def _parse_fixture_name(path: Path) -> tuple[str, str]:
    stem = path.stem
    if "__" not in stem:
        raise AssertionError(f"invalid TeX symbol golden fixture name: {path.name}")
    shape, orientation = stem.split("__", 1)
    return shape, orientation


def _normalize_symbol_image(image: np.ndarray, *, side: int = 256, pad: int = 12) -> np.ndarray:
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    else:
        gray = image.copy()
    cropped = _crop_rendered_content(gray)
    _, binary = cv2.threshold(cropped, 220, 255, cv2.THRESH_BINARY)
    height, width = binary.shape
    scale = (side - (pad * 2)) / max(height, width)
    scaled_width = max(1, int(round(width * scale)))
    scaled_height = max(1, int(round(height * scale)))
    resized = cv2.resize(binary, (scaled_width, scaled_height), interpolation=cv2.INTER_AREA)
    canvas = np.full((side, side), 255, dtype=np.uint8)
    top = (side - scaled_height) // 2
    left = (side - scaled_width) // 2
    canvas[top : top + scaled_height, left : left + scaled_width] = resized
    return canvas


def _crop_rendered_content(image: np.ndarray) -> np.ndarray:
    _, mask = cv2.threshold(image, 245, 255, cv2.THRESH_BINARY_INV)
    coords = cv2.findNonZero(mask)
    if coords is None:
        return image
    x, y, w, h = cv2.boundingRect(coords)
    return image[y : y + h, x : x + w]


def _binary_image_mismatch_ratio(first: np.ndarray, second: np.ndarray) -> float:
    if first.shape != second.shape:
        raise AssertionError(f"image shapes differ: {first.shape} != {second.shape}")
    first_mask = first < 220
    second_mask = second < 220
    return float(np.count_nonzero(first_mask != second_mask)) / float(first_mask.size)
