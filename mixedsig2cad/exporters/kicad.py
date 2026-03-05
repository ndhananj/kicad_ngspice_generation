from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date
from typing import DefaultDict, NamedTuple

from mixedsig2cad.spec import CircuitSpec


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


class Placement(NamedTuple):
    x: float
    y: float
    angle: int = 0


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


def _uuid(seed: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))


def _symbol_property(name: str, value: str, x: float, y: float, *, hidden: bool = False) -> list[str]:
    """Emit KiCad symbol property syntax compatible with KiCad 8 parser.

    Hidden properties must express `hide` inside the `effects` stanza, not as a
    standalone property child node.
    """
    effects = "(effects (font (size 1.27 1.27)) hide)" if hidden else "(effects (font (size 1.27 1.27)))"
    return [
        f'    (property "{name}" "{value}" (at {x} {y} 0)',
        f"      {effects}",
        "    )",
    ]


def _symbol_for_component(kind: str, value: str, model: str | None) -> str:
    if kind != "M":
        return SYMBOL_BY_KIND.get(kind, "examples:R")
    hint = f"{value} {model or ''}".lower()
    if "nm" in hint or "nmos" in hint:
        return "examples:MNMOS"
    return "examples:MPMOS"


def _wire(x1: float, y1: float, x2: float, y2: float, seed: str) -> list[str]:
    return [
        f"  (wire (pts (xy {x1:.2f} {y1:.2f}) (xy {x2:.2f} {y2:.2f}))",
        "    (stroke (width 0) (type solid) (color 0 0 0 0))",
        f"    (uuid {_uuid(seed)})",
        "  )",
    ]


def _label(net: str, x: float, y: float, seed: str) -> list[str]:
    return [
        f'  (label "{net}" (at {x:.2f} {y:.2f} 0)',
        "    (effects (font (size 1.27 1.27)) (justify left bottom))",
        f"    (uuid {_uuid(seed)})",
        "  )",
    ]


def _junction(x: float, y: float) -> str:
    return f"  (junction (at {x:.2f} {y:.2f}) (diameter 1.016) (color 0 0 0 0))"


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


def _orthogonal_wire(
    p1: tuple[float, float],
    p2: tuple[float, float],
    seed: str,
) -> list[str]:
    x1, y1 = p1
    x2, y2 = p2
    if y1 == y2 or x1 == x2:
        return _wire(x1, y1, x2, y2, seed)
    mid_x = round((x1 + x2) / 2.0, 2)
    lines: list[str] = []
    lines.extend(_wire(x1, y1, mid_x, y1, f"{seed}:a"))
    lines.extend(_wire(mid_x, y1, mid_x, y2, f"{seed}:b"))
    lines.extend(_wire(mid_x, y2, x2, y2, f"{seed}:c"))
    lines.append(_junction(mid_x, y1))
    lines.append(_junction(mid_x, y2))
    return lines


def _net_map_lines(
    spec: CircuitSpec,
    pin_positions: DefaultDict[str, list[tuple[float, float]]],
    display_names: dict[str, str],
) -> list[str]:
    if not pin_positions:
        return []

    nets = sorted(pin_positions.keys(), key=lambda n: (n != "0", n))
    lines: list[str] = []
    for net_idx, net in enumerate(nets):
        points = pin_positions[net]
        if not points:
            continue

        label_x = min(p[0] for p in points) - 6.0
        label_y = min(p[1] for p in points) - 1.5 - (net_idx % 2) * 1.5
        label_text = display_names.get(net, net)
        lines.extend(_label(label_text, label_x, label_y, f"label:{spec.name}:{net}"))

        if len(points) == 1:
            continue

        if len(points) == 2:
            lines.extend(_orthogonal_wire(points[0], points[1], f"net2:{spec.name}:{net}"))
            continue

        x_span = max(p[0] for p in points) - min(p[0] for p in points)
        y_min = min(p[1] for p in points)
        y_max = max(p[1] for p in points)
        net_lower = net.lower()
        if net_lower in {"0", "gnd", "vss"}:
            y_trunk = round(y_max + 6.0, 2)
        elif net_lower in {"vcc", "vdd", "vee"}:
            y_trunk = round(y_min - 6.0, 2)
        elif x_span >= 30.0:
            y_trunk = round(y_min - 6.0, 2)
        else:
            y_trunk = round(y_max + 6.0, 2)
        x_min = min(p[0] for p in points) - 1.0
        x_max = max(p[0] for p in points) + 1.0
        lines.extend(_wire(x_min, y_trunk, x_max, y_trunk, f"trunk:{spec.name}:{net}"))
        for point_idx, (px, py) in enumerate(points, start=1):
            lines.extend(_wire(px, py, px, y_trunk, f"stub:{spec.name}:{net}:{point_idx}"))
            lines.append(_junction(px, y_trunk))
    return lines


