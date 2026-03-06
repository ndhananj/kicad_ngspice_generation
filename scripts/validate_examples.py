from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


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
        assert text.count("  (wire ") == 3, "unexpected wire count in rc_lowpass"


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
    for kicad in (ROOT / "examples" / "generated" / "kicad").glob("*.kicad_sch"):
        validate_kicad(kicad)
        _kicad_cli_parse(kicad)
    for cir in (ROOT / "examples" / "generated" / "ngspice").glob("*.cir"):
        validate_ngspice(cir)
    print("all generated examples passed structural + kicad-cli validation")


if __name__ == "__main__":
    main()
