from __future__ import annotations

import cv2
import numpy as np

from examples.specs.catalog import cmos_inverter, rc_lowpass
from mixedsig2cad.exporters.tex import build_circuitikz_ir, export_circuitikz, render_circuitikz_ir
from mixedsig2cad.importers.hybrid_parser import check_validation_runtime_dependencies
from mixedsig2cad.projections.tex_render_validate import (
    DEFAULT_TEX_SYMBOL_GOLDEN_DIR,
    RenderedPdfText,
    _compare_tex_mos_geometry,
    _compare_rendered_tex_labels,
    _compare_tex_page_clipping,
    _compare_tex_transistors,
    _compile_tex_snippet_pdf,
    _compiled_geometry,
    _crop_rendered_mos_region,
    _estimate_tex_raster_transform,
    _extract_tex_macro_segments,
    _has_continuous_right_vertical_macro_spine,
    _observe_tex_mos_macro,
    _extract_pdf_texts,
    _pdf_page_to_image,
    render_tex_symbol_probe_image,
    validate_rendered_tex_example_mos_geometry,
    validate_rendered_tex_symbol_goldens,
)
from mixedsig2cad.models import BoundingBox
from mixedsig2cad.projections.kicad_render_validate import build_symbol_probe_geometry


def test_validation_dependency_status_reports_tooling_fields() -> None:
    status = check_validation_runtime_dependencies()

    assert hasattr(status, "pdflatex_available")
    assert hasattr(status, "kicad_cli_available")
    assert hasattr(status, "pdf_raster_available")


def test_tex_clipping_check_passes_when_content_has_margin() -> None:
    image = np.full((300, 300, 3), 255, dtype=np.uint8)
    image[50:250, 60:240] = 0

    result = _compare_tex_page_clipping("clean", image)

    assert result.passed
    assert result.content_bounds == BoundingBox(60.0, 50.0, 240.0, 250.0)


def test_tex_clipping_check_fails_when_content_touches_page_edge() -> None:
    image = np.full((200, 200, 3), 255, dtype=np.uint8)
    image[0:120, 30:160] = 0

    result = _compare_tex_page_clipping("cropped", image)

    assert not result.passed
    assert "top page edge" in " ".join(result.notes)


def test_tex_label_compare_flags_overlapping_ocr_boxes() -> None:
    geometry = _compiled_geometry(cmos_inverter())
    observed = [
        RenderedPdfText("vin", BoundingBox(10.0, 10.0, 30.0, 24.0)),
        RenderedPdfText("vout", BoundingBox(18.0, 12.0, 40.0, 26.0)),
    ]

    results = _compare_rendered_tex_labels(geometry, observed)

    failing = [result for result in results if result.label_text in {"vin", "vout"}]
    assert failing
    assert any(not result.passed for result in failing)


def test_tex_transistor_validation_accepts_canonical_macros() -> None:
    geometry = _compiled_geometry(cmos_inverter())
    text = export_circuitikz(cmos_inverter())

    results = _compare_tex_transistors(geometry, text)

    assert results
    assert all(result.passed for result in results)


def test_tex_mos_macro_observation_requires_split_right_spine() -> None:
    text = export_circuitikz(cmos_inverter())

    observation = _observe_tex_mos_macro("nmos", text)

    assert observation.terminal_sides["gate"] == "left"
    assert observation.terminal_sides["drain"] == "top"
    assert observation.terminal_sides["source"] == "bottom"
    assert not observation.notes


def test_tex_mos_macro_observation_rejects_continuous_right_spine() -> None:
    text = export_circuitikz(cmos_inverter()).replace(
        r"\draw ({\msx + 0.25},{\msy + 0.88}) -- ({\msx + 0.25},{\msy + 0.22});",
        r"\draw ({\msx + 0.25},{\msy + 0.88}) -- ({\msx + 0.25},{\msy + -0.88});",
        1,
    ).replace(
        r"\draw ({\msx + 0.25},{\msy + -0.22}) -- ({\msx + 0.25},{\msy + -0.88});",
        "",
        1,
    )

    observation = _observe_tex_mos_macro("nmos", text)

    assert any("continuous right-side macro spine" in note for note in observation.notes)


