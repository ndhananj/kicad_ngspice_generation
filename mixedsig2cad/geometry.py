from __future__ import annotations

from collections import Counter

from .intent import IntentComponent, SchematicIntent
from .models import (
    BoundingBox,
    CompiledSchematic,
    GeometryNode,
    JunctionPlacement,
    NodeAnchor,
    NodeTrunk,
    PinExitCorridor,
    PlacedShape,
    PlacedTerminal,
    Point,
    TerminalRef,
    TerminalTemplate,
    TextPlacement,
    WirePath,
)
from .symbols import (
    KICAD_SYMBOLS,
    body_box,
    component_symbol,
    terminal_defs,
    terminal_name_for_component,
)


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
    key: {terminal.name: terminal.offset for terminal in terminal_defs(*key)}
    for key in KICAD_SYMBOLS
}

ROUTING_CLEARANCE = 5.08
KICAD_CONNECTION_GRID = 1.27
PAGE_LEFT = 30.0
PAGE_TOP = 30.0
PAGE_RIGHT = 245.0
PAGE_BOTTOM = 170.0
PAGE_FIT_MARGIN = 8.0
def validate_schematic_geometry(geometry: CompiledSchematic) -> None:
    shape_by_ref = {shape.ref: shape for shape in geometry.shapes}
    point_usage: dict[tuple[float, float], int] = {}
    wire_points: set[tuple[float, float]] = set()
    segments: list[tuple[Point, Point, str]] = []
    for shape in geometry.shapes:
        _assert_on_kicad_grid(shape.center, context=f"shape center '{shape.ref}'")
        for terminal in shape.terminals:
            _assert_on_kicad_grid(terminal.point, context=f"terminal '{shape.ref}.{terminal.name}'")
    for wire in geometry.wires:
        if len(wire.points) < 2:
            raise AssertionError(f"wire path '{wire.uuid_seed}' has fewer than 2 points")
        if _is_local_support_wire(wire.uuid_seed) and _bend_count(wire.points) > 2:
            raise AssertionError(f"local support wire '{wire.uuid_seed}' has unnecessary bends")
        for point in wire.points:
            _assert_on_kicad_grid(point, context=f"wire point '{wire.uuid_seed}'")
            wire_points.add((point.x, point.y))
        for point in (wire.points[0], wire.points[-1]):
            key = (point.x, point.y)
            point_usage[key] = point_usage.get(key, 0) + 1
        for start, end in zip(wire.points, wire.points[1:]):
            if _segment_hits_shape_body(shape_by_ref, wire.uuid_seed, start, end):
                raise AssertionError(f"wire '{wire.uuid_seed}' crosses a component body")
            segments.append((start, end, wire.uuid_seed))

    bounds = _geometry_bounds(geometry)
    if bounds is not None:
        if bounds.left < PAGE_LEFT or bounds.top < PAGE_TOP or bounds.right > PAGE_RIGHT or bounds.bottom > PAGE_BOTTOM:
            raise AssertionError(
                f"geometry bounds {(bounds.left, bounds.top, bounds.right, bounds.bottom)} exceed usable page area"
            )

    junction_points = {(junction.point.x, junction.point.y) for junction in geometry.junctions}
    node_points = {(node.point.x, node.point.y) for node in geometry.nodes}
    for junction_point in junction_points:
        _assert_on_kicad_grid(Point(*junction_point), context=f"junction {junction_point}")
        if junction_point not in node_points:
            raise AssertionError(f"junction at {junction_point} does not correspond to a geometry node")
        if junction_point not in wire_points:
            raise AssertionError(f"junction at {junction_point} does not lie on a compiled wire path")

    _assert_no_ambiguous_wire_overlaps(segments)
    _assert_no_undeclared_wire_intersections(segments, node_points=node_points, junction_points=junction_points)

    for anchor in geometry.anchors:
        _assert_on_kicad_grid(anchor.point, context="node anchor")
        if any(_point_in_box(anchor.point, shape.body_box) for shape in geometry.shapes):
            raise AssertionError(f"node anchor at {(anchor.point.x, anchor.point.y)} lies inside a shape body")
    for trunk in geometry.trunks:
        for shape in geometry.shapes:
            if _segment_intersects_box(trunk.start, trunk.end, shape.body_box):
                raise AssertionError(
                    f"node trunk {(trunk.start.x, trunk.start.y)} -> {(trunk.end.x, trunk.end.y)} intersects shape body '{shape.ref}'"
                )

    for node in geometry.nodes:
        _assert_on_kicad_grid(node.point, context=f"node '{node.id}'")
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


