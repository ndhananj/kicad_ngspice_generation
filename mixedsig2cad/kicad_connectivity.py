from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .spec import CircuitSpec

CONNECTIVITY_ERC_TYPES = {
    "endpoint_off_grid",
    "pin_not_connected",
    "wire_dangling",
}


@dataclass(frozen=True, slots=True)
class KiCadErcViolation:
    type: str
    severity: str
    description: str


@dataclass(frozen=True, slots=True)
class ConnectivityReport:
    expected_nets: dict[str, tuple[str, ...]]
    actual_nets: dict[str, tuple[str, ...]]
    missing_attachments: tuple[str, ...]
    unexpected_attachments: tuple[str, ...]
    missing_nets: tuple[str, ...]
    extra_nets: tuple[str, ...]
    erc_violations: tuple[KiCadErcViolation, ...]
    passed: bool


def validate_kicad_connectivity(spec: CircuitSpec, schematic_path: str | Path) -> ConnectivityReport:
    path = Path(schematic_path)
    netlist_text = _export_kicad_netlist(path)
    from .importers.kicad_schematic import import_kicad_schematic

    imported = import_kicad_schematic(path)
    shapes_by_ref = {shape.ref: shape for shape in imported.shapes}
    actual_nets = _parse_netlist_clusters(netlist_text, expected_refs={comp.ref for comp in spec.components})
    expected_nets = _expected_net_clusters(spec, shapes_by_ref=shapes_by_ref)

    expected_attachments = {attachment for attachments in expected_nets.values() for attachment in attachments}
    actual_attachments = {attachment for attachments in actual_nets.values() for attachment in attachments}
    missing_attachments = tuple(sorted(expected_attachments - actual_attachments))
    unexpected_attachments = tuple(sorted(actual_attachments - expected_attachments))

    expected_clusters = {attachments: name for name, attachments in expected_nets.items()}
    actual_clusters = {attachments: name for name, attachments in actual_nets.items()}
    missing_nets = tuple(
        sorted(
            name
            for attachments, name in expected_clusters.items()
            if attachments not in actual_clusters
        )
    )
    extra_nets = tuple(
        sorted(
            name
            for attachments, name in actual_clusters.items()
            if attachments not in expected_clusters
        )
    )

    erc_violations = tuple(
        violation
        for violation in _run_kicad_erc(path)
        if violation.type in CONNECTIVITY_ERC_TYPES and violation.severity in {"error", "warning"}
    )

    return ConnectivityReport(
        expected_nets=expected_nets,
        actual_nets=actual_nets,
        missing_attachments=missing_attachments,
        unexpected_attachments=unexpected_attachments,
        missing_nets=missing_nets,
        extra_nets=extra_nets,
        erc_violations=erc_violations,
        passed=not missing_attachments and not unexpected_attachments and not missing_nets and not extra_nets and not erc_violations,
    )


def _expected_net_clusters(spec: CircuitSpec, *, shapes_by_ref) -> dict[str, tuple[str, ...]]:
    from .symbols import kicad_pin_map

    clusters: dict[str, list[str]] = {}
    for comp in spec.components:
        shape = shapes_by_ref.get(comp.ref)
        if shape is None:
            continue
        pin_map = kicad_pin_map(shape.shape, shape.orientation)
        terminal_names = tuple(pin_map)
        for pin_index, net_name in enumerate(comp.nodes, start=1):
            terminal_name = terminal_names[min(pin_index - 1, len(terminal_names) - 1)]
            clusters.setdefault(net_name, []).append(f"{comp.ref}.{pin_map[terminal_name]}")
    return {
        net_name: tuple(sorted(attachments))
        for net_name, attachments in sorted(clusters.items())
        if len(attachments) >= 2
    }


