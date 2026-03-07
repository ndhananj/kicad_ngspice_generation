from __future__ import annotations

from dataclasses import dataclass

from mixedsig2cad.geometry import Point


@dataclass(frozen=True, slots=True)
class ObservedSymbol:
    kind: str
    center: Point
    orientation: str | None
    confidence: float
    ref_text: str | None = None
    value_text: str | None = None


@dataclass(frozen=True, slots=True)
class ObservedWire:
    points: tuple[Point, ...]
    confidence: float


@dataclass(frozen=True, slots=True)
class ObservedJunction:
    point: Point
    confidence: float


@dataclass(frozen=True, slots=True)
class DrawingObservation:
    symbols: tuple[ObservedSymbol, ...]
    wires: tuple[ObservedWire, ...]
    junctions: tuple[ObservedJunction, ...]
    source_kind: str
