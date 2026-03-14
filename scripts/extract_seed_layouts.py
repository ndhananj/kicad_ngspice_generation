from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from examples.specs.catalog import _all_circuit_specs
from mixedsig2cad.importers.kicad_schematic import import_kicad_schematic
from mixedsig2cad.models import Point
from mixedsig2cad.spec import CircuitSpec
from mixedsig2cad.symbols import component_symbol, terminal_name_for_component


OUT_PATH = ROOT / "examples" / "specs" / "seeded_layouts.json"
KICAD_DIR = ROOT / "examples" / "generated" / "kicad"
GROUND_NAMES = {"gnd", "0"}


@dataclass(frozen=True, slots=True)
class ImportedComponent:
    key: str
    shape: str
    value: str
    orientation: str
    center: Point
    hidden_reference: bool
    reference_position: Point
    value_position: Point
    terminal_nets: dict[str, str | None]
    node_keys: dict[str, str]


def main() -> None:
    payload = {}
    for spec in _all_circuit_specs():
        payload[spec.name] = extract_seed_layout(spec)
        print(f"extracted {spec.name}")
    OUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def extract_seed_layout(spec: CircuitSpec) -> dict:
    geometry = import_kicad_schematic(KICAD_DIR / f"{spec.name}.kicad_sch")
    node_points = _node_point_sets(geometry)
    node_names = _infer_node_names(geometry, node_points)
    imported_components, support_shapes = _classify_shapes(geometry, node_names)
    ref_by_key = _assign_refs(imported_components, spec)

    shapes_by_ref = {}
    for item in geometry.shapes:
        shapes_by_ref.setdefault(item.ref, []).append(item)
    labels = list(geometry.labels)

    supports = []
    support_index = 1
    support_key_by_node: dict[str, str] = {}
    for shape in support_shapes:
        support_ref = f"#SUPPORT{support_index:04d}"
        support_index += 1
        supports.append(
            {
                "ref": support_ref,
                "shape": shape.shape,
                "value": shape.value,
                "center": _point_to_payload(shape.center),
                "orientation": shape.orientation,
                "reference_position": _point_to_payload(_default_support_text_position(shape.center, "reference")),
                "value_position": _point_to_payload(_default_support_text_position(shape.center, "value")),
                "hidden_reference": shape.hidden_reference,
            }
        )
        for terminal in shape.terminals:
            for node in geometry.nodes:
                if any(a.owner_ref == shape.ref and a.terminal_name == terminal.name for a in node.attachments):
                    support_key_by_node[node.id] = _normalize_net_name(shape.value)

    components = []
    for imported in imported_components:
        ref = ref_by_key[imported.key]
        components.append(
            {
                "ref": ref,
                "center": _point_to_payload(imported.center),
                "orientation": imported.orientation,
                "reference_position": _point_to_payload(imported.reference_position),
                "value_position": _point_to_payload(imported.value_position),
                "hidden_reference": imported.hidden_reference,
            }
        )

    routed_nets = []
    wires_by_name: dict[str, list[list[dict[str, float]]]] = defaultdict(list)
    junctions_by_name: dict[str, list[dict[str, float]]] = defaultdict(list)
    wire_name_by_signature = _wire_names(geometry, node_points, imported_components, ref_by_key, spec, support_key_by_node)
    for wire in geometry.wires:
        name = wire_name_by_signature.get(_wire_signature(wire), wire.uuid_seed)
        wires_by_name[name].append([_point_to_payload(point) for point in wire.points])
    for junction in geometry.junctions:
        name = wire_name_by_signature.get((junction.point.x, junction.point.y), f"junction:{junction.point.x}:{junction.point.y}")
        junctions_by_name[name].append(_point_to_payload(junction.point))
    for name in sorted(set(wires_by_name) | set(junctions_by_name)):
        routed_nets.append({"name": name, "segments": wires_by_name.get(name, []), "junctions": junctions_by_name.get(name, [])})

    texts = [
        {
            "text": label.text,
            "role": label.role,
            "position": _point_to_payload(label.position),
            "owner_ref": label.owner_ref,
            "font_size": label.font_size,
        }
        for label in geometry.labels
        if label.role == "net_label"
    ]
    return {
        "name": spec.name,
        "components": components,
        "supports": supports,
        "texts": texts,
        "routed_nets": routed_nets,
    }


def _infer_node_names(geometry, node_points: dict[str, set[tuple[float, float]]]) -> dict[str, str | None]:
    names: dict[str, str | None] = {}
    for node in geometry.nodes:
        candidates = set()
        for label in geometry.labels:
            if label.role == "net_label" and (label.position.x, label.position.y) in node_points[node.id]:
                candidates.add(_normalize_net_name(label.text))
        for attachment in node.attachments:
            shape = next((shape for shape in geometry.shapes if shape.ref == attachment.owner_ref), None)
            if shape is None:
                continue
            if shape.shape == "ground":
                candidates.add(_normalize_net_name(shape.value))
        names[node.id] = sorted(candidates)[0] if candidates else None
    return names


