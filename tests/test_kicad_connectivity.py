from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import re

from examples.specs.catalog import cmos_inverter, opamp_inverting, rc_lowpass, schmitt_trigger
from mixedsig2cad.geometry import validate_schematic_geometry
from mixedsig2cad.importers.kicad_schematic import import_kicad_schematic
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

    def test_removed_opamp_output_label_is_rejected(self) -> None:
        source = GENERATED / "opamp_inverting.kicad_sch"
        mutated = self._mutate(
            source,
            lambda text: re.sub(
                r'  \(label "vout" \(at [-0-9.]+ 69\.85 0\)\n'
                r'    \(effects \(font \(size [-0-9.]+ [-0-9.]+\)\)\)\n'
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
                '  (junction (at 156.21 97.79) (diameter 1.016) (color 0 0 0 0))\n',
                '',
                1,
            ),
        )
        with self.assertRaises(AssertionError):
            validate_schematic_geometry(import_kicad_schematic(mutated))

    def test_generated_bjt_common_emitter_contains_substrate_ground_drop(self) -> None:
        source = GENERATED / "bjt_common_emitter.kicad_sch"
        text = source.read_text(encoding="utf-8")
        self.assertIn('(wire (pts (xy 157.48 109.22) (xy 157.48 121.92))', text)
        self.assertIn('(junction (at 157.48 121.92)', text)

    def test_generated_cmos_inverter_uses_cmos_pin_roles(self) -> None:
        source = GENERATED / "cmos_inverter.kicad_sch"
        report = validate_kicad_connectivity(cmos_inverter(), source)
        self.assertTrue(report.passed)
        text = source.read_text(encoding="utf-8")
        self.assertIn('(junction (at 110.49 113.03)', text)
        self.assertIn('(wire (pts (xy 83.82 113.03) (xy 110.49 113.03))', text)
        self.assertIn('(wire (pts (xy 110.49 88.90) (xy 110.49 113.03))', text)
        self.assertIn('(wire (pts (xy 110.49 137.16) (xy 110.49 113.03))', text)
        self.assertNotIn('(wire (pts (xy 144.78 88.90) (xy 144.78 137.16))', text)
        self.assertNotIn('(wire (pts (xy 144.78 113.03) (xy 110.49 113.03))', text)
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
        self.assertIn('(name "VCC")', netlist)
        self.assertRegex(netlist, r'\(node \(ref "XU1"\) \(pin "4"\).*')
        self.assertIn('(name "VEE")', netlist)
        self.assertRegex(netlist, r'\(node \(ref "XU1"\) \(pin "5"\).*')

    def test_generated_opamp_inverting_uses_power_symbols_instead_of_supply_labels(self) -> None:
        source = GENERATED / "opamp_inverting.kicad_sch"
        text = source.read_text(encoding="utf-8")
        self.assertEqual(text.count('(symbol (lib_id "VCC")'), 4)
        self.assertEqual(text.count('(symbol (lib_id "VEE")'), 0)
        self.assertNotIn('(label "vcc"', text)
        self.assertNotIn('(label "vee"', text)
        self.assertNotIn('(wire (pts (xy 167.64 78.74)', text)
        self.assertNotIn('(wire (pts (xy 167.64 110.49)', text)
        self.assertIn('(symbol (lib_id "VCC") (at 80.01 90.17 0)', text)
        self.assertIn('(property "Value" "VEE" (at 80.01 93.98 0)', text)
        self.assertIn('(symbol (lib_id "VCC") (at 167.64 100.33 180)', text)
        self.assertIn('(property "Value" "VEE" (at 167.64 104.14 0)', text)

    def test_generated_opamp_inverting_uses_larger_readable_signal_labels(self) -> None:
        source = GENERATED / "opamp_inverting.kicad_sch"
        text = source.read_text(encoding="utf-8")
        self.assertIn('(label "vin" (at 123.19 82.55 0)\n    (effects (font (size 1.50 1.50)))', text)
        self.assertIn('(label "vplus_ref" (at 162.56 97.79 0)\n    (effects (font (size 1.50 1.50)))', text)
        self.assertIn('(label "vminus" (at 162.56 82.55 0)\n    (effects (font (size 1.50 1.50)))', text)
        self.assertIn('(label "vout" (at 177.80 69.85 0)\n    (effects (font (size 1.50 1.50)))', text)

    def test_generated_opamp_inverting_uses_compact_feedback_loop(self) -> None:
        source = GENERATED / "opamp_inverting.kicad_sch"
        text = source.read_text(encoding="utf-8")
        self.assertIn('(wire (pts (xy 177.80 90.17) (xy 177.80 69.85))', text)
        self.assertIn('(wire (pts (xy 162.56 69.85) (xy 177.80 69.85))', text)
        self.assertIn('(wire (pts (xy 162.56 87.63) (xy 162.56 82.55))', text)
        self.assertNotIn('(wire (pts (xy 179.07 48.26) (xy 156.21 48.26))', text)
        self.assertNotIn('(wire (pts (xy 156.21 48.26) (xy 156.21 87.63))', text)

    def test_generated_schmitt_trigger_uses_canonical_pin_roles(self) -> None:
        source = GENERATED / "schmitt_trigger.kicad_sch"
        report = validate_kicad_connectivity(schmitt_trigger(), source)
        self.assertTrue(report.passed)
        netlist = _export_kicad_netlist(source)
        vin_net = re.search(r'\(net \(code "[^"]+"\) \(name "/vin"\)(.*?)\)\n    \(net ', netlist, re.S)
        self.assertIsNotNone(vin_net)
        self.assertIn('(name "/vin")', netlist)
        self.assertRegex(netlist, r'\(node \(ref "XU1"\) \(pin "2"\).*')
        self.assertRegex(netlist, r'\(node \(ref "VIN"\) \(pin "2"\).*')
        self.assertNotIn('(node (ref "XU1") (pin "1")', vin_net.group(1))
        self.assertIn('(name "/vplus")', netlist)
        self.assertRegex(netlist, r'\(node \(ref "XU1"\) \(pin "1"\).*')
        self.assertRegex(netlist, r'\(node \(ref "R1"\) \(pin "2"\).*')
        self.assertRegex(netlist, r'\(node \(ref "R2"\) \(pin "2"\).*')
        self.assertRegex(netlist, r'\(node \(ref "R3"\) \(pin "2"\).*')
        self.assertIn('(name "/vref")', netlist)
        self.assertRegex(netlist, r'\(node \(ref "VREF"\) \(pin "1"\).*')
        self.assertRegex(netlist, r'\(node \(ref "R1"\) \(pin "1"\).*')
        self.assertIn('(name "/vout")', netlist)
        self.assertRegex(netlist, r'\(node \(ref "XU1"\) \(pin "3"\).*')
        self.assertRegex(netlist, r'\(node \(ref "R3"\) \(pin "1"\).*')
        self.assertIn('(name "VCC")', netlist)
        self.assertRegex(netlist, r'\(node \(ref "XU1"\) \(pin "4"\).*')
        self.assertIn('(name "GND")', netlist)
        self.assertRegex(netlist, r'\(node \(ref "XU1"\) \(pin "5"\).*')

    def test_removed_schmitt_trigger_positive_input_junction_is_rejected(self) -> None:
        source = GENERATED / "schmitt_trigger.kicad_sch"
        mutated = self._mutate(
            source,
            lambda text: re.sub(
                r'  \(wire \(pts \(xy 160\.02 97\.79\) \(xy 162\.56 97\.79\)\)\n'
                r'    \(stroke \(width 0\) \(type solid\) \(color 0 0 0 0\)\)\n'
                r'    \(uuid [^)]+\)\n'
                r'  \)\n',
                "",
                text,
                count=1,
            ),
        )
        with self.assertRaises(AssertionError):
            validate_schematic_geometry(import_kicad_schematic(mutated))

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
