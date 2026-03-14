from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from mixedsig2cad.kicad_symbols import KiCadLibPin, project_symbol_body_bounds, project_symbol_pins
from mixedsig2cad.models import CompiledSchematic, Point, TextPlacement, WirePath
from mixedsig2cad.symbols import kicad_pin_map, kicad_symbol, symbol_geometry, terminal_defs


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
    font_size: float


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

def project_geometry_to_kicad(geometry: CompiledSchematic) -> KiCadProjection:
    projection = KiCadProjection(name=geometry.name)
    for shape in geometry.shapes:
        lib_id, angle = kicad_symbol(shape.shape, shape.orientation)
        if shape.shape == "power":
            if shape.value.upper() in {"VCC", "VDD"}:
                lib_id = "VCC"
            elif shape.value.upper() == "VEE":
                lib_id = "VEE"
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


def validate_kicad_projection(projection: KiCadProjection, geometry: CompiledSchematic) -> None:
    symbol_by_ref = {symbol.ref: symbol for symbol in projection.symbols}
    for shape in geometry.shapes:
        symbol = symbol_by_ref.get(shape.ref)
        if symbol is None:
            raise AssertionError(f"missing projected symbol for '{shape.ref}'")
        if symbol.placement.x != shape.center.x or symbol.placement.y != shape.center.y:
            raise AssertionError(f"symbol '{shape.ref}' placement drifted from geometry center")
        geometry_def = symbol_geometry(shape.shape, shape.orientation)
        expected_exits = {template.name: template.exit_direction for template in geometry_def.terminals}
        expected_offsets = {template.name: template.offset for template in geometry_def.terminals}
        pin_map = kicad_pin_map(shape.shape, shape.orientation)
        lib_id, angle = kicad_symbol(shape.shape, shape.orientation)
        lib_pins = _embedded_kicad_symbols()[lib_id]
        for terminal in shape.terminals:
            pin_number = pin_map.get(terminal.name)
            if pin_number is None:
                raise AssertionError(f"missing KiCad pin mapping for '{shape.shape}/{shape.orientation}:{terminal.name}'")
            if pin_number not in lib_pins:
                raise AssertionError(f"KiCad pin '{pin_number}' missing from symbol '{lib_id}'")
            if terminal.side != expected_exits[terminal.name]:
                raise AssertionError(f"terminal '{shape.ref}.{terminal.name}' drifted from template exit direction")
            expected_point = Point(
                round(shape.center.x + expected_offsets[terminal.name][0], 2),
                round(shape.center.y + expected_offsets[terminal.name][1], 2),
            )
            if terminal.point != expected_point:
                raise AssertionError(
                    f"terminal '{shape.ref}.{terminal.name}' drifted from canonical KiCad pin position: "
                    f"{terminal.point} != {expected_point}"
                )
        projected_body = project_symbol_body_bounds(lib_id, angle)
        expected_body = (
            round(shape.center.x + projected_body.left, 2),
            round(shape.center.y + projected_body.top, 2),
            round(shape.center.x + projected_body.right, 2),
            round(shape.center.y + projected_body.bottom, 2),
        )
        actual_body = (shape.body_box.left, shape.body_box.top, shape.body_box.right, shape.body_box.bottom)
        if actual_body != expected_body:
            raise AssertionError(f"symbol '{shape.ref}' body box drifted from canonical KiCad geometry")
    for wire in projection.wires:
        if wire.x1 != wire.x2 and wire.y1 != wire.y2:
            raise AssertionError(f"non-orthogonal KiCad wire segment '{wire.uuid_seed}'")


def _embedded_kicad_symbols() -> dict[str, dict[str, KiCadLibPin]]:
    return project_symbol_pins()


def _projected_kicad_offsets(shape_name: str, orientation: str) -> dict[str, tuple[float, float]]:
    return {terminal.name: terminal.offset for terminal in terminal_defs(shape_name, orientation)}


def _validate_npn_orientation(offsets: dict[str, tuple[float, float]]) -> None:
    collector = offsets["collector"]
    base = offsets["base"]
    emitter = offsets["emitter"]
    if base[0] >= collector[0] or base[0] >= emitter[0]:
        raise AssertionError("npn_bjt/right no longer has base on the left")
    if collector[1] >= emitter[1]:
        raise AssertionError("npn_bjt/right no longer has collector above emitter")


def _project_text(text: TextPlacement) -> KiCadTextPlacement:
    return KiCadTextPlacement(
        text=text.text,
        role=text.role,
        owner_ref=text.owner_ref,
        x=text.position.x,
        y=text.position.y,
        uuid_seed=text.uuid_seed,
        font_size=text.font_size,
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
