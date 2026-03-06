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
    preferred_connection_class: str | None = None


@dataclass(frozen=True, slots=True)
class TerminalTemplate:
    name: str
    offset: tuple[float, float]
    exit_direction: str
    preferred_connection_class: str | None = None


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
class PinExitCorridor:
    owner_ref: str
    terminal_name: str
    start: Point
    end: Point


@dataclass(frozen=True, slots=True)
class NodeAnchor:
    point: Point


@dataclass(frozen=True, slots=True)
class NodeTrunk:
    start: Point
    end: Point


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
    anchors: list[NodeAnchor] = field(default_factory=list)
    trunks: list[NodeTrunk] = field(default_factory=list)
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


SHAPE_TERMINALS: dict[tuple[str, str], tuple[TerminalTemplate, ...]] = {
    ("voltage_source", "vertical_up"): (
        TerminalTemplate("pos", (0.0, -7.62), "top"),
        TerminalTemplate("neg", (0.0, 7.62), "bottom", "local_ground_drop"),
    ),
    ("current_source", "vertical_up"): (
        TerminalTemplate("pos", (0.0, -10.16), "top"),
        TerminalTemplate("neg", (0.0, 10.16), "bottom", "local_ground_drop"),
    ),
    ("resistor", "horizontal"): (
        TerminalTemplate("left", (-6.35, 0.0), "left", "series_inline"),
        TerminalTemplate("right", (6.35, 0.0), "right", "series_inline"),
    ),
    ("resistor", "vertical"): (
        TerminalTemplate("top", (0.0, -6.35), "top", "branch_to_junction"),
        TerminalTemplate("bottom", (0.0, 6.35), "bottom", "local_ground_drop"),
    ),
    ("capacitor", "vertical"): (
        TerminalTemplate("top", (0.0, -6.35), "top", "branch_to_junction"),
        TerminalTemplate("bottom", (0.0, 6.35), "bottom", "local_ground_drop"),
    ),
    ("capacitor", "horizontal"): (
        TerminalTemplate("left", (-6.35, 0.0), "left", "series_inline"),
        TerminalTemplate("right", (6.35, 0.0), "right", "series_inline"),
    ),
    ("inductor", "horizontal"): (
        TerminalTemplate("left", (-6.35, 0.0), "left", "series_inline"),
        TerminalTemplate("right", (6.35, 0.0), "right", "series_inline"),
    ),
    ("diode", "horizontal"): (
        TerminalTemplate("left", (-5.08, 0.0), "left", "series_inline"),
        TerminalTemplate("right", (5.08, 0.0), "right", "branch_to_junction"),
    ),
    ("ground", "down"): (
        TerminalTemplate("top", (0.0, 0.0), "top", "local_ground_drop"),
    ),
    ("power", "up"): (
        TerminalTemplate("bottom", (0.0, 0.0), "bottom", "local_supply_rise"),
    ),
    ("opamp", "right"): (
        TerminalTemplate("plus", (-7.62, 2.54), "left", "branch_to_junction"),
        TerminalTemplate("minus", (-7.62, -2.54), "left", "feedback_loop"),
        TerminalTemplate("out", (7.62, 0.0), "right", "series_inline"),
        TerminalTemplate("vplus", (-2.54, 7.62), "bottom", "local_supply_rise"),
        TerminalTemplate("vminus", (-2.54, -7.62), "top", "local_ground_drop"),
    ),
    ("npn_bjt", "right"): (
        TerminalTemplate("collector", (3.81, -8.89), "top", "branch_to_junction"),
        TerminalTemplate("base", (-7.62, 0.0), "left", "branch_to_junction"),
        TerminalTemplate("emitter", (3.81, 8.89), "bottom", "local_ground_drop"),
    ),
    ("pmos", "right"): (
        TerminalTemplate("drain", (2.54, -5.08), "top", "branch_to_junction"),
        TerminalTemplate("gate", (-5.08, 0.0), "left", "branch_to_junction"),
        TerminalTemplate("source", (2.54, 5.08), "bottom", "local_supply_rise"),
        TerminalTemplate("body", (5.08, 5.08), "right", "local_supply_rise"),
    ),
    ("nmos", "right"): (
        TerminalTemplate("drain", (2.54, 5.08), "bottom", "branch_to_junction"),
        TerminalTemplate("gate", (-5.08, 0.0), "left", "branch_to_junction"),
        TerminalTemplate("source", (2.54, -5.08), "top", "local_ground_drop"),
        TerminalTemplate("body", (5.08, -5.08), "right", "local_ground_drop"),
    ),
}

