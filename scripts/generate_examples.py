from __future__ import annotations

from datetime import date
import os
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
KICAD_SYMBOL_DIR = Path(os.environ.get("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols"))
PROJECT_LIB_SYMBOLS = (
    ("pspice.kicad_sym", "VSOURCE"),
    ("pspice.kicad_sym", "ISOURCE"),
    ("pspice.kicad_sym", "R"),
    ("pspice.kicad_sym", "CAP"),
    ("pspice.kicad_sym", "INDUCTOR"),
    ("pspice.kicad_sym", "DIODE"),
    ("pspice.kicad_sym", "QNPN"),
    ("pspice.kicad_sym", "MNMOS"),
    ("pspice.kicad_sym", "MPMOS"),
    ("pspice.kicad_sym", "OPAMP"),
    ("power.kicad_sym", "GND"),
    ("power.kicad_sym", "VCC"),
)


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
        "  (title_block",
        '    (title "mixedsig2cad examples")',
        f'    (date "{date.today().isoformat()}")',
        '    (comment 1 "Example sheet index")',
        "  )",
        "  (lib_symbols)",
    ]

    start_x = 25
    start_y = 24
    width = 78
    height = 14
    step_y = 18
    col_gap = 20
    rows_per_col = 9

    for idx, (name, sheet_uuid) in enumerate(sheets):
        col = idx // rows_per_col
        row = idx % rows_per_col
        x = start_x + col * (width + col_gap)
        y = start_y + (row * step_y)
        lines.extend(
            [
                f"  (sheet (at {x} {y}) (size {width} {height})",
                "    (stroke (width 0) (type solid) (color 0 0 0 0))",
                "    (fill (color 0 0 0 0))",
                f"    (uuid {sheet_uuid})",
                f'    (property "Sheet name" "{name}" (at {x} {y - 1.5} 0)',
                "      (effects (font (size 1.27 1.27)) (justify left bottom))",
                "    )",
                f'    (property "Sheet file" "{name}.kicad_sch" (at {x} {y + height + 1.5} 0)',
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
    \"pinned_symbol_libs\": [
      \"examples\"
    ]
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


def _project_symbol_library_file() -> str:
    lines = [
        "(kicad_symbol_lib",
        "  (version 20231120)",
        '  (generator "mixedsig2cad")',
    ]
    for src_file, symbol_name in PROJECT_LIB_SYMBOLS:
        block = _extract_symbol_block(KICAD_SYMBOL_DIR / src_file, symbol_name)
        for row in block.splitlines():
            lines.append(f"  {row}")
    lines.append(")")
    return "\n".join(lines) + "\n"


def _extract_symbol_block(lib_path: Path, symbol_name: str) -> str:
    text = lib_path.read_text(encoding="utf-8")
    needle = f'(symbol "{symbol_name}"'
    start = text.find(needle)
    if start < 0:
        raise RuntimeError(f"symbol '{symbol_name}' not found in {lib_path}")

    depth = 0
    end = -1
    for idx in range(start, len(text)):
        ch = text[idx]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                end = idx + 1
                break
    if end < 0:
        raise RuntimeError(f"failed to parse symbol block '{symbol_name}' in {lib_path}")
    return text[start:end]


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
    project_path = KICAD_DIR / f"{PROJECT_NAME}.kicad_pro"
    if not project_path.exists() or os.environ.get("OVERWRITE_KICAD_PROJECT", "").strip() == "1":
        project_path.write_text(_project_file(), encoding="utf-8")
    else:
        print(f"preserved existing project file: {project_path.name}")
    (KICAD_DIR / f"{PROJECT_NAME}.kicad_sym").write_text(_project_symbol_library_file(), encoding="utf-8")
    print(f"generated: {PROJECT_NAME}.kicad_pro")


if __name__ == "__main__":
    main()
