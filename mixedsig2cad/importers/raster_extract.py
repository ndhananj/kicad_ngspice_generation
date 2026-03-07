from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from mixedsig2cad.compiled import CompiledSchematic, make_body_box, make_terminals
from mixedsig2cad.geometry import (
    JunctionPlacement,
    Point,
    PlacedShape,
    TextPlacement,
    WirePath,
)
from mixedsig2cad.importers.kicad_schematic import _derive_nodes
from mixedsig2cad.importers.raster_observation import DrawingObservation, ObservedJunction, ObservedSymbol, ObservedWire
from mixedsig2cad.symbols import default_orientation_for_shape

_ACTIVE_SYMBOL_KINDS = {"opamp", "npn_bjt", "pmos", "nmos"}
_PIN_LABELS_BY_KIND = {
    "voltage_source": {"E1", "E2"},
    "current_source": {"E1", "E2"},
    "diode": {"A", "K"},
    "opamp": {"+", "-", "V+", "V-", "~"},
    "npn_bjt": {"B", "C", "E"},
    "pmos": {"G", "D", "S", "B"},
    "nmos": {"G", "D", "S", "B"},
}


def extract_geometry_from_image(path: str | Path, *, mode: str = "kicad_raster") -> CompiledSchematic:
    image_path = Path(path)
    if image_path.suffix.lower() == ".svg":
        observation = observe_kicad_svg(image_path)
        return _observation_to_geometry(observation, image_path.stem)
    raise NotImplementedError(
        "Raster bitmap extraction is not implemented yet; use KiCad-exported SVG images for exact image extraction."
    )


def observe_kicad_svg(path: str | Path) -> DrawingObservation:
    root = ET.fromstring(Path(path).read_text(encoding="utf-8"))
    texts = _svg_texts(root)
    wires = tuple(ObservedWire(points=wire, confidence=1.0) for wire in _svg_wires(root))
    junctions = tuple(ObservedJunction(point=point, confidence=1.0) for point in _wire_junctions(wires))
    symbols = tuple(_infer_svg_symbols(texts, wires))
    return DrawingObservation(symbols=symbols, wires=wires, junctions=junctions, source_kind="kicad_svg")


def _observation_to_geometry(observation: DrawingObservation, name: str) -> CompiledSchematic:
    geometry = CompiledSchematic(name=name)
    for symbol in observation.symbols:
        if symbol.kind == "ground":
            value = symbol.value_text or "GND"
            ref = symbol.ref_text or f"#PWRGND{len(geometry.shapes) + 1:04d}"
            shape_name = "ground"
            orientation = "down"
        elif symbol.kind == "power":
            value = symbol.value_text or "VCC"
            ref = symbol.ref_text or f"#PWRVCC{len(geometry.shapes) + 1:04d}"
            shape_name = "power"
            orientation = "up"
        else:
            ref = symbol.ref_text or f"SYM{len(geometry.shapes) + 1}"
            value = symbol.value_text or ""
            shape_name = symbol.kind
            orientation = symbol.orientation or _default_orientation(shape_name)
        shape = PlacedShape(
            ref=ref,
            value=value,
            shape=shape_name,
            orientation=orientation,
            center=symbol.center,
            terminals=make_terminals(shape_name, orientation, symbol.center),
            body_box=make_body_box(shape_name, orientation, symbol.center),
            hidden_reference=ref.startswith("#PWR"),
        )
        geometry.shapes.append(shape)
        if symbol.ref_text is not None and not shape.hidden_reference:
            geometry.labels.append(
                TextPlacement(
                    text=symbol.ref_text,
                    role="reference",
                    position=Point(shape.center.x, round(shape.center.y - 10.0, 2)),
                    owner_ref=shape.ref,
                    uuid_seed=f"{name}:{shape.ref}:reference:image",
                )
            )
        if symbol.value_text is not None:
            geometry.labels.append(
                TextPlacement(
                    text=symbol.value_text,
                    role="value",
                    position=Point(shape.center.x, round(shape.center.y + 10.0, 2)),
                    owner_ref=shape.ref,
                    uuid_seed=f"{name}:{shape.ref}:value:image",
                )
            )

    geometry.wires.extend(
        WirePath(points=wire.points, uuid_seed=f"{name}:image:wire:{idx}")
        for idx, wire in enumerate(observation.wires, start=1)
    )
    geometry.junctions.extend(JunctionPlacement(point=junction.point) for junction in observation.junctions)
    geometry.nodes.extend(_derive_nodes(geometry.shapes, geometry.wires, geometry.junctions))
    return geometry


def _svg_texts(root: ET.Element) -> list[tuple[str, Point]]:
    texts: list[tuple[str, Point]] = []
    for text in root.iter():
        if not text.tag.endswith("text"):
            continue
        content = (text.text or "").strip()
        if not content:
            continue
        try:
            x = round(float(text.attrib.get("x", "0")), 2)
            y = round(float(text.attrib.get("y", "0")), 2)
        except ValueError:
            continue
        if _is_noise_text(content, x, y):
            continue
        texts.append((content, Point(x, y)))
    return texts


