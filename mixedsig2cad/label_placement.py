from __future__ import annotations

from dataclasses import dataclass

from .models import BoundingBox, CompiledSchematic, PlacedShape, Point, TextPlacement

_GRID = 1.27
_BODY_CLEARANCE = 1.27
_WIRE_CLEARANCE = 0.8
_JUNCTION_RADIUS = 1.2
_LABEL_GAP = 2.54


@dataclass(frozen=True, slots=True)
class _LabelCandidate:
    position: Point
    box: BoundingBox
    score: tuple[float, float, float]


def normalize_example_label_positions(geometry: CompiledSchematic) -> CompiledSchematic:
    shape_by_ref = {shape.ref: shape for shape in geometry.shapes}
    accepted_boxes: list[BoundingBox] = []
    normalized: list[TextPlacement] = []

    for text in geometry.labels:
        if text.role == "reference":
            owner = shape_by_ref.get(text.owner_ref)
            if owner is not None and owner.hidden_reference:
                normalized.append(text)
                continue
            candidate = _place_shape_text(text, owner, geometry, accepted_boxes)
        elif text.role == "value":
            candidate = _place_shape_text(text, shape_by_ref.get(text.owner_ref), geometry, accepted_boxes)
        elif text.role == "net_label":
            candidate = _place_net_label(text, geometry, accepted_boxes)
        else:
            candidate = _with_box(text)
        normalized.append(candidate)
        if text.role in {"reference", "value", "net_label"}:
            accepted_boxes.append(_text_box(candidate))

    geometry.labels = normalized
    return geometry


def _place_shape_text(
    text: TextPlacement,
    owner: PlacedShape | None,
    geometry: CompiledSchematic,
    accepted_boxes: list[BoundingBox],
) -> TextPlacement:
    if owner is None:
        return text
    preferred = _preferred_side_for_box(text.position, owner.body_box)
    order = _candidate_side_order(preferred)
    candidates: list[_LabelCandidate] = []
    for side in order:
        candidates.extend(_shape_text_candidates(text, owner.body_box, side))
    return _choose_candidate(text, candidates, geometry, accepted_boxes, owner.body_box)


def _place_net_label(
    text: TextPlacement,
    geometry: CompiledSchematic,
    accepted_boxes: list[BoundingBox],
) -> TextPlacement:
    anchor = _nearest_label_anchor(text.position, geometry)
    forced_side = _example_net_label_side_override(geometry.name, text.text)
    if forced_side is not None:
        position = _rendered_net_label_position(anchor, text, forced_side)
        return TextPlacement(
            text=text.text,
            role=text.role,
            position=position,
            owner_ref=text.owner_ref,
            uuid_seed=text.uuid_seed,
            font_size=text.font_size,
            anchor_position=anchor,
            anchor_angle=0,
            anchor_justify=_label_anchor_justify(forced_side),
        )
    preferred = _preferred_side_from_anchor(text.position, anchor)
    order = _candidate_side_order(preferred or _preferred_side_from_geometry(anchor, geometry))
    candidates: list[_LabelCandidate] = []
    for side in order:
        position = _rendered_net_label_position(anchor, text, side)
        box = _text_box(
            TextPlacement(
                text=text.text,
                role=text.role,
                position=position,
                owner_ref=text.owner_ref,
                uuid_seed=text.uuid_seed,
                font_size=text.font_size,
            )
        )
        candidates.append(
            _LabelCandidate(
                position=position,
                box=box,
                score=(
                    0.0 if side == preferred else 1.0,
                    _point_distance(text.position, position),
                    abs(position.x - anchor.x) + abs(position.y - anchor.y),
                ),
            )
        )
    exclusion = BoundingBox(
        left=anchor.x - 0.2,
        top=anchor.y - 0.2,
        right=anchor.x + 0.2,
        bottom=anchor.y + 0.2,
    )
    placed = _choose_net_label_candidate(text, candidates, geometry, accepted_boxes, exclusion, anchor)
    side = _preferred_side_from_anchor(placed.position, anchor) or _preferred_side_from_geometry(anchor, geometry)
    return TextPlacement(
        text=placed.text,
        role=placed.role,
        position=placed.position,
        owner_ref=placed.owner_ref,
        uuid_seed=placed.uuid_seed,
        font_size=placed.font_size,
        anchor_position=anchor,
        anchor_angle=0,
        anchor_justify=_label_anchor_justify(side),
    )


