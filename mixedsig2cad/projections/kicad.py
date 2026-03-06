from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from mixedsig2cad.geometry import JunctionPlacement, Point, SchematicGeometry, TextPlacement, WirePath


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
    ("ground", "down"): ("GND", 0),
    ("power", "up"): ("VCC", 0),
    ("opamp", "right"): ("OPAMP", 0),
    ("npn_bjt", "right"): ("QNPN", 180),
    ("pmos", "right"): ("MPMOS", 0),
    ("nmos", "right"): ("MNMOS", 0),
}


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
    return projection


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
