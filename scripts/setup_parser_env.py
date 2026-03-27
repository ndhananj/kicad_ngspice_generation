from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mixedsig2cad.dev_env import BOOTSTRAP_COMMAND, frontend_runtime_issues, missing_python_modules


def main() -> int:
    missing_modules = missing_python_modules()
    missing_tools: list[str] = []
    if "pytesseract" not in missing_modules and shutil.which("tesseract") is None:
        missing_tools.append("tesseract")
    if shutil.which("pdflatex") is None:
        missing_tools.append("pdflatex")
    if shutil.which("kicad-cli") is None:
        missing_tools.append("kicad-cli")
    missing_tools.extend(frontend_runtime_issues())
    if missing_modules or missing_tools:
        for name in missing_modules:
            print(f"missing python module: {name}")
        for name in missing_tools:
            print(f"missing external tool: {name}")
        print(
            "Bootstrap the local toolchain with "
            f"`{BOOTSTRAP_COMMAND}` and rerun `python3 scripts/setup_parser_env.py`."
        )
        return 1
    print("Parser and validation environment looks ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
