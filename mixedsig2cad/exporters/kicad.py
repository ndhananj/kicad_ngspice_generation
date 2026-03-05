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
        lib_id = SYMBOL_BY_KIND.get(comp.kind, "Device:R")
        x = base_x + (idx - 1) % 4 * 35
        if idx > 1 and (idx - 1) % 4 == 0:
            y += 30
        node_text = " ".join(comp.nodes)
        lines.extend(
            [
                f"  (text \"nodes: {node_text}\" (at {x} {y-8} 0)",
                "    (effects (font (size 1.27 1.27)) (justify left))",
                "  )",
                f"  (symbol (lib_id \"{lib_id}\") (at {x} {y} 0) (unit 1)",
                "    (in_bom yes) (on_board yes)",
                f"    (uuid {symbol_uuid})",
                f"    (property \"Reference\" \"{comp.ref}\" (at {x} {y-3.81} 0)",
                "      (effects (font (size 1.27 1.27)))",
                "    )",
                f"    (property \"Value\" \"{comp.value}\" (at {x} {y+3.81} 0)",
                "      (effects (font (size 1.27 1.27)))",
                "    )",
                '    (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27))) (hide yes))',
                '    (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27))) (hide yes))',
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
