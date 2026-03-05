from __future__ import annotations

from pathlib import Path
import sys

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
    for cir in (ROOT / "examples" / "generated" / "ngspice").glob("*.cir"):
        validate_ngspice(cir)
    print("all generated examples passed structural validation")


if __name__ == "__main__":
    main()
