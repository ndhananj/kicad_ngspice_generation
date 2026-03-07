from __future__ import annotations

from dataclasses import dataclass, field

from .compiler_impl import compile_intent_geometry
from .geometry import (
    BoundingBox,
    GeometryNode,
    JunctionPlacement,
    NodeAnchor,
    NodeTrunk,
    PlacedShape,
    PlacedTerminal,
    Point,
    TextPlacement,
    WirePath,
)
from .intent import SchematicIntent
from .symbols import body_box, terminal_defs


@dataclass(slots=True)
class CompiledSchematic:
    name: str
    shapes: list[PlacedShape] = field(default_factory=list)
    nodes: list[GeometryNode] = field(default_factory=list)
    anchors: list[NodeAnchor] = field(default_factory=list)
    trunks: list[NodeTrunk] = field(default_factory=list)
    wires: list[WirePath] = field(default_factory=list)
    labels: list[TextPlacement] = field(default_factory=list)
    junctions: list[JunctionPlacement] = field(default_factory=list)


def _as_compiled_schematic(geometry) -> CompiledSchematic:
    return CompiledSchematic(
        name=geometry.name,
        shapes=list(geometry.shapes),
        nodes=list(geometry.nodes),
        anchors=list(geometry.anchors),
        trunks=list(geometry.trunks),
        wires=list(geometry.wires),
        labels=list(geometry.labels),
        junctions=list(geometry.junctions),
    )


def compile_schematic(intent: SchematicIntent) -> CompiledSchematic:
    return _as_compiled_schematic(compile_intent_geometry(intent))


def make_terminals(shape: str, orientation: str, center: Point) -> tuple[PlacedTerminal, ...]:
    return tuple(
        PlacedTerminal(
            name=terminal.name,
            point=Point(round(center.x + terminal.offset[0], 2), round(center.y + terminal.offset[1], 2)),
            side=terminal.exit_direction,
            preferred_connection_class=terminal.preferred_connection_class,
            preferred_branch_offset=terminal.preferred_branch_offset,
        )
        for terminal in terminal_defs(shape, orientation)
    )


def make_body_box(shape: str, orientation: str, center: Point) -> BoundingBox:
    left, top, right, bottom = body_box(shape, orientation)
    return BoundingBox(
        left=round(center.x + left, 2),
        top=round(center.y + top, 2),
        right=round(center.x + right, 2),
        bottom=round(center.y + bottom, 2),
    )


def place_shape(
    *,
    ref: str,
    value: str,
    shape: str,
    orientation: str,
    center: Point,
    hidden_reference: bool = False,
) -> PlacedShape:
    return PlacedShape(
        ref=ref,
        value=value,
        shape=shape,
        orientation=orientation,
        center=center,
        terminals=make_terminals(shape, orientation, center),
        body_box=make_body_box(shape, orientation, center),
        hidden_reference=hidden_reference,
    )
