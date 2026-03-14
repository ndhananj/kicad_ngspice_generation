from __future__ import annotations

import importlib.util
import shutil
import sys


PYTHON_MODULES = (
    "numpy",
    "PIL",
    "cv2",
    "svgpathtools",
    "segment_anything",
    "pytesseract",
)


def main() -> int:
    missing_modules = [name for name in PYTHON_MODULES if importlib.util.find_spec(name) is None]
    missing_tools: list[str] = []
    if importlib.util.find_spec("pytesseract") is not None and shutil.which("tesseract") is None:
        missing_tools.append("tesseract")
    if missing_modules or missing_tools:
        for name in missing_modules:
            print(f"missing python module: {name}")
        for name in missing_tools:
            print(f"missing external tool: {name}")
        print("Install dependencies with `pip install -r requirements.txt` and ensure external OCR tools are available.")
        return 1
    print("Parser environment looks ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
