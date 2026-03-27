from __future__ import annotations

import json
from typing import Any

from mixedsig2cad.compiled import compile_schematic
from mixedsig2cad.design import ExampleDesign
from mixedsig2cad.intent import build_schematic_intent
from mixedsig2cad.layout_compiler import compile_design
from mixedsig2cad.models import CompiledSchematic, Point
from mixedsig2cad.spec import CircuitSpec


def build_frontend_scene(source: ExampleDesign | CircuitSpec | CompiledSchematic) -> dict[str, Any]:
    geometry = _compiled_geometry(source)
    shape_by_ref = {shape.ref: shape for shape in geometry.shapes}
    return {
        "name": geometry.name,
        "bounds": _bounds_payload(geometry),
        "components": [
            {
                "id": shape.ref,
                "ref": shape.ref,
                "value": shape.value,
                "shape": shape.shape,
                "orientation": shape.orientation,
                "center": _point_payload(shape.center),
                "bodyBox": {
                    "left": shape.body_box.left,
                    "top": shape.body_box.top,
                    "right": shape.body_box.right,
                    "bottom": shape.body_box.bottom,
                },
                "terminals": [
                    {
                        "name": terminal.name,
                        "point": _point_payload(terminal.point),
                        "side": terminal.side,
                    }
                    for terminal in shape.terminals
                ],
                "hiddenReference": shape.hidden_reference,
            }
            for shape in geometry.shapes
        ],
        "wires": [
            {
                "id": wire.uuid_seed,
                "points": [_point_payload(point) for point in wire.points],
            }
            for wire in geometry.wires
        ],
        "labels": [
            {
                "id": label.uuid_seed,
                "text": label.text,
                "role": label.role,
                "ownerRef": label.owner_ref,
                "position": _point_payload(label.position),
                "fontSize": label.font_size,
            }
            for label in geometry.labels
            if not (
                label.role == "reference"
                and shape_by_ref.get(label.owner_ref) is not None
                and shape_by_ref[label.owner_ref].hidden_reference
            )
        ],
        "junctions": [
            {
                "id": f"{geometry.name}:junction:{index}",
                "point": _point_payload(junction.point),
            }
            for index, junction in enumerate(geometry.junctions, start=1)
        ],
        "nodes": [
            {
                "id": node.id,
                "point": _point_payload(node.point),
                "attachments": [
                    {
                        "ownerRef": attachment.owner_ref,
                        "terminalName": attachment.terminal_name,
                    }
                    for attachment in node.attachments
                ],
                "renderStyle": node.render_style,
                "label": node.label,
                "role": node.role,
            }
            for node in geometry.nodes
        ],
    }


def export_frontend_scene_json(source: ExampleDesign | CircuitSpec | CompiledSchematic) -> str:
    return json.dumps(build_frontend_scene(source), indent=2) + "\n"


def _compiled_geometry(source: ExampleDesign | CircuitSpec | CompiledSchematic) -> CompiledSchematic:
    if isinstance(source, CompiledSchematic):
        return source
    if isinstance(source, ExampleDesign):
        return compile_design(source)
    intent = build_schematic_intent(source)
    return compile_schematic(intent)


def _point_payload(point: Point) -> dict[str, float]:
    return {"x": point.x, "y": point.y}


def _bounds_payload(geometry: CompiledSchematic) -> dict[str, float]:
    xs: list[float] = []
    ys: list[float] = []

    for shape in geometry.shapes:
        xs.extend([shape.body_box.left, shape.body_box.right, shape.center.x])
        ys.extend([shape.body_box.top, shape.body_box.bottom, shape.center.y])
        for terminal in shape.terminals:
            xs.append(terminal.point.x)
            ys.append(terminal.point.y)

    for wire in geometry.wires:
        for point in wire.points:
            xs.append(point.x)
            ys.append(point.y)

    for label in geometry.labels:
        xs.append(label.position.x)
        ys.append(label.position.y)

    for junction in geometry.junctions:
        xs.append(junction.point.x)
        ys.append(junction.point.y)

    if not xs or not ys:
        return {"left": 0.0, "top": 0.0, "right": 0.0, "bottom": 0.0, "width": 0.0, "height": 0.0}

    left = min(xs)
    top = min(ys)
    right = max(xs)
    bottom = max(ys)
    return {
        "left": left,
        "top": top,
        "right": right,
        "bottom": bottom,
        "width": right - left,
        "height": bottom - top,
    }