def pack_schematic_geometry(geometry: CompiledSchematic) -> CompiledSchematic:
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


def _compile_nodes_to_wires(geometry: CompiledSchematic) -> None:
    shape_by_ref = {shape.ref: shape for shape in geometry.shapes}
    occupied = [(shape.ref, shape.body_box) for shape in geometry.shapes]
    for node in geometry.nodes:
        existing_segments = _wire_segments(geometry.wires)
        attachment_terminals = [_resolve_terminal(shape_by_ref, attachment) for attachment in node.attachments]
        attachment_points = [terminal.point for terminal in attachment_terminals]
        distinct_points = {(point.x, point.y) for point in attachment_points}
        if node.render_style == "junction" or len(node.attachments) >= 3:
            geometry.junctions.append(JunctionPlacement(point=node.point))
        route_via_node = _should_route_via_node(node, attachment_terminals)
        if len(distinct_points) == 1 and next(iter(distinct_points)) == (node.point.x, node.point.y):
            if not route_via_node:
                continue
        if len(node.attachments) == 2 and not route_via_node:
            start_ref, end_ref = node.attachments
            path_points = _route_connection(
                shape_by_ref,
                occupied,
                start_ref,
                end_ref,
                existing_segments=existing_segments,
            )
            geometry.wires.append(
                WirePath(points=path_points, uuid_seed=f"{geometry.name}:{node.id}:{start_ref.owner_ref}:{end_ref.owner_ref}")
            )
            continue
        shared_wires = _compile_shared_node_wires(
            geometry.name,
            node,
            shape_by_ref,
            occupied,
            attachment_terminals,
            existing_segments=existing_segments,
        )
        if shared_wires is not None:
            geometry.wires.extend(shared_wires)
            continue
        for idx, attachment in enumerate(node.attachments, start=1):
            point = _resolve_terminal_ref(shape_by_ref, attachment)
            if point.x == node.point.x and point.y == node.point.y:
                continue
            path_points = _route_attachment_to_node(
                shape_by_ref,
                occupied,
                attachment,
                node.point,
                existing_segments=existing_segments,
            )
            geometry.wires.append(
                WirePath(points=path_points, uuid_seed=f"{geometry.name}:{node.id}:{attachment.owner_ref}:{idx}")
            )


def _normalize_active_branch_nodes(nodes: list[GeometryNode], shapes: list[PlacedShape]) -> list[GeometryNode]:
    shape_by_ref = {shape.ref: shape for shape in shapes}
    normalized: list[GeometryNode] = []
    for node in nodes:
        point = _preferred_branch_point(node, shape_by_ref)
        normalized.append(
            GeometryNode(
                id=node.id,
                point=point,
                attachments=node.attachments,
                render_style=node.render_style,
                label=node.label,
                role=node.role,
            )
        )
    return normalized


