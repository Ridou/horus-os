"""Unit tests for SQLitePersister: event routing, rollup, latency guard.

The persister sees three event kinds and must:

1. INSERT one row into llm_calls per LLMCallEvent (all 16 columns
   beyond the auto-increment id).
2. INSERT one row into tool_invocations per ToolCallEvent (all 11
   columns beyond the auto-increment id).
3. On RUN_END, UPDATE the matching traces row with SUM rollups from
   llm_calls plus the event's own latency_ms.
4. Refuse to insert any row whose latency_ms is negative; the assertion
   is the Pitfall 3 guard.
5. Preserve NULL in total_cost_usd when any contributing llm_calls row
   has cost_usd NULL (Pitfall 5; NULL is honest, zero is a lie).

These tests publish events directly through the ObservationBus to prove
the bus contract and the persister contract compose. No runner code is
touched.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from horus_os import AgentResult, Database
from horus_os.observability.bus import (
    LLMCallEvent,
    ObservationBus,
    RunEndEvent,
    ToolCallEvent,
)
from horus_os.observability.persist import SQLitePersister


def _make_db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    return db


def _seed_trace(db: Database) -> str:
    """Insert one traces row so RUN_END rollups have a target. Returns trace_id."""
    result = AgentResult(text="ok", provider="anthropic", model="claude-sonnet-4-6")
    return db.record_trace("test prompt", result)


def test_llm_call_event_inserts_row(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    trace_id = _seed_trace(db)
    bus = ObservationBus()
    persister = SQLitePersister(db)
    bus.subscribe(persister.on_event)

    event = LLMCallEvent(
        trace_id=trace_id,
        iteration_idx=2,
        provider="anthropic",
        model="claude-sonnet-4-6",
        input_tokens=123,
        output_tokens=45,
        cache_creation_input_tokens=7,
        cache_read_input_tokens=8,
        cost_usd=0.0012,
        pricing_missing=False,
        latency_ms=400,
    )
    bus.publish(event)

    with sqlite3.connect(str(db.path)) as conn:
        rows = conn.execute(
            "SELECT call_id, trace_id, iteration_idx, provider, model, "
            "input_tokens, output_tokens, cache_creation_input_tokens, "
            "cache_read_input_tokens, cost_usd, pricing_missing, latency_ms, "
            "status, error_message, error_type FROM llm_calls"
        ).fetchall()
    assert len(rows) == 1
    row = rows[0]
    assert row[0] == event.call_id
    assert row[1] == trace_id
    assert row[2] == 2
    assert row[3] == "anthropic"
    assert row[4] == "claude-sonnet-4-6"
    assert row[5] == 123
    assert row[6] == 45
    assert row[7] == 7
    assert row[8] == 8
    assert row[9] == pytest.approx(0.0012)
    assert row[10] == 0  # pricing_missing False -> 0
    assert row[11] == 400
    assert row[12] == "success"
    assert row[13] is None
    assert row[14] is None


def test_tool_call_event_inserts_row(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    trace_id = _seed_trace(db)
    bus = ObservationBus()
    persister = SQLitePersister(db)
    bus.subscribe(persister.on_event)

    event = ToolCallEvent(
        trace_id=trace_id,
        tool_name="read_file",
        latency_ms=12,
        parent_trace_id="parent-xyz",
        retry_count=2,
        output_size=4096,
    )
    bus.publish(event)

    with sqlite3.connect(str(db.path)) as conn:
        rows = conn.execute(
            "SELECT invocation_id, trace_id, parent_trace_id, tool_name, "
            "latency_ms, status, error_message, error_type, retry_count, "
            "output_size FROM tool_invocations"
        ).fetchall()
    assert len(rows) == 1
    row = rows[0]
    assert row[0] == event.invocation_id
    assert row[1] == trace_id
    assert row[2] == "parent-xyz"
    assert row[3] == "read_file"
    assert row[4] == 12
    assert row[5] == "success"
    assert row[6] is None
    assert row[7] is None
    assert row[8] == 2
    assert row[9] == 4096


def test_run_end_rolls_up_traces_columns(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    trace_id = _seed_trace(db)
    bus = ObservationBus()
    persister = SQLitePersister(db)
    bus.subscribe(persister.on_event)

    # Publish two LLM calls. One has cost_usd, one does not (pricing missing).
    bus.publish(
        LLMCallEvent(
            trace_id=trace_id,
            iteration_idx=0,
            provider="anthropic",
            model="claude-sonnet-4-6",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.01,
            latency_ms=10,
        )
    )
    bus.publish(
        LLMCallEvent(
            trace_id=trace_id,
            iteration_idx=1,
            provider="anthropic",
            model="some-unknown-model",
            input_tokens=200,
            output_tokens=75,
            cost_usd=None,
            pricing_missing=True,
            latency_ms=20,
        )
    )
    bus.publish(RunEndEvent(trace_id=trace_id, latency_ms=500))

    with sqlite3.connect(str(db.path)) as conn:
        row = conn.execute(
            "SELECT total_input_tokens, total_output_tokens, total_cost_usd, "
            "total_duration_ms FROM traces WHERE trace_id = ?",
            (trace_id,),
        ).fetchone()
    assert row is not None
    assert row[0] == 300  # 100 + 200
    assert row[1] == 125  # 50 + 75
    # NULL preservation: one contributing row has cost_usd NULL so SUM is NULL.
    # Zero would lie about pricing-missing rows (Pitfall 5).
    assert row[2] is None
    assert row[3] == 500


def test_negative_latency_rejects(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    trace_id = _seed_trace(db)
    persister = SQLitePersister(db)

    # Direct call (not via bus.publish), because the bus swallows exceptions
    # per the contract in tools/loop.py:_call_logger. Pitfall 3.
    event = LLMCallEvent(
        trace_id=trace_id,
        iteration_idx=0,
        provider="anthropic",
        model="claude-sonnet-4-6",
        latency_ms=-1,
    )
    with pytest.raises(AssertionError, match="negative latency_ms"):
        persister.on_event(event)

    tool_event = ToolCallEvent(trace_id=trace_id, tool_name="read_file", latency_ms=-5)
    with pytest.raises(AssertionError, match="negative latency_ms"):
        persister.on_event(tool_event)
