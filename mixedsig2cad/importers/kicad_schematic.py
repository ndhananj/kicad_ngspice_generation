from __future__ import annotations

import re
from pathlib import Path

from mixedsig2cad.compiled import make_body_box, make_terminals
from mixedsig2cad.models import (
    CompiledSchematic,
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
    name = _match_group(text, r'\(title\s+"([^"]+)"\)') or Path(path).stem
    geometry = CompiledSchematic(name=name)

    for block in _top_level_blocks(text, "symbol"):
        if '(lib_id "' not in block:
            continue
        shape = _parse_symbol(block)
        geometry.shapes.append(shape)
        geometry.labels.extend(_parse_symbol_labels(shape, block, name))

    geometry.labels.extend(_parse_global_labels(text, name))
    geometry.wires.extend(_parse_wires(text, name))
    geometry.junctions.extend(_parse_junctions(text))
    geometry.nodes.extend(_derive_nodes(geometry.shapes, geometry.wires, geometry.junctions))
    return geometry


def _parse_symbol(block: str) -> PlacedShape:
    lib_id = _require_group(block, r'\(lib_id\s+"([^"]+)"\)')
    x, y, angle = _require_groups(block, r"\(at\s+([-0-9.]+)\s+([-0-9.]+)\s+([-0-9.]+)\)")
    ref, ref_hidden, _ = _parse_property(block, "Reference")
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


def _parse_global_labels(text: str, schematic_name: str) -> list[TextPlacement]:
    labels: list[TextPlacement] = []
    for index, block in enumerate(_top_level_blocks(text, "label"), start=1):
        label_text = _require_group(block, r'\(label\s+"([^"]+)"')
        x, y = _require_groups(block, r"\(at\s+([-0-9.]+)\s+([-0-9.]+)\s+[-0-9.]+\)")
        font_size = _parse_font_size(block)
        labels.append(
            TextPlacement(
                text=label_text,
                role="net_label",
                position=Point(round(float(x), 2), round(float(y), 2)),
                owner_ref=f"label:{index}",
                uuid_seed=f"{schematic_name}:label:{index}",
                font_size=font_size,
            )
        )
    return labels


def _parse_property(block: str, prop_name: str) -> tuple[str, bool, Point]:
    prop_block = _extract_named_property_block(block, prop_name)
    value = _require_group(prop_block, r'^\(property\s+"[^"]+"\s+"([^"]*)"', flags=re.S)
    x, y = _require_groups(prop_block, r"\(at\s+([-0-9.]+)\s+([-0-9.]+)\s+[-0-9.]+\)")
    hidden = "(hide yes)" in prop_block or re.search(r"\(effects\b.*?\bhide\)", prop_block, re.S) is not None
    return value, hidden, Point(round(float(x), 2), round(float(y), 2))


def _parse_font_size(block: str) -> float:
    match = re.search(r"\(size\s+([-0-9.]+)\s+([-0-9.]+)\)", block)
    if match is None:
        return 1.27
    return round(float(match.group(1)), 2)


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
    junctions: list[JunctionPlacement] = []
    for block in _top_level_blocks(text, "junction"):
        x, y = _require_groups(block, r"\(at\s+([-0-9.]+)\s+([-0-9.]+)\)")
        junctions.append(JunctionPlacement(point=Point(round(float(x), 2), round(float(y), 2))))
    return junctions


def _derive_nodes(
    shapes: list[PlacedShape],
    wires: list[WirePath],
    junctions: list[JunctionPlacement],
) -> list[GeometryNode]:
    terminals_by_point: dict[tuple[float, float], list[TerminalRef]] = {}
    for shape in shapes:
        for terminal in shape.terminals:
            terminals_by_point.setdefault((terminal.point.x, terminal.point.y), []).append(
                TerminalRef(shape.ref, terminal.name)
            )

    graph: dict[tuple[float, float], set[tuple[float, float]]] = {}
    for wire in wires:
        for start, end in zip(wire.points, wire.points[1:]):
            a = (start.x, start.y)
            b = (end.x, end.y)
            graph.setdefault(a, set()).add(b)
            graph.setdefault(b, set()).add(a)
    for point in terminals_by_point:
        graph.setdefault(point, set())
    junction_points = {(junction.point.x, junction.point.y) for junction in junctions}
    for point in junction_points:
        graph.setdefault(point, set())

    visited: set[tuple[float, float]] = set()
    nodes: list[GeometryNode] = []
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
        node_point = _choose_node_point(component, junction_points)
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


def _choose_node_point(component: set[tuple[float, float]], junction_points: set[tuple[float, float]]) -> Point:
    component_junctions = sorted(component & junction_points)
    if component_junctions:
        x, y = component_junctions[0]
        return Point(x, y)
    x, y = sorted(component)[0]
    return Point(x, y)


def _top_level_blocks(text: str, kind: str) -> list[str]:
    blocks: list[str] = []
    pattern = re.compile(rf"\({kind}(?=[\s\)])")
    for match in pattern.finditer(text):
        idx = match.start()
        if _depth_at(text, idx) != 1:
            continue
        blocks.append(_extract_nested_block(text, idx))
    return blocks


def _extract_named_property_block(text: str, prop_name: str) -> str:
    pattern = re.compile(rf'\(property\s+"{re.escape(prop_name)}"(?=[\s"])')
    match = pattern.search(text)
    if match is None:
        raise AssertionError(f"missing property '{prop_name}'")
    return _extract_nested_block(text, match.start())


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


def _extract_nested_block(text: str, start: int) -> str:
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
    raise AssertionError(f"unterminated block at {start}")


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
