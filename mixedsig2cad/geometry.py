from __future__ import annotations

from dataclasses import dataclass, field

from .intent import GROUND_NETS, SUPPLY_NETS, IntentComponent, IntentPattern, SchematicIntent


@dataclass(frozen=True, slots=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class PlacedTerminal:
    name: str
    point: Point


@dataclass(frozen=True, slots=True)
class PlacedShape:
    ref: str
    value: str
    shape: str
    orientation: str
    center: Point
    terminals: tuple[PlacedTerminal, ...]
    hidden_reference: bool = False


@dataclass(frozen=True, slots=True)
class WirePath:
    points: tuple[Point, ...]
    uuid_seed: str


@dataclass(frozen=True, slots=True)
class TextPlacement:
    text: str
    role: str
    position: Point
    owner_ref: str
    uuid_seed: str


@dataclass(frozen=True, slots=True)
class JunctionPlacement:
    point: Point


@dataclass(slots=True)
class SchematicGeometry:
    name: str
    shapes: list[PlacedShape] = field(default_factory=list)
    wires: list[WirePath] = field(default_factory=list)
    labels: list[TextPlacement] = field(default_factory=list)
    junctions: list[JunctionPlacement] = field(default_factory=list)


SHAPE_GROUP_X = {
    "source": 50.0,
    "passive": 100.0,
    "active": 150.0,
}

SHAPE_GROUP_Y = {
    "source": 70.0,
    "passive": 70.0,
    "active": 90.0,
}

SHAPE_GROUP_STEP_Y = {
    "source": 40.0,
    "passive": 38.0,
    "active": 48.0,
}


GENERIC_SHAPES: dict[tuple[str, str], dict[str, tuple[float, float]]] = {
    ("voltage_source", "vertical_up"): {"pos": (0.0, -7.62), "neg": (0.0, 7.62)},
    ("current_source", "vertical_up"): {"pos": (0.0, -10.16), "neg": (0.0, 10.16)},
    ("resistor", "horizontal"): {"left": (-6.35, 0.0), "right": (6.35, 0.0)},
    ("resistor", "vertical"): {"top": (0.0, -6.35), "bottom": (0.0, 6.35)},
    ("capacitor", "vertical"): {"top": (0.0, -6.35), "bottom": (0.0, 6.35)},
    ("capacitor", "horizontal"): {"left": (-6.35, 0.0), "right": (6.35, 0.0)},
    ("inductor", "horizontal"): {"left": (-6.35, 0.0), "right": (6.35, 0.0)},
    ("diode", "horizontal"): {"left": (-5.08, 0.0), "right": (5.08, 0.0)},
    ("ground", "down"): {"top": (0.0, 0.0)},
    ("power", "up"): {"bottom": (0.0, 0.0)},
    ("opamp", "right"): {
        "plus": (-7.62, 2.54),
        "minus": (-7.62, -2.54),
        "out": (7.62, 0.0),
        "vplus": (-2.54, 7.62),
        "vminus": (-2.54, -7.62),
    },
    ("npn_bjt", "right"): {"collector": (3.81, -8.89), "base": (-7.62, 0.0), "emitter": (3.81, 8.89)},
    ("pmos", "right"): {"drain": (2.54, -5.08), "gate": (-5.08, 0.0), "source": (2.54, 5.08), "body": (5.08, 5.08)},
    ("nmos", "right"): {"drain": (2.54, 5.08), "gate": (-5.08, 0.0), "source": (2.54, -5.08), "body": (5.08, -5.08)},
}


def build_schematic_geometry(intent: SchematicIntent) -> SchematicGeometry:
    for pattern in intent.patterns:
        if pattern.kind == "rc_lowpass":
            return _build_rc_lowpass_geometry(intent, pattern)
        if pattern.kind == "rc_highpass":
            return _build_rc_highpass_geometry(intent, pattern)
    return _build_fallback_geometry(intent)


def _build_rc_lowpass_geometry(intent: SchematicIntent, pattern: IntentPattern) -> SchematicGeometry:
    by_ref = {comp.ref: comp for comp in intent.components}
    source = by_ref[pattern.components["source"]]
    series = by_ref[pattern.components["series"]]
    shunt = by_ref[pattern.components["shunt"]]

    geometry = SchematicGeometry(name=intent.name)
    source_shape = _place_shape_from_component(source, Point(50.0, 78.0), orientation="vertical_up")
    resistor_shape = _place_shape_from_component(series, Point(90.0, 70.38), orientation="horizontal")
    capacitor_shape = _place_shape_from_component(shunt, Point(96.35, 76.73), orientation="vertical")
    source_gnd = _place_ground("#PWR0001", Point(50.0, 95.62))
    cap_gnd = _place_ground("#PWR0002", Point(96.35, 93.08))

    geometry.shapes.extend([source_shape, resistor_shape, capacitor_shape, source_gnd, cap_gnd])

    src_pos = _terminal_point(source_shape, "pos")
    src_neg = _terminal_point(source_shape, "neg")
    r_left = _terminal_point(resistor_shape, "left")
    r_right = _terminal_point(resistor_shape, "right")
    c_top = _terminal_point(capacitor_shape, "top")
    c_bottom = _terminal_point(capacitor_shape, "bottom")
    gnd1 = _terminal_point(source_gnd, "top")
    gnd2 = _terminal_point(cap_gnd, "top")

    geometry.wires.extend(
        [
            WirePath(points=(src_pos, r_left), uuid_seed=f"{intent.name}:vin"),
            WirePath(points=(src_neg, gnd1), uuid_seed=f"{intent.name}:source_gnd"),
            WirePath(points=(c_bottom, gnd2), uuid_seed=f"{intent.name}:cap_gnd"),
        ]
    )
    geometry.junctions.append(JunctionPlacement(point=r_right))
    geometry.labels.extend(_standard_texts(source_shape))
    geometry.labels.extend(_standard_texts(resistor_shape))
    geometry.labels.extend(_standard_texts(capacitor_shape))
    return geometry


def _build_rc_highpass_geometry(intent: SchematicIntent, pattern: IntentPattern) -> SchematicGeometry:
    by_ref = {comp.ref: comp for comp in intent.components}
    source = by_ref[pattern.components["source"]]
    series = by_ref[pattern.components["series"]]
    shunt = by_ref[pattern.components["shunt"]]

    geometry = SchematicGeometry(name=intent.name)
    source_shape = _place_shape_from_component(source, Point(50.0, 78.0), orientation="vertical_up")
    capacitor_shape = _place_shape_from_component(series, Point(90.0, 70.38), orientation="horizontal")
    resistor_shape = _place_shape_from_component(shunt, Point(96.35, 98.73), orientation="vertical")
    source_gnd = _place_ground("#PWR0001", Point(50.0, 95.62))
    resistor_gnd = _place_ground("#PWR0002", Point(96.35, 115.08))

    geometry.shapes.extend([source_shape, capacitor_shape, resistor_shape, source_gnd, resistor_gnd])

    src_pos = _terminal_point(source_shape, "pos")
    src_neg = _terminal_point(source_shape, "neg")
    c_left = _terminal_point(capacitor_shape, "left")
    c_right = _terminal_point(capacitor_shape, "right")
    r_top = _terminal_point(resistor_shape, "top")
    r_bottom = _terminal_point(resistor_shape, "bottom")
    gnd1 = _terminal_point(source_gnd, "top")
    gnd2 = _terminal_point(resistor_gnd, "top")

    geometry.wires.extend(
        [
            WirePath(points=(src_pos, c_left), uuid_seed=f"{intent.name}:vin"),
            WirePath(points=(src_neg, gnd1), uuid_seed=f"{intent.name}:source_gnd"),
            WirePath(points=(r_bottom, gnd2), uuid_seed=f"{intent.name}:res_gnd"),
        ]
    )
    geometry.junctions.append(JunctionPlacement(point=c_right))
    geometry.labels.extend(_standard_texts(source_shape))
    geometry.labels.extend(_standard_texts(capacitor_shape))
    geometry.labels.extend(_standard_texts(resistor_shape))
    return geometry


def _build_fallback_geometry(intent: SchematicIntent) -> SchematicGeometry:
    geometry = SchematicGeometry(name=intent.name)
    shapes_by_ref: dict[str, PlacedShape] = {}
    counts = {"source": 0, "passive": 0, "active": 0}
    net_points: dict[str, list[Point]] = {}

    power_ref_idx = 1
    for comp in intent.components:
        group = _component_group(comp.kind)
        x = SHAPE_GROUP_X[group]
        y = SHAPE_GROUP_Y[group] + counts[group] * SHAPE_GROUP_STEP_Y[group]
        counts[group] += 1
        shape = _place_shape_from_component(comp, Point(x, y))
        shapes_by_ref[comp.ref] = shape
        geometry.shapes.append(shape)
        geometry.labels.extend(_standard_texts(shape))

    for comp in intent.components:
        shape = shapes_by_ref[comp.ref]
        for pin_index, net_name in enumerate(comp.nodes):
            point = _component_terminal(shape, comp.kind, pin_index)
            role = intent.nets[net_name].role
            lowered = net_name.lower()
            if role == "ground":
                ref = f"#PWR{power_ref_idx:04d}"
                power_ref_idx += 1
                gnd_center = Point(point.x, point.y + 12.0)
                gnd_shape = _place_ground(ref, gnd_center)
                geometry.shapes.append(gnd_shape)
                geometry.wires.append(WirePath(points=(point, _terminal_point(gnd_shape, "top")), uuid_seed=f"{intent.name}:{ref}"))
                continue
            if role == "supply":
                ref = f"#PWR{power_ref_idx:04d}"
                power_ref_idx += 1
                power_shape = _place_power(ref, lowered.upper(), Point(point.x, point.y - 12.0))
                geometry.shapes.append(power_shape)
                geometry.wires.append(WirePath(points=(point, _terminal_point(power_shape, "bottom")), uuid_seed=f"{intent.name}:{ref}"))
                continue
            net_points.setdefault(net_name, []).append(point)

    for net_name, points in sorted(net_points.items()):
        if len(points) == 2:
            geometry.wires.extend(_orthogonal_path(points[0], points[1], f"net2:{intent.name}:{net_name}", geometry.junctions))
        elif len(points) > 2:
            x_min = min(point.x for point in points)
            x_max = max(point.x for point in points)
            y_trunk = min(point.y for point in points) - 10.0
            geometry.wires.append(
                WirePath(points=(Point(x_min, y_trunk), Point(x_max, y_trunk)), uuid_seed=f"trunk:{intent.name}:{net_name}")
            )
            for idx, point in enumerate(points, start=1):
                geometry.wires.append(
                    WirePath(points=(point, Point(point.x, y_trunk)), uuid_seed=f"stub:{intent.name}:{net_name}:{idx}")
                )
                geometry.junctions.append(JunctionPlacement(point=Point(point.x, y_trunk)))
    return geometry


def _place_shape_from_component(comp: IntentComponent, center: Point, orientation: str | None = None) -> PlacedShape:
    shape_name, default_orientation = _shape_for_component(comp)
    actual_orientation = orientation or default_orientation
    terminals = _make_terminals(shape_name, actual_orientation, center)
    return PlacedShape(ref=comp.ref, value=comp.value, shape=shape_name, orientation=actual_orientation, center=center, terminals=terminals)


def _shape_for_component(comp: IntentComponent) -> tuple[str, str]:
    if comp.kind == "V":
        return ("voltage_source", "vertical_up")
    if comp.kind == "I":
        return ("current_source", "vertical_up")
    if comp.kind == "R":
        return ("resistor", "horizontal")
    if comp.kind == "C":
        return ("capacitor", "vertical")
    if comp.kind == "L":
        return ("inductor", "horizontal")
    if comp.kind == "D":
        return ("diode", "horizontal")
    if comp.kind == "Q":
        return ("npn_bjt", "right")
    if comp.kind == "X":
        return ("opamp", "right")
    if comp.kind == "M":
        hint = f"{comp.value} {comp.model or ''}".lower()
        return ("nmos", "right") if "nm" in hint or "nmos" in hint else ("pmos", "right")
    return ("resistor", "horizontal")


def _place_ground(ref: str, center: Point) -> PlacedShape:
    return PlacedShape(ref=ref, value="GND", shape="ground", orientation="down", center=center, terminals=_make_terminals("ground", "down", center), hidden_reference=True)


def _place_power(ref: str, value: str, center: Point) -> PlacedShape:
    return PlacedShape(ref=ref, value=value, shape="power", orientation="up", center=center, terminals=_make_terminals("power", "up", center), hidden_reference=True)


def _make_terminals(shape: str, orientation: str, center: Point) -> tuple[PlacedTerminal, ...]:
    offsets = GENERIC_SHAPES[(shape, orientation)]
    return tuple(
        PlacedTerminal(name=name, point=Point(round(center.x + dx, 2), round(center.y + dy, 2)))
        for name, (dx, dy) in offsets.items()
    )


def _terminal_point(shape: PlacedShape, terminal_name: str) -> Point:
    for terminal in shape.terminals:
        if terminal.name == terminal_name:
            return terminal.point
    raise KeyError(f"terminal {terminal_name} not found for {shape.ref}")


def _component_terminal(shape: PlacedShape, kind: str, pin_index: int) -> Point:
    terminal_order = {
        "V": ("pos", "neg"),
        "I": ("pos", "neg"),
        "R": ("left", "right"),
        "C": ("top", "bottom"),
        "L": ("left", "right"),
        "D": ("left", "right"),
        "Q": ("collector", "base", "emitter"),
        "X": ("plus", "minus", "out", "vplus", "vminus"),
        "M": ("drain", "gate", "source", "body"),
    }.get(kind, ("left", "right"))
    terminal_name = terminal_order[min(pin_index, len(terminal_order) - 1)]
    return _terminal_point(shape, terminal_name)


def _component_group(kind: str) -> str:
    if kind in {"V", "I"}:
        return "source"
    if kind in {"R", "C", "L", "D"}:
        return "passive"
    return "active"


def _standard_texts(shape: PlacedShape) -> list[TextPlacement]:
    dx = 0.0
    if shape.shape in {"resistor", "capacitor", "inductor", "diode"}:
        ref_pos = Point(shape.center.x, shape.center.y - 8.0)
        value_pos = Point(shape.center.x, shape.center.y + 8.0)
    elif shape.shape in {"ground", "power"}:
        ref_pos = Point(shape.center.x, shape.center.y - 4.0)
        value_pos = Point(shape.center.x, shape.center.y + 4.0)
    else:
        ref_pos = Point(shape.center.x + dx, shape.center.y - 10.0)
        value_pos = Point(shape.center.x + dx, shape.center.y + 10.0)
    return [
        TextPlacement(text=shape.ref, role="reference", position=ref_pos, owner_ref=shape.ref, uuid_seed=f"text:{shape.ref}:ref"),
        TextPlacement(text=shape.value, role="value", position=value_pos, owner_ref=shape.ref, uuid_seed=f"text:{shape.ref}:value"),
    ]


def _orthogonal_path(
    p1: Point,
    p2: Point,
    seed: str,
    junctions: list[JunctionPlacement],
) -> list[WirePath]:
    if p1.x == p2.x or p1.y == p2.y:
        return [WirePath(points=(p1, p2), uuid_seed=seed)]
    mid_x = round((p1.x + p2.x) / 2.0, 2)
    mid1 = Point(mid_x, p1.y)
    mid2 = Point(mid_x, p2.y)
    junctions.append(JunctionPlacement(point=mid1))
    junctions.append(JunctionPlacement(point=mid2))
    return [
        WirePath(points=(p1, mid1), uuid_seed=f"{seed}:a"),
        WirePath(points=(mid1, mid2), uuid_seed=f"{seed}:b"),
        WirePath(points=(mid2, p2), uuid_seed=f"{seed}:c"),
    ]
