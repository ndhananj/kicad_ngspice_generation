from __future__ import annotations

from examples.specs.catalog import opamp_inverting, rc_lowpass
from mixedsig2cad.compiled import compile_schematic
from mixedsig2cad.exporters.kicad import export_kicad_schematic, render_kicad_schematic
from mixedsig2cad.intent import build_schematic_intent
from mixedsig2cad.projections.kicad import project_geometry_to_kicad


def test_export_kicad_schematic_uses_canonical_compile_path() -> None:
    for spec in (rc_lowpass(), opamp_inverting()):
        intent = build_schematic_intent(spec)
        compiled = compile_schematic(intent)
        expected = render_kicad_schematic(project_geometry_to_kicad(compiled))
        assert export_kicad_schematic(spec) == expected

