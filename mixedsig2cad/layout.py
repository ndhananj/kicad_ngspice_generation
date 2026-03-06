from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import DefaultDict

from .spec import CircuitSpec


SYMBOL_BY_KIND = {
    "R": "examples:R",
    "C": "examples:CAP",
    "L": "examples:INDUCTOR",
    "V": "examples:VSOURCE",
    "I": "examples:ISOURCE",
    "D": "examples:DIODE",
    "Q": "examples:QNPN",
    "M": "examples:MPMOS",
    "X": "examples:OPAMP",
}

POWER_SYMBOL_BY_NET = {
    "0": "GND",
    "gnd": "GND",
    "vss": "GND",
    "vdd": "VCC",
    "vcc": "VCC",
}

PIN_OFFSETS = {
    "examples:VSOURCE": ((0.0, 7.62), (0.0, -7.62)),
    "examples:ISOURCE": ((0.0, 10.16), (0.0, -10.16)),
    "examples:R": ((0.0, 6.35), (0.0, -6.35)),
    "examples:CAP": ((0.0, 6.35), (0.0, -6.35)),
    "examples:INDUCTOR": ((-6.35, 0.0), (6.35, 0.0)),
    "examples:DIODE": ((-5.08, 0.0), (5.08, 0.0)),
    "examples:QNPN": ((3.81, 8.89), (-7.62, 0.0), (3.81, -8.89), (-2.54, -8.89)),
    "examples:MNMOS": ((2.54, 5.08), (-5.08, 0.0), (2.54, -5.08), (5.08, -5.08)),
    "examples:MPMOS": ((2.54, -5.08), (-5.08, 0.0), (2.54, 5.08), (5.08, 5.08)),
    "examples:OPAMP": ((-7.62, 2.54), (-7.62, -2.54), (7.62, 0.0), (-2.54, 7.62), (-2.54, -7.62)),
    "examples:GND": ((0.0, 0.0),),
    "examples:VCC": ((0.0, 0.0),),
}

GROUP_X = {
    "source": 50.0,
    "passive": 95.0,
    "active": 150.0,
}

GROUP_Y = {
    "source": 55.0,
    "passive": 55.0,
    "active": 85.0,
}

GROUP_STEP_Y = {
    "source": 35.0,
    "passive": 35.0,
    "active": 45.0,
}


@dataclass(frozen=True, slots=True)
class Placement:
    x: float
    y: float
    angle: int = 0


@dataclass(frozen=True, slots=True)
class PinPlacement:
    owner_ref: str
    net: str
    pin_index: int
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class SymbolPlacement:
    uuid: str
    ref: str
    value: str
    lib_id: str
    placement: Placement
    hidden_reference: bool = False


@dataclass(frozen=True, slots=True)
class LabelPlacement:
    text: str
    x: float
    y: float
    uuid_seed: str


@dataclass(frozen=True, slots=True)
class WireSegment:
    x1: float
    y1: float
    x2: float
    y2: float
    uuid_seed: str


@dataclass(frozen=True, slots=True)
class JunctionPoint:
    x: float
    y: float


@dataclass(slots=True)
class SchematicLayout:
    name: str
    symbols: list[SymbolPlacement] = field(default_factory=list)
    pins_by_net: dict[str, list[PinPlacement]] = field(default_factory=dict)
    labels: list[LabelPlacement] = field(default_factory=list)
    wires: list[WireSegment] = field(default_factory=list)
    junctions: list[JunctionPoint] = field(default_factory=list)


def deterministic_uuid(seed: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))


def symbol_for_component(kind: str, value: str, model: str | None) -> str:
    if kind != "M":
        return SYMBOL_BY_KIND.get(kind, "examples:R")
    hint = f"{value} {model or ''}".lower()
    if "nm" in hint or "nmos" in hint:
        return "examples:MNMOS"
    return "examples:MPMOS"


