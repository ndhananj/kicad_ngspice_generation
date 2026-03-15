from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from mixedsig2cad.importers.kicad_schematic import import_kicad_schematic
from mixedsig2cad.compiled import make_body_box, make_terminals
from mixedsig2cad.exporters.kicad import render_kicad_schematic
from mixedsig2cad.models import (
    BoundingBox,
    CompiledSchematic,
    Point,
    PlacedShape,
    TextPlacement,
    WirePath,
)
from mixedsig2cad.projections.kicad import _embedded_kicad_symbols, project_geometry_to_kicad
from mixedsig2cad.symbols import KICAD_SYMBOLS, kicad_pin_map, kicad_symbol, terminal_defs

PROBE_CENTER = Point(100.0, 100.0)
PROBE_STUB_LENGTH = 14.0
PROBE_LABEL_OFFSET = 5.0


@dataclass(frozen=True, slots=True)
class RenderedPinObservation:
    name: str
    side: str
    point: Point


@dataclass(frozen=True, slots=True)
class RenderedSymbolObservation:
    shape: str
    orientation: str
    center: Point
    terminal_sides: dict[str, str]
    pin_name_terminals: dict[str, str]


@dataclass(frozen=True, slots=True)
class RenderedSymbolComparison:
    shape: str
    orientation: str
    lib_id: str
    angle: int
    expected_terminal_sides: dict[str, str]
    rendered_terminal_sides: dict[str, str]
    expected_pin_name_terminals: dict[str, str]
    rendered_pin_name_terminals: dict[str, str]
    passed: bool
    notes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RenderedSvgText:
    text: str
    anchor: Point
    bounds: BoundingBox


@dataclass(frozen=True, slots=True)
class RenderedExampleLabelComparison:
    schematic_name: str
    label_text: str
    role: str
    expected_position: Point
    rendered_bounds: BoundingBox
    passed: bool
    notes: tuple[str, ...]


def build_symbol_probe_geometry(shape: str, orientation: str) -> CompiledSchematic:
    ref = _probe_ref(shape)
    value = _probe_value(shape)
    geometry = CompiledSchematic(name=f"probe_{shape}_{orientation}")
    placed = PlacedShape(
        ref=ref,
        value=value,
        shape=shape,
        orientation=orientation,
        center=PROBE_CENTER,
        terminals=make_terminals(shape, orientation, PROBE_CENTER),
        body_box=make_body_box(shape, orientation, PROBE_CENTER),
        hidden_reference=False,
    )
    geometry.shapes.append(placed)
    geometry.labels.append(
        TextPlacement(
            text=ref,
            role="reference",
            position=Point(PROBE_CENTER.x, PROBE_CENTER.y - 14.0),
            owner_ref=ref,
            uuid_seed=f"{geometry.name}:{ref}:reference",
        )
    )
    geometry.labels.append(
        TextPlacement(
            text=value,
            role="value",
            position=Point(PROBE_CENTER.x, PROBE_CENTER.y + 14.0),
            owner_ref=ref,
            uuid_seed=f"{geometry.name}:{ref}:value",
        )
    )
    for terminal in placed.terminals:
        stub_end = _stub_endpoint(terminal.point, terminal.side)
        geometry.wires.append(
            WirePath(
                points=(terminal.point, stub_end),
                uuid_seed=f"{geometry.name}:wire:{terminal.name}",
            )
        )
        label_point = _stub_endpoint(stub_end, terminal.side, PROBE_LABEL_OFFSET)
        geometry.labels.append(
            TextPlacement(
                text=f"TERM:{terminal.name}",
                role="probe_terminal",
                position=label_point,
                owner_ref=ref,
                uuid_seed=f"{geometry.name}:label:{terminal.name}",
            )
        )
    return geometry


def observe_rendered_symbol_svg(path: str | Path, shape: str, orientation: str) -> RenderedSymbolObservation:
    root = ET.fromstring(Path(path).read_text(encoding="utf-8"))
    texts = _svg_texts(root)
    wires = _svg_wires(root)
    terminal_sides, terminal_points = _observe_terminal_sides(texts, wires)
    pin_name_terminals = _observe_pin_name_terminals(texts, terminal_points, shape, orientation)
    return RenderedSymbolObservation(
        shape=shape,
        orientation=orientation,
        center=PROBE_CENTER,
        terminal_sides=terminal_sides,
        pin_name_terminals=pin_name_terminals,
    )


