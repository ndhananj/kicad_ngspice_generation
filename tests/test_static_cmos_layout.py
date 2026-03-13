from __future__ import annotations

from examples.specs.catalog import cmos_inverter
from mixedsig2cad.compiled import compile_schematic
from mixedsig2cad.intent import build_schematic_intent
from mixedsig2cad.spec import CircuitSpec
from mixedsig2cad.topology_layout import build_topology_layout


def test_cmos_inverter_uses_static_cmos_topology() -> None:
    intent = build_schematic_intent(cmos_inverter())
    layout = build_topology_layout(intent)

    assert layout is not None
    placements = {placement.ref: placement for placement in layout.placements}
    assert placements["MP1"].center.y < placements["MN1"].center.y
    assert placements["VDD"].center.x < placements["MP1"].center.x
    assert placements["VIN"].center.x < placements["MP1"].center.x

    connections = {connection.id: connection for connection in layout.connections}
    assert {item.owner_ref for item in connections["gate:vin"].attachments} == {"VIN", "MP1", "MN1"}
    assert {item.owner_ref for item in connections["net:vout"].attachments} == {"MP1", "MN1"}
    assert {item.owner_ref for item in connections["net:vdd"].attachments} == {"VDD", "MP1"}

    compiled = compile_schematic(intent)
    shapes = {shape.ref: shape for shape in compiled.shapes}
    assert shapes["MP1"].center.y < shapes["MN1"].center.y
    output_node = next(node for node in compiled.nodes if node.id == "net:vout")
    assert (output_node.point.x, output_node.point.y) == (162.56, 113.03)
    output_wires = [wire for wire in compiled.wires if wire.uuid_seed.startswith("cmos_inverter:net:vout")]
    assert len(output_wires) == 1
    assert [(point.x, point.y) for point in output_wires[0].points] == [(162.56, 83.82), (162.56, 142.24)]


def test_static_cmos_layout_handles_multi_transistor_nand() -> None:
    spec = (
        CircuitSpec("cmos_nand")
        .add("VDD", "V", "DC 3.3", "vdd", "0")
        .add("VA", "V", "PULSE(0 3.3 0 1n 1n 10n 20n)", "va", "0")
        .add("VB", "V", "PULSE(0 3.3 0 1n 1n 10n 20n)", "vb", "0")
        .add("MP1", "M", "PM1", "vout", "va", "vdd", "vdd", model="PM1")
        .add("MP2", "M", "PM1", "vout", "vb", "vdd", "vdd", model="PM1")
        .add("MN1", "M", "NM1", "vout", "va", "nmid", "0", model="NM1")
        .add("MN2", "M", "NM1", "nmid", "vb", "0", "0", model="NM1")
    )

    intent = build_schematic_intent(spec)
    layout = build_topology_layout(intent)

    assert layout is not None
    placements = {placement.ref: placement for placement in layout.placements}
    assert placements["MP1"].center.y < placements["MN1"].center.y
    assert placements["MP2"].center.y < placements["MN2"].center.y
    assert placements["MN1"].center.x == placements["MN2"].center.x
    assert placements["MP1"].center.x != placements["MP2"].center.x

    connections = {connection.id: connection for connection in layout.connections}
    assert {item.owner_ref for item in connections["gate:va"].attachments} == {"VA", "MP1", "MN1"}
    assert {item.owner_ref for item in connections["gate:vb"].attachments} == {"VB", "MP2", "MN2"}
    assert {item.owner_ref for item in connections["net:nmid"].attachments} == {"MN1", "MN2"}

    compiled = compile_schematic(intent)
    stack_node = next(node for node in compiled.nodes if node.id == "net:nmid")
    assert stack_node.point.x == 152.40
    stack_wires = [wire for wire in compiled.wires if wire.uuid_seed.startswith("cmos_nand:net:nmid")]
    assert len(stack_wires) == 1
    assert [(point.x, point.y) for point in stack_wires[0].points] == [(152.40, 125.17), (152.40, 153.11)]
