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
    external_pins: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ParameterizedBlock:
    name: str
    topology: ExampleTopology
    default_values: dict
    layout: SchematicLayoutIntent


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
    return [_topology_named(name) for name in _BLOCK_NAMES]


def block_named(name: str) -> ParameterizedBlock:
    try:
        return _blocks()[name]
    except KeyError as exc:
        raise KeyError(f"unknown block: {name}") from exc


def all_blocks() -> list[ParameterizedBlock]:
    return [block_named(name) for name in _BLOCK_NAMES]


def block_instance_values(name: str) -> dict:
    return json.loads(json.dumps(block_named(name).default_values))


def example_instance_values(name: str) -> dict:
    return block_instance_values(name)


def instantiate_topology(topology: ExampleTopology, values: dict) -> CircuitSpec:
    spec = CircuitSpec(topology.name)
    components_by_ref = values["components"]
    _validate_component_values(topology, components_by_ref)

    node_map = {pin: pin for pin in topology.external_pins}
    for component in topology.components:
        value_entry = components_by_ref[component.ref]
        spec.add(
            component.ref,
            component.kind,
            value_entry["value"],
            *(node_map.get(node, node) for node in component.nodes),
            model=value_entry.get("model"),
        )

    for model_line in values.get("models", []):
        spec.add_model(model_line)
    for analysis in values.get("analyses", []):
        spec.analyze(analysis)
    return spec


def instantiate_circuit_block(
    block: ParameterizedBlock,
    *,
    parameters: dict | None = None,
    pin_map: dict[str, str] | None = None,
    ref_prefix: str | None = None,
    instance_name: str | None = None,
) -> CircuitSpec:
    values = _resolved_block_values(block, parameters)
    mapped_pins = _resolved_pin_map(block.topology, pin_map)
    circuit = CircuitSpec(instance_name or block.name)
    for component in block.topology.components:
        value_entry = values["components"][component.ref]
        circuit.add(
            _prefixed_ref(component.ref, ref_prefix),
            component.kind,
            value_entry["value"],
            *(mapped_pins.get(node, node) for node in component.nodes),
            model=value_entry.get("model"),
        )

    for model_line in values.get("models", []):
        circuit.add_model(model_line)
    for analysis in values.get("analyses", []):
        circuit.analyze(analysis)
    return circuit


def instantiate_block(
    block: ParameterizedBlock,
    *,
    parameters: dict | None = None,
    pin_map: dict[str, str] | None = None,
    ref_prefix: str | None = None,
    instance_name: str | None = None,
    layout_offset: Point | tuple[float, float] | None = None,
) -> ExampleDesign:
    mapped_pins = _resolved_pin_map(block.topology, pin_map)
    circuit = instantiate_circuit_block(
        block,
        parameters=parameters,
        pin_map=mapped_pins,
        ref_prefix=ref_prefix,
        instance_name=instance_name or block.name,
    )
    layout = _instantiate_layout(
        block.layout,
        node_map=mapped_pins,
        ref_prefix=ref_prefix,
        instance_name=instance_name or block.name,
        layout_offset=layout_offset,
    )
    return ExampleDesign(name=instance_name or block.name, circuit=circuit, layout=layout)


def instantiate_example(name: str) -> ExampleDesign:
    return instantiate_block(block_named(name))


