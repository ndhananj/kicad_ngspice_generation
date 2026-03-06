"""High-level mixed-signal spec to KiCad/ngspice generators."""

from .layout import (
    JunctionPoint,
    LabelPlacement,
    PinPlacement,
    Placement,
    SchematicLayout,
    SymbolPlacement,
    WireSegment,
    build_kicad_layout,
)
from .spec import Analysis, CircuitSpec, Component
from .exporters.kicad import export_kicad_schematic
from .exporters.ngspice import export_ngspice_netlist

__all__ = [
    "Analysis",
    "CircuitSpec",
    "Component",
    "JunctionPoint",
    "LabelPlacement",
    "PinPlacement",
    "Placement",
    "SchematicLayout",
    "SymbolPlacement",
    "WireSegment",
    "build_kicad_layout",
    "export_kicad_schematic",
    "export_ngspice_netlist",
]
