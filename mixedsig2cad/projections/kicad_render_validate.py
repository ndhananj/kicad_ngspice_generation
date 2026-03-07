from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from mixedsig2cad.compiled import make_body_box, make_terminals
from mixedsig2cad.exporters.kicad import render_kicad_schematic
from mixedsig2cad.models import (
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


def validate_rendered_kicad_symbols(*, strict_pin_labels: bool = False) -> list[RenderedSymbolComparison]:
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
    diagnostics: list[str] = []
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
            target = hard_failures if strict_pin_labels else diagnostics
            target.append(
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
        notes=tuple(hard_failures + [f"diagnostic: {note}" for note in diagnostics]),
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
