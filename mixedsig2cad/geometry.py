from __future__ import annotations

from dataclasses import dataclass, field

from .intent import IntentComponent, IntentPattern, SchematicIntent


@dataclass(frozen=True, slots=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class PlacedTerminal:
    name: str
    point: Point


@dataclass(frozen=True, slots=True)
class PlacedShape:
    ref: str
    value: str
    shape: str
    orientation: str
    center: Point
    terminals: tuple[PlacedTerminal, ...]
    hidden_reference: bool = False


@dataclass(frozen=True, slots=True)
class TerminalRef:
    owner_ref: str
    terminal_name: str


@dataclass(frozen=True, slots=True)
class GeometryNode:
    id: str
    point: Point
    attachments: tuple[TerminalRef, ...]
    render_style: str = "inline"
    label: str | None = None


@dataclass(frozen=True, slots=True)
class WirePath:
    points: tuple[Point, ...]
    uuid_seed: str


@dataclass(frozen=True, slots=True)
class TextPlacement:
    text: str
    role: str
    position: Point
    owner_ref: str
    uuid_seed: str


@dataclass(frozen=True, slots=True)
class JunctionPlacement:
    point: Point


@dataclass(slots=True)
class SchematicGeometry:
    name: str
    shapes: list[PlacedShape] = field(default_factory=list)
    nodes: list[GeometryNode] = field(default_factory=list)
    wires: list[WirePath] = field(default_factory=list)
    labels: list[TextPlacement] = field(default_factory=list)
    junctions: list[JunctionPlacement] = field(default_factory=list)


SHAPE_GROUP_X = {
    "source": 50.0,
    "passive": 100.0,
    "active": 150.0,
}

SHAPE_GROUP_Y = {
    "source": 70.0,
    "passive": 70.0,
    "active": 90.0,
}

SHAPE_GROUP_STEP_Y = {
    "source": 40.0,
    "passive": 38.0,
    "active": 48.0,
}


GENERIC_SHAPES: dict[tuple[str, str], dict[str, tuple[float, float]]] = {
    ("voltage_source", "vertical_up"): {"pos": (0.0, -7.62), "neg": (0.0, 7.62)},
    ("current_source", "vertical_up"): {"pos": (0.0, -10.16), "neg": (0.0, 10.16)},
    ("resistor", "horizontal"): {"left": (-6.35, 0.0), "right": (6.35, 0.0)},
    ("resistor", "vertical"): {"top": (0.0, -6.35), "bottom": (0.0, 6.35)},
    ("capacitor", "vertical"): {"top": (0.0, -6.35), "bottom": (0.0, 6.35)},
    ("capacitor", "horizontal"): {"left": (-6.35, 0.0), "right": (6.35, 0.0)},
    ("inductor", "horizontal"): {"left": (-6.35, 0.0), "right": (6.35, 0.0)},
    ("diode", "horizontal"): {"left": (-5.08, 0.0), "right": (5.08, 0.0)},
    ("ground", "down"): {"top": (0.0, 0.0)},
    ("power", "up"): {"bottom": (0.0, 0.0)},
    ("opamp", "right"): {
        "plus": (-7.62, 2.54),
        "minus": (-7.62, -2.54),
        "out": (7.62, 0.0),
        "vplus": (-2.54, 7.62),
        "vminus": (-2.54, -7.62),
    },
    ("npn_bjt", "right"): {"collector": (3.81, -8.89), "base": (-7.62, 0.0), "emitter": (3.81, 8.89)},
    ("pmos", "right"): {"drain": (2.54, -5.08), "gate": (-5.08, 0.0), "source": (2.54, 5.08), "body": (5.08, 5.08)},
    ("nmos", "right"): {"drain": (2.54, 5.08), "gate": (-5.08, 0.0), "source": (2.54, -5.08), "body": (5.08, -5.08)},
}


def build_schematic_geometry(intent: SchematicIntent) -> SchematicGeometry:
    for pattern in intent.patterns:
        if pattern.kind == "rc_lowpass":
            return _finalize_geometry(_build_rc_lowpass_geometry(intent, pattern))
        if pattern.kind == "rc_highpass":
            return _finalize_geometry(_build_rc_highpass_geometry(intent, pattern))
    return _finalize_geometry(_build_fallback_geometry(intent))


def validate_schematic_geometry(geometry: SchematicGeometry) -> None:
    shape_by_ref = {shape.ref: shape for shape in geometry.shapes}
    point_usage: dict[tuple[float, float], int] = {}
    for wire in geometry.wires:
        if len(wire.points) < 2:
            raise AssertionError(f"wire path '{wire.uuid_seed}' has fewer than 2 points")
        for point in (wire.points[0], wire.points[-1]):
            key = (point.x, point.y)
            point_usage[key] = point_usage.get(key, 0) + 1

    junction_points = {(junction.point.x, junction.point.y) for junction in geometry.junctions}
    for junction_point in junction_points:
        if junction_point not in {(node.point.x, node.point.y) for node in geometry.nodes}:
            raise AssertionError(f"junction at {junction_point} does not correspond to a geometry node")

    for node in geometry.nodes:
        if len(node.attachments) < 2:
            raise AssertionError(f"node '{node.id}' has fewer than 2 attachments")
        attachment_points = [_resolve_terminal_ref(shape_by_ref, attachment) for attachment in node.attachments]
        if len({(point.x, point.y) for point in attachment_points}) == 1 and (
            attachment_points[0].x != node.point.x or attachment_points[0].y != node.point.y
        ):
            raise AssertionError(f"node '{node.id}' attachments coincide away from node point")
        for point in attachment_points:
            if point.x == node.point.x and point.y == node.point.y:
                continue
            key = (point.x, point.y)
            if key not in point_usage:
                raise AssertionError(f"node '{node.id}' terminal at {key} is not covered by compiled wires")
        if node.render_style == "junction" or len(node.attachments) >= 3:
            key = (node.point.x, node.point.y)
            if key not in junction_points:
                raise AssertionError(f"node '{node.id}' expected a visible junction")


def _finalize_geometry(geometry: SchematicGeometry) -> SchematicGeometry:
    _compile_nodes_to_wires(geometry)
    validate_schematic_geometry(geometry)
    return geometry


def _build_rc_lowpass_geometry(intent: SchematicIntent, pattern: IntentPattern) -> SchematicGeometry:
    by_ref = {comp.ref: comp for comp in intent.components}
    source = by_ref[pattern.components["source"]]
    series = by_ref[pattern.components["series"]]
    shunt = by_ref[pattern.components["shunt"]]

    geometry = SchematicGeometry(name=intent.name)
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
                attachments=(
                    TerminalRef(source_shape.ref, "pos"),
                    TerminalRef(resistor_shape.ref, "left"),
                ),
            ),
            GeometryNode(
                id="vout_node",
                point=Point(96.35, 70.38),
                attachments=(
                    TerminalRef(resistor_shape.ref, "right"),
                    TerminalRef(capacitor_shape.ref, "top"),
                ),
                render_style="junction",
            ),
            GeometryNode(
                id="source_ground",
                point=_terminal_point(source_gnd, "top"),
                attachments=(
                    TerminalRef(source_shape.ref, "neg"),
                    TerminalRef(source_gnd.ref, "top"),
                ),
            ),
            GeometryNode(
                id="cap_ground",
                point=_terminal_point(cap_gnd, "top"),
                attachments=(
                    TerminalRef(capacitor_shape.ref, "bottom"),
                    TerminalRef(cap_gnd.ref, "top"),
                ),
            ),
        ]
    )
    geometry.labels.extend(_standard_texts(source_shape))
    geometry.labels.extend(_standard_texts(resistor_shape))
    geometry.labels.extend(_standard_texts(capacitor_shape))
    return geometry


