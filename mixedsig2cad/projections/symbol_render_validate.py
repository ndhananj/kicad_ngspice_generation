from __future__ import annotations

from dataclasses import dataclass

from mixedsig2cad.kicad_symbols import project_symbol_pins
from mixedsig2cad.symbols import kicad_pin_map, kicad_symbol, terminal_defs


@dataclass(frozen=True, slots=True)
class SymbolRenderObservation:
    shape: str
    orientation: str
    terminal_sides: dict[str, str]
    pin_name_terminals: dict[str, str] | None = None
    ignored_terminals: frozenset[str] = frozenset()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SymbolRenderComparison:
    shape: str
    orientation: str
    expected_terminal_sides: dict[str, str]
    rendered_terminal_sides: dict[str, str]
    expected_pin_name_terminals: dict[str, str]
    rendered_pin_name_terminals: dict[str, str]
    passed: bool
    notes: tuple[str, ...]


def compare_symbol_render_observation(
    shape: str,
    orientation: str,
    observation: SymbolRenderObservation,
    *,
    strict_pin_labels: bool = True,
) -> SymbolRenderComparison:
    expected_terminal_sides = {template.name: template.exit_direction for template in terminal_defs(shape, orientation)}
    expected_pin_name_terminals = _expected_pin_name_terminals(shape, orientation)
    rendered_pin_name_terminals = observation.pin_name_terminals or {}
    notes = list(observation.notes)
    for terminal_name, expected_side in expected_terminal_sides.items():
        if terminal_name in observation.ignored_terminals:
            continue
        observed_side = observation.terminal_sides.get(terminal_name)
        if observed_side is None:
            notes.append(f"missing rendered terminal observation for {terminal_name}")
            continue
        if observed_side != expected_side:
            notes.append(f"terminal {terminal_name} rendered on {observed_side}, expected {expected_side}")
    for pin_name, expected_terminal in expected_pin_name_terminals.items():
        observed_terminal = rendered_pin_name_terminals.get(pin_name)
        if observed_terminal is None or observed_terminal == expected_terminal:
            continue
        note = f"pin name {pin_name} rendered nearest terminal {observed_terminal}, expected {expected_terminal}"
        if strict_pin_labels:
            notes.append(note)
    return SymbolRenderComparison(
        shape=shape,
        orientation=orientation,
        expected_terminal_sides=expected_terminal_sides,
        rendered_terminal_sides=observation.terminal_sides,
        expected_pin_name_terminals=expected_pin_name_terminals,
        rendered_pin_name_terminals=rendered_pin_name_terminals,
        passed=not notes,
        notes=tuple(notes),
    )


def _expected_pin_name_terminals(shape: str, orientation: str) -> dict[str, str]:
    pin_map = kicad_pin_map(shape, orientation)
    lib_id, _ = kicad_symbol(shape, orientation)
    lib_pins = project_symbol_pins()[lib_id]
    expected: dict[str, str] = {}
    for terminal_name, pin_number in pin_map.items():
        pin = lib_pins.get(pin_number)
        if pin is None or pin.name in {"", "~"}:
            continue
        expected[pin.name] = terminal_name
    return expected
