from __future__ import annotations

from dataclasses import dataclass, field

from .intent import IntentComponent, SchematicIntent
from .symbols import default_orientation_for_component, terminal_offset_for_component

KICAD_CONNECTION_GRID = 1.27

@dataclass(frozen=True, slots=True)
class TopologyPoint:
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class TopologyPlacement:
    ref: str
    center: TopologyPoint
    orientation: str | None = None
    shape: str | None = None
    value: str | None = None


@dataclass(frozen=True, slots=True)
class TopologyAttachment:
    owner_ref: str
    terminal_name: str


@dataclass(frozen=True, slots=True)
class TopologyConnection:
    id: str
    point: TopologyPoint
    attachments: tuple[TopologyAttachment, ...]
    render_style: str = "inline"
    role: str | None = None


@dataclass(slots=True)
class TopologyLayout:
    name: str
    placements: list[TopologyPlacement] = field(default_factory=list)
    connections: list[TopologyConnection] = field(default_factory=list)


def build_topology_layout(intent: SchematicIntent) -> TopologyLayout | None:
    return (
        _build_series_shunt_layout(intent)
        or _build_bjt_common_emitter_layout(intent)
        or _build_opamp_inverting_layout(intent)
    )


def _build_series_shunt_layout(intent: SchematicIntent) -> TopologyLayout | None:
    if not all(comp.kind in {"V", "I", "R", "C", "L", "D"} and len(comp.nodes) == 2 for comp in intent.components):
        return None
    sources = [comp for comp in intent.components if comp.kind in {"V", "I"} and intent.nets[comp.nodes[1]].role == "ground"]
    if len(sources) != 1:
        return None
    source = sources[0]
    passives = [comp for comp in intent.components if comp.ref != source.ref]
    path: list[IntentComponent] = []
    used: set[str] = set()
    current_net = source.nodes[0]
    while True:
        candidates = [
            comp
            for comp in passives
            if comp.ref not in used
            and current_net in comp.nodes
            and all(intent.nets[node].role not in {"ground", "supply"} for node in comp.nodes)
        ]
        if not candidates:
            break
        chosen = sorted(candidates, key=lambda comp: (comp.kind == "D", comp.ref))[0]
        path.append(chosen)
        used.add(chosen.ref)
        current_net = chosen.nodes[1] if chosen.nodes[0] == current_net else chosen.nodes[0]
    if not path:
        return None
    shunts = [
        comp
        for comp in passives
        if comp.ref not in used
        and current_net in comp.nodes
        and any(intent.nets[node].role == "ground" for node in comp.nodes)
    ]
    if not shunts:
        return None

    layout = TopologyLayout(name=intent.name)
    source_center = TopologyPoint(56.0, 86.0)
    layout.placements.append(TopologyPlacement(ref=source.ref, center=source_center, orientation="vertical_up"))
    source_gnd = TopologyPlacement(ref="#PWR0001", center=TopologyPoint(56.0, 105.62), shape="ground", value="GND", orientation="down")
    layout.placements.append(source_gnd)

    main_y = 78.0
    for idx, comp in enumerate(path):
        layout.placements.append(
            TopologyPlacement(ref=comp.ref, center=TopologyPoint(90.0 + idx * 30.0, main_y), orientation=_series_orientation(comp))
        )

    last = path[-1]
    output_point = terminal_point(last, layout, "right")
    for idx, comp in enumerate(shunts, start=1):
        orientation = _shunt_orientation(comp)
        center = _shunt_center_for_output(comp, orientation, output_point, idx, len(shunts))
        layout.placements.append(TopologyPlacement(ref=comp.ref, center=center, orientation=orientation))
        gnd_ref = f"#PWR{idx + 1:04d}"
        gnd_center = _ground_center_for_shunt(comp, center, orientation)
        layout.placements.append(TopologyPlacement(ref=gnd_ref, center=gnd_center, shape="ground", value="GND", orientation="down"))
        layout.connections.append(
            TopologyConnection(
                id=f"{gnd_ref}:ground",
                point=_point(gnd_center.x, gnd_center.y),
                attachments=(
                    TopologyAttachment(comp.ref, _ground_terminal_name(comp)),
                    TopologyAttachment(gnd_ref, "top"),
                ),
                role="local_ground",
            )
        )

    layout.connections.append(
        TopologyConnection(
            id="source_ground",
            point=_point(source_gnd.center.x, source_gnd.center.y),
            attachments=(TopologyAttachment(source.ref, "neg"), TopologyAttachment(source_gnd.ref, "top")),
            role="local_ground",
        )
    )

    first = path[0]
    layout.connections.append(
        TopologyConnection(
            id="source_path",
            point=_point((source_pos(source_center).x + terminal_point(first, layout, "left").x) / 2.0, main_y),
            attachments=(TopologyAttachment(source.ref, "pos"), TopologyAttachment(first.ref, "left")),
            role="series_inline",
        )
    )

    for first_comp, second_comp in zip(path, path[1:]):
        point = terminal_point(first_comp, layout, "right")
        layout.connections.append(
            TopologyConnection(
                id=f"{first_comp.ref}:{second_comp.ref}",
                point=_point(point.x, point.y),
                attachments=(TopologyAttachment(first_comp.ref, "right"), TopologyAttachment(second_comp.ref, "left")),
                role="series_inline",
            )
        )

    shunt_attachments = [TopologyAttachment(last.ref, "right")]
    for comp in shunts:
        shunt_attachments.append(TopologyAttachment(comp.ref, _shunt_terminal_name(comp)))
    layout.connections.append(
        TopologyConnection(
            id="output_node",
            point=output_point,
            attachments=tuple(shunt_attachments),
            render_style="junction" if len(shunt_attachments) >= 3 else "inline",
            role="shunt_branch",
        )
    )
    return layout


