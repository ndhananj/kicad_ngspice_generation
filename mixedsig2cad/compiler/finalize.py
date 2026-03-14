from __future__ import annotations

from ..geometry import (
    _body_box,
    _compile_nodes_to_wires,
    _make_terminals,
    _normalize_active_branch_nodes,
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


def _compile_node_labels(geometry: CompiledSchematic) -> list[TextPlacement]:
    labels: list[TextPlacement] = []
    for node in geometry.nodes:
        if not node.label or node.role == "local_ground":
            continue
        labels.append(
            TextPlacement(
                text=node.label,
                role="net_label",
                position=Point(node.point.x, node.point.y),
                owner_ref=node.id,
                uuid_seed=f"{geometry.name}:{node.id}:label",
            )
        )
    return labels


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
        )
        for text in geometry.labels
    ]
    geometry.junctions = [JunctionPlacement(point=snap_point(junction.point)) for junction in geometry.junctions]
    return geometry