def merge_designs(name: str, designs: list[ExampleDesign]) -> ExampleDesign:
    circuit = CircuitSpec(name)
    merged_components = []
    merged_supports = []
    merged_texts = []
    merged_routed_nets = []
    seen_component_refs: set[str] = set()
    seen_layout_refs: set[str] = set()
    seen_models: set[str] = set()
    seen_analyses: set[str] = set()

    for design in designs:
        for component in design.circuit.components:
            if component.ref in seen_component_refs:
                raise ValueError(f"duplicate component ref while merging designs: {component.ref}")
            seen_component_refs.add(component.ref)
            circuit.add(component.ref, component.kind, component.value, *component.nodes, model=component.model)

        for model_line in design.circuit.models:
            if model_line not in seen_models:
                seen_models.add(model_line)
                circuit.add_model(model_line)

        for analysis in design.circuit.analyses:
            if analysis.command not in seen_analyses:
                seen_analyses.add(analysis.command)
                circuit.analyze(analysis.command)

        for component in design.layout.components:
            if component.ref in seen_layout_refs:
                raise ValueError(f"duplicate layout ref while merging designs: {component.ref}")
            seen_layout_refs.add(component.ref)
            merged_components.append(component)

        for support in design.layout.supports:
            if support.ref in seen_layout_refs:
                raise ValueError(f"duplicate layout ref while merging designs: {support.ref}")
            seen_layout_refs.add(support.ref)
            merged_supports.append(support)

        merged_texts.extend(design.layout.texts)
        merged_routed_nets.extend(design.layout.routed_nets)

    return ExampleDesign(
        name=name,
        circuit=circuit,
        layout=SchematicLayoutIntent(
            name=name,
            components=tuple(merged_components),
            supports=tuple(merged_supports),
            texts=tuple(merged_texts),
            routed_nets=tuple(merged_routed_nets),
        ),
    )


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
    return [instantiate_example(name) for name in _BLOCK_NAMES]


def _all_circuit_specs() -> list[CircuitSpec]:
    return [instantiate_circuit_block(block_named(name)) for name in _BLOCK_NAMES]


_BLOCK_NAMES = (
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
    return block_named(name).topology


@lru_cache(maxsize=1)
def _blocks() -> dict[str, ParameterizedBlock]:
    topologies = _topologies()
    values = _instance_catalog()
    layouts = _seed_layouts()
    return {
        name: ParameterizedBlock(name=name, topology=topologies[name], default_values=values[name], layout=layouts[name])
        for name in _BLOCK_NAMES
    }


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
            external_pins=("vin", "vout"),
        ),
        "rc_highpass": ExampleTopology(
            name="rc_highpass",
            components=(
                ComponentTopology("V1", "V", ("vin", "0")),
                ComponentTopology("C1", "C", ("vin", "vmid")),
                ComponentTopology("R1", "R", ("vmid", "0")),
            ),
            external_pins=("vin", "vmid"),
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
            external_pins=("vin", "n2"),
        ),
        "diode_clipper": ExampleTopology(
            name="diode_clipper",
            components=(
                ComponentTopology("V1", "V", ("vin", "0")),
                ComponentTopology("R1", "R", ("vin", "vout")),
                ComponentTopology("D1", "D", ("vout", "0")),
            ),
            external_pins=("vin", "vout"),
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
            external_pins=("vcc", "vin_src", "vout"),
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
            external_pins=("vcc", "vee", "vin", "vout"),
        ),
        "cmos_inverter": ExampleTopology(
            name="cmos_inverter",
            components=(
                ComponentTopology("VDD", "V", ("vdd", "0")),
                ComponentTopology("VIN", "V", ("vin", "0")),
                ComponentTopology("MP1", "M", ("vout", "vin", "vdd", "vdd")),
                ComponentTopology("MN1", "M", ("vout", "vin", "0", "0")),
            ),
            external_pins=("vdd", "vin", "vout"),
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
            external_pins=("vcc", "vin", "vref", "vout"),
        ),
    }


def _validate_component_values(topology: ExampleTopology, components_by_ref: dict[str, dict]) -> None:
    expected_refs = {component.ref for component in topology.components}
    unknown_refs = set(components_by_ref) - expected_refs
    missing_refs = expected_refs - set(components_by_ref)
    if not unknown_refs and not missing_refs:
        return

    problems = []
    if unknown_refs:
        problems.append(f"unknown component refs: {sorted(unknown_refs)}")
    if missing_refs:
        problems.append(f"missing component refs: {sorted(missing_refs)}")
    raise ValueError(f"invalid values for topology {topology.name}: {'; '.join(problems)}")