def test_tex_transistor_validation_rejects_rectangular_fallback() -> None:
    geometry = _compiled_geometry(cmos_inverter())
    text = export_circuitikz(cmos_inverter()).replace(
        r"\providecommand{\msCircuitMixedSigPmosSymbol}[4]{%",
        "",
        1,
    )

    results = _compare_tex_transistors(geometry, text)

    assert any(not result.passed for result in results)


def test_extract_tex_macro_segments_finds_split_mos_leads() -> None:
    segments = _extract_tex_macro_segments(export_circuitikz(cmos_inverter()), "msCircuitMixedSigNmosSymbol")
    right_vertical = [
        segment for segment in segments if abs(segment[0][0] - segment[1][0]) <= 0.05 and max(segment[0][0], segment[1][0]) >= 0.20
    ]

    assert len(right_vertical) >= 2
    assert not _has_continuous_right_vertical_macro_spine(right_vertical)


def test_tex_label_validation_uses_pruned_readable_label_policy() -> None:
    geometry = _compiled_geometry(rc_lowpass())
    observed = [
        RenderedPdfText("vin", BoundingBox(10.0, 10.0, 30.0, 24.0)),
        RenderedPdfText("vout", BoundingBox(40.0, 10.0, 62.0, 24.0)),
    ]

    results = _compare_rendered_tex_labels(geometry, observed)

    assert {result.label_text for result in results} == {"vin", "vout"}


def test_tex_symbol_goldens_exist_for_supported_components() -> None:
    fixtures = sorted(DEFAULT_TEX_SYMBOL_GOLDEN_DIR.glob("*.png"))

    assert fixtures
    assert any(path.name == "npn_bjt__right.png" for path in fixtures)


def test_symbol_probe_render_contains_visible_content_for_vertical_capacitor() -> None:
    image = render_tex_symbol_probe_image("capacitor", "vertical")
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

    assert int((gray < 245).sum()) > 0


def test_current_checked_in_mos_fixtures_are_straight_and_have_no_extra_connection() -> None:
    for shape in ("nmos", "pmos"):
        fixture = cv2.imread(str(DEFAULT_TEX_SYMBOL_GOLDEN_DIR / f"{shape}__right.png"), cv2.IMREAD_GRAYSCALE)
        assert fixture is not None

        result = _compare_tex_mos_geometry(f"{shape}__right", shape, fixture)

        assert result.passed, result.notes


def test_symbol_probe_pdf_contains_drawings_for_npn_bjt() -> None:
    pdf_path = _compile_tex_snippet_pdf(
        render_circuitikz_ir(build_circuitikz_ir(build_symbol_probe_geometry("npn_bjt", "right"))),
        stem="probe_npn_bjt_right",
    )

    assert _extract_pdf_texts(pdf_path)
    image = _pdf_page_to_image(pdf_path, dpi=300)
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    assert int((gray < 245).sum()) > 0


def test_tex_symbol_golden_fixtures_are_not_blank() -> None:
    fixtures = sorted(DEFAULT_TEX_SYMBOL_GOLDEN_DIR.glob("*.png"))

    assert fixtures
    for path in fixtures:
        image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        assert image is not None
        assert int((image < 220).sum()) > 0, f"blank golden fixture: {path.name}"


def test_tex_symbol_golden_validation_passes_for_checked_in_fixtures() -> None:
    status = check_validation_runtime_dependencies()

    assert status.pdflatex_available
    assert status.pdf_raster_available

    results = validate_rendered_tex_symbol_goldens()

    assert results
    assert all(result.passed for result in results)


def test_cmos_inverter_rendered_mos_regions_are_straight_and_three_terminal() -> None:
    results = validate_rendered_tex_example_mos_geometry([cmos_inverter()])

    assert results
    assert all(result.passed for result in results)


def test_cmos_inverter_rendered_mos_crop_finds_reference_anchor() -> None:
    snippet = export_circuitikz(cmos_inverter())
    pdf_path = _compile_tex_snippet_pdf(snippet, stem="cmos_inverter_mos_crop")
    image = _pdf_page_to_image(pdf_path, dpi=300)
    observed = _extract_pdf_texts(pdf_path)
    geometry = _compiled_geometry(cmos_inverter())
    transform = _estimate_tex_raster_transform(geometry, observed)

    mn1 = next(shape for shape in geometry.shapes if shape.ref == "MN1")
    crop = _crop_rendered_mos_region(image, transform, mn1.center)

    assert crop is not None
    assert crop.size > 0
