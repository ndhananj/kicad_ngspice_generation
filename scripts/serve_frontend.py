"""Serve the static Editorial Circuitry frontend for local exploration."""

from __future__ import annotations

import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT = 8000


class CacheFriendlyHandler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main() -> None:
    handler = functools.partial(CacheFriendlyHandler, directory=str(ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", PORT), handler)
    print(f"Serving Editorial Circuitry frontend at http://127.0.0.1:{PORT}/frontend/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
