from __future__ import annotations

import pytest

from mixedsig2cad.geometry import validate_schematic_geometry
from mixedsig2cad.models import CompiledSchematic, Point, WirePath


def test_overlapping_wire_segments_are_rejected() -> None:
    geometry = CompiledSchematic(
        name="overlap",
        wires=[
            WirePath(points=(Point(50.80, 50.80), Point(50.80, 76.20)), uuid_seed="overlap:a"),
            WirePath(points=(Point(50.80, 63.50), Point(50.80, 88.90)), uuid_seed="overlap:b"),
        ],
    )

    with pytest.raises(AssertionError, match="overlap"):
        validate_schematic_geometry(geometry)


def test_undeclared_wire_intersections_are_rejected() -> None:
    geometry = CompiledSchematic(
        name="intersection",
        wires=[
            WirePath(points=(Point(50.80, 63.50), Point(88.90, 63.50)), uuid_seed="intersection:h"),
            WirePath(points=(Point(69.85, 50.80), Point(69.85, 88.90)), uuid_seed="intersection:v"),
        ],
    )

    with pytest.raises(AssertionError, match="intersect"):
        validate_schematic_geometry(geometry)
