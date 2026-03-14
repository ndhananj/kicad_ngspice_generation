from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SymbolTerminalDef:
    name: str
    offset: tuple[float, float]
    exit_direction: str
    preferred_connection_class: str | None = None
    preferred_branch_offset: tuple[float, float] | None = None


SYMBOL_TERMINALS: dict[tuple[str, str], tuple[SymbolTerminalDef, ...]] = {
    ("voltage_source", "vertical_up"): (
        SymbolTerminalDef("pos", (0.0, -7.62), "top"),
        SymbolTerminalDef("neg", (0.0, 7.62), "bottom", "local_ground_drop"),
    ),
    ("current_source", "vertical_up"): (
        SymbolTerminalDef("pos", (0.0, -10.16), "top"),
        SymbolTerminalDef("neg", (0.0, 10.16), "bottom", "local_ground_drop"),
    ),
    ("resistor", "horizontal"): (
        SymbolTerminalDef("left", (-6.35, 0.0), "left", "series_inline"),
        SymbolTerminalDef("right", (6.35, 0.0), "right", "series_inline"),
    ),
    ("resistor", "vertical"): (
        SymbolTerminalDef("top", (0.0, -6.35), "top", "branch_to_junction"),
        SymbolTerminalDef("bottom", (0.0, 6.35), "bottom", "local_ground_drop"),
    ),
    ("capacitor", "vertical"): (
        SymbolTerminalDef("top", (0.0, -6.35), "top", "branch_to_junction"),
        SymbolTerminalDef("bottom", (0.0, 6.35), "bottom", "local_ground_drop"),
    ),
    ("capacitor", "horizontal"): (
        SymbolTerminalDef("left", (-6.35, 0.0), "left", "series_inline"),
        SymbolTerminalDef("right", (6.35, 0.0), "right", "series_inline"),
    ),
    ("inductor", "horizontal"): (
        SymbolTerminalDef("left", (-6.35, 0.0), "left", "series_inline"),
        SymbolTerminalDef("right", (6.35, 0.0), "right", "series_inline"),
    ),
    ("diode", "horizontal"): (
        SymbolTerminalDef("left", (-5.08, 0.0), "left", "series_inline"),
        SymbolTerminalDef("right", (5.08, 0.0), "right", "branch_to_junction"),
    ),
    ("diode", "vertical"): (
        SymbolTerminalDef("top", (0.0, -5.08), "top", "branch_to_junction"),
        SymbolTerminalDef("bottom", (0.0, 5.08), "bottom", "local_ground_drop"),
    ),
    ("ground", "down"): (
        SymbolTerminalDef("top", (0.0, 0.0), "top", "local_ground_drop"),
    ),
    ("power", "up"): (
        SymbolTerminalDef("bottom", (0.0, 0.0), "bottom", "local_supply_rise"),
    ),
    ("opamp", "right"): (
        SymbolTerminalDef("plus", (-7.62, 2.54), "left", "branch_to_junction", (-6.0, 0.0)),
        SymbolTerminalDef("minus", (-7.62, -2.54), "left", "feedback_loop", (-6.0, 0.0)),
        SymbolTerminalDef("out", (7.62, 0.0), "right", "series_inline", (6.0, 0.0)),
        SymbolTerminalDef("vplus", (-2.54, -7.62), "top", "local_supply_rise"),
        SymbolTerminalDef("vminus", (-2.54, 7.62), "bottom", "local_supply_rise"),
    ),
    ("npn_bjt", "right"): (
        SymbolTerminalDef("collector", (3.81, -8.89), "top", "branch_to_junction", (0.0, -6.0)),
        SymbolTerminalDef("base", (-7.62, 0.0), "left", "branch_to_junction", (-6.0, 0.0)),
        SymbolTerminalDef("emitter", (3.81, 8.89), "bottom", "local_ground_drop", (0.0, 6.0)),
        SymbolTerminalDef("substrate", (-2.54, 8.89), "bottom", "local_ground_drop", (0.0, 6.0)),
    ),
    ("pmos", "right"): (
        SymbolTerminalDef("drain", (2.54, 5.08), "bottom", "branch_to_junction", (0.0, 6.0)),
        SymbolTerminalDef("gate", (-5.08, 0.0), "left", "branch_to_junction", (-10.16, 0.0)),
        SymbolTerminalDef("source", (2.54, -5.08), "top", "local_supply_rise"),
        SymbolTerminalDef("body", (5.08, -5.08), "right", "local_supply_rise"),
    ),
    ("nmos", "right"): (
        SymbolTerminalDef("drain", (2.54, -5.08), "top", "branch_to_junction", (0.0, -6.0)),
        SymbolTerminalDef("gate", (-5.08, 0.0), "left", "branch_to_junction", (-10.16, 0.0)),
        SymbolTerminalDef("source", (2.54, 5.08), "bottom", "local_ground_drop"),
        SymbolTerminalDef("body", (5.08, 5.08), "right", "local_ground_drop"),
    ),
}

SYMBOL_BODY_BOXES: dict[tuple[str, str], tuple[float, float, float, float]] = {
    ("voltage_source", "vertical_up"): (-5.5, -5.5, 5.5, 5.5),
    ("current_source", "vertical_up"): (-5.5, -5.5, 5.5, 5.5),
    ("resistor", "horizontal"): (-4.5, -2.0, 4.5, 2.0),
    ("resistor", "vertical"): (-2.0, -4.5, 2.0, 4.5),
    ("capacitor", "vertical"): (-4.0, -2.0, 4.0, 2.0),
    ("capacitor", "horizontal"): (-2.0, -4.0, 2.0, 4.0),
    ("inductor", "horizontal"): (-5.2, -2.0, 5.2, 2.0),
    ("diode", "horizontal"): (-3.5, -3.0, 3.5, 3.0),
    ("diode", "vertical"): (-3.0, -3.5, 3.0, 3.5),
    ("ground", "down"): (-2.0, -3.0, 2.0, 1.0),
    ("power", "up"): (-2.0, -1.0, 2.0, 3.0),
    ("opamp", "right"): (-6.0, -6.0, 6.0, 6.0),
    ("npn_bjt", "right"): (-3.0, -5.0, 4.5, 5.0),
    ("pmos", "right"): (-3.0, -4.0, 5.5, 4.0),
    ("nmos", "right"): (-3.0, -4.0, 5.5, 4.0),
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
    for symbol_shape, orientation in SYMBOL_TERMINALS:
        if symbol_shape == shape:
            return orientation
    raise KeyError(shape)


def terminal_defs(shape: str, orientation: str) -> tuple[SymbolTerminalDef, ...]:
    return SYMBOL_TERMINALS[(shape, orientation)]


def body_box(shape: str, orientation: str) -> tuple[float, float, float, float]:
    return SYMBOL_BODY_BOXES[(shape, orientation)]


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
    return {value: key for key, value in KICAD_SYMBOLS.items()}
