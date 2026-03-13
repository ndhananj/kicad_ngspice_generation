from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DEFAULT_KICAD_SYMBOL_DIR = Path("/usr/share/kicad/symbols")
ASSET_SYMBOL_DIR = Path(__file__).resolve().parent / "assets"

PROJECT_LIB_SYMBOLS: tuple[tuple[str, str], ...] = (
    ("pspice.kicad_sym", "VSOURCE"),
    ("pspice.kicad_sym", "ISOURCE"),
    ("pspice.kicad_sym", "R"),
    ("pspice.kicad_sym", "CAP"),
    ("pspice.kicad_sym", "INDUCTOR"),
    ("pspice.kicad_sym", "DIODE"),
    ("examples.kicad_sym", "QNPN"),
    ("pspice.kicad_sym", "MNMOS"),
    ("pspice.kicad_sym", "MPMOS"),
    ("pspice.kicad_sym", "OPAMP"),
    ("power.kicad_sym", "GND"),
    ("power.kicad_sym", "VCC"),
)

PROJECT_LIB_SOURCES = {symbol_name: src_file for src_file, symbol_name in PROJECT_LIB_SYMBOLS}


def kicad_symbol_dir() -> Path:
    return Path(os.environ.get("KICAD_SYMBOL_DIR", str(DEFAULT_KICAD_SYMBOL_DIR)))


def extract_symbol_block(lib_path: Path, symbol_name: str) -> str:
    text = lib_path.read_text(encoding="utf-8")
    return extract_symbol_block_from_text(text, symbol_name, source=str(lib_path))


def extract_project_symbol_block(symbol_name: str) -> str:
    return extract_project_symbol_block_from_dir(kicad_symbol_dir(), symbol_name)


def extract_symbol_block_from_text(text: str, symbol_name: str, *, source: str = "<memory>") -> str:
    needle = f'(symbol "{symbol_name}"'
    start = text.find(needle)
    if start < 0:
        raise RuntimeError(f"symbol '{symbol_name}' not found in {source}")

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
        raise RuntimeError(f"failed to parse symbol block '{symbol_name}' in {source}")
    return text[start:end]


@lru_cache(maxsize=8)
def project_symbol_pins(symbol_dir: str | None = None) -> dict[str, dict[str, KiCadLibPin]]:
    resolved_dir = Path(symbol_dir) if symbol_dir is not None else kicad_symbol_dir()
    symbols: dict[str, dict[str, KiCadLibPin]] = {}
    for symbol_name in PROJECT_LIB_SOURCES:
        block = extract_project_symbol_block_from_dir(resolved_dir, symbol_name)
        pins: dict[str, KiCadLibPin] = {}
        for match in re.finditer(
            r'\(pin\s+\w+\s+\w+\s+\(at\s+([-0-9.]+)\s+([-0-9.]+)\s+[-0-9.]+\).*?\n\s*\(name\s+"([^"]+)".*?\n\s*\(number\s+"([^"]+)"',
            block,
            re.S,
        ):
            pin = KiCadLibPin(
                number=match.group(4),
                name=match.group(3),
                x=float(match.group(1)),
                y=float(match.group(2)),
            )
            pins[pin.number] = pin
        symbols[symbol_name] = pins
    return symbols


def extract_project_symbol_block_from_dir(symbol_dir: Path, symbol_name: str) -> str:
    src_file = PROJECT_LIB_SOURCES.get(symbol_name)
    if src_file is None:
        raise RuntimeError(f"symbol '{symbol_name}' is not configured in PROJECT_LIB_SYMBOLS")
    candidate = symbol_dir / src_file
    if not candidate.exists():
        candidate = ASSET_SYMBOL_DIR / src_file
    return extract_symbol_block(candidate, symbol_name)


@dataclass(frozen=True, slots=True)
class KiCadLibPin:
    number: str
    name: str
    x: float
    y: float
