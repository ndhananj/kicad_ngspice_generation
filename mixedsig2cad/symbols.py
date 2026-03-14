from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from .kicad_symbols import project_symbol_body_bounds, project_symbol_pins
from .models import SymbolGeometry, TerminalTemplate


@dataclass(frozen=True, slots=True)
class SymbolTerminalDef:
    name: str
    exit_direction: str
    preferred_connection_class: str | None = None
    preferred_branch_offset: tuple[float, float] | None = None


SYMBOL_TERMINAL_METADATA: dict[tuple[str, str], tuple[SymbolTerminalDef, ...]] = {
    ("voltage_source", "vertical_up"): (
        SymbolTerminalDef("pos", "top"),
        SymbolTerminalDef("neg", "bottom", "local_ground_drop"),
    ),
    ("current_source", "vertical_up"): (
        SymbolTerminalDef("pos", "top"),
        SymbolTerminalDef("neg", "bottom", "local_ground_drop"),
    ),
    ("resistor", "horizontal"): (
        SymbolTerminalDef("left", "left", "series_inline"),
        SymbolTerminalDef("right", "right", "series_inline"),
    ),
    ("resistor", "vertical"): (
        SymbolTerminalDef("top", "top", "branch_to_junction"),
        SymbolTerminalDef("bottom", "bottom", "local_ground_drop"),
    ),
    ("capacitor", "vertical"): (
        SymbolTerminalDef("top", "top", "branch_to_junction"),
        SymbolTerminalDef("bottom", "bottom", "local_ground_drop"),
    ),
    ("capacitor", "horizontal"): (
        SymbolTerminalDef("left", "left", "series_inline"),
        SymbolTerminalDef("right", "right", "series_inline"),
    ),
    ("inductor", "horizontal"): (
        SymbolTerminalDef("left", "left", "series_inline"),
        SymbolTerminalDef("right", "right", "series_inline"),
    ),
    ("diode", "horizontal"): (
        SymbolTerminalDef("left", "left", "series_inline"),
        SymbolTerminalDef("right", "right", "branch_to_junction"),
    ),
    ("diode", "vertical"): (
        SymbolTerminalDef("top", "top", "branch_to_junction"),
        SymbolTerminalDef("bottom", "bottom", "local_ground_drop"),
    ),
    ("ground", "down"): (
        SymbolTerminalDef("top", "top", "local_ground_drop"),
    ),
    ("power", "up"): (
        SymbolTerminalDef("bottom", "bottom", "local_supply_rise"),
    ),
    ("opamp", "right"): (
        SymbolTerminalDef("plus", "left", "branch_to_junction", (-6.0, 0.0)),
        SymbolTerminalDef("minus", "left", "feedback_loop", (-6.0, 0.0)),
        SymbolTerminalDef("out", "right", "series_inline", (6.0, 0.0)),
        SymbolTerminalDef("vplus", "top", "local_supply_rise"),
        SymbolTerminalDef("vminus", "bottom", "local_supply_rise"),
    ),
    ("npn_bjt", "right"): (
        SymbolTerminalDef("collector", "top", "branch_to_junction", (0.0, -6.0)),
        SymbolTerminalDef("base", "left", "branch_to_junction", (-6.0, 0.0)),
        SymbolTerminalDef("emitter", "bottom", "local_ground_drop", (0.0, 6.0)),
        SymbolTerminalDef("substrate", "bottom", "local_ground_drop", (0.0, 6.0)),
    ),
    ("pmos", "right"): (
        SymbolTerminalDef("drain", "bottom", "branch_to_junction", (0.0, 6.0)),
        SymbolTerminalDef("gate", "left", "branch_to_junction", (-10.16, 0.0)),
        SymbolTerminalDef("source", "top", "local_supply_rise"),
        SymbolTerminalDef("body", "right", "local_supply_rise"),
    ),
    ("nmos", "right"): (
        SymbolTerminalDef("drain", "top", "branch_to_junction", (0.0, -6.0)),
        SymbolTerminalDef("gate", "left", "branch_to_junction", (-10.16, 0.0)),
        SymbolTerminalDef("source", "bottom", "local_ground_drop"),
        SymbolTerminalDef("body", "right", "local_ground_drop"),
    ),
}

COMPONENT_SYMBOL_KINDS: dict[str, tuple[str, str]] = {
    "V": ("voltage_source", "vertical_up"),
    "I": ("current_source", "vertical_up"),
    "R": ("resistor", "horizontal"),
    "C": ("capacitor", "vertical"),
    "L": ("inductor", "horizontal"),
    "D": ("diode", "horizontal"),
    "Q": ("npn_bjt", "right"),
    "X": ("opamp", "right"),
}

COMPONENT_TERMINAL_ORDERS: dict[tuple[str, str], tuple[str, ...]] = {
    ("V", "vertical_up"): ("pos", "neg"),
    ("I", "vertical_up"): ("pos", "neg"),
    ("R", "horizontal"): ("left", "right"),
    ("R", "vertical"): ("top", "bottom"),
    ("C", "horizontal"): ("left", "right"),
    ("C", "vertical"): ("top", "bottom"),
    ("L", "horizontal"): ("left", "right"),
    ("D", "horizontal"): ("left", "right"),
    ("D", "vertical"): ("top", "bottom"),
    ("Q", "right"): ("collector", "base", "emitter", "substrate"),
    ("X", "right"): ("plus", "minus", "out", "vplus", "vminus"),
    ("M", "right"): ("drain", "gate", "source", "body"),
}

