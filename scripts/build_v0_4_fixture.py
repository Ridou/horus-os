"""Rebuild tests/fixtures/v0_4_database.sqlite3 deterministically.

The fixture pins the v0.4 schema (schema_version = 5) and a small
canned data set: two traces rows (one with rollup columns populated,
one with NULL rollups so the v4 -> v5 migration's NULL preservation
path stays covered), one llm_calls row, one tool_invocations row,
one note_writes row, and the default agent_profile row. Phase 41's
MIG-05 migration test consumes this fixture; Phase 49's release gate
re-asserts the upgrade path stays clean.

Usage:
    python scripts/build_v0_4_fixture.py

Re-run only if v0.4 schema ever needs a re-pin (it should not; v0.4
shipped in 2026-05). The script writes deterministic bytes: same
inputs always produce the same fixture, so the committed checksum
stays stable across regenerations.

The v0.4 SCHEMA_SQL is inlined below to keep the regenerator
independent of any future storage.py refactor. The bytes here MUST
match the schema as it stood when v0.4 was tagged: traces with the
four rollup columns added in v5, llm_calls and tool_invocations
WITHOUT plugin_name (Phase 41 adds that). Do not import the live
SCHEMA_SQL constant — it is the v6 surface after Phase 41 lands.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "v0_4_database.sqlite3"

# Deterministic timestamps so the fixture bytes do not drift between regenerations.
FIXED_TS = "2026-05-20T00:00:00Z"

# Inlined copy of the v5 SCHEMA_SQL as it stood at the v0.4 tag. Do not change.
V5_SCHEMA_SQL = """
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
CREATE INDEX IF NOT EXISTS idx_traces_parent_trace_id ON traces(parent_trace_id);

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


def build() -> None:
    """Rebuild the v0.4 fixture at FIXTURE_PATH from scratch."""
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if FIXTURE_PATH.exists():
        FIXTURE_PATH.unlink()
    # Also clean WAL and SHM sidecars left over from any prior run.
    for ext in ("-wal", "-shm"):
        sidecar = FIXTURE_PATH.with_name(FIXTURE_PATH.name + ext)
        if sidecar.exists():
            sidecar.unlink()
    # Use the default rollback-journal mode (not WAL) so the regenerated
    # file is a single self-contained sqlite3 binary with no sidecars.
    conn = sqlite3.connect(str(FIXTURE_PATH), isolation_level=None)
    try:
        conn.executescript(V5_SCHEMA_SQL)
        conn.execute("INSERT INTO schema_version (version) VALUES (5)")

        # Trace #1: full v5 surface — rollup columns populated.
        conn.execute(
            """
            INSERT INTO traces (
                trace_id, created_at, provider, model, prompt,
                response_text, tool_uses, usage, latency_ms,
                status, error_message, parent_trace_id, agent_profile_name,
                total_input_tokens, total_output_tokens, total_cost_usd,
                total_duration_ms
            ) VALUES (
                'fixture-v04-trace-001', ?, 'anthropic', 'claude-sonnet-4-6',
                'fixture prompt one', 'fixture response one', '[]',
                '{"input_tokens": 200, "output_tokens": 100}', 350,
                'success', NULL, NULL, 'default',
                200, 100, 0.0042, 350
            )
            """,
            (FIXED_TS,),
        )
        # Trace #2: rollup columns NULL — covers the v4 -> v5 NULL preservation path.
        conn.execute(
            """
            INSERT INTO traces (
                trace_id, created_at, provider, model, prompt,
                response_text, tool_uses, usage, latency_ms,
                status, error_message, parent_trace_id, agent_profile_name,
                total_input_tokens, total_output_tokens, total_cost_usd,
                total_duration_ms
            ) VALUES (
                'fixture-v04-trace-002', ?, 'gemini', 'gemini-2.0-flash',
                'fixture prompt two', 'fixture response two', '[]', '{}', 200,
                'success', NULL, NULL, 'default',
                NULL, NULL, NULL, NULL
            )
            """,
            (FIXED_TS,),
        )

        # One llm_calls row.
        conn.execute(
            """
            INSERT INTO llm_calls (
                call_id, trace_id, iteration_idx, created_at, provider, model,
                input_tokens, output_tokens, cache_creation_input_tokens,
                cache_read_input_tokens, cost_usd, pricing_missing, latency_ms,
                status, error_message, error_type
            ) VALUES (
                'fixture-v04-call-001', 'fixture-v04-trace-001', 0, ?,
                'anthropic', 'claude-sonnet-4-6',
                200, 100, 0, 0, 0.0042, 0, 350,
                'success', NULL, NULL
            )
            """,
            (FIXED_TS,),
        )

        # One tool_invocations row.
        conn.execute(
            """
            INSERT INTO tool_invocations (
                invocation_id, trace_id, parent_trace_id, created_at,
                tool_name, latency_ms, status, error_message, error_type,
                retry_count, output_size
            ) VALUES (
                'fixture-v04-inv-001', 'fixture-v04-trace-001', NULL, ?,
                'read_file', 12, 'success', NULL, NULL, 0, 245
            )
            """,
            (FIXED_TS,),
        )

        # One note_writes row.
        conn.execute(
            """
            INSERT INTO note_writes (
                write_id, created_at, operation, rel_path,
                bytes_before, bytes_after, content, trace_id
            ) VALUES (
                'fixture-v04-write-001', ?, 'create', 'notes/v04-fixture.md',
                0, 18, 'fixture v04 body', 'fixture-v04-trace-001'
            )
            """,
            (FIXED_TS,),
        )

        # Default agent profile.
        conn.execute(
            """
            INSERT INTO agent_profiles (
                name, system_prompt, default_model, allowed_tools,
                memory_scope, created_at, updated_at
            ) VALUES (
                'default', 'You are a helpful assistant.', NULL, NULL,
                NULL, ?, ?
            )
            """,
            (FIXED_TS, FIXED_TS),
        )
    finally:
        conn.close()


if __name__ == "__main__":
    build()
    print(f"wrote {FIXTURE_PATH}")
