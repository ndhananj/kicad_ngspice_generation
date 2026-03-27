from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import urlopen

import cv2
import numpy as np
import pytesseract

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mixedsig2cad.dev_env import find_browser_executable
from mixedsig2cad.importers.hybrid_parser import check_validation_runtime_dependencies

DEFAULT_PORT = 4174


def _resolve_port(preferred_port: int) -> int:
    return preferred_port + (os.getpid() % 200)


def _wait_for_server(url: str, *, timeout_seconds: float = 20.0, process: subprocess.Popen[str] | None = None) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if process is not None and process.poll() is not None:
            output = process.stdout.read() if process.stdout is not None else ""
            raise RuntimeError(f"frontend server exited before becoming ready for {url}\n{output}")
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


def _crop_relative_rect(rect: dict[str, float], pane_rect: dict[str, float]) -> dict[str, float]:
    return {
        "left": rect["left"] - pane_rect["left"],
        "top": rect["top"] - pane_rect["top"],
        "right": rect["right"] - pane_rect["left"],
        "bottom": rect["bottom"] - pane_rect["top"],
        "width": rect["width"],
        "height": rect["height"],
    }


def _rect_overlap(first: dict[str, float], second: dict[str, float]) -> float:
    left = max(first["left"], second["left"])
    top = max(first["top"], second["top"])
    right = min(first["right"], second["right"])
    bottom = min(first["bottom"], second["bottom"])
    if right <= left or bottom <= top:
        return 0.0
    return float((right - left) * (bottom - top))


def _extract_text_mask(crop: np.ndarray) -> np.ndarray:
    rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    channel_max = rgb.max(axis=2)
    channel_min = rgb.min(axis=2)
    color_span = channel_max.astype(np.int16) - channel_min.astype(np.int16)
    bright = channel_max >= 110
    colored = color_span >= 24
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    pale_text = gray >= 150
    mask = ((bright & colored) | pale_text).astype(np.uint8) * 255
    return cv2.medianBlur(mask, 3)


def _rect_has_text_signal(mask: np.ndarray, rect: dict[str, float], *, minimum_pixels: int = 8) -> bool:
    height, width = mask.shape[:2]
    left = max(int(round(rect["left"])), 0)
    top = max(int(round(rect["top"])), 0)
    right = min(int(round(rect["right"])), width)
    bottom = min(int(round(rect["bottom"])), height)
    if right <= left or bottom <= top:
        return False
    region = mask[top:bottom, left:right]
    return int((region > 0).sum()) >= minimum_pixels


def _find_label_overlap_failures(metrics: dict[str, object], text_mask: np.ndarray) -> list[str]:
    failures: list[str] = []
    pane_rect = metrics["paneRect"]
    labels = [
        {
            **entry,
            "cropRect": _crop_relative_rect(entry["rect"], pane_rect),
        }
        for entry in metrics.get("labelMetrics", [])
    ]
    component_bodies = [
        {
            **entry,
            "cropRect": _crop_relative_rect(entry["rect"], pane_rect),
        }
        for entry in metrics.get("bodyMetrics", [])
    ]

    hidden_support_refs = [entry["text"] for entry in labels if entry["text"].startswith("#SUPPORT")]
    if hidden_support_refs:
        failures.append(f"hidden support references are visible in editor labels: {', '.join(hidden_support_refs[:3])}")

    for index, label in enumerate(labels):
        for other in labels[index + 1 :]:
            overlap = _rect_overlap(label["cropRect"], other["cropRect"])
            if overlap >= 6.0:
                failures.append(f"label boxes overlap in screenshot: {label['text']} vs {other['text']}")
                break

    for label in labels:
        if label["role"] == "net_label":
            continue
        for body in component_bodies:
            if body["id"] == label.get("ownerRef"):
                continue
            overlap = _rect_overlap(label["cropRect"], body["cropRect"])
            if overlap >= 6.0:
                failures.append(f"label {label['text']} overlaps component body {body['id']} in screenshot")
                break

    return failures