def _preferred_branch_point(node: GeometryNode, shape_by_ref: dict[str, PlacedShape]) -> Point:
    if node.role in {"collector_node", "emitter_node"}:
        return node.point
    if node.role in {"local_ground", "local_supply", "labeled_supply"}:
        return node.point
    if node.role == "gate_bus":
        return node.point
    boxes = [shape.body_box for shape in shape_by_ref.values()]
    all_terminals = [_resolve_terminal(shape_by_ref, attachment) for attachment in node.attachments]
    active_terminals = [
        _resolve_terminal(shape_by_ref, attachment)
        for attachment in node.attachments
        if shape_by_ref[attachment.owner_ref].shape in {"opamp", "npn_bjt", "pmos", "nmos"}
    ]
    attachment_points = [_resolve_terminal_ref(shape_by_ref, attachment) for attachment in node.attachments]
    if not active_terminals:
        return node.point
    shared_point = _shared_node_preferred_point(node, all_terminals, boxes)
    if shared_point is not None and all(not _point_in_box(shared_point, box) for box in boxes):
        return shared_point
    if (
        node.role in {"sum_node", "feedback_join", "stage_output", "base_drive"}
        and all(not _point_in_box(node.point, box) for box in boxes)
        and all(_point_distance(node.point, terminal.point) >= 4.0 for terminal in active_terminals)
    ):
        return node.point
    distinct_points = {(point.x, point.y) for point in attachment_points}
    if (
        node.role not in {"sum_node", "feedback_join", "stage_output", "base_drive"}
        and len(node.attachments) < 3
        and len(distinct_points) > 1
    ):
        return node.point
    for terminal in active_terminals:
        if terminal.preferred_branch_offset is None:
            continue
        candidate = _branch_point_from_terminal(terminal, boxes)
        if candidate is not None:
            return candidate
    return node.point


def _shared_node_preferred_point(node: GeometryNode, terminals: list[PlacedTerminal], boxes: list[BoundingBox]) -> Point | None:
    if node.role not in {"stage_output", "transistor_stack"}:
        return None
    attachment_points = _shared_node_attachment_points(node, terminals, boxes)
    pseudo_terminals = tuple(
        PlacedTerminal(name=str(idx), point=point, side="")
        for idx, point in enumerate(attachment_points, start=1)
    )
    axis = _shared_attachment_axis(list(pseudo_terminals))
    if axis is None:
        return None
    orientation, axis_value = axis
    off_axis_points = [
        point
        for point in attachment_points
        if (point.x if orientation == "vertical" else point.y) != axis_value
    ]
    if orientation == "vertical":
        if off_axis_points:
            return Point(round(axis_value, 2), round(_average_coordinate(point.y for point in off_axis_points), 2))
        return Point(round(axis_value, 2), round(_average_coordinate(point.y for point in attachment_points), 2))
    if off_axis_points:
        return Point(round(_average_coordinate(point.x for point in off_axis_points), 2), round(axis_value, 2))
    return Point(round(_average_coordinate(point.x for point in attachment_points), 2), round(axis_value, 2))


def _average_coordinate(values) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def _shared_node_attachment_points(
    node: GeometryNode,
    terminals: list[PlacedTerminal],
    boxes: list[BoundingBox],
) -> list[Point]:
    points: list[Point] = []
    for terminal in terminals:
        if node.role == "gate_bus" and terminal.preferred_branch_offset is not None:
            branch_point = _branch_point_from_terminal(terminal, boxes)
            if branch_point is not None:
                points.append(branch_point)
                continue
        points.append(terminal.point)
    return points


def _should_route_via_node(node: GeometryNode, terminals: list[PlacedTerminal]) -> bool:
    if node.role in {"sum_node", "feedback_join", "stage_output", "base_drive", "transistor_stack"}:
        return True
    if node.render_style == "junction" or len(terminals) >= 3:
        return True
    active_terminals = [terminal for terminal in terminals if terminal.preferred_branch_offset is not None]
    if not active_terminals:
        return False
    distinct_points = {(terminal.point.x, terminal.point.y) for terminal in terminals}
    return len(distinct_points) == 1