def _classify_shapes(geometry, node_names: dict[str, str | None]) -> tuple[list[ImportedComponent], list]:
    imported: list[ImportedComponent] = []
    supports = []
    occurrence = defaultdict(int)
    for shape in geometry.shapes:
        if shape.shape in {"ground", "power"}:
            supports.append(shape)
            continue
        occurrence[shape.ref] += 1
        key = f"{shape.ref}:{occurrence[shape.ref]}"
        terminal_nets: dict[str, str | None] = {}
        node_keys: dict[str, str] = {}
        for terminal in shape.terminals:
            for node in geometry.nodes:
                if any(a.owner_ref == shape.ref and a.terminal_name == terminal.name for a in node.attachments):
                    terminal_nets[terminal.name] = node_names[node.id]
                    node_keys[terminal.name] = node.id
                    break
            else:
                terminal_nets[terminal.name] = None
        reference_label = _shape_property_label(shape, geometry.labels, "reference")
        value_label = _shape_property_label(shape, geometry.labels, "value")
        imported.append(
            ImportedComponent(
                key=key,
                shape=shape.shape,
                value=shape.value,
                orientation=shape.orientation,
                center=shape.center,
                hidden_reference=shape.hidden_reference,
                reference_position=reference_label.position,
                value_position=value_label.position,
                terminal_nets=terminal_nets,
                node_keys=node_keys,
            )
        )
    return imported, supports


def _assign_refs(imported: list[ImportedComponent], spec: CircuitSpec) -> dict[str, str]:
    candidates = {}
    for item in imported:
        item_candidates = []
        for component in spec.components:
            shape, _ = component_symbol(component.kind, component.value, component.model)
            if shape != item.shape or component.value != item.value:
                continue
            if _component_matches_known_nets(component, item):
                item_candidates.append(component.ref)
        if not item_candidates:
            raise AssertionError(f"no CircuitSpec candidate for imported component {item}")
        candidates[item.key] = item_candidates

    ordered = sorted(imported, key=lambda item: (len(candidates[item.key]), item.center.x, item.center.y))
    used: set[str] = set()
    assigned: dict[str, str] = {}

    def search(index: int) -> bool:
        if index == len(ordered):
            return True
        item = ordered[index]
        for ref in candidates[item.key]:
            if ref in used:
                continue
            assigned[item.key] = ref
            used.add(ref)
            if _partial_assignment_is_consistent(imported, assigned, spec) and search(index + 1):
                return True
            used.remove(ref)
            assigned.pop(item.key, None)
        return False

    if not search(0):
        heuristic = _heuristic_ref_assignment(imported, spec)
        if heuristic is not None:
            return heuristic
        raise AssertionError(f"failed to map imported components for {spec.name}")
    return assigned


def _component_matches_known_nets(component, item: ImportedComponent) -> bool:
    return bool(_component_terminal_net_maps(component, item))


def _partial_assignment_is_consistent(imported: list[ImportedComponent], assigned: dict[str, str], spec: CircuitSpec) -> bool:
    spec_by_ref = {component.ref: component for component in spec.components}
    expected_by_node: dict[str, set[str]] = defaultdict(set)
    for item in imported:
        ref = assigned.get(item.key)
        if ref is None:
            continue
        component = spec_by_ref[ref]
        net_maps = _component_terminal_net_maps(component, item)
        if not net_maps:
            return False
        net_map = net_maps[0]
        for terminal, net_name in net_map.items():
            node_key = item.node_keys.get(terminal)
            if node_key is not None:
                expected_by_node[node_key].add(net_name)
    for names in expected_by_node.values():
        non_global = {name for name in names if name.lower() not in {"0", "gnd", "vcc", "vdd", "vee", "vss"}}
        if len(non_global) > 1:
            return False
    return True


def _wire_names(geometry, node_points: dict[str, set[tuple[float, float]]], imported: list[ImportedComponent], ref_by_key: dict[str, str], spec: CircuitSpec, support_key_by_node: dict[str, str]) -> dict:
    spec_by_ref = {component.ref: component for component in spec.components}
    net_by_node: dict[str, str] = {}
    for item in imported:
        ref = ref_by_key[item.key]
        component = spec_by_ref[ref]
        for terminal, net_name in _component_terminal_net_maps(component, item)[0].items():
            node_key = item.node_keys.get(terminal)
            if node_key is not None:
                net_by_node[node_key] = net_name
    net_by_node.update(support_key_by_node)
    for node in geometry.nodes:
        for label in geometry.labels:
            if label.role == "net_label" and (label.position.x, label.position.y) in node_points[node.id]:
                net_by_node[node.id] = _normalize_net_name(label.text)

    result = {}
    for wire in geometry.wires:
        name = wire.uuid_seed
        for node in geometry.nodes:
            if set(_wire_signature(wire)) & node_points[node.id]:
                name = net_by_node.get(node.id, name)
                break
        result[_wire_signature(wire)] = name
    for junction in geometry.junctions:
        name = f"junction:{junction.point.x}:{junction.point.y}"
        for node in geometry.nodes:
            if (junction.point.x, junction.point.y) == (node.point.x, node.point.y):
                name = net_by_node.get(node.id, name)
                break
        result[(junction.point.x, junction.point.y)] = name
    return result


