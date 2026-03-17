from __future__ import annotations

from examples.specs.catalog import (
    block_named,
    build_rc_lowpass_topology,
    example_instance_values,
    instantiate_block,
    instantiate_circuit_block,
    instantiate_topology,
    merge_designs,
    opamp_inverting,
)
from mixedsig2cad.models import Point


def test_topology_builders_capture_connectivity_without_values() -> None:
    topology = build_rc_lowpass_topology()

    assert topology.name == "rc_lowpass"
    assert topology.external_pins == ("vin", "vout")
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


def test_block_named_exposes_reusable_full_design_data() -> None:
    block = block_named("rc_lowpass")

    assert block.name == "rc_lowpass"
    assert block.topology.external_pins == ("vin", "vout")
    assert block.default_values["components"]["R1"]["value"] == "1k"
    assert block.layout.name == "rc_lowpass"


def test_instantiate_block_supports_parameter_pin_and_ref_overrides() -> None:
    design = instantiate_block(
        block_named("rc_lowpass"),
        parameters={"components": {"R1": {"value": "4.7k"}}},
        pin_map={"vin": "input_bus", "vout": "filtered_out"},
        ref_prefix="F1_",
        instance_name="front_end",
        layout_offset=Point(10.0, -5.0),
    )

    assert design.name == "front_end"
    assert [(component.ref, component.value, component.nodes) for component in design.circuit.components] == [
        ("F1_V1", "DC 5", ("input_bus", "0")),
        ("F1_R1", "4.7k", ("input_bus", "filtered_out")),
        ("F1_C1", "100n", ("filtered_out", "0")),
    ]
    assert [text.text for text in design.layout.texts if text.role == "net_label"] == ["filtered_out", "input_bus"]
    assert design.layout.components[0].center == Point(65.88, 81.36)


def test_instantiate_circuit_block_returns_flat_circuit_spec() -> None:
    spec = instantiate_circuit_block(
        block_named("cmos_inverter"),
        pin_map={"vdd": "vlogic", "vin": "sig_in", "vout": "sig_out"},
        ref_prefix="INV_",
        instance_name="stage_a",
    )

    assert spec.name == "stage_a"
    assert [component.ref for component in spec.components] == ["INV_VDD", "INV_VIN", "INV_MP1", "INV_MN1"]
    assert [component.nodes for component in spec.components[-2:]] == [
        ("sig_out", "sig_in", "vlogic", "vlogic"),
        ("sig_out", "sig_in", "0", "0"),
    ]


def test_merge_designs_combines_prefixed_block_instances_without_ref_collisions() -> None:
    stage_a = instantiate_block(
        block_named("rc_lowpass"),
        pin_map={"vin": "vin_a", "vout": "mid"},
        ref_prefix="A_",
        instance_name="stage_a",
    )
    stage_b = instantiate_block(
        block_named("rc_highpass"),
        pin_map={"vin": "mid", "vmid": "vout_b"},
        ref_prefix="B_",
        instance_name="stage_b",
        layout_offset=(80.0, 0.0),
    )

    merged = merge_designs("filter_chain", [stage_a, stage_b])

    assert merged.name == "filter_chain"
    assert [component.ref for component in merged.circuit.components] == ["A_V1", "A_R1", "A_C1", "B_V1", "B_C1", "B_R1"]
    assert [analysis.command for analysis in merged.circuit.analyses] == ["op", "ac dec 20 10 1e6"]
    assert {component.ref for component in merged.layout.components} == {"A_V1", "A_R1", "A_C1", "B_V1", "B_C1", "B_R1"}
