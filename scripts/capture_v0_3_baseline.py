"""Capture the v0.3 capture-overhead baseline for the v0.4 observability benchmark.

Runs a 3-iteration agent loop against a stubbed provider (no network, no real
LLM call), measures total wall-clock via time.perf_counter() across N=20
iterations, takes the median, and merges the result keyed on (os, python)
into tests/perf/v0_3_baseline.json. Idempotent: re-running on the same
(os, python) combo overwrites that entry only; entries for other OS/python
combos are preserved.

Run on each target combo (Ubuntu 3.11, Ubuntu 3.12, macOS 3.11, macOS 3.12,
Windows 3.11, Windows 3.12) and commit the resulting JSON. Phase 33 reads
the entry matching the current CI runner to enforce METRIC-05 (capture
overhead stays within 50ms of the pinned v0.3 number).

Decision rationale (per planner): capture-once-per-environment is cleaner
than per-OS CI capture. The v0.3 baseline is fixed (v0.3 is shipped) so
rerunning the script in CI on every push would re-measure the same artifact
and add no value. Phase 33's CI benchmark reads the matching entry from
this JSON; it does not re-run this script.

Usage:
    python scripts/capture_v0_3_baseline.py
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from horus_os import agent as agent_module
from horus_os.tools.registry import ToolRegistry
from horus_os.types import AgentResult, Tool, ToolUse

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = REPO_ROOT / "tests" / "perf" / "v0_3_baseline.json"
N_SAMPLES = 20
LOOP_ITERATIONS = 3


class _StubConversation:
    """Stub Conversation: returns tool_uses for the first two iterations.

    The stub mimics the surface horus_os.agent.run_agent_loop calls without
    performing any network I/O, file I/O, or sleep. The first two .send()
    calls return one tool_use each so the loop drives through three full
    iterations of registry dispatch and bookkeeping. The third .send()
    returns no tool_uses, which terminates the loop. Total: three
    Conversation.send() calls plus two execute_tool_uses passes, the
    closest pure-Python analog to v0.3's runner.send-think-tool cadence.
    """

    def __init__(self, model: str | None = None, system_prompt: str | None = None) -> None:
        self.model = model
        self.system_prompt = system_prompt
        self._calls = 0

    def send(self, prompt: str | None = None, tool_results=None, tools=None) -> AgentResult:
        # prompt / tool_results / tools intentionally unused by the stub
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
    del provider  # stub ignores provider selection; always returns _StubConversation
    return _StubConversation(model=model, system_prompt=system_prompt)


def _noop_handler() -> str:
    """No-op tool handler: returns the same constant on every call."""
    return "noop-result"


def _build_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="noop",
            description="No-op tool used by the v0.3 baseline harness.",
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
    """Normalize sys.platform into the keys used in v0_3_baseline.json."""
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


def _run_one_iteration(registry: ToolRegistry) -> None:
    """Run a single 3-iteration agent loop end to end against the stub provider."""
    agent_module.run_agent_loop(
        "baseline prompt",
        registry=registry,
        provider="anthropic",
        max_iterations=LOOP_ITERATIONS,
    )


def _capture_samples() -> float:
    """Return the median wall-clock duration in milliseconds across N_SAMPLES runs.

    Rounded to 3 decimal places (microsecond precision) so a near-zero
    median against a fully in-process stub still surfaces a non-zero
    number for Phase 33's 50 ms tolerance check.
    """
    registry = _build_registry()
    # Monkey-patch the provider boundary so no network call ever happens.
    original = agent_module._new_conversation
    agent_module._new_conversation = _stub_new_conversation
    try:
        samples: list[float] = []
        for _ in range(N_SAMPLES):
            t0 = time.perf_counter()
            _run_one_iteration(registry)
            samples.append(time.perf_counter() - t0)
    finally:
        agent_module._new_conversation = original
    median_seconds = statistics.median(samples)
    return round(median_seconds * 1000, 3)


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
    median_ms = _capture_samples()
    entry = {
        "os": os_key,
        "python": py_key,
        "horus_os_version": _read_version(),
        "median_3_iteration_loop_ms": median_ms,
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

    print(f"baseline ({os_key}, py{py_key}): {median_ms} ms median over {N_SAMPLES} samples")
    print(f"wrote {BASELINE_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
