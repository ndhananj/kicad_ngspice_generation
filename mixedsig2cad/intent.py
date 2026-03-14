from __future__ import annotations

from dataclasses import dataclass, field

from .design import ExampleDesign, circuit_of
from .spec import CircuitSpec, Component


@dataclass(frozen=True, slots=True)
class IntentComponent:
    ref: str
    kind: str
    value: str
    nodes: tuple[str, ...]
    model: str | None = None


@dataclass(frozen=True, slots=True)
class IntentNet:
    name: str
    role: str
    degree: int


@dataclass(frozen=True, slots=True)
class IntentConnection:
    component_ref: str
    pin_index: int
    net_name: str


@dataclass(frozen=True, slots=True)
class IntentPattern:
    kind: str
    components: dict[str, str]
    nets: dict[str, str]


@dataclass(frozen=True, slots=True)
class IntentGroup:
    name: str
    kind: str
    members: tuple[str, ...]


@dataclass(slots=True)
class SchematicIntent:
    name: str
    components: list[IntentComponent] = field(default_factory=list)
    nets: dict[str, IntentNet] = field(default_factory=dict)
    connections: list[IntentConnection] = field(default_factory=list)
    patterns: list[IntentPattern] = field(default_factory=list)
    groups: list[IntentGroup] = field(default_factory=list)
    flow_direction: str = "left_to_right"


GROUND_NETS = {"0", "gnd", "vss"}
SUPPLY_NETS = {"vcc", "vdd", "vee"}


def build_schematic_intent(spec: ExampleDesign | CircuitSpec) -> SchematicIntent:
    spec = circuit_of(spec)
    components = [
        IntentComponent(ref=comp.ref, kind=comp.kind, value=comp.value, nodes=comp.nodes, model=comp.model)
        for comp in spec.components
    ]
    net_degrees: dict[str, int] = {}
    connections: list[IntentConnection] = []
    for comp in components:
        for pin_index, net_name in enumerate(comp.nodes):
            net_degrees[net_name] = net_degrees.get(net_name, 0) + 1
            connections.append(IntentConnection(component_ref=comp.ref, pin_index=pin_index, net_name=net_name))

    nets = {
        net_name: IntentNet(name=net_name, role=_classify_net_role(net_name), degree=degree)
        for net_name, degree in sorted(net_degrees.items())
    }

    patterns = _infer_patterns(components, nets)
    groups = _build_groups(components)
    return SchematicIntent(
        name=spec.name,
        components=components,
        nets=nets,
        connections=connections,
        patterns=patterns,
        groups=groups,
        flow_direction="left_to_right",
    )


def _classify_net_role(net_name: str) -> str:
    lowered = net_name.lower()
    if lowered in GROUND_NETS:
        return "ground"
    if lowered in SUPPLY_NETS:
        return "supply"
    if lowered in {"vin", "in", "input"}:
        return "signal_in"
    if lowered in {"vout", "out", "output"}:
        return "signal_out"
    return "signal"


def _build_groups(components: list[IntentComponent]) -> list[IntentGroup]:
    groups: dict[str, list[str]] = {"sources": [], "passives": [], "actives": []}
    for comp in components:
        if comp.kind in {"V", "I"}:
            groups["sources"].append(comp.ref)
        elif comp.kind in {"R", "C", "L", "D"}:
            groups["passives"].append(comp.ref)
        else:
            groups["actives"].append(comp.ref)
    return [
        IntentGroup(name=name, kind=name[:-1] if name.endswith("s") else name, members=tuple(members))
        for name, members in groups.items()
        if members
    ]


def _infer_patterns(components: list[IntentComponent], nets: dict[str, IntentNet]) -> list[IntentPattern]:
    patterns: list[IntentPattern] = []
    grounded_sources = [
        comp
        for comp in components
        if comp.kind in {"V", "I"} and len(comp.nodes) >= 2 and nets[comp.nodes[1]].role == "ground"
    ]
    two_pin_passives = [comp for comp in components if comp.kind in {"R", "C", "L", "D"} and len(comp.nodes) == 2]

    for source in grounded_sources:
        source_net = source.nodes[0]
        series_candidates = [
            comp
            for comp in two_pin_passives
            if source_net in comp.nodes and all(nets[node].role != "ground" for node in comp.nodes)
        ]
        for series in series_candidates:
            branch_net = series.nodes[1] if series.nodes[0] == source_net else series.nodes[0]
            shunt_candidates = [
                comp
                for comp in two_pin_passives
                if branch_net in comp.nodes and any(nets[node].role == "ground" for node in comp.nodes)
            ]
            for shunt in shunt_candidates:
                kind = _pattern_kind(series, shunt)
                if kind is None:
                    continue
                patterns.append(
                    IntentPattern(
                        kind=kind,
                        components={"source": source.ref, "series": series.ref, "shunt": shunt.ref},
                        nets={"input": source_net, "node": branch_net, "ground": shunt.nodes[0] if nets[shunt.nodes[0]].role == "ground" else shunt.nodes[1]},
                    )
                )
    return patterns


def _pattern_kind(series: IntentComponent, shunt: IntentComponent) -> str | None:
    if series.kind == "R" and shunt.kind == "C":
        return "rc_lowpass"
    if series.kind == "C" and shunt.kind == "R":
        return "rc_highpass"
    return None
