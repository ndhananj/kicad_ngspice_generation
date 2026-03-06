from __future__ import annotations

"""Compatibility facade for the older layout API.

New code should use:
- mixedsig2cad.intent.build_schematic_intent
- mixedsig2cad.geometry.build_schematic_geometry
- mixedsig2cad.projections.kicad.project_geometry_to_kicad
"""

from .geometry import JunctionPlacement, Point, PlacedShape, PlacedTerminal, SchematicGeometry, TextPlacement, WirePath
from .intent import SchematicIntent, build_schematic_intent
from .projections.kicad import (
    KiCadJunctionPlacement as JunctionPoint,
    KiCadPlacement as Placement,
    KiCadProjection as SchematicLayout,
    KiCadSymbolPlacement as SymbolPlacement,
    KiCadTextPlacement as LabelPlacement,
    KiCadWireSegment as WireSegment,
    project_geometry_to_kicad,
)
from .spec import CircuitSpec
from .geometry import build_schematic_geometry


def build_kicad_layout(spec: CircuitSpec) -> SchematicLayout:
    return project_geometry_to_kicad(build_schematic_geometry(build_schematic_intent(spec)))


__all__ = [
    "JunctionPlacement",
    "JunctionPoint",
    "LabelPlacement",
    "PlacedShape",
    "PlacedTerminal",
    "Placement",
    "Point",
    "SchematicGeometry",
    "SchematicIntent",
    "SchematicLayout",
    "SymbolPlacement",
    "TextPlacement",
    "WirePath",
    "WireSegment",
    "build_kicad_layout",
    "build_schematic_geometry",
    "build_schematic_intent",
]
