from __future__ import annotations

import math
import re
import uuid
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from mixedsig2cad.geometry import GENERIC_SHAPES, SHAPE_TERMINALS, JunctionPlacement, Point, SchematicGeometry, TextPlacement, WirePath


def deterministic_uuid(seed: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))


@dataclass(frozen=True, slots=True)
class KiCadPlacement:
    x: float
    y: float
    angle: int = 0


@dataclass(frozen=True, slots=True)
class KiCadSymbolPlacement:
    uuid: str
    ref: str
    value: str
    lib_id: str
    placement: KiCadPlacement
    hidden_reference: bool = False


@dataclass(frozen=True, slots=True)
class KiCadTextPlacement:
    text: str
    role: str
    owner_ref: str
    x: float
    y: float
    uuid_seed: str


@dataclass(frozen=True, slots=True)
class KiCadWireSegment:
    x1: float
    y1: float
    x2: float
    y2: float
    uuid_seed: str


@dataclass(frozen=True, slots=True)
class KiCadJunctionPlacement:
    x: float
    y: float


@dataclass(slots=True)
class KiCadProjection:
    name: str
    symbols: list[KiCadSymbolPlacement] = field(default_factory=list)
    texts: list[KiCadTextPlacement] = field(default_factory=list)
    wires: list[KiCadWireSegment] = field(default_factory=list)
    junctions: list[KiCadJunctionPlacement] = field(default_factory=list)


SHAPE_TO_KICAD = {
    ("voltage_source", "vertical_up"): ("VSOURCE", 180),
    ("current_source", "vertical_up"): ("ISOURCE", 180),
    ("resistor", "horizontal"): ("R", 90),
    ("resistor", "vertical"): ("R", 180),
    ("capacitor", "vertical"): ("CAP", 180),
    ("capacitor", "horizontal"): ("CAP", 90),
    ("inductor", "horizontal"): ("INDUCTOR", 0),
    ("diode", "horizontal"): ("DIODE", 0),
    ("diode", "vertical"): ("DIODE", 90),
    ("ground", "down"): ("GND", 0),
    ("power", "up"): ("VCC", 0),
    ("opamp", "right"): ("OPAMP", 0),
    ("npn_bjt", "right"): ("QNPN", 0),
    ("pmos", "right"): ("MPMOS", 0),
    ("nmos", "right"): ("MNMOS", 0),
}

GENERIC_TO_KICAD_PIN = {
    ("voltage_source", "vertical_up"): {"pos": "1", "neg": "2"},
    ("current_source", "vertical_up"): {"pos": "1", "neg": "2"},
    ("resistor", "horizontal"): {"left": "1", "right": "2"},
    ("resistor", "vertical"): {"top": "1", "bottom": "2"},
    ("capacitor", "vertical"): {"top": "1", "bottom": "2"},
    ("capacitor", "horizontal"): {"left": "1", "right": "2"},
    ("inductor", "horizontal"): {"left": "1", "right": "2"},
    ("diode", "horizontal"): {"left": "1", "right": "2"},
    ("diode", "vertical"): {"top": "1", "bottom": "2"},
    ("ground", "down"): {"top": "1"},
    ("power", "up"): {"bottom": "1"},
    ("opamp", "right"): {"plus": "1", "minus": "2", "out": "3", "vplus": "4", "vminus": "5"},
    ("npn_bjt", "right"): {"collector": "1", "base": "2", "emitter": "3"},
    ("pmos", "right"): {"drain": "1", "gate": "2", "source": "3", "body": "4"},
    ("nmos", "right"): {"drain": "1", "gate": "2", "source": "3", "body": "4"},
}


@dataclass(frozen=True, slots=True)
class KiCadLibPin:
    number: str
    name: str
    x: float
    y: float


def project_geometry_to_kicad(geometry: SchematicGeometry) -> KiCadProjection:
    projection = KiCadProjection(name=geometry.name)
    for shape in geometry.shapes:
        lib_id, angle = SHAPE_TO_KICAD[(shape.shape, shape.orientation)]
        if shape.shape == "power" and shape.value.upper() in {"VCC", "VDD"}:
            lib_id = "VCC"
        projection.symbols.append(
            KiCadSymbolPlacement(
                uuid=deterministic_uuid(f"sym:{geometry.name}:{shape.ref}"),
                ref=shape.ref,
                value=shape.value,
                lib_id=lib_id,
                placement=KiCadPlacement(shape.center.x, shape.center.y, angle),
                hidden_reference=shape.hidden_reference,
            )
        )

    for text in geometry.labels:
        if text.role == "reference" and text.text.startswith("#PWR"):
            continue
        projection.texts.append(_project_text(text))

    for wire in geometry.wires:
        projection.wires.extend(_project_wire_path(wire))

    for junction in geometry.junctions:
        projection.junctions.append(KiCadJunctionPlacement(junction.point.x, junction.point.y))
    validate_kicad_projection(projection, geometry)
    return projection


