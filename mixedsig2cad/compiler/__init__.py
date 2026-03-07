from __future__ import annotations

from .finalize import finalize_compiled_schematic
from .patterns import build_rc_highpass, build_rc_lowpass
from .strategies import build_fallback, build_flow
from .topology import build_from_topology_layout
from ..geometry import _can_use_flow_layout
from ..intent import SchematicIntent
from ..models import CompiledSchematic
from ..topology_layout import build_topology_layout


def compile_intent(intent: SchematicIntent) -> CompiledSchematic:
    topology_layout = build_topology_layout(intent)
    if topology_layout is not None:
        return finalize_compiled_schematic(build_from_topology_layout(intent, topology_layout))
    for pattern in intent.patterns:
        if pattern.kind == "rc_lowpass":
            return finalize_compiled_schematic(build_rc_lowpass(intent, pattern))
        if pattern.kind == "rc_highpass":
            return finalize_compiled_schematic(build_rc_highpass(intent, pattern))
    if _can_use_flow_layout(intent):
        return finalize_compiled_schematic(build_flow(intent))
    return finalize_compiled_schematic(build_fallback(intent))
