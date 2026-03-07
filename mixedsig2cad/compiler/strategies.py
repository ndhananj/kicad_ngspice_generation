from __future__ import annotations

from ..geometry import (
    _choose_node_layout,
    _component_adjacency,
    _component_terminal_name,
    _first_signal_net,
    _is_two_pin_shunt,
    _longest_component_path,
    _net_anchor_x,
    _place_ground,
    _place_power,
    _place_shape_from_component,
    _place_support_symbol_for_terminal,
    _preferred_source_component,
    _series_orientation,
    _shape_for_component,
    _shunt_orientation,
    _standard_texts,
    _terminal,
    _terminal_point,
)
from ..intent import SchematicIntent
from ..models import CompiledSchematic, GeometryNode, NodeAnchor, PlacedShape, Point, TerminalRef


def build_flow(intent: SchematicIntent) -> CompiledSchematic:
    geometry = CompiledSchematic(name=intent.name)
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
        centers[ref] = Point(x_cursor + idx * 30.0, main_y)
        orientations[ref] = _series_orientation(comp)

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

    shapes_by_ref = _place_components(intent, geometry, centers, orientations)
    _attach_supports_and_build_nodes(intent, geometry, shapes_by_ref)
    return geometry


def build_fallback(intent: SchematicIntent) -> CompiledSchematic:
    geometry = CompiledSchematic(name=intent.name)
    shapes_by_ref: dict[str, PlacedShape] = {}
    counts = {"source": 0, "passive": 0, "active": 0}
    group_x = {"source": 50.0, "passive": 100.0, "active": 150.0}
    group_y = {"source": 70.0, "passive": 70.0, "active": 90.0}
    group_step_y = {"source": 40.0, "passive": 38.0, "active": 48.0}

    for comp in intent.components:
        group = _component_group(comp.kind)
        center = Point(group_x[group], group_y[group] + counts[group] * group_step_y[group])
        counts[group] += 1
        shape = _place_shape_from_component(comp, center)
        shapes_by_ref[comp.ref] = shape
        geometry.shapes.append(shape)
        geometry.labels.extend(_standard_texts(shape))

    _attach_supports_and_build_nodes(intent, geometry, shapes_by_ref)
    return geometry


def _place_components(
    intent: SchematicIntent,
    geometry: CompiledSchematic,
    centers: dict[str, Point],
    orientations: dict[str, str],
) -> dict[str, PlacedShape]:
    shapes_by_ref: dict[str, PlacedShape] = {}
    for comp in intent.components:
        shape = _place_shape_from_component(comp, centers[comp.ref], orientation=orientations[comp.ref])
        shapes_by_ref[comp.ref] = shape
        geometry.shapes.append(shape)
        geometry.labels.extend(_standard_texts(shape))
    return shapes_by_ref


def _attach_supports_and_build_nodes(
    intent: SchematicIntent,
    geometry: CompiledSchematic,
    shapes_by_ref: dict[str, PlacedShape],
) -> None:
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


def _component_group(kind: str) -> str:
    if kind in {"V", "I"}:
        return "source"
    if kind in {"R", "C", "L", "D"}:
        return "passive"
    return "active"
