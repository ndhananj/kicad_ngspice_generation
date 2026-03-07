from __future__ import annotations

from mixedsig2cad import CircuitSpec


def rc_lowpass() -> CircuitSpec:
    return (
        CircuitSpec("rc_lowpass")
        .add("V1", "V", "DC 5", "vin", "0")
        .add("R1", "R", "1k", "vin", "vout")
        .add("C1", "C", "100n", "vout", "0")
        .analyze("op")
        .analyze("ac dec 20 10 1e6")
    )


def rc_highpass() -> CircuitSpec:
    return (
        CircuitSpec("rc_highpass")
        .add("V1", "V", "AC 1", "vin", "0")
        .add("C1", "C", "10n", "vin", "vmid")
        .add("R1", "R", "10k", "vmid", "0")
        .analyze("ac dec 20 10 1e6")
    )


def rlc_bandpass() -> CircuitSpec:
    return (
        CircuitSpec("rlc_bandpass")
        .add("V1", "V", "AC 1", "vin", "0")
        .add("R1", "R", "50", "vin", "n1")
        .add("L1", "L", "10m", "n1", "n2")
        .add("C1", "C", "100n", "n2", "0")
        .add("R2", "R", "1k", "n2", "0")
        .analyze("ac dec 40 10 100k")
    )


def diode_clipper() -> CircuitSpec:
    return (
        CircuitSpec("diode_clipper")
        .add("V1", "V", "SIN(0 5 1k)", "vin", "0")
        .add("R1", "R", "1k", "vin", "vout")
        .add("D1", "D", "D4148", "vout", "0", model="D4148")
        .add_model(".model D4148 D(Is=2.5e-9 N=1.75 Rs=0.6 Cjo=1.5p)")
        .analyze("tran 0.05ms 5ms")
    )


def bjt_common_emitter() -> CircuitSpec:
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


def opamp_inverting() -> CircuitSpec:
    return (
        CircuitSpec("opamp_inverting")
        .add("VCC", "V", "DC 12", "vcc", "0")
        .add("VEE", "V", "DC -12", "vee", "0")
        .add("VIN", "V", "SIN(0 0.5 500)", "vin", "0")
        .add("RIN", "R", "10k", "vin", "vminus")
        .add("RF", "R", "100k", "vout", "vminus")
        .add("XU1", "X", "OPAMP", "0", "vminus", "vout")
        .add_model(".subckt OPAMP 1 2 6")
        .add_model("EGAIN 6 0 1 2 1e5")
        .add_model("RINP 1 0 1e9")
        .add_model("RINN 2 0 1e9")
        .add_model(".ends OPAMP")
        .analyze("tran 0.1ms 10ms")
    )


def cmos_inverter() -> CircuitSpec:
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


def schmitt_trigger() -> CircuitSpec:
    return (
        CircuitSpec("schmitt_trigger")
        .add("VCC", "V", "DC 5", "vcc", "0")
        .add("VIN", "V", "PWL(0 0 1m 5 2m 0)", "vin", "0")
        .add("R1", "R", "100k", "vcc", "vout")
        .add("R2", "R", "100k", "vout", "vplus")
        .add("R3", "R", "10k", "vin", "vminus")
        .add("XU1", "X", "OPCMP", "vplus", "vminus", "vout")
        .add_model(".subckt OPCMP 1 2 6")
        .add_model("E1 6 0 1 2 1e6")
        .add_model("R1i 1 0 1e9")
        .add_model("R2i 2 0 1e9")
        .add_model(".ends OPCMP")
        .analyze("tran 10us 3ms")
    )


def all_examples() -> list[CircuitSpec]:
    return [
        rc_lowpass(),
        rc_highpass(),
        rlc_bandpass(),
        diode_clipper(),
        bjt_common_emitter(),
        opamp_inverting(),
        cmos_inverter(),
        schmitt_trigger(),
    ]