KICAD_SYMBOLS: dict[tuple[str, str], tuple[str, int]] = {
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

KICAD_PIN_MAPS: dict[tuple[str, str], dict[str, str]] = {
    ("voltage_source", "vertical_up"): {"pos": "2", "neg": "1"},
    ("current_source", "vertical_up"): {"pos": "2", "neg": "1"},
    ("resistor", "horizontal"): {"left": "1", "right": "2"},
    ("resistor", "vertical"): {"top": "2", "bottom": "1"},
    ("capacitor", "vertical"): {"top": "2", "bottom": "1"},
    ("capacitor", "horizontal"): {"left": "1", "right": "2"},
    ("inductor", "horizontal"): {"left": "1", "right": "2"},
    ("diode", "horizontal"): {"left": "1", "right": "2"},
    ("diode", "vertical"): {"top": "2", "bottom": "1"},
    ("ground", "down"): {"top": "1"},
    ("power", "up"): {"bottom": "1"},
    ("opamp", "right"): {"plus": "1", "minus": "2", "out": "3", "vplus": "4", "vminus": "5"},
    ("npn_bjt", "right"): {"collector": "1", "base": "2", "emitter": "3", "substrate": "4"},
    ("pmos", "right"): {"drain": "1", "gate": "2", "source": "3", "body": "4"},
    ("nmos", "right"): {"drain": "1", "gate": "2", "source": "3", "body": "4"},
}


def component_symbol(kind: str, value: str = "", model: str | None = None) -> tuple[str, str]:
    if kind == "M":
        hint = f"{value} {model or ''}".lower()
        return ("nmos", "right") if "nm" in hint or "nmos" in hint else ("pmos", "right")
    return COMPONENT_SYMBOL_KINDS.get(kind, ("resistor", "horizontal"))


def default_orientation_for_component(kind: str, value: str = "", model: str | None = None) -> str:
    return component_symbol(kind, value, model)[1]


def default_orientation_for_shape(shape: str) -> str:
    for symbol_shape, orientation in SYMBOL_TERMINAL_METADATA:
        if symbol_shape == shape:
            return orientation
    raise KeyError(shape)


@lru_cache(maxsize=64)
def symbol_geometry(shape: str, orientation: str) -> SymbolGeometry:
    metadata = SYMBOL_TERMINAL_METADATA[(shape, orientation)]
    lib_id, angle = kicad_symbol(shape, orientation)
    pin_map = kicad_pin_map(shape, orientation)
    lib_pins = project_symbol_pins()[lib_id]
    body = project_symbol_body_bounds(lib_id, angle)
    terminals = tuple(
        TerminalTemplate(
            name=terminal.name,
            offset=_rotate_offset(lib_pins[pin_map[terminal.name]].x, lib_pins[pin_map[terminal.name]].y, angle),
            exit_direction=terminal.exit_direction,
            preferred_connection_class=terminal.preferred_connection_class,
            preferred_branch_offset=terminal.preferred_branch_offset,
        )
        for terminal in metadata
    )
    return SymbolGeometry(
        shape=shape,
        orientation=orientation,
        lib_id=lib_id,
        angle=angle,
        terminals=terminals,
        body_box=(body.left, body.top, body.right, body.bottom),
    )


def terminal_defs(shape: str, orientation: str) -> tuple[TerminalTemplate, ...]:
    return symbol_geometry(shape, orientation).terminals


def body_box(shape: str, orientation: str) -> tuple[float, float, float, float]:
    return symbol_geometry(shape, orientation).body_box


def terminal_offset_for_component(
    kind: str,
    orientation: str,
    terminal_name: str,
    *,
    value: str = "",
    model: str | None = None,
) -> tuple[float, float]:
    shape, _ = component_symbol(kind, value, model)
    for terminal in terminal_defs(shape, orientation):
        if terminal.name == terminal_name:
            return terminal.offset
    raise KeyError((kind, orientation, terminal_name))


def terminal_name_for_component(
    kind: str,
    orientation: str,
    pin_index: int,
) -> str:
    terminal_order = COMPONENT_TERMINAL_ORDERS.get((kind, orientation))
    if terminal_order is None:
        terminal_order = tuple(terminal.name for terminal in terminal_defs(*component_symbol(kind)))
    return terminal_order[min(pin_index, len(terminal_order) - 1)]


def kicad_symbol(shape: str, orientation: str) -> tuple[str, int]:
    return KICAD_SYMBOLS[(shape, orientation)]


def kicad_pin_map(shape: str, orientation: str) -> dict[str, str]:
    return KICAD_PIN_MAPS[(shape, orientation)]


def inverse_kicad_symbol_map() -> dict[tuple[str, int], tuple[str, str]]:
    inverse = {value: key for key, value in KICAD_SYMBOLS.items()}
    inverse[("VEE", 0)] = ("power", "up")
    return inverse


def _rotate_offset(x: float, y: float, angle: int) -> tuple[float, float]:
    normalized = angle % 360
    if normalized == 0:
        return round(x, 2), round(-y, 2)
    if normalized == 90:
        return round(-y, 2), round(-x, 2)
    if normalized == 180:
        return round(-x, 2), round(y, 2)
    if normalized == 270:
        return round(y, 2), round(x, 2)
    raise ValueError(f"unsupported KiCad symbol rotation angle: {angle}")
