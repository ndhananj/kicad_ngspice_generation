from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from mixedsig2cad import CircuitSpec
from mixedsig2cad.design import (
    ExampleDesign,
    LayoutComponentIntent,
    LayoutSupportIntent,
    LayoutTextIntent,
    RoutedNetIntent,
    SchematicLayoutIntent,
)
from mixedsig2cad.models import Point


@dataclass(frozen=True, slots=True)
class ComponentTopology:
    ref: str
    kind: str
    nodes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExampleTopology:
    name: str
    components: tuple[ComponentTopology, ...]


def build_rc_lowpass_topology() -> ExampleTopology:
    return _topology_named("rc_lowpass")


def build_rc_highpass_topology() -> ExampleTopology:
    return _topology_named("rc_highpass")


def build_rlc_bandpass_topology() -> ExampleTopology:
    return _topology_named("rlc_bandpass")


def build_diode_clipper_topology() -> ExampleTopology:
    return _topology_named("diode_clipper")


def build_bjt_common_emitter_topology() -> ExampleTopology:
    return _topology_named("bjt_common_emitter")


def build_opamp_inverting_topology() -> ExampleTopology:
    return _topology_named("opamp_inverting")


def build_cmos_inverter_topology() -> ExampleTopology:
    return _topology_named("cmos_inverter")


def build_schmitt_trigger_topology() -> ExampleTopology:
    return _topology_named("schmitt_trigger")


def topology_named(name: str) -> ExampleTopology:
    return _topology_named(name)


def all_topologies() -> list[ExampleTopology]:
    return [_topology_named(name) for name in _TOPOLOGY_BUILDERS]


def example_instance_values(name: str) -> dict:
    return json.loads(json.dumps(_instance_catalog()[name]))


def instantiate_topology(topology: ExampleTopology, values: dict) -> CircuitSpec:
    spec = CircuitSpec(topology.name)
    components_by_ref = values["components"]
    expected_refs = {component.ref for component in topology.components}
    unknown_refs = set(components_by_ref) - expected_refs
    missing_refs = expected_refs - set(components_by_ref)
    if unknown_refs or missing_refs:
        problems = []
        if unknown_refs:
            problems.append(f"unknown component refs: {sorted(unknown_refs)}")
        if missing_refs:
            problems.append(f"missing component refs: {sorted(missing_refs)}")
        raise ValueError(f"invalid values for topology {topology.name}: {'; '.join(problems)}")

    for component in topology.components:
        value_entry = components_by_ref[component.ref]
        spec.add(
            component.ref,
            component.kind,
            value_entry["value"],
            *component.nodes,
            model=value_entry.get("model"),
        )

    for model_line in values.get("models", []):
        spec.add_model(model_line)
    for analysis in values.get("analyses", []):
        spec.analyze(analysis)
    return spec


def instantiate_example(name: str) -> ExampleDesign:
    spec = instantiate_topology(_topology_named(name), _instance_catalog()[name])
    return ExampleDesign(name=name, circuit=spec, layout=_seed_layouts()[name])


def rc_lowpass() -> ExampleDesign:
    return instantiate_example("rc_lowpass")


def rc_highpass() -> ExampleDesign:
    return instantiate_example("rc_highpass")


def rlc_bandpass() -> ExampleDesign:
    return instantiate_example("rlc_bandpass")


def diode_clipper() -> ExampleDesign:
    return instantiate_example("diode_clipper")


def bjt_common_emitter() -> ExampleDesign:
    return instantiate_example("bjt_common_emitter")


def opamp_inverting() -> ExampleDesign:
    return instantiate_example("opamp_inverting")


def cmos_inverter() -> ExampleDesign:
    return instantiate_example("cmos_inverter")


def schmitt_trigger() -> ExampleDesign:
    return instantiate_example("schmitt_trigger")


def all_examples() -> list[ExampleDesign]:
    return [instantiate_example(name) for name in _TOPOLOGY_BUILDERS]


def _all_circuit_specs() -> list[CircuitSpec]:
    return [instantiate_topology(_topology_named(name), _instance_catalog()[name]) for name in _TOPOLOGY_BUILDERS]


_TOPOLOGY_BUILDERS = (
    "rc_lowpass",
    "rc_highpass",
    "rlc_bandpass",
    "diode_clipper",
    "bjt_common_emitter",
    "opamp_inverting",
    "cmos_inverter",
    "schmitt_trigger",
)


def _topology_named(name: str) -> ExampleTopology:
    try:
        return _topologies()[name]
    except KeyError as exc:
        raise KeyError(f"unknown example topology: {name}") from exc