def _compile_shared_node_wires(
    geometry_name: str,
    node: GeometryNode,
    shape_by_ref: dict[str, PlacedShape],
    occupied: list[tuple[str, BoundingBox]],
    terminals: list[PlacedTerminal],
    *,
    existing_segments: list[tuple[Point, Point, str]] | None = None,
) -> list[WirePath] | None:
    if node.role not in {"stage_output", "transistor_stack", "gate_bus"}:
        return None
    occupied_boxes = [box for _, box in occupied]
    resolved_points = _shared_node_attachment_points(node, terminals, occupied_boxes)
    axis = _shared_attachment_axis(
        [PlacedTerminal(name=terminal.name, point=point, side=terminal.side) for terminal, point in zip(terminals, resolved_points)]
    )
    if axis is None:
        return None
    orientation, axis_value = axis
    points_by_attachment = {
        attachment: (terminal.point, resolved_point)
        for attachment, terminal, resolved_point in zip(node.attachments, terminals, resolved_points)
    }
    axis_points = [
        _project_point_to_axis(point, orientation, axis_value)
        for _terminal_point, point in points_by_attachment.values()
    ]
    node_axis_point = _project_point_to_axis(node.point, orientation, axis_value)
    axis_points.append(node_axis_point)
    spine = _build_axis_spine(axis_points, orientation)
    wires: list[WirePath] = []
    if len(spine) >= 2:
        wires.append(WirePath(points=spine, uuid_seed=f"{geometry_name}:{node.id}:spine"))
    if node_axis_point != node.point:
        node_path = _best_path_between_points(
            node_axis_point,
            node.point,
            occupied_boxes,
            existing_segments=existing_segments,
        )
        wires.append(WirePath(points=node_path, uuid_seed=f"{geometry_name}:{node.id}:node"))
    for idx, attachment in enumerate(node.attachments, start=1):
        terminal_point, point = points_by_attachment[attachment]
        branch_target = _project_point_to_axis(point, orientation, axis_value)
        if terminal_point == branch_target:
            continue
        path_points = _route_attachment_to_point(
            shape_by_ref,
            occupied,
            attachment,
            branch_target,
            existing_segments=existing_segments,
        )
        wires.append(WirePath(points=path_points, uuid_seed=f"{geometry_name}:{node.id}:{attachment.owner_ref}:{idx}"))
    deduped = [_dedupe_wire_path(wire) for wire in wires]
    return [wire for wire in deduped if len(wire.points) >= 2]


def _resolve_terminal_ref(shape_by_ref: dict[str, PlacedShape], terminal_ref: TerminalRef) -> Point:
    shape = shape_by_ref.get(terminal_ref.owner_ref)
    if shape is None:
        raise AssertionError(f"unknown shape '{terminal_ref.owner_ref}' in geometry node")
    return _terminal_point(shape, terminal_ref.terminal_name)


def _shared_attachment_axis(terminals: list[PlacedTerminal]) -> tuple[str, float] | None:
    if len(terminals) < 2:
        return None
    x_counts = Counter(terminal.point.x for terminal in terminals)
    y_counts = Counter(terminal.point.y for terminal in terminals)
    candidates: list[tuple[int, float, str]] = []
    for x, count in x_counts.items():
        if count >= 2:
            candidates.append((count, _axis_span(terminals, "vertical", x), f"vertical:{x:.2f}"))
    for y, count in y_counts.items():
        if count >= 2:
            candidates.append((count, _axis_span(terminals, "horizontal", y), f"horizontal:{y:.2f}"))
    if not candidates:
        return None
    count, _span, encoded = max(candidates, key=lambda item: (item[0], item[1]))
    orientation, value = encoded.split(":", 1)
    return orientation, float(value)


def _axis_span(terminals: list[PlacedTerminal], orientation: str, axis_value: float) -> float:
    relevant = [
        terminal.point.y if orientation == "vertical" else terminal.point.x
        for terminal in terminals
        if (terminal.point.x if orientation == "vertical" else terminal.point.y) == axis_value
    ]
    if len(relevant) < 2:
        return 0.0
    return max(relevant) - min(relevant)


def _project_point_to_axis(point: Point, orientation: str, axis_value: float) -> Point:
    if orientation == "vertical":
        return Point(round(axis_value, 2), point.y)
    return Point(point.x, round(axis_value, 2))


def _build_axis_spine(points: list[Point], orientation: str) -> tuple[Point, ...]:
    if orientation == "vertical":
        x = points[0].x
        ys = sorted({round(point.y, 2) for point in points})
        return (Point(x, ys[0]), Point(x, ys[-1])) if len(ys) >= 2 else ()
    y = points[0].y
    xs = sorted({round(point.x, 2) for point in points})
    return (Point(xs[0], y), Point(xs[-1], y)) if len(xs) >= 2 else ()


