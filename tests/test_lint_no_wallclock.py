"""Pytest wrapper around scripts/lint_no_wallclock.py so the gate runs in CI.

Phase 32 Pitfall 3 prevention. Phase 33 extended WATCHED_FILES to cover
server/api.py because the SSE chat_stream branch publishes
LLMCallEvents whose latency_ms must use perf_counter. If a future
commit ever re-introduces `time.time()` into the watched paths, the
gate test fails the unit-test job.
"""

from __future__ import annotations

import importlib.util
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


def _load_lint_module():
    """Import scripts/lint_no_wallclock.py as a module without modifying sys.path."""
    script = REPO_ROOT / "scripts" / "lint_no_wallclock.py"
    spec = importlib.util.spec_from_file_location("_lint_no_wallclock_under_test", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_lint_no_wallclock_includes_server_api() -> None:
    """Phase 33: server/api.py joined the watched scope (Pitfall 3)."""
    mod = _load_lint_module()
    watched_files = {str(p) for p in mod.WATCHED_FILES}
    expected = str(REPO_ROOT / "src" / "horus_os" / "server" / "api.py")
    assert expected in watched_files, (
        f"server/api.py missing from WATCHED_FILES; got: {sorted(watched_files)}"
    )


def test_lint_guard_fires_on_violation(monkeypatch) -> None:
    """Sanity: the scanner reports a violation when time.time() is present.

    Creates a temp Python file UNDER the repo root (so the scanner's
    `relative_to(REPO_ROOT)` does not raise), points WATCHED_FILES at
    it, and asserts main() returns 1. Cleaned up via the test's own
    try/finally so a failure mid-test does not leave a stale file.
    """
    bad = REPO_ROOT / "_lint_guard_under_test_scratch.py"
    try:
        bad.write_text("import time\n\nx = time.time()\n", encoding="utf-8")
        mod = _load_lint_module()
        monkeypatch.setattr(mod, "WATCHED_DIRS", ())
        monkeypatch.setattr(mod, "WATCHED_FILES", (bad,))
        rc = mod.main()
        assert rc == 1
    finally:
        if bad.exists():
            bad.unlink()
