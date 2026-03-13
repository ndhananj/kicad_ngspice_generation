from __future__ import annotations

import importlib.util

from examples.specs.catalog import cmos_inverter, opamp_inverting, rc_lowpass
from mixedsig2cad.compiled import CompiledSchematic, compile_schematic
from mixedsig2cad.exporters.kicad import export_kicad_schematic, render_kicad_schematic
from mixedsig2cad import geometry
from mixedsig2cad.intent import build_schematic_intent
from mixedsig2cad import models
from mixedsig2cad.projections.kicad import project_geometry_to_kicad


def test_compile_schematic_returns_canonical_compiled_type() -> None:
    intent = build_schematic_intent(rc_lowpass())
    compiled = compile_schematic(intent)

    assert isinstance(compiled, CompiledSchematic)


def test_export_kicad_schematic_uses_canonical_compile_path() -> None:
    for spec in (rc_lowpass(), opamp_inverting(), cmos_inverter()):
        intent = build_schematic_intent(spec)
        compiled = compile_schematic(intent)
        expected = render_kicad_schematic(project_geometry_to_kicad(compiled))
        assert export_kicad_schematic(spec) == expected


def test_legacy_forward_entrypoints_are_removed() -> None:
    assert not hasattr(geometry, "build_schematic_geometry")
    assert importlib.util.find_spec("mixedsig2cad.layout") is None
    assert not hasattr(models, "SchematicGeometry")
    assert importlib.util.find_spec("mixedsig2cad.compiler_impl") is None
