from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from mixedsig2cad.compiled import compile_schematic
from mixedsig2cad.design import ExampleDesign, circuit_of
from mixedsig2cad.exporters.tex_ir import (
    TexBundleFile,
    TexDocument,
    TexDocumentSection,
    TexDrawing,
    TexInput,
    TexReportBundle,
    TexSvgInclude,
    TexSymbolDefinition,
)
from mixedsig2cad.intent import build_schematic_intent
from mixedsig2cad.layout_compiler import compile_design
from mixedsig2cad.models import CompiledSchematic, PlacedShape, Point, TextPlacement
from mixedsig2cad.projections.kicad import project_geometry_to_kicad
from mixedsig2cad.spec import CircuitSpec
from mixedsig2cad.symbols import body_box, default_orientation_for_shape, terminal_defs


SCALE = 0.1
DOCUMENT_PACKAGES = (
    r"\usepackage[margin=1in]{geometry}",
    r"\usepackage[T1]{fontenc}",
    r"\usepackage{graphicx}",
    r"\usepackage{svg}",
    r"\usepackage{tikz}",
    r"\usepackage[american]{circuitikz}",
    r"\usepackage{longtable}",
    r"\usepackage{hyperref}",
)
SHARED_TEX_MACROS = (
    r"\svgsetup{inkscape=false,inkscapeversion=1,inkscapelatex=false}",
    r"\providecommand{\MixedSigIncludeKicadSvg}[2][\linewidth]{%",
    r"  \begin{center}",
    r"  \IfFileExists{#2.pdf}{\includegraphics[width=#1]{#2.pdf}}{\includesvg[width=#1]{#2}}",
    r"  \end{center}",
    r"}",
    r"\providecommand{\MixedSigReadableValueLabel}[2]{#2}",
    r"\providecommand{\MixedSigReadableDeviceText}[2]{#1\\#2}",
    r"\providecommand{\MixedSigReadableTransistorSecondary}[2]{#2}",
)
DEFAULT_REPORT_SVG_PATH = "../svg/{name}"
ReadableLabelMode = Literal["specific", "general", "templated"]


@dataclass(frozen=True, slots=True)
class ReportSections:
    general_circuitikz: TexDrawing
    specific_circuitikz: TexDrawing
    kicad_reference: TexSvgInclude
    summary: str
    starter_notes: str


@dataclass(frozen=True, slots=True)
class TransistorSymbolSpec:
    shape: str
    macro_stem: str


TRANSISTOR_SYMBOLS: dict[str, TransistorSymbolSpec] = {
    "nmos": TransistorSymbolSpec(shape="nmos", macro_stem="MixedSigNmos"),
    "pmos": TransistorSymbolSpec(shape="pmos", macro_stem="MixedSigPmos"),
    "npn_bjt": TransistorSymbolSpec(shape="npn_bjt", macro_stem="MixedSigNpnBjt"),
}


def export_circuitikz(spec: ExampleDesign | CircuitSpec) -> str:
    return render_circuitikz_ir(build_circuitikz_ir(spec))


def export_literal_tikz(spec: ExampleDesign | CircuitSpec) -> str:
    return render_literal_tikz_ir(build_literal_tikz_ir(spec))


def export_example_report_tex(spec: ExampleDesign | CircuitSpec) -> str:
    return render_tex_document(build_tex_report(spec))


def export_examples_master_report(specs: list[ExampleDesign | CircuitSpec]) -> str:
    return render_tex_document(build_examples_master_report(specs))


def build_example_report_bundle(
    source: ExampleDesign | CircuitSpec,
    *,
    common_dir: str = "common",
    fragments_dir: str = "fragments",
    svg_dir: str = "../svg",
) -> TexReportBundle:
    geometry = _compiled_geometry(source)
    spec = circuit_of(source)
    fragment_root = f"{fragments_dir}/{geometry.name}"
    sections = _report_sections(spec, geometry, kicad_svg_path=f"{svg_dir}/{geometry.name}")
    files = (
        TexBundleFile(path=f"{common_dir}/packages.tex", content=_shared_packages_tex()),
        TexBundleFile(path=f"{common_dir}/macros.tex", content=_shared_macros_tex()),
        TexBundleFile(
            path=f"{fragment_root}/readable_base.tex",
            content=render_circuitikz_ir(build_circuitikz_ir(geometry, label_mode="templated")) + "\n",
        ),
        TexBundleFile(
            path=f"{fragment_root}/readable_general.tex",
            content=_readable_variant_wrapper_tex(fragment_root, label_mode="general"),
        ),
        TexBundleFile(
            path=f"{fragment_root}/readable_specific.tex",
            content=_readable_variant_wrapper_tex(fragment_root, label_mode="specific"),
        ),
        TexBundleFile(path=f"{fragment_root}/summary.tex", content=sections.summary + "\n"),
        TexBundleFile(path=f"{fragment_root}/notes.tex", content=sections.starter_notes + "\n"),
        TexBundleFile(path=f"{geometry.name}.tex", content=_render_example_bundle_entrypoint(geometry.name, common_dir, fragment_root, sections.kicad_reference)),
    )
    return TexReportBundle(entrypoint=f"{geometry.name}.tex", files=files)


