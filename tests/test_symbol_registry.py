from __future__ import annotations

from mixedsig2cad.kicad_symbols import project_symbol_body_bounds, project_symbol_pins
from mixedsig2cad.projections.kicad import _projected_kicad_offsets
from mixedsig2cad.symbols import (
    KICAD_PIN_MAPS,
    KICAD_SYMBOLS,
    body_box,
    component_symbol,
    default_orientation_for_component,
    terminal_defs,
    terminal_name_for_component,
    terminal_offset_for_component,
)


def test_kicad_mappings_cover_every_symbol_variant() -> None:
    assert set(KICAD_SYMBOLS) == set(KICAD_PIN_MAPS)
    for shape, orientation in KICAD_SYMBOLS:
        terminal_names = {terminal.name for terminal in terminal_defs(shape, orientation)}
        assert terminal_names == set(KICAD_PIN_MAPS[(shape, orientation)])


def test_component_symbol_rules_drive_terminal_metadata() -> None:
    assert component_symbol("R") == ("resistor", "horizontal")
    assert default_orientation_for_component("C") == "vertical"
    assert component_symbol("M", "NM1", "NMOS_MODEL")[0] == "nmos"
    assert component_symbol("M", "PM1", "PMOS_MODEL")[0] == "pmos"

    assert terminal_name_for_component("Q", "right", 0) == "collector"
    assert terminal_name_for_component("Q", "right", 1) == "base"
    assert terminal_name_for_component("Q", "right", 3) == "substrate"
    assert terminal_offset_for_component("R", "horizontal", "left") == (-6.35, 0.0)
    assert terminal_offset_for_component("Q", "right", "substrate") == (-2.54, 8.89)
    assert terminal_offset_for_component("X", "right", "plus") == (-7.62, 2.54)
    assert body_box("opamp", "right") == (-5.08, -5.08, 5.08, 5.08)
    assert body_box("power", "up") == (-0.76, -2.54, 0.76, 0.0)
    assert body_box("power", "down") == (-0.76, 0.0, 0.76, 2.54)


def test_terminal_offsets_match_embedded_kicad_pins_for_every_symbol_variant() -> None:
    lib_pins_by_symbol = project_symbol_pins()
    for shape, orientation in KICAD_SYMBOLS:
        lib_id, _angle = KICAD_SYMBOLS[(shape, orientation)]
        pin_map = KICAD_PIN_MAPS[(shape, orientation)]
        lib_pins = lib_pins_by_symbol[lib_id]
        projected = _projected_kicad_offsets(shape, orientation)
        for terminal_name, pin_number in pin_map.items():
            assert pin_number in lib_pins
            assert terminal_name in projected


def test_body_boxes_are_derived_from_embedded_kicad_symbol_art() -> None:
    for shape, orientation in KICAD_SYMBOLS:
        lib_id, angle = KICAD_SYMBOLS[(shape, orientation)]
        expected = project_symbol_body_bounds(lib_id, angle)
        assert body_box(shape, orientation) == (
            expected.left,
            expected.top,
            expected.right,
            expected.bottom,
        )
