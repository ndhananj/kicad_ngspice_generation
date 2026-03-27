from __future__ import annotations

from pathlib import Path
import shutil


FIXTURE_URL_PREFIX = "/_frontend_fixtures"
EXPECTED_FIXTURE_ARTIFACTS = {
    "rc_lowpass": {
        "editorScene": True,
        "svg": True,
        "pdf": False,
        "kicad": True,
        "ngspice": True,
        "reportTex": True,
        "circuitikzTex": True,
        "reportPdf": False,
    },
    "rc_highpass": {
        "editorScene": True,
        "svg": False,
        "pdf": False,
        "kicad": True,
        "ngspice": True,
        "reportTex": False,
        "circuitikzTex": True,
        "reportPdf": False,
    },
    "diode_clipper": {
        "editorScene": True,
        "svg": False,
        "pdf": False,
        "kicad": True,
        "ngspice": True,
        "reportTex": True,
        "circuitikzTex": True,
        "reportPdf": False,
    },
}
EXPECTED_FIXTURE_FILES = {
    "examples/generated/frontend/diode_clipper.scene.json",
    "examples/generated/frontend/rc_highpass.scene.json",
    "examples/generated/frontend/rc_lowpass.scene.json",
    "examples/generated/kicad/diode_clipper.kicad_sch",
    "examples/generated/kicad/rc_highpass.kicad_sch",
    "examples/generated/kicad/rc_lowpass.kicad_sch",
    "examples/generated/ngspice/diode_clipper.cir",
    "examples/generated/ngspice/rc_highpass.cir",
    "examples/generated/ngspice/rc_lowpass.cir",
    "examples/generated/svg/rc_lowpass.svg",
    "examples/generated/tex/diode_clipper.circuitikz.tex",
    "examples/generated/tex/diode_clipper.tex",
    "examples/generated/tex/rc_highpass.circuitikz.tex",
    "examples/generated/tex/rc_lowpass.circuitikz.tex",
    "examples/generated/tex/rc_lowpass.tex",
}


def build_sanitized_fixture_corpus(source_root: Path, destination_root: Path) -> Path:
    destination_root.mkdir(parents=True, exist_ok=True)
    for relative in EXPECTED_FIXTURE_FILES:
        source = source_root / relative
        target = destination_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return destination_root
