from __future__ import annotations

import json
from pathlib import Path

from scripts.serve_frontend import ARTIFACT_RELATIVE_PATHS


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "frontend" / "example_catalog.json"
EXAMPLES_ROOT = ROOT
CATALOG_IDS = [entry["id"] for entry in json.loads(CATALOG_PATH.read_text(encoding="utf-8"))]
REQUIRED_GENERATED_ARTIFACT_KEYS = (
    "editorScene",
    "svg",
    "pdf",
    "kicad",
    "ngspice",
    "reportTex",
    "circuitikzTex",
    "reportPdf",
)


def _artifact_path(example_id: str, artifact_key: str) -> Path:
    return EXAMPLES_ROOT / ARTIFACT_RELATIVE_PATHS[artifact_key].format(example_id=example_id)


def test_frontend_catalog_lists_expected_example_ids() -> None:
    assert CATALOG_IDS == [
        "rc_lowpass",
        "rc_highpass",
        "rlc_bandpass",
        "diode_clipper",
        "bjt_common_emitter",
        "opamp_inverting",
        "cmos_inverter",
        "schmitt_trigger",
    ]


def test_generated_frontend_artifacts_cover_every_catalog_example() -> None:
    missing_by_example: dict[str, list[str]] = {}

    for example_id in CATALOG_IDS:
        missing = [
            artifact_key
            for artifact_key in REQUIRED_GENERATED_ARTIFACT_KEYS
            if not _artifact_path(example_id, artifact_key).exists()
        ]
        if missing:
            missing_by_example[example_id] = missing

    assert not missing_by_example, f"missing generated frontend artifacts: {missing_by_example}"


def test_generated_tex_reports_exist_for_every_catalog_example() -> None:
    missing_reports = [
        example_id
        for example_id in CATALOG_IDS
        if not (_artifact_path(example_id, "reportTex").exists() and _artifact_path(example_id, "reportPdf").exists())
    ]

    assert not missing_reports, f"missing TeX report artifacts for: {missing_reports}"
