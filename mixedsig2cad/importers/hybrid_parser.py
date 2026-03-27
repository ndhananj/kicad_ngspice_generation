from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from mixedsig2cad.dev_env import BOOTSTRAP_COMMAND
from mixedsig2cad.exporters.ngspice import export_ngspice_netlist
from mixedsig2cad.importers.kicad_schematic import import_kicad_schematic
from mixedsig2cad.importers.raster_extract import extract_geometry_from_image
from mixedsig2cad.models import CompiledSchematic, Point
from mixedsig2cad.spec import CircuitSpec


SourceType = Literal["vector", "raster"]


@dataclass(frozen=True, slots=True)
class SceneStroke:
    points: tuple[Point, ...]
    source: str


@dataclass(frozen=True, slots=True)
class SceneFill:
    box: tuple[float, float, float, float]
    source: str


@dataclass(frozen=True, slots=True)
class SceneText:
    text: str
    role: str
    position: Point
    source: str


@dataclass(frozen=True, slots=True)
class SceneMask:
    kind: str
    box: tuple[float, float, float, float]
    source: str


@dataclass(frozen=True, slots=True)
class SceneBox:
    kind: str
    box: tuple[float, float, float, float]
    source: str


@dataclass(frozen=True, slots=True)
class SceneGraphObject:
    kind: str
    id: str
    box: tuple[float, float, float, float] | None = None
    attachments: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CanonicalScene:
    source_kind: str
    strokes: tuple[SceneStroke, ...] = ()
    fills: tuple[SceneFill, ...] = ()
    texts: tuple[SceneText, ...] = ()
    masks: tuple[SceneMask, ...] = ()
    boxes: tuple[SceneBox, ...] = ()
    graph_objects: tuple[SceneGraphObject, ...] = ()


@dataclass(frozen=True, slots=True)
class ParsedComponent:
    ref: str
    kind: str
    value: str
    center: Point
    orientation: str
    terminals: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ParsedJunction:
    x: float
    y: float
    degree: int


@dataclass(frozen=True, slots=True)
class ParsedGraph:
    nodes: dict[str, tuple[str, ...]]
    connections: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class OverlayArtifact:
    path: Path
    kind: Literal["svg", "png"]


@dataclass(frozen=True, slots=True)
class DependencyStatus:
    sam_available: bool
    ocr_available: bool
    pdflatex_available: bool = False
    kicad_cli_available: bool = False
    pdf_raster_available: bool = False
    missing: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ParseArtifacts:
    components_json: Path
    junctions_json: Path
    graph_json: Path
    netlist_txt: Path | None
    overlay: Path


@dataclass(frozen=True, slots=True)
class ParseResult:
    source_type: SourceType
    scene: CanonicalScene
    components: tuple[ParsedComponent, ...]
    junctions: tuple[ParsedJunction, ...]
    graph: ParsedGraph
    compiled_schematic: CompiledSchematic
    netlist_text: str | None
    overlay: OverlayArtifact
    artifacts: ParseArtifacts | None
    dependency_status: DependencyStatus
    notes: tuple[str, ...] = ()


def check_parser_runtime_dependencies(*, require_sam: bool = False, require_ocr: bool = False) -> DependencyStatus:
    if require_sam or require_ocr:
        _require_runtime_dependencies(require_sam=require_sam, require_ocr=require_ocr)
    return _runtime_dependency_status()


def check_validation_runtime_dependencies(
    *,
    require_kicad: bool = False,
    require_tex: bool = False,
    require_ocr: bool = False,
    require_pdf_raster: bool = False,
) -> DependencyStatus:
    if require_kicad or require_tex or require_ocr or require_pdf_raster:
        _require_validation_runtime_dependencies(
            require_kicad=require_kicad,
            require_tex=require_tex,
            require_ocr=require_ocr,
            require_pdf_raster=require_pdf_raster,
        )
    return _runtime_dependency_status()


def parse_circuit_source(
    source: str | Path,
    *,
    source_type: SourceType,
    output_dir: str | Path | None = None,
    spec: CircuitSpec | None = None,
) -> ParseResult:
    path = Path(source)
    if source_type == "vector":
        return _parse_vector_source(path, output_dir=output_dir, spec=spec)
    if source_type == "raster":
        _require_runtime_dependencies(require_sam=True, require_ocr=True)
        raise NotImplementedError(
            "Raster parsing architecture is wired but not implemented yet; install dependencies and add a SAM-backed segmenter."
        )
    raise AssertionError(f"unsupported source_type: {source_type}")