def build_examples_master_bundle(
    specs: list[ExampleDesign | CircuitSpec],
    *,
    common_dir: str = "common",
    fragments_dir: str = "fragments",
    svg_dir: str = "../svg",
) -> TexReportBundle:
    files: dict[str, str] = {
        f"{common_dir}/packages.tex": _shared_packages_tex(),
        f"{common_dir}/macros.tex": _shared_macros_tex(),
    }
    section_blocks: list[str] = []
    for source in specs:
        geometry = _compiled_geometry(source)
        spec = circuit_of(source)
        fragment_root = f"{fragments_dir}/{geometry.name}"
        sections = _report_sections(spec, geometry, kicad_svg_path=f"{svg_dir}/{geometry.name}")
        files[f"{fragment_root}/readable_base.tex"] = (
            render_circuitikz_ir(build_circuitikz_ir(geometry, label_mode="templated")) + "\n"
        )
        files[f"{fragment_root}/readable_general.tex"] = _readable_variant_wrapper_tex(
            fragment_root,
            label_mode="general",
        )
        files[f"{fragment_root}/readable_specific.tex"] = _readable_variant_wrapper_tex(
            fragment_root,
            label_mode="specific",
        )
        files[f"{fragment_root}/summary.tex"] = sections.summary + "\n"
        files[f"{fragment_root}/notes.tex"] = sections.starter_notes + "\n"
        section_blocks.append(_render_master_example_block(geometry.name, fragment_root, sections.kicad_reference))
    files["examples.tex"] = _render_master_bundle_entrypoint(common_dir, section_blocks)
    rendered_files = tuple(TexBundleFile(path=path, content=content) for path, content in sorted(files.items()))
    return TexReportBundle(entrypoint="examples.tex", files=rendered_files)


def build_circuitikz_ir(
    source: ExampleDesign | CircuitSpec | CompiledSchematic,
    *,
    label_mode: ReadableLabelMode = "specific",
) -> TexDrawing:
    geometry = _compiled_geometry(source)
    return TexDrawing(
        environment="circuitikz",
        options=("american voltages", "scale=1", "transform shape"),
        symbol_definitions=_transistor_symbol_definitions(geometry, dialect="circuitikz"),
        body_lines=tuple(
            [
                *_render_circuitikz_shapes(geometry, label_mode=label_mode),
                *_render_circuitikz_wires(geometry),
                *_render_circuitikz_labels(geometry),
            ]
        ),
    )


def build_literal_tikz_ir(source: ExampleDesign | CircuitSpec | CompiledSchematic) -> TexDrawing:
    geometry = _compiled_geometry(source)
    projection = project_geometry_to_kicad(geometry)
    lines: list[str] = []
    for wire in projection.wires:
        lines.append(rf"  \draw ({wire.x1:.2f},{wire.y1:.2f}) -- ({wire.x2:.2f},{wire.y2:.2f});")
    for junction in projection.junctions:
        lines.append(rf"  \fill ({junction.x:.2f},{junction.y:.2f}) circle (1.2pt);")
    for symbol in geometry.shapes:
        lines.extend(_render_literal_shape(symbol))
    for text in geometry.labels:
        rendered = _render_literal_text(text)
        if rendered:
            lines.append(rendered)
    return TexDrawing(
        environment="tikzpicture",
        options=("x=0.1cm", "y=-0.1cm", "line cap=round", "line join=round"),
        symbol_definitions=_transistor_symbol_definitions(geometry, dialect="literal"),
        body_lines=tuple(lines),
    )


def build_tex_report(source: ExampleDesign | CircuitSpec, *, kicad_svg_path: str | None = None) -> TexDocument:
    geometry = _compiled_geometry(source)
    spec = circuit_of(source)
    sections = _report_sections(
        spec,
        geometry,
        kicad_svg_path=kicad_svg_path or DEFAULT_REPORT_SVG_PATH.format(name=geometry.name),
    )
    return TexDocument(
        title=geometry.name,
        packages=DOCUMENT_PACKAGES,
        sections=(
            TexDocumentSection(
                title="Readable Circuit",
                subsections=(
                    TexDocumentSection(title="General Readable Circuit", body=sections.general_circuitikz),
                    TexDocumentSection(title="Specific Readable Circuit", body=sections.specific_circuitikz),
                ),
            ),
            TexDocumentSection(title="KiCad SVG Reference", body=sections.kicad_reference),
            TexDocumentSection(title="Reference Summary", body=sections.summary),
            TexDocumentSection(title="Design Notes", body=sections.starter_notes),
        ),
    )


