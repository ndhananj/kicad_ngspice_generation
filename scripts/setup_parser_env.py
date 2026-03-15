from __future__ import annotations

import importlib.util
import shutil
import sys


PYTHON_MODULES = (
    "numpy",
    "PIL",
    "cv2",
    "fitz",
    "svgpathtools",
    "segment_anything",
    "pytesseract",
)


def main() -> int:
    missing_modules = [name for name in PYTHON_MODULES if importlib.util.find_spec(name) is None]
    missing_tools: list[str] = []
    if importlib.util.find_spec("pytesseract") is not None and shutil.which("tesseract") is None:
        missing_tools.append("tesseract")
    if shutil.which("pdflatex") is None:
        missing_tools.append("pdflatex")
    if shutil.which("kicad-cli") is None:
        missing_tools.append("kicad-cli")
    if missing_modules or missing_tools:
        for name in missing_modules:
            print(f"missing python module: {name}")
        for name in missing_tools:
            print(f"missing external tool: {name}")
        print(
            "Install Python dependencies with `pip install -r requirements.txt`, "
            "then install the external tools `pdflatex`, `kicad-cli`, and `tesseract`."
        )
        return 1
    print("Parser and validation environment looks ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