def validate_kicad_projection(projection: KiCadProjection, geometry: SchematicGeometry) -> None:
    symbol_by_ref = {symbol.ref: symbol for symbol in projection.symbols}
    for shape in geometry.shapes:
        symbol = symbol_by_ref.get(shape.ref)
        if symbol is None:
            raise AssertionError(f"missing projected symbol for '{shape.ref}'")
        if symbol.placement.x != shape.center.x or symbol.placement.y != shape.center.y:
            raise AssertionError(f"symbol '{shape.ref}' placement drifted from geometry center")
        expected_offsets = _projected_kicad_offsets(shape.shape, shape.orientation)
        expected_exits = {template.name: template.exit_direction for template in SHAPE_TERMINALS[(shape.shape, shape.orientation)]}
        for terminal in shape.terminals:
            dx = round(terminal.point.x - shape.center.x, 2)
            dy = round(terminal.point.y - shape.center.y, 2)
            expected = expected_offsets[terminal.name]
            if round(expected[0], 2) != dx or round(expected[1], 2) != dy:
                raise AssertionError(
                    f"terminal '{shape.ref}.{terminal.name}' drifted from KiCad symbol mapping: "
                    f"expected {expected}, got {(dx, dy)}"
                )
            if terminal.side != expected_exits[terminal.name]:
                raise AssertionError(f"terminal '{shape.ref}.{terminal.name}' drifted from template exit direction")
    for wire in projection.wires:
        if wire.x1 != wire.x2 and wire.y1 != wire.y2:
            raise AssertionError(f"non-orthogonal KiCad wire segment '{wire.uuid_seed}'")


@lru_cache(maxsize=1)
def _embedded_kicad_symbols() -> dict[str, dict[str, KiCadLibPin]]:
    text = (Path(__file__).resolve().parents[1] / "assets" / "examples.kicad_sym").read_text(encoding="utf-8")
    symbols: dict[str, dict[str, KiCadLibPin]] = {}
    for lib_id in {lib_id for lib_id, _ in SHAPE_TO_KICAD.values()}:
        block = _extract_symbol_block(text, lib_id)
        pins: dict[str, KiCadLibPin] = {}
        for match in re.finditer(
            r'\(pin\s+\w+\s+\w+\s+\(at\s+([-0-9.]+)\s+([-0-9.]+)\s+[-0-9.]+\).*?\n\s*\(name\s+"([^"]+)".*?\n\s*\(number\s+"([^"]+)"',
            block,
            re.S,
        ):
            pin = KiCadLibPin(
                number=match.group(4),
                name=match.group(3),
                x=float(match.group(1)),
                y=float(match.group(2)),
            )
            pins[pin.number] = pin
        symbols[lib_id] = pins
    return symbols


def _extract_symbol_block(text: str, lib_id: str) -> str:
    start = text.find(f'(symbol "{lib_id}"')
    if start < 0:
        raise AssertionError(f"embedded KiCad symbol '{lib_id}' not found")
    depth = 0
    for idx in range(start, len(text)):
        ch = text[idx]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]
    raise AssertionError(f"unterminated symbol block for '{lib_id}'")


def _projected_kicad_offsets(shape_name: str, orientation: str) -> dict[str, tuple[float, float]]:
    lib_id, angle = SHAPE_TO_KICAD[(shape_name, orientation)]
    pin_map = GENERIC_TO_KICAD_PIN[(shape_name, orientation)]
    lib_pins = _embedded_kicad_symbols()[lib_id]
    offsets: dict[str, tuple[float, float]] = {}
    for terminal_name, pin_number in pin_map.items():
        pin = lib_pins.get(pin_number)
        if pin is None:
            raise AssertionError(f"KiCad pin '{pin_number}' missing from symbol '{lib_id}'")
        offsets[terminal_name] = _rotate_offset(pin.x, pin.y, angle)
    return offsets


def _rotate_offset(x: float, y: float, angle: int) -> tuple[float, float]:
    radians = math.radians(angle)
    rx = round(x * math.cos(radians) - y * math.sin(radians), 2)
    ry = round(x * math.sin(radians) + y * math.cos(radians), 2)
    return rx, ry


def _project_text(text: TextPlacement) -> KiCadTextPlacement:
    return KiCadTextPlacement(
        text=text.text,
        role=text.role,
        owner_ref=text.owner_ref,
        x=text.position.x,
        y=text.position.y,
        uuid_seed=text.uuid_seed,
    )


def _project_wire_path(wire: WirePath) -> list[KiCadWireSegment]:
    if len(wire.points) < 2:
        return []
    segments: list[KiCadWireSegment] = []
    for idx in range(len(wire.points) - 1):
        start = wire.points[idx]
        end = wire.points[idx + 1]
        segments.append(
            KiCadWireSegment(
                x1=start.x,
                y1=start.y,
                x2=end.x,
                y2=end.y,
                uuid_seed=f"{wire.uuid_seed}:{idx + 1}",
            )
        )
    return segments
