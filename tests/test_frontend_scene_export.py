from __future__ import annotations

from examples.specs.catalog import instantiate_example
from mixedsig2cad.exporters.frontend import build_frontend_scene


def test_frontend_scene_export_contains_compiled_geometry_content() -> None:
    scene = build_frontend_scene(instantiate_example("rc_lowpass"))

    assert scene["name"] == "rc_lowpass"
    refs = {component["ref"] for component in scene["components"]}
    assert {"V1", "R1", "C1"}.issubset(refs)
    assert any(wire["points"] for wire in scene["wires"])
    assert any(label["role"] == "reference" for label in scene["labels"])
    assert scene["bounds"]["width"] > 0
    assert scene["bounds"]["height"] > 0


def test_frontend_scene_export_omits_hidden_support_reference_labels() -> None:
    scene = build_frontend_scene(instantiate_example("rlc_bandpass"))

    labels = scene["labels"]
    assert not any(label["text"].startswith("#SUPPORT") for label in labels)
    assert any(label["text"] == "GND" for label in labels)
