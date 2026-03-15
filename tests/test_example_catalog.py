from __future__ import annotations

from examples.specs.catalog import (
    build_rc_lowpass_topology,
    example_instance_values,
    instantiate_topology,
    opamp_inverting,
)


def test_topology_builders_capture_connectivity_without_values() -> None:
    topology = build_rc_lowpass_topology()

    assert topology.name == "rc_lowpass"
    assert [(component.ref, component.kind, component.nodes) for component in topology.components] == [
        ("V1", "V", ("vin", "0")),
        ("R1", "R", ("vin", "vout")),
        ("C1", "C", ("vout", "0")),
    ]
    assert all(not hasattr(component, "value") for component in topology.components)


def test_instantiate_topology_pulls_values_from_shared_catalog() -> None:
    topology = build_rc_lowpass_topology()
    values = example_instance_values("rc_lowpass")

    spec = instantiate_topology(topology, values)

    assert [component.value for component in spec.components] == ["DC 5", "1k", "100n"]
    assert [analysis.command for analysis in spec.analyses] == ["op", "ac dec 20 10 1e6"]


def test_example_helper_preserves_model_and_analysis_data_from_catalog() -> None:
    spec = opamp_inverting().circuit

    assert [component.value for component in spec.components if component.ref in {"RIN", "RF", "R3"}] == [
        "10k",
        "100k",
        "10k",
    ]
    assert spec.models == [
        ".subckt OPAMP 1 2 6 4 5",
        "EGAIN 6 0 1 2 1e5",
        "RINP 1 0 1e9",
        "RINN 2 0 1e9",
        ".ends OPAMP",
    ]
    assert [analysis.command for analysis in spec.analyses] == ["tran 0.1ms 10ms"]