def build_examples_master_report(
    specs: list[ExampleDesign | CircuitSpec],
    *,
    svg_path_template: str = DEFAULT_REPORT_SVG_PATH,
) -> TexDocument:
    sections: list[TexDocumentSection] = []
    for spec in specs:
        circuit_spec = circuit_of(spec)
        geometry = _compiled_geometry(spec)
        report_sections = _report_sections(
            circuit_spec,
            geometry,
            kicad_svg_path=svg_path_template.format(name=geometry.name),
        )
        sections.append(
            TexDocumentSection(
                title=_latex_escape(circuit_spec.name),
                subsections=(
                    TexDocumentSection(
                        title="Readable Circuit",
                        subsections=(
                            TexDocumentSection(
                                title="General Readable Circuit",
                                body=report_sections.general_circuitikz,
                            ),
                            TexDocumentSection(
                                title="Specific Readable Circuit",
                                body=report_sections.specific_circuitikz,
                            ),
                        ),
                    ),
                    TexDocumentSection(title="KiCad SVG Reference", body=report_sections.kicad_reference),
                    TexDocumentSection(title="Reference Summary", body=report_sections.summary),
                    TexDocumentSection(title="Design Notes", body=report_sections.starter_notes + "\n\\clearpage"),
                ),
            )
        )
    return TexDocument(
        title="mixedsig2cad Example Reports",
        packages=DOCUMENT_PACKAGES,
        include_table_of_contents=True,
        sections=tuple(sections),
    )


def render_tex_document(document: TexDocument) -> str:
    lines = [r"\documentclass[11pt]{article}", *document.packages, *SHARED_TEX_MACROS]
    lines.extend(
        [
            r"\title{" + _latex_escape(document.title) + r"}",
            r"\author{" + _latex_escape(document.author) + r"}",
            r"\date{" + document.date_expr + r"}",
            r"\begin{document}",
            r"\maketitle",
        ]
    )
    if document.include_table_of_contents:
        lines.append(r"\tableofcontents")
    for section in document.sections:
        lines.extend(_render_document_section(section, level=1))
    lines.append(r"\end{document}")
    return "\n".join(lines) + "\n"


def render_circuitikz_ir(drawing: TexDrawing) -> str:
    return render_tex_drawing(drawing)


def render_literal_tikz_ir(drawing: TexDrawing) -> str:
    return render_tex_drawing(drawing)


def render_tex_drawing(drawing: TexDrawing) -> str:
    lines = [*_render_symbol_definitions(drawing.symbol_definitions)]
    options = ",".join(drawing.options)
    lines.append(rf"\begin{{{drawing.environment}}}[{options}]")
    lines.extend(drawing.body_lines)
    lines.append(rf"\end{{{drawing.environment}}}")
    return "\n".join(lines)


def render_circuitikz(geometry: CompiledSchematic) -> str:
    return render_circuitikz_ir(build_circuitikz_ir(geometry))


def render_literal_tikz(geometry: CompiledSchematic) -> str:
    return render_literal_tikz_ir(build_literal_tikz_ir(geometry))


def _compiled_geometry(source: ExampleDesign | CircuitSpec | CompiledSchematic) -> CompiledSchematic:
    if isinstance(source, CompiledSchematic):
        return source
    if isinstance(source, ExampleDesign):
        return compile_design(source)
    intent = build_schematic_intent(circuit_of(source))
    return compile_schematic(intent)


def _report_sections(spec: CircuitSpec, geometry: CompiledSchematic, *, kicad_svg_path: str) -> ReportSections:
    return ReportSections(
        general_circuitikz=build_circuitikz_ir(geometry, label_mode="general"),
        specific_circuitikz=build_circuitikz_ir(geometry, label_mode="specific"),
        kicad_reference=TexSvgInclude(path=kicad_svg_path),
        summary=_reference_section(spec),
        starter_notes=_starter_notes(spec),
    )


def _shared_packages_tex() -> str:
    return "\n".join(DOCUMENT_PACKAGES) + "\n"


def _shared_macros_tex() -> str:
    return "\n".join(SHARED_TEX_MACROS) + "\n"


def _readable_variant_wrapper_tex(fragment_root: str, *, label_mode: ReadableLabelMode) -> str:
    if label_mode == "general":
        lines = [
            r"\begingroup",
            r"\renewcommand{\MixedSigReadableValueLabel}[2]{#1}",
            r"\renewcommand{\MixedSigReadableDeviceText}[2]{#1}",
            r"\renewcommand{\MixedSigReadableTransistorSecondary}[2]{}",
            rf"\input{{{fragment_root}/readable_base.tex}}",
            r"\endgroup",
        ]
        return "\n".join(lines) + "\n"
    if label_mode == "specific":
        lines = [
            r"\begingroup",
            rf"\input{{{fragment_root}/readable_base.tex}}",
            r"\endgroup",
        ]
        return "\n".join(lines) + "\n"
    raise AssertionError(f"unsupported readable variant wrapper mode {label_mode}")


