"""Pytest wrapper around the cross-OS install smoke driver.

The dedicated ``install-smoke`` CI job runs ``scripts/install_smoke.py``
once per matrix cell (Ubuntu, macOS, Windows by Python 3.11, 3.12).
This wrapper runs the same script under the regular lint+test pytest
matrix so the smoke logic is exercised on every push, not only on the
dedicated job. The wrapper drives the script with ``HORUS_OS_SMOKE_DATA_DIR``
pointed at ``tmp_path`` so each pytest run is isolated.

The wrapper skips when the ``horus-os`` console script is not on PATH,
which is the case when running pytest from a non-installed checkout.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "install_smoke.py"


def test_install_smoke_runs(tmp_path: Path) -> None:
    """Run install_smoke.py under sys.executable; assert exit 0 and final marker."""
    if shutil.which("horus-os") is None:
        pytest.skip("horus-os console script not on PATH; skipping install-smoke wrapper")
    if not _SCRIPT_PATH.is_file():
        pytest.skip(f"install_smoke script not found at {_SCRIPT_PATH}")

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["HORUS_OS_SMOKE_DATA_DIR"] = str(tmp_path)
    env["ANTHROPIC_API_KEY"] = ""
    env["GEMINI_API_KEY"] = ""
    env["GOOGLE_API_KEY"] = ""

    proc = subprocess.run(
        [sys.executable, str(_SCRIPT_PATH)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    if proc.returncode != 0:
        # Surface full output so a CI failure is debuggable from the log alone.
        pytest.fail(
            "install_smoke.py exited "
            f"{proc.returncode}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )

    assert "All install-smoke checks passed." in proc.stdout, proc.stdout
    # Schema-on-disk check ran (v0.2 surface).
    assert "schema_version==4" in proc.stdout, proc.stdout
    # agents CRUD round-trip ran.
    assert "agents create smoke_test" in proc.stdout, proc.stdout
    assert "agents delete smoke_test" in proc.stdout, proc.stdout
    # Public-surface import smoke ran.
    assert "public surface imports and discover_adapters()" in proc.stdout, proc.stdout
    # v0.3 surface markers (Phase 30): per-module adapter imports and
    # the TestClient pass against /api/adapters + the toggle 404 path.
    assert "per-module adapter imports (lazy SDK pattern)" in proc.stdout, proc.stdout
    assert "GET /api/adapters shape + toggle 404 path" in proc.stdout, proc.stdout