def build_kicad_layout(spec: CircuitSpec) -> SchematicLayout:
    placements = _component_placements(spec)
    pin_positions: DefaultDict[str, list[PinPlacement]] = defaultdict(list)
    symbols: list[SymbolPlacement] = []

    for comp in spec.components:
        lib_id = symbol_for_component(comp.kind, comp.value, comp.model)
        placement = placements[comp.ref]
        symbol_uuid = deterministic_uuid(f"sym:{spec.name}:{comp.ref}")
        symbols.append(
            SymbolPlacement(
                uuid=symbol_uuid,
                ref=comp.ref,
                value=comp.value,
                lib_id=lib_id,
                placement=placement,
            )
        )
        for pin_index, net in enumerate(comp.nodes):
            x, y = _pin_anchor(lib_id, placement, pin_index)
            pin_positions[net].append(
                PinPlacement(owner_ref=comp.ref, net=net, pin_index=pin_index, x=x, y=y)
            )

    _inject_power_symbols(spec, pin_positions, symbols)
    labels, wires, junctions = _route_nets(spec, pin_positions)
    return SchematicLayout(
        name=spec.name,
        symbols=symbols,
        pins_by_net={net: list(pins) for net, pins in pin_positions.items()},
        labels=labels,
        wires=wires,
        junctions=junctions,
    )


def _rotate_point(x: float, y: float, angle: int) -> tuple[float, float]:
    normalized = angle % 360
    if normalized == 0:
        return (x, y)
    if normalized == 90:
        return (-y, x)
    if normalized == 180:
        return (-x, -y)
    if normalized == 270:
        return (y, -x)
    raise ValueError(f"unsupported angle: {angle}")


def _pin_anchor(lib_id: str, placement: Placement, pin_index: int) -> tuple[float, float]:
    offsets = PIN_OFFSETS.get(lib_id)
    if offsets is None or pin_index >= len(offsets):
        return (placement.x, placement.y)
    local_x, local_y = offsets[pin_index]
    dx, dy = _rotate_point(local_x, local_y, placement.angle)
    return (round(placement.x + dx, 2), round(placement.y + dy, 2))


def _component_group(kind: str) -> str:
    if kind in {"V", "I"}:
        return "source"
    if kind in {"R", "C", "L", "D"}:
        return "passive"
    return "active"


def _component_angle(kind: str, ref: str, nodes: tuple[str, ...]) -> int:
    if kind in {"R", "C"}:
        return 90
    if kind in {"V", "I"}:
        nets = {node.lower() for node in nodes}
        if ref.upper().startswith(("VCC", "VDD", "VEE")) or "0" in nets or "gnd" in nets:
            return 0
        return 90
    return 0


def _placement_overrides(spec: CircuitSpec) -> dict[str, Placement]:
    if spec.name == "opamp_inverting":
        return {
            "VCC": Placement(45.0, 40.0, 0),
            "VEE": Placement(45.0, 120.0, 0),
            "VIN": Placement(45.0, 80.0, 90),
            "RIN": Placement(90.0, 80.0, 90),
            "RF": Placement(135.0, 55.0, 90),
            "XU1": Placement(145.0, 80.0, 0),
        }
    if spec.name == "schmitt_trigger":
        return {
            "VCC": Placement(45.0, 40.0, 0),
            "VIN": Placement(45.0, 105.0, 90),
            "R1": Placement(95.0, 40.0, 90),
            "R2": Placement(140.0, 55.0, 90),
            "R3": Placement(95.0, 105.0, 90),
            "XU1": Placement(145.0, 85.0, 0),
        }
    return {}


def _component_placements(spec: CircuitSpec) -> dict[str, Placement]:
    placements = _placement_overrides(spec)
    counts = {"source": 0, "passive": 0, "active": 0}
    for comp in spec.components:
        if comp.ref in placements:
            continue
        group = _component_group(comp.kind)
        x = GROUP_X[group]
        y = GROUP_Y[group] + counts[group] * GROUP_STEP_Y[group]
        counts[group] += 1
        placements[comp.ref] = Placement(x, y, _component_angle(comp.kind, comp.ref, comp.nodes))
    return placements


