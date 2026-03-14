from __future__ import annotations

import json
from pathlib import Path

import pytest

from examples.specs.catalog import rc_lowpass
from mixedsig2cad import check_parser_runtime_dependencies, parse_circuit_source
from scripts import setup_parser_env


def test_parse_vector_kicad_source_emits_scene_and_artifacts(tmp_path: Path) -> None:
    source = Path("examples/generated/kicad/rc_lowpass.kicad_sch")

    result = parse_circuit_source(source, source_type="vector", output_dir=tmp_path, spec=rc_lowpass())

    assert result.source_type == "vector"
    assert result.scene.source_kind == "vector:.kicad_sch"
    assert result.components
    assert result.graph.nodes
    assert result.netlist_text is not None
    assert result.overlay.path == tmp_path / "overlay.svg"
    assert result.artifacts is not None
    assert result.artifacts.components_json.exists()
    assert result.artifacts.junctions_json.exists()
    assert result.artifacts.graph_json.exists()
    assert result.artifacts.netlist_txt == tmp_path / "netlist.txt"
    assert (tmp_path / "overlay.svg").exists()

    components = json.loads((tmp_path / "components.json").read_text(encoding="utf-8"))
    graph = json.loads((tmp_path / "graph.json").read_text(encoding="utf-8"))
    assert any(component["ref"] == "R1" for component in components)
    assert graph["nodes"]


def test_parse_raster_requires_dependencies() -> None:
    with pytest.raises(RuntimeError, match="Missing parser dependencies"):
        parse_circuit_source("dummy.png", source_type="raster")


def test_dependency_status_reports_missing_runtime_tools() -> None:
    status = check_parser_runtime_dependencies()

    assert status.sam_available is False
    assert status.ocr_available is False
    assert status.missing


def test_setup_parser_env_returns_failure_when_modules_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(setup_parser_env.importlib.util, "find_spec", lambda name: None)
    monkeypatch.setattr(setup_parser_env.shutil, "which", lambda name: None)

    assert setup_parser_env.main() == 1
