from __future__ import annotations

from .geometry import (
    GeometryNode,
    NodeAnchor,
    NodeTrunk,
    PlacedShape,
    Point,
    SchematicGeometry,
    TerminalRef,
    TextPlacement,
    _body_box,
    _can_use_flow_layout,
    _choose_node_layout,
    _compile_nodes_to_wires,
    _component_adjacency,
    _component_terminal_name,
    _first_signal_net,
    _is_two_pin_shunt,
    _longest_component_path,
    _make_terminals,
    _net_anchor_x,
    _net_to_components,
    _normalize_active_branch_nodes,
    _place_ground,
    _place_power,
    _place_shape_from_component,
    _place_support_symbol_for_terminal,
    _point_in_box,
    _preferred_source_component,
    _series_orientation,
    _shape_for_component,
    _shunt_orientation,
    _snap_value,
    _standard_texts,
    _terminal,
    _terminal_point,
    pack_schematic_geometry,
)
from .intent import IntentComponent, IntentPattern, SchematicIntent
from .symbols import default_orientation_for_component, terminal_name_for_component
from .topology_layout import TopologyLayout, TopologyPlacement, build_topology_layout


def compile_intent_geometry(intent: SchematicIntent) -> SchematicGeometry:
    topology_layout = build_topology_layout(intent)
    if topology_layout is not None:
        return _finalize_geometry(_compile_topology_layout(intent, topology_layout))
    for pattern in intent.patterns:
        if pattern.kind == "rc_lowpass":
            return _finalize_geometry(_build_rc_lowpass_geometry(intent, pattern))
        if pattern.kind == "rc_highpass":
            return _finalize_geometry(_build_rc_highpass_geometry(intent, pattern))
    if _can_use_flow_layout(intent):
        return _finalize_geometry(_build_flow_geometry(intent))
    return _finalize_geometry(_build_fallback_geometry(intent))


def _finalize_geometry(geometry: SchematicGeometry) -> SchematicGeometry:
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
    return pack_schematic_geometry(geometry)


def _compile_node_labels(geometry: SchematicGeometry) -> list[TextPlacement]:
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


def _snap_geometry_to_grid(geometry: SchematicGeometry) -> SchematicGeometry:
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
    geometry.wires = [type(wire)(points=snap_wire_points(wire.points), uuid_seed=wire.uuid_seed) for wire in geometry.wires]
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
    geometry.junctions = [type(junction)(point=snap_point(junction.point)) for junction in geometry.junctions]
    return geometry


def _compile_topology_layout(intent: SchematicIntent, layout: TopologyLayout) -> SchematicGeometry:
    geometry = SchematicGeometry(name=layout.name)
    by_ref = {comp.ref: comp for comp in intent.components}
    placement_by_ref = {placement.ref: placement for placement in layout.placements}
    for placement in layout.placements:
        shape = _place_topology_item(by_ref, placement)
        geometry.shapes.append(shape)
        if shape.shape not in {"ground", "power"}:
            geometry.labels.extend(_standard_texts(shape))
    geometry.nodes.extend(
        GeometryNode(
            id=connection.id,
            point=Point(connection.point.x, connection.point.y),
            attachments=tuple(
                TerminalRef(owner_ref=attachment.owner_ref, terminal_name=attachment.terminal_name)
                for attachment in connection.attachments
            ),
            render_style=connection.render_style,
            label=_topology_connection_label(intent, by_ref, placement_by_ref, connection),
            role=connection.role,
        )
        for connection in layout.connections
    )
    return geometry


def _place_topology_item(by_ref: dict[str, IntentComponent], placement: TopologyPlacement) -> PlacedShape:
    if placement.ref in by_ref:
        return _place_shape_from_component(
            by_ref[placement.ref],
            Point(placement.center.x, placement.center.y),
            orientation=placement.orientation,
        )
    if placement.shape == "ground":
        return _place_ground(placement.ref, Point(placement.center.x, placement.center.y))
    if placement.shape == "power":
        return _place_power(placement.ref, placement.value or "VCC", Point(placement.center.x, placement.center.y))
    raise AssertionError(f"unknown topology placement '{placement.ref}'")


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


def _build_flow_geometry(intent: SchematicIntent) -> SchematicGeometry:
    geometry = SchematicGeometry(name=intent.name)
    by_ref = {comp.ref: comp for comp in intent.components}
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
            role = intent.nets[net_name].role
            if role == "ground":
                ref = f"#PWR{power_ref_idx:04d}"
                power_ref_idx += 1
                gnd_shape = _place_ground(ref, _place_support_symbol_for_terminal(terminal, "ground", geometry.shapes, preferred="down"))
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
                power_shape = _place_power(ref, net_name.upper(), _place_support_symbol_for_terminal(terminal, "power", geometry.shapes, preferred="up"))
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
            net_points.setdefault(net_name, []).append(terminal.point)

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
                label=net_name,
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
        x = _SHAPE_GROUP_X[group]
        y = _SHAPE_GROUP_Y[group] + counts[group] * _SHAPE_GROUP_STEP_Y[group]
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
            role = intent.nets[net_name].role
            if role == "ground":
                ref = f"#PWR{power_ref_idx:04d}"
                power_ref_idx += 1
                gnd_shape = _place_ground(ref, _place_support_symbol_for_terminal(terminal, "ground", geometry.shapes, preferred="down"))
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
                power_shape = _place_power(ref, net_name.upper(), _place_support_symbol_for_terminal(terminal, "power", geometry.shapes, preferred="up"))
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
            net_points.setdefault(net_name, []).append(terminal.point)

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
                label=net_name,
                render_style="junction" if len(attachments) >= 3 else "inline",
            )
        )
    return geometry


def _topology_connection_label(
    intent: SchematicIntent,
    components_by_ref: dict[str, IntentComponent],
    placements_by_ref: dict[str, TopologyPlacement],
    connection,
) -> str | None:
    candidate_nets: set[str] | None = None
    for attachment in connection.attachments:
        comp = components_by_ref.get(attachment.owner_ref)
        if comp is None:
            continue
        placement = placements_by_ref.get(attachment.owner_ref)
        orientation = (
            placement.orientation
            if placement is not None and placement.orientation
            else default_orientation_for_component(comp.kind, comp.value, comp.model)
        )
        nets_for_attachment = {
            net_name
            for pin_index, net_name in enumerate(comp.nodes)
            if terminal_name_for_component(comp.kind, orientation, pin_index) == attachment.terminal_name
        }
        if candidate_nets is None:
            candidate_nets = nets_for_attachment
        else:
            candidate_nets &= nets_for_attachment
    if not candidate_nets:
        return None
    for net_name in sorted(candidate_nets):
        role = intent.nets.get(net_name)
        if role is not None and role.role != "ground":
            return net_name
    return None


def _component_group(kind: str) -> str:
    if kind in {"V", "I"}:
        return "source"
    if kind in {"R", "C", "L", "D"}:
        return "passive"
    return "active"


_SHAPE_GROUP_X = {
    "source": 50.0,
    "passive": 100.0,
    "active": 150.0,
}

_SHAPE_GROUP_Y = {
    "source": 70.0,
    "passive": 70.0,
    "active": 90.0,
}

_SHAPE_GROUP_STEP_Y = {
    "source": 40.0,
    "passive": 38.0,
    "active": 48.0,
}
