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
        assert version == 13


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


def test_agent_activity_groups_per_agent(tmp_path: Path) -> None:
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    db.record_trace("a1", _make_result(), agent_profile_name="Coordinator")
    time.sleep(0.001)
    last_coord = db.record_trace("a2", _make_result(), agent_profile_name="Coordinator")
    db.record_trace("b1", _make_result(), agent_profile_name="Engineer")
    # An unattributed trace buckets under the literal "default" key.
    db.record_trace("c1", _make_result())

    activity = db.agent_activity()
    assert activity["Coordinator"][0] == 2
    assert activity["Engineer"][0] == 1
    assert activity["default"][0] == 1
    # last_created_at for Coordinator matches the newer of its two traces.
    coord_record = db.get_trace(last_coord)
    assert coord_record is not None
    assert activity["Coordinator"][1] == coord_record.created_at


def test_agent_activity_empty_on_fresh_db(tmp_path: Path) -> None:
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    assert db.agent_activity() == {}


def test_list_traces_for_agent_newest_first(tmp_path: Path) -> None:
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    db.record_trace("x1", _make_result(text="r0"), agent_profile_name="Writer")
    time.sleep(0.001)
    db.record_trace("x2", _make_result(text="r1"), agent_profile_name="Writer")
    db.record_trace("other", _make_result(text="r2"), agent_profile_name="Operator")
    # Unattributed traces match the "default" bucket.
    db.record_trace("d1", _make_result(text="r3"))

    writer = db.list_traces_for_agent("Writer")
    assert [t.response_text for t in writer] == ["r1", "r0"]
    assert db.list_traces_for_agent("Writer", limit=1)[0].response_text == "r1"
    assert [t.response_text for t in db.list_traces_for_agent("default")] == ["r3"]


def test_count_traces(tmp_path: Path) -> None:
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    assert db.count_traces() == 0
    db.record_trace("hi", _make_result())
    db.record_trace("hi again", _make_result())
    assert db.count_traces() == 2


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
        assert version == 13
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
        assert version == 13
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
        assert version == 13
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


# ---------------------------------------------------------------------------
# v0.3 (schema v4) to v0.4 (schema v5) migration tests
# ---------------------------------------------------------------------------

import shutil  # noqa: E402

V0_3_FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "v0_3_database.sqlite3"


def test_schema_v4_database_upgrades_to_v5(tmp_path: Path) -> None:
    """Single highest-leverage check for Pitfall 11 (additive-only contract).

    Copies the checked-in v0.3 fixture to a tmp directory so the test does
    not mutate it, runs Database.init() on the copy, and asserts the v4 to
    v5 upgrade adds the new tables and columns while preserving the old
    usage JSON blob and leaving pre-v0.4 rows NULL on the new columns.
    """
    assert V0_3_FIXTURE_PATH.exists(), (
        f"v0.3 fixture missing at {V0_3_FIXTURE_PATH}; "
        "run scripts/build_v0_3_fixture.py to regenerate"
    )
    db_path = tmp_path / "horus.sqlite"
    shutil.copy(V0_3_FIXTURE_PATH, db_path)

    db = Database(db_path)
    db.init()

    with sqlite3.connect(str(db_path)) as conn:
        version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
        assert version == 13
        tables = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert "llm_calls" in tables
        assert "tool_invocations" in tables
        traces_cols = {row[1] for row in conn.execute("PRAGMA table_info(traces)")}
        assert {
            "total_input_tokens",
            "total_output_tokens",
            "total_cost_usd",
            "total_duration_ms",
        }.issubset(traces_cols)
        # Pre-v0.4 rows must have NULL on the new rollup columns (Pitfall 11).
        rollup_rows = conn.execute(
            "SELECT total_input_tokens, total_output_tokens, "
            "total_cost_usd, total_duration_ms FROM traces"
        ).fetchall()
        assert len(rollup_rows) == 2
        for row in rollup_rows:
            assert all(value is None for value in row)
        # Old usage JSON blob must still read back intact (Pitfall 11).
        usage_row = conn.execute(
            "SELECT usage FROM traces WHERE usage LIKE '%input_tokens%'"
        ).fetchone()
        assert usage_row is not None
        assert "input_tokens" in usage_row[0]
        assert "output_tokens" in usage_row[0]


def test_v5_init_is_idempotent(tmp_path: Path) -> None:
    """Three init() calls in a row leave a v5 database in a stable state."""
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    db.init()
    db.init()
    with sqlite3.connect(str(db.path)) as conn:
        version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
        assert version == 13
        llm_count = conn.execute("SELECT COUNT(*) FROM llm_calls").fetchone()[0]
        assert llm_count == 0
        tool_count = conn.execute("SELECT COUNT(*) FROM tool_invocations").fetchone()[0]
        assert tool_count == 0


