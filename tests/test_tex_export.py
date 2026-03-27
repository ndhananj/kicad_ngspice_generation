from __future__ import annotations

from examples.specs.catalog import all_examples, bjt_common_emitter, cmos_inverter, opamp_inverting, rc_lowpass
from mixedsig2cad import (
    TexReportBundle,
    TexSvgInclude,
    TexDocument,
    TexDrawing,
    build_circuitikz_ir,
    build_example_report_bundle,
    build_examples_master_bundle,
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


def test_circuitikz_export_prunes_duplicate_passive_and_ground_labels() -> None:
    text = export_circuitikz(rc_lowpass())

    assert r"to[V,l={DC 5},t={V1}]" in text
    assert r"to[R,l={1k},t={R1}]" in text
    assert r"to[C,l={100n},t={C1}]" in text
    assert r"\node[font=\scriptsize] at (5.21,-7.75) {V1};" not in text
    assert r"\node[font=\scriptsize] at (5.33,-9.53) {DC 5};" not in text
    assert r"\node[font=\scriptsize] at (9.02,-7.37) {R1};" not in text
    assert r"\node[font=\scriptsize] at (9.02,-8.13) {1k};" not in text
    assert r"\node[font=\scriptsize] at (9.65,-9.27) {C1};" not in text
    assert r"\node[font=\scriptsize] at (9.65,-10.03) {100n};" not in text
    assert "GND" not in text


def test_general_circuitikz_export_uses_component_refs_for_component_labels() -> None:
    text = render_circuitikz_ir(build_circuitikz_ir(rc_lowpass(), label_mode="general"))

    assert r"to[V,l={V1},t={V1}]" in text
    assert r"to[R,l={R1},t={R1}]" in text
    assert r"to[C,l={C1},t={C1}]" in text
    assert "DC 5" not in text
    assert "1k" not in text
    assert "100n" not in text
    assert "vin" in text
    assert "vout" in text


def test_circuitikz_export_removes_ground_text_in_all_examples() -> None:
    for example in all_examples():
        assert "GND" not in export_circuitikz(example)


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
    assert r"\providecommand{\msCircuitMixedSigPmosSymbol}[4]" in rendered
    assert r"\node[nmos]" not in rendered
    assert r"\node[pmos]" not in rendered


def test_general_circuitikz_export_uses_refs_for_active_device_labels() -> None:
    cmos_text = render_circuitikz_ir(build_circuitikz_ir(cmos_inverter(), label_mode="general"))
    opamp_text = render_circuitikz_ir(build_circuitikz_ir(opamp_inverting(), label_mode="general"))

    assert r"\msCircuitMixedSigNmosSymbol{16.00}{-13.72}{MN1}{}" in cmos_text
    assert r"\msCircuitMixedSigPmosSymbol{16.00}{-8.89}{MP1}{}" in cmos_text
    assert r"\draw (16.51,-14.22)" not in cmos_text
    assert r"\draw (16.51,-8.38)" not in cmos_text
    assert "PM1" not in cmos_text
    assert "NM1" not in cmos_text
    assert "{XU1}" in opamp_text
    assert "OPAMP" not in opamp_text


def test_bjt_circuitikz_export_uses_native_npn_node() -> None:
    text = render_circuitikz_ir(build_circuitikz_ir(bjt_common_emitter(), label_mode="general"))

    assert r"\node[npn]" in text
    assert r"\providecommand{\msCircuitMixedSigNpnBjtSymbol}[4]" not in text
    assert r"\msCircuitMixedSigNpnBjtSymbol" not in text


def test_tex_report_builder_returns_document_ir_with_drawings() -> None:
    document = build_tex_report(cmos_inverter())

    assert isinstance(document, TexDocument)
    assert document.title == "cmos_inverter"
    assert document.sections[0].title == "Readable Circuit"
    assert document.sections[0].body is None
    assert document.sections[0].subsections[0].title == "General Readable Circuit"
    assert isinstance(document.sections[0].subsections[0].body, TexDrawing)
    assert document.sections[0].subsections[1].title == "Specific Readable Circuit"
    assert isinstance(document.sections[0].subsections[1].body, TexDrawing)
    assert document.sections[1].title == "KiCad SVG Reference"
    assert isinstance(document.sections[1].body, TexSvgInclude)
    assert document.sections[1].body.path.endswith("cmos_inverter")


def test_standalone_report_contains_expected_sections_and_starter_notes() -> None:
    text = export_example_report_tex(cmos_inverter())

    assert text.startswith(r"\documentclass")
    assert r"\section{Readable Circuit}" in text
    assert r"\subsection{General Readable Circuit}" in text
    assert r"\subsection{Specific Readable Circuit}" in text
    assert r"\section{KiCad SVG Reference}" in text
    assert r"\section{Reference Summary}" in text
    assert r"\section{Design Notes}" in text
    assert r"\providecommand{\msCircuitMixedSigNmosSymbol}[4]" in text
    assert r"\providecommand{\MixedSigIncludeKicadSvg}[2]" in text
    assert r"\msCircuitMixedSigNmosSymbol" in text
    assert r"\msCircuitMixedSigPmosSymbol" in text
    assert r"\MixedSigIncludeKicadSvg[\linewidth]{../svg/cmos_inverter}" in text
    assert "Replace these starter notes" in text


def test_reference_summary_uses_instantiated_catalog_values() -> None:
    text = export_example_report_tex(opamp_inverting())

    assert "RIN &amp;" not in text
    assert "RIN" in text
    assert "100k" in text
    assert "tran 0.1ms 10ms" in text
    assert ".subckt OPAMP 1 2 6 4 5" in text


def test_master_report_inputs_each_example_report() -> None:
    text = export_examples_master_report([rc_lowpass(), opamp_inverting(), cmos_inverter()])

    assert r"\tableofcontents" in text
    assert r"\section{rc\_lowpass}" in text
    assert r"\section{opamp\_inverting}" in text
    assert r"\section{cmos\_inverter}" in text
    assert r"\providecommand{\msCircuitMixedSigNmosSymbol}[4]" in text
    assert r"\msCircuitMixedSigNmosSymbol" in text
    assert text.count(r"\subsubsection{General Readable Circuit}") == 3
    assert text.count(r"\subsubsection{Specific Readable Circuit}") == 3
    assert text.count(r"\subsection{KiCad SVG Reference}") == 3


def test_example_report_bundle_writes_modular_files() -> None:
    bundle = build_example_report_bundle(cmos_inverter())

    assert isinstance(bundle, TexReportBundle)
    paths = {file.path for file in bundle.files}
    assert bundle.entrypoint == "cmos_inverter.tex"
    assert "common/packages.tex" in paths
    assert "common/macros.tex" in paths
    assert "fragments/cmos_inverter/readable_base.tex" in paths
    assert "fragments/cmos_inverter/readable_general.tex" in paths
    assert "fragments/cmos_inverter/readable_specific.tex" in paths
    assert "fragments/cmos_inverter/summary.tex" in paths
    assert "fragments/cmos_inverter/notes.tex" in paths
    readable_base = next(
        file.content for file in bundle.files if file.path == "fragments/cmos_inverter/readable_base.tex"
    )
    readable_general = next(
        file.content
        for file in bundle.files
        if file.path == "fragments/cmos_inverter/readable_general.tex"
    )
    readable_specific = next(
        file.content
        for file in bundle.files
        if file.path == "fragments/cmos_inverter/readable_specific.tex"
    )
    assert r"\MixedSigReadableValueLabel{VDD}{DC 3.3}" in readable_base
    assert r"\MixedSigReadableTransistorSecondary{MN1}{NM1}" in readable_base
    assert r"\renewcommand{\MixedSigReadableValueLabel}[2]{#1}" in readable_general
    assert r"\renewcommand{\MixedSigReadableDeviceText}[2]{#1}" in readable_general
    assert r"\input{fragments/cmos_inverter/readable_base.tex}" in readable_general
    assert r"\input{fragments/cmos_inverter/readable_base.tex}" in readable_specific
    assert r"\renewcommand{\MixedSigReadableValueLabel}[2]{#1}" not in readable_specific
    entrypoint = next(file.content for file in bundle.files if file.path == bundle.entrypoint)
    assert r"\input{common/packages.tex}" in entrypoint
    assert r"\input{fragments/cmos_inverter/readable_general.tex}" in entrypoint
    assert r"\input{fragments/cmos_inverter/readable_specific.tex}" in entrypoint
    assert r"\MixedSigIncludeKicadSvg[\linewidth]{../svg/cmos_inverter}" in entrypoint


def test_master_report_bundle_reuses_common_files() -> None:
    bundle = build_examples_master_bundle([rc_lowpass(), cmos_inverter()])

    paths = {file.path for file in bundle.files}
    assert bundle.entrypoint == "examples.tex"
    assert "common/packages.tex" in paths
    assert "common/macros.tex" in paths
    assert "fragments/rc_lowpass/readable_base.tex" in paths
    assert "fragments/rc_lowpass/readable_general.tex" in paths
    assert "fragments/rc_lowpass/readable_specific.tex" in paths
    assert "fragments/cmos_inverter/notes.tex" in paths
    entrypoint = next(file.content for file in bundle.files if file.path == bundle.entrypoint)
    assert r"\tableofcontents" in entrypoint
    assert r"\input{fragments/rc_lowpass/readable_general.tex}" in entrypoint
    assert r"\input{fragments/rc_lowpass/readable_specific.tex}" in entrypoint
    assert r"\MixedSigIncludeKicadSvg[\linewidth]{../svg/rc_lowpass}" in entrypoint
