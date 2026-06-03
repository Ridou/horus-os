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
from typing import Any, ClassVar

from horus_os.types import AgentProfile, AgentResult, NoteWrite, ToolUse

SCHEMA_VERSION = 12

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
    color         TEXT,
    description   TEXT,
    soul_path     TEXT,
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
    error_type                    TEXT,
    plugin_name                   TEXT  -- v6 OBSERVE-01: NULL = horus-os core
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
    output_size     INTEGER,
    plugin_name     TEXT  -- v6 OBSERVE-01: NULL = horus-os core
);

CREATE INDEX IF NOT EXISTS idx_tool_invocations_trace_id ON tool_invocations(trace_id);
CREATE INDEX IF NOT EXISTS idx_tool_invocations_tool_name
    ON tool_invocations(tool_name, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tool_invocations_created_at
    ON tool_invocations(created_at DESC);

-- v6: plugin runtime tables
CREATE TABLE IF NOT EXISTS plugins (
    name          TEXT PRIMARY KEY,
    version       TEXT NOT NULL,
    manifest_hash TEXT NOT NULL,
    enabled       INTEGER NOT NULL DEFAULT 1,
    installed_at  TEXT NOT NULL,
    source        TEXT NOT NULL CHECK (source IN ('entry_point', 'filesystem'))
);

CREATE TABLE IF NOT EXISTS plugin_capabilities (
    plugin_name    TEXT NOT NULL,
    plugin_version TEXT NOT NULL,
    capability     TEXT NOT NULL,
    manifest_hash  TEXT NOT NULL,
    state          TEXT NOT NULL CHECK (state IN ('granted', 'pending', 'revoked')),
    granted_at     TEXT,
    PRIMARY KEY (plugin_name, plugin_version, capability),
    FOREIGN KEY (plugin_name) REFERENCES plugins(name) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS plugin_status (
    plugin_name   TEXT PRIMARY KEY,
    status        TEXT NOT NULL CHECK (status IN ('loaded', 'pending', 'error', 'disabled')),
    error_phase   TEXT,
    error_message TEXT,
    last_seen     TEXT,
    FOREIGN KEY (plugin_name) REFERENCES plugins(name) ON DELETE CASCADE
);

-- v6 additive: PERMISSION-02 audit log. Append-only audit trail of
-- grant / revoke / pending_on_upgrade transitions. Schema version
-- stays at 6 (this table is additive within v6); the v5 -> v6
-- migration block in init() does not need a new ALTER TABLE because
-- CREATE TABLE IF NOT EXISTS is idempotent on both fresh and
-- upgraded databases.
CREATE TABLE IF NOT EXISTS plugin_capability_grants_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    plugin_name    TEXT NOT NULL,
    plugin_version TEXT NOT NULL,
    capability     TEXT NOT NULL,
    action         TEXT NOT NULL CHECK (action IN ('granted', 'revoked', 'pending_on_upgrade')),
    manifest_hash  TEXT NOT NULL,
    actor          TEXT NOT NULL CHECK (actor IN ('cli', 'dashboard', 'system')),
    timestamp      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_plugin_capability_grants_log_plugin
    ON plugin_capability_grants_log(plugin_name, timestamp DESC);

-- v8: integration verification state (Phase 62 - MIG-06)
-- CREATE TABLE IF NOT EXISTS is idempotent on both fresh and upgraded databases.
CREATE TABLE IF NOT EXISTS integration_verification_state (
    integration_id TEXT NOT NULL PRIMARY KEY,
    key_hash       TEXT NOT NULL,
    verified       INTEGER NOT NULL DEFAULT 0,
    verified_at    TEXT,
    updated_at     TEXT NOT NULL
);

-- v9: tasks queue table (Phase 63 - minimal scaffold for /tasks page)
-- CREATE TABLE IF NOT EXISTS is idempotent on both fresh and upgraded databases.
CREATE TABLE IF NOT EXISTS tasks (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id            TEXT NOT NULL UNIQUE,
    title              TEXT NOT NULL,
    description        TEXT NOT NULL DEFAULT '',
    status             TEXT NOT NULL DEFAULT 'pending'
                       CHECK (status IN ('pending', 'running', 'completed', 'error', 'cancelled')),
    agent_profile_name TEXT,
    trace_id           TEXT,
    is_demo_seed       INTEGER NOT NULL DEFAULT 0,
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at DESC);

-- v10: discord reaction feedback (Phase 64 - DISC-08)
-- CREATE TABLE IF NOT EXISTS is idempotent on both fresh and upgraded databases.
CREATE TABLE IF NOT EXISTS discord_feedback (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id  TEXT NOT NULL,
    channel_id  TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    emoji       TEXT NOT NULL,
    positive    INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL,
    UNIQUE(message_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_discord_feedback_created_at ON discord_feedback(created_at DESC);

-- v11: sync cursor tracking for Supabase push-only sync (Phase 65 - SUPA-01)
-- CREATE TABLE IF NOT EXISTS is idempotent on both fresh and upgraded databases.
CREATE TABLE IF NOT EXISTS sync_cursors (
    table_name     TEXT NOT NULL PRIMARY KEY,
    cursor_value   TEXT NOT NULL DEFAULT '1970-01-01T00:00:00.000000Z',
    last_synced_at TEXT NOT NULL
);

-- v12: schedules for the in-process cron scheduler (Phase 66 - REMOTE-05)
-- CREATE TABLE IF NOT EXISTS is idempotent on both fresh and upgraded databases.
CREATE TABLE IF NOT EXISTS schedules (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL UNIQUE,
    cron_expression     TEXT NOT NULL,
    agent_profile_name  TEXT NOT NULL,
    prompt              TEXT NOT NULL,
    enabled             INTEGER NOT NULL DEFAULT 1,
    catch_up_policy     TEXT NOT NULL DEFAULT 'coalesce',
    last_run_at         TEXT,
    next_run_at         TEXT,
    last_trace_id       TEXT,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);
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


@dataclass
class TaskRecord:
    """One persisted task row."""

    task_id: str
    title: str
    description: str
    status: str  # pending | running | completed | error | cancelled
    agent_profile_name: str | None
    trace_id: str | None
    is_demo_seed: bool
    created_at: str
    updated_at: str


@dataclass
class ScheduleRecord:
    """One persisted recurring-schedule row (Phase 66 - REMOTE-05)."""

    id: int
    name: str
    cron_expression: str
    agent_profile_name: str
    prompt: str
    enabled: int
    catch_up_policy: str
    last_run_at: str | None
    next_run_at: str | None
    last_trace_id: str | None
    created_at: str
    updated_at: str


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
            # v5 -> v6: two NULLABLE plugin_name columns on llm_calls and
            # tool_invocations. ADD COLUMN is not idempotent; guard with
            # OperationalError. New columns stay NULL on existing v0.4 rows
            # (NULL = "horus-os core" per OBSERVE-01). Fresh databases get
            # plugin_name via the SCHEMA_SQL CREATE TABLE blocks above, so
            # the ALTER TABLE here only runs on the v5 -> v6 upgrade path.
            # The plugins / plugin_capabilities / plugin_status tables are
            # created via CREATE TABLE IF NOT EXISTS in SCHEMA_SQL above.
            if stored_version is not None and stored_version < 6:
                for ddl in (
                    "ALTER TABLE llm_calls ADD COLUMN plugin_name TEXT",
                    "ALTER TABLE tool_invocations ADD COLUMN plugin_name TEXT",
                ):
                    try:
                        conn.execute(ddl)
                    except sqlite3.OperationalError:
                        # Column already exists; safe to ignore.
                        pass
            # v6 -> v7: three NULLABLE persona columns on agent_profiles. These
            # back the v0.7 starter-team feature (color, one-line description,
            # and the relative path to a SOUL.md persona file under notes_dir).
            # ADD COLUMN is not idempotent; guard with OperationalError. New
            # columns stay NULL on existing rows, including the seeded 'default'
            # profile. Fresh databases get these columns via the SCHEMA_SQL
            # CREATE TABLE block above, so this ALTER TABLE only runs on the
            # v6 -> v7 upgrade path.
            if stored_version is not None and stored_version < 7:
                for ddl in (
                    "ALTER TABLE agent_profiles ADD COLUMN color TEXT",
                    "ALTER TABLE agent_profiles ADD COLUMN description TEXT",
                    "ALTER TABLE agent_profiles ADD COLUMN soul_path TEXT",
                ):
                    try:
                        conn.execute(ddl)
                    except sqlite3.OperationalError:
                        # Column already exists; safe to ignore.
                        pass
            # v7 -> v8: integration_verification_state is a new table, not a column add.
            # CREATE TABLE IF NOT EXISTS in SCHEMA_SQL handles both fresh and upgraded
            # databases, so no ALTER TABLE is needed here. This block documents the
            # migration boundary for MIG-06 and ensures future phases can anchor
            # additional v8 work to a concrete stored_version check.
            if stored_version is not None and stored_version < 8:
                pass  # No ALTER TABLE needed - new table only (idempotent via SCHEMA_SQL)
            # v8 -> v9: tasks table is a new table, not a column add.
            # CREATE TABLE IF NOT EXISTS in SCHEMA_SQL handles both fresh and upgraded
            # databases, so no ALTER TABLE is needed here.
            if stored_version is not None and stored_version < 9:
                pass  # No ALTER TABLE needed - new table only (idempotent via SCHEMA_SQL)
            # v9 -> v10: discord_feedback table is a new table, not a column add.
            # CREATE TABLE IF NOT EXISTS in SCHEMA_SQL handles both fresh and upgraded
            # databases, so no ALTER TABLE is needed here.
            if stored_version is not None and stored_version < 10:
                pass  # No ALTER TABLE needed - new table only (idempotent via SCHEMA_SQL)
            # v10 -> v11: sync_cursors table is a new table, not a column add.
            # CREATE TABLE IF NOT EXISTS in SCHEMA_SQL handles both fresh and upgraded
            # databases, so no ALTER TABLE is needed here.
            if stored_version is not None and stored_version < 11:
                pass  # No ALTER TABLE needed - new table only (idempotent via SCHEMA_SQL)
            # v11 -> v12: schedules table is a new table, not a column add.
            # CREATE TABLE IF NOT EXISTS in SCHEMA_SQL handles both fresh and upgraded
            # databases, so no ALTER TABLE is needed here.
            if stored_version is not None and stored_version < 12:
                pass  # No ALTER TABLE needed - new table only (idempotent via SCHEMA_SQL)
            # The parent_trace_id index lives outside SCHEMA_SQL so it only runs
            # after the column is guaranteed to exist (either via fresh CREATE
            # TABLE or via the v3 -> v4 ALTER TABLE block above).
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_traces_parent_trace_id ON traces(parent_trace_id)"
            )
            # The plugin_name index lives outside SCHEMA_SQL for the same reason
            # as idx_traces_parent_trace_id: on an upgraded v5 database the
            # column did not exist when SCHEMA_SQL was authored. We rely on the
            # v5 -> v6 ALTER TABLE block above guaranteeing the column exists
            # on upgrade, and on the SCHEMA_SQL CREATE TABLE block declaring it
            # on a fresh database.
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tool_invocations_plugin "
                "ON tool_invocations(plugin_name, created_at)"
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
        trace_id: str | None = None,
        parent_trace_id: str | None = None,
        agent_profile_name: str | None = None,
        latency_ms: int | None = None,
        status: str = "success",
        error_message: str | None = None,
    ) -> str:
        """Write one trace row. Returns the generated trace_id (UUID4).

        Phase 33: `trace_id` is now an optional keyword. When supplied,
        the row uses that id verbatim so the caller can pre-generate one
        and pass the same id into observability events whose RUN_END
        rollup UPDATEs the matching traces row. When omitted, a fresh
        uuid4 is generated (Phase 32 behavior).
        """
        trace_id = trace_id if trace_id is not None else uuid.uuid4().hex
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

    def agent_activity(self) -> dict[str, tuple[int, str | None]]:
        """Return per-agent trace activity keyed by agent_profile_name.

        One row per distinct ``agent_profile_name`` that appears on at least
        one trace, mapping the name to a ``(trace_count, last_created_at)``
        pair. ``last_created_at`` is the maximum ``created_at`` over that
        agent's traces (ISO 8601 UTC string). Traces with a NULL
        ``agent_profile_name`` are bucketed under the literal key
        ``"default"`` so the dashboard team view can attribute them.

        Implemented as a single GROUP BY so the team endpoint does not run
        one query per agent.
        """
        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT COALESCE(agent_profile_name, 'default') AS agent,
                       COUNT(*) AS trace_count,
                       MAX(created_at) AS last_created_at
                FROM traces
                GROUP BY COALESCE(agent_profile_name, 'default')
                """
            )
            return {
                row["agent"]: (int(row["trace_count"]), row["last_created_at"])
                for row in cursor.fetchall()
            }

    def list_traces_for_agent(self, name: str, *, limit: int = 10) -> list[TraceRecord]:
        """Return the most recent traces for one agent, newest first.

        Traces with a NULL ``agent_profile_name`` are matched under the
        bucket name ``"default"`` so the dashboard's ``default`` agent
        surfaces unattributed runs.
        """
        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT trace_id, created_at, provider, model, prompt,
                       response_text, tool_uses, usage, latency_ms,
                       status, error_message, parent_trace_id, agent_profile_name
                FROM traces
                WHERE COALESCE(agent_profile_name, 'default') = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (name, limit),
            )
            return [self._row_to_trace(row) for row in cursor.fetchall()]

    def count_traces(self) -> int:
        """Return the total number of trace rows."""
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM traces").fetchone()
            return int(row["n"]) if row is not None else 0

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
                    memory_scope, color, description, soul_path,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    system_prompt = excluded.system_prompt,
                    default_model = excluded.default_model,
                    allowed_tools = excluded.allowed_tools,
                    memory_scope = excluded.memory_scope,
                    color = excluded.color,
                    description = excluded.description,
                    soul_path = excluded.soul_path,
                    updated_at = excluded.updated_at
                """,
                (
                    profile.name,
                    profile.system_prompt,
                    profile.default_model,
                    allowed_tools_json,
                    profile.memory_scope,
                    profile.color,
                    profile.description,
                    profile.soul_path,
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

    def load_profile_icase(self, slug: str) -> AgentProfile | None:
        """Return one agent profile by case-insensitive name match, or None."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM agent_profiles WHERE LOWER(name) = LOWER(?)", (slug,)
            ).fetchone()
            return self._row_to_profile(row) if row is not None else None

    def save_task(self, task: TaskRecord) -> None:
        """Insert a task row. task_id must be unique (used for demo seed idempotency).

        ``created_at`` and ``updated_at`` are always set to the current server
        time regardless of the values on the passed TaskRecord. The TaskRecord
        fields are output-only: they are populated on rows returned by
        ``list_tasks`` and ``_row_to_task``, but callers must not rely on
        them being preserved on insert. Demo seed tasks pass empty strings for
        both fields and rely on this server-assignment behavior.
        """
        now = _now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO tasks (
                    task_id, title, description, status,
                    agent_profile_name, trace_id, is_demo_seed,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.task_id,
                    task.title,
                    task.description,
                    task.status,
                    task.agent_profile_name,
                    task.trace_id,
                    1 if task.is_demo_seed else 0,
                    now,
                    now,
                ),
            )

    def list_tasks(self, *, status: str | None = None, limit: int = 100) -> list[TaskRecord]:
        """Return tasks ordered by creation time, newest first. Optionally filtered by status."""
        with self._connect() as conn:
            if status:
                cursor = conn.execute(
                    "SELECT * FROM tasks WHERE status = ? ORDER BY id DESC LIMIT ?",
                    (status, limit),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM tasks ORDER BY id DESC LIMIT ?",
                    (limit,),
                )
            return [self._row_to_task(row) for row in cursor.fetchall()]

    def delete_task(self, task_id: str) -> bool:
        """Delete one task by task_id. Returns True if a row was deleted."""
        with self._connect() as conn:
            result = conn.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
            return result.rowcount > 0

    def delete_trace(self, trace_id: str) -> bool:
        """Delete one trace by trace_id. Returns True if a row was deleted."""
        with self._connect() as conn:
            result = conn.execute("DELETE FROM traces WHERE trace_id = ?", (trace_id,))
            return result.rowcount > 0

    def save_discord_feedback(
        self,
        *,
        message_id: str,
        channel_id: str,
        user_id: str,
        emoji: str,
        positive: bool,
    ) -> None:
        """Persist one Discord reaction feedback row.

        Uses INSERT OR REPLACE so the last reaction from a given user on a
        given message wins (last-reaction-wins semantics). The UNIQUE constraint
        on (message_id, user_id) ensures exactly one row per user per message.
        """
        now = _now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO discord_feedback
                    (message_id, channel_id, user_id, emoji, positive, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    channel_id,
                    user_id,
                    emoji,
                    1 if positive else 0,
                    now,
                ),
            )

    def update_task_status(self, task_id: str, status: str) -> bool:
        """Update the status of one task. Returns True if a row was updated."""
        now = _now_iso()
        with self._connect() as conn:
            result = conn.execute(
                "UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ?",
                (status, now, task_id),
            )
            return result.rowcount > 0

    def upsert_integration_verification(
        self,
        integration_id: str,
        key_hash: str,
        *,
        verified: bool,
    ) -> None:
        """Upsert key hash and verified state for an integration.

        A key hash change resets verified to False and clears verified_at,
        enforcing re-verification when a new credential is saved (VERIFY-03).
        A same-hash write applies the passed verified value without overriding
        an existing verified=1 state with False if the hash matches.
        All SQL uses parameterized binding to prevent injection (T-62-01).
        """
        now = _now_iso()
        verified_at = now if verified else None
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO integration_verification_state
                    (integration_id, key_hash, verified, verified_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(integration_id) DO UPDATE SET
                    key_hash    = excluded.key_hash,
                    verified    = CASE WHEN excluded.key_hash != key_hash THEN 0
                                       ELSE MAX(excluded.verified, verified) END,
                    verified_at = CASE WHEN excluded.key_hash != key_hash THEN NULL
                                       WHEN excluded.verified = 1 THEN excluded.verified_at
                                       ELSE verified_at END,
                    updated_at  = excluded.updated_at
                """,
                (integration_id, key_hash, int(verified), verified_at, now),
            )

    def get_integration_verification(self, integration_id: str) -> dict | None:
        """Return the verification row for an integration, or None if not found.

        Keys: integration_id, key_hash, verified (int 0/1), verified_at (str|None),
        updated_at (str).
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT integration_id, key_hash, verified, verified_at, updated_at "
                "FROM integration_verification_state WHERE integration_id = ?",
                (integration_id,),
            ).fetchone()
            if row is None:
                return None
            return dict(row)

    # Allowlist of tables and their cursor columns valid for list_rows_after.
    # These are the only sync-eligible tables for the Supabase push-only sync
    # (Phase 65 - SUPA-01). table_name and cursor_col are interpolated into SQL
    # so they must be validated before use (T-65-01).
    _SYNC_ALLOWLIST: ClassVar[dict[str, str]] = {
        "traces": "created_at",
        "note_writes": "created_at",
        "llm_calls": "created_at",
        "tool_invocations": "created_at",
        "discord_feedback": "created_at",
        "agent_profiles": "updated_at",
        "tasks": "updated_at",
    }

    def get_sync_cursor(self, table_name: str) -> str:
        """Return the stored cursor value for a table, or the epoch default when absent."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT cursor_value FROM sync_cursors WHERE table_name = ?",
                (table_name,),
            ).fetchone()
        return row["cursor_value"] if row is not None else "1970-01-01T00:00:00.000000Z"

    def upsert_sync_cursor(self, table_name: str, cursor_value: str) -> None:
        """Insert or update the cursor value for a table."""
        now = _now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sync_cursors (table_name, cursor_value, last_synced_at)
                VALUES (?, ?, ?)
                ON CONFLICT(table_name) DO UPDATE SET
                    cursor_value   = excluded.cursor_value,
                    last_synced_at = excluded.last_synced_at
                """,
                (table_name, cursor_value, now),
            )

    def list_rows_after(
        self,
        table_name: str,
        cursor_col: str,
        cursor_value: str,
        *,
        id_after: int = 0,
        limit: int = 500,
    ) -> list[dict]:
        """Return rows newer than a (cursor_value, id_after) keyset, oldest first.

        Rows are ordered by cursor_col then by the surrogate id so the keyset is
        strictly increasing and ties on cursor_col never get skipped across page
        boundaries (Phase 65 CR-02). A row qualifies when its cursor_col is greater
        than cursor_value, or equal to cursor_value with an id greater than id_after.

        With the defaults (id_after=0, cursor_value at the epoch) behavior matches
        the original strict-greater-than scan for existing callers and tests.

        table_name and cursor_col are interpolated into the SQL query and must
        come from the sync allowlist (_SYNC_ALLOWLIST). cursor_value and id_after
        are passed as bound parameters. Raises ValueError for any table or column
        outside the allowlist (T-65-01). LIMIT caps the result set per page (T-65-02).
        """
        if table_name not in self._SYNC_ALLOWLIST:
            raise ValueError(
                f"table_name {table_name!r} is not in the sync allowlist; "
                f"allowed: {sorted(self._SYNC_ALLOWLIST)}"
            )
        allowed_col = self._SYNC_ALLOWLIST[table_name]
        if cursor_col != allowed_col:
            raise ValueError(
                f"cursor_col {cursor_col!r} is not valid for table {table_name!r}; "
                f"expected {allowed_col!r}"
            )
        query = (
            f"SELECT * FROM {table_name} "
            f"WHERE ({cursor_col} > ?) OR ({cursor_col} = ? AND id > ?) "
            f"ORDER BY {cursor_col} ASC, id ASC LIMIT ?"
        )
        with self._connect() as conn:
            rows = conn.execute(query, (cursor_value, cursor_value, id_after, limit)).fetchall()
        return [dict(row) for row in rows]

    # Schedule accessors (Phase 66 - REMOTE-05). The scheduler reads/writes the
    # schedules table; the CLI manages schedule CRUD (D-07). Column names are
    # static literals and all values are passed as bound parameters.

    _SCHEDULE_UPDATABLE: ClassVar[frozenset[str]] = frozenset(
        {
            "cron_expression",
            "agent_profile_name",
            "prompt",
            "enabled",
            "catch_up_policy",
            "last_run_at",
            "next_run_at",
            "last_trace_id",
        }
    )

    def create_schedule(
        self,
        name: str,
        *,
        cron_expression: str,
        agent_profile_name: str,
        prompt: str,
        catch_up_policy: str = "coalesce",
        next_run_at: str | None = None,
    ) -> None:
        """Create a schedule. Raises sqlite3.IntegrityError if the name already exists."""
        now = _now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO schedules (
                    name, cron_expression, agent_profile_name, prompt,
                    catch_up_policy, next_run_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    cron_expression,
                    agent_profile_name,
                    prompt,
                    catch_up_policy,
                    next_run_at,
                    now,
                    now,
                ),
            )

    def list_schedules(self) -> list[ScheduleRecord]:
        """Return every schedule, oldest first."""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM schedules ORDER BY id ASC").fetchall()
        return [self._row_to_schedule(row) for row in rows]

    def list_enabled_schedules(self) -> list[ScheduleRecord]:
        """Return only schedules where enabled = 1, oldest first."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM schedules WHERE enabled = 1 ORDER BY id ASC"
            ).fetchall()
        return [self._row_to_schedule(row) for row in rows]

    def get_schedule(self, name: str) -> ScheduleRecord | None:
        """Return a single schedule by name, or None when absent."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM schedules WHERE name = ?", (name,)).fetchone()
        return self._row_to_schedule(row) if row is not None else None

    def update_schedule(self, name: str, **fields: Any) -> None:
        """Update one or more updatable columns on a schedule by name.

        Only columns in _SCHEDULE_UPDATABLE may be set; unknown keys raise
        ValueError so a caller typo never silently no-ops. updated_at is
        always refreshed. Column names come from the static allowlist, never
        from caller-supplied strings interpolated unchecked.
        """
        unknown = set(fields) - self._SCHEDULE_UPDATABLE
        if unknown:
            raise ValueError(f"cannot update schedule columns: {sorted(unknown)}")
        if not fields:
            return
        assignments = ", ".join(f"{col} = ?" for col in fields)
        values = list(fields.values())
        values.append(_now_iso())
        values.append(name)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE schedules SET {assignments}, updated_at = ? WHERE name = ?",
                values,
            )

    def delete_schedule(self, name: str) -> bool:
        """Delete a schedule by name. Returns True when a row was removed."""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM schedules WHERE name = ?", (name,))
        return cur.rowcount > 0

    def set_schedule_enabled(self, name: str, enabled: bool) -> None:
        """Enable or disable a schedule by name."""
        self.update_schedule(name, enabled=1 if enabled else 0)

    def update_schedule_run(
        self,
        name: str,
        *,
        last_run_at: str,
        next_run_at: str | None,
        last_trace_id: str | None,
    ) -> None:
        """Persist run state for a schedule after (or before) firing it."""
        self.update_schedule(
            name,
            last_run_at=last_run_at,
            next_run_at=next_run_at,
            last_trace_id=last_trace_id,
        )

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
            color=row["color"],
            description=row["description"],
            soul_path=row["soul_path"],
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
    def _row_to_task(row: sqlite3.Row) -> TaskRecord:
        return TaskRecord(
            task_id=row["task_id"],
            title=row["title"],
            description=row["description"],
            status=row["status"],
            agent_profile_name=row["agent_profile_name"],
            trace_id=row["trace_id"],
            is_demo_seed=bool(row["is_demo_seed"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_schedule(row: sqlite3.Row) -> ScheduleRecord:
        return ScheduleRecord(
            id=row["id"],
            name=row["name"],
            cron_expression=row["cron_expression"],
            agent_profile_name=row["agent_profile_name"],
            prompt=row["prompt"],
            enabled=row["enabled"],
            catch_up_policy=row["catch_up_policy"],
            last_run_at=row["last_run_at"],
            next_run_at=row["next_run_at"],
            last_trace_id=row["last_trace_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
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
