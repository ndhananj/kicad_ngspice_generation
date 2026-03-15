from __future__ import annotations

import shutil

import pytest

from mixedsig2cad.models import BoundingBox, Point
from mixedsig2cad.projections.kicad_render_validate import (
    PROBE_CENTER,
    RenderedSvgText,
    RenderedSymbolObservation,
    _compare_rendered_symbol,
    _expected_pin_name_points,
    _observe_pin_name_terminals,
    validate_rendered_kicad_symbols,
)
from mixedsig2cad.symbols import terminal_defs


def test_expected_pin_name_points_match_canonical_terminal_geometry() -> None:
    for shape, orientation in (
        ("voltage_source", "vertical_up"),
        ("diode", "vertical"),
        ("opamp", "right"),
        ("resistor", "horizontal"),
    ):
        expected_points = _expected_pin_name_points(shape, orientation)
        for terminal in terminal_defs(shape, orientation):
            if terminal.name not in expected_points:
                continue
            assert expected_points[terminal.name] == Point(
                round(PROBE_CENTER.x + terminal.offset[0], 2),
                round(PROBE_CENTER.y + terminal.offset[1], 2),
            )


def test_observe_pin_name_terminals_ignores_distant_duplicate_text() -> None:
    terminal_points = {
        "left": Point(94.92, 100.0),
        "right": Point(105.08, 100.0),
    }
    texts = [
        RenderedSvgText(
            text="1",
            anchor=Point(35.0, 11.65),
            bounds=BoundingBox(34.0, 11.0, 36.0, 12.0),
        ),
        RenderedSvgText(
            text="2",
            anchor=Point(85.0, 11.65),
            bounds=BoundingBox(84.0, 11.0, 86.0, 12.0),
        ),
        RenderedSvgText(
            text="1",
            anchor=Point(94.28, 99.75),
            bounds=BoundingBox(93.5, 99.0, 95.0, 100.5),
        ),
        RenderedSvgText(
            text="2",
            anchor=Point(105.72, 99.75),
            bounds=BoundingBox(105.0, 99.0, 106.5, 100.5),
        ),
    ]

    assignments = _observe_pin_name_terminals(texts, terminal_points, "inductor", "horizontal")

    assert assignments == {"1": "left", "2": "right"}


def test_observe_pin_name_terminals_matches_nearest_probe_terminal() -> None:
    terminal_points = {
        "drain": Point(102.54, 76.31),
        "gate": Point(75.92, 100.39),
        "source": Point(102.54, 124.47),
        "body": Point(124.08, 105.47),
    }
    texts = [
        RenderedSvgText("D", Point(102.29, 96.19), BoundingBox(101.0, 95.0, 103.0, 97.0)),
        RenderedSvgText("G", Point(96.83, 99.75), BoundingBox(96.0, 99.0, 97.5, 100.5)),
        RenderedSvgText("S", Point(102.29, 103.81), BoundingBox(101.0, 103.0, 103.0, 104.5)),
        RenderedSvgText("B", Point(104.83, 102.54), BoundingBox(104.0, 101.5, 105.5, 103.5)),
    ]

    assignments = _observe_pin_name_terminals(texts, terminal_points, "nmos", "right")

    assert assignments == {"D": "drain", "G": "gate", "S": "source", "B": "body"}


def test_compare_rendered_symbol_honors_strict_pin_labels_flag() -> None:
    observation = RenderedSymbolObservation(
        shape="opamp",
        orientation="right",
        center=PROBE_CENTER,
        terminal_sides={
            "plus": "left",
            "minus": "left",
            "out": "right",
            "vplus": "top",
            "vminus": "bottom",
        },
        pin_name_terminals={
            "+": "minus",
            "-": "plus",
            "V+": "vminus",
            "V-": "vplus",
        },
    )

    strict = _compare_rendered_symbol("opamp", "right", observation, strict_pin_labels=True)
    non_strict = _compare_rendered_symbol("opamp", "right", observation, strict_pin_labels=False)

    assert not strict.passed
    assert strict.notes
    assert non_strict.passed
    assert not non_strict.notes


@pytest.mark.skipif(shutil.which("kicad-cli") is None, reason="kicad-cli not installed")
def test_validate_rendered_kicad_symbols_passes_for_known_regressions() -> None:
    results = validate_rendered_kicad_symbols()
    by_key = {(result.shape, result.orientation): result for result in results}

    for key in (
        ("voltage_source", "vertical_up"),
        ("current_source", "vertical_up"),
        ("diode", "horizontal"),
        ("diode", "vertical"),
        ("inductor", "horizontal"),
        ("nmos", "right"),
        ("pmos", "right"),
        ("npn_bjt", "right"),
        ("opamp", "right"),
    ):
        assert by_key[key].passed, by_key[key].notes
