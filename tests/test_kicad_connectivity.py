from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import re

from examples.specs.catalog import opamp_inverting, rc_lowpass, schmitt_trigger
from mixedsig2cad.kicad_connectivity import validate_kicad_connectivity


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "examples" / "generated" / "kicad"


class KiCadConnectivityTests(unittest.TestCase):
    def _mutate(self, source: Path, transform) -> Path:
        text = source.read_text(encoding="utf-8")
        mutated = transform(text)
        tmpdir = tempfile.TemporaryDirectory(prefix="mixedsig2cad-connectivity-")
        self.addCleanup(tmpdir.cleanup)
        path = Path(tmpdir.name) / source.name
        path.write_text(mutated, encoding="utf-8")
        return path

    def test_current_rc_lowpass_is_rejected_by_kicad_oracle(self) -> None:
        report = validate_kicad_connectivity(rc_lowpass(), GENERATED / "rc_lowpass.kicad_sch")
        self.assertFalse(report.passed)
        self.assertTrue(report.missing_attachments)
        self.assertTrue(report.erc_violations)

    def test_removed_opamp_wire_is_rejected(self) -> None:
        source = GENERATED / "opamp_inverting.kicad_sch"
        mutated = self._mutate(
            source,
            lambda text: re.sub(
                r'  \(wire \(pts \(xy 177\.80 90\.17\) \(xy 184\.15 90\.17\)\)\n'
                r'    \(stroke \(width 0\) \(type solid\) \(color 0 0 0 0\)\)\n'
                r'    \(uuid [^)]+\)\n'
                r'  \)\n',
                '',
                text,
                count=1,
            ),
        )
        report = validate_kicad_connectivity(opamp_inverting(), mutated)
        self.assertFalse(report.passed)
        self.assertTrue(report.missing_attachments or report.missing_nets or report.erc_violations)

    def test_removed_junction_is_rejected(self) -> None:
        source = GENERATED / "schmitt_trigger.kicad_sch"
        mutated = self._mutate(
            source,
            lambda text: text.replace(
                '  (junction (at 163.83 90.17) (diameter 1.016) (color 0 0 0 0))\n',
                '',
                1,
            ),
        )
        report = validate_kicad_connectivity(schmitt_trigger(), mutated)
        self.assertFalse(report.passed)
        self.assertTrue(report.missing_nets or report.erc_violations)

    def test_off_grid_wire_is_rejected(self) -> None:
        source = GENERATED / "rc_lowpass.kicad_sch"
        mutated = self._mutate(
            source,
            lambda text: text.replace('(xy 55.88 78.74)', '(xy 55.89 78.74)', 1),
        )
        report = validate_kicad_connectivity(rc_lowpass(), mutated)
        self.assertFalse(report.passed)
        self.assertTrue(any(item.type == "endpoint_off_grid" for item in report.erc_violations))


if __name__ == "__main__":
    unittest.main()
