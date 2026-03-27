from __future__ import annotations

from mixedsig2cad.projections.symbol_render_validate import (
    SymbolRenderObservation,
    compare_symbol_render_observation,
)


def test_compare_symbol_render_observation_accepts_canonical_nmos_terminals() -> None:
    result = compare_symbol_render_observation(
        "nmos",
        "right",
        SymbolRenderObservation(
            shape="nmos",
            orientation="right",
            terminal_sides={"drain": "top", "gate": "left", "source": "bottom"},
            ignored_terminals=frozenset({"body"}),
        ),
        strict_pin_labels=False,
    )

    assert result.passed
    assert not result.notes


def test_compare_symbol_render_observation_rejects_swapped_cmos_terminals() -> None:
    result = compare_symbol_render_observation(
        "pmos",
        "right",
        SymbolRenderObservation(
            shape="pmos",
            orientation="right",
            terminal_sides={"drain": "top", "gate": "left", "source": "bottom"},
            ignored_terminals=frozenset({"body"}),
        ),
        strict_pin_labels=False,
    )

    assert not result.passed
    assert "terminal drain rendered on top, expected bottom" in result.notes
    assert "terminal source rendered on bottom, expected top" in result.notes