def _render_example_bundle_entrypoint(
    name: str,
    common_dir: str,
    fragment_root: str,
    kicad_reference: TexSvgInclude,
) -> str:
    lines = [
        r"\documentclass[11pt]{article}",
        rf"\input{{{common_dir}/packages.tex}}",
        rf"\input{{{common_dir}/macros.tex}}",
        rf"\title{{{_latex_escape(name)}}}",
        r"\author{Generated by mixedsig2cad}",
        r"\date{\today}",
        r"\begin{document}",
        r"\maketitle",
        r"\section{Readable Circuit}",
        r"\subsection{General Readable Circuit}",
        rf"\input{{{fragment_root}/readable_general.tex}}",
        r"\subsection{Specific Readable Circuit}",
        rf"\input{{{fragment_root}/readable_specific.tex}}",
        r"\section{KiCad SVG Reference}",
        _render_svg_include(kicad_reference),
        r"\section{Reference Summary}",
        rf"\input{{{fragment_root}/summary.tex}}",
        r"\section{Design Notes}",
        rf"\input{{{fragment_root}/notes.tex}}",
        r"\end{document}",
    ]
    return "\n".join(lines) + "\n"


def _render_master_bundle_entrypoint(common_dir: str, section_blocks: list[str]) -> str:
    lines = [
        r"\documentclass[11pt]{article}",
        rf"\input{{{common_dir}/packages.tex}}",
        rf"\input{{{common_dir}/macros.tex}}",
        r"\title{mixedsig2cad Example Reports}",
        r"\author{Generated by mixedsig2cad}",
        r"\date{\today}",
        r"\begin{document}",
        r"\maketitle",
        r"\tableofcontents",
        *section_blocks,
        r"\end{document}",
    ]
    return "\n".join(lines) + "\n"


def _render_master_example_block(name: str, fragment_root: str, kicad_reference: TexSvgInclude) -> str:
    lines = [
        rf"\section{{{_latex_escape(name)}}}",
        r"\subsection{Readable Circuit}",
        r"\subsubsection{General Readable Circuit}",
        rf"\input{{{fragment_root}/readable_general.tex}}",
        r"\subsubsection{Specific Readable Circuit}",
        rf"\input{{{fragment_root}/readable_specific.tex}}",
        r"\subsection{KiCad SVG Reference}",
        _render_svg_include(kicad_reference),
        r"\subsection{Reference Summary}",
        rf"\input{{{fragment_root}/summary.tex}}",
        r"\subsection{Design Notes}",
        rf"\input{{{fragment_root}/notes.tex}}",
        r"\clearpage",
    ]
    return "\n".join(lines)


def _render_circuitikz_shapes(geometry: CompiledSchematic, *, label_mode: ReadableLabelMode) -> list[str]:
    lines: list[str] = []
    for shape in geometry.shapes:
        if shape.shape == "resistor":
            lines.append(_two_terminal(shape, "R", label_mode=label_mode))
        elif shape.shape == "capacitor":
            lines.append(_two_terminal(shape, "C", label_mode=label_mode))
        elif shape.shape == "inductor":
            lines.append(_two_terminal(shape, "L", label_mode=label_mode))
        elif shape.shape == "diode":
            lines.append(_two_terminal(shape, "Do", label_mode=label_mode))
        elif shape.shape == "voltage_source":
            lines.append(_two_terminal(shape, "V", label_mode=label_mode))
        elif shape.shape == "current_source":
            lines.append(_two_terminal(shape, "I", label_mode=label_mode))
        elif shape.shape == "ground":
            lines.append(_ground(shape))
        elif shape.shape == "power":
            lines.append(_power(shape))
        elif shape.shape == "opamp":
            lines.extend(_device_box(shape, label_mode=label_mode))
        elif shape.shape == "npn_bjt":
            lines.extend(_native_circuitikz_npn_symbol(shape, label_mode=label_mode))
        elif shape.shape == "pmos":
            lines.append(_transistor_symbol_call(shape, dialect="circuitikz", label_mode=label_mode))
        elif shape.shape == "nmos":
            lines.append(_transistor_symbol_call(shape, dialect="circuitikz", label_mode=label_mode))
        else:
            lines.extend(_device_box(shape, label_mode=label_mode))
    return lines


def _render_circuitikz_wires(geometry: CompiledSchematic) -> list[str]:
    lines: list[str] = []
    for wire in geometry.wires:
        if len(wire.points) < 2:
            continue
        coords = " -- ".join(_pt(point) for point in wire.points)
        lines.append(rf"  \draw {coords};")
    for junction in geometry.junctions:
        lines.append(rf"  \fill {_pt(junction.point)} circle (1.2pt);")
    return lines


def _render_circuitikz_labels(geometry: CompiledSchematic) -> list[str]:
    lines: list[str] = []
    for text in _visible_readable_labels(geometry):
        anchor = text.anchor_position if text.anchor_position is not None else text.position
        label = _latex_escape(text.text)
        lines.append(rf"  \node[font=\scriptsize] at {_pt(anchor)} {{{label}}};")
    return lines


def _visible_readable_labels(geometry: CompiledSchematic) -> list[TextPlacement]:
    shape_by_ref = {shape.ref: shape for shape in geometry.shapes}
    visible: list[TextPlacement] = []
    for text in geometry.labels:
        if not _is_visible_readable_label(text, shape_by_ref):
            continue
        visible.append(text)
    return visible


