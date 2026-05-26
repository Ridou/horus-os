"""Tests for cost_by_model in observability.queries.

cost_by_model is the per-model counterpart to cost_by_agent. It rolls
up llm_calls directly (not via traces), so it surfaces token sums and
cost across whichever models the agent picked over the window.

Same Pitfall 11 honesty contract as cost_by_agent: SUM excludes NULL
cost rows; a separate `uncosted_calls` counter surfaces those rows so
the dashboard / CLI can explain missing dollars instead of hiding them.

Same float-precision contract (USAGE-04): Python `round(value, 6)` at
the boundary; SQLite's banker rounding is platform-variable.
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


def _insert_llm_call(
    db: Database,
    *,
    created_at: str | None = None,
    provider: str = "anthropic",
    model: str = "claude-sonnet-4-6",
    cost_usd: float | None = 0.0001,
    input_tokens: int = 100,
    output_tokens: int = 50,
    cache_read_input_tokens: int = 0,
    cache_creation_input_tokens: int = 0,
    latency_ms: int = 100,
) -> str:
    cid = uuid.uuid4().hex
    with sqlite3.connect(str(db.path)) as conn:
        conn.execute(
            "INSERT INTO llm_calls "
            "(call_id, trace_id, iteration_idx, created_at, provider, model, "
            "input_tokens, output_tokens, cache_creation_input_tokens, "
            "cache_read_input_tokens, cost_usd, latency_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                cid,
                uuid.uuid4().hex,
                0,
                created_at or _now_iso(),
                provider,
                model,
                input_tokens,
                output_tokens,
                cache_creation_input_tokens,
                cache_read_input_tokens,
                cost_usd,
                latency_ms,
            ),
        )
    return cid


def test_cost_by_model_empty_db_returns_empty_list(tmp_path: Path) -> None:
    from horus_os.observability.queries import cost_by_model

    db = _init(tmp_path)
    assert cost_by_model(db, "7d") == []


def test_cost_by_model_window_excludes_old_rows(tmp_path: Path) -> None:
    from horus_os.observability.queries import cost_by_model

    db = _init(tmp_path)
    far_past = (datetime.now(UTC) - timedelta(days=8)).isoformat().replace("+00:00", "Z")
    _insert_llm_call(db, created_at=far_past, cost_usd=0.999)
    _insert_llm_call(db, created_at=_now_iso(), cost_usd=0.001)
    rows = cost_by_model(db, "7d")
    assert len(rows) == 1
    assert rows[0]["total_cost_usd"] == 0.001
    assert rows[0]["call_count"] == 1


def test_cost_by_model_multi_model_rollup(tmp_path: Path) -> None:
    from horus_os.observability.queries import cost_by_model

    db = _init(tmp_path)
    _insert_llm_call(db, model="claude-sonnet-4-6", cost_usd=0.001)
    _insert_llm_call(db, model="claude-sonnet-4-6", cost_usd=0.002)
    _insert_llm_call(db, provider="gemini", model="gemini-2.5-pro", cost_usd=0.0005)
    rows = cost_by_model(db, "7d")
    assert len(rows) == 2
    sonnet = next(r for r in rows if r["model"] == "claude-sonnet-4-6")
    gemini = next(r for r in rows if r["model"] == "gemini-2.5-pro")
    assert sonnet["total_cost_usd"] == 0.003
    assert sonnet["call_count"] == 2
    assert sonnet["provider"] == "anthropic"
    assert gemini["total_cost_usd"] == 0.0005
    assert gemini["call_count"] == 1
    assert gemini["provider"] == "gemini"


def test_cost_by_model_cache_tokens_sum(tmp_path: Path) -> None:
    """Cache tokens flow through SUM from llm_calls."""
    from horus_os.observability.queries import cost_by_model

    db = _init(tmp_path)
    _insert_llm_call(
        db,
        cost_usd=0.001,
        cache_read_input_tokens=500,
        cache_creation_input_tokens=20,
    )
    _insert_llm_call(
        db,
        cost_usd=0.001,
        cache_read_input_tokens=300,
        cache_creation_input_tokens=10,
    )
    rows = cost_by_model(db, "7d")
    assert rows[0]["total_cache_read_input_tokens"] == 800
    assert rows[0]["total_cache_creation_input_tokens"] == 30


def test_cost_by_model_uncosted_calls_surfaces_null_cost_rows(tmp_path: Path) -> None:
    """Pitfall 11: NULL cost surfaces via uncosted_calls counter; cost is 0.0."""
    from horus_os.observability.queries import cost_by_model

    db = _init(tmp_path)
    _insert_llm_call(db, cost_usd=0.001)
    _insert_llm_call(db, cost_usd=None)
    rows = cost_by_model(db, "7d")
    assert len(rows) == 1
    row = rows[0]
    assert row["uncosted_calls"] == 1
    assert row["call_count"] == 2
    # Matches cost_by_agent's family contract: SUM excludes NULL.
    assert row["total_cost_usd"] == 0.001


def test_cost_by_model_ordering_cost_desc_then_name_asc(tmp_path: Path) -> None:
    from horus_os.observability.queries import cost_by_model

    db = _init(tmp_path)
    _insert_llm_call(db, model="z-model", cost_usd=0.005)
    _insert_llm_call(db, model="a-model", cost_usd=0.010)
    # Tie: m-model and n-model both at 0.002.
    _insert_llm_call(db, model="n-model", cost_usd=0.002)
    _insert_llm_call(db, model="m-model", cost_usd=0.002)
    rows = cost_by_model(db, "7d")
    assert [r["model"] for r in rows] == ["a-model", "z-model", "m-model", "n-model"]


def test_cost_by_model_re_exported_from_observability_package() -> None:
    from horus_os.observability import cost_by_model as via_pkg
    from horus_os.observability.queries import cost_by_model as direct

    assert via_pkg is direct
    from horus_os.observability import __all__ as pkg_all
    from horus_os.observability.queries import __all__ as mod_all

    assert "cost_by_model" in pkg_all
    assert "cost_by_model" in mod_all
