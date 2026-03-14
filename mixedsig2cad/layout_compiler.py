from __future__ import annotations

from collections import defaultdict

from .compiled import place_shape
from .design import ExampleDesign, SchematicLayoutIntent
from .models import CompiledSchematic, GeometryNode, JunctionPlacement, Point, TerminalRef, TextPlacement, WirePath
from .spec import CircuitSpec
from .symbols import component_symbol

GLOBAL_NETS = {"0", "gnd", "vcc", "vdd", "vee", "vss"}


def compile_design(design: ExampleDesign) -> CompiledSchematic:
    geometry = compile_layout_intent(design.circuit, design.layout)
    geometry.name = design.name
    return geometry


def compile_layout_intent(spec: CircuitSpec, layout: SchematicLayoutIntent) -> CompiledSchematic:
    geometry = CompiledSchematic(name=layout.name)
    components_by_ref = {component.ref: component for component in spec.components}

    for placement in layout.components:
        component = components_by_ref.get(placement.ref)
        if component is None:
            raise AssertionError(f"layout component '{placement.ref}' does not exist in CircuitSpec")
        shape_name, _ = component_symbol(component.kind, component.value, component.model)
        geometry.shapes.append(
            place_shape(
                ref=placement.ref,
                value=component.value,
                shape=shape_name,
                orientation=placement.orientation,
                center=placement.center,
                hidden_reference=placement.hidden_reference,
            )
        )
        geometry.labels.append(
            TextPlacement(
                text=placement.ref,
                role="reference",
                position=placement.reference_position,
                owner_ref=placement.ref,
                uuid_seed=f"{layout.name}:{placement.ref}:reference",
            )
        )
        geometry.labels.append(
            TextPlacement(
                text=component.value,
                role="value",
                position=placement.value_position,
                owner_ref=placement.ref,
                uuid_seed=f"{layout.name}:{placement.ref}:value",
            )
        )

    for support in layout.supports:
        if support.shape == "power" and support.value.lower() not in GLOBAL_NETS:
            geometry.labels.append(
                TextPlacement(
                    text=support.value.lower(),
                    role="net_label",
                    position=support.center,
                    owner_ref=support.ref,
                    uuid_seed=f"{layout.name}:{support.ref}:net_label",
                    font_size=1.27,
                )
            )
            continue
        geometry.shapes.append(
            place_shape(
                ref=support.ref,
                value=support.value,
                shape=support.shape,
                orientation=support.orientation,
                center=support.center,
                hidden_reference=support.hidden_reference,
            )
        )
        geometry.labels.append(
            TextPlacement(
                text=support.ref,
                role="reference",
                position=support.reference_position,
                owner_ref=support.ref,
                uuid_seed=f"{layout.name}:{support.ref}:reference",
            )
        )
        geometry.labels.append(
            TextPlacement(
                text=support.value,
                role="value",
                position=support.value_position,
                owner_ref=support.ref,
                uuid_seed=f"{layout.name}:{support.ref}:value",
            )
        )

    for text in layout.texts:
        geometry.labels.append(
            TextPlacement(
                text=text.text,
                role=text.role,
                position=text.position,
                owner_ref=text.owner_ref,
                uuid_seed=f"{layout.name}:{text.owner_ref}:{text.role}:{text.text}",
                font_size=text.font_size,
            )
        )

    for routed_net in layout.routed_nets:
        for index, segment in enumerate(routed_net.segments, start=1):
            geometry.wires.append(WirePath(points=segment, uuid_seed=f"{layout.name}:{routed_net.name}:{index}"))
        for point in routed_net.junctions:
            geometry.junctions.append(JunctionPlacement(point=point))

    geometry.nodes.extend(_derive_layout_nodes(geometry))
    _validate_layout_realizes_spec(spec, geometry)
    return geometry


def _derive_layout_nodes(geometry: CompiledSchematic) -> list[GeometryNode]:
    terminals_by_point: dict[tuple[float, float], list[TerminalRef]] = defaultdict(list)
    for shape in geometry.shapes:
        for terminal in shape.terminals:
            terminals_by_point[(terminal.point.x, terminal.point.y)].append(TerminalRef(shape.ref, terminal.name))

    graph: dict[tuple[float, float], set[tuple[float, float]]] = defaultdict(set)
    for wire in geometry.wires:
        for start, end in zip(wire.points, wire.points[1:]):
            a = (start.x, start.y)
            b = (end.x, end.y)
            graph[a].add(b)
            graph[b].add(a)

    for point in terminals_by_point:
        graph.setdefault(point, set())
    junction_points = {(junction.point.x, junction.point.y) for junction in geometry.junctions}
    for point in junction_points:
        graph.setdefault(point, set())

    nodes: list[GeometryNode] = []
    visited: set[tuple[float, float]] = set()
    component_index = 1
    for point in graph:
        if point in visited:
            continue
        stack = [point]
        component: set[tuple[float, float]] = set()
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            component.add(current)
            stack.extend(graph[current] - visited)
        attachments: list[TerminalRef] = []
        for item in sorted(component):
            attachments.extend(terminals_by_point.get(item, ()))
        if len(attachments) < 2:
            continue
        node_point = sorted(component & junction_points)[0] if component & junction_points else sorted(component)[0]
        nodes.append(
            GeometryNode(
                id=f"layout:{component_index}",
                point=Point(*node_point),
                attachments=tuple(attachments),
                render_style="junction" if len(attachments) >= 3 or node_point in junction_points else "inline",
            )
        )
        component_index += 1
    return nodes


def _validate_layout_realizes_spec(spec: CircuitSpec, geometry: CompiledSchematic) -> None:
    shape_by_ref = {shape.ref: shape for shape in geometry.shapes}
    for component in spec.components:
        shape = shape_by_ref.get(component.ref)
        if shape is None:
            raise AssertionError(f"compiled layout missing component '{component.ref}'")