def _is_visible_readable_label(text: TextPlacement, shape_by_ref: dict[str, PlacedShape]) -> bool:
    owner = shape_by_ref.get(text.owner_ref)
    if text.role == "net_label":
        return text.text.strip().lower() != "gnd"
    if owner is None:
        return False
    if owner.ref.startswith("#PWR") or owner.ref.startswith("#SUPPORT"):
        return False
    if owner.shape in {
        "resistor",
        "capacitor",
        "inductor",
        "diode",
        "voltage_source",
        "current_source",
        "ground",
        "power",
        "opamp",
        "npn_bjt",
        "pmos",
        "nmos",
    }:
        return False
    return text.role in {"reference", "value"} and not owner.hidden_reference


def _render_literal_shape(shape: PlacedShape) -> list[str]:
    if shape.shape in TRANSISTOR_SYMBOLS:
        return [_transistor_symbol_call(shape, dialect="literal")]
    left = shape.body_box.left
    top = shape.body_box.top
    right = shape.body_box.right
    bottom = shape.body_box.bottom
    cx = shape.center.x
    cy = shape.center.y
    label = _latex_escape(f"{shape.ref} {shape.value}")
    if shape.shape in {"resistor", "capacitor", "inductor", "diode"}:
        return [
            rf"  \draw ({left:.2f},{top:.2f}) rectangle ({right:.2f},{bottom:.2f});",
            rf"  \node[font=\scriptsize,align=center] at ({cx:.2f},{cy:.2f}) {{{label}}};",
        ]
    if shape.shape in {"voltage_source", "current_source"}:
        radius = max(right - left, bottom - top) / 2
        return [
            rf"  \draw ({cx:.2f},{cy:.2f}) circle ({radius:.2f});",
            rf"  \node[font=\scriptsize,align=center] at ({cx:.2f},{cy:.2f}) {{{label}}};",
        ]
    if shape.shape == "ground":
        return [
            rf"  \draw ({cx:.2f},{top:.2f}) -- ({cx:.2f},{bottom:.2f});",
            rf"  \draw ({cx - 2.00:.2f},{bottom - 1.50:.2f}) -- ({cx + 2.00:.2f},{bottom - 1.50:.2f});",
            rf"  \node[font=\scriptsize] at ({cx:.2f},{bottom + 3.00:.2f}) {{{_latex_escape(shape.ref)}}};",
        ]
    return [
        rf"  \draw ({left:.2f},{top:.2f}) rectangle ({right:.2f},{bottom:.2f});",
        rf"  \node[font=\scriptsize,align=center] at ({cx:.2f},{cy:.2f}) {{{label}}};",
    ]


def _render_literal_text(text: TextPlacement) -> str:
    if text.role == "reference" and text.owner_ref.startswith("#SUPPORT"):
        return ""
    return rf"  \node[font=\scriptsize] at ({text.position.x:.2f},{text.position.y:.2f}) {{{_latex_escape(text.text)}}};"


def _two_terminal(shape: PlacedShape, element: str, *, label_mode: ReadableLabelMode) -> str:
    a, b = shape.terminals[:2]
    if label_mode == "templated":
        options = [f"l={{{_templated_component_value(shape)}}}"]
    else:
        options = [f"l={{{_latex_escape(_displayed_component_value(shape, label_mode=label_mode))}}}"]
    if not shape.hidden_reference:
        options.append(f"t={{{_latex_escape(shape.ref)}}}")
    return rf"  \draw {_pt(a.point)} to[{element},{','.join(options)}] {_pt(b.point)};"


def _ground(shape: PlacedShape) -> str:
    terminal = shape.terminals[0]
    return rf"  \draw {_pt(terminal.point)} node[ground] {{}};"


def _power(shape: PlacedShape) -> str:
    terminal = shape.terminals[0]
    return rf"  \node[font=\scriptsize,anchor=south] at {_pt(terminal.point)} {{{_latex_escape(shape.value)}}};"


def _device_box(shape: PlacedShape, *, label_mode: ReadableLabelMode) -> list[str]:
    lines = [
        rf"  \draw ({shape.body_box.left * SCALE:.2f},{-shape.body_box.top * SCALE:.2f}) rectangle ({shape.body_box.right * SCALE:.2f},{-shape.body_box.bottom * SCALE:.2f});",
        rf"  \node[font=\scriptsize,align=center] at {_pt(shape.center)} {_device_box_text(shape, label_mode=label_mode)};",
    ]
    for terminal in shape.terminals:
        edge = _point_on_box(shape, terminal.point)
        lines.append(rf"  \draw {_pt(terminal.point)} -- {_pt(edge)};")
    return lines


def _transistor_symbol_definitions(geometry: CompiledSchematic, *, dialect: str) -> tuple[TexSymbolDefinition, ...]:
    definitions: list[TexSymbolDefinition] = []
    seen_shapes: set[str] = set()
    for shape in geometry.shapes:
        if shape.shape not in TRANSISTOR_SYMBOLS or shape.shape in seen_shapes:
            continue
        if dialect == "circuitikz" and shape.shape == "npn_bjt":
            continue
        seen_shapes.add(shape.shape)
        definitions.append(_build_transistor_symbol_definition(shape.shape, dialect=dialect))
    return tuple(definitions)


