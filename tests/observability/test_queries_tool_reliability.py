"""Tests for tool_reliability in observability.queries.

Pitfall 9: status enum is {success, error, retry_then_success,
expected_no_result}. retry_then_success is NOT an error.
expected_no_result is informational and NOT in the success-rate
denominator. Pitfall 7 + Pitfall 9: the error_message column never
appears anywhere in queries.py; only error_type (exception class name)
is surfaced.
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


def _insert_tool(
    db: Database,
    *,
    tool_name: str,
    status: str = "success",
    error_type: str | None = None,
    created_at: str | None = None,
    latency_ms: int = 50,
) -> None:
    with sqlite3.connect(str(db.path)) as conn:
        conn.execute(
            "INSERT INTO tool_invocations "
            "(invocation_id, trace_id, parent_trace_id, created_at, tool_name, "
            "latency_ms, status, error_message, error_type) "
            "VALUES (?, ?, NULL, ?, ?, ?, ?, NULL, ?)",
            (
                uuid.uuid4().hex,
                uuid.uuid4().hex,
                created_at or _now_iso(),
                tool_name,
                latency_ms,
                status,
                error_type,
            ),
        )


def test_tool_reliability_empty_database_returns_empty_list(tmp_path: Path) -> None:
    from horus_os.observability.queries import tool_reliability

    db = _init(tmp_path)
    assert tool_reliability(db, "7d") == []


def test_tool_reliability_aggregates_per_tool(tmp_path: Path) -> None:
    """4 success + 1 retry_then_success + 1 error -> success=5, error=1, rate=0.8333."""
    from horus_os.observability.queries import tool_reliability

    db = _init(tmp_path)
    for _ in range(4):
        _insert_tool(db, tool_name="read_file", status="success")
    _insert_tool(db, tool_name="read_file", status="retry_then_success")
    _insert_tool(db, tool_name="read_file", status="error", error_type="OSError")
    rows = tool_reliability(db, "7d")
    assert len(rows) == 1
    row = rows[0]
    assert row["tool_name"] == "read_file"
    assert row["call_count"] == 6
    assert row["success_count"] == 5
    assert row["error_count"] == 1
    assert row["retry_then_success_count"] == 1
    assert row["success_rate"] == round(5 / 6, 4)


def test_tool_reliability_retry_then_success_NOT_counted_as_error(tmp_path: Path) -> None:
    """Pitfall 9 regression: 10 success + 5 retry_then_success + 0 errors -> error_count=0."""
    from horus_os.observability.queries import tool_reliability

    db = _init(tmp_path)
    for _ in range(10):
        _insert_tool(db, tool_name="write_file", status="success")
    for _ in range(5):
        _insert_tool(db, tool_name="write_file", status="retry_then_success")
    rows = tool_reliability(db, "7d")
    row = next(r for r in rows if r["tool_name"] == "write_file")
    assert row["error_count"] == 0
    assert row["success_count"] == 15
    assert row["retry_then_success_count"] == 5
    assert row["success_rate"] == 1.0


def test_tool_reliability_expected_no_result_excluded_from_denominator(tmp_path: Path) -> None:
    """Pitfall 9: expected_no_result is informational, not success and not error."""
    from horus_os.observability.queries import tool_reliability

    db = _init(tmp_path)
    for _ in range(3):
        _insert_tool(db, tool_name="search_notes", status="expected_no_result")
    rows = tool_reliability(db, "7d")
    row = next(r for r in rows if r["tool_name"] == "search_notes")
    assert row["success_count"] == 0
    assert row["error_count"] == 0
    assert row["expected_no_result_count"] == 3
    # 0 success + 0 error = denominator 0, so success_rate is None NOT 0.0 or 1.0.
    assert row["success_rate"] is None


def test_tool_reliability_last_error_type_and_timestamp(tmp_path: Path) -> None:
    from horus_os.observability.queries import tool_reliability

    db = _init(tmp_path)
    older = (datetime.now(UTC) - timedelta(minutes=10)).isoformat().replace("+00:00", "Z")
    # Sleep 1 microsecond is wasteful; use crafted strings so MAX(created_at)
    # is unambiguous.
    newer = (datetime.now(UTC) - timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
    _insert_tool(
        db, tool_name="read_file", status="error", error_type="FileNotFoundError",
        created_at=older,
    )
    _insert_tool(
        db, tool_name="read_file", status="error", error_type="PermissionError",
        created_at=newer,
    )
    # A subsequent success row should not change last_error_type.
    _insert_tool(db, tool_name="read_file", status="success")
    rows = tool_reliability(db, "7d")
    row = next(r for r in rows if r["tool_name"] == "read_file")
    assert row["last_error_type"] == "PermissionError"
    assert row["last_error_at"] == newer


def test_tool_reliability_no_errors_returns_null_last_error(tmp_path: Path) -> None:
    from horus_os.observability.queries import tool_reliability

    db = _init(tmp_path)
    for _ in range(3):
        _insert_tool(db, tool_name="list_notes", status="success")
    rows = tool_reliability(db, "7d")
    row = next(r for r in rows if r["tool_name"] == "list_notes")
    assert row["last_error_type"] is None
    assert row["last_error_at"] is None


def test_tool_reliability_ordered_by_call_count_desc_then_name_asc(tmp_path: Path) -> None:
    from horus_os.observability.queries import tool_reliability

    db = _init(tmp_path)
    for _ in range(5):
        _insert_tool(db, tool_name="busy_tool")
    for _ in range(2):
        _insert_tool(db, tool_name="zeta_tied")
    for _ in range(2):
        _insert_tool(db, tool_name="alpha_tied")
    rows = tool_reliability(db, "7d")
    names = [r["tool_name"] for r in rows]
    # call_count DESC: busy_tool (5) first; ties (2 each) broken by name ASC.
    assert names == ["busy_tool", "alpha_tied", "zeta_tied"]


def test_tool_reliability_excludes_out_of_window_rows(tmp_path: Path) -> None:
    from horus_os.observability.queries import tool_reliability

    db = _init(tmp_path)
    far_past = (datetime.now(UTC) - timedelta(days=60)).isoformat().replace("+00:00", "Z")
    _insert_tool(db, tool_name="ancient_tool", created_at=far_past)
    _insert_tool(db, tool_name="recent_tool")
    rows = tool_reliability(db, "7d")
    names = [r["tool_name"] for r in rows]
    assert names == ["recent_tool"]


def test_tool_reliability_re_exported_from_observability_package() -> None:
    from horus_os.observability import tool_reliability as via_pkg
    from horus_os.observability.queries import tool_reliability as direct

    assert via_pkg is direct


def test_queries_py_never_references_error_message_column(tmp_path: Path) -> None:
    """Pitfall 7 + Pitfall 9 file content hygiene: error_message stays in the persister."""
    # Touch the unused fixture so pytest does not warn about ordering.
    _ = tmp_path
    src = Path(__file__).resolve().parents[2] / "src" / "horus_os" / "observability" / "queries.py"
    text = src.read_text()
    # Substring check: no `error_message` anywhere (uncommented or commented).
    assert "error_message" not in text
