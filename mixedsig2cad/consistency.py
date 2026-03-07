from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tempfile

from mixedsig2cad.compiled import CompiledSchematic
from mixedsig2cad.exporters.kicad import render_kicad_schematic
from mixedsig2cad.geometry import Point
from mixedsig2cad.importers.kicad_schematic import import_kicad_schematic
from mixedsig2cad.importers.raster_extract import extract_geometry_from_image
from mixedsig2cad.projections.kicad import project_geometry_to_kicad
from mixedsig2cad.topology_layout import (
    TopologyAttachment,
    TopologyConnection,
    TopologyLayout,
    TopologyPlacement,
    TopologyPoint,
)


@dataclass(frozen=True, slots=True)
class GeometryComparison:
    matched_symbols: int
    missing_symbols: tuple[str, ...]
    extra_symbols: tuple[str, ...]
    wire_mismatches: tuple[str, ...]
    junction_mismatches: tuple[str, ...]
    within_tolerance: bool


@dataclass(frozen=True, slots=True)
class TopologyComparison:
    missing_connections: tuple[str, ...]
    extra_connections: tuple[str, ...]
    node_role_mismatches: tuple[str, ...]
    equivalent: bool


@dataclass(frozen=True, slots=True)
class RoundTripReport:
    geometry: GeometryComparison
    topology: TopologyComparison
    notes: tuple[str, ...]
    exact_roundtrip: bool


def derive_topology_layout(geometry: CompiledSchematic) -> TopologyLayout:
    layout = TopologyLayout(name=geometry.name)
    for shape in geometry.shapes:
        layout.placements.append(
            TopologyPlacement(
                ref=shape.ref,
                center=TopologyPoint(shape.center.x, shape.center.y),
                orientation=shape.orientation,
                shape=shape.shape,
                value=shape.value,
            )
        )
    for node in geometry.nodes:
        layout.connections.append(
            TopologyConnection(
                id=node.id,
                point=TopologyPoint(node.point.x, node.point.y),
                attachments=tuple(
                    TopologyAttachment(owner_ref=attachment.owner_ref, terminal_name=attachment.terminal_name)
                    for attachment in node.attachments
                ),
                render_style=node.render_style,
                role=node.role,
            )
        )
    return layout


def compare_geometries(
    expected: CompiledSchematic,
    observed: CompiledSchematic,
    *,
    coordinate_tolerance: float = 0.01,
) -> GeometryComparison:
    expected_shapes = {shape.ref: shape for shape in expected.shapes}
    observed_shapes = {shape.ref: shape for shape in observed.shapes}
    missing_symbols = tuple(sorted(set(expected_shapes) - set(observed_shapes)))
    extra_symbols = tuple(sorted(set(observed_shapes) - set(expected_shapes)))
    matched_symbols = 0
    mismatches: list[str] = []
    for ref in sorted(set(expected_shapes) & set(observed_shapes)):
        exp = expected_shapes[ref]
        obs = observed_shapes[ref]
        if exp.shape != obs.shape or exp.orientation != obs.orientation:
            mismatches.append(f"symbol:{ref}")
            continue
        if _distance(exp.center, obs.center) > coordinate_tolerance or exp.value != obs.value:
            mismatches.append(f"symbol:{ref}")
            continue
        matched_symbols += 1

    expected_wires = _normalized_wire_segments(expected)
    observed_wires = _normalized_wire_segments(observed)
    wire_mismatches = tuple(
        sorted(
            {
                f"missing:{segment}"
                for segment in sorted(expected_wires - observed_wires)
            }
            | {
                f"extra:{segment}"
                for segment in sorted(observed_wires - expected_wires)
            }
            | set(mismatches)
        )
    )
    expected_junctions = {(junction.point.x, junction.point.y) for junction in expected.junctions}
    observed_junctions = {(junction.point.x, junction.point.y) for junction in observed.junctions}
    junction_mismatches = tuple(
        sorted(
            [f"missing:{point}" for point in sorted(expected_junctions - observed_junctions)]
            + [f"extra:{point}" for point in sorted(observed_junctions - expected_junctions)]
        )
    )
    return GeometryComparison(
        matched_symbols=matched_symbols,
        missing_symbols=missing_symbols,
        extra_symbols=extra_symbols,
        wire_mismatches=wire_mismatches,
        junction_mismatches=junction_mismatches,
        within_tolerance=not missing_symbols and not extra_symbols and not wire_mismatches and not junction_mismatches,
    )