def _build_transistor_symbol_definition(shape_name: str, *, dialect: str) -> TexSymbolDefinition:
    spec = TRANSISTOR_SYMBOLS[shape_name]
    orientation = default_orientation_for_shape(shape_name)
    _, _, _, _ = body_box(shape_name, orientation)
    label = r"{#3\\#4}" if dialect == "circuitikz" else r"{#3 #4}"
    if shape_name == "npn_bjt":
        body_lines = (
            r"  \pgfmathsetmacro{\msx}{#1}",
            r"  \pgfmathsetmacro{\msy}{#2}",
            *_transistor_line_commands(
                (
                    ((-5.08, 0.0), (-1.60, 0.0)),
                    ((-1.60, -4.00), (-1.60, 4.00)),
                    ((-1.60, -1.20), (3.00, -5.00)),
                    ((-1.60, 1.20), (2.00, 4.80)),
                    ((0.80, 3.60), (2.00, 4.80)),
                    ((1.40, 2.10), (2.00, 4.80)),
                    ((0.80, -8.20), (3.00, -5.00)),
                    ((4.80, 0.0), (2.00, 4.80)),
                ),
                dialect=dialect,
            ),
            rf"  \node[font=\scriptsize,align=center] at ({{\msx + 0.00}},{{\msy + {_tex_dimension(-10.50, dialect=dialect):.2f}}}) {label};",
        )
    elif shape_name == "nmos":
        body_lines = (
            r"  \pgfmathsetmacro{\msx}{#1}",
            r"  \pgfmathsetmacro{\msy}{#2}",
            *_transistor_line_commands(
                (
                    ((-7.00, 0.0), (-3.20, 0.0)),
                    ((-1.80, -4.60), (-1.80, 4.60)),
                    ((1.80, -4.60), (1.80, 4.60)),
                    ((-3.20, 0.0), (-3.20, 4.20)),
                    ((-3.20, -4.20), (-3.20, 0.0)),
                    ((1.80, -8.80), (1.80, -4.60)),
                    ((1.80, 4.60), (1.80, 8.80)),
                    ((4.80, 0.0), (1.80, 0.0)),
                    ((0.20, 1.80), (1.80, 0.0)),
                    ((0.20, -1.80), (1.80, 0.0)),
                ),
                dialect=dialect,
            ),
            rf"  \node[font=\scriptsize,align=center] at ({{\msx + 0.00}},{{\msy + {_tex_dimension(-10.80, dialect=dialect):.2f}}}) {label};",
        )
    elif shape_name == "pmos":
        bubble_radius = _tex_dimension(0.90, dialect=dialect)
        body_lines = (
            r"  \pgfmathsetmacro{\msx}{#1}",
            r"  \pgfmathsetmacro{\msy}{#2}",
            *_transistor_line_commands(
                (
                    ((-7.40, 0.0), (-4.20, 0.0)),
                    ((-1.80, -4.60), (-1.80, 4.60)),
                    ((1.80, -4.60), (1.80, 4.60)),
                    ((-4.20, 0.0), (-4.20, 4.20)),
                    ((-4.20, -4.20), (-4.20, 0.0)),
                    ((1.80, -8.80), (1.80, -4.60)),
                    ((1.80, 4.60), (1.80, 8.80)),
                    ((4.80, 0.0), (1.80, 0.0)),
                    ((0.20, 1.80), (1.80, 0.0)),
                    ((0.20, -1.80), (1.80, 0.0)),
                ),
                dialect=dialect,
            ),
            rf"  \draw ({{\msx + {_tex_dimension(-3.20, dialect=dialect):.2f}}},{{\msy + 0.00}}) circle ({bubble_radius:.2f});",
            rf"  \node[font=\scriptsize,align=center] at ({{\msx + 0.00}},{{\msy + {_tex_dimension(-10.80, dialect=dialect):.2f}}}) {label};",
        )
    else:
        raise AssertionError(f"unsupported transistor TeX macro shape {shape_name}")
    return TexSymbolDefinition(
        name=_transistor_macro_name(spec, dialect=dialect),
        parameter_count=4,
        body_lines=body_lines,
    )


def _transistor_symbol_call(
    shape: PlacedShape,
    *,
    dialect: str,
    label_mode: ReadableLabelMode = "specific",
) -> str:
    if dialect == "circuitikz" and shape.shape == "npn_bjt":
        raise AssertionError("npn_bjt circuitikz export uses native node rendering")
    spec = TRANSISTOR_SYMBOLS[shape.shape]
    x, y = _tex_point_values(shape.center, dialect=dialect)
    primary_label, secondary_label = _transistor_symbol_labels(shape, label_mode=label_mode)
    if label_mode == "templated":
        rendered_primary = primary_label
        rendered_secondary = secondary_label
    else:
        rendered_primary = _latex_escape(primary_label)
        rendered_secondary = _latex_escape(secondary_label)
    return (
        rf"  \{_transistor_macro_name(spec, dialect=dialect)}"
        rf"{{{x:.2f}}}{{{y:.2f}}}{{{rendered_primary}}}{{{rendered_secondary}}}"
    )


