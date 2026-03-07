from __future__ import annotations

import re
from pathlib import Path

from mixedsig2cad.compiled import CompiledSchematic, make_body_box, make_terminals
from mixedsig2cad.geometry import (
    GeometryNode,
    JunctionPlacement,
    Point,
    PlacedShape,
    TerminalRef,
    TextPlacement,
    WirePath,
)
from mixedsig2cad.symbols import inverse_kicad_symbol_map

_INVERSE_KICAD = inverse_kicad_symbol_map()


def import_kicad_schematic(path: str | Path) -> CompiledSchematic:
    text = Path(path).read_text(encoding="utf-8")
    name = _match_group(text, r'\(title "([^"]+)"\)') or Path(path).stem
    geometry = CompiledSchematic(name=name)

    for block in _top_level_blocks(text, "symbol"):
        shape = _parse_symbol(block)
        geometry.shapes.append(shape)
        geometry.labels.extend(_parse_symbol_labels(shape, block, name))

    geometry.wires.extend(_parse_wires(text, name))
    geometry.junctions.extend(_parse_junctions(text))
    geometry.nodes.extend(_derive_nodes(geometry.shapes, geometry.wires, geometry.junctions))
    return geometry


def _parse_symbol(block: str) -> PlacedShape:
    lib_id = _require_group(block, r'\(lib_id "([^"]+)"\)')
    x, y, angle = _require_groups(block, r"\(at\s+([-0-9.]+)\s+([-0-9.]+)\s+([-0-9.]+)\)")
    ref, ref_hidden, ref_pos = _parse_property(block, "Reference")
    value, _, _ = _parse_property(block, "Value")
    shape_name, orientation = _INVERSE_KICAD[(lib_id, int(float(angle)))]
    center = Point(round(float(x), 2), round(float(y), 2))
    return PlacedShape(
        ref=ref,
        value=value,
        shape=shape_name,
        orientation=orientation,
        center=center,
        terminals=make_terminals(shape_name, orientation, center),
        body_box=make_body_box(shape_name, orientation, center),
        hidden_reference=ref_hidden,
    )


def _parse_symbol_labels(shape: PlacedShape, block: str, schematic_name: str) -> list[TextPlacement]:
    labels: list[TextPlacement] = []
    for role, prop in (("reference", "Reference"), ("value", "Value")):
        text, _, pos = _parse_property(block, prop)
        labels.append(
            TextPlacement(
                text=text,
                role=role,
                position=pos,
                owner_ref=shape.ref,
                uuid_seed=f"{schematic_name}:{shape.ref}:{role}",
            )
        )
    return labels


def _parse_property(block: str, prop_name: str) -> tuple[str, bool, Point]:
    prop_block = _extract_nested_block(block, f'(property "{prop_name}"')
    value = _require_group(prop_block, r'^.*?\(property "[^"]+" "([^"]*)"', flags=re.S)
    x, y = _require_groups(prop_block, r"\(at\s+([-0-9.]+)\s+([-0-9.]+)\s+[-0-9.]+\)")
    hidden = " hide)" in prop_block
    return value, hidden, Point(round(float(x), 2), round(float(y), 2))


def _parse_wires(text: str, schematic_name: str) -> list[WirePath]:
    wires: list[WirePath] = []
    for idx, block in enumerate(_top_level_blocks(text, "wire"), start=1):
        points = [
            Point(round(float(x), 2), round(float(y), 2))
            for x, y in re.findall(r"\(xy\s+([-0-9.]+)\s+([-0-9.]+)\)", block)
        ]
        if len(points) >= 2:
            wires.append(WirePath(points=tuple(points), uuid_seed=f"{schematic_name}:imported:wire:{idx}"))
    return wires


def _parse_junctions(text: str) -> list[JunctionPlacement]:
    return [
        JunctionPlacement(point=Point(round(float(x), 2), round(float(y), 2)))
        for x, y in re.findall(r"\(junction\s+\(at\s+([-0-9.]+)\s+([-0-9.]+)\)", text)
    ]


