from __future__ import annotations

import numpy as np

from examples.specs.catalog import cmos_inverter
from mixedsig2cad.exporters.tex import export_circuitikz
from mixedsig2cad.importers.hybrid_parser import check_validation_runtime_dependencies
from mixedsig2cad.projections.tex_render_validate import (
    RenderedPdfText,
    _compare_rendered_tex_labels,
    _compare_tex_page_clipping,
    _compare_tex_transistors,
    _compiled_geometry,
)
from mixedsig2cad.models import BoundingBox


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


def test_tex_transistor_validation_rejects_rectangular_fallback() -> None:
    geometry = _compiled_geometry(cmos_inverter())
    text = export_circuitikz(cmos_inverter()).replace("circle", "ellipse", 1).replace(
        r"\draw ({\msx + -0.70},{\msy + 0.00}) -- ({\msx + -0.32},{\msy + 0.00});",
        r"\draw ({\msx + -0.56},{\msy + 0.39}) rectangle ({\msx + 0.56},{\msy + -0.39});",
        1,
    )

    results = _compare_tex_transistors(geometry, text)

    assert any(not result.passed for result in results)