def _transistor_macro_name(spec: TransistorSymbolSpec, *, dialect: str) -> str:
    prefix = "msCircuit" if dialect == "circuitikz" else "msLiteral"
    return f"{prefix}{spec.macro_stem}Symbol"


def _native_circuitikz_npn_symbol(shape: PlacedShape, *, label_mode: ReadableLabelMode) -> list[str]:
    by_name = {terminal.name: terminal.point for terminal in shape.terminals}
    collector = by_name["collector"]
    emitter = by_name["emitter"]
    base = by_name["base"]
    node_center = Point(
        x=(collector.x + emitter.x) / 2.0,
        y=(collector.y + emitter.y) / 2.0,
    )
    node_name = _tikz_safe_name(shape.ref)
    primary_label, secondary_label = _transistor_symbol_labels(shape, label_mode=label_mode)
    if label_mode == "templated":
        rendered_primary = primary_label
        rendered_secondary = secondary_label
    else:
        rendered_primary = _latex_escape(primary_label)
        rendered_secondary = _latex_escape(secondary_label)
    rendered_label = (
        "{" + rendered_primary + "}"
        if not rendered_secondary
        else "{" + rendered_primary + r"\\" + rendered_secondary + "}"
    )
    lines = [
        rf"  \node[npn] ({node_name}) at {_pt(node_center)} {{}};",
        rf"  \draw {_pt(base)} -- ({node_name}.B);",
        rf"  \draw {_pt(collector)} -- ({node_name}.C);",
        rf"  \draw {_pt(emitter)} -- ({node_name}.E);",
        rf"  \node[font=\scriptsize,align=center] at ({node_name}.text) {rendered_label};",
    ]
    return lines


def _tikz_safe_name(text: str) -> str:
    sanitized = "".join(char if char.isalnum() else "_" for char in text)
    return f"msNode{sanitized or 'unnamed'}"


def _tex_point_values(point: Point, *, dialect: str) -> tuple[float, float]:
    if dialect == "circuitikz":
        return (point.x * SCALE, -point.y * SCALE)
    return (point.x, point.y)


def _tex_offset(x: float, y: float, *, dialect: str) -> tuple[float, float]:
    if dialect == "circuitikz":
        return (x * SCALE, -y * SCALE)
    return (x, y)


def _tex_dimension(value: float, *, dialect: str) -> float:
    return value * SCALE if dialect == "circuitikz" else value


def _transistor_line_commands(
    segments: tuple[tuple[tuple[float, float], tuple[float, float]], ...],
    *,
    dialect: str,
) -> tuple[str, ...]:
    commands: list[str] = []
    for start, end in segments:
        start_x, start_y = _tex_offset(start[0], start[1], dialect=dialect)
        end_x, end_y = _tex_offset(end[0], end[1], dialect=dialect)
        commands.append(
            rf"  \draw ({{\msx + {start_x:.2f}}},{{\msy + {start_y:.2f}}}) -- ({{\msx + {end_x:.2f}}},{{\msy + {end_y:.2f}}});"
        )
    return tuple(commands)


def _render_symbol_definitions(definitions: tuple[TexSymbolDefinition, ...]) -> list[str]:
    lines: list[str] = []
    for definition in definitions:
        lines.append(rf"\providecommand{{\{definition.name}}}[{definition.parameter_count}]{{%")
        lines.extend(definition.body_lines)
        lines.append("}")
    return lines


def _render_document_section(section: TexDocumentSection, *, level: int) -> list[str]:
    command = {1: "section", 2: "subsection", 3: "subsubsection"}.get(level, "paragraph")
    lines = [rf"\{command}{{{section.title}}}"]
    if section.body is not None:
        lines.append(_render_section_body(section.body))
    for subsection in section.subsections:
        lines.extend(_render_document_section(subsection, level=level + 1))
    return lines


def _render_section_body(body: str | TexDrawing | TexSvgInclude | TexInput) -> str:
    if isinstance(body, TexDrawing):
        drawing = render_tex_drawing(body)
        return "\n".join(
            [
                r"\begin{center}",
                r"\resizebox{\linewidth}{!}{%",
                drawing,
                r"}",
                r"\end{center}",
            ]
        )
    if isinstance(body, TexSvgInclude):
        return _render_svg_include(body)
    if isinstance(body, TexInput):
        return rf"\input{{{body.path}}}"
    return body


def _render_svg_include(include: TexSvgInclude) -> str:
    return rf"\MixedSigIncludeKicadSvg[{include.width}]{{{include.path}}}"


