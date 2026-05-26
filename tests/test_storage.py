"""Tests for the SQLite trace storage layer."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from horus_os import AgentProfile, AgentResult, Database, ToolUse, TraceRecord


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
        assert "note_writes" in tables
        assert "agent_profiles" in tables
        version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
        assert version == 5


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


def test_record_note_write_returns_uuid_hex(tmp_path: Path) -> None:
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    write_id = db.record_note_write("create", "a.md", 0, 5, "hello")
    assert isinstance(write_id, str)
    assert len(write_id) == 32
    int(write_id, 16)


def test_list_note_writes_newest_first(tmp_path: Path) -> None:
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    db.record_note_write("create", "a.md", 0, 1, "a")
    db.record_note_write("append", "a.md", 1, 3, "ab")
    db.record_note_write("create", "b.md", 0, 1, "x")
    writes = db.list_note_writes()
    assert len(writes) == 3
    assert writes[0].rel_path == "b.md"
    assert writes[-1].rel_path == "a.md"
    assert writes[-1].operation == "create"


def test_schema_v1_database_upgrades_to_current(tmp_path: Path) -> None:
    # Simulate a database created by a v1 build (just the v1 surface).
    db_path = tmp_path / "horus.sqlite"
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(
            """
            CREATE TABLE schema_version (version INTEGER NOT NULL PRIMARY KEY);
            INSERT INTO schema_version (version) VALUES (1);
            CREATE TABLE traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt TEXT NOT NULL,
                response_text TEXT NOT NULL DEFAULT '',
                tool_uses TEXT NOT NULL DEFAULT '[]',
                usage TEXT NOT NULL DEFAULT '{}',
                latency_ms INTEGER,
                status TEXT NOT NULL DEFAULT 'success',
                error_message TEXT
            );
            """
        )
    db = Database(db_path)
    db.init()
    with sqlite3.connect(str(db_path)) as conn:
        version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
        assert version == 5
        tables = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert "note_writes" in tables
        assert "agent_profiles" in tables


def test_init_creates_default_agent(tmp_path: Path) -> None:
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    with sqlite3.connect(str(tmp_path / "horus.sqlite")) as conn:
        row = conn.execute(
            "SELECT name, system_prompt FROM agent_profiles WHERE name='default'"
        ).fetchone()
        assert row is not None
        assert row[0] == "default"
        assert row[1] == "You are a helpful assistant."


def test_init_default_agent_is_idempotent(tmp_path: Path) -> None:
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    db.init()
    db.init()
    with sqlite3.connect(str(tmp_path / "horus.sqlite")) as conn:
        count = conn.execute("SELECT COUNT(*) FROM agent_profiles").fetchone()[0]
        assert count == 1


def test_schema_v2_database_upgrades_to_v3(tmp_path: Path) -> None:
    db_path = tmp_path / "horus.sqlite"
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(
            """
            CREATE TABLE schema_version (version INTEGER NOT NULL PRIMARY KEY);
            INSERT INTO schema_version (version) VALUES (2);
            CREATE TABLE traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt TEXT NOT NULL,
                response_text TEXT NOT NULL DEFAULT '',
                tool_uses TEXT NOT NULL DEFAULT '[]',
                usage TEXT NOT NULL DEFAULT '{}',
                latency_ms INTEGER,
                status TEXT NOT NULL DEFAULT 'success',
                error_message TEXT
            );
            INSERT INTO traces (trace_id, created_at, provider, model, prompt)
                VALUES ('abc123', '2026-01-01T00:00:00Z', 'anthropic', 'claude-sonnet-4-6', 'hello');
            CREATE TABLE note_writes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                write_id TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                operation TEXT NOT NULL,
                rel_path TEXT NOT NULL,
                bytes_before INTEGER NOT NULL,
                bytes_after INTEGER NOT NULL,
                content TEXT NOT NULL,
                trace_id TEXT
            );
            """
        )
    db = Database(db_path)
    db.init()
    with sqlite3.connect(str(db_path)) as conn:
        tables = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert "agent_profiles" in tables
        version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
        assert version == 5
    record = db.get_trace("abc123")
    assert record is not None
    assert record.prompt == "hello"


# ---------------------------------------------------------------------------
# AgentProfile CRUD tests
# ---------------------------------------------------------------------------


def test_load_profile_returns_none_for_missing(tmp_path: Path) -> None:
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    assert db.load_profile("nonexistent") is None


def test_load_profile_returns_profile(tmp_path: Path) -> None:
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    profile = db.load_profile("default")
    assert profile is not None
    assert isinstance(profile, AgentProfile)
    assert profile.name == "default"
    assert profile.system_prompt == "You are a helpful assistant."
    assert profile.default_model is None
    assert profile.allowed_tools is None
    assert profile.memory_scope is None


def test_save_profile_creates_new(tmp_path: Path) -> None:
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    profile = AgentProfile(name="researcher", system_prompt="You research things.")
    db.save_profile(profile)
    loaded = db.load_profile("researcher")
    assert loaded is not None
    assert loaded.name == "researcher"
    assert loaded.system_prompt == "You research things."


def test_save_profile_updates_preserves_created_at(tmp_path: Path) -> None:
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    profile = AgentProfile(name="coder", system_prompt="You write code.")
    db.save_profile(profile)
    original = db.load_profile("coder")
    assert original is not None

    updated = AgentProfile(name="coder", system_prompt="You write better code.")
    db.save_profile(updated)
    reloaded = db.load_profile("coder")
    assert reloaded is not None
    assert reloaded.system_prompt == "You write better code."
    assert reloaded.created_at == original.created_at
    assert reloaded.updated_at >= original.updated_at


def test_save_profile_round_trips_allowed_tools(tmp_path: Path) -> None:
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    tools = ["read_file", "write_note"]
    profile = AgentProfile(name="restricted", system_prompt="Limited.", allowed_tools=tools)
    db.save_profile(profile)
    loaded = db.load_profile("restricted")
    assert loaded is not None
    assert loaded.allowed_tools == tools


def test_list_profiles_order(tmp_path: Path) -> None:
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    db.save_profile(AgentProfile(name="zebra", system_prompt="z"))
    db.save_profile(AgentProfile(name="alpha", system_prompt="a"))
    profiles = db.list_profiles()
    names = [p.name for p in profiles]
    assert names == sorted(names)
    assert "default" in names
    assert "alpha" in names
    assert "zebra" in names


def test_delete_profile_returns_true(tmp_path: Path) -> None:
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    db.save_profile(AgentProfile(name="temp", system_prompt="temporary"))
    assert db.delete_profile("temp") is True
    assert db.load_profile("temp") is None


def test_delete_profile_returns_false_for_missing(tmp_path: Path) -> None:
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    assert db.delete_profile("ghost") is False


# ---------------------------------------------------------------------------
# v3 -> v4 migration: parent_trace_id and agent_profile_name
# ---------------------------------------------------------------------------


def test_migration_v3_to_v4(tmp_path: Path) -> None:
    """A v3 database (no parent_trace_id or agent_profile_name columns) upgrades to v4."""
    db_path = tmp_path / "horus.sqlite"
    # Build a v3 database manually: traces table without the new columns, version=3.
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(
            """
            CREATE TABLE schema_version (version INTEGER NOT NULL PRIMARY KEY);
            INSERT INTO schema_version (version) VALUES (3);
            CREATE TABLE traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt TEXT NOT NULL,
                response_text TEXT NOT NULL DEFAULT '',
                tool_uses TEXT NOT NULL DEFAULT '[]',
                usage TEXT NOT NULL DEFAULT '{}',
                latency_ms INTEGER,
                status TEXT NOT NULL DEFAULT 'success',
                error_message TEXT
            );
            INSERT INTO traces (trace_id, created_at, provider, model, prompt)
                VALUES ('legacy', '2026-01-01T00:00:00Z', 'anthropic', 'claude', 'old');
            CREATE TABLE note_writes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                write_id TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                operation TEXT NOT NULL,
                rel_path TEXT NOT NULL,
                bytes_before INTEGER NOT NULL,
                bytes_after INTEGER NOT NULL,
                content TEXT NOT NULL,
                trace_id TEXT
            );
            CREATE TABLE agent_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                system_prompt TEXT NOT NULL DEFAULT '',
                default_model TEXT,
                allowed_tools TEXT,
                memory_scope TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
    db = Database(db_path)
    db.init()
    # Version is bumped to 5.
    with sqlite3.connect(str(db_path)) as conn:
        version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
        assert version == 5
        cols = {row[1] for row in conn.execute("PRAGMA table_info(traces)")}
        assert "parent_trace_id" in cols
        assert "agent_profile_name" in cols
    # Legacy row still readable.
    legacy = db.get_trace("legacy")
    assert legacy is not None
    assert legacy.parent_trace_id is None
    assert legacy.agent_profile_name is None
    # New rows can carry parent_trace_id round-trip.
    new_id = db.record_trace(
        "child task",
        _make_result(),
        parent_trace_id="legacy",
        agent_profile_name="helper",
    )
    child = db.get_trace(new_id)
    assert child is not None
    assert child.parent_trace_id == "legacy"
    assert child.agent_profile_name == "helper"


