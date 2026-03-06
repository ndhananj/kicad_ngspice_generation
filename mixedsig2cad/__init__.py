"""High-level mixed-signal spec to KiCad/ngspice generators."""

from .geometry import JunctionPlacement, Point, PlacedShape, PlacedTerminal, SchematicGeometry, TextPlacement, WirePath, build_schematic_geometry
from .intent import (
    IntentComponent,
    IntentConnection,
    IntentGroup,
    IntentNet,
    IntentPattern,
    SchematicIntent,
    build_schematic_intent,
)
from .layout import build_kicad_layout
from .projections.kicad import (
    KiCadJunctionPlacement,
    KiCadPlacement,
    KiCadProjection,
    KiCadSymbolPlacement,
    KiCadTextPlacement,
    KiCadWireSegment,
    project_geometry_to_kicad,
)
from .spec import Analysis, CircuitSpec, Component
from .exporters.kicad import export_kicad_schematic
from .exporters.ngspice import export_ngspice_netlist

__all__ = [
    "Analysis",
    "CircuitSpec",
    "Component",
    "IntentComponent",
    "IntentConnection",
    "IntentGroup",
    "IntentNet",
    "IntentPattern",
    "JunctionPlacement",
    "KiCadJunctionPlacement",
    "KiCadPlacement",
    "KiCadProjection",
    "KiCadSymbolPlacement",
    "KiCadTextPlacement",
    "KiCadWireSegment",
    "PlacedShape",
    "PlacedTerminal",
    "Point",
    "SchematicGeometry",
    "SchematicIntent",
    "TextPlacement",
    "WirePath",
    "build_kicad_layout",
    "build_schematic_geometry",
    "build_schematic_intent",
    "export_kicad_schematic",
    "export_ngspice_netlist",
    "project_geometry_to_kicad",
]
