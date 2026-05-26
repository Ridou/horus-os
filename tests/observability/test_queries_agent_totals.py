"""Tests for agent_totals in observability.queries.

agent_totals aggregates per-agent rollup over a window. All percentiles
come from llm_calls.latency_ms via NTILE(100) at the SQL boundary, never
from a Python statistics call. Pre-v0.4 traces (total_cost_usd IS NULL)
contribute to total_runs and to uncosted_runs but do NOT inflate the
cost sum (Pitfall 11 contract: NULL never silently becomes zero).
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from horus_os.storage import Database


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _iso_offset(seconds: int) -> str:
    return (datetime.now(UTC) + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


def _init(tmp_path: Path) -> Database:
    db = Database(tmp_path / "horus.db")
    db.init()
    return db


def _seed_profile(db: Database, name: str) -> None:
    now = _now_iso()
    with sqlite3.connect(str(db.path)) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO agent_profiles "
            "(name, system_prompt, default_model, allowed_tools, memory_scope, created_at, "
            "updated_at) VALUES (?, ?, NULL, NULL, NULL, ?, ?)",
            (name, "p", now, now),
        )


def _insert_trace(
    db: Database,
    *,
    agent: str,
    created_at: str,
    total_cost_usd: float | None,
    total_input_tokens: int | None = 100,
    total_output_tokens: int | None = 50,
) -> str:
    trace_id = uuid.uuid4().hex
    with sqlite3.connect(str(db.path)) as conn:
        conn.execute(
            "INSERT INTO traces "
            "(trace_id, created_at, provider, model, prompt, response_text, "
            "agent_profile_name, total_input_tokens, total_output_tokens, total_cost_usd) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                trace_id,
                created_at,
                "anthropic",
                "claude-sonnet-4-6",
                "p",
                "r",
                agent,
                total_input_tokens,
                total_output_tokens,
                total_cost_usd,
            ),
        )
    return trace_id


def _insert_llm_call(
    db: Database, *, trace_id: str, created_at: str, latency_ms: int, cost_usd: float | None = None
) -> None:
    with sqlite3.connect(str(db.path)) as conn:
        conn.execute(
            "INSERT INTO llm_calls "
            "(call_id, trace_id, iteration_idx, created_at, provider, model, "
            "input_tokens, output_tokens, cost_usd, latency_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                uuid.uuid4().hex,
                trace_id,
                0,
                created_at,
                "anthropic",
                "claude-sonnet-4-6",
                100,
                50,
                cost_usd,
                latency_ms,
            ),
        )


def test_agent_totals_empty_database_returns_empty_list(tmp_path: Path) -> None:
    from horus_os.observability.queries import agent_totals

    db = _init(tmp_path)
    assert agent_totals(db, "7d") == []


def test_agent_totals_single_agent_counts_runs(tmp_path: Path) -> None:
    from horus_os.observability.queries import agent_totals

    db = _init(tmp_path)
    _seed_profile(db, "alpha")
    for _ in range(3):
        _insert_trace(db, agent="alpha", created_at=_now_iso(), total_cost_usd=0.001)
    rows = agent_totals(db, "7d")
    assert len(rows) == 1
    assert rows[0]["agent"] == "alpha"
    assert rows[0]["total_runs"] == 3


def test_agent_totals_no_llm_calls_renders_null_percentiles(tmp_path: Path) -> None:
    """Pitfall 10: empty window for percentile fields returns None, never 0."""
    from horus_os.observability.queries import agent_totals

    db = _init(tmp_path)
    _seed_profile(db, "alpha")
    # Trace exists, but no llm_calls rows are linked.
    _insert_trace(db, agent="alpha", created_at=_now_iso(), total_cost_usd=0.001)
    rows = agent_totals(db, "7d")
    assert len(rows) == 1
    row = rows[0]
    assert row["latency_p50_ms"] is None
    assert row["latency_p95_ms"] is None
    assert row["sample_count"] == 0


def test_agent_totals_cost_sum_excludes_null_rows_and_surfaces_uncosted_counter(
    tmp_path: Path,
) -> None:
    """Pitfall 11: pre-v0.4 NULL cost rows contribute to uncosted_runs, not the sum."""
    from horus_os.observability.queries import agent_totals

    db = _init(tmp_path)
    _seed_profile(db, "alpha")
    _insert_trace(db, agent="alpha", created_at=_now_iso(), total_cost_usd=0.002)
    _insert_trace(db, agent="alpha", created_at=_now_iso(), total_cost_usd=0.003)
    _insert_trace(
        db,
        agent="alpha",
        created_at=_now_iso(),
        total_cost_usd=None,
        total_input_tokens=None,
        total_output_tokens=None,
    )
    rows = agent_totals(db, "7d")
    assert len(rows) == 1
    row = rows[0]
    assert row["total_runs"] == 3
    assert row["uncosted_runs"] == 1
    # 0.002 + 0.003 = 0.005; NULL row excluded.
    assert row["total_cost_usd"] == 0.005


def test_agent_totals_returns_token_totals_as_float_or_int(tmp_path: Path) -> None:
    from horus_os.observability.queries import agent_totals

    db = _init(tmp_path)
    _seed_profile(db, "alpha")
    _insert_trace(
        db,
        agent="alpha",
        created_at=_now_iso(),
        total_cost_usd=0.001,
        total_input_tokens=200,
        total_output_tokens=100,
    )
    rows = agent_totals(db, "7d")
    assert rows[0]["total_input_tokens"] == 200
    assert rows[0]["total_output_tokens"] == 100


def test_agent_totals_percentiles_use_llm_calls_latency_ms(tmp_path: Path) -> None:
    """Percentiles come from llm_calls.latency_ms (NOT traces.latency_ms)."""
    from horus_os.observability.queries import agent_totals

    db = _init(tmp_path)
    _seed_profile(db, "alpha")
    trace_id = _insert_trace(db, agent="alpha", created_at=_now_iso(), total_cost_usd=0.001)
    # Ten calls all at 100ms; p50 = p95 = 100, sample_count = 10.
    for _ in range(10):
        _insert_llm_call(
            db, trace_id=trace_id, created_at=_now_iso(), latency_ms=100, cost_usd=0.0001
        )
    rows = agent_totals(db, "7d")
    assert rows[0]["latency_p50_ms"] == 100
    assert rows[0]["latency_p95_ms"] == 100
    assert rows[0]["sample_count"] == 10


def test_agent_totals_excludes_rows_outside_window(tmp_path: Path) -> None:
    from horus_os.observability.queries import agent_totals

    db = _init(tmp_path)
    _seed_profile(db, "alpha")
    # Insert two traces: one inside window (now), one 60 days back (outside 7d).
    _insert_trace(db, agent="alpha", created_at=_now_iso(), total_cost_usd=0.001)
    far_past = (datetime.now(UTC) - timedelta(days=60)).isoformat().replace("+00:00", "Z")
    _insert_trace(db, agent="alpha", created_at=far_past, total_cost_usd=0.999)
    rows = agent_totals(db, "7d")
    assert rows[0]["total_runs"] == 1
    assert rows[0]["total_cost_usd"] == 0.001


def test_agent_totals_returns_one_row_per_agent(tmp_path: Path) -> None:
    from horus_os.observability.queries import agent_totals

    db = _init(tmp_path)
    _seed_profile(db, "alpha")
    _seed_profile(db, "beta")
    _insert_trace(db, agent="alpha", created_at=_now_iso(), total_cost_usd=0.001)
    _insert_trace(db, agent="beta", created_at=_now_iso(), total_cost_usd=0.002)
    rows = agent_totals(db, "7d")
    agents = {row["agent"] for row in rows}
    assert agents == {"alpha", "beta"}


def test_agent_totals_re_exported_from_observability_package() -> None:
    from horus_os.observability import agent_totals as via_pkg
    from horus_os.observability.queries import agent_totals as direct

    assert via_pkg is direct
