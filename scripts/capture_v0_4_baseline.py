"""Capture the v0.4 cold-start + zero-plugin discovery baseline (BASELINE-02).

Mirror of scripts/capture_v0_3_baseline.py one-to-one in structure, with the
two new metrics (cold_import_ms, entry_points_discovery_ms) added and
wall_clock_ms (cold create_app() startup) replacing the v0.3
median_3_iteration_loop_ms as the headline metric. agent_loop_3_iter_ms is
preserved as a v0.3-parity trend column so Phase 42's benchmark report can
compute the v0.3 to v0.4 delta.

Four metrics captured per (os, python) run, N_SAMPLES = 20 samples each,
median rounded to 3 decimal places:

1. wall_clock_ms: subprocess wall-clock from
   `python -c "from horus_os.server.api import create_app; create_app()"`
   start to interpreter exit. Each sample spawns a fresh interpreter so
   the import is cold, mirroring the user's first dashboard startup.
2. agent_loop_3_iter_ms: in-process 3-iteration agent loop against a
   stubbed Conversation, replicated verbatim from
   scripts/capture_v0_3_baseline.py for trend continuity with METRIC-05.
3. cold_import_ms: subprocess wall-clock from
   `python -c "import horus_os.adapters"` start to exit. Measures the
   cold-import cost of the adapters package; Phase 42's plugins package
   extends this same import chain.
4. entry_points_discovery_ms: in-process wall-clock for one call to
   `discover_adapters()`. Between samples, sys.modules entries matching
   horus_os.adapters* are popped so each sample re-imports fresh and the
   number reflects the importlib.metadata + sort + load overhead floor.

All four helpers measure exclusively with the nanosecond perf counter;
the script never calls calendar-time or seconds-resolution timers.
Pitfall 3 (PITFALLS.md) discipline is enforced by
scripts/lint_no_wallclock.py over the watched src/horus_os paths;
scripts/ is outside the watched set but the project's social convention
extends so future readers find a self-consistent example.

Idempotent on re-run: the second invocation on the same (os, python) combo
replaces the existing entry in place. Other (os, python) entries are
preserved verbatim so capturing on multiple hosts produces a clean merge.

BASELINE-02 substrate. The artifact at tests/perf/v0_4_baseline.json is
read by Phase 42's TEST-18 cold-start <100ms benchmark, which is why this
script MUST land and the JSON MUST commit before Phase 42 work begins.

Usage:
    python scripts/capture_v0_4_baseline.py
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from horus_os import agent as agent_module
from horus_os.tools.registry import ToolRegistry
from horus_os.types import AgentResult, Tool, ToolUse

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = REPO_ROOT / "tests" / "perf" / "v0_4_baseline.json"
N_SAMPLES = 20
LOOP_ITERATIONS = 3


class _StubConversation:
    """Stub Conversation: returns tool_uses for the first two iterations.

    Replicated verbatim from scripts/capture_v0_3_baseline.py so the v0.4
    agent_loop_3_iter_ms metric measures the same cadence as v0.3's
    median_3_iteration_loop_ms. The first two .send() calls each emit one
    tool_use; the third returns no tool_uses and terminates the loop.
    """

    def __init__(self, model: str | None = None, system_prompt: str | None = None) -> None:
        self.model = model
        self.system_prompt = system_prompt
        self._calls = 0

    def send(self, prompt: str | None = None, tool_results=None, tools=None) -> AgentResult:
        del prompt, tool_results, tools
        self._calls += 1
        if self._calls < LOOP_ITERATIONS:
            return AgentResult(
                text="",
                tool_uses=[ToolUse(id=f"tu-{self._calls}", name="noop", input={})],
                provider="stub",
                model="stub",
                usage={"input_tokens": 100, "output_tokens": 50},
            )
        return AgentResult(
            text="ok",
            tool_uses=[],
            provider="stub",
            model="stub",
            usage={"input_tokens": 100, "output_tokens": 50},
        )


def _stub_new_conversation(provider: str, model, *, system_prompt=None):
    del provider
    return _StubConversation(model=model, system_prompt=system_prompt)


def _noop_handler() -> str:
    """No-op tool handler: returns the same constant on every call."""
    return "noop-result"


def _build_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="noop",
            description="No-op tool used by the v0.4 baseline harness.",
            parameters={"type": "object", "properties": {}},
            handler=_noop_handler,
        )
    )
    return registry


def _read_version() -> str:
    """Read the installed horus_os version string."""
    try:
        from horus_os import __version__

        return str(__version__)
    except Exception:
        return "unknown"


def _platform_key() -> str:
    """Normalize sys.platform into the keys used in v0_4_baseline.json."""
    plat = sys.platform
    if plat.startswith("linux"):
        return "linux"
    if plat == "darwin":
        return "darwin"
    if plat.startswith("win"):
        return "win32"
    return plat


def _python_key() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def _capture_wall_clock_ms() -> float:
    """Median subprocess wall-clock for `create_app()` cold-start in ms.

    Spawns N_SAMPLES fresh interpreters via subprocess.run with list-form
    args (no shell=True, no argv injection). Each subprocess imports
    horus_os.server.api from scratch and calls create_app(), then exits.
    The parent process measures the wall clock via perf_counter_ns
    before and after subprocess.run; the difference is the cold-start
    cost from import to interpreter teardown.
    """
    samples_ns: list[int] = []
    for _ in range(N_SAMPLES):
        t0 = time.perf_counter_ns()
        subprocess.run(
            [sys.executable, "-c", "from horus_os.server.api import create_app; create_app()"],
            check=True,
            capture_output=True,
            timeout=30,
        )
        samples_ns.append(time.perf_counter_ns() - t0)
    median_ns = statistics.median(samples_ns)
    return round(median_ns / 1_000_000, 3)


def _capture_agent_loop_3_iter_ms() -> float:
    """Median in-process 3-iteration agent loop in ms (v0.3 parity).

    Monkey-patches agent_module._new_conversation to the stub so no
    network call ever happens, then runs run_agent_loop N_SAMPLES times
    under perf_counter_ns. Restores the original on exit. Identical
    cadence to scripts/capture_v0_3_baseline.py's _capture_samples.
    """
    registry = _build_registry()
    original = agent_module._new_conversation
    agent_module._new_conversation = _stub_new_conversation
    try:
        samples_ns: list[int] = []
        for _ in range(N_SAMPLES):
            t0 = time.perf_counter_ns()
            agent_module.run_agent_loop(
                "baseline prompt",
                registry=registry,
                provider="anthropic",
                max_iterations=LOOP_ITERATIONS,
            )
            samples_ns.append(time.perf_counter_ns() - t0)
    finally:
        agent_module._new_conversation = original
    median_ns = statistics.median(samples_ns)
    return round(median_ns / 1_000_000, 3)


def _capture_cold_import_ms() -> float:
    """Median subprocess wall-clock for `import horus_os.adapters` in ms.

    Phase 42's discovery system extends the adapters package, so the
    cold-import cost of that package is the import-time floor every
    discovered-plugin walk pays before discover_plugins() runs. Fresh
    interpreter per sample so the module cache cannot pollute the
    measurement.
    """
    samples_ns: list[int] = []
    for _ in range(N_SAMPLES):
        t0 = time.perf_counter_ns()
        subprocess.run(
            [sys.executable, "-c", "import horus_os.adapters"],
            check=True,
            capture_output=True,
            timeout=15,
        )
        samples_ns.append(time.perf_counter_ns() - t0)
    median_ns = statistics.median(samples_ns)
    return round(median_ns / 1_000_000, 3)


def _capture_entry_points_discovery_ms() -> float:
    """Median in-process discover_adapters() wall-clock in ms.

    Between samples, sys.modules entries matching horus_os.adapters and
    horus_os.adapters.base are popped so each sample re-imports fresh.
    The measured number captures the importlib.metadata entry-points
    walk + sort + per-entry load overhead. With the 6 built-in adapter
    entry points declared in pyproject.toml (webhook, discord, slack,
    email, calendar, otel) this is the v0.4 floor; Phase 42's
    discover_plugins() reads this number as the comparison baseline for
    the <100ms cold-start contract.
    """
    samples_ns: list[int] = []
    for _ in range(N_SAMPLES):
        # Clear cached modules so the next import + discover_adapters call
        # pays the cold-walk cost rather than returning from sys.modules.
        for key in list(sys.modules):
            if key == "horus_os.adapters" or key.startswith("horus_os.adapters."):
                del sys.modules[key]
        import horus_os.adapters as _adapters

        t0 = time.perf_counter_ns()
        _adapters.discover_adapters()
        samples_ns.append(time.perf_counter_ns() - t0)
    median_ns = statistics.median(samples_ns)
    return round(median_ns / 1_000_000, 3)


def _load_baseline() -> dict:
    if BASELINE_PATH.exists():
        with BASELINE_PATH.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if "samples" not in data or not isinstance(data["samples"], list):
            data = {"samples": []}
        return data
    return {"samples": []}


def _write_baseline(data: dict) -> None:
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with BASELINE_PATH.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")


def main() -> int:
    os_key = _platform_key()
    py_key = _python_key()

    wall_clock_ms = _capture_wall_clock_ms()
    agent_loop_3_iter_ms = _capture_agent_loop_3_iter_ms()
    cold_import_ms = _capture_cold_import_ms()
    entry_points_discovery_ms = _capture_entry_points_discovery_ms()

    entry = {
        "os": os_key,
        "python": py_key,
        "horus_os_version": _read_version(),
        "wall_clock_ms": wall_clock_ms,
        "agent_loop_3_iter_ms": agent_loop_3_iter_ms,
        "cold_import_ms": cold_import_ms,
        "entry_points_discovery_ms": entry_points_discovery_ms,
        "n_samples": N_SAMPLES,
        "captured_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }

    data = _load_baseline()
    # Remove any prior entry for this (os, python) combo to keep the list
    # de-duplicated, then append the new entry and sort for deterministic
    # diffs across re-runs on other machines.
    data["samples"] = [
        s for s in data["samples"] if not (s.get("os") == os_key and s.get("python") == py_key)
    ]
    data["samples"].append(entry)
    data["samples"].sort(key=lambda s: (s.get("os", ""), s.get("python", "")))
    _write_baseline(data)

    print(
        f"baseline ({os_key}, py{py_key}): "
        f"wall_clock_ms={wall_clock_ms} "
        f"agent_loop_3_iter_ms={agent_loop_3_iter_ms} "
        f"cold_import_ms={cold_import_ms} "
        f"entry_points_discovery_ms={entry_points_discovery_ms} "
        f"(n={N_SAMPLES} per metric)"
    )
    print(f"wrote {BASELINE_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
