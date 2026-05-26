"""Phase 33 Task 8: capture-overhead benchmark (METRIC-05 / TEST-12).

Runs a 5-iteration / 3-tool-call agent loop against the FULL Phase 33
wiring (real ObservationBus, real SQLitePersister writing to a tmp
SQLite DB, real LLMCallEvent + ToolCallEvent + RunEndEvent publishes),
measures the median wall-clock duration across N=20 samples, and
asserts it stays within 50ms of the matching `(os, python)` baseline
entry in `tests/perf/v0_3_baseline.json`.

When no matching baseline entry exists, the test SKIPS (not fails) so
unseeded CI combos do not block the build. See planning context guide.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import pytest

from horus_os import Database
from horus_os import agent as agent_module
from horus_os.agent import run_agent_loop
from horus_os.observability import (
    SQLitePersister,
    get_observation_bus,
    reset_observation_bus_for_tests,
)
from horus_os.observability.bus import RunEndEvent
from horus_os.tools.registry import ToolRegistry
from horus_os.types import AgentResult, Tool, ToolUse

BASELINE_PATH = Path(__file__).parent / "v0_3_baseline.json"
N_SAMPLES = 20
LOOP_ITERATIONS = 5
TOOL_CALLS_PER_RUN = 3
OVERHEAD_TOLERANCE_MS = 50


def _platform_key() -> str:
    """Mirror scripts/capture_v0_3_baseline.py:_platform_key normalization."""
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


def _load_matching_baseline_ms() -> float | None:
    """Return the matching median_3_iteration_loop_ms or None when absent."""
    if not BASELINE_PATH.exists():
        return None
    with BASELINE_PATH.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    samples = data.get("samples") or []
    for entry in samples:
        if entry.get("os") == _platform_key() and entry.get("python") == _python_key():
            value = entry.get("median_3_iteration_loop_ms")
            return float(value) if value is not None else None
    return None


class _StubConversation:
    """5-iteration cadence: iterations 0,1,2 emit one tool_use each; 3,4 text-only.

    Total: 5 Conversation.send() calls + 3 execute_tool_uses passes,
    matching the ROADMAP success-criterion 5 wording.
    """

    def __init__(self, model: str | None = None, system_prompt: str | None = None) -> None:
        self.model = model or "stub-model"
        self.system_prompt = system_prompt
        self._calls = 0

    def send(self, prompt=None, tool_results=None, tools=None) -> AgentResult:
        del prompt, tool_results, tools
        idx = self._calls
        self._calls += 1
        if idx < TOOL_CALLS_PER_RUN:
            return AgentResult(
                text="",
                tool_uses=[ToolUse(id=f"tu-{idx}", name="noop", input={})],
                provider="stub",
                model=self.model,
                usage={"input_tokens": 100, "output_tokens": 50},
            )
        return AgentResult(
            text="ok",
            tool_uses=[],
            provider="stub",
            model=self.model,
            usage={"input_tokens": 100, "output_tokens": 50},
        )


def _stub_new_conversation(provider, model, *, system_prompt=None):
    del provider
    return _StubConversation(model=model, system_prompt=system_prompt)


def _noop_handler() -> str:
    return "noop-result"


def _build_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="noop",
            description="No-op tool for the capture-overhead benchmark.",
            parameters={"type": "object", "properties": {}},
            handler=_noop_handler,
        )
    )
    return registry


def test_baseline_json_shape_is_valid() -> None:
    """Guard against drift between the capture script and this reader."""
    assert BASELINE_PATH.exists(), f"baseline JSON missing at {BASELINE_PATH}"
    with BASELINE_PATH.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    assert isinstance(data, dict)
    assert "samples" in data
    assert isinstance(data["samples"], list)
    required = {
        "os",
        "python",
        "horus_os_version",
        "median_3_iteration_loop_ms",
        "n_samples",
        "captured_at",
    }
    for entry in data["samples"]:
        missing = required - set(entry)
        assert not missing, f"baseline entry missing required keys: {missing}"


def test_capture_overhead_within_50ms(tmp_path: Path, monkeypatch) -> None:
    """Median wall-clock of the wired loop must stay within 50ms of baseline."""
    baseline_ms = _load_matching_baseline_ms()
    if baseline_ms is None:
        pytest.skip(
            f"No v0_3 baseline entry for ({_platform_key()}, py{_python_key()}). "
            "Run scripts/capture_v0_3_baseline.py on this host first."
        )

    reset_observation_bus_for_tests()
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    get_observation_bus().subscribe(SQLitePersister(db).on_event)
    monkeypatch.setattr(agent_module, "_new_conversation", _stub_new_conversation)
    registry = _build_registry()
    bus = get_observation_bus()

    samples: list[float] = []
    for _ in range(N_SAMPLES):
        trace_id = uuid.uuid4().hex
        # Pre-seed traces row so the RUN_END rollup UPDATE matches.
        db.record_trace(
            "benchmark",
            AgentResult(text="", provider="anthropic", model="stub-model"),
            latency_ms=0,
            trace_id=trace_id,
        )
        t0 = time.perf_counter()
        run_agent_loop(
            "prompt",
            registry=registry,
            provider="anthropic",
            max_iterations=LOOP_ITERATIONS,
            trace_id=trace_id,
        )
        bus.publish(RunEndEvent(trace_id=trace_id, latency_ms=0))
        samples.append(time.perf_counter() - t0)

    actual_median_ms = round(statistics.median(samples) * 1000, 3)
    delta = round(actual_median_ms - baseline_ms, 3)
    # Print so CI logs surface both numbers and the delta for trend
    # tracking even when the assertion passes.
    print(f"capture_overhead: baseline={baseline_ms}ms actual={actual_median_ms}ms delta={delta}ms")
    msg: Any = (
        f"Capture overhead {actual_median_ms}ms exceeds baseline {baseline_ms}ms "
        f"+ {OVERHEAD_TOLERANCE_MS}ms tolerance (delta {delta}ms)"
    )
    assert actual_median_ms <= baseline_ms + OVERHEAD_TOLERANCE_MS, msg
