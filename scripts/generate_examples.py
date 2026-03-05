from __future__ import annotations

from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from examples.specs.catalog import all_examples
from mixedsig2cad import export_kicad_schematic, export_ngspice_netlist

KICAD_DIR = ROOT / "examples" / "generated" / "kicad"
NGSPICE_DIR = ROOT / "examples" / "generated" / "ngspice"
PROJECT_NAME = "examples"


def _aggregate_schematic(example_names: list[str]) -> str:
    project_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, "mixedsig2cad:examples_project")
    sheets: list[tuple[str, uuid.UUID]] = [
        (name, uuid.uuid5(uuid.NAMESPACE_DNS, f"mixedsig2cad:sheet:{name}"))
        for name in example_names
    ]

    lines = [
        "(kicad_sch",
        "  (version 20231120)",
        '  (generator "mixedsig2cad")',
        f"  (uuid {project_uuid})",
        '  (paper "A4")',
        "  (lib_symbols)",
    ]

    start_x = 25
    start_y = 20
    width = 120
    height = 16
    step_y = 18

    for idx, (name, sheet_uuid) in enumerate(sheets):
        y = start_y + (idx * step_y)
        lines.extend(
            [
                f"  (sheet (at {start_x} {y}) (size {width} {height})",
                "    (stroke (width 0) (type solid) (color 0 0 0 0))",
                "    (fill (color 0 0 0 0))",
                f"    (uuid {sheet_uuid})",
                f'    (property "Sheet name" "{name}" (at {start_x} {y - 1.5} 0)',
                "      (effects (font (size 1.27 1.27)) (justify left bottom))",
                "    )",
                f'    (property "Sheet file" "{name}.kicad_sch" (at {start_x} {y + height + 1.5} 0)',
                "      (effects (font (size 1.27 1.27)) (justify left top))",
                "    )",
                "  )",
            ]
        )

    lines.extend(["  (sheet_instances", '    (path "/" (page "1"))'])
    for page, (_, sheet_uuid) in enumerate(sheets, start=2):
        lines.append(f'    (path "/{sheet_uuid}" (page "{page}"))')
    lines.extend(["  )", "  (symbol_instances)", ")"])
    return "\n".join(lines) + "\n"


def _project_file() -> str:
    return """{
  \"board\": {
    \"3dviewports\": [],
    \"design_settings\": {
      \"defaults\": {
        \"board_outline_line_width\": 0.1,
        \"copper_line_width\": 0.2,
        \"copper_text_size_h\": 1.5,
        \"copper_text_size_v\": 1.5,
        \"copper_text_thickness\": 0.3,
        \"other_line_width\": 0.1,
        \"silk_line_width\": 0.12,
        \"silk_text_size_h\": 1,
        \"silk_text_size_v\": 1,
        \"silk_text_thickness\": 0.15
      }
    }
  },
  \"boards\": [],
  \"cvpcb\": {
    \"equivalence_files\": []
  },
  \"libraries\": {
    \"pinned_footprint_libs\": [],
    \"pinned_symbol_libs\": []
  },
  \"meta\": {
    \"filename\": \"examples.kicad_pro\",
    \"version\": 1
  },
  \"schematic\": {
    \"legacy_lib_dir\": \"\",
    \"legacy_lib_list\": [],
    \"meta\": {
      \"version\": 1
    }
  },
  \"text_variables\": {}
}
"""


def main() -> None:
    KICAD_DIR.mkdir(parents=True, exist_ok=True)
    NGSPICE_DIR.mkdir(parents=True, exist_ok=True)

    specs = all_examples()
    for spec in specs:
        (KICAD_DIR / f"{spec.name}.kicad_sch").write_text(export_kicad_schematic(spec), encoding="utf-8")
        (NGSPICE_DIR / f"{spec.name}.cir").write_text(export_ngspice_netlist(spec), encoding="utf-8")
        print(f"generated: {spec.name}")

    example_names = [spec.name for spec in specs]
    (KICAD_DIR / f"{PROJECT_NAME}.kicad_sch").write_text(
        _aggregate_schematic(example_names),
        encoding="utf-8",
    )
    (KICAD_DIR / f"{PROJECT_NAME}.kicad_pro").write_text(_project_file(), encoding="utf-8")
    print(f"generated: {PROJECT_NAME}.kicad_pro")


if __name__ == "__main__":
    main()