def _ocr_label_boxes(crop: np.ndarray) -> list[dict[str, object]]:
    data = pytesseract.image_to_data(
        cv2.cvtColor(crop, cv2.COLOR_BGR2RGB),
        output_type=pytesseract.Output.DICT,
        config="--psm 11",
    )
    boxes: list[dict[str, object]] = []
    for index, text in enumerate(data["text"]):
        content = (text or "").strip()
        if not content:
            continue
        try:
            confidence = float(data["conf"][index])
        except (TypeError, ValueError):
            confidence = -1.0
        if confidence < 35.0:
            continue
        left = int(data["left"][index])
        top = int(data["top"][index])
        width = int(data["width"][index])
        height = int(data["height"][index])
        boxes.append(
            {
                "text": content,
                "confidence": confidence,
                "rect": {
                    "left": left,
                    "top": top,
                    "right": left + width,
                    "bottom": top + height,
                    "width": width,
                    "height": height,
                },
            }
        )
    return boxes


def _normalized_text(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9#+-]", "", value).upper()


def _find_ocr_failures(metrics: dict[str, object], crop: np.ndarray) -> tuple[list[str], dict[str, object]]:
    status = check_validation_runtime_dependencies()
    analysis: dict[str, object] = {
        "available": bool(status.ocr_available),
        "expectedVisibleLabels": [entry["text"] for entry in metrics.get("labelMetrics", [])],
        "recognizedLabels": [],
    }
    if not status.ocr_available:
        analysis["reason"] = "OCR dependency unavailable"
        return [], analysis

    boxes = _ocr_label_boxes(crop)
    analysis["recognizedLabels"] = [
        {
            "text": entry["text"],
            "confidence": entry["confidence"],
        }
        for entry in boxes
    ]
    expected = [_normalized_text(entry["text"]) for entry in metrics.get("labelMetrics", [])]
    recognized = [_normalized_text(entry["text"]) for entry in boxes]
    failures: list[str] = []

    support_hits = [entry["text"] for entry in boxes if entry["text"].startswith("#SUPPORT")]
    if support_hits:
        failures.append(f"OCR detected hidden support references in the editor crop: {', '.join(support_hits[:3])}")

    expected_counts: dict[str, int] = {}
    for label in expected:
        if label:
            expected_counts[label] = expected_counts.get(label, 0) + 1
    recognized_counts: dict[str, int] = {}
    for label in recognized:
        if label:
            recognized_counts[label] = recognized_counts.get(label, 0) + 1

    for label, count in expected_counts.items():
        seen = recognized_counts.get(label, 0)
        if seen > count:
            failures.append(f"OCR recognized {seen} copies of {label}, expected at most {count}")

    return failures, analysis


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
    port = _resolve_port(args.port)

    screenshot_path = output_dir / "frontend-visible-viewport.png"
    crop_path = output_dir / "frontend-editor-crop.png"
    mask_path = output_dir / "frontend-editor-mask.png"
    metrics_path = output_dir / "frontend-editor-metrics.json"

    env = os.environ.copy()
    browser_executable = find_browser_executable()
    if browser_executable is not None:
        env.setdefault("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH", browser_executable)

    server = subprocess.Popen(
        [sys.executable, str(ROOT / "scripts" / "serve_frontend.py"), "--port", str(port)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        _wait_for_server(f"http://127.0.0.1:{port}/frontend/api/examples.json", process=server)
        capture = subprocess.run(
            [
                "node",
                str(ROOT / "scripts" / "capture_frontend_state.js"),
                "--url",
                f"http://127.0.0.1:{port}/frontend/?test=1",
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
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    image = cv2.imread(str(screenshot_path))
    if image is None:
        raise RuntimeError(f"failed to read screenshot at {screenshot_path}")

    crop = _extract_visible_editor_crop(image, metrics["paneRect"])
    mask, signal_rows = _compute_signal_rows(crop)
    text_mask = _extract_text_mask(crop)
    failures = _validate_metrics(metrics, crop, signal_rows)
    failures.extend(_find_label_overlap_failures(metrics, text_mask))
    ocr_failures, ocr_analysis = _find_ocr_failures(metrics, crop)
    failures.extend(ocr_failures)

    cv2.imwrite(str(crop_path), crop)
    cv2.imwrite(str(mask_path), mask)
    metrics_with_analysis = {
        **metrics,
        "analysis": {
            "signalRowCount": len(signal_rows),
            "firstSignalRow": signal_rows[0] if signal_rows else None,
            "outputDir": str(output_dir),
            "ocr": ocr_analysis,
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