def _build_rc_highpass_geometry(intent: SchematicIntent, pattern: IntentPattern) -> SchematicGeometry:
    by_ref = {comp.ref: comp for comp in intent.components}
    source = by_ref[pattern.components["source"]]
    series = by_ref[pattern.components["series"]]
    shunt = by_ref[pattern.components["shunt"]]

    geometry = SchematicGeometry(name=intent.name)
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
                attachments=(
                    TerminalRef(source_shape.ref, "pos"),
                    TerminalRef(capacitor_shape.ref, "left"),
                ),
            ),
            GeometryNode(
                id="vmid_node",
                point=Point(106.35, 82.38),
                attachments=(
                    TerminalRef(capacitor_shape.ref, "right"),
                    TerminalRef(resistor_shape.ref, "top"),
                ),
                render_style="junction",
            ),
            GeometryNode(
                id="source_ground",
                point=_terminal_point(source_gnd, "top"),
                attachments=(
                    TerminalRef(source_shape.ref, "neg"),
                    TerminalRef(source_gnd.ref, "top"),
                ),
            ),
            GeometryNode(
                id="res_ground",
                point=_terminal_point(resistor_gnd, "top"),
                attachments=(
                    TerminalRef(resistor_shape.ref, "bottom"),
                    TerminalRef(resistor_gnd.ref, "top"),
                ),
            ),
        ]
    )
    geometry.labels.extend(_standard_texts(source_shape))
    geometry.labels.extend(_standard_texts(capacitor_shape))
    geometry.labels.extend(_standard_texts(resistor_shape))
    return geometry