def _route_attachment_to_point(
    shape_by_ref: dict[str, PlacedShape],
    occupied: list[tuple[str, BoundingBox]],
    attachment: TerminalRef,
    target: Point,
    *,
    existing_segments: list[tuple[Point, Point, str]] | None = None,
) -> tuple[Point, ...]:
    terminal = _resolve_terminal(shape_by_ref, attachment)
    boxes = [box for _, box in occupied]
    return _best_path(
        terminal,
        shape_by_ref[attachment.owner_ref].body_box,
        target,
        None,
        boxes,
        existing_segments=existing_segments,
    )


def _best_path_between_points(
    start: Point,
    end: Point,
    boxes: list[BoundingBox],
    *,
    existing_segments: list[tuple[Point, Point, str]] | None = None,
) -> tuple[Point, ...]:
    if start == end:
        return (start,)
    candidates = [
        (start, end),
        (start, Point(end.x, start.y), end),
        (start, Point(start.x, end.y), end),
    ]
    valid_paths = [
        _simplify_path(path)
        for path in (_sanitize_raw_path(candidate) for candidate in candidates)
        if _point_path_is_clear(path, boxes, existing_segments=existing_segments)
    ]
    if not valid_paths:
        return _simplify_path((start, end))
    valid_paths.sort(key=lambda path: (_bend_count(path), _path_length(path)))
    return valid_paths[0]


def _point_path_is_clear(
    path: tuple[Point, ...],
    boxes: list[BoundingBox],
    *,
    existing_segments: list[tuple[Point, Point, str]] | None = None,
) -> bool:
    for start, end in zip(path, path[1:]):
        for box in boxes:
            if _segment_intersects_box(start, end, box):
                return False
    if existing_segments and _path_hits_existing_segments(path, existing_segments):
        return False
    return True


def _wire_segments(wires: list[WirePath]) -> list[tuple[Point, Point, str]]:
    return [
        (start, end, wire.uuid_seed)
        for wire in wires
        for start, end in zip(wire.points, wire.points[1:])
    ]


def _path_hits_existing_segments(
    path: tuple[Point, ...],
    existing_segments: list[tuple[Point, Point, str]],
) -> bool:
    for start, end in zip(path, path[1:]):
        for other_start, other_end, _seed in existing_segments:
            overlap = _overlapping_segment(start, end, other_start, other_end)
            if overlap is not None and not _shared_endpoint_only(start, end, other_start, other_end, overlap):
                return True
            intersection = _orthogonal_intersection(start, end, other_start, other_end)
            if intersection is None:
                continue
            if intersection in {
                (start.x, start.y),
                (end.x, end.y),
                (other_start.x, other_start.y),
                (other_end.x, other_end.y),
            }:
                continue
            return True
    return False


def _shared_endpoint_only(
    start: Point,
    end: Point,
    other_start: Point,
    other_end: Point,
    overlap: tuple[Point, Point],
) -> bool:
    return overlap[0] == overlap[1] and overlap[0] in {start, end, other_start, other_end}


def _dedupe_wire_path(wire: WirePath) -> WirePath:
    return WirePath(points=_simplify_path(wire.points), uuid_seed=wire.uuid_seed)


def _choose_node_layout(
    net_name: str,
    points: list[Point],
    attachments: list[TerminalRef],
    shapes_by_ref: dict[str, PlacedShape],
) -> tuple[Point, NodeTrunk | None]:
    active_branch_point = _active_attachment_branch_point(attachments, shapes_by_ref)
    if active_branch_point is not None:
        return active_branch_point, None
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


def _active_attachment_branch_point(
    attachments: list[TerminalRef],
    shapes_by_ref: dict[str, PlacedShape],
) -> Point | None:
    if len(attachments) < 2:
        return None
    active_terminals: list[PlacedTerminal] = []
    all_points: list[Point] = []
    for attachment in attachments:
        shape = shapes_by_ref[attachment.owner_ref]
        terminal = _terminal(shape, attachment.terminal_name)
        all_points.append(terminal.point)
        if shape.shape in {"opamp", "npn_bjt", "pmos", "nmos"} and terminal.preferred_branch_offset is not None:
            active_terminals.append(terminal)
    if not active_terminals:
        return None
    if len(attachments) < 3 and len({(point.x, point.y) for point in all_points}) > 1:
        return None
    boxes = [shape.body_box for shape in shapes_by_ref.values()]
    terminal = active_terminals[0]
    return _branch_point_from_terminal(terminal, boxes)