def _inject_power_symbols(
    spec: CircuitSpec,
    pin_positions: DefaultDict[str, list[PinPlacement]],
    symbols: list[SymbolPlacement],
) -> None:
    power_ref_idx = 1
    power_nets = sorted(net for net in pin_positions.keys() if net.lower() in POWER_SYMBOL_BY_NET)
    for net in power_nets:
        symbol_name = POWER_SYMBOL_BY_NET[net.lower()]
        px = min(pin.x for pin in pin_positions[net]) - 12.0
        py = min(pin.y for pin in pin_positions[net]) - 6.0
        sym_uuid = deterministic_uuid(f"pwr:{spec.name}:{net}:{symbol_name}")
        ref = f"#PWR{power_ref_idx:04d}"
        power_ref_idx += 1
        symbols.append(
            SymbolPlacement(
                uuid=sym_uuid,
                ref=ref,
                value=symbol_name,
                lib_id=f"examples:{symbol_name}",
                placement=Placement(px, py, 0),
                hidden_reference=True,
            )
        )
        pin_positions[net].append(
            PinPlacement(owner_ref=ref, net=net, pin_index=0, x=px, y=py)
        )


def _route_nets(
    spec: CircuitSpec,
    pin_positions: dict[str, list[PinPlacement]],
) -> tuple[list[LabelPlacement], list[WireSegment], list[JunctionPoint]]:
    labels: list[LabelPlacement] = []
    wires: list[WireSegment] = []
    junctions: list[JunctionPoint] = []
    nets = sorted(pin_positions.keys(), key=lambda n: (n != "0", n))
    for net_idx, net in enumerate(nets):
        pins = pin_positions[net]
        if not pins:
            continue
        label_text = POWER_SYMBOL_BY_NET.get(net.lower(), net)
        label_x = min(pin.x for pin in pins) - 6.0
        label_y = min(pin.y for pin in pins) - 1.5 - (net_idx % 2) * 1.5
        labels.append(LabelPlacement(text=label_text, x=label_x, y=label_y, uuid_seed=f"label:{spec.name}:{net}"))
        if len(pins) == 1:
            continue
        points = [(pin.x, pin.y) for pin in pins]
        if len(points) == 2:
            wires.extend(_orthogonal_segments(points[0], points[1], f"net2:{spec.name}:{net}", junctions))
            continue
        x_span = max(x for x, _ in points) - min(x for x, _ in points)
        y_min = min(y for _, y in points)
        y_max = max(y for _, y in points)
        net_lower = net.lower()
        if net_lower in {"0", "gnd", "vss"}:
            y_trunk = round(y_max + 6.0, 2)
        elif net_lower in {"vcc", "vdd", "vee"}:
            y_trunk = round(y_min - 6.0, 2)
        elif x_span >= 30.0:
            y_trunk = round(y_min - 6.0, 2)
        else:
            y_trunk = round(y_max + 6.0, 2)
        x_min = min(x for x, _ in points) - 1.0
        x_max = max(x for x, _ in points) + 1.0
        wires.append(WireSegment(x1=x_min, y1=y_trunk, x2=x_max, y2=y_trunk, uuid_seed=f"trunk:{spec.name}:{net}"))
        for point_idx, (px, py) in enumerate(points, start=1):
            wires.append(
                WireSegment(x1=px, y1=py, x2=px, y2=y_trunk, uuid_seed=f"stub:{spec.name}:{net}:{point_idx}")
            )
            junctions.append(JunctionPoint(x=px, y=y_trunk))
    return labels, wires, junctions


def _orthogonal_segments(
    p1: tuple[float, float],
    p2: tuple[float, float],
    seed: str,
    junctions: list[JunctionPoint],
) -> list[WireSegment]:
    x1, y1 = p1
    x2, y2 = p2
    if y1 == y2 or x1 == x2:
        return [WireSegment(x1=x1, y1=y1, x2=x2, y2=y2, uuid_seed=seed)]
    mid_x = round((x1 + x2) / 2.0, 2)
    junctions.append(JunctionPoint(x=mid_x, y=y1))
    junctions.append(JunctionPoint(x=mid_x, y=y2))
    return [
        WireSegment(x1=x1, y1=y1, x2=mid_x, y2=y1, uuid_seed=f"{seed}:a"),
        WireSegment(x1=mid_x, y1=y1, x2=mid_x, y2=y2, uuid_seed=f"{seed}:b"),
        WireSegment(x1=mid_x, y1=y2, x2=x2, y2=y2, uuid_seed=f"{seed}:c"),
    ]
