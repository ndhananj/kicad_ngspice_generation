from pathlib import Path

from scripts.serve_frontend import ARTIFACT_RELATIVE_PATHS, build_example_payload
from frontend_fixture_contract import (
    EXPECTED_FIXTURE_ARTIFACTS,
    EXPECTED_FIXTURE_FILES,
    FIXTURE_URL_PREFIX,
    build_sanitized_fixture_corpus,
)


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "frontend_corpus"


def _expected_url(example_id: str, artifact_key: str) -> str:
    relative = ARTIFACT_RELATIVE_PATHS[artifact_key].format(example_id=example_id)
    return f"{FIXTURE_URL_PREFIX}/{relative}"


def test_fixture_manifest_matches_declared_smoke_corpus_contract(tmp_path: Path) -> None:
    fixture_root = build_sanitized_fixture_corpus(FIXTURE_ROOT, tmp_path / "frontend_corpus")
    payload = build_example_payload(fixture_root, FIXTURE_URL_PREFIX)
    by_id = {entry["id"]: entry for entry in payload}

    assert list(by_id) == list(EXPECTED_FIXTURE_ARTIFACTS)

    for example_id, expected_artifacts in EXPECTED_FIXTURE_ARTIFACTS.items():
        actual_artifacts = by_id[example_id]["artifacts"]
        assert set(actual_artifacts) == set(expected_artifacts)
        for artifact_key, expected_available in expected_artifacts.items():
            artifact = actual_artifacts[artifact_key]
            assert artifact["available"] is expected_available
            assert artifact["url"] == _expected_url(example_id, artifact_key)


def test_fixture_source_contains_expected_smoke_files() -> None:
    for relative in EXPECTED_FIXTURE_FILES:
        assert (FIXTURE_ROOT / relative).exists(), relative