def _branch_point_from_terminal(terminal: PlacedTerminal, boxes: list[BoundingBox]) -> Point | None:
    if terminal.preferred_branch_offset is None:
        return None
    dx, dy = terminal.preferred_branch_offset
    for scale in (1.0, 1.5, 2.0, 2.5, 3.0):
        candidate = Point(
            round(terminal.point.x + dx * scale, 2),
            round(terminal.point.y + dy * scale, 2),
        )
        if all(not _point_in_box(candidate, box) for box in boxes):
            return candidate
    return None


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
    return component_symbol(comp.kind, comp.value, comp.model)


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
    templates = terminal_defs(shape, orientation)
    return tuple(
        PlacedTerminal(
            name=template.name,
            point=Point(round(center.x + template.offset[0], 2), round(center.y + template.offset[1], 2)),
            side=template.exit_direction,
            preferred_connection_class=template.preferred_connection_class,
            preferred_branch_offset=template.preferred_branch_offset,
        )
        for template in templates
    )


def _body_box(shape: str, orientation: str, center: Point) -> BoundingBox:
    left, top, right, bottom = body_box(shape, orientation)
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
    return terminal_name_for_component(kind, shape.orientation, pin_index)


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
    *,
    existing_segments: list[tuple[Point, Point, str]] | None = None,
) -> tuple[Point, ...]:
    start_shape = shape_by_ref[start_ref.owner_ref]
    end_shape = shape_by_ref[end_ref.owner_ref]
    start = _resolve_terminal(shape_by_ref, start_ref)
    end = _resolve_terminal(shape_by_ref, end_ref)
    connection_class = _classify_connection(start_shape, start, end_shape, end)
    if connection_class in {"local_ground_drop", "local_supply_rise"}:
        return _route_local_support_connection(start, start_shape.body_box, end, end_shape.body_box)
    return _route_between_terminals(
        shape_by_ref,
        occupied,
        start_ref,
        end_ref,
        existing_segments=existing_segments,
    )


def _route_between_terminals(
    shape_by_ref: dict[str, PlacedShape],
    occupied: list[tuple[str, BoundingBox]],
    start_ref: TerminalRef,
    end_ref: TerminalRef,
    *,
    existing_segments: list[tuple[Point, Point, str]] | None = None,
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
        existing_segments=existing_segments,
    )


