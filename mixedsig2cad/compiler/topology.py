from __future__ import annotations

from ..geometry import _place_ground, _place_power, _place_shape_from_component, _standard_texts
from ..intent import IntentComponent, SchematicIntent
from ..models import CompiledSchematic, GeometryNode, Point, TerminalRef
from ..symbols import default_orientation_for_component, terminal_name_for_component
from ..topology_layout import TopologyLayout, TopologyPlacement


def build_from_topology_layout(intent: SchematicIntent, layout: TopologyLayout) -> CompiledSchematic:
    geometry = CompiledSchematic(name=layout.name)
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


def _place_topology_item(by_ref: dict[str, IntentComponent], placement: TopologyPlacement):
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
