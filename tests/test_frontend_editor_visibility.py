from __future__ import annotations

import shutil
import subprocess
import sys

import pytest


def test_real_frontend_editor_is_visible_in_initial_viewport() -> None:
    if shutil.which("node") is None:
        raise AssertionError("node is required for frontend visibility validation")

    result = subprocess.run(
        [sys.executable, "scripts/validate_frontend_editor_visibility.py"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return
    combined_output = f"{result.stdout}\n{result.stderr}"
    if "PermissionError: [Errno 1] Operation not permitted" in combined_output:
        pytest.skip("local sandbox prevented the frontend validator from binding its loopback server")
    raise subprocess.CalledProcessError(result.returncode, result.args, output=result.stdout, stderr=result.stderr)
