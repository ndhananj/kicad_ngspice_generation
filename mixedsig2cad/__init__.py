"""High-level mixed-signal spec to KiCad/ngspice generators."""

from .compiled import CompiledSchematic, compile_schematic
from .intent import build_schematic_intent
from .consistency import (
    GeometryComparison,
    RoundTripReport,
    TopologyComparison,
    compare_geometries,
    compare_topologies,
    derive_topology_layout,
    roundtrip_image,
    roundtrip_kicad_schematic,
)
from .kicad_connectivity import ConnectivityReport, KiCadErcViolation, validate_kicad_connectivity
from .importers import (
    DrawingObservation,
    ObservedJunction,
    ObservedSymbol,
    ObservedWire,
    extract_geometry_from_image,
    import_kicad_schematic,
)
from .projections.kicad_render_validate import validate_rendered_kicad_symbols
from .spec import Analysis, CircuitSpec, Component
from .exporters.kicad import export_kicad_schematic
from .exporters.ngspice import export_ngspice_netlist

__all__ = [
    "Analysis",
    "CircuitSpec",
    "CompiledSchematic",
    "Component",
    "compile_schematic",
    "compare_geometries",
    "compare_topologies",
    "ConnectivityReport",
    "KiCadErcViolation",
    "GeometryComparison",
    "DrawingObservation",
    "ObservedJunction",
    "ObservedSymbol",
    "ObservedWire",
    "RoundTripReport",
    "build_schematic_intent",
    "derive_topology_layout",
    "extract_geometry_from_image",
    "export_kicad_schematic",
    "export_ngspice_netlist",
    "import_kicad_schematic",
    "roundtrip_image",
    "roundtrip_kicad_schematic",
    "validate_kicad_connectivity",
    "validate_rendered_kicad_symbols",
]