def _svg_wires(root: ET.Element) -> list[tuple[Point, ...]]:
    wires: list[tuple[Point, ...]] = []
    current_wire_group = False
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag == "g":
            style = element.attrib.get("style", "")
            current_wire_group = "stroke:#009600" in style
            continue
        if tag != "path" or not current_wire_group:
            continue
        path = element.attrib.get("d", "")
        points = _parse_svg_path_points(path)
        if len(points) >= 2:
            wires.append(points)
    return wires


def _parse_svg_path_points(path: str) -> tuple[Point, ...]:
    coords = [float(value) for value in re.findall(r"[-0-9.]+", path)]
    if len(coords) < 4:
        return ()
    return tuple(Point(round(coords[idx], 2), round(coords[idx + 1], 2)) for idx in range(0, len(coords), 2))


def _wire_junctions(wires: tuple[ObservedWire, ...]) -> list[Point]:
    counts: dict[tuple[float, float], int] = {}
    for wire in wires:
        for point in wire.points:
            counts[(point.x, point.y)] = counts.get((point.x, point.y), 0) + 1
    return [Point(x, y) for (x, y), count in counts.items() if count >= 3]


def _infer_svg_symbols(texts: list[tuple[str, Point]], wires: tuple[ObservedWire, ...]) -> list[ObservedSymbol]:
    symbols: list[ObservedSymbol] = []
    used_texts: set[int] = set()

    for idx, (content, point) in enumerate(texts):
        if idx in used_texts:
            continue
        if content in {"GND", "VCC", "VDD", "VEE", "VSS"}:
            anchor = _nearest_wire_point(point, wires, radius=14.0)
            if anchor is None:
                continue
            kind = "ground" if content == "GND" else "power"
            symbols.append(ObservedSymbol(kind=kind, center=anchor, orientation="down" if kind == "ground" else "up", confidence=0.9, value_text=content))
            used_texts.add(idx)
            continue
        if not _looks_like_reference(content):
            continue
        kind = _shape_from_reference(content)
        if kind is None:
            continue
        value_idx, value_point, value_text = _nearest_value_text(idx, texts, kind)
        center_seed = point if kind in _ACTIVE_SYMBOL_KINDS else (value_point or point)
        center = _estimate_center(point, center_seed)
        orientation = _best_orientation(kind, center, wires)
        if kind in _ACTIVE_SYMBOL_KINDS:
            center = _fit_center_from_wires(kind, orientation, point, wires) or center
        center = _refine_center(kind, orientation, center, wires)
        symbols.append(
            ObservedSymbol(
                kind=kind,
                center=center,
                orientation=orientation,
                confidence=0.85,
                ref_text=content,
                value_text=value_text,
                terminal_hints=_terminal_hints(kind, orientation, center, wires),
            )
        )
        used_texts.add(idx)
        if value_idx is not None:
            used_texts.add(value_idx)
    return symbols


def _looks_like_reference(text: str) -> bool:
    return bool(re.match(r"^(R|C|L|D|Q|M|XU|U|V)[A-Za-z0-9]+$", text))


def _shape_from_reference(text: str) -> str | None:
    if text.startswith("R"):
        return "resistor"
    if text.startswith("C"):
        return "capacitor"
    if text.startswith("L"):
        return "inductor"
    if text.startswith("D"):
        return "diode"
    if text.startswith("Q"):
        return "npn_bjt"
    if text.startswith("M"):
        return "nmos"
    if text.startswith("XU") or text.startswith("U"):
        return "opamp"
    if text.startswith("V"):
        return "voltage_source"
    return None


def _nearest_value_text(index: int, texts: list[tuple[str, Point]], kind: str) -> tuple[int | None, Point | None, str | None]:
    content, point = texts[index]
    best: tuple[float, int, Point, str] | None = None
    excluded_pin_labels = _PIN_LABELS_BY_KIND.get(kind, set())
    for other_idx, (other_text, other_point) in enumerate(texts):
        if other_idx == index or _looks_like_reference(other_text):
            continue
        if _is_pin_number(other_text):
            continue
        if other_text in excluded_pin_labels:
            continue
        if kind in _ACTIVE_SYMBOL_KINDS and _looks_like_passive_value(other_text):
            continue
        distance = ((point.x - other_point.x) ** 2 + (point.y - other_point.y) ** 2) ** 0.5
        if distance > 16.0:
            continue
        candidate = (distance, other_idx, other_point, other_text)
        if best is None or candidate < best:
            best = candidate
    if best is None:
        return None, None, None
    _, other_idx, other_point, other_text = best
    return other_idx, other_point, other_text


