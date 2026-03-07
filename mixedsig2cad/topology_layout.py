from __future__ import annotations

from dataclasses import dataclass, field

from .intent import IntentComponent, SchematicIntent


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


TERMINAL_OFFSETS: dict[tuple[str, str], dict[str, tuple[float, float]]] = {
    ("V", "vertical_up"): {"pos": (0.0, -7.62), "neg": (0.0, 7.62)},
    ("R", "horizontal"): {"left": (-6.35, 0.0), "right": (6.35, 0.0)},
    ("R", "vertical"): {"top": (0.0, -6.35), "bottom": (0.0, 6.35)},
    ("C", "horizontal"): {"left": (-6.35, 0.0), "right": (6.35, 0.0)},
    ("C", "vertical"): {"top": (0.0, -6.35), "bottom": (0.0, 6.35)},
    ("L", "horizontal"): {"left": (-6.35, 0.0), "right": (6.35, 0.0)},
    ("D", "horizontal"): {"left": (-5.08, 0.0), "right": (5.08, 0.0)},
    ("D", "vertical"): {"top": (0.0, -5.08), "bottom": (0.0, 5.08)},
    ("Q", "right"): {"collector": (3.81, -8.89), "base": (-7.62, 0.0), "emitter": (3.81, 8.89)},
    ("ground", "down"): {"top": (0.0, 0.0)},
}


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
    supply_sources = [comp for comp in intent.components if comp.kind == "V" and len(comp.nodes) == 2 and intent.nets[comp.nodes[1]].role == "ground" and intent.nets[comp.nodes[0]].role == "supply"]
    if len(supply_sources) != 1:
        return None
    supply = supply_sources[0]
    supply_net = supply.nodes[0]

    rc = _find_resistor(resistors, supply_net, collector_net)
    re = _find_resistor(resistors, emitter_net, "0")
    rb = _find_resistor(resistors, supply_net, base_net)
    if rc is None or re is None or rb is None:
        return None

    layout = TopologyLayout(name=intent.name)
    transistor_center = TopologyPoint(170.0, 100.0)
    collector_x = 173.81
    base_x = 156.38
    vcc_y = 68.41
    layout.placements.extend(
        [
            TopologyPlacement(ref=supply.ref, center=TopologyPoint(215.0, 76.03), orientation="vertical_up"),
            TopologyPlacement(ref=transistor.ref, center=transistor_center, orientation="right"),
            TopologyPlacement(ref=rc.ref, center=TopologyPoint(collector_x, 84.76), orientation="vertical"),
            TopologyPlacement(ref=re.ref, center=TopologyPoint(collector_x, 115.24), orientation="vertical"),
            TopologyPlacement(ref=rb.ref, center=TopologyPoint(base_x, 74.76), orientation="vertical"),
            TopologyPlacement(ref="#PWR0001", center=TopologyPoint(215.0, 95.65), shape="ground", value="GND", orientation="down"),
            TopologyPlacement(ref="#PWR0002", center=TopologyPoint(collector_x, 133.59), shape="ground", value="GND", orientation="down"),
        ]
    )
    floating_sources = [comp for comp in intent.components if comp.kind == "V" and comp.ref != supply.ref]
    for idx, source in enumerate(floating_sources, start=3):
        center = TopologyPoint(95.0, 107.62 + (idx - 3) * 36.0)
        gnd_center = TopologyPoint(center.x, center.y + 19.62)
        layout.placements.append(TopologyPlacement(ref=source.ref, center=center, orientation="vertical_up"))
        layout.placements.append(TopologyPlacement(ref=f"#PWR{idx:04d}", center=gnd_center, shape="ground", value="GND", orientation="down"))
        layout.connections.append(
            TopologyConnection(
                id=f"#PWR{idx:04d}:ground",
                point=_point(gnd_center.x, gnd_center.y),
                attachments=(TopologyAttachment(source.ref, "neg"), TopologyAttachment(f"#PWR{idx:04d}", "top")),
                role="local_ground",
            )
        )

    base_attachments = [TopologyAttachment(rb.ref, "bottom"), TopologyAttachment(transistor.ref, "base")]
    for source in floating_sources:
        if any(intent.nets[node].role == "signal_in" for node in source.nodes):
            base_attachments.append(TopologyAttachment(source.ref, "pos"))

    layout.connections.extend(
        [
            TopologyConnection(
                id="supply_ground",
                point=_point(215.0, 95.65),
                attachments=(TopologyAttachment(supply.ref, "neg"), TopologyAttachment("#PWR0001", "top")),
                role="local_ground",
            ),
            TopologyConnection(
                id="emitter_ground",
                point=_point(collector_x, 133.59),
                attachments=(TopologyAttachment(re.ref, "bottom"), TopologyAttachment("#PWR0002", "top")),
                role="local_ground",
            ),
            TopologyConnection(
                id="vcc_node",
                point=_point(collector_x, vcc_y),
                attachments=(
                    TopologyAttachment(supply.ref, "pos"),
                    TopologyAttachment(rc.ref, "top"),
                    TopologyAttachment(rb.ref, "top"),
                ),
                render_style="junction",
                role="local_supply",
            ),
            TopologyConnection(
                id="collector_node",
                point=_point(collector_x, 91.11),
                attachments=(TopologyAttachment(rc.ref, "bottom"), TopologyAttachment(transistor.ref, "collector")),
                role="collector_node",
            ),
            TopologyConnection(
                id="base_node",
                point=_point(base_x, 100.0),
                attachments=tuple(base_attachments),
                render_style="junction",
                role="base_drive",
            ),
            TopologyConnection(
                id="emitter_node",
                point=_point(collector_x, 108.89),
                attachments=(TopologyAttachment(transistor.ref, "emitter"), TopologyAttachment(re.ref, "top")),
                role="emitter_node",
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
    resistors = [comp for comp in intent.components if comp.kind == "R" and len(comp.nodes) == 2]
    rin = next((comp for comp in resistors if minus_net in comp.nodes and any(intent.nets[node].role == "signal_in" for node in comp.nodes)), None)
    rf = next((comp for comp in resistors if minus_net in comp.nodes and out_net in comp.nodes), None)
    vin = next((comp for comp in intent.components if comp.kind == "V" and comp.nodes[0] in {net for net in opamp.nodes} | {node for comp in resistors for node in comp.nodes}), None)
    if rin is None or rf is None:
        return None

    layout = TopologyLayout(name=intent.name)
    layout.placements.extend(
        [
            TopologyPlacement(ref=opamp.ref, center=TopologyPoint(170.0, 90.0), orientation="right"),
            TopologyPlacement(ref=rin.ref, center=TopologyPoint(130.03, 87.46), orientation="horizontal"),
            TopologyPlacement(ref=rf.ref, center=TopologyPoint(170.0, 68.0), orientation="horizontal"),
            TopologyPlacement(ref="#PWR0001", center=TopologyPoint(162.38, 104.54), shape="ground", value="GND", orientation="down"),
        ]
    )
    sources = [comp for comp in intent.components if comp.kind == "V"]
    source_y = 60.0
    for idx, source in enumerate(sources, start=2):
        layout.placements.append(TopologyPlacement(ref=source.ref, center=TopologyPoint(80.0, source_y), orientation="vertical_up"))
        layout.placements.append(TopologyPlacement(ref=f"#PWR{idx:04d}", center=TopologyPoint(80.0, source_y + 19.62), shape="ground", value="GND", orientation="down"))
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
    return layout


def _find_resistor(resistors: list[IntentComponent], net_a: str, net_b: str) -> IntentComponent | None:
    nets = {net_a, net_b}
    for resistor in resistors:
        if set(resistor.nodes) == nets:
            return resistor
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
    return TERMINAL_OFFSETS[(comp.kind, orientation)][terminal_name]


def _default_orientation(comp: IntentComponent) -> str:
    return {
        "V": "vertical_up",
        "R": "horizontal",
        "C": "vertical",
        "L": "horizontal",
        "D": "horizontal",
        "Q": "right",
        "X": "right",
    }.get(comp.kind, "horizontal")


def _point(x: float, y: float) -> TopologyPoint:
    return TopologyPoint(round(x, 2), round(y, 2))