def _reference_section(spec: CircuitSpec) -> str:
    lines = [
        r"\begin{longtable}{p{0.16\linewidth}p{0.18\linewidth}p{0.30\linewidth}p{0.22\linewidth}}",
        r"\textbf{Ref} & \textbf{Kind} & \textbf{Value / Model} & \textbf{Nodes}\\",
        r"\hline",
    ]
    for component in spec.components:
        value = component.model or component.value
        lines.append(
            " & ".join(
                [
                    _latex_escape(component.ref),
                    _latex_escape(component.kind),
                    _latex_escape(value),
                    _latex_escape(", ".join(component.nodes)),
                ]
            )
            + r"\\"
        )
    lines.extend(
        [
            r"\end{longtable}",
            "",
            r"\paragraph{Model Statements}",
        ]
    )
    if spec.models:
        lines.append(r"\begin{itemize}")
        for model_line in spec.models:
            lines.append(rf"  \item \texttt{{{_latex_escape(model_line)}}}")
        lines.append(r"\end{itemize}")
    else:
        lines.append("No model statements defined.")
    lines.extend(
        [
            "",
            r"\paragraph{Analyses}",
        ]
    )
    if spec.analyses:
        lines.append(r"\begin{itemize}")
        for analysis in spec.analyses:
            lines.append(rf"  \item \texttt{{{_latex_escape(analysis.command)}}}")
        lines.append(r"\end{itemize}")
    else:
        lines.append("No analyses defined.")
    return "\n".join(lines)


def _starter_notes(spec: CircuitSpec) -> str:
    lines = [
        r"\subsection*{Overview}",
        _latex_escape(_overview_sentence(spec)),
        "",
        r"\subsection*{Operating Notes}",
        r"\begin{itemize}",
    ]
    for sentence in _operating_notes(spec):
        lines.append(r"  \item " + _latex_escape(sentence))
    lines.extend(
        [
            r"\end{itemize}",
            r"\subsection*{Design Notes To Edit}",
            r"\begin{itemize}",
            r"  \item Replace these starter notes with intended operating limits, tuning guidance, and simulation expectations.",
            r"  \item Record any KiCad-specific layout conventions that should stay aligned with the generated schematic.",
            r"  \item Add usage notes for the ngspice analyses that matter for this example.",
            r"\end{itemize}",
        ]
    )
    return "\n".join(lines)


def _overview_sentence(spec: CircuitSpec) -> str:
    kind_names = [_kind_display_name(component.kind) for component in spec.components]
    dominant = ", ".join(kind_names[:3])
    if len(kind_names) > 3:
        dominant += ", and related support parts"
    return f"This generated example captures the {spec.name.replace('_', ' ')} circuit using {dominant}."


def _operating_notes(spec: CircuitSpec) -> list[str]:
    notes = [
        f"Primary simulation commands: {', '.join(analysis.command for analysis in spec.analyses) or 'none specified'}.",
        f"Component count: {len(spec.components)} active entries in the shared CircuitSpec.",
    ]
    named_nodes = sorted({node for component in spec.components for node in component.nodes if node != '0'})
    if named_nodes:
        notes.append(f"Named nets to review during edits: {', '.join(named_nodes[:6])}.")
    if spec.models:
        notes.append(f"Custom device models are embedded for {len(spec.models)} statements.")
    return notes


def _kind_display_name(kind: str) -> str:
    return {
        "V": "voltage sources",
        "I": "current sources",
        "R": "resistors",
        "C": "capacitors",
        "L": "inductors",
        "D": "diodes",
        "Q": "BJTs",
        "X": "subcircuits",
        "M": "MOS devices",
    }.get(kind, kind)


def _pt(point: Point) -> str:
    return f"({point.x * SCALE:.2f},{-point.y * SCALE:.2f})"


def _displayed_component_value(shape: PlacedShape, *, label_mode: ReadableLabelMode) -> str:
    if label_mode == "general":
        return shape.ref
    if label_mode == "templated":
        return _templated_component_value(shape)
    return shape.value


def _transistor_symbol_labels(shape: PlacedShape, *, label_mode: ReadableLabelMode) -> tuple[str, str]:
    if label_mode == "general":
        return (shape.ref, "")
    if label_mode == "templated":
        return (
            _latex_escape(shape.ref),
            rf"\MixedSigReadableTransistorSecondary{{{_latex_escape(shape.ref)}}}{{{_latex_escape(shape.value)}}}",
        )
    return (shape.ref, shape.value)


def _device_box_text(shape: PlacedShape, *, label_mode: ReadableLabelMode) -> str:
    if label_mode == "general":
        return "{" + _latex_escape(shape.ref) + "}"
    if label_mode == "templated":
        return (
            "{"
            + rf"\MixedSigReadableDeviceText{{{_latex_escape(shape.ref)}}}{{{_latex_escape(shape.value)}}}"
            + "}"
        )
    return "{" + _latex_escape(shape.ref) + r"\\" + _latex_escape(shape.value) + "}"


def _templated_component_value(shape: PlacedShape) -> str:
    return rf"\MixedSigReadableValueLabel{{{_latex_escape(shape.ref)}}}{{{_latex_escape(shape.value)}}}"


def _point_on_box(shape: PlacedShape, point: Point) -> Point:
    x = min(max(point.x, shape.body_box.left), shape.body_box.right)
    y = min(max(point.y, shape.body_box.top), shape.body_box.bottom)
    return Point(x=x, y=y)


def _latex_escape(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in text)
