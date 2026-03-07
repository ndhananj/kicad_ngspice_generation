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
    build_schematic_intent,
    compare_geometries,
    compile_schematic,
    compare_topologies,
    derive_topology_layout,
    extract_geometry_from_image,
    import_kicad_schematic,
    roundtrip_kicad_schematic,
    validate_kicad_connectivity,
    validate_rendered_kicad_symbols,
)
from mixedsig2cad.geometry import PAGE_BOTTOM, PAGE_LEFT, PAGE_RIGHT, PAGE_TOP
from mixedsig2cad.importers.raster_extract import observe_kicad_svg
from mixedsig2cad.projections.kicad import project_geometry_to_kicad
from mixedsig2cad.symbols import KICAD_SYMBOLS

EXPECTED_CONNECTIVITY_PASS = {
    "rc_lowpass": True,
    "rc_highpass": True,
    "rlc_bandpass": True,
    "diode_clipper": True,
    "bjt_common_emitter": False,
    "opamp_inverting": True,
    "cmos_inverter": False,
    "schmitt_trigger": False,
}


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
        assert '(label "vin"' in text and '(label "vout"' in text, "expected named signal labels in rc_lowpass"
        assert text.count("  (wire ") >= 4, "expected explicit node-driven connections in rc_lowpass"
    if path.name == "rc_highpass.kicad_sch":
        assert text.count('(symbol (lib_id "GND")') == 2, "expected local ground symbols in rc_highpass"
        assert '(label "vin"' in text and '(label "vmid"' in text, "expected named signal labels in rc_highpass"
        assert text.count("  (wire ") >= 5, "expected explicit node-driven connections in rc_highpass"
    if path.name == "rlc_bandpass.kicad_sch":
        assert text.count("  (junction ") >= 1, "expected an explicit branch junction in rlc_bandpass"
        assert "(wire (pts (xy 100.00 108.00) (xy 100.00 98.00))" not in text, (
            "unexpected body-crossing vertical route remains in rlc_bandpass"
        )
    if path.name == "bjt_common_emitter.kicad_sch":
        assert text.count('(symbol (lib_id "R")') == 5, "expected 5 resistors in canonical common-emitter example"
        assert text.count('(symbol (lib_id "CAP")') == 3, "expected 3 capacitors in canonical common-emitter example"
        assert text.count('(symbol (lib_id "VSOURCE")') == 2, "expected signal and supply sources in canonical common-emitter example"
        assert text.count('(symbol (lib_id "QNPN")') == 1, "expected one NPN transistor in canonical common-emitter example"
        assert text.count("  (junction ") >= 4, "expected explicit stage junctions in canonical common-emitter example"
    report = roundtrip_kicad_schematic(path)
    assert report.exact_roundtrip, f"structured KiCad roundtrip failed for {path}: {report}"
    if path.name == "bjt_common_emitter.kicad_sch":
        _validate_common_emitter_svg_orientation(path)


def validate_connectivity() -> None:
    for spec in all_examples():
        path = ROOT / "examples" / "generated" / "kicad" / f"{spec.name}.kicad_sch"
        report = validate_kicad_connectivity(spec, path)
        expected = EXPECTED_CONNECTIVITY_PASS[spec.name]
        assert report.passed == expected, (
            f"unexpected KiCad connectivity result for {spec.name}: expected passed={expected}, got {report}"
        )


def validate_geometry() -> None:
    for spec in all_examples():
        intent = build_schematic_intent(spec)
        geometry = compile_schematic(intent)
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


def validate_rendered_symbols() -> None:
    results = validate_rendered_kicad_symbols()
    assert results or shutil.which("kicad-cli") is None, "expected rendered symbol validation results when kicad-cli is installed"
    by_shape = {(result.shape, result.orientation): result for result in results}
    for key in KICAD_SYMBOLS:
        if shutil.which("kicad-cli") is None:
            break
        assert key in by_shape, f"missing rendered validation result for symbol mapping {key}"
    if shutil.which("kicad-cli") is not None:
        opamp = by_shape[("opamp", "right")]
        expected = {"plus", "minus", "out", "vplus", "vminus"}
        assert set(opamp.rendered_terminal_sides) == expected, f"missing rendered OPAMP terminals: {opamp.rendered_terminal_sides}"


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


def _export_svg(path: Path, output_dir: Path) -> Path:
    kicad_cli = shutil.which("kicad-cli")
    if not kicad_cli:
        raise AssertionError("kicad-cli is required for SVG orientation validation")
    env = dict(os.environ)
    env["HOME"] = str(output_dir)
    env["XDG_CONFIG_HOME"] = str(output_dir / ".config")
    result = subprocess.run(
        [
            kicad_cli,
            "sch",
            "export",
            "svg",
            "--output",
            str(output_dir),
            str(path),
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, (
        f"kicad-cli SVG export failed for {path}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    svg_path = output_dir / f"{path.stem}.svg"
    assert svg_path.exists(), f"expected SVG output for {path}"
    return svg_path


def _validate_common_emitter_svg_orientation(path: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="kicad-svg-") as tmp_home:
        svg_path = _export_svg(path, Path(tmp_home))
        observation = observe_kicad_svg(svg_path)
        q1 = next((symbol for symbol in observation.symbols if symbol.ref_text == "Q1"), None)
        assert q1 is not None, "expected to observe Q1 in common-emitter SVG"
        assert q1.terminal_hints is not None, "expected transistor terminal hints from SVG observation"
        assert q1.terminal_hints.get("base") == "left", f"expected base-left NPN, got {q1.terminal_hints}"
        assert q1.terminal_hints.get("collector") == "top", f"expected collector-up NPN, got {q1.terminal_hints}"
        assert q1.terminal_hints.get("emitter") == "bottom", f"expected emitter-down NPN, got {q1.terminal_hints}"


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
    validate_rendered_symbols()
    for kicad in (ROOT / "examples" / "generated" / "kicad").glob("*.kicad_sch"):
        validate_kicad(kicad)
        _kicad_cli_parse(kicad)
    validate_connectivity()
    for cir in (ROOT / "examples" / "generated" / "ngspice").glob("*.cir"):
        validate_ngspice(cir)
    print("all generated examples passed structural + kicad-cli validation")


if __name__ == "__main__":
    main()
