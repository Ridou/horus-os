"""Phase 33 Task 4 tests: end-to-end RunEnd rollup with the wired persister.

The canonical Pitfall 1 regression test: a 3-iteration agent run with
stubbed usage={input_tokens: 100, output_tokens: 50} per turn must
produce three llm_calls rows and a traces row whose
total_input_tokens == 300 (NOT 100, which was the v0.3 per-iteration
overwrite bug).

Also covers the run_end with tool_invocations and the end-to-end api.py
/api/chat path so the wiring proves itself through the FastAPI handler.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

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

LOOP_ITERATIONS = 3
INPUT_TOKENS = 100
OUTPUT_TOKENS = 50


class _StubConversation:
    """Mirrors scripts/capture_v0_3_baseline.py:_StubConversation cadence.

    First two .send() calls return one tool_use; the third returns
    text-only. Each call surfaces usage={input_tokens: 100,
    output_tokens: 50}. Total: 3 LLMCallEvents + 2 ToolCallEvents.
    """

    def __init__(self, model: str | None = None, system_prompt: str | None = None) -> None:
        self.model = model or "stub-model"
        self.system_prompt = system_prompt
        self._calls = 0

    def send(self, prompt=None, tool_results=None, tools=None) -> AgentResult:
        del prompt, tool_results, tools
        self._calls += 1
        if self._calls < LOOP_ITERATIONS:
            return AgentResult(
                text="",
                tool_uses=[ToolUse(id=f"tu-{self._calls}", name="noop", input={})],
                provider="stub",
                model=self.model,
                usage={"input_tokens": INPUT_TOKENS, "output_tokens": OUTPUT_TOKENS},
            )
        return AgentResult(
            text="ok",
            tool_uses=[],
            provider="stub",
            model=self.model,
            usage={"input_tokens": INPUT_TOKENS, "output_tokens": OUTPUT_TOKENS},
        )


def _stub_new_conversation(provider, model, *, system_prompt=None):
    del provider
    return _StubConversation(model=model, system_prompt=system_prompt)


def _noop_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="noop",
            description="No-op tool for rollup integration tests.",
            parameters={"type": "object", "properties": {}},
            handler=lambda: "ok",
        )
    )
    return registry


def _wire(tmp_path: Path) -> tuple[Database, str]:
    """Set up a real Database with the persister wired to a fresh bus."""
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    reset_observation_bus_for_tests()
    get_observation_bus().subscribe(SQLitePersister(db).on_event)
    trace_id = "deadbeefcafebabe1234567890abcdef"
    return db, trace_id


def test_three_iteration_rollup(tmp_path: Path, monkeypatch) -> None:
    """Pitfall 1 canonical regression test.

    3-iteration stubbed run with 100 input + 50 output per call must
    land traces.total_input_tokens=300 and 3 rows in llm_calls. The v0.3
    bug had per-iteration overwrite landing 100 (last iteration's value).
    """
    db, trace_id = _wire(tmp_path)
    monkeypatch.setattr(agent_module, "_new_conversation", _stub_new_conversation)

    # Seed traces row so the RUN_END rollup UPDATE has a row to match.
    db.record_trace(
        "prompt",
        AgentResult(text="seed", provider="stub", model="stub-model"),
        latency_ms=42,
        trace_id=trace_id,
    )

    run_agent_loop(
        "prompt",
        registry=_noop_registry(),
        provider="anthropic",
        max_iterations=LOOP_ITERATIONS,
        trace_id=trace_id,
    )
    get_observation_bus().publish(RunEndEvent(trace_id=trace_id, latency_ms=42))

    with sqlite3.connect(str(db.path)) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM llm_calls WHERE trace_id = ?", (trace_id,)
        ).fetchone()[0]
        rollup = conn.execute(
            "SELECT total_input_tokens, total_output_tokens, total_cost_usd, "
            "total_duration_ms FROM traces WHERE trace_id = ?",
            (trace_id,),
        ).fetchone()

    assert count == 3, f"expected 3 llm_calls rows, got {count} (Pitfall 1 regression)"
    assert rollup is not None
    assert rollup[0] == 300, f"expected total_input_tokens=300, got {rollup[0]}"
    assert rollup[1] == 150
    # total_cost_usd is NULL until Phase 34's CostAnnotator subscribes;
    # the persister keeps NULL because every llm_calls row has cost_usd
    # NULL (Pitfall 5: NULL is honest, zero is a lie).
    assert rollup[2] is None
    assert rollup[3] == 42


def test_run_end_rollup_with_tool_invocations(tmp_path: Path, monkeypatch) -> None:
    """The 3-iteration stub yields 2 tool_uses; both must persist."""
    db, trace_id = _wire(tmp_path)
    monkeypatch.setattr(agent_module, "_new_conversation", _stub_new_conversation)
    db.record_trace(
        "prompt",
        AgentResult(text="seed", provider="stub", model="stub-model"),
        latency_ms=10,
        trace_id=trace_id,
    )
    run_agent_loop(
        "prompt",
        registry=_noop_registry(),
        provider="anthropic",
        max_iterations=LOOP_ITERATIONS,
        trace_id=trace_id,
    )
    get_observation_bus().publish(RunEndEvent(trace_id=trace_id, latency_ms=10))
    with sqlite3.connect(str(db.path)) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM tool_invocations WHERE trace_id = ?",
            (trace_id,),
        ).fetchone()[0]
    assert count == 2


def test_api_chat_endpoint_e2e_rollup(tmp_path: Path, monkeypatch) -> None:
    """POST /api/chat must drive the full Phase 33 wiring end-to-end."""
    from fastapi.testclient import TestClient

    from horus_os import create_app

    # Seed the data_dir with a fresh DB so create_app's wiring works.
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    reset_observation_bus_for_tests()

    # Provide a fake anthropic API key so the chat handler does not 503.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-used")
    monkeypatch.setattr(agent_module, "_new_conversation", _stub_new_conversation)

    app = create_app(data_dir=tmp_path)
    with TestClient(app) as client:
        response = client.post("/api/chat", json={"prompt": "test"})
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    trace_id = body["trace_id"]
    assert isinstance(trace_id, str)
    assert len(trace_id) == 32

    with sqlite3.connect(str(db.path)) as conn:
        call_count = conn.execute(
            "SELECT COUNT(*) FROM llm_calls WHERE trace_id = ?", (trace_id,)
        ).fetchone()[0]
        rollup = conn.execute(
            "SELECT total_input_tokens, total_output_tokens FROM traces WHERE trace_id = ?",
            (trace_id,),
        ).fetchone()
    assert call_count == 3
    assert rollup is not None
    assert rollup[0] == 300
    assert rollup[1] == 150