def _build_bjt_common_emitter_layout(intent: SchematicIntent) -> TopologyLayout | None:
    bjts = [comp for comp in intent.components if comp.kind == "Q" and len(comp.nodes) >= 3]
    if len(bjts) != 1:
        return None
    transistor = bjts[0]
    collector_net, base_net, emitter_net = transistor.nodes[:3]
    resistors = [comp for comp in intent.components if comp.kind == "R" and len(comp.nodes) == 2]
    capacitors = [comp for comp in intent.components if comp.kind == "C" and len(comp.nodes) == 2]
    sources = [
        comp
        for comp in intent.components
        if comp.kind == "V" and len(comp.nodes) == 2 and intent.nets[comp.nodes[1]].role == "ground"
    ]
    supply_sources = [comp for comp in sources if intent.nets[comp.nodes[0]].role == "supply"]
    if len(supply_sources) != 1:
        return None
    supply = supply_sources[0]
    supply_net = supply.nodes[0]
    signal_sources = [comp for comp in sources if comp.ref != supply.ref]
    if len(signal_sources) != 1:
        return None
    signal = signal_sources[0]
    signal_net = signal.nodes[0]

    rc = _find_resistor(resistors, supply_net, collector_net)
    re = _find_resistor(resistors, emitter_net, "0")
    r1 = _find_resistor(resistors, supply_net, base_net)
    r2 = _find_resistor(resistors, base_net, "0")
    rl = next(
        (
            comp
            for comp in resistors
            if comp.ref not in {ref for ref in {rc, re, r1, r2} if ref is not None}
            and "0" in comp.nodes
            and base_net not in comp.nodes
            and collector_net not in comp.nodes
            and emitter_net not in comp.nodes
        ),
        None,
    )
    cb = _find_capacitor(capacitors, signal_net, base_net)
    ce = _find_capacitor(capacitors, emitter_net, "0")
    cc = next((comp for comp in capacitors if collector_net in comp.nodes and "0" not in comp.nodes and base_net not in comp.nodes and emitter_net not in comp.nodes), None)
    if None in {rc, re, r1, r2, rl, cb, ce, cc}:
        return None

    output_net = next(node for node in cc.nodes if node != collector_net)
    if set(rl.nodes) != {output_net, "0"}:
        return None

    layout = TopologyLayout(name=intent.name)
    q_center = TopologyPoint(160.0, 100.0)
    top_rail_y = 68.41
    bottom_rail_y = 121.59
    base_node = _point(126.0, 100.0)
    collector_node = _point(163.81, 91.11)
    emitter_node = _point(163.81, 108.89)
    output_node = _point(200.0, 91.11)

    layout.placements.extend(
        [
            TopologyPlacement(ref=signal.ref, center=TopologyPoint(70.0, 107.62), orientation="vertical_up"),
            TopologyPlacement(ref=cb.ref, center=TopologyPoint(100.0, 100.0), orientation="horizontal"),
            TopologyPlacement(ref=r1.ref, center=TopologyPoint(base_node.x, 93.65), orientation="vertical"),
            TopologyPlacement(ref=r2.ref, center=TopologyPoint(base_node.x, 115.24), orientation="vertical"),
            TopologyPlacement(ref=transistor.ref, center=q_center, orientation="right"),
            TopologyPlacement(ref=rc.ref, center=TopologyPoint(163.81, 84.76), orientation="vertical"),
            TopologyPlacement(ref=re.ref, center=TopologyPoint(163.81, 115.24), orientation="vertical"),
            TopologyPlacement(ref=ce.ref, center=TopologyPoint(178.0, 115.24), orientation="vertical"),
            TopologyPlacement(ref=cc.ref, center=TopologyPoint(193.65, 91.11), orientation="horizontal"),
            TopologyPlacement(ref=rl.ref, center=TopologyPoint(output_node.x, 115.24), orientation="vertical"),
            TopologyPlacement(ref=supply.ref, center=TopologyPoint(220.0, 76.03), orientation="vertical_up"),
        ]
    )

    layout.connections.extend(
        [
            TopologyConnection(
                id="top_rail",
                point=_point(190.0, top_rail_y),
                attachments=(
                    TopologyAttachment(supply.ref, "pos"),
                    TopologyAttachment(r1.ref, "top"),
                    TopologyAttachment(rc.ref, "top"),
                ),
                render_style="junction",
                role="local_supply",
            ),
            TopologyConnection(
                id="bottom_rail",
                point=_point(200.0, bottom_rail_y),
                attachments=(
                    TopologyAttachment(signal.ref, "neg"),
                    TopologyAttachment(r2.ref, "bottom"),
                    TopologyAttachment(re.ref, "bottom"),
                    TopologyAttachment(ce.ref, "bottom"),
                    TopologyAttachment(rl.ref, "bottom"),
                    TopologyAttachment(supply.ref, "neg"),
                ),
                render_style="junction",
                role="local_ground",
            ),
            TopologyConnection(
                id="base_node",
                point=base_node,
                attachments=(
                    TopologyAttachment(cb.ref, "right"),
                    TopologyAttachment(r1.ref, "bottom"),
                    TopologyAttachment(r2.ref, "top"),
                    TopologyAttachment(transistor.ref, "base"),
                ),
                render_style="junction",
                role="base_drive",
            ),
            TopologyConnection(
                id="input_coupling",
                point=_point(81.83, 100.0),
                attachments=(TopologyAttachment(signal.ref, "pos"), TopologyAttachment(cb.ref, "left")),
                role="series_inline",
            ),
            TopologyConnection(
                id="collector_node",
                point=collector_node,
                attachments=(
                    TopologyAttachment(rc.ref, "bottom"),
                    TopologyAttachment(transistor.ref, "collector"),
                    TopologyAttachment(cc.ref, "left"),
                ),
                render_style="junction",
                role="collector_node",
            ),
            TopologyConnection(
                id="emitter_node",
                point=emitter_node,
                attachments=(
                    TopologyAttachment(transistor.ref, "emitter"),
                    TopologyAttachment(re.ref, "top"),
                    TopologyAttachment(ce.ref, "top"),
                ),
                render_style="junction",
                role="emitter_node",
            ),
            TopologyConnection(
                id="output_node",
                point=output_node,
                attachments=(TopologyAttachment(cc.ref, "right"), TopologyAttachment(rl.ref, "top")),
                render_style="junction",
                role="stage_output",
            ),
        ]
    )
    return layout