def export_kicad_schematic(spec: CircuitSpec) -> str:
    schematic_uuid = _uuid(f"sch:{spec.name}")
    lines: list[str] = [
        "(kicad_sch",
        "  (version 20231120)",
        '  (generator "mixedsig2cad")',
        f"  (uuid {schematic_uuid})",
        '  (paper "A4")',
        "  (title_block",
        f'    (title "{spec.name}")',
        f'    (date "{date.today().isoformat()}")',
        '    (comment 1 "Generated by mixedsig2cad")',
        "  )",
        "  (lib_symbols)",
    ]

    pin_positions: DefaultDict[str, list[tuple[float, float]]] = defaultdict(list)
    display_names: dict[str, str] = {}
    symbol_instances: list[tuple[str, str, str]] = []
    placements = _component_placements(spec)
    for idx, comp in enumerate(spec.components, start=1):
        symbol_uuid = _uuid(f"sym:{spec.name}:{comp.ref}")
        lib_id = _symbol_for_component(comp.kind, comp.value, comp.model)
        placement = placements[comp.ref]
        for pin_index, net in enumerate(comp.nodes):
            pin_positions[net].append(_pin_anchor(lib_id, placement, pin_index))
        lines.extend(
            [
                f"  (symbol (lib_id \"{lib_id}\") (at {placement.x:.2f} {placement.y:.2f} {placement.angle}) (unit 1)",
                "    (in_bom yes) (on_board yes)",
                f"    (uuid {symbol_uuid})",
                *_symbol_property("Reference", comp.ref, placement.x, placement.y - 3.81),
                *_symbol_property("Value", comp.value, placement.x, placement.y + 3.81),
                *_symbol_property("Footprint", "", 0, 0, hidden=True),
                *_symbol_property("Datasheet", "", 0, 0, hidden=True),
                "  )",
            ]
        )
        symbol_instances.append((symbol_uuid, comp.ref, comp.value))

    power_ref_idx = 1
    power_nets = sorted(net for net in pin_positions.keys() if net.lower() in POWER_SYMBOL_BY_NET)
    for net in power_nets:
        symbol_name = POWER_SYMBOL_BY_NET[net.lower()]
        px = min(p[0] for p in pin_positions[net]) - 12.0
        py = min(p[1] for p in pin_positions[net]) - 6.0
        sym_uuid = _uuid(f"pwr:{spec.name}:{net}:{symbol_name}")
        ref = f"#PWR{power_ref_idx:04d}"
        power_ref_idx += 1
        lines.extend(
            [
                f'  (symbol (lib_id "examples:{symbol_name}") (at {px:.2f} {py:.2f} 0) (unit 1)',
                "    (in_bom yes) (on_board yes)",
                f"    (uuid {sym_uuid})",
                *_symbol_property("Reference", ref, px, py - 3.81, hidden=True),
                *_symbol_property("Value", symbol_name, px, py + 3.81),
                *_symbol_property("Footprint", "", 0, 0, hidden=True),
                *_symbol_property("Datasheet", "", 0, 0, hidden=True),
                "  )",
            ]
        )
        pin_positions[net].append((px, py))
        display_names[net] = symbol_name
        symbol_instances.append((sym_uuid, ref, symbol_name))

    lines.extend(_net_map_lines(spec, pin_positions, display_names))

    lines.extend(
        [
            "  (sheet_instances",
            '    (path "/" (page "1"))',
            "  )",
            "  (symbol_instances",
        ]
    )

    for symbol_uuid, ref, value in symbol_instances:
        lines.append(
            f'    (path "/{symbol_uuid}" (reference "{ref}") (unit 1) (value "{value}") (footprint ""))'
        )

    lines.extend(["  )", ")"])
    return "\n".join(lines) + "\n"
