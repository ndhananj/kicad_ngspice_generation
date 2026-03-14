from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class BoundingBox:
    left: float
    top: float
    right: float
    bottom: float


@dataclass(frozen=True, slots=True)
class PlacedTerminal:
    name: str
    point: Point
    side: str
    preferred_connection_class: str | None = None
    preferred_branch_offset: tuple[float, float] | None = None


@dataclass(frozen=True, slots=True)
class TerminalTemplate:
    name: str
    offset: tuple[float, float]
    exit_direction: str
    preferred_connection_class: str | None = None
    preferred_branch_offset: tuple[float, float] | None = None


@dataclass(frozen=True, slots=True)
class SymbolGeometry:
    shape: str
    orientation: str
    lib_id: str
    angle: int
    terminals: tuple[TerminalTemplate, ...]
    body_box: tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class PlacedShape:
    ref: str
    value: str
    shape: str
    orientation: str
    center: Point
    terminals: tuple[PlacedTerminal, ...]
    body_box: BoundingBox
    hidden_reference: bool = False


@dataclass(frozen=True, slots=True)
class TerminalRef:
    owner_ref: str
    terminal_name: str


@dataclass(frozen=True, slots=True)
class PinExitCorridor:
    owner_ref: str
    terminal_name: str
    start: Point
    end: Point


@dataclass(frozen=True, slots=True)
class NodeAnchor:
    point: Point


@dataclass(frozen=True, slots=True)
class NodeTrunk:
    start: Point
    end: Point


@dataclass(frozen=True, slots=True)
class GeometryNode:
    id: str
    point: Point
    attachments: tuple[TerminalRef, ...]
    render_style: str = "inline"
    label: str | None = None
    role: str | None = None


@dataclass(frozen=True, slots=True)
class WirePath:
    points: tuple[Point, ...]
    uuid_seed: str


@dataclass(frozen=True, slots=True)
class TextPlacement:
    text: str
    role: str
    position: Point
    owner_ref: str
    uuid_seed: str


@dataclass(frozen=True, slots=True)
class JunctionPlacement:
    point: Point


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