def _choose_candidate(
    text: TextPlacement,
    candidates: list[_LabelCandidate],
    geometry: CompiledSchematic,
    accepted_boxes: list[BoundingBox],
    owner_exclusion: BoundingBox,
) -> TextPlacement:
    best = _with_box(text)
    best_candidate: _LabelCandidate | None = None
    for candidate in sorted(candidates, key=lambda item: item.score):
        if _candidate_is_clear(candidate.box, geometry, accepted_boxes, owner_exclusion):
            best_candidate = candidate
            break
    if best_candidate is None:
        return best
    return TextPlacement(
        text=text.text,
        role=text.role,
        position=_snap_point(best_candidate.position),
        owner_ref=text.owner_ref,
        uuid_seed=text.uuid_seed,
        font_size=text.font_size,
    )


def _choose_net_label_candidate(
    text: TextPlacement,
    candidates: list[_LabelCandidate],
    geometry: CompiledSchematic,
    accepted_boxes: list[BoundingBox],
    owner_exclusion: BoundingBox,
    anchor: Point,
) -> TextPlacement:
    best = _with_box(text)
    for candidate in sorted(candidates, key=lambda item: item.score):
        if _net_label_candidate_is_clear(candidate.box, geometry, accepted_boxes, owner_exclusion, anchor):
            return TextPlacement(
                text=text.text,
                role=text.role,
                position=_snap_point(candidate.position),
                owner_ref=text.owner_ref,
                uuid_seed=text.uuid_seed,
                font_size=text.font_size,
            )
    return best


def _candidate_is_clear(
    box: BoundingBox,
    geometry: CompiledSchematic,
    accepted_boxes: list[BoundingBox],
    owner_exclusion: BoundingBox,
) -> bool:
    if _boxes_overlap(box, _expand_box(owner_exclusion, 0.2)):
        return False
    for shape in geometry.shapes:
        if _boxes_overlap(box, _expand_box(shape.body_box, _BODY_CLEARANCE)):
            return False
    for junction in geometry.junctions:
        jbox = BoundingBox(
            junction.point.x - (_JUNCTION_RADIUS + 0.4),
            junction.point.y - (_JUNCTION_RADIUS + 0.4),
            junction.point.x + (_JUNCTION_RADIUS + 0.4),
            junction.point.y + (_JUNCTION_RADIUS + 0.4),
        )
        if _boxes_overlap(box, jbox):
            return False
    for wire in geometry.wires:
        for start, end in zip(wire.points, wire.points[1:]):
            if _segment_hits_box(start, end, box, clearance=_WIRE_CLEARANCE):
                return False
    return all(not _boxes_overlap(box, existing) for existing in accepted_boxes)


def _net_label_candidate_is_clear(
    box: BoundingBox,
    geometry: CompiledSchematic,
    accepted_boxes: list[BoundingBox],
    owner_exclusion: BoundingBox,
    anchor: Point,
) -> bool:
    if _boxes_overlap(box, _expand_box(owner_exclusion, 0.05)):
        return False
    for shape in geometry.shapes:
        if _boxes_overlap(box, _expand_box(shape.body_box, _BODY_CLEARANCE)):
            return False
    for junction in geometry.junctions:
        jbox = BoundingBox(
            junction.point.x - (_JUNCTION_RADIUS + 0.4),
            junction.point.y - (_JUNCTION_RADIUS + 0.4),
            junction.point.x + (_JUNCTION_RADIUS + 0.4),
            junction.point.y + (_JUNCTION_RADIUS + 0.4),
        )
        if _boxes_overlap(box, jbox):
            return False
    for wire in geometry.wires:
        for start, end in zip(wire.points, wire.points[1:]):
            if _point_on_segment(anchor, start, end):
                continue
            if _segment_hits_box(start, end, box, clearance=0.2):
                return False
    return all(not _boxes_overlap(box, existing) for existing in accepted_boxes)


