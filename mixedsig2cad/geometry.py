from __future__ import annotations

from dataclasses import dataclass, field

from .intent import IntentComponent, IntentPattern, SchematicIntent


@dataclass(frozen=True, slots=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class BoundingBox:
    left: float
    top: float
    right: float
    bottom: float


@dataclass(frozen=True, slots=True)
class PlacedTerminal:
    name: str
    point: Point
    side: str


@dataclass(frozen=True, slots=True)
class PlacedShape:
    ref: str
    value: str
    shape: str
    orientation: str
    center: Point
    terminals: tuple[PlacedTerminal, ...]
    body_box: BoundingBox
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

SHAPE_BODY_BOXES: dict[tuple[str, str], tuple[float, float, float, float]] = {
    ("voltage_source", "vertical_up"): (-5.5, -5.5, 5.5, 5.5),
    ("current_source", "vertical_up"): (-5.5, -5.5, 5.5, 5.5),
    ("resistor", "horizontal"): (-4.5, -2.0, 4.5, 2.0),
    ("resistor", "vertical"): (-2.0, -4.5, 2.0, 4.5),
    ("capacitor", "vertical"): (-4.0, -2.0, 4.0, 2.0),
    ("capacitor", "horizontal"): (-2.0, -4.0, 2.0, 4.0),
    ("inductor", "horizontal"): (-5.2, -2.0, 5.2, 2.0),
    ("diode", "horizontal"): (-3.5, -3.0, 3.5, 3.0),
    ("ground", "down"): (-2.0, -3.0, 2.0, 1.0),
    ("power", "up"): (-2.0, -1.0, 2.0, 3.0),
    ("opamp", "right"): (-6.0, -6.0, 6.0, 6.0),
    ("npn_bjt", "right"): (-3.0, -5.0, 4.5, 5.0),
    ("pmos", "right"): (-3.0, -4.0, 5.5, 4.0),
    ("nmos", "right"): (-3.0, -4.0, 5.5, 4.0),
}

ROUTING_CLEARANCE = 4.0


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
    wire_points: set[tuple[float, float]] = set()
    for wire in geometry.wires:
        if len(wire.points) < 2:
            raise AssertionError(f"wire path '{wire.uuid_seed}' has fewer than 2 points")
        for point in wire.points:
            wire_points.add((point.x, point.y))
        for point in (wire.points[0], wire.points[-1]):
            key = (point.x, point.y)
            point_usage[key] = point_usage.get(key, 0) + 1
        for start, end in zip(wire.points, wire.points[1:]):
            owners = _wire_owner_refs(wire.uuid_seed)
            for shape in geometry.shapes:
                if shape.ref in owners:
                    continue
                if _segment_intersects_box(start, end, shape.body_box):
                    raise AssertionError(
                        f"wire '{wire.uuid_seed}' intersects shape body '{shape.ref}'"
                    )

    junction_points = {(junction.point.x, junction.point.y) for junction in geometry.junctions}
    for junction_point in junction_points:
        if junction_point not in {(node.point.x, node.point.y) for node in geometry.nodes}:
            raise AssertionError(f"junction at {junction_point} does not correspond to a geometry node")
        if junction_point not in wire_points:
            raise AssertionError(f"junction at {junction_point} does not lie on a compiled wire path")

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
                gnd_shape = _place_ground(
                    ref,
                    _choose_support_symbol_center(point, "ground", geometry.shapes, preferred="down"),
                )
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
                power_shape = _place_power(
                    ref,
                    net_name.upper(),
                    _choose_support_symbol_center(point, "power", geometry.shapes, preferred="up"),
                )
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
                point=_choose_node_point(net_name, points, attachments, shapes_by_ref),
                attachments=tuple(attachments),
                render_style="junction" if len(attachments) >= 3 else "inline",
            )
        )
    return geometry