def _derive_nodes(
    shapes: list[PlacedShape],
    wires: list[WirePath],
    junctions: list[JunctionPlacement],
) -> list[GeometryNode]:
    terminals_by_point: dict[tuple[float, float], list[TerminalRef]] = {}
    for shape in shapes:
        for terminal in shape.terminals:
            terminals_by_point.setdefault((terminal.point.x, terminal.point.y), []).append(TerminalRef(shape.ref, terminal.name))

    graph: dict[tuple[float, float], set[tuple[float, float]]] = {}
    for wire in wires:
        for start, end in zip(wire.points, wire.points[1:]):
            a = (start.x, start.y)
            b = (end.x, end.y)
            graph.setdefault(a, set()).add(b)
            graph.setdefault(b, set()).add(a)
    for point in terminals_by_point:
        graph.setdefault(point, set())
    for junction in junctions:
        graph.setdefault((junction.point.x, junction.point.y), set())

    visited: set[tuple[float, float]] = set()
    nodes: list[GeometryNode] = []
    component_index = 1
    junction_points = {(junction.point.x, junction.point.y) for junction in junctions}

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
        node_point = _choose_node_point(component, attachments, junction_points)
        nodes.append(
            GeometryNode(
                id=f"imported:{component_index}",
                point=node_point,
                attachments=tuple(attachments),
                render_style="junction" if len(attachments) >= 3 or (node_point.x, node_point.y) in junction_points else "inline",
            )
        )
        component_index += 1
    return nodes


def _choose_node_point(
    component: set[tuple[float, float]],
    attachments: list[TerminalRef],
    junction_points: set[tuple[float, float]],
) -> Point:
    component_junctions = sorted(component & junction_points)
    if component_junctions:
        x, y = component_junctions[0]
        return Point(x, y)
    if len(component) == 1:
        x, y = next(iter(component))
        return Point(x, y)
    sorted_points = sorted(component)
    if len(sorted_points) == 2:
        (x1, y1), (x2, y2) = sorted_points
        return Point(round((x1 + x2) / 2.0, 2), round((y1 + y2) / 2.0, 2))
    xs = [point[0] for point in component]
    ys = [point[1] for point in component]
    return Point(round(sum(xs) / len(xs), 2), round(sum(ys) / len(ys), 2))


def _top_level_blocks(text: str, kind: str) -> list[str]:
    blocks: list[str] = []
    needle = f"({kind} "
    start = 0
    while True:
        idx = text.find(needle, start)
        if idx < 0:
            break
        if _depth_at(text, idx) == 1:
            blocks.append(_extract_nested_block(text[idx:], needle))
        start = idx + len(needle)
    return blocks


def _depth_at(text: str, limit: int) -> int:
    depth = 0
    in_string = False
    escape = False
    for ch in text[:limit]:
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
    return depth


def _extract_nested_block(text: str, needle: str) -> str:
    start = text.find(needle)
    if start < 0:
        raise AssertionError(f"missing block starting with {needle}")
    depth = 0
    in_string = False
    escape = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]
    raise AssertionError(f"unterminated block starting with {needle}")


def _match_group(text: str, pattern: str, *, flags: int = 0) -> str | None:
    match = re.search(pattern, text, flags)
    return match.group(1) if match else None


def _require_group(text: str, pattern: str, *, flags: int = 0) -> str:
    match = re.search(pattern, text, flags)
    if match is None:
        raise AssertionError(f"pattern not found: {pattern}")
    return match.group(1)


def _require_groups(text: str, pattern: str, *, flags: int = 0) -> tuple[str, ...]:
    match = re.search(pattern, text, flags)
    if match is None:
        raise AssertionError(f"pattern not found: {pattern}")
    return match.groups()