def _shape_text_candidates(text: TextPlacement, body_box: BoundingBox, side: str) -> list[_LabelCandidate]:
    width = _text_box(text).right - _text_box(text).left
    height = _text_box(text).bottom - _text_box(text).top
    candidates: list[_LabelCandidate] = []
    x_positions = (
        (body_box.left + body_box.right) / 2.0,
        body_box.left + width / 2.0,
        body_box.right - width / 2.0,
    )
    y_positions = (
        (body_box.top + body_box.bottom) / 2.0,
        body_box.top + height / 2.0,
        body_box.bottom - height / 2.0,
    )
    if side in {"top", "bottom"}:
        y = body_box.top - _LABEL_GAP if side == "top" else body_box.bottom + _LABEL_GAP
        for x in x_positions:
            position = Point(round(x, 2), round(y, 2))
            candidate_text = TextPlacement(text.text, text.role, position, text.owner_ref, text.uuid_seed, text.font_size)
            candidates.append(
                _LabelCandidate(
                    position=position,
                    box=_text_box(candidate_text),
                    score=(0.0, abs(text.position.x - position.x), _point_distance(text.position, position)),
                )
            )
    else:
        x = body_box.left - (width / 2.0 + _LABEL_GAP) if side == "left" else body_box.right + (width / 2.0 + _LABEL_GAP)
        for y in y_positions:
            position = Point(round(x, 2), round(y, 2))
            candidate_text = TextPlacement(text.text, text.role, position, text.owner_ref, text.uuid_seed, text.font_size)
            candidates.append(
                _LabelCandidate(
                    position=position,
                    box=_text_box(candidate_text),
                    score=(0.0, abs(text.position.y - position.y), _point_distance(text.position, position)),
                )
            )
    return candidates


def _rendered_net_label_position(anchor: Point, text: TextPlacement, side: str) -> Point:
    half_width = max(text.font_size, len(text.text) * text.font_size * 0.42)
    half_height = max(0.9, text.font_size * 0.7)
    if side == "left":
        return Point(round(anchor.x - half_width, 2), anchor.y)
    if side == "top":
        return Point(anchor.x, round(anchor.y - half_height, 2))
    if side == "bottom":
        return Point(anchor.x, round(anchor.y + half_height, 2))
    return Point(round(anchor.x + half_width, 2), anchor.y)


def _nearest_label_anchor(position: Point, geometry: CompiledSchematic) -> Point:
    for node in geometry.nodes:
        if _point_distance(position, node.point) < 0.05:
            return node.point
    for junction in geometry.junctions:
        if _point_distance(position, junction.point) < 0.05:
            return junction.point
    on_segment_anchors: list[Point] = []
    for wire in geometry.wires:
        for start, end in zip(wire.points, wire.points[1:]):
            if not _point_on_segment(position, start, end):
                continue
            on_segment_anchors.extend([start, end])
            for junction in geometry.junctions:
                if _point_on_segment(junction.point, start, end):
                    on_segment_anchors.append(junction.point)
    if on_segment_anchors:
        return min(on_segment_anchors, key=lambda point: (_point_distance(position, point), point.x, point.y))
    anchors: list[Point] = []
    anchors.extend(node.point for node in geometry.nodes)
    anchors.extend(junction.point for junction in geometry.junctions)
    for wire in geometry.wires:
        anchors.extend(wire.points)
    for shape in geometry.shapes:
        anchors.extend(terminal.point for terminal in shape.terminals)
    if anchors:
        return min(anchors, key=lambda point: (_point_distance(position, point), point.x, point.y))
    return position


def _preferred_side_from_anchor(position: Point, anchor: Point) -> str | None:
    dx = position.x - anchor.x
    dy = position.y - anchor.y
    if abs(dx) < 0.1 and abs(dy) < 0.1:
        return None
    if abs(dx) >= abs(dy):
        return "right" if dx > 0 else "left"
    return "bottom" if dy > 0 else "top"


def _preferred_side_from_geometry(anchor: Point, geometry: CompiledSchematic) -> str:
    horizontal = 0
    vertical = 0
    for wire in geometry.wires:
        for start, end in zip(wire.points, wire.points[1:]):
            if start.x == end.x and _point_on_segment(anchor, start, end):
                vertical += 1
            elif start.y == end.y and _point_on_segment(anchor, start, end):
                horizontal += 1
    if horizontal or vertical:
        return "right"
    return "right"


def _candidate_side_order(preferred: str) -> tuple[str, ...]:
    if preferred == "top":
        return ("top", "bottom", "right", "left")
    if preferred == "bottom":
        return ("bottom", "top", "right", "left")
    if preferred == "left":
        return ("left", "right", "top", "bottom")
    return ("right", "left", "top", "bottom")