def _compile_nodes_to_wires(geometry: SchematicGeometry) -> None:
    shape_by_ref = {shape.ref: shape for shape in geometry.shapes}
    occupied = [(shape.ref, shape.body_box) for shape in geometry.shapes]
    for node in geometry.nodes:
        attachment_points = [_resolve_terminal_ref(shape_by_ref, attachment) for attachment in node.attachments]
        distinct_points = {(point.x, point.y) for point in attachment_points}
        if node.render_style == "junction" or len(node.attachments) >= 3:
            geometry.junctions.append(JunctionPlacement(point=node.point))
        if len(distinct_points) == 1 and next(iter(distinct_points)) == (node.point.x, node.point.y):
            continue
        if len(node.attachments) == 2 and node.render_style != "junction":
            start_ref, end_ref = node.attachments
            path_points = _route_between_terminals(shape_by_ref, occupied, start_ref, end_ref)
            geometry.wires.append(
                WirePath(points=path_points, uuid_seed=f"{geometry.name}:{node.id}:{start_ref.owner_ref}:{end_ref.owner_ref}")
            )
            continue
        for idx, attachment in enumerate(node.attachments, start=1):
            point = _resolve_terminal_ref(shape_by_ref, attachment)
            if point.x == node.point.x and point.y == node.point.y:
                continue
            path_points = _route_attachment_to_node(shape_by_ref, occupied, attachment, node.point)
            geometry.wires.append(
                WirePath(points=path_points, uuid_seed=f"{geometry.name}:{node.id}:{attachment.owner_ref}:{idx}")
            )


def _resolve_terminal_ref(shape_by_ref: dict[str, PlacedShape], terminal_ref: TerminalRef) -> Point:
    shape = shape_by_ref.get(terminal_ref.owner_ref)
    if shape is None:
        raise AssertionError(f"unknown shape '{terminal_ref.owner_ref}' in geometry node")
    return _terminal_point(shape, terminal_ref.terminal_name)


def _choose_node_point(
    net_name: str,
    points: list[Point],
    attachments: list[TerminalRef],
    shapes_by_ref: dict[str, PlacedShape],
) -> Point:
    if len(points) == 2:
        p1, p2 = points
        return Point(round((p1.x + p2.x) / 2.0, 2), round((p1.y + p2.y) / 2.0, 2))
    boxes = [shapes_by_ref[attachment.owner_ref].body_box for attachment in attachments]
    x_min = min(point.x for point in points)
    x_max = max(point.x for point in points)
    y_min = min(point.y for point in points)
    y_max = max(point.y for point in points)
    x_spread = x_max - x_min
    y_spread = y_max - y_min
    lowered = net_name.lower()

    if y_spread >= x_spread:
        lane_y = _choose_free_horizontal_lane(y_min, y_max, boxes)
        if lowered in {"vcc", "vdd", "vee"}:
            lane_y = min(lane_y, min(box.top for box in boxes) - ROUTING_CLEARANCE)
        if lowered in {"0", "gnd", "vss"}:
            lane_y = max(lane_y, max(box.bottom for box in boxes) + ROUTING_CLEARANCE)
        return Point(round((x_min + x_max) / 2.0, 2), round(lane_y, 2))

    lane_x = _choose_free_vertical_lane(x_min, x_max, boxes)
    return Point(round(lane_x, 2), round((y_min + y_max) / 2.0, 2))


def _place_shape_from_component(comp: IntentComponent, center: Point, orientation: str | None = None) -> PlacedShape:
    shape_name, default_orientation = _shape_for_component(comp)
    actual_orientation = orientation or default_orientation
    terminals = _make_terminals(shape_name, actual_orientation, center)
    body_box = _body_box(shape_name, actual_orientation, center)
    return PlacedShape(
        ref=comp.ref,
        value=comp.value,
        shape=shape_name,
        orientation=actual_orientation,
        center=center,
        terminals=terminals,
        body_box=body_box,
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
        body_box=_body_box("ground", "down", center),
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
        body_box=_body_box("power", "up", center),
        hidden_reference=True,
    )


def _make_terminals(shape: str, orientation: str, center: Point) -> tuple[PlacedTerminal, ...]:
    offsets = GENERIC_SHAPES[(shape, orientation)]
    return tuple(
        PlacedTerminal(
            name=name,
            point=Point(round(center.x + dx, 2), round(center.y + dy, 2)),
            side=_infer_terminal_side(dx, dy),
        )
        for name, (dx, dy) in offsets.items()
    )


def _body_box(shape: str, orientation: str, center: Point) -> BoundingBox:
    left, top, right, bottom = SHAPE_BODY_BOXES[(shape, orientation)]
    return BoundingBox(
        left=round(center.x + left, 2),
        top=round(center.y + top, 2),
        right=round(center.x + right, 2),
        bottom=round(center.y + bottom, 2),
    )


def _infer_terminal_side(dx: float, dy: float) -> str:
    if abs(dx) >= abs(dy):
        if dx >= 0:
            return "right"
        return "left"
    if dy >= 0:
        return "bottom"
    return "top"


def _terminal_point(shape: PlacedShape, terminal_name: str) -> Point:
    for terminal in shape.terminals:
        if terminal.name == terminal_name:
            return terminal.point
    raise AssertionError(f"terminal '{terminal_name}' not found on shape '{shape.ref}'")


