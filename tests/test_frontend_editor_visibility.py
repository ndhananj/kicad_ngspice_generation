from __future__ import annotations

import shutil
import subprocess
import sys


def test_real_frontend_editor_is_visible_in_initial_viewport() -> None:
    if shutil.which("node") is None:
        raise AssertionError("node is required for frontend visibility validation")

    subprocess.run(
        [sys.executable, "scripts/validate_frontend_editor_visibility.py"],
        check=True,
    )