def _parse_vector_source(
    path: Path,
    *,
    output_dir: str | Path | None,
    spec: CircuitSpec | None,
) -> ParseResult:
    geometry: CompiledSchematic
    overlay_kind: Literal["svg", "png"]
    if path.suffix.lower() == ".kicad_sch":
        geometry = import_kicad_schematic(path)
        overlay_kind = "svg"
    elif path.suffix.lower() == ".svg":
        geometry = extract_geometry_from_image(path)
        overlay_kind = "svg"
    else:
        raise NotImplementedError(f"unsupported vector input: {path.suffix}")

    scene = _scene_from_geometry(geometry, source_kind=f"vector:{path.suffix.lower()}")
    result = _build_parse_result(
        path,
        geometry,
        scene,
        source_type="vector",
        overlay_kind=overlay_kind,
        output_dir=output_dir,
        spec=spec,
    )
    return result


def _build_parse_result(
    source_path: Path,
    geometry: CompiledSchematic,
    scene: CanonicalScene,
    *,
    source_type: SourceType,
    overlay_kind: Literal["svg", "png"],
    output_dir: str | Path | None,
    spec: CircuitSpec | None,
) -> ParseResult:
    components = tuple(
        ParsedComponent(
            ref=shape.ref,
            kind=shape.shape,
            value=shape.value,
            center=shape.center,
            orientation=shape.orientation,
            terminals=tuple(terminal.name for terminal in shape.terminals),
        )
        for shape in geometry.shapes
    )
    junctions = tuple(
        ParsedJunction(
            x=round(junction.point.x, 2),
            y=round(junction.point.y, 2),
            degree=_junction_degree(geometry, junction.point),
        )
        for junction in geometry.junctions
    )
    graph = _graph_from_geometry(geometry)
    netlist_text = export_ngspice_netlist(spec) if spec is not None else None
    dependency_status = _runtime_dependency_status()
    overlay = _build_overlay(source_path, geometry, overlay_kind=overlay_kind, output_dir=output_dir)
    artifacts = None
    if output_dir is not None:
        artifacts = _write_artifacts(
            output_dir=Path(output_dir),
            components=components,
            junctions=junctions,
            graph=graph,
            netlist_text=netlist_text,
            overlay=overlay,
        )
    notes = ()
    if spec is None:
        notes = ("No CircuitSpec provided; netlist.txt was not emitted.",)
    return ParseResult(
        source_type=source_type,
        scene=scene,
        components=components,
        junctions=junctions,
        graph=graph,
        compiled_schematic=geometry,
        netlist_text=netlist_text,
        overlay=overlay,
        artifacts=artifacts,
        dependency_status=dependency_status,
        notes=notes,
    )


def _scene_from_geometry(geometry: CompiledSchematic, *, source_kind: str) -> CanonicalScene:
    strokes = tuple(SceneStroke(points=wire.points, source="geometry.wire") for wire in geometry.wires)
    fills = tuple(
        SceneFill(
            box=(shape.body_box.left, shape.body_box.top, shape.body_box.right, shape.body_box.bottom),
            source=f"shape:{shape.ref}",
        )
        for shape in geometry.shapes
    )
    texts = tuple(
        SceneText(text=label.text, role=label.role, position=label.position, source=label.owner_ref)
        for label in geometry.labels
    )
    masks = tuple(
        SceneMask(
            kind="junction_hint",
            box=(junction.point.x - 0.5, junction.point.y - 0.5, junction.point.x + 0.5, junction.point.y + 0.5),
            source="geometry.junction",
        )
        for junction in geometry.junctions
    )
    boxes = tuple(
        SceneBox(
            kind=shape.shape,
            box=(shape.body_box.left, shape.body_box.top, shape.body_box.right, shape.body_box.bottom),
            source=shape.ref,
        )
        for shape in geometry.shapes
    )
    graph_objects = tuple(
        SceneGraphObject(
            kind="component",
            id=shape.ref,
            box=(shape.body_box.left, shape.body_box.top, shape.body_box.right, shape.body_box.bottom),
            attachments=tuple(f"{shape.ref}.{terminal.name}" for terminal in shape.terminals),
        )
        for shape in geometry.shapes
    ) + tuple(
        SceneGraphObject(
            kind="net_node",
            id=node.id,
            attachments=tuple(f"{attachment.owner_ref}.{attachment.terminal_name}" for attachment in node.attachments),
        )
        for node in geometry.nodes
    )
    return CanonicalScene(
        source_kind=source_kind,
        strokes=strokes,
        fills=fills,
        texts=texts,
        masks=masks,
        boxes=boxes,
        graph_objects=graph_objects,
    )