def _build_fallback_geometry(intent: SchematicIntent) -> SchematicGeometry:
    geometry = SchematicGeometry(name=intent.name)
    shapes_by_ref: dict[str, PlacedShape] = {}
    counts = {"source": 0, "passive": 0, "active": 0}

    for comp in intent.components:
        group = _component_group(comp.kind)
        x = SHAPE_GROUP_X[group]
        y = SHAPE_GROUP_Y[group] + counts[group] * SHAPE_GROUP_STEP_Y[group]
        counts[group] += 1
        shape = _place_shape_from_component(comp, Point(x, y))
        shapes_by_ref[comp.ref] = shape
        geometry.shapes.append(shape)
        geometry.labels.extend(_standard_texts(shape))

    power_ref_idx = 1
    net_attachments: dict[str, list[TerminalRef]] = {}
    net_points: dict[str, list[Point]] = {}

    for comp in intent.components:
        shape = shapes_by_ref[comp.ref]
        for pin_index, net_name in enumerate(comp.nodes):
            terminal_name = _component_terminal_name(comp.kind, shape, pin_index)
            point = _terminal_point(shape, terminal_name)
            role = intent.nets[net_name].role
            if role == "ground":
                ref = f"#PWR{power_ref_idx:04d}"
                power_ref_idx += 1
                gnd_shape = _place_ground(ref, Point(point.x, point.y + 12.0))
                geometry.shapes.append(gnd_shape)
                geometry.nodes.append(
                    GeometryNode(
                        id=f"{ref}:ground",
                        point=_terminal_point(gnd_shape, "top"),
                        attachments=(TerminalRef(shape.ref, terminal_name), TerminalRef(gnd_shape.ref, "top")),
                    )
                )
                continue
            if role == "supply":
                ref = f"#PWR{power_ref_idx:04d}"
                power_ref_idx += 1
                power_shape = _place_power(ref, net_name.upper(), Point(point.x, point.y - 12.0))
                geometry.shapes.append(power_shape)
                geometry.nodes.append(
                    GeometryNode(
                        id=f"{ref}:supply",
                        point=_terminal_point(power_shape, "bottom"),
                        attachments=(TerminalRef(shape.ref, terminal_name), TerminalRef(power_shape.ref, "bottom")),
                    )
                )
                continue
            net_attachments.setdefault(net_name, []).append(TerminalRef(shape.ref, terminal_name))
            net_points.setdefault(net_name, []).append(point)

    for net_name, attachments in sorted(net_attachments.items()):
        points = net_points[net_name]
        if len(points) < 2:
            continue
        geometry.nodes.append(
            GeometryNode(
                id=f"net:{net_name}",
                point=_choose_node_point(net_name, points),
                attachments=tuple(attachments),
                render_style="junction" if len(attachments) >= 3 else "inline",
            )
        )
    return geometry


def _compile_nodes_to_wires(geometry: SchematicGeometry) -> None:
    shape_by_ref = {shape.ref: shape for shape in geometry.shapes}
    for node in geometry.nodes:
        attachment_points = [_resolve_terminal_ref(shape_by_ref, attachment) for attachment in node.attachments]
        distinct_points = {(point.x, point.y) for point in attachment_points}
        if node.render_style == "junction" or len(node.attachments) >= 3:
            geometry.junctions.append(JunctionPlacement(point=node.point))
        if len(distinct_points) == 1 and next(iter(distinct_points)) == (node.point.x, node.point.y):
            continue
        for idx, point in enumerate(attachment_points, start=1):
            if point.x == node.point.x and point.y == node.point.y:
                continue
            path_points = _route_to_node(point, node.point)
            geometry.wires.append(WirePath(points=path_points, uuid_seed=f"{geometry.name}:{node.id}:{idx}"))


def _route_to_node(start: Point, node_point: Point) -> tuple[Point, ...]:
    if start.x == node_point.x or start.y == node_point.y:
        return (start, node_point)
    elbow = Point(node_point.x, start.y)
    return (start, elbow, node_point)


def _resolve_terminal_ref(shape_by_ref: dict[str, PlacedShape], terminal_ref: TerminalRef) -> Point:
    shape = shape_by_ref.get(terminal_ref.owner_ref)
    if shape is None:
        raise AssertionError(f"unknown shape '{terminal_ref.owner_ref}' in geometry node")
    return _terminal_point(shape, terminal_ref.terminal_name)


def _choose_node_point(net_name: str, points: list[Point]) -> Point:
    if len(points) == 2:
        p1, p2 = points
        if p1.x == p2.x or p1.y == p2.y:
            return Point(round((p1.x + p2.x) / 2.0, 2), round((p1.y + p2.y) / 2.0, 2))
        return Point(round((p1.x + p2.x) / 2.0, 2), round((p1.y + p2.y) / 2.0, 2))
    y_min = min(point.y for point in points)
    y_max = max(point.y for point in points)
    x_min = min(point.x for point in points)
    x_max = max(point.x for point in points)
    lowered = net_name.lower()
    if lowered in {"vcc", "vdd", "vee"}:
        y = round(y_min - 10.0, 2)
    elif lowered in {"0", "gnd", "vss"}:
        y = round(y_max + 10.0, 2)
    else:
        y = round(min(point.y for point in points) - 10.0, 2)
    x = round((x_min + x_max) / 2.0, 2)
    return Point(x, y)