def _wire_signature(wire) -> tuple[tuple[float, float], ...]:
    return tuple((point.x, point.y) for point in wire.points)


def _node_point_sets(geometry) -> dict[str, set[tuple[float, float]]]:
    terminals_by_point: dict[tuple[float, float], list[tuple[str, str]]] = defaultdict(list)
    for shape in geometry.shapes:
        for terminal in shape.terminals:
            terminals_by_point[(terminal.point.x, terminal.point.y)].append((shape.ref, terminal.name))

    graph: dict[tuple[float, float], set[tuple[float, float]]] = defaultdict(set)
    for wire in geometry.wires:
        for start, end in zip(wire.points, wire.points[1:]):
            a = (start.x, start.y)
            b = (end.x, end.y)
            graph[a].add(b)
            graph[b].add(a)
    for point in terminals_by_point:
        graph.setdefault(point, set())
    for junction in geometry.junctions:
        graph.setdefault((junction.point.x, junction.point.y), set())

    node_points: dict[str, set[tuple[float, float]]] = {}
    remaining = {node.id: set((attachment.owner_ref, attachment.terminal_name) for attachment in node.attachments) for node in geometry.nodes}
    visited: set[tuple[float, float]] = set()
    index = 1
    for point in graph:
        if point in visited:
            continue
        stack = [point]
        component: set[tuple[float, float]] = set()
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            component.add(current)
            stack.extend(graph[current] - visited)
        attachments = set()
        for item in component:
            attachments.update(terminals_by_point.get(item, ()))
        if len(attachments) < 2:
            continue
        node_id = next((key for key, value in remaining.items() if value == attachments), f"derived:{index}")
        node_points[node_id] = component
        index += 1
    return node_points


def _normalize_net_name(name: str) -> str:
    lowered = name.strip().lower()
    if lowered in GROUND_NAMES:
        return "0"
    return lowered


def _point_to_payload(point: Point) -> dict[str, float]:
    return {"x": point.x, "y": point.y}


def _default_support_text_position(center: Point, role: str) -> Point:
    return Point(center.x, center.y - 3.81) if role == "reference" else Point(center.x, center.y + 3.81)


def _shape_property_label(shape, labels, role: str):
    candidates = [label for label in labels if label.owner_ref == shape.ref and label.role == role]
    if not candidates:
        raise AssertionError(f"missing {role} label for {shape.ref}")
    return min(candidates, key=lambda label: (abs(label.position.x - shape.center.x) + abs(label.position.y - shape.center.y)))


def _component_terminal_net_maps(component, item: ImportedComponent) -> list[dict[str, str]]:
    direct = {
        terminal_name_for_component(component.kind, item.orientation, pin_index): _normalize_net_name(net_name)
        for pin_index, net_name in enumerate(component.nodes)
    }
    if component.kind == "Q":
        direct["substrate"] = "0"
    candidates = [direct]
    if component.kind in {"R", "C", "L"} and len(component.nodes) == 2:
        reversed_map = {
            terminal_name_for_component(component.kind, item.orientation, 0): _normalize_net_name(component.nodes[1]),
            terminal_name_for_component(component.kind, item.orientation, 1): _normalize_net_name(component.nodes[0]),
        }
        candidates.append(reversed_map)
    result = []
    ignored_terminals = {"vplus", "vminus"} if component.kind == "X" else set()
    for mapping in candidates:
        if all(
            terminal in ignored_terminals or item.terminal_nets.get(terminal) in {None, net_name}
            for terminal, net_name in mapping.items()
        ):
            result.append(mapping)
    if not result and component.kind in {"V", "I"}:
        return [direct]
    return result


def _heuristic_ref_assignment(imported: list[ImportedComponent], spec: CircuitSpec) -> dict[str, str] | None:
    if spec.name != "schmitt_trigger":
        return None
    assigned: dict[str, str] = {}
    resistor_items = sorted((item for item in imported if item.shape == "resistor"), key=lambda item: (item.center.x, item.center.y))
    horizontal = [item for item in resistor_items if item.orientation == "horizontal"]
    vertical = [item for item in resistor_items if item.orientation == "vertical"]
    if len(horizontal) == 1 and len(vertical) == 2:
        assigned[horizontal[0].key] = "R3"
        vertical = sorted(vertical, key=lambda item: item.center.y)
        assigned[vertical[0].key] = "R1"
        assigned[vertical[1].key] = "R2"
    for item in imported:
        if item.key in assigned:
            continue
        for component in spec.components:
            shape, _ = component_symbol(component.kind, component.value, component.model)
            if component.ref in assigned.values():
                continue
            if shape == item.shape and component.value == item.value:
                assigned[item.key] = component.ref
                break
    return assigned if len(assigned) == len(imported) else None


if __name__ == "__main__":
    main()