def test_record_trace_with_parent(tmp_path: Path) -> None:
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    parent_id = db.record_trace("parent prompt", _make_result())
    child_id = db.record_trace(
        "child task",
        _make_result(),
        parent_trace_id=parent_id,
        agent_profile_name="sub",
    )
    child = db.get_trace(child_id)
    assert child is not None
    assert child.parent_trace_id == parent_id
    assert child.agent_profile_name == "sub"


def test_record_trace_defaults_parent_to_none(tmp_path: Path) -> None:
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    trace_id = db.record_trace("no parent", _make_result())
    record = db.get_trace(trace_id)
    assert record is not None
    assert record.parent_trace_id is None
    assert record.agent_profile_name is None


def test_list_child_traces_returns_matching_children(tmp_path: Path) -> None:
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    parent_id = db.record_trace("parent", _make_result())
    child_a = db.record_trace(
        "a", _make_result(text="a"), parent_trace_id=parent_id, agent_profile_name="helper"
    )
    child_b = db.record_trace(
        "b", _make_result(text="b"), parent_trace_id=parent_id, agent_profile_name="helper"
    )
    # Unrelated trace with a different parent.
    db.record_trace("c", _make_result(text="c"), parent_trace_id="other-parent")
    children = db.list_child_traces(parent_id)
    assert len(children) == 2
    child_ids = {c.trace_id for c in children}
    assert child_ids == {child_a, child_b}


def test_list_child_traces_unknown_parent_returns_empty(tmp_path: Path) -> None:
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    assert db.list_child_traces("nonexistent") == []
