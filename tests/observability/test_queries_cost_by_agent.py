"""Tests for cost_by_agent in observability.queries.

cost_by_agent returns per-agent cost breakdown joined with llm_calls so
cache token sums (cache_read_input_tokens, cache_creation_input_tokens)
flow through even though the traces rollup only carries the non-cache
totals. Sums use SQL's NULL-skipping SUM with COALESCE(..., 0) at the
Python boundary, plus a separate uncosted_runs counter for NULL rows
(Pitfall 11 honesty contract).
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from horus_os.storage import Database


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


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
    db: Database,
    *,
    trace_id: str,
    created_at: str,
    latency_ms: int = 100,
    cost_usd: float | None = 0.0001,
    input_tokens: int = 100,
    output_tokens: int = 50,
    cache_read_input_tokens: int = 0,
    cache_creation_input_tokens: int = 0,
) -> None:
    with sqlite3.connect(str(db.path)) as conn:
        conn.execute(
            "INSERT INTO llm_calls "
            "(call_id, trace_id, iteration_idx, created_at, provider, model, "
            "input_tokens, output_tokens, cache_creation_input_tokens, "
            "cache_read_input_tokens, cost_usd, latency_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                uuid.uuid4().hex,
                trace_id,
                0,
                created_at,
                "anthropic",
                "claude-sonnet-4-6",
                input_tokens,
                output_tokens,
                cache_creation_input_tokens,
                cache_read_input_tokens,
                cost_usd,
                latency_ms,
            ),
        )


def test_cost_by_agent_empty_database_returns_empty_list(tmp_path: Path) -> None:
    from horus_os.observability.queries import cost_by_agent

    db = _init(tmp_path)
    assert cost_by_agent(db, "7d") == []


def test_cost_by_agent_sum_excludes_null_and_surfaces_uncosted_runs(tmp_path: Path) -> None:
    """Pitfall 11: 2 priced + 1 NULL -> sum=0.002, run_count=3, uncosted_runs=1."""
    from horus_os.observability.queries import cost_by_agent

    db = _init(tmp_path)
    _seed_profile(db, "alpha")
    _insert_trace(db, agent="alpha", created_at=_now_iso(), total_cost_usd=0.001)
    _insert_trace(db, agent="alpha", created_at=_now_iso(), total_cost_usd=0.001)
    _insert_trace(
        db,
        agent="alpha",
        created_at=_now_iso(),
        total_cost_usd=None,
        total_input_tokens=None,
        total_output_tokens=None,
    )
    rows = cost_by_agent(db, "7d")
    assert len(rows) == 1
    row = rows[0]
    assert row["agent"] == "alpha"
    assert row["total_cost_usd"] == 0.002
    assert row["run_count"] == 3
    assert row["uncosted_runs"] == 1


def test_cost_by_agent_ordered_by_total_cost_desc(tmp_path: Path) -> None:
    from horus_os.observability.queries import cost_by_agent

    db = _init(tmp_path)
    _seed_profile(db, "alpha")
    _seed_profile(db, "beta")
    _insert_trace(db, agent="alpha", created_at=_now_iso(), total_cost_usd=0.001)
    _insert_trace(db, agent="beta", created_at=_now_iso(), total_cost_usd=0.009)
    rows = cost_by_agent(db, "7d")
    assert [row["agent"] for row in rows] == ["beta", "alpha"]


def test_cost_by_agent_excludes_agents_with_only_out_of_window_runs(tmp_path: Path) -> None:
    from horus_os.observability.queries import cost_by_agent

    db = _init(tmp_path)
    _seed_profile(db, "alpha")
    far_past = (datetime.now(UTC) - timedelta(days=60)).isoformat().replace("+00:00", "Z")
    _insert_trace(db, agent="alpha", created_at=far_past, total_cost_usd=0.999)
    assert cost_by_agent(db, "7d") == []


def test_cost_by_agent_cache_tokens_from_llm_calls(tmp_path: Path) -> None:
    """Cache tokens live on llm_calls only; the traces rollup does not carry them."""
    from horus_os.observability.queries import cost_by_agent

    db = _init(tmp_path)
    _seed_profile(db, "alpha")
    trace_id = _insert_trace(db, agent="alpha", created_at=_now_iso(), total_cost_usd=0.001)
    _insert_llm_call(
        db,
        trace_id=trace_id,
        created_at=_now_iso(),
        cache_read_input_tokens=500,
        cache_creation_input_tokens=20,
    )
    rows = cost_by_agent(db, "7d")
    assert rows[0]["total_cache_read_input_tokens"] == 500
    assert rows[0]["total_cache_creation_input_tokens"] == 20


def test_cost_by_agent_ties_broken_by_name_ascending(tmp_path: Path) -> None:
    from horus_os.observability.queries import cost_by_agent

    db = _init(tmp_path)
    _seed_profile(db, "zeta")
    _seed_profile(db, "alpha")
    _insert_trace(db, agent="zeta", created_at=_now_iso(), total_cost_usd=0.001)
    _insert_trace(db, agent="alpha", created_at=_now_iso(), total_cost_usd=0.001)
    rows = cost_by_agent(db, "7d")
    # Same cost; tie broken by agent name ascending.
    assert [row["agent"] for row in rows] == ["alpha", "zeta"]


def test_cost_by_agent_zero_runs_agents_absent(tmp_path: Path) -> None:
    """An agent with no traces in window must not appear with all-zero row."""
    from horus_os.observability.queries import cost_by_agent

    db = _init(tmp_path)
    _seed_profile(db, "alpha")
    _seed_profile(db, "beta")
    _insert_trace(db, agent="alpha", created_at=_now_iso(), total_cost_usd=0.001)
    rows = cost_by_agent(db, "7d")
    assert len(rows) == 1
    assert rows[0]["agent"] == "alpha"


def test_cost_by_agent_rounds_to_6_decimals(tmp_path: Path) -> None:
    from horus_os.observability.queries import cost_by_agent

    db = _init(tmp_path)
    _seed_profile(db, "alpha")
    _insert_trace(db, agent="alpha", created_at=_now_iso(), total_cost_usd=0.0061500001234)
    rows = cost_by_agent(db, "7d")
    # Rounded in Python (NOT in SQL; sqlite3 ROUND is platform-variable).
    assert rows[0]["total_cost_usd"] == 0.00615


def test_cost_by_agent_re_exported_from_observability_package() -> None:
    from horus_os.observability import cost_by_agent as via_pkg
    from horus_os.observability.queries import cost_by_agent as direct

    assert via_pkg is direct