def validate_rendered_kicad_symbols(*, strict_pin_labels: bool = True) -> list[RenderedSymbolComparison]:
    kicad_cli = shutil.which("kicad-cli")
    if not kicad_cli:
        return []
    results: list[RenderedSymbolComparison] = []
    with tempfile.TemporaryDirectory(prefix="kicad-symbol-probes-") as tmpdir:
        tmp = Path(tmpdir)
        for shape, orientation in sorted(KICAD_SYMBOLS):
            geometry = build_symbol_probe_geometry(shape, orientation)
            projection = project_geometry_to_kicad(geometry)
            schematic_path = tmp / f"{geometry.name}.kicad_sch"
            schematic_path.write_text(render_kicad_schematic(projection), encoding="utf-8")
            svg_path = _export_svg(kicad_cli, schematic_path, tmp / geometry.name)
            observation = observe_rendered_symbol_svg(svg_path, shape, orientation)
            results.append(_compare_rendered_symbol(shape, orientation, observation, strict_pin_labels=strict_pin_labels))
    failures = [result for result in results if not result.passed]
    if failures:
        details = "\n".join(
            f"{result.shape}/{result.orientation}: {'; '.join(result.notes)}"
            for result in failures
        )
        raise AssertionError(f"rendered KiCad symbol validation failed:\n{details}")
    return results


def validate_rendered_example_labels(paths: list[str | Path]) -> list[RenderedExampleLabelComparison]:
    kicad_cli = shutil.which("kicad-cli")
    if not kicad_cli:
        return []
    results: list[RenderedExampleLabelComparison] = []
    failures: list[RenderedExampleLabelComparison] = []
    with tempfile.TemporaryDirectory(prefix="kicad-example-labels-") as tmpdir:
        tmp = Path(tmpdir)
        for raw_path in paths:
            path = Path(raw_path)
            geometry = import_kicad_schematic(path)
            svg_path = _export_svg(kicad_cli, path, tmp / path.stem)
            rendered_texts = observe_rendered_svg_texts(svg_path)
            comparisons = _compare_rendered_example_labels(geometry, rendered_texts)
            results.extend(comparisons)
            failures.extend(result for result in comparisons if not result.passed)
    if failures:
        details = "\n".join(
            f"{result.schematic_name}:{result.role}:{result.label_text}: {'; '.join(result.notes)}"
            for result in failures
        )
        raise AssertionError(f"rendered example label validation failed:\n{details}")
    return results


def _compare_rendered_symbol(
    shape: str,
    orientation: str,
    observation: RenderedSymbolObservation,
    *,
    strict_pin_labels: bool,
) -> RenderedSymbolComparison:
    lib_id, angle = kicad_symbol(shape, orientation)
    expected_terminal_sides = {template.name: template.exit_direction for template in terminal_defs(shape, orientation)}
    expected_pin_name_terminals: dict[str, str] = {}
    pin_map = kicad_pin_map(shape, orientation)
    lib_pins = _embedded_kicad_symbols()[lib_id]
    for terminal_name, pin_number in pin_map.items():
        pin = lib_pins.get(pin_number)
        if pin is None or pin.name in {"", "~"}:
            continue
        expected_pin_name_terminals[pin.name] = terminal_name
    hard_failures: list[str] = []
    for terminal_name, expected_side in expected_terminal_sides.items():
        observed_side = observation.terminal_sides.get(terminal_name)
        if observed_side is None:
            hard_failures.append(f"missing rendered terminal observation for {terminal_name}")
        elif observed_side != expected_side:
            hard_failures.append(
                f"terminal {terminal_name} rendered on {observed_side}, expected {expected_side}"
            )
    for pin_name, expected_terminal in expected_pin_name_terminals.items():
        observed_terminal = observation.pin_name_terminals.get(pin_name)
        if observed_terminal is None:
            continue
        if observed_terminal != expected_terminal:
            hard_failures.append(
                f"pin name {pin_name} rendered nearest terminal {observed_terminal}, expected {expected_terminal}"
            )
    return RenderedSymbolComparison(
        shape=shape,
        orientation=orientation,
        lib_id=lib_id,
        angle=angle,
        expected_terminal_sides=expected_terminal_sides,
        rendered_terminal_sides=observation.terminal_sides,
        expected_pin_name_terminals=expected_pin_name_terminals,
        rendered_pin_name_terminals=observation.pin_name_terminals,
        passed=not hard_failures,
        notes=tuple(hard_failures),
    )


