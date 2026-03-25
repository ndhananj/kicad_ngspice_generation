from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from frontend_fixture_contract import build_sanitized_fixture_corpus


SOURCE_FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "frontend_corpus"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=4173)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="frontend_fixture_corpus_") as temp_dir:
        fixture_root = build_sanitized_fixture_corpus(SOURCE_FIXTURE_ROOT, Path(temp_dir) / "frontend_corpus")
        command = [
            sys.executable,
            str(ROOT / "scripts" / "serve_frontend.py"),
            "--port",
            str(args.port),
            "--fixture-root",
            str(fixture_root),
        ]
        raise SystemExit(subprocess.run(command, check=False).returncode)


if __name__ == "__main__":
    main()
