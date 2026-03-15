# kicad_ngspice_generation

A Python-first toolkit and example corpus for generating **KiCad schematic files** and **ngspice netlists** from a shared mixed-signal specification.

## Install

```bash
pip install -r requirements.txt
python3 scripts/setup_parser_env.py
```

The setup script verifies the parser stack is present. For OCR-backed parsing with `pytesseract`, you also need the external `tesseract` binary installed on the system.

## What is included

- `mixedsig2cad/`: library code for high-level spec modeling and exporters.
- `examples/specs/catalog.py`: 8 programmatic circuit examples.
- `examples/generated/kicad/*.kicad_sch`: generated KiCad schematic examples.
- `examples/generated/kicad/examples.kicad_pro`: KiCad project that opens all generated schematics as hierarchical sheets.
- `examples/generated/ngspice/*.cir`: generated ngspice netlist examples.
- `examples/generated/tex/*.tex`: generated TeX circuit reports and the master report.
- `scripts/generate_examples.py`: regenerates all example outputs.
- `scripts/validate_examples.py`: structural validator for generated outputs.

## High-level specification API

```python
from mixedsig2cad import CircuitSpec

spec = (
    CircuitSpec("rc_lowpass")
    .add("V1", "V", "DC 5", "vin", "0")
    .add("R1", "R", "1k", "vin", "vout")
    .add("C1", "C", "100n", "vout", "0")
    .analyze("op")
)
```

Export:

```python
from mixedsig2cad import (
    build_schematic_intent,
    compile_schematic,
    export_circuitikz,
    export_example_report_tex,
    export_kicad_schematic,
    export_ngspice_netlist,
)

kicad_intent = build_schematic_intent(spec)
kicad_geometry = compile_schematic(kicad_intent)
kicad_circuitikz = export_circuitikz(spec)
kicad_report = export_example_report_tex(spec)
kicad_text = export_kicad_schematic(spec)
ngspice_text = export_ngspice_netlist(spec)
```

The pipeline is now layered:

- `CircuitSpec`: circuit connectivity and simulation metadata
- `build_schematic_intent(spec)`: schematic-semantic intent
- `compile_schematic(intent)`: canonical compiled schematic
- `project_geometry_to_kicad(geometry)`: KiCad-specific projection adapter
- `export_kicad_schematic(spec)`: full orchestration to KiCad text
- `export_circuitikz(spec)`: readable TeX circuit rendering
- `export_example_report_tex(spec)`: standalone TeX report with starter notes

`compile_schematic()` is the single supported forward compilation path.

Reverse extraction is also available:

```python
from mixedsig2cad import (
    parse_circuit_source,
    compare_geometries,
    compare_topologies,
    derive_topology_layout,
    import_kicad_schematic,
    roundtrip_kicad_schematic,
)

geometry = import_kicad_schematic("examples/generated/kicad/rc_lowpass.kicad_sch")
topology = derive_topology_layout(geometry)
report = roundtrip_kicad_schematic("examples/generated/kicad/rc_lowpass.kicad_sch")
parsed = parse_circuit_source(
    "examples/generated/kicad/rc_lowpass.kicad_sch",
    source_type="vector",
    output_dir="out/rc_lowpass_parse",
)
```

Current reverse-import guarantees:

- `.kicad_sch -> CompiledSchematic -> TopologyLayout` is exact for the generated example corpus.
- KiCad image import is implemented through `extract_geometry_from_image(...)`.
- SVG images exported from KiCad are the supported image path today.
- Bitmap and hand-drawn image extraction remain best-effort.
- `parse_circuit_source(..., source_type="vector")` emits scene data, graph data, overlay output, and optional netlists when a `CircuitSpec` is provided.
- `parse_circuit_source(..., source_type="raster")` currently enforces parser dependency checks and reserves the SAM-backed raster path.

## Generate the full example library

```bash
python3 scripts/generate_examples.py
python3 scripts/validate_examples.py
```

## Architecture

The supported layering is:

- semantic layer: `CircuitSpec -> build_schematic_intent(spec)`
- canonical compiler layer: `compile_schematic(intent) -> CompiledSchematic`
- adapter layer: KiCad export/import, ngspice export, topology comparison, and raster extraction

Internal code is split so most maintenance tasks only need one focused area:

- `models.py`: canonical schematic dataclasses
- `compiler/`: compile orchestration and strategy modules
- `geometry.py`: low-level routing/validation helpers

## Example library catalog

Each entry has:
1) programmatic source in `examples/specs/catalog.py`,
2) generated KiCad file in `examples/generated/kicad/`, and
3) generated ngspice file in `examples/generated/ngspice/`, and
4) generated TeX report files in `examples/generated/tex/`.

- `rc_lowpass`
- `rc_highpass`
- `rlc_bandpass`
- `diode_clipper`
- `bjt_common_emitter`
- `opamp_inverting`
- `cmos_inverter`
- `schmitt_trigger`


Open `examples/generated/kicad/examples.kicad_pro` in KiCad to browse every generated example from a single project window.

## TeX reports

Running `python3 scripts/generate_examples.py` also writes:

- `<name>.circuitikz.tex`: readable circuit-only source for later manual editing.
- `<name>.literal.tex`: a more literal TikZ rendering derived from the KiCad-aligned geometry.
- `<name>.tex`: a standalone report with both renderings, a generated summary, and starter design-note sections.
- `examples.tex`: a master document covering the whole example corpus.

`python3 scripts/validate_examples.py` compiles the generated report files with `pdflatex`, so a local TeX install with `circuitikz` is expected when running the full validator.

## Notes on compatibility

- ngspice outputs are standard SPICE deck files (`.cir`).
- KiCad outputs are `kicad_sch` schematic files with deterministic UUIDs.
- This repository validates generated files structurally in CI-friendly Python checks.
