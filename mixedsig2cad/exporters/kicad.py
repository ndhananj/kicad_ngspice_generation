from __future__ import annotations

import uuid

from mixedsig2cad.spec import CircuitSpec


SYMBOL_BY_KIND = {
    "R": "Device:R",
    "C": "Device:C",
    "L": "Device:L",
    "V": "pspice:VSOURCE",
    "I": "pspice:ISOURCE",
    "D": "Device:D",
    "Q": "Device:Q_NPN_BCE",
    "M": "Device:Q_PMOS_GSD",
    "X": "Amplifier_Operational:LM358",
}


def _uuid(seed: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))


def _symbol_property(name: str, value: str, x: float, y: float, *, hidden: bool = False) -> list[str]:
    """Emit KiCad symbol property syntax compatible with KiCad 8 parser.

    Hidden properties must express `hide` inside the `effects` stanza, not as a
    standalone property child node.
    """
    effects = "(effects (font (size 1.27 1.27)) hide)" if hidden else "(effects (font (size 1.27 1.27)))"
    return [
        f'    (property "{name}" "{value}" (at {x} {y} 0)',
        f"      {effects}",
        "    )",
    ]


def _symbol_for_component(kind: str, value: str, model: str | None) -> str:
    if kind != "M":
        return SYMBOL_BY_KIND.get(kind, "Device:R")
    hint = f"{value} {model or ''}".lower()
    if "nm" in hint or "nmos" in hint:
        return "Device:Q_NMOS_GSD"
    return "Device:Q_PMOS_GSD"


def _pin_map_text(nodes: tuple[str, ...]) -> str:
    pairs = [f"{idx + 1}:{node}" for idx, node in enumerate(nodes)]
    return "pins " + "  ".join(pairs)


def export_kicad_schematic(spec: CircuitSpec) -> str:
    schematic_uuid = _uuid(f"sch:{spec.name}")
    lines: list[str] = [
        "(kicad_sch",
        "  (version 20231120)",
        '  (generator "mixedsig2cad")',
        f"  (uuid {schematic_uuid})",
        '  (paper "A4")',
        "  (lib_symbols)",
    ]

    base_x = 50
    y = 50
    for idx, comp in enumerate(spec.components, start=1):
        symbol_uuid = _uuid(f"sym:{spec.name}:{comp.ref}")
        lib_id = _symbol_for_component(comp.kind, comp.value, comp.model)
        x = base_x + (idx - 1) % 4 * 35
        if idx > 1 and (idx - 1) % 4 == 0:
            y += 30
        node_text = " ".join(comp.nodes)
        pin_map = _pin_map_text(comp.nodes)
        lines.extend(
            [
                f"  (text \"nodes: {node_text}\" (at {x} {y-8} 0)",
                "    (effects (font (size 1.27 1.27)) (justify left))",
                "  )",
                f"  (text \"{pin_map}\" (at {x} {y+8} 0)",
                "    (effects (font (size 1.0 1.0)) (justify left))",
                "  )",
                f"  (symbol (lib_id \"{lib_id}\") (at {x} {y} 0) (unit 1)",
                "    (in_bom yes) (on_board yes)",
                f"    (uuid {symbol_uuid})",
                *_symbol_property("Reference", comp.ref, x, y - 3.81),
                *_symbol_property("Value", comp.value, x, y + 3.81),
                *_symbol_property("Footprint", "", 0, 0, hidden=True),
                *_symbol_property("Datasheet", "", 0, 0, hidden=True),
                "  )",
            ]
        )

    lines.extend(
        [
            "  (sheet_instances",
            '    (path "/" (page "1"))',
            "  )",
            "  (symbol_instances",
        ]
    )

    for comp in spec.components:
        symbol_uuid = _uuid(f"sym:{spec.name}:{comp.ref}")
        lines.append(
            f'    (path "/{symbol_uuid}" (reference "{comp.ref}") (unit 1) (value "{comp.value}") (footprint ""))'
        )

    lines.extend(["  )", ")"])
    return "\n".join(lines) + "\n"