def _build_opamp_inverting_layout(intent: SchematicIntent) -> TopologyLayout | None:
    opamps = [comp for comp in intent.components if comp.kind == "X" and len(comp.nodes) >= 3]
    if len(opamps) != 1:
        return None
    opamp = opamps[0]
    plus_net, minus_net, out_net = opamp.nodes[:3]
    supply_plus_net = opamp.nodes[3] if len(opamp.nodes) >= 4 else None
    supply_minus_net = opamp.nodes[4] if len(opamp.nodes) >= 5 else None
    resistors = [comp for comp in intent.components if comp.kind == "R" and len(comp.nodes) == 2]
    rin = next((comp for comp in resistors if minus_net in comp.nodes and any(intent.nets[node].role == "signal_in" for node in comp.nodes)), None)
    rf = next((comp for comp in resistors if minus_net in comp.nodes and out_net in comp.nodes), None)
    vin = next((comp for comp in intent.components if comp.kind == "V" and comp.nodes[0] in {net for net in opamp.nodes} | {node for comp in resistors for node in comp.nodes}), None)
    if rin is None or rf is None:
        return None

    layout = TopologyLayout(name=intent.name)
    layout.placements.extend(
        [
            TopologyPlacement(ref=opamp.ref, center=_point(170.0, 90.0), orientation="right"),
            TopologyPlacement(ref=rin.ref, center=_point(130.03, 87.46), orientation="horizontal"),
            TopologyPlacement(ref=rf.ref, center=_point(170.0, 68.0), orientation="horizontal"),
            TopologyPlacement(ref="#PWR0001", center=_point(162.38, 104.54), shape="ground", value="GND", orientation="down"),
        ]
    )
    sources = [comp for comp in intent.components if comp.kind == "V"]
    source_y = 60.0
    for idx, source in enumerate(sources, start=2):
        layout.placements.append(TopologyPlacement(ref=source.ref, center=_point(80.0, source_y), orientation="vertical_up"))
        layout.placements.append(TopologyPlacement(ref=f"#PWR{idx:04d}", center=_point(80.0, source_y + 19.62), shape="ground", value="GND", orientation="down"))
        layout.connections.append(
            TopologyConnection(
                id=f"#PWR{idx:04d}:ground",
                point=_point(80.0, source_y + 19.62),
                attachments=(TopologyAttachment(source.ref, "neg"), TopologyAttachment(f"#PWR{idx:04d}", "top")),
                role="local_ground",
            )
        )
        source_y += 40.0

    vin_source = next((source for source in sources if any(intent.nets[node].role == "signal_in" for node in source.nodes)), None)
    supply_plus_source = next((source for source in sources if supply_plus_net is not None and source.nodes[0] == supply_plus_net), None)
    supply_minus_source = next((source for source in sources if supply_minus_net is not None and source.nodes[0] == supply_minus_net), None)
    if vin_source is not None:
        layout.connections.append(
            TopologyConnection(
                id="vin_node",
                point=_point(123.68, 87.46),
                attachments=(TopologyAttachment(vin_source.ref, "pos"), TopologyAttachment(rin.ref, "left")),
                role="series_inline",
            )
        )
    layout.connections.extend(
        [
            TopologyConnection(
                id="plus_ground",
                point=_point(162.38, 104.54),
                attachments=(TopologyAttachment(opamp.ref, "plus"), TopologyAttachment("#PWR0001", "top")),
                role="local_ground",
            ),
            TopologyConnection(
                id="minus_sum",
                point=_point(162.38, 87.46),
                attachments=(
                    TopologyAttachment(rin.ref, "right"),
                    TopologyAttachment(opamp.ref, "minus"),
                    TopologyAttachment(rf.ref, "left"),
                ),
                render_style="junction",
                role="sum_node",
            ),
            TopologyConnection(
                id="feedback_out",
                point=_point(177.62, 90.0),
                attachments=(TopologyAttachment(opamp.ref, "out"), TopologyAttachment(rf.ref, "right")),
                role="stage_output",
            ),
        ]
    )
    if supply_plus_source is not None:
        layout.connections.append(
            TopologyConnection(
                id="supply_plus",
                point=_point(167.46, 82.38),
                attachments=(TopologyAttachment(opamp.ref, "vplus"), TopologyAttachment(supply_plus_source.ref, "pos")),
                role="local_supply",
            )
        )
    if supply_minus_source is not None:
        layout.connections.append(
            TopologyConnection(
                id="supply_minus",
                point=_point(167.46, 97.62),
                attachments=(TopologyAttachment(opamp.ref, "vminus"), TopologyAttachment(supply_minus_source.ref, "pos")),
                role="local_supply",
            )
        )
    if plus_net != "0":
        return None
    return layout


