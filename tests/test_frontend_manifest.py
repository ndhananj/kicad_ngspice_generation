from pathlib import Path

from scripts.serve_frontend import build_example_payload


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "frontend_corpus"


def test_fixture_manifest_reports_available_and_missing_artifacts() -> None:
    payload = build_example_payload(FIXTURE_ROOT, "/_frontend_fixtures")
    by_id = {entry["id"]: entry for entry in payload}

    assert list(by_id) == ["rc_lowpass", "rc_highpass", "diode_clipper"]
    assert by_id["rc_lowpass"]["artifacts"]["reportTex"]["available"] is True
    assert by_id["rc_lowpass"]["artifacts"]["svg"]["url"] == "/_frontend_fixtures/examples/generated/svg/rc_lowpass.svg"
    assert by_id["rc_highpass"]["artifacts"]["reportTex"]["available"] is False
    assert by_id["diode_clipper"]["artifacts"]["svg"]["available"] is False