def _export_svg(kicad_cli: str, schematic_path: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["HOME"] = str(output_dir)
    env["XDG_CONFIG_HOME"] = str(output_dir / ".config")
    result = subprocess.run(
        [
            kicad_cli,
            "sch",
            "export",
            "svg",
            "--output",
            str(output_dir),
            str(schematic_path),
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"kicad-cli SVG export failed for {schematic_path}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    svg_path = output_dir / f"{schematic_path.stem}.svg"
    if not svg_path.exists():
        raise AssertionError(f"expected SVG output for {schematic_path}")
    return svg_path


def observe_rendered_svg_texts(path: str | Path) -> list[RenderedSvgText]:
    root = ET.fromstring(Path(path).read_text(encoding="utf-8"))
    events: list[tuple[str, ET.Element, tuple[float, float, float, float, float, float]]] = []
    _flatten_svg_events(root, _identity_matrix(), events)
    rendered: list[RenderedSvgText] = []
    pending_text: tuple[ET.Element, tuple[float, float, float, float, float, float]] | None = None
    for kind, element, transform in events:
        if kind == "text":
            content = (element.text or "").strip()
            pending_text = (element, transform) if content else None
            continue
        if kind != "stroked-text" or pending_text is None:
            continue
        text_element, text_transform = pending_text
        content = (text_element.text or "").strip()
        desc = element.find("{*}desc")
        if desc is None or (desc.text or "").strip() != content:
            continue
        bounds = _stroked_text_bounds(element, transform)
        if bounds is None:
            continue
        rendered.append(RenderedSvgText(text=content, anchor=_text_anchor(text_element, text_transform), bounds=bounds))
        pending_text = None
    return rendered


def _compare_rendered_example_labels(
    geometry: CompiledSchematic,
    rendered_texts: list[RenderedSvgText],
) -> list[RenderedExampleLabelComparison]:
    labels = _visible_example_labels(geometry)
    unmatched = list(rendered_texts)
    comparisons: list[RenderedExampleLabelComparison] = []
    accepted_bounds: list[BoundingBox] = []
    for label in labels:
        match = _nearest_rendered_text(label, unmatched)
        if match is None:
            result = RenderedExampleLabelComparison(
                schematic_name=geometry.name,
                label_text=label.text,
                role=label.role,
                expected_position=label.position,
                rendered_bounds=BoundingBox(label.position.x, label.position.y, label.position.x, label.position.y),
                passed=False,
                notes=("missing rendered label",),
            )
            comparisons.append(result)
            continue
        unmatched.remove(match)
        notes = list(_rendered_label_notes(label, match.bounds, geometry, accepted_bounds))
        accepted_bounds.append(match.bounds)
        comparisons.append(
            RenderedExampleLabelComparison(
                schematic_name=geometry.name,
                label_text=label.text,
                role=label.role,
                expected_position=label.position,
                rendered_bounds=match.bounds,
                passed=not notes,
                notes=tuple(notes),
            )
        )
    return comparisons


def _visible_example_labels(geometry: CompiledSchematic) -> list[TextPlacement]:
    shape_by_ref = {shape.ref: shape for shape in geometry.shapes}
    visible: list[TextPlacement] = []
    for label in geometry.labels:
        if label.role == "reference":
            owner = shape_by_ref.get(label.owner_ref)
            if owner is not None and owner.hidden_reference:
                continue
            visible.append(label)
        elif label.role in {"value", "net_label"}:
            visible.append(label)
    return visible


def _nearest_rendered_text(label: TextPlacement, rendered_texts: list[RenderedSvgText]) -> RenderedSvgText | None:
    candidates = [item for item in rendered_texts if item.text == label.text]
    if not candidates:
        return None
    best = min(candidates, key=lambda item: _distance(item.anchor, label.position))
    if _distance(best.anchor, label.position) > 8.0:
        return None
    return best


def _rendered_label_notes(
    label: TextPlacement,
    bounds: BoundingBox,
    geometry: CompiledSchematic,
    accepted_bounds: list[BoundingBox],
) -> tuple[str, ...]:
    notes: list[str] = []
    exclusion = _label_exclusion_zone(label, geometry)
    if _boxes_overlap(bounds, exclusion):
        notes.append("rendered text overlaps labeled object")
    for existing in accepted_bounds:
        if _boxes_overlap(bounds, existing):
            notes.append("rendered text overlaps another example label")
            break
    return tuple(notes)


def _label_exclusion_zone(label: TextPlacement, geometry: CompiledSchematic) -> BoundingBox:
    shape_by_ref = {shape.ref: shape for shape in geometry.shapes}
    if label.role in {"reference", "value"} and label.owner_ref in shape_by_ref:
        return _expand_box(shape_by_ref[label.owner_ref].body_box, 0.2)
    anchor = _net_label_anchor(label.position, geometry)
    return BoundingBox(anchor.x - 0.2, anchor.y - 0.2, anchor.x + 0.2, anchor.y + 0.2)


def _nearest_anchor(position: Point, geometry: CompiledSchematic) -> Point:
    anchors: list[Point] = []
    anchors.extend(node.point for node in geometry.nodes)
    anchors.extend(junction.point for junction in geometry.junctions)
    for shape in geometry.shapes:
        anchors.extend(terminal.point for terminal in shape.terminals)
    for wire in geometry.wires:
        anchors.extend(wire.points)
    if not anchors:
        return position
    return min(anchors, key=lambda point: (_distance(point, position), point.x, point.y))


def _net_label_anchor(position: Point, geometry: CompiledSchematic) -> Point:
    for label in geometry.labels:
        if label.role == "net_label" and label.position == position and label.anchor_position is not None:
            return label.anchor_position
    stub_matches: list[Point] = []
    for wire in geometry.wires:
        points = wire.points
        if len(points) != 2:
            continue
        if _distance(points[1], position) < 0.05:
            stub_matches.append(points[0])
        elif _distance(points[0], position) < 0.05:
            stub_matches.append(points[1])
    if stub_matches:
        return min(stub_matches, key=lambda point: (_distance(point, position), point.x, point.y))
    return _nearest_anchor(position, geometry)


def _svg_texts(root: ET.Element) -> list[tuple[str, Point]]:
    texts: list[tuple[str, Point]] = []
    for text in root.iter():
        if not text.tag.endswith("text"):
            continue
        content = (text.text or "").strip()
        if not content:
            continue
        try:
            x = round(float(text.attrib.get("x", "0")), 2)
            y = round(float(text.attrib.get("y", "0")), 2)
        except ValueError:
            continue
        texts.append((content, Point(x, y)))
    return texts


def _svg_wires(root: ET.Element) -> list[tuple[Point, ...]]:
    wires: list[tuple[Point, ...]] = []
    current_wire_group = False
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag == "g":
            style = element.attrib.get("style", "")
            current_wire_group = "stroke:#009600" in style
            continue
        if tag != "path" or not current_wire_group:
            continue
        coords = [float(value) for value in re.findall(r"[-0-9.]+", element.attrib.get("d", ""))]
        if len(coords) < 4:
            continue
        wires.append(tuple(Point(round(coords[idx], 2), round(coords[idx + 1], 2)) for idx in range(0, len(coords), 2)))
    return wires


def _observe_terminal_sides(texts: list[tuple[str, Point]], wires: list[tuple[Point, ...]]) -> tuple[dict[str, str], dict[str, Point]]:
    observed: dict[str, str] = {}
    points: dict[str, Point] = {}
    for content, point in texts:
        if not content.startswith("TERM:"):
            continue
        terminal_name = content.split(":", 1)[1]
        match = _nearest_wire_endpoint(point, wires)
        if match is None:
            continue
        endpoint, wire = match
        pin_point = wire[0] if wire[-1] == endpoint else wire[-1]
        branch_point = pin_point
        if _distance(PROBE_CENTER, pin_point) < 1.0:
            branch_point = endpoint
        observed[terminal_name] = _relative_side(PROBE_CENTER, branch_point)
        points[terminal_name] = branch_point
    return observed, points


def _observe_pin_name_terminals(
    texts: list[tuple[str, Point]],
    terminal_points: dict[str, Point],
    shape: str,
    orientation: str,
) -> dict[str, str]:
    lib_id, _ = kicad_symbol(shape, orientation)
    lib_pins = _embedded_kicad_symbols()[lib_id]
    valid_pin_names = {pin.name for pin in lib_pins.values() if pin.name not in {"", "~"}}
    expected_points = _expected_pin_name_points(shape, orientation)
    assignments: dict[str, str] = {}
    for content, point in texts:
        if content not in valid_pin_names:
            continue
        if content in assignments:
            continue
        nearest = min(expected_points.items(), key=lambda item: _distance(point, item[1]))
        assignments[content] = nearest[0]
    return assignments


def _expected_pin_name_points(shape: str, orientation: str) -> dict[str, Point]:
    lib_id, angle = kicad_symbol(shape, orientation)
    pin_map = kicad_pin_map(shape, orientation)
    lib_pins = _embedded_kicad_symbols()[lib_id]
    expected: dict[str, Point] = {}
    for terminal_name, pin_number in pin_map.items():
        pin = lib_pins.get(pin_number)
        if pin is None or pin.name in {"", "~"}:
            continue
        x, y = _rotate_offset(pin.x, pin.y, angle)
        expected[terminal_name] = Point(round(PROBE_CENTER.x + x, 2), round(PROBE_CENTER.y + y, 2))
    return expected


def _rotate_offset(x: float, y: float, angle: int) -> tuple[float, float]:
    if angle == 0:
        return round(x, 2), round(y, 2)
    if angle == 90:
        return round(-y, 2), round(x, 2)
    if angle == 180:
        return round(-x, 2), round(-y, 2)
    if angle == 270:
        return round(y, 2), round(-x, 2)
    raise AssertionError(f"unsupported pin rotation angle {angle}")


def _nearest_wire_endpoint(point: Point, wires: list[tuple[Point, ...]], radius: float = 8.0) -> tuple[Point, tuple[Point, ...]] | None:
    best: tuple[float, Point, tuple[Point, ...]] | None = None
    for wire in wires:
        for endpoint in (wire[0], wire[-1]):
            distance = ((endpoint.x - point.x) ** 2 + (endpoint.y - point.y) ** 2) ** 0.5
            if distance > radius:
                continue
            if best is None or distance < best[0]:
                best = (distance, endpoint, wire)
    if best is None:
        return None
    return best[1], best[2]


def _relative_side(center: Point, point: Point) -> str:
    dx = point.x - center.x
    dy = point.y - center.y
    if abs(dx) >= abs(dy):
        return "right" if dx >= 0 else "left"
    return "bottom" if dy >= 0 else "top"


def _distance(a: Point, b: Point) -> float:
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5


def _stub_endpoint(start: Point, side: str, length: float = PROBE_STUB_LENGTH) -> Point:
    dx, dy = {
        "left": (-length, 0.0),
        "right": (length, 0.0),
        "top": (0.0, -length),
        "bottom": (0.0, length),
    }[side]
    return Point(round(start.x + dx, 2), round(start.y + dy, 2))


def _probe_ref(shape: str) -> str:
    return {
        "voltage_source": "V1",
        "current_source": "I1",
        "resistor": "R1",
        "capacitor": "C1",
        "inductor": "L1",
        "diode": "D1",
        "ground": "#PWR01",
        "power": "#PWR02",
        "opamp": "U1",
        "npn_bjt": "Q1",
        "pmos": "M1",
        "nmos": "M1",
    }[shape]


def _probe_value(shape: str) -> str:
    return {
        "voltage_source": "V",
        "current_source": "I",
        "resistor": "1k",
        "capacitor": "1u",
        "inductor": "1m",
        "diode": "D",
        "ground": "GND",
        "power": "VCC",
        "opamp": "OPAMP",
        "npn_bjt": "Q",
        "pmos": "PMOS",
        "nmos": "NMOS",
    }[shape]


def _flatten_svg_events(
    element: ET.Element,
    transform: tuple[float, float, float, float, float, float],
    events: list[tuple[str, ET.Element, tuple[float, float, float, float, float, float]]],
) -> None:
    current_transform = _compose_transform(transform, _parse_transform(element.attrib.get("transform", "")))
    tag = element.tag.rsplit("}", 1)[-1]
    if tag == "text":
        events.append(("text", element, current_transform))
    elif tag == "g" and element.attrib.get("class") == "stroked-text":
        events.append(("stroked-text", element, current_transform))
    for child in element:
        _flatten_svg_events(child, current_transform, events)


def _stroked_text_bounds(
    group: ET.Element,
    transform: tuple[float, float, float, float, float, float],
) -> BoundingBox | None:
    current_transform = _compose_transform(transform, _parse_transform(group.attrib.get("transform", "")))
    points: list[Point] = []
    for child in group:
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "path":
            points.extend(_path_points(child.attrib.get("d", ""), current_transform))
        elif tag == "g":
            nested = _stroked_text_bounds(child, current_transform)
            if nested is not None:
                points.extend(
                    [
                        Point(nested.left, nested.top),
                        Point(nested.right, nested.top),
                        Point(nested.left, nested.bottom),
                        Point(nested.right, nested.bottom),
                    ]
                )
    if not points:
        return None
    return BoundingBox(
        left=round(min(point.x for point in points), 4),
        top=round(min(point.y for point in points), 4),
        right=round(max(point.x for point in points), 4),
        bottom=round(max(point.y for point in points), 4),
    )


def _text_anchor(text: ET.Element, transform: tuple[float, float, float, float, float, float]) -> Point:
    x = float(text.attrib.get("x", "0"))
    y = float(text.attrib.get("y", "0"))
    return _apply_transform(Point(x, y), _compose_transform(transform, _parse_transform(text.attrib.get("transform", ""))))


def _path_points(path_data: str, transform: tuple[float, float, float, float, float, float]) -> list[Point]:
    coords = [float(value) for value in re.findall(r"[-0-9.]+", path_data)]
    points: list[Point] = []
    for idx in range(0, len(coords) - 1, 2):
        points.append(_apply_transform(Point(coords[idx], coords[idx + 1]), transform))
    return points


def _parse_transform(value: str) -> tuple[float, float, float, float, float, float]:
    matrix = _identity_matrix()
    for kind, args_text in re.findall(r"([a-zA-Z]+)\(([^)]*)\)", value):
        args = [float(item) for item in re.findall(r"[-0-9.]+", args_text)]
        if kind == "translate":
            tx = args[0]
            ty = args[1] if len(args) > 1 else 0.0
            step = (1.0, 0.0, 0.0, 1.0, tx, ty)
        elif kind == "scale":
            sx = args[0]
            sy = args[1] if len(args) > 1 else sx
            step = (sx, 0.0, 0.0, sy, 0.0, 0.0)
        elif kind == "rotate":
            angle = math.radians(args[0])
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            if len(args) == 3:
                cx, cy = args[1], args[2]
                step = _compose_transform(
                    _compose_transform((1.0, 0.0, 0.0, 1.0, cx, cy), (cos_a, sin_a, -sin_a, cos_a, 0.0, 0.0)),
                    (1.0, 0.0, 0.0, 1.0, -cx, -cy),
                )
            else:
                step = (cos_a, sin_a, -sin_a, cos_a, 0.0, 0.0)
        else:
            continue
        matrix = _compose_transform(matrix, step)
    return matrix


def _identity_matrix() -> tuple[float, float, float, float, float, float]:
    return (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def _compose_transform(
    first: tuple[float, float, float, float, float, float],
    second: tuple[float, float, float, float, float, float],
) -> tuple[float, float, float, float, float, float]:
    a1, b1, c1, d1, e1, f1 = first
    a2, b2, c2, d2, e2, f2 = second
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


def _apply_transform(point: Point, transform: tuple[float, float, float, float, float, float]) -> Point:
    a, b, c, d, e, f = transform
    return Point(round(a * point.x + c * point.y + e, 4), round(b * point.x + d * point.y + f, 4))


def _expand_box(box: BoundingBox, padding: float) -> BoundingBox:
    return BoundingBox(
        left=round(box.left - padding, 4),
        top=round(box.top - padding, 4),
        right=round(box.right + padding, 4),
        bottom=round(box.bottom + padding, 4),
    )


def _boxes_overlap(first: BoundingBox, second: BoundingBox) -> bool:
    return not (
        first.right <= second.left
        or first.left >= second.right
        or first.bottom <= second.top
        or first.top >= second.bottom
    )
