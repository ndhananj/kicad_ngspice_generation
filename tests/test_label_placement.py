from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from mixedsig2cad.label_placement import normalize_example_label_positions
from mixedsig2cad.models import BoundingBox, CompiledSchematic, GeometryNode, JunctionPlacement, PlacedShape, Point, TextPlacement, WirePath
from mixedsig2cad.projections.kicad_render_validate import validate_rendered_example_labels


ROOT = Path(__file__).resolve().parents[1]


def test_shape_label_is_moved_out_of_body_overlap() -> None:
    geometry = CompiledSchematic(
        name="shape_overlap",
        shapes=[
            PlacedShape(
                ref="R1",
                value="1k",
                shape="resistor",
                orientation="horizontal",
                center=Point(50.8, 50.8),
                terminals=(),
                body_box=BoundingBox(45.0, 48.0, 56.6, 53.6),
            )
        ],
        labels=[
            TextPlacement("R1", "reference", Point(50.8, 50.8), "R1", "shape_overlap:R1:ref"),
        ],
    )

    normalized = normalize_example_label_positions(geometry)
    label = normalized.labels[0]
    box = BoundingBox(label.position.x - 1.5, label.position.y - 0.8, label.position.x + 1.5, label.position.y + 0.8)

    assert not _boxes_overlap(box, normalized.shapes[0].body_box)


def test_net_label_is_moved_off_wire_anchor() -> None:
    geometry = CompiledSchematic(
        name="net_overlap",
        wires=[WirePath(points=(Point(40.0, 40.0), Point(60.0, 40.0)), uuid_seed="wire:1")],
        junctions=[JunctionPlacement(point=Point(50.0, 40.0))],
        nodes=[GeometryNode(id="n1", point=Point(50.0, 40.0), attachments=(), label="vin")],
        labels=[TextPlacement("vin", "net_label", Point(50.0, 40.0), "label:1", "net_overlap:vin")],
    )

    normalized = normalize_example_label_positions(geometry)
    label = normalized.labels[0]

    assert label.position != Point(50.0, 40.0)
    assert label.position.y != 40.0
    assert label.anchor_position == Point(50.0, 40.0)
    assert len(normalized.wires) == 1


def test_label_search_avoids_previously_placed_label_overlap() -> None:
    geometry = CompiledSchematic(
        name="label_stack",
        shapes=[
            PlacedShape(
                ref="R1",
                value="1k",
                shape="resistor",
                orientation="horizontal",
                center=Point(50.8, 50.8),
                terminals=(),
                body_box=BoundingBox(45.0, 48.0, 56.6, 53.6),
            )
        ],
        labels=[
            TextPlacement("R1", "reference", Point(50.8, 45.0), "R1", "label_stack:R1:ref"),
            TextPlacement("1k", "value", Point(50.8, 45.0), "R1", "label_stack:R1:value"),
        ],
    )

    normalized = normalize_example_label_positions(geometry)
    first, second = normalized.labels
    first_box = BoundingBox(first.position.x - 1.5, first.position.y - 0.8, first.position.x + 1.5, first.position.y + 0.8)
    second_box = BoundingBox(second.position.x - 1.5, second.position.y - 0.8, second.position.x + 1.5, second.position.y + 0.8)

    assert not _boxes_overlap(first_box, second_box)


def test_valid_existing_side_preference_is_preserved() -> None:
    geometry = CompiledSchematic(
        name="preferred_side",
        shapes=[
            PlacedShape(
                ref="C1",
                value="100n",
                shape="capacitor",
                orientation="horizontal",
                center=Point(50.8, 50.8),
                terminals=(),
                body_box=BoundingBox(46.0, 47.0, 55.6, 54.6),
            )
        ],
        labels=[TextPlacement("C1", "reference", Point(50.8, 43.18), "C1", "preferred_side:C1:ref")],
    )

    normalized = normalize_example_label_positions(geometry)

    assert normalized.labels[0].position.y < geometry.shapes[0].body_box.top


@pytest.mark.skipif(shutil.which("kicad-cli") is None, reason="kicad-cli not installed")
def test_generated_examples_have_non_overlapping_rendered_labels() -> None:
    paths = sorted((ROOT / "examples" / "generated" / "kicad").glob("*.kicad_sch"))

    results = validate_rendered_example_labels(paths)

    assert results
    assert all(result.passed for result in results)


def _boxes_overlap(first: BoundingBox, second: BoundingBox) -> bool:
    return not (
        first.right <= second.left
        or first.left >= second.right
        or first.bottom <= second.top
        or first.top >= second.bottom
    )