def _graph_from_geometry(geometry: CompiledSchematic) -> ParsedGraph:
    nodes = {
        node.id: tuple(
            f"{attachment.owner_ref}.{attachment.terminal_name}" for attachment in node.attachments
        )
        for node in geometry.nodes
    }
    connections = tuple(
        (node_id, attachment)
        for node_id, attachments in nodes.items()
        for attachment in attachments
    )
    return ParsedGraph(nodes=nodes, connections=connections)


def _junction_degree(geometry: CompiledSchematic, point: Point) -> int:
    degree = 0
    key = (round(point.x, 2), round(point.y, 2))
    for wire in geometry.wires:
        for start, end in zip(wire.points, wire.points[1:]):
            a = (round(start.x, 2), round(start.y, 2))
            b = (round(end.x, 2), round(end.y, 2))
            if key == a or key == b:
                degree += 1
    return degree


def _build_overlay(
    source_path: Path,
    geometry: CompiledSchematic,
    *,
    overlay_kind: Literal["svg", "png"],
    output_dir: str | Path | None,
) -> OverlayArtifact:
    if output_dir is None:
        path = source_path.with_name(f"{source_path.stem}.overlay.{overlay_kind}")
    else:
        path = Path(output_dir) / f"overlay.{overlay_kind}"
        path.parent.mkdir(parents=True, exist_ok=True)
    if overlay_kind == "svg":
        path.write_text(_render_svg_overlay(geometry), encoding="utf-8")
    else:
        path.write_bytes(b"")
    return OverlayArtifact(path=path, kind=overlay_kind)


def _render_svg_overlay(geometry: CompiledSchematic) -> str:
    all_points = [point for wire in geometry.wires for point in wire.points]
    all_points.extend(shape.center for shape in geometry.shapes)
    all_points.extend(junction.point for junction in geometry.junctions)
    if not all_points:
        width = 100.0
        height = 100.0
        min_x = 0.0
        min_y = 0.0
    else:
        min_x = min(point.x for point in all_points) - 10.0
        min_y = min(point.y for point in all_points) - 10.0
        max_x = max(point.x for point in all_points) + 10.0
        max_y = max(point.y for point in all_points) + 10.0
        width = max_x - min_x
        height = max_y - min_y
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{min_x:.2f} {min_y:.2f} {width:.2f} {height:.2f}">',
        '<rect width="100%" height="100%" fill="white"/>',
    ]
    for wire in geometry.wires:
        points = " ".join(f"{point.x:.2f},{point.y:.2f}" for point in wire.points)
        lines.append(f'<polyline points="{points}" fill="none" stroke="#0b7a75" stroke-width="0.8"/>')
    for shape in geometry.shapes:
        width_box = shape.body_box.right - shape.body_box.left
        height_box = shape.body_box.bottom - shape.body_box.top
        lines.append(
            f'<rect x="{shape.body_box.left:.2f}" y="{shape.body_box.top:.2f}" width="{width_box:.2f}" '
            f'height="{height_box:.2f}" fill="none" stroke="#c0392b" stroke-width="0.8"/>'
        )
        lines.append(
            f'<text x="{shape.center.x:.2f}" y="{shape.center.y:.2f}" font-size="3" text-anchor="middle" '
            f'fill="#1f2933">{shape.ref}</text>'
        )
    for junction in geometry.junctions:
        lines.append(f'<circle cx="{junction.point.x:.2f}" cy="{junction.point.y:.2f}" r="1.2" fill="#111827"/>')
    lines.append("</svg>")
    return "\n".join(lines)


