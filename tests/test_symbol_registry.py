from __future__ import annotations

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
    assert body_box("opamp", "right") == (-6.0, -6.0, 6.0, 6.0)
