from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def export_schematic_svg(schematic_path: str | Path, output_dir: str | Path, *, kicad_cli: str | None = None) -> Path:
    return _export_schematic_plot("svg", schematic_path, output_dir, kicad_cli=kicad_cli)


def export_schematic_pdf(schematic_path: str | Path, output_path: str | Path, *, kicad_cli: str | None = None) -> Path:
    output = Path(output_path)
    destination = output.parent
    destination.mkdir(parents=True, exist_ok=True)
    return _export_schematic_plot("pdf", schematic_path, output, kicad_cli=kicad_cli)


def _export_schematic_plot(
    fmt: str,
    schematic_path: str | Path,
    output_target: str | Path,
    *,
    kicad_cli: str | None = None,
) -> Path:
    schematic = Path(schematic_path)
    output = Path(output_target)
    cli = kicad_cli or shutil.which("kicad-cli")
    if not cli:
        raise AssertionError(f"kicad-cli is required for schematic {fmt.upper()} export")

    destination = output if fmt == "svg" else output.parent
    destination.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["HOME"] = str(destination)
    env["XDG_CONFIG_HOME"] = str(destination / ".config")
    result = subprocess.run(
        [
            cli,
            "sch",
            "export",
            fmt,
            "--output",
            str(output),
            str(schematic),
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"kicad-cli {fmt.upper()} export failed for {schematic}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    artifact_path = destination / f"{schematic.stem}.{fmt}" if fmt == "svg" else output
    if not artifact_path.exists():
        raise AssertionError(f"expected {fmt.upper()} output for {schematic}")
    return artifact_path