def _estimate_center(reference: Point, value: Point) -> Point:
    if reference == value:
        return reference
    return Point(round((reference.x + value.x) / 2.0, 2), round((reference.y + value.y) / 2.0, 2))


def _best_orientation(kind: str, center: Point, wires: tuple[ObservedWire, ...]) -> str:
    orientations = {
        "resistor": ("horizontal", "vertical"),
        "capacitor": ("horizontal", "vertical"),
        "diode": ("horizontal", "vertical"),
        "ground": ("down",),
        "power": ("up",),
        "voltage_source": ("vertical_up",),
        "current_source": ("vertical_up",),
        "inductor": ("horizontal",),
        "opamp": ("right",),
        "npn_bjt": ("right",),
        "nmos": ("right",),
        "pmos": ("right",),
    }[kind]
    best_orientation = orientations[0]
    best_score = -1
    for orientation in orientations:
        terminals = make_terminals(kind, orientation, center)
        score = sum(1 for terminal in terminals if _nearest_wire_point(terminal.point, wires, radius=3.0) is not None)
        if score > best_score:
            best_score = score
            best_orientation = orientation
    return best_orientation


def _refine_center(kind: str, orientation: str, center: Point, wires: tuple[ObservedWire, ...]) -> Point:
    estimates: list[Point] = []
    for terminal in make_terminals(kind, orientation, center):
        match = _nearest_wire_point(terminal.point, wires, radius=3.0)
        if match is None:
            continue
        estimates.append(Point(round(match.x - (terminal.point.x - center.x), 2), round(match.y - (terminal.point.y - center.y), 2)))
    if not estimates:
        return center
    return Point(
        round(sum(point.x for point in estimates) / len(estimates), 2),
        round(sum(point.y for point in estimates) / len(estimates), 2),
    )


def _fit_center_from_wires(kind: str, orientation: str, reference: Point, wires: tuple[ObservedWire, ...]) -> Point | None:
    candidates: dict[tuple[float, float], tuple[int, float]] = {}
    templates = make_terminals(kind, orientation, Point(0.0, 0.0))
    wire_points = [point for wire in wires for point in wire.points]
    if not wire_points:
        return None
    for wire_point in wire_points:
        for terminal in templates:
            center = Point(round(wire_point.x - terminal.point.x, 2), round(wire_point.y - terminal.point.y, 2))
            score = sum(
                1 for probe in make_terminals(kind, orientation, center)
                if _nearest_wire_point(probe.point, wires, radius=4.0) is not None
            )
            if score == 0:
                continue
            distance = ((center.x - reference.x) ** 2 + (center.y - reference.y) ** 2) ** 0.5
            key = (center.x, center.y)
            best = candidates.get(key)
            if best is None or score > best[0] or (score == best[0] and distance < best[1]):
                candidates[key] = (score, distance)
    if not candidates:
        return None
    best_center, _ = max(candidates.items(), key=lambda item: (item[1][0], -item[1][1]))
    return Point(best_center[0], best_center[1])


def _nearest_wire_point(target: Point, wires: tuple[ObservedWire, ...], *, radius: float) -> Point | None:
    best: tuple[float, Point] | None = None
    for wire in wires:
        for point in wire.points:
            distance = ((point.x - target.x) ** 2 + (point.y - target.y) ** 2) ** 0.5
            if distance > radius:
                continue
            if best is None or distance < best[0]:
                best = (distance, point)
    return None if best is None else best[1]


def _default_orientation(shape_name: str) -> str:
    return default_orientation_for_shape(shape_name)


def _terminal_hints(
    kind: str,
    orientation: str,
    center: Point,
    wires: tuple[ObservedWire, ...],
) -> dict[str, str] | None:
    if kind not in {"npn_bjt", "opamp", "pmos", "nmos"}:
        return None
    hints: dict[str, str] = {}
    for terminal in make_terminals(kind, orientation, center):
        point = _nearest_wire_point(terminal.point, wires, radius=4.0) or terminal.point
        hints[terminal.name] = _relative_side(center, point)
    return hints


def _relative_side(center: Point, point: Point) -> str:
    dx = point.x - center.x
    dy = point.y - center.y
    if abs(dx) >= abs(dy):
        return "right" if dx >= 0 else "left"
    return "bottom" if dy >= 0 else "top"


def _is_pin_number(text: str) -> bool:
    return bool(re.fullmatch(r"\d+", text))


def _looks_like_passive_value(text: str) -> bool:
    return bool(re.fullmatch(r"[0-9.]+(?:[fpnumkMGT]|meg)?(?:[A-Za-z0-9()]*)?", text))


def _is_noise_text(text: str, x: float, y: float) -> bool:
    if _is_pin_number(text):
        return True
    if len(text) == 1 and text in "ABCD12345":
        return True
    if y < 25.0 or x < 20.0:
        return True
    return False