def _terminal(shape: PlacedShape, terminal_name: str) -> PlacedTerminal:
    for terminal in shape.terminals:
        if terminal.name == terminal_name:
            return terminal
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


def _wire_owner_refs(uuid_seed: str) -> set[str]:
    return {part for part in uuid_seed.split(":") if part and not part.startswith("net")}


def _resolve_terminal(shape_by_ref: dict[str, PlacedShape], terminal_ref: TerminalRef) -> PlacedTerminal:
    shape = shape_by_ref.get(terminal_ref.owner_ref)
    if shape is None:
        raise AssertionError(f"unknown shape '{terminal_ref.owner_ref}' in geometry node")
    return _terminal(shape, terminal_ref.terminal_name)


def _route_between_terminals(
    shape_by_ref: dict[str, PlacedShape],
    occupied: list[tuple[str, BoundingBox]],
    start_ref: TerminalRef,
    end_ref: TerminalRef,
) -> tuple[Point, ...]:
    start = _resolve_terminal(shape_by_ref, start_ref)
    end = _resolve_terminal(shape_by_ref, end_ref)
    ignored = {start_ref.owner_ref, end_ref.owner_ref}
    boxes = [box for owner, box in occupied if owner not in ignored]
    return _best_path(
        start.point,
        start.side,
        shape_by_ref[start_ref.owner_ref].body_box,
        end.point,
        end.side,
        shape_by_ref[end_ref.owner_ref].body_box,
        boxes,
    )


def _route_attachment_to_node(
    shape_by_ref: dict[str, PlacedShape],
    occupied: list[tuple[str, BoundingBox]],
    attachment: TerminalRef,
    node_point: Point,
) -> tuple[Point, ...]:
    terminal = _resolve_terminal(shape_by_ref, attachment)
    boxes = [box for owner, box in occupied if owner != attachment.owner_ref]
    return _best_path(
        terminal.point,
        terminal.side,
        shape_by_ref[attachment.owner_ref].body_box,
        node_point,
        "",
        None,
        boxes,
    )


def _best_path(
    start: Point,
    start_side: str,
    start_box: BoundingBox,
    end: Point,
    end_side: str,
    end_box: BoundingBox | None,
    boxes: list[BoundingBox],
) -> tuple[Point, ...]:
    candidates: list[tuple[Point, ...]] = []
    start_exit = _terminal_exit_point(start, start_side, start_box)
    end_exit = _terminal_exit_point(end, end_side, end_box) if end_box is not None and end_side else end

    direct = (start, end)
    candidates.append(direct)
    candidates.extend(
        [
            (start, start_exit, end_exit, end),
            (start, start_exit, Point(end_exit.x, start_exit.y), end_exit, end),
            (start, start_exit, Point(start_exit.x, end_exit.y), end_exit, end),
        ]
    )

    x_candidates = [min(box.left for box in boxes + [start_box]) - ROUTING_CLEARANCE, max(box.right for box in boxes + [start_box]) + ROUTING_CLEARANCE]
    y_candidates = [min(box.top for box in boxes + [start_box]) - ROUTING_CLEARANCE, max(box.bottom for box in boxes + [start_box]) + ROUTING_CLEARANCE]
    if end_box is not None:
        x_candidates.extend([end_box.left - ROUTING_CLEARANCE, end_box.right + ROUTING_CLEARANCE])
        y_candidates.extend([end_box.top - ROUTING_CLEARANCE, end_box.bottom + ROUTING_CLEARANCE])

    for x in x_candidates:
        candidates.append((start, start_exit, Point(x, start_exit.y), Point(x, end_exit.y), end_exit, end))
    for y in y_candidates:
        candidates.append((start, start_exit, Point(start_exit.x, y), Point(end_exit.x, y), end_exit, end))

    valid_paths = [path for path in (_normalize_path(candidate) for candidate in candidates) if _path_is_clear(path, boxes)]
    if not valid_paths:
        return _normalize_path((start, start_exit, end_exit, end))
    valid_paths.sort(key=lambda path: (_bend_count(path), _path_length(path)))
    return valid_paths[0]


def _terminal_exit_point(point: Point, side: str, box: BoundingBox | None) -> Point:
    if box is None or not side:
        return point
    if side == "left":
        return Point(round(box.left - ROUTING_CLEARANCE, 2), point.y)
    if side == "right":
        return Point(round(box.right + ROUTING_CLEARANCE, 2), point.y)
    if side == "top":
        return Point(point.x, round(box.top - ROUTING_CLEARANCE, 2))
    return Point(point.x, round(box.bottom + ROUTING_CLEARANCE, 2))