def compare_topologies(expected: TopologyLayout, observed: TopologyLayout) -> TopologyComparison:
    expected_connections = _connection_index(expected)
    observed_connections = _connection_index(observed)
    missing_connections = tuple(sorted(set(expected_connections) - set(observed_connections)))
    extra_connections = tuple(sorted(set(observed_connections) - set(expected_connections)))
    role_mismatches: list[str] = []
    for key in sorted(set(expected_connections) & set(observed_connections)):
        if (
            expected_connections[key] is not None
            and observed_connections[key] is not None
            and expected_connections[key] != observed_connections[key]
        ):
            role_mismatches.append(key)
    return TopologyComparison(
        missing_connections=missing_connections,
        extra_connections=extra_connections,
        node_role_mismatches=tuple(role_mismatches),
        equivalent=not missing_connections and not extra_connections and not role_mismatches,
    )


def roundtrip_kicad_schematic(path: str | Path) -> RoundTripReport:
    imported = import_kicad_schematic(path)
    regenerated = _regenerate_geometry(imported)
    geometry_report = compare_geometries(imported, regenerated)
    topology_report = compare_topologies(derive_topology_layout(imported), derive_topology_layout(regenerated))
    return RoundTripReport(
        geometry=geometry_report,
        topology=topology_report,
        notes=(),
        exact_roundtrip=geometry_report.within_tolerance and topology_report.equivalent,
    )


def roundtrip_image(path: str | Path, *, mode: str = "kicad_raster") -> RoundTripReport:
    extracted = extract_geometry_from_image(path, mode=mode)
    regenerated = _regenerate_geometry(extracted)
    geometry_report = compare_geometries(extracted, regenerated, coordinate_tolerance=2.0 if mode != "kicad_schematic" else 0.01)
    topology_report = compare_topologies(derive_topology_layout(extracted), derive_topology_layout(regenerated))
    return RoundTripReport(
        geometry=geometry_report,
        topology=topology_report,
        notes=(),
        exact_roundtrip=topology_report.equivalent and geometry_report.within_tolerance,
    )


def _regenerate_geometry(geometry: CompiledSchematic) -> CompiledSchematic:
    projection = project_geometry_to_kicad(geometry)
    text = render_kicad_schematic(projection)
    with tempfile.TemporaryDirectory(prefix="mixedsig2cad-roundtrip-") as tmp:
        path = Path(tmp) / f"{geometry.name}.kicad_sch"
        path.write_text(text, encoding="utf-8")
        return import_kicad_schematic(path)


def _normalized_wire_segments(geometry: CompiledSchematic) -> set[tuple[tuple[float, float], tuple[float, float]]]:
    segments: set[tuple[tuple[float, float], tuple[float, float]]] = set()
    for wire in geometry.wires:
        for start, end in zip(wire.points, wire.points[1:]):
            a = (round(start.x, 2), round(start.y, 2))
            b = (round(end.x, 2), round(end.y, 2))
            segments.add(tuple(sorted((a, b))))
    return segments


def _connection_index(layout: TopologyLayout) -> dict[str, str | None]:
    index: dict[str, str | None] = {}
    for connection in layout.connections:
        attachments = ",".join(
            f"{attachment.owner_ref}.{attachment.terminal_name}"
            for attachment in sorted(connection.attachments, key=lambda item: (item.owner_ref, item.terminal_name))
        )
        key = attachments
        index[key] = connection.role
    return index


def _distance(a: Point, b: Point) -> float:
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5
