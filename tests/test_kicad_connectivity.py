from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import re

from examples.specs.catalog import cmos_inverter, opamp_inverting, rc_lowpass, schmitt_trigger
from mixedsig2cad.kicad_connectivity import _export_kicad_netlist, validate_kicad_connectivity


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

    def test_current_rc_lowpass_is_accepted_by_kicad_oracle(self) -> None:
        report = validate_kicad_connectivity(rc_lowpass(), GENERATED / "rc_lowpass.kicad_sch")
        self.assertTrue(report.passed)
        self.assertFalse(report.missing_attachments)
        self.assertFalse(report.erc_violations)

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

    def test_generated_bjt_common_emitter_contains_substrate_ground_drop(self) -> None:
        source = GENERATED / "bjt_common_emitter.kicad_sch"
        text = source.read_text(encoding="utf-8")
        self.assertIn('(wire (pts (xy 157.48 109.22) (xy 157.48 121.92))', text)
        self.assertIn('(junction (at 157.48 121.92)', text)

    def test_generated_cmos_inverter_uses_cmos_pin_roles(self) -> None:
        source = GENERATED / "cmos_inverter.kicad_sch"
        report = validate_kicad_connectivity(cmos_inverter(), source)
        self.assertTrue(report.passed)
        netlist = _export_kicad_netlist(source)
        self.assertIn('(name "/vdd")', netlist)
        self.assertRegex(netlist, r'\(node \(ref "MP1"\) \(pin "3"\).*')
        self.assertRegex(netlist, r'\(node \(ref "MP1"\) \(pin "4"\).*')
        self.assertRegex(netlist, r'\(node \(ref "MP1"\) \(pin "2"\).*')
        self.assertRegex(netlist, r'\(node \(ref "MN1"\) \(pin "2"\).*')
        self.assertIn('(name "/vout")', netlist)
        self.assertRegex(netlist, r'\(node \(ref "MP1"\) \(pin "1"\).*')
        self.assertRegex(netlist, r'\(node \(ref "MN1"\) \(pin "1"\).*')
        self.assertIn('(name "GND")', netlist)
        self.assertRegex(netlist, r'\(node \(ref "MN1"\) \(pin "3"\).*')
        self.assertRegex(netlist, r'\(node \(ref "MN1"\) \(pin "4"\).*')

    def test_generated_opamp_inverting_uses_textbook_pin_roles(self) -> None:
        source = GENERATED / "opamp_inverting.kicad_sch"
        report = validate_kicad_connectivity(opamp_inverting(), source)
        self.assertTrue(report.passed)
        netlist = _export_kicad_netlist(source)
        self.assertIn('(name "/vminus")', netlist)
        self.assertRegex(netlist, r'\(node \(ref "XU1"\) \(pin "2"\).*')
        self.assertRegex(netlist, r'\(node \(ref "RIN"\) \(pin "2"\).*')
        self.assertRegex(netlist, r'\(node \(ref "RF"\) \(pin "2"\).*')
        self.assertIn('(name "/vplus_ref")', netlist)
        self.assertRegex(netlist, r'\(node \(ref "XU1"\) \(pin "1"\).*')
        self.assertRegex(netlist, r'\(node \(ref "R3"\) \(pin "1"\).*')
        self.assertIn('(name "GND")', netlist)
        self.assertRegex(netlist, r'\(node \(ref "R3"\) \(pin "2"\).*')
        self.assertIn('(name "/vcc")', netlist)
        self.assertRegex(netlist, r'\(node \(ref "XU1"\) \(pin "4"\).*')
        self.assertIn('(name "/vee")', netlist)
        self.assertRegex(netlist, r'\(node \(ref "XU1"\) \(pin "5"\).*')

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
