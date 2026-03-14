"""High-level mixed-signal spec to KiCad/ngspice generators."""

from .compiled import CompiledSchematic, compile_schematic
from .design import ExampleDesign, SchematicLayoutIntent
from .intent import build_schematic_intent
from .layout_compiler import compile_design
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
    CanonicalScene,
    DependencyStatus,
    DrawingObservation,
    ObservedJunction,
    ObservedSymbol,
    ObservedWire,
    ParseArtifacts,
    ParsedComponent,
    ParsedGraph,
    ParsedJunction,
    ParseResult,
    check_parser_runtime_dependencies,
    extract_geometry_from_image,
    import_kicad_schematic,
    parse_circuit_source,
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
    "ExampleDesign",
    "SchematicLayoutIntent",
    "compile_design",
    "compile_schematic",
    "compare_geometries",
    "compare_topologies",
    "check_parser_runtime_dependencies",
    "ConnectivityReport",
    "DependencyStatus",
    "KiCadErcViolation",
    "GeometryComparison",
    "CanonicalScene",
    "DrawingObservation",
    "ObservedJunction",
    "ObservedSymbol",
    "ObservedWire",
    "ParseArtifacts",
    "ParsedComponent",
    "ParsedGraph",
    "ParsedJunction",
    "ParseResult",
    "RoundTripReport",
    "build_schematic_intent",
    "derive_topology_layout",
    "extract_geometry_from_image",
    "export_kicad_schematic",
    "export_ngspice_netlist",
    "import_kicad_schematic",
    "parse_circuit_source",
    "roundtrip_image",
    "roundtrip_kicad_schematic",
    "validate_kicad_connectivity",
    "validate_rendered_kicad_symbols",
]