def _find_resistor(resistors: list[IntentComponent], net_a: str, net_b: str) -> IntentComponent | None:
    nets = {net_a, net_b}
    for resistor in resistors:
        if set(resistor.nodes) == nets:
            return resistor
    return None


def _find_capacitor(capacitors: list[IntentComponent], net_a: str, net_b: str) -> IntentComponent | None:
    nets = {net_a, net_b}
    for capacitor in capacitors:
        if set(capacitor.nodes) == nets:
            return capacitor
    return None


def _series_orientation(comp: IntentComponent) -> str:
    if comp.kind in {"R", "L", "D", "C"}:
        return "horizontal"
    return "horizontal"


def _shunt_orientation(comp: IntentComponent) -> str:
    if comp.kind in {"R", "C", "D"}:
        return "vertical"
    return "horizontal"


def _shunt_center_for_output(
    comp: IntentComponent,
    orientation: str,
    output_point: TopologyPoint,
    idx: int,
    total_shunts: int,
) -> TopologyPoint:
    _, terminal_dy = _terminal_offset(comp, orientation, _shunt_terminal_name(comp))
    center_y = output_point.y + 12.0 - terminal_dy
    if total_shunts == 1:
        return _point(output_point.x, center_y)
    spacing = 18.0
    center_x = output_point.x + (idx - (total_shunts + 1) / 2.0) * spacing
    return _point(center_x, center_y)