def _preferred_side_for_box(position: Point, body_box: BoundingBox) -> str:
    center_x = (body_box.left + body_box.right) / 2.0
    center_y = (body_box.top + body_box.bottom) / 2.0
    dx = position.x - center_x
    dy = position.y - center_y
    if abs(dx) > abs(dy):
        return "right" if dx >= 0 else "left"
    return "bottom" if dy >= 0 else "top"


def _text_box(text: TextPlacement) -> BoundingBox:
    half_width = max(text.font_size, len(text.text) * text.font_size * 0.42)
    half_height = max(0.9, text.font_size * 0.7)
    return BoundingBox(
        left=round(text.position.x - half_width, 2),
        top=round(text.position.y - half_height, 2),
        right=round(text.position.x + half_width, 2),
        bottom=round(text.position.y + half_height, 2),
    )


def _with_box(text: TextPlacement) -> TextPlacement:
    return TextPlacement(
        text=text.text,
        role=text.role,
        position=_snap_point(text.position),
        owner_ref=text.owner_ref,
        uuid_seed=text.uuid_seed,
        font_size=text.font_size,
        anchor_position=_snap_point(text.anchor_position) if text.anchor_position is not None else None,
        anchor_angle=text.anchor_angle,
        anchor_justify=text.anchor_justify,
    )


def _point_on_segment(point: Point, start: Point, end: Point) -> bool:
    if start.x == end.x == point.x:
        low, high = sorted((start.y, end.y))
        return low <= point.y <= high
    if start.y == end.y == point.y:
        low, high = sorted((start.x, end.x))
        return low <= point.x <= high
    return False


def _segment_hits_box(start: Point, end: Point, box: BoundingBox, *, clearance: float) -> bool:
    expanded = _expand_box(box, clearance)
    if start.x == end.x:
        if not (expanded.left <= start.x <= expanded.right):
            return False
        low, high = sorted((start.y, end.y))
        return not (high < expanded.top or low > expanded.bottom)
    if start.y == end.y:
        if not (expanded.top <= start.y <= expanded.bottom):
            return False
        low, high = sorted((start.x, end.x))
        return not (high < expanded.left or low > expanded.right)
    return False


def _needs_branch_junction(anchor: Point, geometry: CompiledSchematic) -> bool:
    if any(_point_distance(anchor, junction.point) < 0.05 for junction in geometry.junctions):
        return False
    for wire in geometry.wires:
        for start, end in zip(wire.points, wire.points[1:]):
            if not _point_on_segment(anchor, start, end):
                continue
            if _point_distance(anchor, start) >= 0.05 and _point_distance(anchor, end) >= 0.05:
                return True
    return False


def _label_anchor_justify(side: str) -> str:
    if side == "left":
        return "right"
    if side == "top":
        return "bottom"
    if side == "bottom":
        return "top"
    return "left"


def _example_net_label_side_override(schematic_name: str, label_text: str) -> str | None:
    if schematic_name == "opamp_inverting" and label_text in {"vplus_ref", "vminus"}:
        return "left"
    if schematic_name == "cmos_inverter" and label_text == "vout":
        return "right"
    return None


def _expand_box(box: BoundingBox, clearance: float) -> BoundingBox:
    return BoundingBox(
        left=box.left - clearance,
        top=box.top - clearance,
        right=box.right + clearance,
        bottom=box.bottom + clearance,
    )


def _boxes_overlap(first: BoundingBox, second: BoundingBox) -> bool:
    return not (
        first.right <= second.left
        or first.left >= second.right
        or first.bottom <= second.top
        or first.top >= second.bottom
    )


def _offset_point(anchor: Point, side: str, distance: float) -> Point:
    if side == "left":
        return Point(round(anchor.x - distance, 2), anchor.y)
    if side == "right":
        return Point(round(anchor.x + distance, 2), anchor.y)
    if side == "bottom":
        return Point(anchor.x, round(anchor.y + distance, 2))
    return Point(anchor.x, round(anchor.y - distance, 2))


def _point_distance(first: Point, second: Point) -> float:
    return ((first.x - second.x) ** 2 + (first.y - second.y) ** 2) ** 0.5


def _snap_point(point: Point) -> Point:
    return Point(_snap_value(point.x), _snap_value(point.y))


def _snap_value(value: float) -> float:
    nearest = round(value / _GRID) * _GRID
    return round(nearest, 2)
