from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import urlopen

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PORT = 4174


def _wait_for_server(url: str, *, timeout_seconds: float = 20.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=1.0) as response:
                if response.status == 200:
                    return
        except URLError:
            time.sleep(0.1)
    raise TimeoutError(f"timed out waiting for {url}")


def _clip_rect(rect: dict[str, float], width: int, height: int) -> tuple[int, int, int, int]:
    left = max(int(round(rect["left"])), 0)
    top = max(int(round(rect["top"])), 0)
    right = min(int(round(rect["right"])), width)
    bottom = min(int(round(rect["bottom"])), height)
    if right <= left or bottom <= top:
        raise ValueError(f"rect is outside captured viewport: {rect}")
    return left, top, right, bottom


def _extract_visible_editor_crop(image: np.ndarray, pane_rect: dict[str, float]) -> np.ndarray:
    height, width = image.shape[:2]
    left, top, right, bottom = _clip_rect(pane_rect, width, height)
    return image[top:bottom, left:right].copy()


def _compute_signal_rows(crop: np.ndarray) -> tuple[np.ndarray, list[int]]:
    rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    channel_max = rgb.max(axis=2)
    channel_min = rgb.min(axis=2)
    color_span = channel_max.astype(np.int16) - channel_min.astype(np.int16)
    mask = (channel_max >= 90) & (color_span >= 28)
    rows = mask.sum(axis=1)
    signal_rows = [index for index, count in enumerate(rows.tolist()) if count >= 12]
    return mask.astype(np.uint8) * 255, signal_rows


def _validate_metrics(metrics: dict[str, object], crop: np.ndarray, signal_rows: list[int]) -> list[str]:
    failures: list[str] = []
    viewport_height = float(metrics["viewport"]["height"])
    pane_rect = metrics["paneRect"]
    pane_height = float(pane_rect["height"])
    visible_component = metrics.get("visibleComponent")

    if int(metrics.get("exampleCount", 0)) < 8:
        failures.append("expected the live generated corpus to expose all checked-in examples")
    if int(metrics.get("wireCount", 0)) <= 0:
        failures.append("expected rendered editor wires in the live app")
    if not metrics.get("editorEmptyStateHidden"):
        failures.append("editor empty state is visible on initial load")
    if pane_height > viewport_height * 0.82:
        failures.append(
            f"editor pane height {pane_height:.1f}px exceeds 82% of viewport height {viewport_height:.1f}px"
        )
    if not visible_component:
        failures.append("no visible component bounding box was reported by the browser")
    else:
        component_top = float(visible_component["rect"]["top"])
        pane_top = float(pane_rect["top"])
        if component_top > pane_top + pane_height * 0.6:
            failures.append(
                f"first visible component starts too low in the pane ({component_top - pane_top:.1f}px from pane top)"
            )

    if crop.size == 0:
        failures.append("visible editor crop is empty")
    elif not signal_rows:
        failures.append("no bright editor signal was detected in the visible editor crop")
    else:
        first_signal = signal_rows[0]
        if first_signal > crop.shape[0] * 0.6:
            failures.append(
                f"first screenshot signal row {first_signal}px is below 60% of visible pane height {crop.shape[0]}px"
            )

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()

    if shutil.which("node") is None:
        raise RuntimeError("node is required for frontend visibility validation")

    output_dir = args.output_dir.resolve() if args.output_dir else Path(tempfile.mkdtemp(prefix="frontend_visibility_"))
    output_dir.mkdir(parents=True, exist_ok=True)

    screenshot_path = output_dir / "frontend-visible-viewport.png"
    crop_path = output_dir / "frontend-editor-crop.png"
    mask_path = output_dir / "frontend-editor-mask.png"
    metrics_path = output_dir / "frontend-editor-metrics.json"

    env = os.environ.copy()
    env.setdefault("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH", "/usr/bin/google-chrome")

    server = subprocess.Popen(
        [sys.executable, str(ROOT / "scripts" / "serve_frontend.py"), "--port", str(args.port)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        _wait_for_server(f"http://127.0.0.1:{args.port}/frontend/api/examples.json")
        capture = subprocess.run(
            [
                "node",
                str(ROOT / "scripts" / "capture_frontend_state.js"),
                "--url",
                f"http://127.0.0.1:{args.port}/frontend/?test=1",
                "--screenshot",
                str(screenshot_path),
            ],
            cwd=ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)

    metrics = json.loads(capture.stdout.strip())
    image = cv2.imread(str(screenshot_path))
    if image is None:
        raise RuntimeError(f"failed to read screenshot at {screenshot_path}")

    crop = _extract_visible_editor_crop(image, metrics["paneRect"])
    mask, signal_rows = _compute_signal_rows(crop)
    failures = _validate_metrics(metrics, crop, signal_rows)

    cv2.imwrite(str(crop_path), crop)
    cv2.imwrite(str(mask_path), mask)
    metrics_with_analysis = {
        **metrics,
        "analysis": {
            "signalRowCount": len(signal_rows),
            "firstSignalRow": signal_rows[0] if signal_rows else None,
            "outputDir": str(output_dir),
        },
    }
    metrics_path.write_text(json.dumps(metrics_with_analysis, indent=2) + "\n", encoding="utf-8")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        print(f"Saved debug artifacts under {output_dir}", file=sys.stderr)
        return 1

    print(json.dumps(metrics_with_analysis, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
