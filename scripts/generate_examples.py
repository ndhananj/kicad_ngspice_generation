from __future__ import annotations

from datetime import date
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from examples.specs.catalog import all_examples
from mixedsig2cad import (
    build_example_report_bundle,
    build_examples_master_bundle,
    export_circuitikz,
    export_kicad_schematic,
    export_ngspice_netlist,
    export_schematic_pdf,
    export_schematic_svg,
)
from mixedsig2cad.kicad_symbols import PROJECT_LIB_SYMBOLS, extract_project_symbol_block

KICAD_DIR = ROOT / "examples" / "generated" / "kicad"
NGSPICE_DIR = ROOT / "examples" / "generated" / "ngspice"
TEX_DIR = ROOT / "examples" / "generated" / "tex"
SVG_DIR = ROOT / "examples" / "generated" / "svg"
PROJECT_NAME = "examples"


def _compile_report_pdf(path: Path) -> None:
    pdflatex = shutil.which("pdflatex")
    if not pdflatex:
        print(f"skipped report PDF build for {path.name}: pdflatex not installed")
        return

    with tempfile.TemporaryDirectory(prefix="mixedsig2cad-pdf-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        result = subprocess.run(
            [
                pdflatex,
                "-shell-escape",
                "-interaction=nonstopmode",
                "-halt-on-error",
                f"-output-directory={tmp_path}",
                path.name,
            ],
            cwd=path.parent,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"pdflatex failed for {path}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
        output_pdf = tmp_path / f"{path.stem}.pdf"
        if not output_pdf.exists():
            raise RuntimeError(f"pdflatex did not produce {output_pdf.name} for {path}")
        (path.parent / output_pdf.name).write_bytes(output_pdf.read_bytes())


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
    for _, symbol_name in PROJECT_LIB_SYMBOLS:
        block = extract_project_symbol_block(symbol_name)
        for row in block.splitlines():
            lines.append(f"  {row}")
    lines.append(")")
    return "\n".join(lines) + "\n"


def main() -> None:
    KICAD_DIR.mkdir(parents=True, exist_ok=True)
    NGSPICE_DIR.mkdir(parents=True, exist_ok=True)
    TEX_DIR.mkdir(parents=True, exist_ok=True)
    SVG_DIR.mkdir(parents=True, exist_ok=True)

    specs = all_examples()
    for spec in specs:
        schematic_path = KICAD_DIR / f"{spec.name}.kicad_sch"
        schematic_path.write_text(export_kicad_schematic(spec), encoding="utf-8")
        export_schematic_svg(schematic_path, SVG_DIR)
        export_schematic_pdf(schematic_path, SVG_DIR / f"{spec.name}.pdf")
        (NGSPICE_DIR / f"{spec.name}.cir").write_text(export_ngspice_netlist(spec), encoding="utf-8")
        bundle = build_example_report_bundle(spec)
        for file in bundle.files:
            target = TEX_DIR / file.path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(file.content, encoding="utf-8")
        legacy_readable = TEX_DIR / "fragments" / spec.name / "readable.tex"
        if legacy_readable.exists():
            legacy_readable.unlink()
        (TEX_DIR / f"{spec.name}.circuitikz.tex").write_text(export_circuitikz(spec), encoding="utf-8")
        _compile_report_pdf(TEX_DIR / f"{spec.name}.tex")
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
    master_bundle = build_examples_master_bundle(specs)
    for file in master_bundle.files:
        target = TEX_DIR / file.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(file.content, encoding="utf-8")
    _compile_report_pdf(TEX_DIR / f"{PROJECT_NAME}.tex")
    print(f"generated: {PROJECT_NAME}.kicad_pro")


if __name__ == "__main__":
    main()
