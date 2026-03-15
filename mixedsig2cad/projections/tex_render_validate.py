from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
import tempfile

import cv2
import fitz
import numpy as np

from mixedsig2cad.compiled import compile_schematic
from mixedsig2cad.design import ExampleDesign, circuit_of
from mixedsig2cad.exporters.tex import DOCUMENT_PACKAGES, _visible_readable_labels
from mixedsig2cad.intent import build_schematic_intent
from mixedsig2cad.models import BoundingBox, CompiledSchematic, TextPlacement
from mixedsig2cad.spec import CircuitSpec


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


def _compiled_geometry(source: ExampleDesign | CircuitSpec) -> CompiledSchematic:
    if isinstance(source, CircuitSpec):
        return compile_schematic(build_schematic_intent(source))
    return compile_schematic(build_schematic_intent(circuit_of(source)))


def _compile_readable_tex_pdf(tex_path: Path) -> Path:
    snippet = tex_path.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix=f"mixedsig2cad-tex-{tex_path.stem}-") as tmp_dir:
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
                f"pdflatex failed for {tex_path}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
        pdf_path = tmp / "snippet.pdf"
        handle = tempfile.NamedTemporaryFile(prefix=f"{tex_path.stem}-", suffix=".pdf", delete=False)
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
        r"\begin{center}",
        r"\resizebox{\linewidth}{!}{%",
        snippet.strip(),
        r"}",
        r"\end{center}",
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
    by_shape = {
        "npn_bjt": "msCircuitMixedSigNpnBjtSymbol",
        "nmos": "msCircuitMixedSigNmosSymbol",
        "pmos": "msCircuitMixedSigPmosSymbol",
    }
    results: list[RenderedTexTransistorComparison] = []
    for shape in geometry.shapes:
        macro_name = by_shape.get(shape.shape)
        if macro_name is None:
            continue
        notes: list[str] = []
        if rf"\providecommand{{\{macro_name}}}[4]" not in text:
            notes.append("missing canonical transistor macro definition")
        if rf"\{macro_name}" not in text:
            notes.append("missing canonical transistor macro call")
        if _has_rectangular_transistor_macro(text, macro_name):
            notes.append("transistor macro regressed to rectangular fallback")
        if shape.shape == "pmos" and "circle" not in _macro_body(text, macro_name):
            notes.append("pmos TeX macro is missing the gate bubble")
        results.append(
            RenderedTexTransistorComparison(
                schematic_name=geometry.name,
                ref=shape.ref,
                shape=shape.shape,
                macro_name=macro_name,
                passed=not notes,
                notes=tuple(notes),
            )
        )
    return results


def _has_rectangular_transistor_macro(text: str, macro_name: str) -> bool:
    body = _macro_body(text, macro_name)
    return "rectangle" in body


def _macro_body(text: str, macro_name: str) -> str:
    pattern = re.compile(rf"\\providecommand\{{\\{macro_name}\}}\[4\]\{{%(.*?)\n\}}", re.DOTALL)
    match = pattern.search(text)
    return match.group(1) if match is not None else ""


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


def _failure_note(result: RenderedTexLabelComparison | RenderedTexClipComparison | RenderedTexTransistorComparison) -> str:
    if isinstance(result, RenderedTexClipComparison):
        return f"{result.schematic_name}:clip: {'; '.join(result.notes)}"
    if isinstance(result, RenderedTexTransistorComparison):
        return f"{result.schematic_name}:{result.ref}:{result.shape}: {'; '.join(result.notes)}"
    return f"{result.schematic_name}:{result.role}:{result.label_text}: {'; '.join(result.notes)}"
