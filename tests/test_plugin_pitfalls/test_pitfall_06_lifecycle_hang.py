"""Pitfall 6: Plugin failures crash horus-os instead of degrading to "plugin error" status.

See .planning/research/PITFALLS.md §"Pitfall 6" for the documented
threat. A plugin's ``start()`` coroutine hanging forever takes the
entire FastAPI lifespan down with it; a buggy plugin should never
brick horus-os.

The Phase 43 prevention pattern: every plugin lifecycle call goes
through ``asyncio.wait_for(adapter.start(ctx), timeout=2.0)`` — a hard
budget. A 5-second sleep in a plugin's ``start()`` is cut at 2.5s of
wall clock (the timeout) and surfaces as ``status="error" /
error_phase="start"`` on the plugin registry entry. The lifespan
continues serving requests; the broken plugin sits in the error
bucket where the dashboard renders it.

Two structural assertions:

1. META: ``tests/plugins/test_bounded_lifecycle.py`` (the Phase 43
   ISOLATE-02 substrate) exists on disk AND collects without errors
   AND contains a ``_SlowStartAdapter`` class with the expected sleep
   pattern.
2. INLINE: a synthetic ``_SlowStart`` adapter with
   ``await asyncio.sleep(3.0)`` in ``start`` wrapped in
   ``asyncio.wait_for(timeout=2.0)`` MUST raise ``asyncio.TimeoutError``
   within 2.5s wall clock — independent regression of the budget
   semantics regardless of whether the Phase 43 file changes shape.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BOUNDED_LIFECYCLE_FILE = REPO_ROOT / "tests" / "plugins" / "test_bounded_lifecycle.py"


def test_bounded_lifecycle_file_exists_on_disk() -> None:
    """The Phase 43 ISOLATE-02 substrate file MUST exist."""
    assert BOUNDED_LIFECYCLE_FILE.is_file(), (
        f"Pitfall 6 META: missing Phase 43 substrate {BOUNDED_LIFECYCLE_FILE}; "
        "ISOLATE-02 coverage has been deleted."
    )


def test_bounded_lifecycle_contains_slow_start_pattern() -> None:
    """The substrate file must still contain the 5.0s sleep + _SlowStartAdapter."""
    src = BOUNDED_LIFECYCLE_FILE.read_text(encoding="utf-8")
    assert "_SlowStartAdapter" in src, (
        "Pitfall 6 META: _SlowStartAdapter class missing from test_bounded_lifecycle.py"
    )
    assert "asyncio.sleep(5.0)" in src, (
        "Pitfall 6 META: 5.0s sleep pattern missing from test_bounded_lifecycle.py"
    )


def test_bounded_lifecycle_collects_without_errors() -> None:
    """``pytest --collect-only`` over the substrate file returns rc=0 + test ids."""
    args = [
        sys.executable,
        "-m",
        "pytest",
        "--collect-only",
        "-q",
        "--no-header",
        "tests/plugins/test_bounded_lifecycle.py",
    ]
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )
    assert result.returncode == 0, (
        f"Pitfall 6 META: collect-only on bounded-lifecycle failed (rc={result.returncode}).\n"
        f"stdout=\n{result.stdout}\nstderr=\n{result.stderr}"
    )
    assert "::test_" in result.stdout, (
        f"Pitfall 6 META: no test ids collected from test_bounded_lifecycle.py.\n"
        f"stdout=\n{result.stdout}"
    )


@pytest.mark.asyncio
async def test_asyncio_wait_for_cuts_slow_start_within_budget() -> None:
    """Inline regression: ``asyncio.wait_for(timeout=2.0)`` cuts a 3s sleep at ~2s.

    Independent of the Phase 43 substrate file: even if that file
    changes shape, the timeout-budget semantics MUST stay enforceable.
    The wall-clock budget (2.5s upper bound) is generous to absorb
    asyncio scheduling noise on slow CI runners.
    """

    class _SlowStart:
        async def start(self, _ctx: object) -> None:
            await asyncio.sleep(3.0)

    adapter = _SlowStart()
    start_t = time.monotonic()
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(adapter.start(None), timeout=2.0)
    elapsed = time.monotonic() - start_t
    assert elapsed < 2.5, (
        f"asyncio.wait_for(timeout=2.0) took {elapsed:.2f}s "
        "(expected <2.5s wall clock; Pitfall 6 budget regression)."
    )
