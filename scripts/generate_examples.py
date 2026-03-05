from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from examples.specs.catalog import all_examples
from mixedsig2cad import export_kicad_schematic, export_ngspice_netlist

KICAD_DIR = ROOT / "examples" / "generated" / "kicad"
NGSPICE_DIR = ROOT / "examples" / "generated" / "ngspice"


def main() -> None:
    KICAD_DIR.mkdir(parents=True, exist_ok=True)
    NGSPICE_DIR.mkdir(parents=True, exist_ok=True)

    for spec in all_examples():
        (KICAD_DIR / f"{spec.name}.kicad_sch").write_text(export_kicad_schematic(spec), encoding="utf-8")
        (NGSPICE_DIR / f"{spec.name}.cir").write_text(export_ngspice_netlist(spec), encoding="utf-8")
        print(f"generated: {spec.name}")


if __name__ == "__main__":
    main()
