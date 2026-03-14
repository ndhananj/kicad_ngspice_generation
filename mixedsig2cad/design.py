from __future__ import annotations

from dataclasses import dataclass, field

from .models import Point
from .spec import CircuitSpec


@dataclass(frozen=True, slots=True)
class LayoutTextIntent:
    text: str
    role: str
    position: Point
    owner_ref: str
    font_size: float = 1.27


@dataclass(frozen=True, slots=True)
class LayoutComponentIntent:
    ref: str
    center: Point
    orientation: str
    reference_position: Point
    value_position: Point
    hidden_reference: bool = False


@dataclass(frozen=True, slots=True)
class LayoutSupportIntent:
    ref: str
    shape: str
    value: str
    center: Point
    orientation: str
    reference_position: Point
    value_position: Point
    hidden_reference: bool = False


@dataclass(frozen=True, slots=True)
class RoutedNetIntent:
    name: str
    segments: tuple[tuple[Point, ...], ...] = ()
    junctions: tuple[Point, ...] = ()


@dataclass(frozen=True, slots=True)
class SchematicLayoutIntent:
    name: str
    components: tuple[LayoutComponentIntent, ...]
    supports: tuple[LayoutSupportIntent, ...] = ()
    texts: tuple[LayoutTextIntent, ...] = ()
    routed_nets: tuple[RoutedNetIntent, ...] = ()


@dataclass(frozen=True, slots=True)
class ExampleDesign:
    name: str
    circuit: CircuitSpec
    layout: SchematicLayoutIntent


def circuit_of(design: ExampleDesign | CircuitSpec) -> CircuitSpec:
    if isinstance(design, ExampleDesign):
        return design.circuit
    return design


def example_name_of(design: ExampleDesign | CircuitSpec) -> str:
    return design.name if not isinstance(design, ExampleDesign) else design.name
