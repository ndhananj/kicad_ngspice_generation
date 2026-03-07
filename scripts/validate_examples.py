from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from examples.specs.catalog import all_examples
from mixedsig2cad import (
    build_schematic_geometry,
    build_schematic_intent,
    compare_geometries,
    compare_topologies,
    derive_topology_layout,
    import_kicad_schematic,
    project_geometry_to_kicad,
    roundtrip_kicad_schematic,
)
from mixedsig2cad.geometry import PAGE_BOTTOM, PAGE_LEFT, PAGE_RIGHT, PAGE_TOP


def _balanced_parentheses(text: str) -> bool:
    depth = 0
    in_string = False
    escape = False
    for ch in text:
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0 and not in_string


def validate_kicad(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    assert "(kicad_sch" in text, f"missing schematic header in {path}"
    assert "(symbol_instances" in text, f"missing symbol_instances in {path}"
    assert _balanced_parentheses(text), f"unbalanced parentheses in {path}"
    assert "examples:" not in text, f"unexpected external project symbol reference in {path}"
    assert "(hide yes)" not in text, f"legacy '(hide yes)' found in {path}"
    assert "(hide))" not in text, f"invalid standalone '(hide)' property child found in {path}"
    if '(property "Footprint"' in text or '(property "Datasheet"' in text:
        assert "effects (font (size 1.27 1.27)) hide" in text, (
            f"expected hidden property syntax '(effects ... hide)' not found in {path}"
        )
    if path.name == "rc_lowpass.kicad_sch":
        assert text.count('(symbol (lib_id "GND")') == 2, "expected local ground symbols in rc_lowpass"
        assert '(label "vin"' not in text and '(label "vout"' not in text, "unexpected compensating net labels in rc_lowpass"
        assert text.count("  (wire ") >= 4, "expected explicit node-driven connections in rc_lowpass"
    if path.name == "rc_highpass.kicad_sch":
        assert text.count('(symbol (lib_id "GND")') == 2, "expected local ground symbols in rc_highpass"
        assert text.count("  (wire ") >= 5, "expected explicit node-driven connections in rc_highpass"
    if path.name == "rlc_bandpass.kicad_sch":
        assert text.count("  (junction ") >= 1, "expected an explicit branch junction in rlc_bandpass"
        assert "(wire (pts (xy 100.00 108.00) (xy 100.00 98.00))" not in text, (
            "unexpected body-crossing vertical route remains in rlc_bandpass"
        )
    report = roundtrip_kicad_schematic(path)
    assert report.exact_roundtrip, f"structured KiCad roundtrip failed for {path}: {report}"


def validate_geometry() -> None:
    for spec in all_examples():
        intent = build_schematic_intent(spec)
        geometry = build_schematic_geometry(intent)
        project_geometry_to_kicad(geometry)
        bounds = _geometry_bounds(geometry)
        assert bounds is not None, f"missing geometry bounds for {spec.name}"
        assert bounds.left >= PAGE_LEFT, f"{spec.name} extends past left page bound"
        assert bounds.top >= PAGE_TOP, f"{spec.name} extends past top page bound"
        assert bounds.right <= PAGE_RIGHT, f"{spec.name} extends past right page bound"
        assert bounds.bottom <= PAGE_BOTTOM, f"{spec.name} extends past bottom page bound"
        kicad_path = ROOT / "examples" / "generated" / "kicad" / f"{spec.name}.kicad_sch"
        if kicad_path.exists():
            imported = import_kicad_schematic(kicad_path)
            geometry_report = compare_geometries(geometry, imported)
            topology_report = compare_topologies(derive_topology_layout(geometry), derive_topology_layout(imported))
            assert geometry_report.within_tolerance, f"geometry import mismatch for {spec.name}: {geometry_report}"
            assert topology_report.equivalent, f"topology import mismatch for {spec.name}: {topology_report}"


def _geometry_bounds(geometry) -> tuple[float, float, float, float] | None:
    xs: list[float] = []
    ys: list[float] = []
    for shape in geometry.shapes:
        xs.extend([shape.body_box.left, shape.body_box.right])
        ys.extend([shape.body_box.top, shape.body_box.bottom])
    for wire in geometry.wires:
        for point in wire.points:
            xs.append(point.x)
            ys.append(point.y)
    if not xs or not ys:
        return None
    return type("Bounds", (), {"left": min(xs), "top": min(ys), "right": max(xs), "bottom": max(ys)})()


def _kicad_cli_parse(path: Path) -> None:
    kicad_cli = shutil.which("kicad-cli")
    if not kicad_cli:
        return

    with tempfile.TemporaryDirectory(prefix="kicad-cli-") as tmp_home:
        tmp_home_path = Path(tmp_home)
        output = tmp_home_path / "out.net"
        env = dict(os.environ)
        env["HOME"] = str(tmp_home_path)
        env["XDG_CONFIG_HOME"] = str(tmp_home_path / ".config")
        result = subprocess.run(
            [
                kicad_cli,
                "sch",
                "export",
                "netlist",
                "--format",
                "kicadsexpr",
                "--output",
                str(output),
                str(path),
            ],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0, (
            f"kicad-cli parse/export failed for {path}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )


def validate_ngspice(path: Path) -> None:
    text = path.read_text(encoding="utf-8").strip().splitlines()
    assert text[0].startswith("*"), f"missing title in {path}"
    assert text[-1] == ".end", f"missing .end in {path}"
    in_control = False
    for line in text:
        stripped = line.strip()
        if stripped == ".control":
            in_control = True
            continue
        if stripped == ".endc":
            in_control = False
            continue
        if in_control or not stripped or stripped.startswith(("*", ".", "+")):
            continue
        tokens = stripped.split()
        assert len(tokens) >= 3, f"invalid element line '{line}' in {path}"


def main() -> None:
    validate_geometry()
    for kicad in (ROOT / "examples" / "generated" / "kicad").glob("*.kicad_sch"):
        validate_kicad(kicad)
        _kicad_cli_parse(kicad)
    for cir in (ROOT / "examples" / "generated" / "ngspice").glob("*.cir"):
        validate_ngspice(cir)
    print("all generated examples passed structural + kicad-cli validation")


if __name__ == "__main__":
    main()
