"""SQLite persistence for agent traces, note writes, and agent profiles.

Three tables for v0.2:
  * `traces` is one row per agent invocation.
  * `note_writes` is one row per file write the memory layer performs.
  * `agent_profiles` is one row per named agent configuration.

Tool uses, usage, and write content are stored as text; structured
columns return parsed objects via the dataclass wrappers below.

Connection lifecycle is per-operation: each public method opens, runs,
and closes a connection. WAL mode plus a 5 second busy timeout handles
the default desktop concurrency profile.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from horus_os.types import AgentProfile, AgentResult, NoteWrite, ToolUse

SCHEMA_VERSION = 5

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS traces (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id            TEXT NOT NULL UNIQUE,
    created_at          TEXT NOT NULL,
    provider            TEXT NOT NULL,
    model               TEXT NOT NULL,
    prompt              TEXT NOT NULL,
    response_text       TEXT NOT NULL DEFAULT '',
    tool_uses           TEXT NOT NULL DEFAULT '[]',
    usage               TEXT NOT NULL DEFAULT '{}',
    latency_ms          INTEGER,
    status              TEXT NOT NULL DEFAULT 'success',
    error_message       TEXT,
    parent_trace_id     TEXT,
    agent_profile_name  TEXT,
    total_input_tokens  INTEGER,
    total_output_tokens INTEGER,
    total_cost_usd      REAL,
    total_duration_ms   INTEGER
);

CREATE INDEX IF NOT EXISTS idx_traces_created_at ON traces(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_traces_provider_model ON traces(provider, model);
-- idx_traces_parent_trace_id is created post-migration in init() because the
-- column may not exist on a pre-v4 database when this script first runs.

CREATE TABLE IF NOT EXISTS note_writes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    write_id        TEXT NOT NULL UNIQUE,
    created_at      TEXT NOT NULL,
    operation       TEXT NOT NULL,
    rel_path        TEXT NOT NULL,
    bytes_before    INTEGER NOT NULL,
    bytes_after     INTEGER NOT NULL,
    content         TEXT NOT NULL,
    trace_id        TEXT
);

CREATE INDEX IF NOT EXISTS idx_note_writes_created_at ON note_writes(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_note_writes_path ON note_writes(rel_path);

CREATE TABLE IF NOT EXISTS agent_profiles (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL UNIQUE,
    system_prompt TEXT NOT NULL DEFAULT '',
    default_model TEXT,
    allowed_tools TEXT,
    memory_scope  TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agent_profiles_name ON agent_profiles(name);

CREATE TABLE IF NOT EXISTS llm_calls (
    id                            INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id                       TEXT NOT NULL UNIQUE,
    trace_id                      TEXT NOT NULL,
    iteration_idx                 INTEGER NOT NULL,
    created_at                    TEXT NOT NULL,
    provider                      TEXT NOT NULL,
    model                         TEXT NOT NULL,
    input_tokens                  INTEGER NOT NULL DEFAULT 0,
    output_tokens                 INTEGER NOT NULL DEFAULT 0,
    cache_creation_input_tokens   INTEGER NOT NULL DEFAULT 0,
    cache_read_input_tokens       INTEGER NOT NULL DEFAULT 0,
    cost_usd                      REAL,
    pricing_missing               INTEGER NOT NULL DEFAULT 0,
    latency_ms                    INTEGER NOT NULL,
    status                        TEXT NOT NULL DEFAULT 'success',
    error_message                 TEXT,
    error_type                    TEXT
);

CREATE INDEX IF NOT EXISTS idx_llm_calls_trace_id ON llm_calls(trace_id);
CREATE INDEX IF NOT EXISTS idx_llm_calls_created_at ON llm_calls(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_llm_calls_model ON llm_calls(provider, model);

CREATE TABLE IF NOT EXISTS tool_invocations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    invocation_id   TEXT NOT NULL UNIQUE,
    trace_id        TEXT NOT NULL,
    parent_trace_id TEXT,
    created_at      TEXT NOT NULL,
    tool_name       TEXT NOT NULL,
    latency_ms      INTEGER NOT NULL,
    status          TEXT NOT NULL DEFAULT 'success',
    error_message   TEXT,
    error_type      TEXT,
    retry_count     INTEGER,
    output_size     INTEGER
);

CREATE INDEX IF NOT EXISTS idx_tool_invocations_trace_id ON tool_invocations(trace_id);
CREATE INDEX IF NOT EXISTS idx_tool_invocations_tool_name
    ON tool_invocations(tool_name, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tool_invocations_created_at
    ON tool_invocations(created_at DESC);
"""


@dataclass
class TraceRecord:
    """One persisted agent invocation."""

    trace_id: str
    created_at: str
    provider: str
    model: str
    prompt: str
    response_text: str
    tool_uses: list[ToolUse] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)
    latency_ms: int | None = None
    status: str = "success"
    error_message: str | None = None
    parent_trace_id: str | None = None
    agent_profile_name: str | None = None


