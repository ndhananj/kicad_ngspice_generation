from __future__ import annotations

from mixedsig2cad.spec import CircuitSpec


def _component_line(ref: str, value: str, nodes: tuple[str, ...], model: str | None) -> str:
    joined_nodes = " ".join(nodes)
    if model:
        return f"{ref} {joined_nodes} {model}"
    return f"{ref} {joined_nodes} {value}"


def export_ngspice_netlist(spec: CircuitSpec) -> str:
    lines = [f"* {spec.name}"]
    for comp in spec.components:
        lines.append(_component_line(comp.ref, comp.value, comp.nodes, comp.model))

    if spec.models:
        lines.append("")
        lines.extend(spec.models)

    if spec.analyses:
        lines.append("")
        lines.append(".control")
        for analysis in spec.analyses:
            lines.append(analysis.command)
        lines.append(".endc")

    lines.append(".end")
    return "\n".join(lines) + "\n"