def _ground_center_for_shunt(comp: IntentComponent, center: TopologyPoint, orientation: str) -> TopologyPoint:
    terminal_dx, terminal_dy = _terminal_offset(comp, orientation, _ground_terminal_name(comp))
    return _point(center.x + terminal_dx, center.y + terminal_dy + 12.0)


def _ground_terminal_name(comp: IntentComponent) -> str:
    return "bottom"


def _shunt_terminal_name(comp: IntentComponent) -> str:
    return "top"


def source_pos(center: TopologyPoint) -> TopologyPoint:
    return TopologyPoint(center.x, round(center.y - 7.62, 2))


def terminal_point(comp: IntentComponent, layout: TopologyLayout, terminal_name: str) -> TopologyPoint:
    placement = next(item for item in layout.placements if item.ref == comp.ref)
    orientation = placement.orientation or _default_orientation(comp)
    dx, dy = _terminal_offset(comp, orientation, terminal_name)
    return TopologyPoint(round(placement.center.x + dx, 2), round(placement.center.y + dy, 2))


def _terminal_offset(comp: IntentComponent, orientation: str, terminal_name: str) -> tuple[float, float]:
    return terminal_offset_for_component(
        comp.kind,
        orientation,
        terminal_name,
        value=comp.value,
        model=comp.model,
    )


def _default_orientation(comp: IntentComponent) -> str:
    return default_orientation_for_component(comp.kind, comp.value, comp.model)


def _point(x: float, y: float) -> TopologyPoint:
    return TopologyPoint(_snap_value(x), _snap_value(y))


def _snap_value(value: float) -> float:
    return round(round(value / KICAD_CONNECTION_GRID) * KICAD_CONNECTION_GRID, 2)
