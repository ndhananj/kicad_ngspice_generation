from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from mixedsig2cad import CircuitSpec
from mixedsig2cad.design import (
    ExampleDesign,
    LayoutComponentIntent,
    LayoutSupportIntent,
    LayoutTextIntent,
    RoutedNetIntent,
    SchematicLayoutIntent,
)
from mixedsig2cad.models import Point


def rc_lowpass() -> ExampleDesign:
    return _example_design("rc_lowpass")


def rc_highpass() -> ExampleDesign:
    return _example_design("rc_highpass")


def rlc_bandpass() -> ExampleDesign:
    return _example_design("rlc_bandpass")


def diode_clipper() -> ExampleDesign:
    return _example_design("diode_clipper")


def bjt_common_emitter() -> ExampleDesign:
    return _example_design("bjt_common_emitter")


def opamp_inverting() -> ExampleDesign:
    return _example_design("opamp_inverting")


def cmos_inverter() -> ExampleDesign:
    return _example_design("cmos_inverter")


def schmitt_trigger() -> ExampleDesign:
    return _example_design("schmitt_trigger")


def all_examples() -> list[ExampleDesign]:
    return [_example_design(spec.name) for spec in _all_circuit_specs()]


def _all_circuit_specs() -> list[CircuitSpec]:
    return [
        _rc_lowpass_spec(),
        _rc_highpass_spec(),
        _rlc_bandpass_spec(),
        _diode_clipper_spec(),
        _bjt_common_emitter_spec(),
        _opamp_inverting_spec(),
        _cmos_inverter_spec(),
        _schmitt_trigger_spec(),
    ]


def _example_design(name: str) -> ExampleDesign:
    spec = next(spec for spec in _all_circuit_specs() if spec.name == name)
    layout = _seed_layouts()[name]
    return ExampleDesign(name=name, circuit=spec, layout=layout)


@lru_cache(maxsize=1)
def _seed_layouts() -> dict[str, SchematicLayoutIntent]:
    payload = json.loads((Path(__file__).with_name("seeded_layouts.json")).read_text(encoding="utf-8"))
    layouts = {}
    for name, entry in payload.items():
        layouts[name] = SchematicLayoutIntent(
            name=entry["name"],
            components=tuple(
                LayoutComponentIntent(
                    ref=item["ref"],
                    center=_point(item["center"]),
                    orientation=_component_orientation(name, item["ref"], item["orientation"]),
                    reference_position=_point(item["reference_position"]),
                    value_position=_point(item["value_position"]),
                    hidden_reference=item.get("hidden_reference", False),
                )
                for item in entry["components"]
            ),
            supports=tuple(
                LayoutSupportIntent(
                    ref=item["ref"],
                    shape=item["shape"],
                    value=item["value"],
                    center=_point(item["center"]),
                    orientation=item["orientation"],
                    reference_position=_point(item["reference_position"]),
                    value_position=_point(item["value_position"]),
                    hidden_reference=item.get("hidden_reference", False),
                )
                for item in entry.get("supports", [])
            ),
            texts=tuple(
                LayoutTextIntent(
                    text=item["text"],
                    role=item["role"],
                    position=_point(item["position"]),
                    owner_ref=item["owner_ref"],
                    font_size=item.get("font_size", 1.27),
                )
                for item in entry.get("texts", [])
            ),
            routed_nets=tuple(
                RoutedNetIntent(
                    name=item["name"],
                    segments=tuple(tuple(_point(point) for point in segment) for segment in item.get("segments", [])),
                    junctions=tuple(_point(point) for point in item.get("junctions", [])),
                )
                for item in entry.get("routed_nets", [])
            ),
        )
    return layouts


def _point(payload: dict[str, float]) -> Point:
    return Point(payload["x"], payload["y"])


def _component_orientation(name: str, ref: str, orientation: str) -> str:
    if name == "schmitt_trigger" and ref == "R3":
        return "horizontal_flipped"
    return orientation


def _rc_lowpass_spec() -> CircuitSpec:
    return (
        CircuitSpec("rc_lowpass")
        .add("V1", "V", "DC 5", "vin", "0")
        .add("R1", "R", "1k", "vin", "vout")
        .add("C1", "C", "100n", "vout", "0")
        .analyze("op")
        .analyze("ac dec 20 10 1e6")
    )


def _rc_highpass_spec() -> CircuitSpec:
    return (
        CircuitSpec("rc_highpass")
        .add("V1", "V", "AC 1", "vin", "0")
        .add("C1", "C", "10n", "vin", "vmid")
        .add("R1", "R", "10k", "vmid", "0")
        .analyze("ac dec 20 10 1e6")
    )


