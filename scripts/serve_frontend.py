"""Serve the static circuit editor frontend for local exploration and testing."""

from __future__ import annotations

import argparse
import functools
import json
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PORT = 8000
CATALOG_PATH = ROOT / "frontend" / "example_catalog.json"
FIXTURE_PREFIX = "/_frontend_fixtures"

ARTIFACT_RELATIVE_PATHS = {
    "svg": "examples/generated/svg/{example_id}.svg",
    "pdf": "examples/generated/svg/{example_id}.pdf",
    "kicad": "examples/generated/kicad/{example_id}.kicad_sch",
    "ngspice": "examples/generated/ngspice/{example_id}.cir",
    "reportTex": "examples/generated/tex/{example_id}.tex",
    "circuitikzTex": "examples/generated/tex/{example_id}.circuitikz.tex",
    "reportPdf": "examples/generated/tex/{example_id}.pdf",
}


def load_catalog() -> list[dict[str, object]]:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def build_artifact(base_root: Path, url_prefix: str, relative_template: str, example_id: str) -> dict[str, object]:
    relative_path = Path(relative_template.format(example_id=example_id))
    return {
        "url": f"{url_prefix}/{relative_path.as_posix()}" if url_prefix else f"/{relative_path.as_posix()}",
        "available": (base_root / relative_path).exists(),
    }


def build_example_payload(base_root: Path, url_prefix: str = "") -> list[dict[str, object]]:
    payload = []
    for entry in load_catalog():
        example_id = str(entry["id"])
        artifacts = {
            key: build_artifact(base_root, url_prefix, template, example_id)
            for key, template in ARTIFACT_RELATIVE_PATHS.items()
        }
        if any(artifact["available"] for artifact in artifacts.values()):
            payload.append({**entry, "artifacts": artifacts})
    return payload


class CacheFriendlyHandler(SimpleHTTPRequestHandler):
    fixture_root: Path | None = None
    catalog_payload: bytes = b"[]"

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self) -> None:
        request_path = urlsplit(self.path).path
        if request_path == "/frontend/api/examples.json":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(self.catalog_payload)))
            self.end_headers()
            self.wfile.write(self.catalog_payload)
            return
        super().do_GET()

    def translate_path(self, path: str) -> str:
        request_path = urlsplit(path).path
        if self.fixture_root and request_path.startswith(f"{FIXTURE_PREFIX}/"):
            relative = request_path.removeprefix(f"{FIXTURE_PREFIX}/")
            return str((self.fixture_root / relative).resolve())
        return super().translate_path(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--fixture-root",
        type=Path,
        help="Serve generated examples from a fixture corpus instead of the repository examples directory.",
    )
    args = parser.parse_args()

    fixture_root = args.fixture_root.resolve() if args.fixture_root else None
    content_root = fixture_root if fixture_root else ROOT
    url_prefix = FIXTURE_PREFIX if fixture_root else ""

    class FrontendHandler(CacheFriendlyHandler):
        pass

    FrontendHandler.fixture_root = fixture_root
    FrontendHandler.catalog_payload = json.dumps(
        build_example_payload(content_root, url_prefix),
        indent=2,
    ).encode("utf-8")

    handler = functools.partial(FrontendHandler, directory=str(ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(f"Serving circuit editor frontend at http://127.0.0.1:{args.port}/frontend/")
    if fixture_root:
        print(f"Using fixture corpus from {fixture_root}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
