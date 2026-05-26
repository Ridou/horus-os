"""Phase 33 Task 7: Pitfall 3 negative-latency assertions stay live.

Phase 32 shipped `assert event.latency_ms >= 0` inside
SQLitePersister._insert_llm_call and _insert_tool_invocation. The
ObservationBus swallows subscriber exceptions per its contract, so a
negative-latency publish through the bus must result in zero rows
landing rather than a propagated exception.

These tests prove the Phase 32 guards still fire after the Phase 33
wiring; future capture-site changes cannot silently bypass the gate.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from horus_os import AgentResult, Database
from horus_os.observability import (
    SQLitePersister,
    get_observation_bus,
    reset_observation_bus_for_tests,
)
from horus_os.observability.bus import LLMCallEvent, ToolCallEvent


def _wire(tmp_path: Path) -> tuple[Database, str]:
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    reset_observation_bus_for_tests()
    get_observation_bus().subscribe(SQLitePersister(db).on_event)
    trace_id = db.record_trace(
        "seed",
        AgentResult(text="seed", provider="anthropic", model="claude-sonnet-4-6"),
    )
    return db, trace_id


def test_persister_swallows_negative_latency_publish(tmp_path: Path) -> None:
    """Publishing an LLMCallEvent with latency_ms<0 lands zero rows.

    The persister assertion fires inside on_event; the bus swallows it.
    A downstream SELECT proves the row was rejected even though the
    publisher saw no error (matching the bus contract).
    """
    db, trace_id = _wire(tmp_path)
    get_observation_bus().publish(
        LLMCallEvent(
            trace_id=trace_id,
            iteration_idx=0,
            provider="anthropic",
            model="claude-sonnet-4-6",
            latency_ms=-5,
        )
    )
    with sqlite3.connect(str(db.path)) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM llm_calls WHERE trace_id = ?", (trace_id,)
        ).fetchone()[0]
    assert count == 0, f"expected 0 llm_calls rows, got {count} (Pitfall 3 regression)"


def test_persister_swallows_negative_latency_tool_call(tmp_path: Path) -> None:
    """Same guard for ToolCallEvent with latency_ms<0."""
    db, trace_id = _wire(tmp_path)
    get_observation_bus().publish(
        ToolCallEvent(trace_id=trace_id, tool_name="leaky", latency_ms=-1)
    )
    with sqlite3.connect(str(db.path)) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM tool_invocations WHERE trace_id = ?",
            (trace_id,),
        ).fetchone()[0]
    assert count == 0