def test_pragmas_read_back_correctly(tmp_path: Path) -> None:
    """STORE-05 + Pitfall 8: journal_mode=wal and synchronous=NORMAL after init.

    journal_mode is a file-level property and persists across connections;
    a fresh raw sqlite3.connect on the same path must report 'wal'.
    synchronous is per-connection, so we open a connection via the same
    PRAGMA dance Database._connect uses and assert it reads back as 1
    (NORMAL), never 2 (FULL) or 0 (OFF).
    """
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    # File-level: journal_mode persists across connections.
    with sqlite3.connect(str(db.path)) as raw:
        journal_mode = raw.execute("PRAGMA journal_mode").fetchone()[0]
    assert journal_mode.lower() == "wal", f"expected journal_mode=wal, got {journal_mode!r}"
    # Per-connection: synchronous must come back as NORMAL on connections
    # opened via the same pragma dance as Database._connect.
    conn = sqlite3.connect(str(db.path), isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        synchronous = conn.execute("PRAGMA synchronous").fetchone()[0]
    finally:
        conn.close()
    assert synchronous == 1, (
        f"expected synchronous=1 (NORMAL), got {synchronous} (0=OFF, 1=NORMAL, 2=FULL, 3=EXTRA)"
    )


# ---------------------------------------------------------------------------
# v7 -> v8 migration: integration_verification_state (MIG-06)
# ---------------------------------------------------------------------------


def test_v7_to_v8_migration_adds_verification_table_idempotently(tmp_path: Path) -> None:
    """A v7 database upgrades to v8 by gaining integration_verification_state.

    Simulates a pre-v8 database by creating schema_version=7 and inserting a
    sentinel row in agent_profiles. Runs init() twice to prove idempotency.
    The sentinel row must survive the upgrade (additive-only contract, MIG-06).
    """
    db_path = tmp_path / "horus.sqlite"
    # Build a minimal v7 database: version row + sentinel agent row, no new table.
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(
            """
            CREATE TABLE schema_version (version INTEGER NOT NULL PRIMARY KEY);
            INSERT INTO schema_version (version) VALUES (7);
            CREATE TABLE agent_profiles (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL UNIQUE,
                system_prompt TEXT NOT NULL DEFAULT '',
                default_model TEXT,
                allowed_tools TEXT,
                memory_scope  TEXT,
                color         TEXT,
                description   TEXT,
                soul_path     TEXT,
                created_at    TEXT NOT NULL,
                updated_at    TEXT NOT NULL
            );
            INSERT INTO agent_profiles (name, system_prompt, created_at, updated_at)
                VALUES ('sentinel-v7', 'I am a sentinel row', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z');
            """
        )

    db = Database(db_path)
    # First init: upgrade from v7 to v8.
    db.init()
    with sqlite3.connect(str(db_path)) as conn:
        version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
        assert version == 13, f"expected schema_version=13 after upgrade, got {version}"
        tables = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert "integration_verification_state" in tables, (
            "integration_verification_state table must exist after v7->v8 upgrade"
        )
        # Sentinel row must survive the additive migration.
        sentinel = conn.execute(
            "SELECT system_prompt FROM agent_profiles WHERE name = 'sentinel-v7'"
        ).fetchone()
        assert sentinel is not None and sentinel[0] == "I am a sentinel row", (
            f"sentinel row lost or corrupted after upgrade: {sentinel}"
        )

    # Second init: idempotent, no exception, version stays at current.
    db.init()
    with sqlite3.connect(str(db_path)) as conn:
        version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
        assert version == 13, "version must remain 13 after second init()"
        count = conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]
        assert count == 1, "schema_version must have exactly one row"


def test_integration_verification_hash_change_invalidates(tmp_path: Path) -> None:
    """Key hash change must reset verified to 0 and clear verified_at (VERIFY-03).

    Also proves that same-hash re-write preserves an existing verified=1 state.
    """
    db = Database(tmp_path / "horus.sqlite")
    db.init()

    # Insert first hash, mark verified.
    db.upsert_integration_verification("anthropic", "sha256-hashA", verified=True)
    row = db.get_integration_verification("anthropic")
    assert row is not None
    assert row["verified"] == 1, "verified should be 1 after marking True"
    assert row["verified_at"] is not None, "verified_at should be set when verified=True"
    assert row["key_hash"] == "sha256-hashA"

    # Re-upsert the same hash with verified=False: must NOT clobber the stored verified=1.
    db.upsert_integration_verification("anthropic", "sha256-hashA", verified=False)
    row = db.get_integration_verification("anthropic")
    assert row is not None
    assert row["verified"] == 1, "same-hash write must preserve existing verified=1"

    # Now upsert a different hash: must reset verified to 0 and clear verified_at.
    db.upsert_integration_verification("anthropic", "sha256-hashB", verified=False)
    row = db.get_integration_verification("anthropic")
    assert row is not None
    assert row["verified"] == 0, "hash change must reset verified to 0"
    assert row["verified_at"] is None, "hash change must clear verified_at"
    assert row["key_hash"] == "sha256-hashB", "key_hash must update to new hash"

    # Unknown integration_id returns None.
    assert db.get_integration_verification("unknown-integration") is None
