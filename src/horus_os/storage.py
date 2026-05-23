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

SCHEMA_VERSION = 3

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS traces (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id        TEXT NOT NULL UNIQUE,
    created_at      TEXT NOT NULL,
    provider        TEXT NOT NULL,
    model           TEXT NOT NULL,
    prompt          TEXT NOT NULL,
    response_text   TEXT NOT NULL DEFAULT '',
    tool_uses       TEXT NOT NULL DEFAULT '[]',
    usage           TEXT NOT NULL DEFAULT '{}',
    latency_ms      INTEGER,
    status          TEXT NOT NULL DEFAULT 'success',
    error_message   TEXT
);

CREATE INDEX IF NOT EXISTS idx_traces_created_at ON traces(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_traces_provider_model ON traces(provider, model);

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
            if row is None:
                conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
            elif row[0] < SCHEMA_VERSION:
                conn.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION,))
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
                    status, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                       status, error_message
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
                       status, error_message
                FROM traces
                WHERE trace_id = ?
                """,
                (trace_id,),
            ).fetchone()
            return self._row_to_trace(row) if row is not None else None

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
