from __future__ import annotations

from ..geometry import (
    _body_box,
    _compile_nodes_to_wires,
    _make_terminals,
    _normalize_active_branch_nodes,
    _resolve_terminal,
    _point_in_box,
    _snap_value,
    pack_schematic_geometry,
)
from ..models import (
    CompiledSchematic,
    GeometryNode,
    JunctionPlacement,
    NodeAnchor,
    NodeTrunk,
    PlacedShape,
    Point,
    TextPlacement,
    WirePath,
)


def finalize_compiled_schematic(geometry: CompiledSchematic) -> CompiledSchematic:
    geometry.nodes = _normalize_active_branch_nodes(geometry.nodes, geometry.shapes)
    geometry = _snap_geometry_to_grid(geometry)
    labeled_wires, labeled_texts, geometry.nodes = _compile_labeled_stub_nodes(geometry)
    geometry.wires.extend(labeled_wires)
    geometry.labels.extend(labeled_texts)
    geometry.labels.extend(_compile_node_labels(geometry))
    geometry.anchors = [
        NodeAnchor(point=node.point)
        for node in geometry.nodes
        if node.role not in {"local_ground", "local_supply"}
        and all(not _point_in_box(node.point, shape.body_box) for shape in geometry.shapes)
    ]
    geometry.trunks = []
    _compile_nodes_to_wires(geometry)
    geometry = _snap_geometry_to_grid(geometry)
    geometry = pack_schematic_geometry(geometry)
    geometry = _snap_geometry_to_grid(geometry)
    return geometry


def _compile_labeled_stub_nodes(
    geometry: CompiledSchematic,
) -> tuple[list[WirePath], list[TextPlacement], list[GeometryNode]]:
    shape_by_ref = {shape.ref: shape for shape in geometry.shapes}
    wires: list[WirePath] = []
    labels: list[TextPlacement] = []
    remaining_nodes: list[GeometryNode] = []
    for node in geometry.nodes:
        if node.role != "labeled_supply" or not node.label:
            remaining_nodes.append(node)
            continue
        for idx, attachment in enumerate(node.attachments, start=1):
            terminal = _resolve_terminal(shape_by_ref, attachment)
            label_point = _label_stub_endpoint(terminal.point, terminal.side)
            if terminal.point != label_point:
                wires.append(
                    WirePath(
                        points=(terminal.point, label_point),
                        uuid_seed=f"{geometry.name}:{node.id}:{attachment.owner_ref}:{idx}:stub",
                    )
                )
            labels.append(
                TextPlacement(
                    text=node.label,
                    role="net_label",
                    position=label_point,
                    owner_ref=node.id,
                    uuid_seed=f"{geometry.name}:{node.id}:{attachment.owner_ref}:{idx}:label",
                    font_size=_preferred_net_label_font_size(geometry.name, node.label),
                )
            )
    return wires, labels, remaining_nodes


def _label_stub_endpoint(point: Point, side: str, distance: float = 2.54) -> Point:
    if side == "left":
        return Point(point.x - distance, point.y)
    if side == "right":
        return Point(point.x + distance, point.y)
    if side == "top":
        return Point(point.x, point.y - distance)
    if side == "bottom":
        return Point(point.x, point.y + distance)
    return point


def _compile_node_labels(geometry: CompiledSchematic) -> list[TextPlacement]:
    labels: list[TextPlacement] = []
    for node in geometry.nodes:
        if not node.label or node.role in {"local_ground", "local_supply"}:
            continue
        labels.append(
            TextPlacement(
                text=node.label,
                role="net_label",
                position=Point(node.point.x, node.point.y),
                owner_ref=node.id,
                uuid_seed=f"{geometry.name}:{node.id}:label",
                font_size=_preferred_net_label_font_size(geometry.name, node.label),
            )
        )
    return labels


def _preferred_net_label_font_size(schematic_name: str, label: str) -> float:
    if schematic_name == "opamp_inverting" and label in {"vin", "vplus_ref", "vminus", "vout"}:
        return 1.50
    return 1.27


def _snap_geometry_to_grid(geometry: CompiledSchematic) -> CompiledSchematic:
    def snap_point(point: Point) -> Point:
        return Point(_snap_value(point.x), _snap_value(point.y))

    def snap_wire_points(points: tuple[Point, ...]) -> tuple[Point, ...]:
        if not points:
            return ()
        snapped: list[Point] = [snap_point(points[0])]
        for point in points[1:]:
            end = snap_point(point)
            start = snapped[-1]
            if start == end:
                continue
            if start.x != end.x and start.y != end.y:
                corner = Point(end.x, start.y)
                if corner != start and corner != end:
                    snapped.append(corner)
            snapped.append(end)
        return tuple(snapped)

    geometry.shapes = [
        PlacedShape(
            ref=shape.ref,
            value=shape.value,
            shape=shape.shape,
            orientation=shape.orientation,
            center=snap_point(shape.center),
            terminals=_make_terminals(shape.shape, shape.orientation, snap_point(shape.center)),
            body_box=_body_box(shape.shape, shape.orientation, snap_point(shape.center)),
            hidden_reference=shape.hidden_reference,
        )
        for shape in geometry.shapes
    ]
    geometry.nodes = [
        GeometryNode(
            id=node.id,
            point=snap_point(node.point),
            attachments=node.attachments,
            render_style=node.render_style,
            label=node.label,
            role=node.role,
        )
        for node in geometry.nodes
    ]
    geometry.anchors = [NodeAnchor(point=snap_point(anchor.point)) for anchor in geometry.anchors]
    geometry.trunks = [NodeTrunk(start=snap_point(trunk.start), end=snap_point(trunk.end)) for trunk in geometry.trunks]
    geometry.wires = [WirePath(points=snap_wire_points(wire.points), uuid_seed=wire.uuid_seed) for wire in geometry.wires]
    geometry.labels = [
        TextPlacement(
            text=text.text,
            role=text.role,
            position=snap_point(text.position),
            owner_ref=text.owner_ref,
            uuid_seed=text.uuid_seed,
            font_size=text.font_size,
        )
        for text in geometry.labels
    ]
    geometry.junctions = [JunctionPlacement(point=snap_point(junction.point)) for junction in geometry.junctions]
    return geometry
