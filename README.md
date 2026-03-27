# kicad_ngspice_generation

A Python-first toolkit and example corpus for generating **KiCad schematic files** and **ngspice netlists** from a shared mixed-signal specification.

## Install

```bash
bash scripts/install_dev_env.sh
python3 scripts/setup_parser_env.py
```

`scripts/install_dev_env.sh` is the supported bootstrap path for Debian/Ubuntu-style Linux hosts. It installs the local system packages and repo dependencies needed for the full validator stack, including OCR, TeX, KiCad CLI, Node, npm packages, and Playwright's Chromium runtime.

`python3 scripts/setup_parser_env.py` is the verification pass. It checks the Python modules, OCR binary, TeX tooling, KiCad CLI, and frontend runtime, then points back to the bootstrap command if anything is still missing.

## What is included

- `mixedsig2cad/`: library code for high-level spec modeling and exporters.
- `examples/specs/catalog.py`: parameterized example topologies plus instantiation helpers.
- `examples/specs/circuit_values.json`: single source of circuit values, models, waveforms, and analyses for all examples.
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
    build_circuitikz_ir,
    build_example_report_bundle,
    build_schematic_intent,
    build_tex_report,
    compile_schematic,
    export_circuitikz,
    export_example_report_tex,
    export_kicad_schematic,
    export_ngspice_netlist,
    render_circuitikz_ir,
)

kicad_intent = build_schematic_intent(spec)
kicad_geometry = compile_schematic(kicad_intent)
kicad_circuitikz_ir = build_circuitikz_ir(spec)
kicad_report_bundle = build_example_report_bundle(spec)
kicad_report_ir = build_tex_report(spec)
kicad_circuitikz = export_circuitikz(spec)
kicad_circuitikz_text = render_circuitikz_ir(kicad_circuitikz_ir)
kicad_report = export_example_report_tex(spec)
kicad_text = export_kicad_schematic(spec)
ngspice_text = export_ngspice_netlist(spec)
```

## Parameterized example library

The authored examples are split into:

- topology templates in `examples/specs/catalog.py` with refs, kinds, and connectivity only
- shared instance data in `examples/specs/circuit_values.json`
- generated `CircuitSpec` / `ExampleDesign` objects created by instantiating a topology with one JSON entry

Example:

```python
from examples.specs.catalog import (
    block_named,
    build_rc_lowpass_topology,
    instantiate_block,
    instantiate_circuit_block,
    example_instance_values,
    instantiate_topology,
    merge_designs,
    rc_lowpass,
)

topology = build_rc_lowpass_topology()
values = example_instance_values("rc_lowpass")
spec = instantiate_topology(topology, values)
design = rc_lowpass()

lowpass_block = block_named("rc_lowpass")
stage_a = instantiate_block(
    lowpass_block,
    parameters={"components": {"R1": {"value": "4.7k"}}},
    pin_map={"vin": "sensor_in", "vout": "filtered_a"},
    ref_prefix="A_",
    instance_name="stage_a",
)
stage_b = instantiate_circuit_block(
    lowpass_block,
    pin_map={"vin": "filtered_a", "vout": "filtered_b"},
    ref_prefix="B_",
    instance_name="stage_b",
)
stacked = merge_designs("two_stage_filter", [stage_a, rc_lowpass()])
```

This keeps the main architectures free of hard-coded numbers and ensures the TeX, KiCad, and ngspice outputs all draw their example-specific values from the same source.

The same catalog can now be used as a reusable Python block library:

- `block_named(name)`: fetch a reusable full-design block definition
- `instantiate_circuit_block(...)`: flatten a block directly into a `CircuitSpec`
- `instantiate_block(...)`: flatten a block into an `ExampleDesign` with reusable layout intent
- `merge_designs(...)`: combine prefixed block instances into a larger flat design

The pipeline is now layered:

- `CircuitSpec`: circuit connectivity and simulation metadata
- `build_schematic_intent(spec)`: schematic-semantic intent
- `compile_schematic(intent)`: canonical compiled schematic
- `project_geometry_to_kicad(geometry)`: KiCad-specific projection adapter
- `build_circuitikz_ir(spec)`: staged TeX drawing IR for readable circuits
- `build_example_report_bundle(spec)`: modular TeX report bundle with shared includes and external KiCad image assets
- `build_tex_report(spec)`: staged TeX document IR for reports
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


## Circuit Editor frontend

A lightweight static frontend is included in `frontend/` for browsing the generated circuit corpus with the circuit editor design system.

```bash
python3 scripts/serve_frontend.py
```

Then open `http://127.0.0.1:8000/frontend/` to browse SVG previews and jump directly to generated KiCad, ngspice, and TeX artifacts.

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
1) topology source in `examples/specs/catalog.py`,
2) shared instance values in `examples/specs/circuit_values.json`,
3) generated KiCad file in `examples/generated/kicad/`, and
4) generated ngspice file in `examples/generated/ngspice/`, and
5) generated TeX report files in `examples/generated/tex/`.

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
- `<name>.tex`: a standalone report assembled from shared TeX includes and per-example fragments.
- `common/*.tex`: shared TeX package and macro includes used by all reports.
- `fragments/<name>/*.tex`: modular readable/summary/notes TeX fragments for each example.
- `../svg/<name>.svg`: KiCad-rendered reference view kept as a separate asset.
- `../svg/<name>.pdf`: TeX-friendly companion for the same KiCad-rendered reference view.
- `examples.tex`: a master document covering the whole example corpus.

`python3 scripts/validate_examples.py` compiles the generated report files with `pdflatex -shell-escape`. The Linux bootstrap script installs the TeX tooling expected by the full validator.

## Notes on compatibility

- ngspice outputs are standard SPICE deck files (`.cir`).
- KiCad outputs are `kicad_sch` schematic files with deterministic UUIDs.
- This repository validates generated files structurally in CI-friendly Python checks.

## Frontend testing

The frontend now exposes a manifest-driven fixture mode so UI behavior can be validated even when the generated example corpus is incomplete.

Run the browser suite:

```bash
npm run test:frontend
```

If you have not bootstrapped the repo yet, run `bash scripts/install_dev_env.sh` first so Node, npm packages, and a Chromium runtime are available locally.

Refresh the visual baselines after intentional UI changes:

```bash
npm run test:frontend:update
```

The Playwright config starts `scripts/serve_frontend.py` against `tests/fixtures/frontend_corpus`, which includes success and missing-artifact cases for `report.tex` and SVG previews.
