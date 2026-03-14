from __future__ import annotations

import pytest

from mixedsig2cad.compiled import place_shape
from mixedsig2cad.geometry import _path_is_clear, _simplify_path, validate_schematic_geometry
from mixedsig2cad.models import BoundingBox, CompiledSchematic, PinExitCorridor, Point, WirePath
from mixedsig2cad.projections.kicad import project_geometry_to_kicad, validate_kicad_projection


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


def test_exit_corridor_remains_legal_after_path_simplification() -> None:
    start_box = BoundingBox(161.83, 151.94, 165.83, 155.94)
    node_box = BoundingBox(157.02, 133.16, 165.52, 141.16)
    raw_path = (
        Point(163.83, 154.94),
        Point(163.83, 146.86),
        Point(163.83, 142.24),
    )
    corridor = PinExitCorridor(
        owner_ref="#PWR0003",
        terminal_name="top",
        start=Point(163.83, 154.94),
        end=Point(163.83, 146.86),
    )
    assert _path_is_clear(raw_path, [start_box, node_box], corridor, None, start_box=start_box, end_box=None)

    simplified = _simplify_path(raw_path)
    assert simplified == (Point(163.83, 154.94), Point(163.83, 142.24))
    assert _path_is_clear(simplified, [start_box, node_box], corridor, None, start_box=start_box, end_box=None)


def test_local_support_wire_with_extra_bends_is_rejected() -> None:
    geometry = CompiledSchematic(
        name="support_kink",
        wires=[
            WirePath(
                points=(
                    Point(163.83, 154.94),
                    Point(163.83, 147.32),
                    Point(171.45, 147.32),
                    Point(171.45, 142.24),
                    Point(163.83, 142.24),
                ),
                uuid_seed="support_kink:#PWR0003:ground:#PWR0003:3",
            )
        ],
    )

    with pytest.raises(AssertionError, match="unnecessary bends"):
        validate_schematic_geometry(geometry)


def test_kicad_projection_rejects_terminal_drift_from_canonical_symbol_geometry() -> None:
    geometry = CompiledSchematic(
        name="terminal_drift",
        shapes=[place_shape(ref="XU1", value="OPAMP", shape="opamp", orientation="right", center=Point(100.0, 100.0))],
    )
    projection = project_geometry_to_kicad(geometry)
    shape = geometry.shapes[0]
    geometry.shapes[0] = type(shape)(
        ref=shape.ref,
        value=shape.value,
        shape=shape.shape,
        orientation=shape.orientation,
        center=shape.center,
        terminals=(
            type(shape.terminals[0])(
                name=shape.terminals[0].name,
                point=Point(shape.terminals[0].point.x, shape.terminals[0].point.y + 1.27),
                side=shape.terminals[0].side,
                preferred_connection_class=shape.terminals[0].preferred_connection_class,
                preferred_branch_offset=shape.terminals[0].preferred_branch_offset,
            ),
            *shape.terminals[1:],
        ),
        body_box=shape.body_box,
        hidden_reference=shape.hidden_reference,
    )

    with pytest.raises(AssertionError, match="canonical KiCad pin position"):
        validate_kicad_projection(projection, geometry)