def _place_shape_from_component(comp: IntentComponent, center: Point, orientation: str | None = None) -> PlacedShape:
    shape_name, default_orientation = _shape_for_component(comp)
    actual_orientation = orientation or default_orientation
    terminals = _make_terminals(shape_name, actual_orientation, center)
    return PlacedShape(
        ref=comp.ref,
        value=comp.value,
        shape=shape_name,
        orientation=actual_orientation,
        center=center,
        terminals=terminals,
    )


def _shape_for_component(comp: IntentComponent) -> tuple[str, str]:
    if comp.kind == "V":
        return ("voltage_source", "vertical_up")
    if comp.kind == "I":
        return ("current_source", "vertical_up")
    if comp.kind == "R":
        return ("resistor", "horizontal")
    if comp.kind == "C":
        return ("capacitor", "vertical")
    if comp.kind == "L":
        return ("inductor", "horizontal")
    if comp.kind == "D":
        return ("diode", "horizontal")
    if comp.kind == "Q":
        return ("npn_bjt", "right")
    if comp.kind == "X":
        return ("opamp", "right")
    if comp.kind == "M":
        hint = f"{comp.value} {comp.model or ''}".lower()
        return ("nmos", "right") if "nm" in hint or "nmos" in hint else ("pmos", "right")
    return ("resistor", "horizontal")


def _place_ground(ref: str, center: Point) -> PlacedShape:
    return PlacedShape(
        ref=ref,
        value="GND",
        shape="ground",
        orientation="down",
        center=center,
        terminals=_make_terminals("ground", "down", center),
        hidden_reference=True,
    )


def _place_power(ref: str, value: str, center: Point) -> PlacedShape:
    return PlacedShape(
        ref=ref,
        value=value,
        shape="power",
        orientation="up",
        center=center,
        terminals=_make_terminals("power", "up", center),
        hidden_reference=True,
    )


def _make_terminals(shape: str, orientation: str, center: Point) -> tuple[PlacedTerminal, ...]:
    offsets = GENERIC_SHAPES[(shape, orientation)]
    return tuple(
        PlacedTerminal(name=name, point=Point(round(center.x + dx, 2), round(center.y + dy, 2)))
        for name, (dx, dy) in offsets.items()
    )


def _terminal_point(shape: PlacedShape, terminal_name: str) -> Point:
    for terminal in shape.terminals:
        if terminal.name == terminal_name:
            return terminal.point
    raise AssertionError(f"terminal '{terminal_name}' not found on shape '{shape.ref}'")


def _component_terminal_name(kind: str, shape: PlacedShape, pin_index: int) -> str:
    terminal_order = {
        "V": ("pos", "neg"),
        "I": ("pos", "neg"),
        "R": ("left", "right") if shape.orientation == "horizontal" else ("top", "bottom"),
        "C": ("top", "bottom") if shape.orientation == "vertical" else ("left", "right"),
        "L": ("left", "right"),
        "D": ("left", "right"),
        "Q": ("collector", "base", "emitter"),
        "X": ("plus", "minus", "out", "vplus", "vminus"),
        "M": ("drain", "gate", "source", "body"),
    }.get(kind, tuple(terminal.name for terminal in shape.terminals))
    return terminal_order[min(pin_index, len(terminal_order) - 1)]


def _component_group(kind: str) -> str:
    if kind in {"V", "I"}:
        return "source"
    if kind in {"R", "C", "L", "D"}:
        return "passive"
    return "active"


def _standard_texts(shape: PlacedShape) -> list[TextPlacement]:
    if shape.shape in {"resistor", "capacitor", "inductor", "diode"}:
        ref_pos = Point(shape.center.x, shape.center.y - 8.0)
        value_pos = Point(shape.center.x, shape.center.y + 8.0)
    elif shape.shape in {"ground", "power"}:
        ref_pos = Point(shape.center.x, shape.center.y - 4.0)
        value_pos = Point(shape.center.x, shape.center.y + 4.0)
    else:
        ref_pos = Point(shape.center.x, shape.center.y - 10.0)
        value_pos = Point(shape.center.x, shape.center.y + 10.0)
    return [
        TextPlacement(
            text=shape.ref,
            role="reference",
            position=ref_pos,
            owner_ref=shape.ref,
            uuid_seed=f"text:{shape.ref}:ref",
        ),
        TextPlacement(
            text=shape.value,
            role="value",
            position=value_pos,
            owner_ref=shape.ref,
            uuid_seed=f"text:{shape.ref}:value",
        ),
    ]
