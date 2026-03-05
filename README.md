# kicad_ngspice_generation

A Python-first toolkit and example corpus for generating **KiCad schematic files** and **ngspice netlists** from a shared mixed-signal specification.

## What is included

- `mixedsig2cad/`: library code for high-level spec modeling and exporters.
- `examples/specs/catalog.py`: 8 programmatic circuit examples.
- `examples/generated/kicad/*.kicad_sch`: generated KiCad schematic examples.
- `examples/generated/kicad/examples.kicad_pro`: KiCad project that opens all generated schematics as hierarchical sheets.
- `examples/generated/ngspice/*.cir`: generated ngspice netlist examples.
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
from mixedsig2cad import export_kicad_schematic, export_ngspice_netlist

kicad_text = export_kicad_schematic(spec)
ngspice_text = export_ngspice_netlist(spec)
```

## Generate the full example library

```bash
python3 scripts/generate_examples.py
python3 scripts/validate_examples.py
```

## Example library catalog

Each entry has:
1) programmatic source in `examples/specs/catalog.py`,
2) generated KiCad file in `examples/generated/kicad/`, and
3) generated ngspice file in `examples/generated/ngspice/`.

- `rc_lowpass`
- `rc_highpass`
- `rlc_bandpass`
- `diode_clipper`
- `bjt_common_emitter`
- `opamp_inverting`
- `cmos_inverter`
- `schmitt_trigger`


Open `examples/generated/kicad/examples.kicad_pro` in KiCad to browse every generated example from a single project window.

## Notes on compatibility

- ngspice outputs are standard SPICE deck files (`.cir`).
- KiCad outputs are `kicad_sch` schematic files with deterministic UUIDs.
- This repository validates generated files structurally in CI-friendly Python checks.
