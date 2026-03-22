from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mixedsig2cad import check_validation_runtime_dependencies, refresh_rendered_tex_symbol_goldens


def main() -> None:
    check_validation_runtime_dependencies(require_tex=True, require_pdf_raster=True)
    written = refresh_rendered_tex_symbol_goldens()
    for path in written:
        print(f"wrote: {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