def _resolved_block_values(block: ParameterizedBlock, parameters: dict | None) -> dict:
    values = json.loads(json.dumps(block.default_values))
    if not parameters:
        return values

    component_overrides = parameters.get("components", {})
    unknown_refs = set(component_overrides) - {component.ref for component in block.topology.components}
    if unknown_refs:
        raise ValueError(f"unknown component overrides for block {block.name}: {sorted(unknown_refs)}")

    for ref, override in component_overrides.items():
        values["components"][ref].update(override)

    if "models" in parameters:
        values["models"] = list(parameters["models"])
    if "analyses" in parameters:
        values["analyses"] = list(parameters["analyses"])
    return values


def _resolved_pin_map(topology: ExampleTopology, pin_map: dict[str, str] | None) -> dict[str, str]:
    mapping = {pin: pin for pin in topology.external_pins}
    if not pin_map:
        return mapping

    unknown_pins = set(pin_map) - set(topology.external_pins)
    if unknown_pins:
        raise ValueError(f"unknown pin mappings for block {topology.name}: {sorted(unknown_pins)}")
    mapping.update(pin_map)
    return mapping


def _instantiate_layout(
    layout: SchematicLayoutIntent,
    *,
    node_map: dict[str, str],
    ref_prefix: str | None,
    instance_name: str,
    layout_offset: Point | tuple[float, float] | None,
) -> SchematicLayoutIntent:
    dx, dy = _offset_xy(layout_offset)
    return SchematicLayoutIntent(
        name=instance_name,
        components=tuple(
            LayoutComponentIntent(
                ref=_prefixed_ref(item.ref, ref_prefix),
                center=_translate_point(item.center, dx, dy),
                orientation=item.orientation,
                reference_position=_translate_point(item.reference_position, dx, dy),
                value_position=_translate_point(item.value_position, dx, dy),
                hidden_reference=item.hidden_reference,
            )
            for item in layout.components
        ),
        supports=tuple(
            LayoutSupportIntent(
                ref=_prefixed_ref(item.ref, ref_prefix),
                shape=item.shape,
                value=node_map.get(item.value, item.value),
                center=_translate_point(item.center, dx, dy),
                orientation=item.orientation,
                reference_position=_translate_point(item.reference_position, dx, dy),
                value_position=_translate_point(item.value_position, dx, dy),
                hidden_reference=item.hidden_reference,
            )
            for item in layout.supports
        ),
        texts=tuple(
            LayoutTextIntent(
                text=node_map.get(item.text, item.text) if item.role == "net_label" else item.text,
                role=item.role,
                position=_translate_point(item.position, dx, dy),
                owner_ref=_prefixed_owner_ref(item.owner_ref, ref_prefix),
                font_size=item.font_size,
            )
            for item in layout.texts
        ),
        routed_nets=tuple(
            RoutedNetIntent(
                name=node_map.get(item.name, item.name),
                segments=tuple(tuple(_translate_point(point, dx, dy) for point in segment) for segment in item.segments),
                junctions=tuple(_translate_point(point, dx, dy) for point in item.junctions),
            )
            for item in layout.routed_nets
        ),
    )


def _prefixed_ref(ref: str, ref_prefix: str | None) -> str:
    return f"{ref_prefix}{ref}" if ref_prefix else ref


def _prefixed_owner_ref(owner_ref: str, ref_prefix: str | None) -> str:
    if not ref_prefix:
        return owner_ref
    if owner_ref.startswith("label:"):
        return f"{ref_prefix}{owner_ref}"
    return _prefixed_ref(owner_ref, ref_prefix)


def _offset_xy(layout_offset: Point | tuple[float, float] | None) -> tuple[float, float]:
    if layout_offset is None:
        return 0.0, 0.0
    if isinstance(layout_offset, Point):
        return layout_offset.x, layout_offset.y
    return float(layout_offset[0]), float(layout_offset[1])


def _translate_point(point: Point, dx: float, dy: float) -> Point:
    return Point(point.x + dx, point.y + dy)


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