def _parse_netlist_clusters(text: str, *, expected_refs: set[str]) -> dict[str, tuple[str, ...]]:
    clusters: dict[str, tuple[str, ...]] = {}
    for block in _nested_blocks(text, "net"):
        name_match = re.search(r'\(name "([^"]+)"\)', block)
        if name_match is None:
            continue
        attachments = tuple(
            sorted(
                f"{ref}.{pin}"
                for ref, pin in re.findall(r'\(node\s+\(ref "([^"]+)"\)\s+\(pin "([^"]+)"\)', block)
                if ref in expected_refs
            )
        )
        if len(attachments) >= 2:
            clusters[name_match.group(1)] = attachments
    return clusters


def _nested_blocks(text: str, kind: str) -> list[str]:
    blocks: list[str] = []
    needle = f"({kind} "
    start = 0
    while True:
        idx = text.find(needle, start)
        if idx < 0:
            break
        blocks.append(_extract_nested_block(text[idx:], needle))
        start = idx + len(needle)
    return blocks


def _run_kicad_erc(path: Path) -> tuple[KiCadErcViolation, ...]:
    kicad_cli = shutil.which("kicad-cli")
    if not kicad_cli:
        raise AssertionError("kicad-cli is required for connectivity validation")
    with tempfile.TemporaryDirectory(prefix="kicad-erc-") as tmp_home:
        env = dict(os.environ)
        env["HOME"] = tmp_home
        env["XDG_CONFIG_HOME"] = os.path.join(tmp_home, ".config")
        output = Path(tmp_home) / "erc.json"
        result = subprocess.run(
            [
                kicad_cli,
                "sch",
                "erc",
                "--format",
                "json",
                "--severity-all",
                "--output",
                str(output),
                str(path),
            ],
            capture_output=True,
            text=True,
            env=env,
        )
        if result.returncode != 0 or not output.exists():
            raise AssertionError(
                f"kicad-cli ERC failed for {path}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
        payload = json.loads(output.read_text(encoding="utf-8"))
    violations: list[KiCadErcViolation] = []
    for sheet in payload.get("sheets", []):
        for item in sheet.get("violations", []):
            violations.append(
                KiCadErcViolation(
                    type=item.get("type", ""),
                    severity=item.get("severity", ""),
                    description=item.get("description", ""),
                )
            )
    return tuple(violations)


def _export_kicad_netlist(path: Path) -> str:
    kicad_cli = shutil.which("kicad-cli")
    if not kicad_cli:
        raise AssertionError("kicad-cli is required for connectivity validation")
    with tempfile.TemporaryDirectory(prefix="kicad-netlist-") as tmp_home:
        env = dict(os.environ)
        env["HOME"] = tmp_home
        env["XDG_CONFIG_HOME"] = os.path.join(tmp_home, ".config")
        output = Path(tmp_home) / f"{path.stem}.net"
        result = subprocess.run(
            [
                kicad_cli,
                "sch",
                "export",
                "netlist",
                "--format",
                "kicadsexpr",
                "--output",
                str(output),
                str(path),
            ],
            capture_output=True,
            text=True,
            env=env,
        )
        if result.returncode != 0 or not output.exists():
            raise AssertionError(
                f"kicad-cli netlist export failed for {path}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
        return output.read_text(encoding="utf-8")


def _top_level_blocks(text: str, kind: str) -> list[str]:
    blocks: list[str] = []
    needle = f"({kind} "
    start = 0
    while True:
        idx = text.find(needle, start)
        if idx < 0:
            break
        if _depth_at(text, idx) == 1:
            blocks.append(_extract_nested_block(text[idx:], needle))
        start = idx + len(needle)
    return blocks


def _depth_at(text: str, limit: int) -> int:
    depth = 0
    in_string = False
    escape = False
    for ch in text[:limit]:
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
    return depth


def _extract_nested_block(text: str, needle: str) -> str:
    start = text.find(needle)
    if start < 0:
        raise AssertionError(f"missing block starting with {needle}")
    depth = 0
    in_string = False
    escape = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]
    raise AssertionError(f"unterminated block starting with {needle}")