def _rlc_bandpass_spec() -> CircuitSpec:
    return (
        CircuitSpec("rlc_bandpass")
        .add("V1", "V", "AC 1", "vin", "0")
        .add("R1", "R", "50", "vin", "n1")
        .add("L1", "L", "10m", "n1", "n2")
        .add("C1", "C", "100n", "n2", "0")
        .add("R2", "R", "1k", "n2", "0")
        .analyze("ac dec 40 10 100k")
    )


def _diode_clipper_spec() -> CircuitSpec:
    return (
        CircuitSpec("diode_clipper")
        .add("V1", "V", "SIN(0 5 1k)", "vin", "0")
        .add("R1", "R", "1k", "vin", "vout")
        .add("D1", "D", "D4148", "vout", "0", model="D4148")
        .add_model(".model D4148 D(Is=2.5e-9 N=1.75 Rs=0.6 Cjo=1.5p)")
        .analyze("tran 0.05ms 5ms")
    )


def _bjt_common_emitter_spec() -> CircuitSpec:
    return (
        CircuitSpec("bjt_common_emitter")
        .add("VCC", "V", "DC 12", "vcc", "0")
        .add("VS", "V", "SIN(0 0.02 1k)", "vin_src", "0")
        .add("CB", "C", "10u", "vin_src", "base")
        .add("R1", "R", "100k", "vcc", "base")
        .add("R2", "R", "22k", "base", "0")
        .add("RC", "R", "2.2k", "vcc", "collector")
        .add("RE", "R", "1k", "emitter", "0")
        .add("CE", "C", "100u", "emitter", "0")
        .add("CC", "C", "10u", "collector", "vout")
        .add("RL", "R", "10k", "vout", "0")
        .add("Q1", "Q", "2N3904", "collector", "base", "emitter", model="Q2N3904")
        .add_model(".model Q2N3904 NPN(Is=6.734f Bf=255.9 Vaf=74.03 Cje=4.493p Tf=301.2p)")
        .analyze("tran 10us 5ms")
    )


def _opamp_inverting_spec() -> CircuitSpec:
    return (
        CircuitSpec("opamp_inverting")
        .add("VCC", "V", "DC 12", "vcc", "0")
        .add("VEE", "V", "DC -12", "vee", "0")
        .add("VIN", "V", "SIN(0 0.5 500)", "vin", "0")
        .add("RIN", "R", "10k", "vin", "vminus")
        .add("RF", "R", "100k", "vout", "vminus")
        .add("R3", "R", "10k", "vplus_ref", "0")
        .add("XU1", "X", "OPAMP", "vplus_ref", "vminus", "vout", "vcc", "vee")
        .add_model(".subckt OPAMP 1 2 6 4 5")
        .add_model("EGAIN 6 0 1 2 1e5")
        .add_model("RINP 1 0 1e9")
        .add_model("RINN 2 0 1e9")
        .add_model(".ends OPAMP")
        .analyze("tran 0.1ms 10ms")
    )


def _cmos_inverter_spec() -> CircuitSpec:
    return (
        CircuitSpec("cmos_inverter")
        .add("VDD", "V", "DC 3.3", "vdd", "0")
        .add("VIN", "V", "PULSE(0 3.3 0 1n 1n 10n 20n)", "vin", "0")
        .add("MP1", "M", "PM1", "vout", "vin", "vdd", "vdd", model="PM1")
        .add("MN1", "M", "NM1", "vout", "vin", "0", "0", model="NM1")
        .add_model(".model NM1 NMOS (Level=1 Vto=0.7 Kp=120u Lambda=0.03)")
        .add_model(".model PM1 PMOS (Level=1 Vto=-0.7 Kp=60u Lambda=0.04)")
        .analyze("tran 0.1n 100n")
    )


def _schmitt_trigger_spec() -> CircuitSpec:
    return (
        CircuitSpec("schmitt_trigger")
        .add("VCC", "V", "DC 5", "vcc", "0")
        .add("VIN", "V", "PWL(0 0 1m 5 2m 0)", "vin", "0")
        .add("VREF", "V", "DC 2.5", "vref", "0")
        .add("R1", "R", "100k", "vref", "vplus")
        .add("R2", "R", "100k", "vplus", "0")
        .add("R3", "R", "100k", "vout", "vplus")
        .add("XU1", "X", "OPCMP", "vplus", "vin", "vout", "vcc", "0")
        .add_model(".subckt OPCMP 1 2 6 4 5")
        .add_model("E1 6 0 1 2 1e6")
        .add_model("R1i 1 0 1e9")
        .add_model("R2i 2 0 1e9")
        .add_model(".ends OPCMP")
        .analyze("tran 10us 3ms")
    )
