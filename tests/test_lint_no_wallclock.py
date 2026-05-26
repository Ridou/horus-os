"""Pytest wrapper around scripts/lint_no_wallclock.py so the gate runs in CI.

Phase 32 Pitfall 3 prevention. Phase 33 will add `time.perf_counter()`-based
capture sites to agent.py and tools/loop.py. If a future commit ever
re-introduces `time.time()` into the watched paths, this test fails the
unit-test job.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_no_wallclock_in_observability_paths() -> None:
    script = REPO_ROOT / "scripts" / "lint_no_wallclock.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"lint_no_wallclock found violations:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
