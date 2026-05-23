"""Tests for the SQLite trace storage layer."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from horus_os import AgentResult, Database, ToolUse, TraceRecord


def _make_result(
    *,
    text: str = "ok",
    provider: str = "anthropic",
    model: str = "claude-sonnet-4-6",
    tool_uses: list[ToolUse] | None = None,
    usage: dict | None = None,
) -> AgentResult:
    return AgentResult(
        text=text,
        tool_uses=tool_uses or [],
        provider=provider,
        model=model,
        usage=usage or {},
    )


def test_init_creates_schema_on_fresh_db(tmp_path: Path) -> None:
    db_path = tmp_path / "horus.sqlite"
    db = Database(db_path)
    db.init()
    assert db_path.exists()
    with sqlite3.connect(str(db_path)) as conn:
        tables = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert "traces" in tables
        assert "schema_version" in tables
        version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
        assert version == 1


def test_init_is_idempotent(tmp_path: Path) -> None:
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    db.init()
    db.init()
    with sqlite3.connect(str(db.path)) as conn:
        rows = conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]
        assert rows == 1


def test_init_creates_parent_directory(tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "deeper" / "horus.sqlite"
    Database(db_path).init()
    assert db_path.exists()


def test_wal_journal_mode_is_enabled(tmp_path: Path) -> None:
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    with sqlite3.connect(str(db.path)) as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal"


def test_record_trace_returns_uuid_hex(tmp_path: Path) -> None:
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    trace_id = db.record_trace("hi", _make_result())
    assert isinstance(trace_id, str)
    assert len(trace_id) == 32
    int(trace_id, 16)  # raises if not valid hex


def test_record_and_get_round_trip(tmp_path: Path) -> None:
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    result = _make_result(
        text="hi there",
        tool_uses=[ToolUse(id="tu_1", name="echo", input={"text": "hi"})],
        usage={"input_tokens": 5, "output_tokens": 3},
    )
    trace_id = db.record_trace("say hi", result, latency_ms=42)
    record = db.get_trace(trace_id)
    assert record is not None
    assert isinstance(record, TraceRecord)
    assert record.trace_id == trace_id
    assert record.provider == "anthropic"
    assert record.model == "claude-sonnet-4-6"
    assert record.prompt == "say hi"
    assert record.response_text == "hi there"
    assert record.latency_ms == 42
    assert record.status == "success"
    assert record.error_message is None
    assert len(record.tool_uses) == 1
    assert record.tool_uses[0].name == "echo"
    assert record.tool_uses[0].input == {"text": "hi"}
    assert record.usage == {"input_tokens": 5, "output_tokens": 3}


def test_get_trace_returns_none_for_unknown_id(tmp_path: Path) -> None:
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    assert db.get_trace("00000000000000000000000000000000") is None


def test_list_traces_returns_newest_first(tmp_path: Path) -> None:
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    ids: list[str] = []
    for i in range(3):
        ids.append(db.record_trace(f"prompt {i}", _make_result(text=f"r{i}")))
        time.sleep(0.001)
    records = db.list_traces()
    assert [r.trace_id for r in records] == list(reversed(ids))
    assert records[0].response_text == "r2"


def test_list_traces_pagination(tmp_path: Path) -> None:
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    for i in range(5):
        db.record_trace(f"prompt {i}", _make_result(text=f"r{i}"))
    page_1 = db.list_traces(limit=2, offset=0)
    page_2 = db.list_traces(limit=2, offset=2)
    page_3 = db.list_traces(limit=2, offset=4)
    assert [r.response_text for r in page_1] == ["r4", "r3"]
    assert [r.response_text for r in page_2] == ["r2", "r1"]
    assert [r.response_text for r in page_3] == ["r0"]


def test_error_status_records_message(tmp_path: Path) -> None:
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    trace_id = db.record_trace(
        "broken",
        _make_result(text=""),
        status="error",
        error_message="provider returned 500",
    )
    record = db.get_trace(trace_id)
    assert record is not None
    assert record.status == "error"
    assert record.error_message == "provider returned 500"


def test_corrupted_tool_uses_json_decodes_to_empty_list(tmp_path: Path) -> None:
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    trace_id = db.record_trace("hi", _make_result())
    with sqlite3.connect(str(db.path)) as conn:
        conn.execute("UPDATE traces SET tool_uses = ? WHERE trace_id = ?", ("{not json", trace_id))
        conn.commit()
    record = db.get_trace(trace_id)
    assert record is not None
    assert record.tool_uses == []


def test_string_path_is_accepted(tmp_path: Path) -> None:
    db = Database(str(tmp_path / "horus.sqlite"))
    db.init()
    trace_id = db.record_trace("hi", _make_result())
    assert db.get_trace(trace_id) is not None
