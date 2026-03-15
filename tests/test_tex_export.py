from __future__ import annotations

from examples.specs.catalog import cmos_inverter, opamp_inverting, rc_lowpass
from mixedsig2cad import (
    TexDocument,
    TexDrawing,
    build_circuitikz_ir,
    build_tex_report,
    export_circuitikz,
    export_example_report_tex,
    export_examples_master_report,
    export_literal_tikz,
    render_circuitikz_ir,
)


def test_circuitikz_export_contains_expected_environments_and_labels() -> None:
    text = export_circuitikz(rc_lowpass())

    assert r"\begin{circuitikz}" in text
    assert "to[R" in text
    assert "to[C" in text
    assert "vin" in text
    assert "vout" in text


def test_literal_tikz_export_contains_expected_draw_commands() -> None:
    text = export_literal_tikz(opamp_inverting())

    assert r"\begin{tikzpicture}" in text
    assert r"\draw" in text
    assert "XU1 OPAMP" in text
    assert "vminus" in text


def test_circuitikz_ir_exposes_reusable_transistor_symbol_definitions() -> None:
    drawing = build_circuitikz_ir(cmos_inverter())

    assert isinstance(drawing, TexDrawing)
    names = {definition.name for definition in drawing.symbol_definitions}
    assert "msCircuitMixedSigNmosSymbol" in names
    assert "msCircuitMixedSigPmosSymbol" in names

    rendered = render_circuitikz_ir(drawing)
    assert r"\providecommand{\msCircuitMixedSigNmosSymbol}[4]" in rendered
    assert r"\msCircuitMixedSigNmosSymbol" in rendered
    assert r"\providecommand{\msCircuitMixedSigPmosSymbol}[4]" in rendered
    assert r"\msCircuitMixedSigPmosSymbol" in rendered


def test_tex_report_builder_returns_document_ir_with_drawings() -> None:
    document = build_tex_report(cmos_inverter())

    assert isinstance(document, TexDocument)
    assert document.title == "cmos_inverter"
    assert document.sections[0].title == "Readable Circuit"
    assert isinstance(document.sections[0].body, TexDrawing)
    assert document.sections[1].title == "Literal KiCad Reference"
    assert isinstance(document.sections[1].body, TexDrawing)


def test_standalone_report_contains_expected_sections_and_starter_notes() -> None:
    text = export_example_report_tex(cmos_inverter())

    assert text.startswith(r"\documentclass")
    assert r"\section{Readable Circuit}" in text
    assert r"\section{Literal KiCad Reference}" in text
    assert r"\section{Reference Summary}" in text
    assert r"\section{Design Notes}" in text
    assert r"\providecommand{\msCircuitMixedSigNmosSymbol}[4]" in text
    assert r"\providecommand{\msLiteralMixedSigPmosSymbol}[4]" in text
    assert "Replace these starter notes" in text


def test_master_report_inputs_each_example_report() -> None:
    text = export_examples_master_report([rc_lowpass(), opamp_inverting(), cmos_inverter()])

    assert r"\tableofcontents" in text
    assert r"\section{rc\_lowpass}" in text
    assert r"\section{opamp\_inverting}" in text
    assert r"\section{cmos\_inverter}" in text
    assert r"\providecommand{\msCircuitMixedSigNmosSymbol}[4]" in text