def _normalize_path(path: tuple[Point, ...]) -> tuple[Point, ...]:
    normalized: list[Point] = []
    for point in path:
        if normalized and normalized[-1].x == point.x and normalized[-1].y == point.y:
            continue
        normalized.append(point)
    compressed: list[Point] = []
    for point in normalized:
        if len(compressed) >= 2:
            p1 = compressed[-2]
            p2 = compressed[-1]
            if (p1.x == p2.x == point.x) or (p1.y == p2.y == point.y):
                compressed[-1] = point
                continue
        compressed.append(point)
    return tuple(compressed)


def _path_is_clear(path: tuple[Point, ...], boxes: list[BoundingBox]) -> bool:
    for start, end in zip(path, path[1:]):
        for box in boxes:
            if _segment_intersects_box(start, end, box):
                return False
    return True


def _segment_intersects_box(start: Point, end: Point, box: BoundingBox) -> bool:
    if start.x == end.x:
        x = start.x
        if x <= box.left or x >= box.right:
            return False
        seg_top = min(start.y, end.y)
        seg_bottom = max(start.y, end.y)
        return not (seg_bottom <= box.top or seg_top >= box.bottom)
    if start.y == end.y:
        y = start.y
        if y <= box.top or y >= box.bottom:
            return False
        seg_left = min(start.x, end.x)
        seg_right = max(start.x, end.x)
        return not (seg_right <= box.left or seg_left >= box.right)
    return True


def _bend_count(path: tuple[Point, ...]) -> int:
    return max(0, len(path) - 2)


def _path_length(path: tuple[Point, ...]) -> float:
    length = 0.0
    for start, end in zip(path, path[1:]):
        length += abs(end.x - start.x) + abs(end.y - start.y)
    return length


def _choose_free_horizontal_lane(y_min: float, y_max: float, boxes: list[BoundingBox]) -> float:
    sorted_boxes = sorted(boxes, key=lambda box: box.top)
    candidates = [y_min - ROUTING_CLEARANCE, y_max + ROUTING_CLEARANCE]
    for first, second in zip(sorted_boxes, sorted_boxes[1:]):
        gap_top = first.bottom + ROUTING_CLEARANCE
        gap_bottom = second.top - ROUTING_CLEARANCE
        if gap_bottom > gap_top:
            candidates.append((gap_top + gap_bottom) / 2.0)
    return min(candidates, key=lambda y: abs(y - ((y_min + y_max) / 2.0)))


def _choose_free_vertical_lane(x_min: float, x_max: float, boxes: list[BoundingBox]) -> float:
    sorted_boxes = sorted(boxes, key=lambda box: box.left)
    candidates = [x_min - ROUTING_CLEARANCE, x_max + ROUTING_CLEARANCE]
    for first, second in zip(sorted_boxes, sorted_boxes[1:]):
        gap_left = first.right + ROUTING_CLEARANCE
        gap_right = second.left - ROUTING_CLEARANCE
        if gap_right > gap_left:
            candidates.append((gap_left + gap_right) / 2.0)
    return min(candidates, key=lambda x: abs(x - ((x_min + x_max) / 2.0)))


def _choose_support_symbol_center(
    terminal_point: Point,
    symbol_kind: str,
    existing_shapes: list[PlacedShape],
    *,
    preferred: str,
) -> Point:
    prototype = SHAPE_BODY_BOXES[(symbol_kind, "down" if symbol_kind == "ground" else "up")]
    candidate_offsets = {
        "down": [(0.0, 12.0), (-12.0, 6.0), (12.0, 6.0), (-16.0, 0.0), (16.0, 0.0)],
        "up": [(0.0, -12.0), (-12.0, -6.0), (12.0, -6.0), (-16.0, 0.0), (16.0, 0.0)],
    }[preferred]
    occupied = [shape.body_box for shape in existing_shapes]
    for dx, dy in candidate_offsets:
        center = Point(round(terminal_point.x + dx, 2), round(terminal_point.y + dy, 2))
        box = BoundingBox(
            left=center.x + prototype[0],
            top=center.y + prototype[1],
            right=center.x + prototype[2],
            bottom=center.y + prototype[3],
        )
        if all(not _boxes_overlap(box, existing) for existing in occupied):
            return center
    dx, dy = candidate_offsets[0]
    return Point(round(terminal_point.x + dx, 2), round(terminal_point.y + dy, 2))


def _boxes_overlap(first: BoundingBox, second: BoundingBox) -> bool:
    return not (
        first.right <= second.left
        or first.left >= second.right
        or first.bottom <= second.top
        or first.top >= second.bottom
    )


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
