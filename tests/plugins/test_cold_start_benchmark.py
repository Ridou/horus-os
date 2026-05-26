"""TEST-18 cold-start benchmark: discover + load with zero plugins < 100ms.

The pipeline runs N=11 samples; the first is discarded as a cold-cache
warm-up. The remaining 10 samples are sorted and the median is
compared against the 100ms upper bound. Failure message names the
median wall clock so a CI regression is self-diagnostic.

The benchmark also exercises the contract that ``discover_plugins()``
+ ``PluginLoader.load()`` with ZERO installed plugins is the happy
path: ``entry_points`` returns an empty selection,
``HORUS_OS_PLUGIN_DIR`` points at an empty tmp directory, no specs
materialize, no loads happen, the lifespan completes in well under
the 100ms threshold (current Phase 41 baseline:
entry_points_discovery_ms = 1.909 on darwin/3.12).
"""

from __future__ import annotations

import os
import statistics
import time
from pathlib import Path

import pytest

from horus_os.adapters.base import AdapterRegistry
from horus_os.plugins import PluginLoader, discover_plugins
from horus_os.tools.registry import ToolRegistry

COLD_START_THRESHOLD_MS = 100.0
N_SAMPLES = 11  # first sample discarded; the remaining 10 feed the median.


def _timed_pipeline() -> float:
    """Run one full discover + load pass with zero plugins; return wall ms."""
    start = time.perf_counter()
    specs, errors = discover_plugins()
    # Zero plugins -> zero loads. Still exercise the loader's __init__
    # so the benchmark covers the constructor cost.
    loader = PluginLoader(
        tool_registry=ToolRegistry(),
        adapter_registry=AdapterRegistry(),
    )
    for spec in specs:
        loader.load(spec)
    # Defensive: make sure no real plugin slipped in (the test fixture
    # rebinds entry_points + HORUS_OS_PLUGIN_DIR, so this is a no-op
    # assertion that doubles as a benchmark sanity check).
    assert specs == []
    assert errors == []
    return (time.perf_counter() - start) * 1000.0


def test_cold_start_zero_plugins_below_100ms(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Median of N=10 samples (after warm-up) is below the 100ms threshold."""
    # Rebind entry_points to an always-empty source.
    def _empty_entry_points(*, group: str) -> list[object]:
        return []

    monkeypatch.setattr(
        "horus_os.plugins.discovery.entry_points", _empty_entry_points
    )
    # Point the filesystem walk at an empty tmp dir.
    empty_plugins_dir = tmp_path / "plugins"
    empty_plugins_dir.mkdir()
    monkeypatch.setenv("HORUS_OS_PLUGIN_DIR", str(empty_plugins_dir))

    samples: list[float] = []
    for _ in range(N_SAMPLES):
        samples.append(_timed_pipeline())
    # Discard the first sample to absorb cold-cache variance.
    measured = samples[1:]
    median_ms = statistics.median(measured)

    assert median_ms < COLD_START_THRESHOLD_MS, (
        f"Cold-start regression: median wall clock = {median_ms:.3f}ms "
        f"over N={len(measured)} samples; threshold = {COLD_START_THRESHOLD_MS}ms. "
        f"Samples (ms): {[round(s, 3) for s in measured]}"
    )

    # Optional trend capture: when HORUS_OS_CAPTURE_PERF=1, write one
    # JSON line to tests/perf/ for trend tracking. CI does not set
    # the env var, so the file stays untouched on green builds.
    if os.environ.get("HORUS_OS_CAPTURE_PERF") == "1":
        _capture_trend_line(median_ms, len(measured))


def _capture_trend_line(median_ms: float, n_samples: int) -> None:
    """Append a trend-capture record to tests/perf/v0_5_phase42_cold_start.json."""
    import json
    import sys
    from datetime import UTC, datetime

    from horus_os import __version__

    record = {
        "os": sys.platform,
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "horus_os_version": __version__,
        "median_ms": round(median_ms, 3),
        "n_samples": n_samples,
        "threshold_ms": COLD_START_THRESHOLD_MS,
        "captured_at": datetime.now(UTC).isoformat(),
    }
    perf_dir = Path(__file__).resolve().parents[1] / "perf"
    perf_dir.mkdir(exist_ok=True)
    path = perf_dir / "v0_5_phase42_cold_start.json"
    if path.exists():
        existing = json.loads(path.read_text())
        if isinstance(existing, list):
            existing.append(record)
            path.write_text(json.dumps(existing, indent=2))
            return
    path.write_text(json.dumps([record], indent=2))