@lru_cache(maxsize=1)
def _topologies() -> dict[str, ExampleTopology]:
    return {
        "rc_lowpass": ExampleTopology(
            name="rc_lowpass",
            components=(
                ComponentTopology("V1", "V", ("vin", "0")),
                ComponentTopology("R1", "R", ("vin", "vout")),
                ComponentTopology("C1", "C", ("vout", "0")),
            ),
        ),
        "rc_highpass": ExampleTopology(
            name="rc_highpass",
            components=(
                ComponentTopology("V1", "V", ("vin", "0")),
                ComponentTopology("C1", "C", ("vin", "vmid")),
                ComponentTopology("R1", "R", ("vmid", "0")),
            ),
        ),
        "rlc_bandpass": ExampleTopology(
            name="rlc_bandpass",
            components=(
                ComponentTopology("V1", "V", ("vin", "0")),
                ComponentTopology("R1", "R", ("vin", "n1")),
                ComponentTopology("L1", "L", ("n1", "n2")),
                ComponentTopology("C1", "C", ("n2", "0")),
                ComponentTopology("R2", "R", ("n2", "0")),
            ),
        ),
        "diode_clipper": ExampleTopology(
            name="diode_clipper",
            components=(
                ComponentTopology("V1", "V", ("vin", "0")),
                ComponentTopology("R1", "R", ("vin", "vout")),
                ComponentTopology("D1", "D", ("vout", "0")),
            ),
        ),
        "bjt_common_emitter": ExampleTopology(
            name="bjt_common_emitter",
            components=(
                ComponentTopology("VCC", "V", ("vcc", "0")),
                ComponentTopology("VS", "V", ("vin_src", "0")),
                ComponentTopology("CB", "C", ("vin_src", "base")),
                ComponentTopology("R1", "R", ("vcc", "base")),
                ComponentTopology("R2", "R", ("base", "0")),
                ComponentTopology("RC", "R", ("vcc", "collector")),
                ComponentTopology("RE", "R", ("emitter", "0")),
                ComponentTopology("CE", "C", ("emitter", "0")),
                ComponentTopology("CC", "C", ("collector", "vout")),
                ComponentTopology("RL", "R", ("vout", "0")),
                ComponentTopology("Q1", "Q", ("collector", "base", "emitter")),
            ),
        ),
        "opamp_inverting": ExampleTopology(
            name="opamp_inverting",
            components=(
                ComponentTopology("VCC", "V", ("vcc", "0")),
                ComponentTopology("VEE", "V", ("vee", "0")),
                ComponentTopology("VIN", "V", ("vin", "0")),
                ComponentTopology("RIN", "R", ("vin", "vminus")),
                ComponentTopology("RF", "R", ("vout", "vminus")),
                ComponentTopology("R3", "R", ("vplus_ref", "0")),
                ComponentTopology("XU1", "X", ("vplus_ref", "vminus", "vout", "vcc", "vee")),
            ),
        ),
        "cmos_inverter": ExampleTopology(
            name="cmos_inverter",
            components=(
                ComponentTopology("VDD", "V", ("vdd", "0")),
                ComponentTopology("VIN", "V", ("vin", "0")),
                ComponentTopology("MP1", "M", ("vout", "vin", "vdd", "vdd")),
                ComponentTopology("MN1", "M", ("vout", "vin", "0", "0")),
            ),
        ),
        "schmitt_trigger": ExampleTopology(
            name="schmitt_trigger",
            components=(
                ComponentTopology("VCC", "V", ("vcc", "0")),
                ComponentTopology("VIN", "V", ("vin", "0")),
                ComponentTopology("VREF", "V", ("vref", "0")),
                ComponentTopology("R1", "R", ("vref", "vplus")),
                ComponentTopology("R2", "R", ("vplus", "0")),
                ComponentTopology("R3", "R", ("vout", "vplus")),
                ComponentTopology("XU1", "X", ("vplus", "vin", "vout", "vcc", "0")),
            ),
        ),
    }


@lru_cache(maxsize=1)
def _instance_catalog() -> dict[str, dict]:
    return json.loads((Path(__file__).with_name("circuit_values.json")).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _seed_layouts() -> dict[str, SchematicLayoutIntent]:
    payload = json.loads((Path(__file__).with_name("seeded_layouts.json")).read_text(encoding="utf-8"))
    layouts = {}
    for name, entry in payload.items():
        layouts[name] = SchematicLayoutIntent(
            name=entry["name"],
            components=tuple(
                LayoutComponentIntent(
                    ref=item["ref"],
                    center=_point(item["center"]),
                    orientation=_component_orientation(name, item["ref"], item["orientation"]),
                    reference_position=_point(item["reference_position"]),
                    value_position=_point(item["value_position"]),
                    hidden_reference=item.get("hidden_reference", False),
                )
                for item in entry["components"]
            ),
            supports=tuple(
                LayoutSupportIntent(
                    ref=item["ref"],
                    shape=item["shape"],
                    value=item["value"],
                    center=_point(item["center"]),
                    orientation=item["orientation"],
                    reference_position=_point(item["reference_position"]),
                    value_position=_point(item["value_position"]),
                    hidden_reference=item.get("hidden_reference", False),
                )
                for item in entry.get("supports", [])
            ),
            texts=tuple(
                LayoutTextIntent(
                    text=item["text"],
                    role=item["role"],
                    position=_point(item["position"]),
                    owner_ref=item["owner_ref"],
                    font_size=item.get("font_size", 1.27),
                )
                for item in entry.get("texts", [])
            ),
            routed_nets=tuple(
                RoutedNetIntent(
                    name=item["name"],
                    segments=tuple(tuple(_point(point) for point in segment) for segment in item.get("segments", [])),
                    junctions=tuple(_point(point) for point in item.get("junctions", [])),
                )
                for item in entry.get("routed_nets", [])
            ),
        )
    return layouts


def _point(payload: dict[str, float]) -> Point:
    return Point(payload["x"], payload["y"])


def _component_orientation(name: str, ref: str, orientation: str) -> str:
    if name == "schmitt_trigger" and ref == "R3":
        return "horizontal_flipped"
    return orientation