def _write_artifacts(
    *,
    output_dir: Path,
    components: tuple[ParsedComponent, ...],
    junctions: tuple[ParsedJunction, ...],
    graph: ParsedGraph,
    netlist_text: str | None,
    overlay: OverlayArtifact,
) -> ParseArtifacts:
    output_dir.mkdir(parents=True, exist_ok=True)
    components_json = output_dir / "components.json"
    junctions_json = output_dir / "junctions.json"
    graph_json = output_dir / "graph.json"
    components_json.write_text(json.dumps([_serialize_dataclass(item) for item in components], indent=2), encoding="utf-8")
    junctions_json.write_text(json.dumps([_serialize_dataclass(item) for item in junctions], indent=2), encoding="utf-8")
    graph_json.write_text(json.dumps(_serialize_dataclass(graph), indent=2), encoding="utf-8")
    if overlay.path.parent != output_dir:
        shutil.copyfile(overlay.path, output_dir / overlay.path.name)
        overlay = OverlayArtifact(path=output_dir / overlay.path.name, kind=overlay.kind)
    netlist_path = output_dir / "netlist.txt" if netlist_text is not None else None
    if netlist_path is not None:
        netlist_path.write_text(netlist_text, encoding="utf-8")
    return ParseArtifacts(
        components_json=components_json,
        junctions_json=junctions_json,
        graph_json=graph_json,
        netlist_txt=netlist_path,
        overlay=overlay.path,
    )


def _serialize_dataclass(value):
    payload = asdict(value)
    return _normalize_payload(payload)


def _normalize_payload(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _normalize_payload(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_normalize_payload(item) for item in value]
    if isinstance(value, list):
        return [_normalize_payload(item) for item in value]
    return value


def _runtime_dependency_status() -> DependencyStatus:
    missing: list[str] = []
    sam_available = _module_available("segment_anything") or _module_available("sam2")
    ocr_available = _module_available("easyocr") or _module_available("pytesseract")
    pdflatex_available = shutil.which("pdflatex") is not None
    kicad_cli_available = shutil.which("kicad-cli") is not None
    pdf_raster_available = _module_available("fitz")
    if not sam_available:
        missing.append("segment_anything or sam2")
    if not ocr_available:
        missing.append("easyocr or pytesseract")
    if _module_available("pytesseract") and shutil.which("tesseract") is None:
        missing.append("tesseract binary")
        ocr_available = False
    if not pdflatex_available:
        missing.append("pdflatex")
    if not kicad_cli_available:
        missing.append("kicad-cli")
    if not pdf_raster_available:
        missing.append("PyMuPDF")
    return DependencyStatus(
        sam_available=sam_available,
        ocr_available=ocr_available,
        pdflatex_available=pdflatex_available,
        kicad_cli_available=kicad_cli_available,
        pdf_raster_available=pdf_raster_available,
        missing=tuple(missing),
    )


def _require_runtime_dependencies(*, require_sam: bool, require_ocr: bool) -> None:
    status = _runtime_dependency_status()
    missing: list[str] = []
    if require_sam and not status.sam_available:
        missing.append("segment_anything or sam2")
    if require_ocr and not status.ocr_available:
        missing.append("easyocr or pytesseract with tesseract binary")
    if missing:
        raise RuntimeError(
            "Missing parser dependencies: "
            + ", ".join(missing)
            + f". Run `{BOOTSTRAP_COMMAND}` and then `python3 scripts/setup_parser_env.py`."
        )


def _require_validation_runtime_dependencies(
    *,
    require_kicad: bool,
    require_tex: bool,
    require_ocr: bool,
    require_pdf_raster: bool,
) -> None:
    status = _runtime_dependency_status()
    missing: list[str] = []
    if require_kicad and not status.kicad_cli_available:
        missing.append("kicad-cli")
    if require_tex and not status.pdflatex_available:
        missing.append("pdflatex")
    if require_ocr and not status.ocr_available:
        missing.append("easyocr or pytesseract with tesseract binary")
    if require_pdf_raster and not status.pdf_raster_available:
        missing.append("PyMuPDF")
    if missing:
        raise RuntimeError(
            "Missing validation dependencies: "
            + ", ".join(missing)
            + f". Run `{BOOTSTRAP_COMMAND}` and then `python3 scripts/setup_parser_env.py`."
        )


def _module_available(name: str) -> bool:
    import importlib.util

    return importlib.util.find_spec(name) is not None