GENERIC_SHAPES: dict[tuple[str, str], dict[str, tuple[float, float]]] = {
    key: {terminal.name: terminal.offset for terminal in terminals}
    for key, terminals in SHAPE_TERMINALS.items()
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
PAGE_LEFT = 30.0
PAGE_TOP = 30.0
PAGE_RIGHT = 245.0
PAGE_BOTTOM = 170.0
PAGE_FIT_MARGIN = 8.0


def build_schematic_geometry(intent: SchematicIntent) -> SchematicGeometry:
    for pattern in intent.patterns:
        if pattern.kind == "rc_lowpass":
            return _finalize_geometry(_build_rc_lowpass_geometry(intent, pattern))
        if pattern.kind == "rc_highpass":
            return _finalize_geometry(_build_rc_highpass_geometry(intent, pattern))
    if _can_use_flow_layout(intent):
        return _finalize_geometry(_build_flow_geometry(intent))
    return _finalize_geometry(_build_fallback_geometry(intent))


def validate_schematic_geometry(geometry: SchematicGeometry) -> None:
    shape_by_ref = {shape.ref: shape for shape in geometry.shapes}
    point_usage: dict[tuple[float, float], int] = {}
    wire_points: set[tuple[float, float]] = set()
    for wire in geometry.wires:
        if len(wire.points) < 2:
            raise AssertionError(f"wire path '{wire.uuid_seed}' has fewer than 2 points")
        if _is_local_support_wire(wire.uuid_seed) and _bend_count(wire.points) > 2:
            raise AssertionError(f"local support wire '{wire.uuid_seed}' has unnecessary bends")
        for point in wire.points:
            wire_points.add((point.x, point.y))
        for point in (wire.points[0], wire.points[-1]):
            key = (point.x, point.y)
            point_usage[key] = point_usage.get(key, 0) + 1
        for start, end in zip(wire.points, wire.points[1:]):
            if _segment_hits_shape_body(shape_by_ref, wire.uuid_seed, start, end):
                raise AssertionError(f"wire '{wire.uuid_seed}' crosses a component body")

    bounds = _geometry_bounds(geometry)
    if bounds is not None:
        if bounds.left < PAGE_LEFT or bounds.top < PAGE_TOP or bounds.right > PAGE_RIGHT or bounds.bottom > PAGE_BOTTOM:
            raise AssertionError(
                f"geometry bounds {(bounds.left, bounds.top, bounds.right, bounds.bottom)} exceed usable page area"
            )

    junction_points = {(junction.point.x, junction.point.y) for junction in geometry.junctions}
    for junction_point in junction_points:
        if junction_point not in {(node.point.x, node.point.y) for node in geometry.nodes}:
            raise AssertionError(f"junction at {junction_point} does not correspond to a geometry node")
        if junction_point not in wire_points:
            raise AssertionError(f"junction at {junction_point} does not lie on a compiled wire path")

    for anchor in geometry.anchors:
        if any(_point_in_box(anchor.point, shape.body_box) for shape in geometry.shapes):
            raise AssertionError(f"node anchor at {(anchor.point.x, anchor.point.y)} lies inside a shape body")
    for trunk in geometry.trunks:
        for shape in geometry.shapes:
            if _segment_intersects_box(trunk.start, trunk.end, shape.body_box):
                raise AssertionError(
                    f"node trunk {(trunk.start.x, trunk.start.y)} -> {(trunk.end.x, trunk.end.y)} intersects shape body '{shape.ref}'"
                )

    for node in geometry.nodes:
        if len(node.attachments) < 2:
            raise AssertionError(f"node '{node.id}' has fewer than 2 attachments")
        if any(_node_point_inside_forbidden_shape(node.point, shape) for shape in geometry.shapes):
            raise AssertionError(f"node '{node.id}' anchor lies inside a component body")
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


def pack_schematic_geometry(geometry: SchematicGeometry) -> SchematicGeometry:
    bounds = _geometry_bounds(geometry)
    if bounds is None:
        return geometry
    dx = 0.0
    dy = 0.0
    if bounds.left < PAGE_LEFT + PAGE_FIT_MARGIN:
        dx = PAGE_LEFT + PAGE_FIT_MARGIN - bounds.left
    elif bounds.right > PAGE_RIGHT - PAGE_FIT_MARGIN:
        dx = PAGE_RIGHT - PAGE_FIT_MARGIN - bounds.right
    if bounds.top < PAGE_TOP + PAGE_FIT_MARGIN:
        dy = PAGE_TOP + PAGE_FIT_MARGIN - bounds.top
    elif bounds.bottom > PAGE_BOTTOM - PAGE_FIT_MARGIN:
        dy = PAGE_BOTTOM - PAGE_FIT_MARGIN - bounds.bottom
    if dx == 0.0 and dy == 0.0:
        return geometry
    return _translate_geometry(geometry, dx, dy)


def _finalize_geometry(geometry: SchematicGeometry) -> SchematicGeometry:
    _compile_nodes_to_wires(geometry)
    packed = pack_schematic_geometry(geometry)
    validate_schematic_geometry(packed)
    return packed


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


def _build_flow_geometry(intent: SchematicIntent) -> SchematicGeometry:
    geometry = SchematicGeometry(name=intent.name)
    by_ref = {comp.ref: comp for comp in intent.components}
    net_to_components = _net_to_components(intent)
    source = _preferred_source_component(intent)
    main_path = _longest_component_path(source.ref, _component_adjacency(intent)) if source is not None else []
    main_path_set = set(main_path)

    centers: dict[str, Point] = {}
    orientations: dict[str, str] = {}
    main_y = 78.0
    source_y = 86.0
    x_cursor = 56.0
    if source is not None:
        centers[source.ref] = Point(x_cursor, source_y)
        orientations[source.ref] = "vertical_up"
        x_cursor += 34.0

    for idx, ref in enumerate(main_path):
        comp = by_ref[ref]
        orientation = _series_orientation(comp)
        centers[ref] = Point(x_cursor + idx * 30.0, main_y)
        orientations[ref] = orientation

    shunt_counts: dict[str, int] = {}
    remaining_x = (x_cursor + len(main_path) * 30.0) if main_path else 100.0
    for comp in intent.components:
        if comp.ref in centers:
            continue
        if _is_two_pin_shunt(comp, intent):
            net_name = _first_signal_net(comp, intent)
            anchor_x = _net_anchor_x(net_name, main_path, centers, by_ref) if net_name is not None else remaining_x
            slot = shunt_counts.get(net_name or comp.ref, 0)
            shunt_counts[net_name or comp.ref] = slot + 1
            centers[comp.ref] = Point(anchor_x + slot * 22.0, main_y + 34.0 + slot * 18.0)
            orientations[comp.ref] = _shunt_orientation(comp)
            continue
        centers[comp.ref] = Point(remaining_x, 120.0 + 24.0 * (len(centers) - len(main_path_set)))
        orientations[comp.ref] = _shape_for_component(comp)[1]
        remaining_x += 28.0

    shapes_by_ref: dict[str, PlacedShape] = {}
    for comp in intent.components:
        shape = _place_shape_from_component(comp, centers[comp.ref], orientation=orientations[comp.ref])
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
            terminal = _terminal(shape, terminal_name)
            point = terminal.point
            role = intent.nets[net_name].role
            if role == "ground":
                ref = f"#PWR{power_ref_idx:04d}"
                power_ref_idx += 1
                gnd_shape = _place_ground(
                    ref,
                    _place_support_symbol_for_terminal(terminal, "ground", geometry.shapes, preferred="down"),
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
                    _place_support_symbol_for_terminal(terminal, "power", geometry.shapes, preferred="up"),
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
        node_point, trunk = _choose_node_layout(net_name, points, attachments, shapes_by_ref)
        geometry.anchors.append(NodeAnchor(point=node_point))
        if trunk is not None:
            geometry.trunks.append(trunk)
        geometry.nodes.append(
            GeometryNode(
                id=f"net:{net_name}",
                point=node_point,
                attachments=tuple(attachments),
                render_style="junction" if len(attachments) >= 3 else "inline",
            )
        )
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
            terminal = _terminal(shape, terminal_name)
            point = terminal.point
            role = intent.nets[net_name].role
            if role == "ground":
                ref = f"#PWR{power_ref_idx:04d}"
                power_ref_idx += 1
                gnd_shape = _place_ground(
                    ref,
                    _place_support_symbol_for_terminal(terminal, "ground", geometry.shapes, preferred="down"),
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
                    _place_support_symbol_for_terminal(terminal, "power", geometry.shapes, preferred="up"),
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
        node_point, trunk = _choose_node_layout(net_name, points, attachments, shapes_by_ref)
        geometry.anchors.append(NodeAnchor(point=node_point))
        if trunk is not None:
            geometry.trunks.append(trunk)
        geometry.nodes.append(
            GeometryNode(
                id=f"net:{net_name}",
                point=node_point,
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
            path_points = _route_connection(shape_by_ref, occupied, start_ref, end_ref)
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


def _choose_node_layout(
    net_name: str,
    points: list[Point],
    attachments: list[TerminalRef],
    shapes_by_ref: dict[str, PlacedShape],
) -> tuple[Point, NodeTrunk | None]:
    if len(points) == 2:
        p1, p2 = points
        return Point(round((p1.x + p2.x) / 2.0, 2), round((p1.y + p2.y) / 2.0, 2)), None
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
        point = Point(round((x_min + x_max) / 2.0, 2), round(lane_y, 2))
        trunk = NodeTrunk(
            start=Point(round(x_min, 2), point.y),
            end=Point(round(x_max, 2), point.y),
        )
        return point, trunk

    lane_x = _choose_free_vertical_lane(x_min, x_max, boxes)
    point = Point(round(lane_x, 2), round((y_min + y_max) / 2.0, 2))
    trunk = NodeTrunk(
        start=Point(point.x, round(y_min, 2)),
        end=Point(point.x, round(y_max, 2)),
    )
    return point, trunk


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
    templates = SHAPE_TERMINALS[(shape, orientation)]
    return tuple(
        PlacedTerminal(
            name=template.name,
            point=Point(round(center.x + template.offset[0], 2), round(center.y + template.offset[1], 2)),
            side=template.exit_direction,
            preferred_connection_class=template.preferred_connection_class,
        )
        for template in templates
    )


def _body_box(shape: str, orientation: str, center: Point) -> BoundingBox:
    left, top, right, bottom = SHAPE_BODY_BOXES[(shape, orientation)]
    return BoundingBox(
        left=round(center.x + left, 2),
        top=round(center.y + top, 2),
        right=round(center.x + right, 2),
        bottom=round(center.y + bottom, 2),
    )


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


def _is_local_support_wire(uuid_seed: str) -> bool:
    return ":ground:" in uuid_seed or ":supply:" in uuid_seed


def _resolve_terminal(shape_by_ref: dict[str, PlacedShape], terminal_ref: TerminalRef) -> PlacedTerminal:
    shape = shape_by_ref.get(terminal_ref.owner_ref)
    if shape is None:
        raise AssertionError(f"unknown shape '{terminal_ref.owner_ref}' in geometry node")
    return _terminal(shape, terminal_ref.terminal_name)


def _route_connection(
    shape_by_ref: dict[str, PlacedShape],
    occupied: list[tuple[str, BoundingBox]],
    start_ref: TerminalRef,
    end_ref: TerminalRef,
) -> tuple[Point, ...]:
    start_shape = shape_by_ref[start_ref.owner_ref]
    end_shape = shape_by_ref[end_ref.owner_ref]
    start = _resolve_terminal(shape_by_ref, start_ref)
    end = _resolve_terminal(shape_by_ref, end_ref)
    connection_class = _classify_connection(start_shape, start, end_shape, end)
    if connection_class in {"local_ground_drop", "local_supply_rise"}:
        return _route_local_support_connection(start, start_shape.body_box, end, end_shape.body_box)
    return _route_between_terminals(shape_by_ref, occupied, start_ref, end_ref)


def _route_between_terminals(
    shape_by_ref: dict[str, PlacedShape],
    occupied: list[tuple[str, BoundingBox]],
    start_ref: TerminalRef,
    end_ref: TerminalRef,
) -> tuple[Point, ...]:
    start = _resolve_terminal(shape_by_ref, start_ref)
    end = _resolve_terminal(shape_by_ref, end_ref)
    boxes = [box for _, box in occupied]
    return _best_path(
        start,
        shape_by_ref[start_ref.owner_ref].body_box,
        end,
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
    boxes = [box for _, box in occupied]
    return _best_path(
        terminal,
        shape_by_ref[attachment.owner_ref].body_box,
        node_point,
        None,
        boxes,
    )


def _classify_connection(
    start_shape: PlacedShape,
    start: PlacedTerminal,
    end_shape: PlacedShape,
    end: PlacedTerminal,
) -> str:
    support_shapes = {"ground", "power"}
    if start_shape.shape in support_shapes:
        return start.preferred_connection_class or "generic_net"
    if end_shape.shape in support_shapes:
        return end.preferred_connection_class or "generic_net"
    if start.preferred_connection_class == end.preferred_connection_class and start.preferred_connection_class:
        return start.preferred_connection_class
    return "generic_net"


def _route_local_support_connection(
    start: PlacedTerminal,
    start_box: BoundingBox,
    end: PlacedTerminal,
    end_box: BoundingBox,
) -> tuple[Point, ...]:
    if (start.point.x == end.point.x or start.point.y == end.point.y) and not _segment_intersects_box(start.point, end.point, end_box):
        return _normalize_path((start.point, end.point))
    start_exit = _terminal_exit_point(start.point, start.side, start_box)
    end_exit = _terminal_exit_point(end.point, end.side, end_box)
    if start_exit.x == end_exit.x or start_exit.y == end_exit.y:
        return _normalize_path((start.point, start_exit, end_exit, end.point))
    if start.side in {"top", "bottom"} and end.side in {"top", "bottom"}:
        elbow = Point(start_exit.x, end_exit.y)
    elif start.side in {"left", "right"} and end.side in {"left", "right"}:
        elbow = Point(end_exit.x, start_exit.y)
    elif start.side in {"top", "bottom"}:
        elbow = Point(start_exit.x, end_exit.y)
    else:
        elbow = Point(end_exit.x, start_exit.y)
    return _normalize_path((start.point, start_exit, elbow, end_exit, end.point))


def _best_path(
    start: PlacedTerminal,
    start_box: BoundingBox,
    end: Point | PlacedTerminal,
    end_box: BoundingBox | None,
    boxes: list[BoundingBox],
) -> tuple[Point, ...]:
    candidates: list[tuple[Point, ...]] = []
    start_exit = _terminal_exit_point(start.point, start.side, start_box)
    end_point = end.point if isinstance(end, PlacedTerminal) else end
    end_side = end.side if isinstance(end, PlacedTerminal) else ""
    end_exit = _terminal_exit_point(end_point, end_side, end_box) if end_box is not None and end_side else end_point
    start_corridor = PinExitCorridor("", start.name, start.point, start_exit)
    end_corridor = (
        PinExitCorridor("", end.name, end_exit, end.point)
        if isinstance(end, PlacedTerminal) and end_box is not None
        else None
    )

    candidates.extend(
        [
            (start.point, start_exit, end_exit, end_point),
            (start.point, start_exit, Point(end_exit.x, start_exit.y), end_exit, end_point),
            (start.point, start_exit, Point(start_exit.x, end_exit.y), end_exit, end_point),
        ]
    )

    x_candidates = [min(box.left for box in boxes + [start_box]) - ROUTING_CLEARANCE, max(box.right for box in boxes + [start_box]) + ROUTING_CLEARANCE]
    y_candidates = [min(box.top for box in boxes + [start_box]) - ROUTING_CLEARANCE, max(box.bottom for box in boxes + [start_box]) + ROUTING_CLEARANCE]
    if end_box is not None:
        x_candidates.extend([end_box.left - ROUTING_CLEARANCE, end_box.right + ROUTING_CLEARANCE])
        y_candidates.extend([end_box.top - ROUTING_CLEARANCE, end_box.bottom + ROUTING_CLEARANCE])

    for x in x_candidates:
        candidates.append((start.point, start_exit, Point(x, start_exit.y), Point(x, end_exit.y), end_exit, end_point))
    for y in y_candidates:
        candidates.append((start.point, start_exit, Point(start_exit.x, y), Point(end_exit.x, y), end_exit, end_point))

    valid_paths = [
        path
        for path in (_normalize_path(candidate) for candidate in candidates)
        if _path_is_clear(path, boxes, start_corridor, end_corridor)
    ]
    if not valid_paths:
        return _normalize_path((start.point, start_exit, end_exit, end_point))
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


def _path_is_clear(
    path: tuple[Point, ...],
    boxes: list[BoundingBox],
    start_corridor: PinExitCorridor,
    end_corridor: PinExitCorridor | None,
) -> bool:
    corridor_segments = {
        ((start_corridor.start.x, start_corridor.start.y), (start_corridor.end.x, start_corridor.end.y)),
        ((start_corridor.end.x, start_corridor.end.y), (start_corridor.start.x, start_corridor.start.y)),
    }
    if end_corridor is not None:
        corridor_segments.update(
            {
                ((end_corridor.start.x, end_corridor.start.y), (end_corridor.end.x, end_corridor.end.y)),
                ((end_corridor.end.x, end_corridor.end.y), (end_corridor.start.x, end_corridor.start.y)),
            }
        )
    for start, end in zip(path, path[1:]):
        if ((start.x, start.y), (end.x, end.y)) in corridor_segments:
            continue
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


def _can_use_flow_layout(intent: SchematicIntent) -> bool:
    supported = {"V", "I", "R", "C", "L", "D"}
    return bool(intent.components) and all(comp.kind in supported and len(comp.nodes) == 2 for comp in intent.components)


def _net_to_components(intent: SchematicIntent) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for comp in intent.components:
        for net in comp.nodes:
            mapping.setdefault(net, []).append(comp.ref)
    return mapping


def _component_adjacency(intent: SchematicIntent) -> dict[str, list[str]]:
    shunts = {comp.ref for comp in intent.components if _is_two_pin_shunt(comp, intent)}
    adjacency: dict[str, set[str]] = {comp.ref: set() for comp in intent.components if comp.ref not in shunts}
    for net_name, members in _net_to_components(intent).items():
        if intent.nets[net_name].role in {"ground", "supply"}:
            continue
        path_members = [ref for ref in members if ref not in shunts]
        for ref in path_members:
            adjacency.setdefault(ref, set()).update(other for other in path_members if other != ref)
    return {ref: sorted(neighbors) for ref, neighbors in adjacency.items()}


def _preferred_source_component(intent: SchematicIntent) -> IntentComponent | None:
    grounded_sources = [
        comp for comp in intent.components if comp.kind in {"V", "I"} and any(intent.nets[net].role == "ground" for net in comp.nodes)
    ]
    if grounded_sources:
        return grounded_sources[0]
    for comp in intent.components:
        if comp.kind in {"V", "I"}:
            return comp
    return intent.components[0] if intent.components else None


def _longest_component_path(start_ref: str, adjacency: dict[str, list[str]]) -> list[str]:
    best: list[str] = []

    def walk(ref: str, path: list[str], seen: set[str]) -> None:
        nonlocal best
        if len(path) > len(best):
            best = path.copy()
        for neighbor in adjacency.get(ref, []):
            if neighbor in seen:
                continue
            seen.add(neighbor)
            path.append(neighbor)
            walk(neighbor, path, seen)
            path.pop()
            seen.remove(neighbor)

    walk(start_ref, [start_ref], {start_ref})
    return best[1:]


def _series_orientation(comp: IntentComponent) -> str:
    if comp.kind in {"R", "L", "D"}:
        return "horizontal"
    if comp.kind == "C":
        return "horizontal"
    return _shape_for_component(comp)[1]


def _shunt_orientation(comp: IntentComponent) -> str:
    if comp.kind == "R":
        return "vertical"
    if comp.kind == "C":
        return "vertical"
    return _shape_for_component(comp)[1]


def _is_two_pin_shunt(comp: IntentComponent, intent: SchematicIntent) -> bool:
    if comp.kind not in {"R", "C", "L", "D"}:
        return False
    if len(comp.nodes) != 2:
        return False
    roles = {intent.nets[net].role for net in comp.nodes}
    return "ground" in roles or "supply" in roles


def _first_signal_net(comp: IntentComponent, intent: SchematicIntent) -> str | None:
    for net in comp.nodes:
        if intent.nets[net].role not in {"ground", "supply"}:
            return net
    return None


def _net_anchor_x(net_name: str, main_path: list[str], centers: dict[str, Point], by_ref: dict[str, IntentComponent]) -> float:
    for ref in main_path:
        comp = by_ref[ref]
        if net_name in comp.nodes and ref in centers:
            return centers[ref].x
    for ref, center in centers.items():
        comp = by_ref.get(ref)
        if comp is not None and net_name in comp.nodes:
            return center.x
    return 100.0


def _segment_hits_shape_body(
    shape_by_ref: dict[str, PlacedShape],
    wire_seed: str,
    start: Point,
    end: Point,
) -> bool:
    owners = _wire_owner_refs(wire_seed)
    for ref, shape in shape_by_ref.items():
        if not _segment_intersects_box(start, end, shape.body_box):
            continue
        if ref in owners and _is_legal_owner_corridor(shape, start, end):
            continue
        return True
    return False


def _is_legal_owner_corridor(shape: PlacedShape, start: Point, end: Point) -> bool:
    for terminal in shape.terminals:
        exit_point = _terminal_exit_point(terminal.point, terminal.side, shape.body_box)
        if _segment_uses_terminal_corridor(start, end, terminal.point, exit_point):
            return True
    return False


def _segment_uses_terminal_corridor(start: Point, end: Point, terminal: Point, exit_point: Point) -> bool:
    if _segment_key(start, end) in {
        _segment_key(terminal, exit_point),
        _segment_key(exit_point, terminal),
    }:
        return True
    if terminal.x == exit_point.x == start.x == end.x:
        seg_top = min(start.y, end.y)
        seg_bottom = max(start.y, end.y)
        if not (seg_top <= terminal.y <= seg_bottom):
            return False
        if exit_point.y < terminal.y:
            return seg_top < terminal.y
        return seg_bottom > terminal.y
    if terminal.y == exit_point.y == start.y == end.y:
        seg_left = min(start.x, end.x)
        seg_right = max(start.x, end.x)
        if not (seg_left <= terminal.x <= seg_right):
            return False
        if exit_point.x < terminal.x:
            return seg_left < terminal.x
        return seg_right > terminal.x
    return False


def _point_in_box(point: Point, box: BoundingBox) -> bool:
    return box.left < point.x < box.right and box.top < point.y < box.bottom


def _node_point_inside_forbidden_shape(point: Point, shape: PlacedShape) -> bool:
    if not _point_in_box(point, shape.body_box):
        return False
    if shape.shape in {"ground", "power"}:
        return False
    return True


def _segment_key(start: Point, end: Point) -> tuple[tuple[float, float], tuple[float, float]]:
    return ((start.x, start.y), (end.x, end.y))


def _geometry_bounds(geometry: SchematicGeometry) -> BoundingBox | None:
    xs: list[float] = []
    ys: list[float] = []
    for shape in geometry.shapes:
        xs.extend([shape.body_box.left, shape.body_box.right])
        ys.extend([shape.body_box.top, shape.body_box.bottom])
    for wire in geometry.wires:
        for point in wire.points:
            xs.append(point.x)
            ys.append(point.y)
    for text in geometry.labels:
        xs.append(text.position.x)
        ys.append(text.position.y)
    for junction in geometry.junctions:
        xs.append(junction.point.x)
        ys.append(junction.point.y)
    if not xs or not ys:
        return None
    return BoundingBox(min(xs), min(ys), max(xs), max(ys))


def _translate_geometry(geometry: SchematicGeometry, dx: float, dy: float) -> SchematicGeometry:
    def move_point(point: Point) -> Point:
        return Point(round(point.x + dx, 2), round(point.y + dy, 2))

    def move_box(box: BoundingBox) -> BoundingBox:
        return BoundingBox(
            left=round(box.left + dx, 2),
            top=round(box.top + dy, 2),
            right=round(box.right + dx, 2),
            bottom=round(box.bottom + dy, 2),
        )

    geometry.shapes = [
        PlacedShape(
            ref=shape.ref,
            value=shape.value,
            shape=shape.shape,
            orientation=shape.orientation,
            center=move_point(shape.center),
            terminals=tuple(
                PlacedTerminal(name=terminal.name, point=move_point(terminal.point), side=terminal.side)
                for terminal in shape.terminals
            ),
            body_box=move_box(shape.body_box),
            hidden_reference=shape.hidden_reference,
        )
        for shape in geometry.shapes
    ]
    geometry.nodes = [
        GeometryNode(
            id=node.id,
            point=move_point(node.point),
            attachments=node.attachments,
            render_style=node.render_style,
            label=node.label,
        )
        for node in geometry.nodes
    ]
    geometry.anchors = [NodeAnchor(point=move_point(anchor.point)) for anchor in geometry.anchors]
    geometry.trunks = [NodeTrunk(start=move_point(trunk.start), end=move_point(trunk.end)) for trunk in geometry.trunks]
    geometry.wires = [
        WirePath(points=tuple(move_point(point) for point in wire.points), uuid_seed=wire.uuid_seed)
        for wire in geometry.wires
    ]
    geometry.labels = [
        TextPlacement(
            text=text.text,
            role=text.role,
            position=move_point(text.position),
            owner_ref=text.owner_ref,
            uuid_seed=text.uuid_seed,
        )
        for text in geometry.labels
    ]
    geometry.junctions = [JunctionPlacement(point=move_point(junction.point)) for junction in geometry.junctions]
    return geometry


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


def _place_support_symbol_for_terminal(
    terminal: PlacedTerminal,
    symbol_kind: str,
    existing_shapes: list[PlacedShape],
    *,
    preferred: str,
) -> Point:
    prototype = SHAPE_BODY_BOXES[(symbol_kind, "down" if symbol_kind == "ground" else "up")]
    primary_offset = 12.0 if preferred == "down" else -12.0
    lateral_step = 12.0
    if terminal.side in {"left", "right"}:
        lateral_dx = 10.0 if terminal.side == "right" else -10.0
        candidate_offsets: list[tuple[float, float]] = [
            (lateral_dx, primary_offset / 2.0),
            (lateral_dx, primary_offset),
            (lateral_dx + (4.0 if lateral_dx > 0 else -4.0), primary_offset / 2.0),
            (lateral_dx + (4.0 if lateral_dx > 0 else -4.0), primary_offset),
        ]
    else:
        candidate_offsets = [
            (0.0, primary_offset),
            (-lateral_step, primary_offset / 2.0),
            (lateral_step, primary_offset / 2.0),
            (-lateral_step, primary_offset),
            (lateral_step, primary_offset),
        ]
    candidate_offsets.extend([(-16.0, 0.0), (16.0, 0.0)])
    occupied = [shape.body_box for shape in existing_shapes]
    for dx, dy in candidate_offsets:
        center = Point(round(terminal.point.x + dx, 2), round(terminal.point.y + dy, 2))
        box = BoundingBox(
            left=center.x + prototype[0],
            top=center.y + prototype[1],
            right=center.x + prototype[2],
            bottom=center.y + prototype[3],
        )
        if all(not _boxes_overlap(box, existing) for existing in occupied):
            return center
    dx, dy = candidate_offsets[0]
    return Point(round(terminal.point.x + dx, 2), round(terminal.point.y + dy, 2))


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
