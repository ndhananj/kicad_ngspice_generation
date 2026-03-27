from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_COMMAND = "bash scripts/install_dev_env.sh"
SUPPORTED_LINUX_DISTROS = ("Ubuntu", "Debian", "Linux Mint")
NODE_MIN_VERSION = (18, 0, 0)
PYTHON_MODULES = (
    "numpy",
    "PIL",
    "cv2",
    "fitz",
    "svgpathtools",
    "segment_anything",
    "pytesseract",
)
BROWSER_CANDIDATES = (
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium-browser",
    "/usr/bin/chromium",
    "/usr/bin/brave-browser",
)


def supported_linux_distros_text() -> str:
    return ", ".join(SUPPORTED_LINUX_DISTROS)


def parse_os_release(text: str) -> dict[str, str]:
    data: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key] = value.strip().strip('"')
    return data


def linux_bootstrap_supported(os_release_text: str) -> bool:
    data = parse_os_release(os_release_text)
    distro_tokens = {
        token
        for value in (data.get("ID", ""), data.get("ID_LIKE", ""))
        for token in value.lower().split()
        if token
    }
    return bool(distro_tokens & {"ubuntu", "debian", "linuxmint"})


def missing_python_modules() -> list[str]:
    return [name for name in PYTHON_MODULES if importlib.util.find_spec(name) is None]


def find_browser_executable() -> str | None:
    configured = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
    if configured and Path(configured).exists():
        return configured
    for candidate in BROWSER_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return None


def parse_node_version(text: str) -> tuple[int, int, int] | None:
    raw = text.strip()
    if raw.startswith("v"):
        raw = raw[1:]
    parts = raw.split(".")
    if len(parts) < 3:
        return None
    try:
        return tuple(int(part) for part in parts[:3])
    except ValueError:
        return None


def node_version() -> tuple[int, int, int] | None:
    if shutil.which("node") is None:
        return None
    result = subprocess.run(["node", "--version"], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return None
    return parse_node_version(result.stdout)


def format_version(version: tuple[int, int, int]) -> str:
    return ".".join(str(part) for part in version)


def node_version_error() -> str | None:
    version = node_version()
    if version is None:
        return "node >= 18"
    if version < NODE_MIN_VERSION:
        return f"node >= 18 (found {format_version(version)})"
    return None


def npm_packages_available() -> bool:
    result = subprocess.run(
        ["node", "-e", "require('playwright'); require('@playwright/test');"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def playwright_browser_available() -> bool:
    result = subprocess.run(
        [
            "node",
            "-e",
            (
                "const fs = require('fs');"
                "const { chromium } = require('playwright');"
                "const path = chromium.executablePath();"
                "process.exit(path && fs.existsSync(path) ? 0 : 1);"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def frontend_runtime_issues() -> list[str]:
    issues: list[str] = []
    if shutil.which("node") is None:
        issues.append("node")
        return issues
    version_error = node_version_error()
    if version_error is not None:
        issues.append(version_error)
    if shutil.which("npm") is None:
        issues.append("npm")
        return issues
    if not npm_packages_available():
        issues.append("frontend npm packages")
        return issues
    if find_browser_executable() is None and not playwright_browser_available():
        issues.append("Playwright Chromium browser")
    return issues
