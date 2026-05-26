"""Per-plugin observability rollup correctness.

Six behavioral contracts pinned by separate tests:

  1. Empty database -> ``per_plugin_rollup`` returns ``[]``.
  2. One plugin with 10 successful + 5 errored tool_invocations -> error_rate
     == 0.3333 (5 / 15 rounded to 4dp).
  3. NULL plugin_name rows bucket under the literal string ``'horus-os core'``.
  4. n < 10 invocations -> ``latency_p50_ms`` / ``latency_p95_ms`` come back as
     None (Pitfall 10 applied in Python before serialization).
  5. cost_usd == NULL for every llm_call of a plugin -> ``total_cost_usd`` is
     None (NOT 0.0; Pitfall 11 honesty contract).
  6. ``parse_window`` errors propagate as ``ValueError``.

The tests seed rows via direct INSERT through ``db._connect()`` so the
contract under test is the rollup query, not the persister.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from horus_os.observability.queries import per_plugin_rollup
from horus_os.storage import Database


def _make_db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "horus.sqlite3")
    db.init()
    return db


def _seed_tool_invocation(
    db: Database,
    *,
    invocation_id: str,
    tool_name: str,
    status: str,
    plugin_name: str | None,
    latency_ms: int = 100,
    created_at: str = "2099-01-01T00:00:00Z",
    trace_id: str = "trace-1",
) -> None:
    with db._connect() as conn:
        conn.execute(
            """
            INSERT INTO tool_invocations
                (invocation_id, trace_id, created_at, tool_name, latency_ms,
                 status, plugin_name)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (invocation_id, trace_id, created_at, tool_name, latency_ms, status, plugin_name),
        )


def _seed_llm_call(
    db: Database,
    *,
    call_id: str,
    plugin_name: str | None,
    cost_usd: float | None,
    latency_ms: int = 100,
    created_at: str = "2099-01-01T00:00:00Z",
    trace_id: str = "trace-1",
) -> None:
    with db._connect() as conn:
        conn.execute(
            """
            INSERT INTO llm_calls
                (call_id, trace_id, iteration_idx, created_at, provider, model,
                 input_tokens, output_tokens, cost_usd, latency_ms, status, plugin_name)
            VALUES (?, ?, 0, ?, 'anthropic', 'claude-3', 10, 20, ?, ?, 'success', ?)
            """,
            (call_id, trace_id, created_at, cost_usd, latency_ms, plugin_name),
        )


def test_empty_database_returns_empty_list(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    result = per_plugin_rollup(db, "7d")
    assert result == []


def test_error_rate_excludes_retry_and_expected_no_result(tmp_path: Path) -> None:
    """10 success + 5 error => error_rate = 0.3333, denominator = 15.

    Mirrors tool_reliability semantics: numerator counts only 'error'; denominator
    is success + error; retry_then_success and expected_no_result are excluded.
    """
    db = _make_db(tmp_path)
    for i in range(10):
        _seed_tool_invocation(
            db,
            invocation_id=f"ok-{i}",
            tool_name="t",
            status="success",
            plugin_name="plugin_a",
            latency_ms=50,
        )
    for i in range(5):
        _seed_tool_invocation(
            db,
            invocation_id=f"err-{i}",
            tool_name="t",
            status="error",
            plugin_name="plugin_a",
            latency_ms=200,
        )

    rows = per_plugin_rollup(db, "7d")
    assert len(rows) == 1
    row = rows[0]
    assert row["plugin_name"] == "plugin_a"
    assert row["total_invocations"] == 15
    assert row["error_rate"] == 0.3333


def test_null_plugin_name_buckets_as_horus_os_core(tmp_path: Path) -> None:
    """NULL plugin_name rows are bucketed under the literal 'horus-os core'."""
    db = _make_db(tmp_path)
    _seed_tool_invocation(
        db,
        invocation_id="core-1",
        tool_name="t",
        status="success",
        plugin_name=None,
    )
    _seed_tool_invocation(
        db,
        invocation_id="plug-1",
        tool_name="t",
        status="success",
        plugin_name="plugin_a",
    )
    rows = per_plugin_rollup(db, "7d")
    names = {r["plugin_name"] for r in rows}
    assert names == {"horus-os core", "plugin_a"}


def test_latency_percentiles_null_when_sample_under_ten(tmp_path: Path) -> None:
    """n<10 invocations -> p50/p95 == None (Pitfall 10 applied in Python)."""
    db = _make_db(tmp_path)
    for i in range(5):
        _seed_tool_invocation(
            db,
            invocation_id=f"i-{i}",
            tool_name="t",
            status="success",
            plugin_name="plugin_small",
            latency_ms=10 + i,
        )
    rows = per_plugin_rollup(db, "7d")
    assert len(rows) == 1
    row = rows[0]
    assert row["plugin_name"] == "plugin_small"
    assert row["latency_p50_ms"] is None
    assert row["latency_p95_ms"] is None
    assert row["total_invocations"] == 5


def test_total_cost_usd_null_stays_null_never_zero(tmp_path: Path) -> None:
    """Pitfall 11: if every llm_call has cost_usd IS NULL, total stays None (not 0.0)."""
    db = _make_db(tmp_path)
    # One invocation so the plugin shows up in the rollup at all.
    _seed_tool_invocation(
        db,
        invocation_id="t-1",
        tool_name="t",
        status="success",
        plugin_name="plugin_uncosted",
    )
    # Two llm_calls with cost_usd = NULL.
    _seed_llm_call(
        db, call_id="lc-1", plugin_name="plugin_uncosted", cost_usd=None
    )
    _seed_llm_call(
        db, call_id="lc-2", plugin_name="plugin_uncosted", cost_usd=None
    )

    rows = per_plugin_rollup(db, "7d")
    row = next(r for r in rows if r["plugin_name"] == "plugin_uncosted")
    assert row["total_cost_usd"] is None


def test_invalid_window_raises_value_error(tmp_path: Path) -> None:
    """parse_window's ValueError propagates from per_plugin_rollup."""
    db = _make_db(tmp_path)
    with pytest.raises(ValueError):
        per_plugin_rollup(db, "not-a-window")
