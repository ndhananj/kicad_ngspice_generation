from __future__ import annotations

from ..geometry import _place_ground, _place_shape_from_component, _standard_texts, _terminal_point
from ..intent import IntentPattern, SchematicIntent
from ..models import CompiledSchematic, GeometryNode, Point, TerminalRef


def build_rc_lowpass(intent: SchematicIntent, pattern: IntentPattern) -> CompiledSchematic:
    by_ref = {comp.ref: comp for comp in intent.components}
    source = by_ref[pattern.components["source"]]
    series = by_ref[pattern.components["series"]]
    shunt = by_ref[pattern.components["shunt"]]

    geometry = CompiledSchematic(name=intent.name)
    source_shape = _place_shape_from_component(source, Point(50.0, 78.0), orientation="vertical_up")
    resistor_shape = _place_shape_from_component(series, Point(90.0, 70.38), orientation="horizontal")
    capacitor_shape = _place_shape_from_component(shunt, Point(96.35, 89.08), orientation="vertical")
    source_gnd = _place_ground("#PWR0001", Point(50.0, 95.62))
    cap_gnd = _place_ground("#PWR0002", Point(96.35, 108.08))
    geometry.shapes.extend([source_shape, resistor_shape, capacitor_shape, source_gnd, cap_gnd])
    geometry.nodes.extend(
        [
            GeometryNode(
                id="vin_path",
                point=Point(70.0, 70.38),
                attachments=(TerminalRef(source_shape.ref, "pos"), TerminalRef(resistor_shape.ref, "left")),
                label=pattern.nets["input"],
            ),
            GeometryNode(
                id="vout_node",
                point=Point(96.35, 70.38),
                attachments=(TerminalRef(resistor_shape.ref, "right"), TerminalRef(capacitor_shape.ref, "top")),
                label=pattern.nets["node"],
                render_style="junction",
            ),
            GeometryNode(
                id="source_ground",
                point=_terminal_point(source_gnd, "top"),
                attachments=(TerminalRef(source_shape.ref, "neg"), TerminalRef(source_gnd.ref, "top")),
            ),
            GeometryNode(
                id="cap_ground",
                point=_terminal_point(cap_gnd, "top"),
                attachments=(TerminalRef(capacitor_shape.ref, "bottom"), TerminalRef(cap_gnd.ref, "top")),
            ),
        ]
    )
    geometry.labels.extend(_standard_texts(source_shape))
    geometry.labels.extend(_standard_texts(resistor_shape))
    geometry.labels.extend(_standard_texts(capacitor_shape))
    return geometry


def build_rc_highpass(intent: SchematicIntent, pattern: IntentPattern) -> CompiledSchematic:
    by_ref = {comp.ref: comp for comp in intent.components}
    source = by_ref[pattern.components["source"]]
    series = by_ref[pattern.components["series"]]
    shunt = by_ref[pattern.components["shunt"]]

    geometry = CompiledSchematic(name=intent.name)
    source_shape = _place_shape_from_component(source, Point(50.0, 78.0), orientation="vertical_up")
    capacitor_shape = _place_shape_from_component(series, Point(90.0, 70.38), orientation="horizontal")
    resistor_shape = _place_shape_from_component(shunt, Point(106.35, 98.73), orientation="vertical")
    source_gnd = _place_ground("#PWR0001", Point(50.0, 95.62))
    resistor_gnd = _place_ground("#PWR0002", Point(106.35, 115.08))
    geometry.shapes.extend([source_shape, capacitor_shape, resistor_shape, source_gnd, resistor_gnd])
    geometry.nodes.extend(
        [
            GeometryNode(
                id="vin_path",
                point=Point(70.0, 70.38),
                attachments=(TerminalRef(source_shape.ref, "pos"), TerminalRef(capacitor_shape.ref, "left")),
                label=pattern.nets["input"],
            ),
            GeometryNode(
                id="vmid_node",
                point=Point(106.35, 82.38),
                attachments=(TerminalRef(capacitor_shape.ref, "right"), TerminalRef(resistor_shape.ref, "top")),
                label=pattern.nets["node"],
                render_style="junction",
            ),
            GeometryNode(
                id="source_ground",
                point=_terminal_point(source_gnd, "top"),
                attachments=(TerminalRef(source_shape.ref, "neg"), TerminalRef(source_gnd.ref, "top")),
            ),
            GeometryNode(
                id="res_ground",
                point=_terminal_point(resistor_gnd, "top"),
                attachments=(TerminalRef(resistor_shape.ref, "bottom"), TerminalRef(resistor_gnd.ref, "top")),
            ),
        ]
    )
    geometry.labels.extend(_standard_texts(source_shape))
    geometry.labels.extend(_standard_texts(capacitor_shape))
    geometry.labels.extend(_standard_texts(resistor_shape))
    return geometry