def _route_attachment_to_node(
    shape_by_ref: dict[str, PlacedShape],
    occupied: list[tuple[str, BoundingBox]],
    attachment: TerminalRef,
    node_point: Point,
    *,
    existing_segments: list[tuple[Point, Point, str]] | None = None,
) -> tuple[Point, ...]:
    terminal = _resolve_terminal(shape_by_ref, attachment)
    boxes = [box for _, box in occupied]
    return _best_path(
        terminal,
        shape_by_ref[attachment.owner_ref].body_box,
        node_point,
        None,
        boxes,
        existing_segments=existing_segments,
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
        return _simplify_path((start.point, end.point))
    start_exit = _terminal_exit_point(start.point, start.side, start_box)
    end_exit = _terminal_exit_point(end.point, end.side, end_box)
    if start_exit.x == end_exit.x or start_exit.y == end_exit.y:
        return _simplify_path((start.point, start_exit, end_exit, end.point))
    if start.side in {"top", "bottom"} and end.side in {"top", "bottom"}:
        elbow = Point(start_exit.x, end_exit.y)
    elif start.side in {"left", "right"} and end.side in {"left", "right"}:
        elbow = Point(end_exit.x, start_exit.y)
    elif start.side in {"top", "bottom"}:
        elbow = Point(start_exit.x, end_exit.y)
    else:
        elbow = Point(end_exit.x, start_exit.y)
    return _simplify_path((start.point, start_exit, elbow, end_exit, end.point))


def _best_path(
    start: PlacedTerminal,
    start_box: BoundingBox,
    end: Point | PlacedTerminal,
    end_box: BoundingBox | None,
    boxes: list[BoundingBox],
    *,
    existing_segments: list[tuple[Point, Point, str]] | None = None,
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
    for x in x_candidates:
        for y in y_candidates:
            candidates.append(
                (
                    start.point,
                    start_exit,
                    Point(x, start_exit.y),
                    Point(x, y),
                    Point(end_exit.x, y),
                    end_exit,
                    end_point,
                )
            )

    valid_paths = [
        _simplify_path(path)
        for path in (_sanitize_raw_path(candidate) for candidate in candidates)
        if _path_is_clear(
            path,
            boxes,
            start_corridor,
            end_corridor,
            start_box=start_box,
            end_box=end_box,
            existing_segments=existing_segments,
        )
    ]
    if not valid_paths:
        return _simplify_path((start.point, start_exit, end_exit, end_point))
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


def _sanitize_raw_path(path: tuple[Point, ...]) -> tuple[Point, ...]:
    normalized: list[Point] = []
    for point in path:
        if normalized and normalized[-1].x == point.x and normalized[-1].y == point.y:
            continue
        normalized.append(point)
    return tuple(normalized)


def _simplify_path(path: tuple[Point, ...]) -> tuple[Point, ...]:
    normalized = list(_sanitize_raw_path(path))
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
    *,
    start_box: BoundingBox,
    end_box: BoundingBox | None,
    existing_segments: list[tuple[Point, Point, str]] | None = None,
) -> bool:
    for start, end in zip(path, path[1:]):
        for box in boxes:
            if box == start_box and _segment_uses_exit_corridor(start, end, start_corridor):
                continue
            if end_corridor is not None and end_box is not None and box == end_box and _segment_uses_exit_corridor(start, end, end_corridor):
                continue
            if _segment_intersects_box(start, end, box):
                return False
    if existing_segments and _path_hits_existing_segments(path, existing_segments):
        return False
    return True


def _segment_uses_exit_corridor(start: Point, end: Point, corridor: PinExitCorridor) -> bool:
    if corridor.start.x == corridor.end.x:
        if start.x != end.x or start.x != corridor.start.x:
            return False
        seg_top, seg_bottom = sorted((start.y, end.y))
        corridor_top, corridor_bottom = sorted((corridor.start.y, corridor.end.y))
        if seg_top > corridor_top or seg_bottom < corridor_bottom:
            return False
        start_dist = abs(start.y - corridor.start.y)
        end_dist = abs(end.y - corridor.start.y)
        return start_dist == 0 or end_dist == 0
    if corridor.start.y == corridor.end.y:
        if start.y != end.y or start.y != corridor.start.y:
            return False
        seg_left, seg_right = sorted((start.x, end.x))
        corridor_left, corridor_right = sorted((corridor.start.x, corridor.end.x))
        if seg_left > corridor_left or seg_right < corridor_right:
            return False
        start_dist = abs(start.x - corridor.start.x)
        end_dist = abs(end.x - corridor.start.x)
        return start_dist == 0 or end_dist == 0
    return False


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


def _assert_no_ambiguous_wire_overlaps(segments: list[tuple[Point, Point, str]]) -> None:
    for idx, (start, end, seed) in enumerate(segments):
        for other_start, other_end, other_seed in segments[idx + 1:]:
            overlap = _overlapping_segment(start, end, other_start, other_end)
            if overlap is None:
                continue
            if _wire_logical_node_key(seed) == _wire_logical_node_key(other_seed):
                continue
            raise AssertionError(
                f"wire segments '{seed}' and '{other_seed}' overlap from "
                f"{(overlap[0].x, overlap[0].y)} to {(overlap[1].x, overlap[1].y)}"
            )


def _assert_no_undeclared_wire_intersections(
    segments: list[tuple[Point, Point, str]],
    *,
    node_points: set[tuple[float, float]],
    junction_points: set[tuple[float, float]],
) -> None:
    declared_points = node_points | junction_points
    for idx, (start, end, seed) in enumerate(segments):
        for other_start, other_end, other_seed in segments[idx + 1:]:
            intersection = _orthogonal_intersection(start, end, other_start, other_end)
            if intersection is None:
                continue
            if intersection in declared_points:
                continue
            if intersection in {
                (start.x, start.y),
                (end.x, end.y),
                (other_start.x, other_start.y),
                (other_end.x, other_end.y),
            }:
                continue
            raise AssertionError(
                f"wire segments '{seed}' and '{other_seed}' intersect at {intersection} without a declared node"
            )


def _overlapping_segment(first_start: Point, first_end: Point, second_start: Point, second_end: Point) -> tuple[Point, Point] | None:
    if first_start.x == first_end.x == second_start.x == second_end.x:
        x = first_start.x
        first_top, first_bottom = sorted((first_start.y, first_end.y))
        second_top, second_bottom = sorted((second_start.y, second_end.y))
        top = max(first_top, second_top)
        bottom = min(first_bottom, second_bottom)
        if bottom <= top:
            return None
        return Point(x, top), Point(x, bottom)
    if first_start.y == first_end.y == second_start.y == second_end.y:
        y = first_start.y
        first_left, first_right = sorted((first_start.x, first_end.x))
        second_left, second_right = sorted((second_start.x, second_end.x))
        left = max(first_left, second_left)
        right = min(first_right, second_right)
        if right <= left:
            return None
        return Point(left, y), Point(right, y)
    return None


def _orthogonal_intersection(
    first_start: Point,
    first_end: Point,
    second_start: Point,
    second_end: Point,
) -> tuple[float, float] | None:
    if first_start.x == first_end.x and second_start.y == second_end.y:
        x = first_start.x
        y = second_start.y
        if _value_in_range(x, second_start.x, second_end.x) and _value_in_range(y, first_start.y, first_end.y):
            return round(x, 2), round(y, 2)
        return None
    if first_start.y == first_end.y and second_start.x == second_end.x:
        x = second_start.x
        y = first_start.y
        if _value_in_range(x, first_start.x, first_end.x) and _value_in_range(y, second_start.y, second_end.y):
            return round(x, 2), round(y, 2)
        return None
    return None


def _value_in_range(value: float, first: float, second: float) -> bool:
    low, high = sorted((first, second))
    return low <= value <= high


def _wire_logical_node_key(seed: str) -> str:
    parts = seed.split(":")
    if parts[-1] in {"spine", "node"}:
        return ":".join(parts[:-1])
    if len(parts) >= 3:
        return ":".join(parts[:-2])
    return seed


def _bend_count(path: tuple[Point, ...]) -> int:
    return max(0, len(path) - 2)


def _path_length(path: tuple[Point, ...]) -> float:
    length = 0.0
    for start, end in zip(path, path[1:]):
        length += abs(end.x - start.x) + abs(end.y - start.y)
    return length


def _point_distance(a: Point, b: Point) -> float:
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5


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


def _geometry_bounds(geometry: CompiledSchematic) -> BoundingBox | None:
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


def _translate_geometry(geometry: CompiledSchematic, dx: float, dy: float) -> CompiledSchematic:
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
                PlacedTerminal(
                    name=terminal.name,
                    point=move_point(terminal.point),
                    side=terminal.side,
                    preferred_connection_class=terminal.preferred_connection_class,
                    preferred_branch_offset=terminal.preferred_branch_offset,
                )
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
            role=node.role,
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


def _snap_value(value: float) -> float:
    return round(round(value / KICAD_CONNECTION_GRID) * KICAD_CONNECTION_GRID, 2)


def _assert_on_kicad_grid(point: Point, *, context: str) -> None:
    snapped = (_snap_value(point.x), _snap_value(point.y))
    actual = (round(point.x, 2), round(point.y, 2))
    if actual != snapped:
        raise AssertionError(f"{context} is off the KiCad connection grid: {actual} != {snapped}")


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
    prototype = body_box(symbol_kind, "down" if symbol_kind == "ground" else "up")
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