class Database:
    """SQLite-backed trace and write store.

    The path is stored eagerly but the file is created lazily on first
    `init()` call. Subsequent operations open and close connections
    on demand so the object is safe to share across threads.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.row_factory = sqlite3.Row
        return conn

    def init(self) -> None:
        """Create the schema. Idempotent on both fresh and upgraded databases."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)
            row = conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
            stored_version = row[0] if row is not None else None
            if row is None:
                conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
            elif row[0] < SCHEMA_VERSION:
                conn.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION,))
            # v3 -> v4: ALTER TABLE is not idempotent; guard with OperationalError.
            if stored_version is not None and stored_version < 4:
                for ddl in (
                    "ALTER TABLE traces ADD COLUMN parent_trace_id TEXT",
                    "ALTER TABLE traces ADD COLUMN agent_profile_name TEXT",
                ):
                    try:
                        conn.execute(ddl)
                    except sqlite3.OperationalError:
                        # Column already exists; safe to ignore.
                        pass
            # v4 -> v5: four nullable rollup columns on traces. ADD COLUMN is not
            # idempotent; guard with OperationalError. New columns stay NULL on
            # existing v0.3 rows because SQLite refuses NOT NULL ADD COLUMN
            # without a DEFAULT on a populated table, and a default of zero
            # would lie about pre-v0.4 rows that simply had no measurement.
            if stored_version is not None and stored_version < 5:
                for ddl in (
                    "ALTER TABLE traces ADD COLUMN total_input_tokens INTEGER",
                    "ALTER TABLE traces ADD COLUMN total_output_tokens INTEGER",
                    "ALTER TABLE traces ADD COLUMN total_cost_usd REAL",
                    "ALTER TABLE traces ADD COLUMN total_duration_ms INTEGER",
                ):
                    try:
                        conn.execute(ddl)
                    except sqlite3.OperationalError:
                        # Column already exists; safe to ignore.
                        pass
            # The parent_trace_id index lives outside SCHEMA_SQL so it only runs
            # after the column is guaranteed to exist (either via fresh CREATE
            # TABLE or via the v3 -> v4 ALTER TABLE block above).
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_traces_parent_trace_id ON traces(parent_trace_id)"
            )
            now = _now_iso()
            conn.execute(
                """
                INSERT OR IGNORE INTO agent_profiles (
                    name, system_prompt, default_model, allowed_tools,
                    memory_scope, created_at, updated_at
                ) VALUES (?, ?, NULL, NULL, NULL, ?, ?)
                """,
                ("default", "You are a helpful assistant.", now, now),
            )

    def record_trace(
        self,
        prompt: str,
        result: AgentResult,
        *,
        parent_trace_id: str | None = None,
        agent_profile_name: str | None = None,
        latency_ms: int | None = None,
        status: str = "success",
        error_message: str | None = None,
    ) -> str:
        """Write one trace row. Returns the generated trace_id (UUID4)."""
        trace_id = uuid.uuid4().hex
        created_at = _now_iso()
        tool_uses_json = json.dumps(
            [{"id": u.id, "name": u.name, "input": u.input} for u in result.tool_uses]
        )
        usage_json = json.dumps(result.usage)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO traces (
                    trace_id, created_at, provider, model, prompt,
                    response_text, tool_uses, usage, latency_ms,
                    status, error_message, parent_trace_id, agent_profile_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trace_id,
                    created_at,
                    result.provider,
                    result.model,
                    prompt,
                    result.text,
                    tool_uses_json,
                    usage_json,
                    latency_ms,
                    status,
                    error_message,
                    parent_trace_id,
                    agent_profile_name,
                ),
            )
        return trace_id

    def list_traces(self, *, limit: int = 50, offset: int = 0) -> list[TraceRecord]:
        """Return traces ordered by creation time, newest first."""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT trace_id, created_at, provider, model, prompt,
                       response_text, tool_uses, usage, latency_ms,
                       status, error_message, parent_trace_id, agent_profile_name
                FROM traces
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
            return [self._row_to_trace(row) for row in cursor.fetchall()]

    def get_trace(self, trace_id: str) -> TraceRecord | None:
        """Return one trace by id, or None if not found."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT trace_id, created_at, provider, model, prompt,
                       response_text, tool_uses, usage, latency_ms,
                       status, error_message, parent_trace_id, agent_profile_name
                FROM traces
                WHERE trace_id = ?
                """,
                (trace_id,),
            ).fetchone()
            return self._row_to_trace(row) if row is not None else None

    def list_child_traces(self, parent_trace_id: str) -> list[TraceRecord]:
        """Return all traces whose parent_trace_id matches, oldest first."""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT trace_id, created_at, provider, model, prompt,
                       response_text, tool_uses, usage, latency_ms,
                       status, error_message, parent_trace_id, agent_profile_name
                FROM traces
                WHERE parent_trace_id = ?
                ORDER BY id ASC
                """,
                (parent_trace_id,),
            )
            return [self._row_to_trace(row) for row in cursor.fetchall()]

    def record_note_write(
        self,
        operation: str,
        rel_path: str,
        bytes_before: int,
        bytes_after: int,
        content: str,
        *,
        trace_id: str | None = None,
    ) -> str:
        """Write one note_writes row. Returns the generated write_id (UUID4)."""
        write_id = uuid.uuid4().hex
        created_at = _now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO note_writes (
                    write_id, created_at, operation, rel_path,
                    bytes_before, bytes_after, content, trace_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    write_id,
                    created_at,
                    operation,
                    rel_path,
                    bytes_before,
                    bytes_after,
                    content,
                    trace_id,
                ),
            )
        return write_id

    def list_note_writes(self, *, limit: int = 50, offset: int = 0) -> list[NoteWrite]:
        """Return note writes ordered by creation time, newest first."""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT write_id, created_at, operation, rel_path,
                       bytes_before, bytes_after, content, trace_id
                FROM note_writes
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
            return [self._row_to_write(row) for row in cursor.fetchall()]

    def load_profile(self, name: str) -> AgentProfile | None:
        """Return one agent profile by name, or None if not found."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM agent_profiles WHERE name = ?", (name,)).fetchone()
            return self._row_to_profile(row) if row is not None else None

    def save_profile(self, profile: AgentProfile) -> None:
        """Upsert an agent profile. created_at is preserved on conflict."""
        now = _now_iso()
        allowed_tools_json = (
            json.dumps(profile.allowed_tools) if profile.allowed_tools is not None else None
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO agent_profiles (
                    name, system_prompt, default_model, allowed_tools,
                    memory_scope, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    system_prompt = excluded.system_prompt,
                    default_model = excluded.default_model,
                    allowed_tools = excluded.allowed_tools,
                    memory_scope = excluded.memory_scope,
                    updated_at = excluded.updated_at
                """,
                (
                    profile.name,
                    profile.system_prompt,
                    profile.default_model,
                    allowed_tools_json,
                    profile.memory_scope,
                    now,
                    now,
                ),
            )

    def list_profiles(self) -> list[AgentProfile]:
        """Return all agent profiles ordered by name ascending."""
        with self._connect() as conn:
            cursor = conn.execute("SELECT * FROM agent_profiles ORDER BY name ASC")
            return [self._row_to_profile(row) for row in cursor.fetchall()]

    def delete_profile(self, name: str) -> bool:
        """Delete an agent profile by name. Returns True if a row was deleted."""
        with self._connect() as conn:
            result = conn.execute("DELETE FROM agent_profiles WHERE name = ?", (name,))
            return result.rowcount > 0

    @staticmethod
    def _row_to_profile(row: sqlite3.Row) -> AgentProfile:
        allowed_tools = None
        if row["allowed_tools"] is not None:
            try:
                allowed_tools = json.loads(row["allowed_tools"])
            except json.JSONDecodeError:
                allowed_tools = None
        return AgentProfile(
            name=row["name"],
            system_prompt=row["system_prompt"],
            default_model=row["default_model"],
            allowed_tools=allowed_tools,
            memory_scope=row["memory_scope"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_trace(row: sqlite3.Row) -> TraceRecord:
        try:
            raw_tool_uses = json.loads(row["tool_uses"] or "[]")
        except json.JSONDecodeError:
            raw_tool_uses = []
        try:
            usage = json.loads(row["usage"] or "{}")
        except json.JSONDecodeError:
            usage = {}
        tool_uses = [
            ToolUse(
                id=str(item.get("id", "")),
                name=str(item.get("name", "")),
                input=dict(item.get("input") or {}),
            )
            for item in raw_tool_uses
            if isinstance(item, dict)
        ]
        return TraceRecord(
            trace_id=row["trace_id"],
            created_at=row["created_at"],
            provider=row["provider"],
            model=row["model"],
            prompt=row["prompt"],
            response_text=row["response_text"],
            tool_uses=tool_uses,
            usage=usage if isinstance(usage, dict) else {},
            latency_ms=row["latency_ms"],
            status=row["status"],
            error_message=row["error_message"],
            parent_trace_id=row["parent_trace_id"],
            agent_profile_name=row["agent_profile_name"],
        )

    @staticmethod
    def _row_to_write(row: sqlite3.Row) -> NoteWrite:
        return NoteWrite(
            write_id=row["write_id"],
            created_at=row["created_at"],
            operation=row["operation"],
            rel_path=row["rel_path"],
            bytes_before=row["bytes_before"],
            bytes_after=row["bytes_after"],
            content=row["content"],
            trace_id=row["trace_id"],
        )


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
