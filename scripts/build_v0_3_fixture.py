"""Rebuild tests/fixtures/v0_3_database.sqlite3 deterministically.

The fixture pins the v0.3 schema (schema_version = 4) and a small
canned data set: two traces rows (one with a non-trivial usage JSON
blob, one with empty usage), one note_writes row, and the default
agent_profile row. Phase 32's migration test (test_storage.py) copies
this fixture to a tmp directory, runs Database.init() on the copy, and
asserts the v4 to v5 upgrade is additive and preserves old data
(PITFALLS.md Pitfall 11).

Usage:
    python scripts/build_v0_3_fixture.py

Re-run only if v0.3 schema ever needs a re-pin (it should not; v0.3
shipped on 2026-05-24). The script writes deterministic bytes: same
inputs always produce the same fixture, so the committed checksum
stays stable across regenerations.

The v0.3 SCHEMA_SQL is inlined below to keep the regenerator
independent of any future storage.py refactor. The bytes here MUST
match the schema as it stood when v0.3 was tagged.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "v0_3_database.sqlite3"

# Deterministic timestamps so the fixture bytes do not drift between regenerations.
FIXED_TS = "2026-05-24T00:00:00Z"

# Inlined copy of the v4 SCHEMA_SQL as it stood at the v0.3 tag. Do not change.
V4_SCHEMA_SQL = """
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
    agent_profile_name  TEXT
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
"""


def build() -> None:
    """Rebuild the v0.3 fixture at FIXTURE_PATH from scratch."""
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
        conn.executescript(V4_SCHEMA_SQL)
        conn.execute("INSERT INTO schema_version (version) VALUES (4)")
        conn.execute(
            """
            INSERT INTO traces (
                trace_id, created_at, provider, model, prompt,
                response_text, tool_uses, usage, latency_ms,
                status, error_message, parent_trace_id, agent_profile_name
            ) VALUES (
                'fixture-trace-001', ?, 'anthropic', 'claude-sonnet-4-6',
                'test prompt one', 'response one', '[]',
                '{"input_tokens": 100, "output_tokens": 50}', 250,
                'success', NULL, NULL, 'default'
            )
            """,
            (FIXED_TS,),
        )
        conn.execute(
            """
            INSERT INTO traces (
                trace_id, created_at, provider, model, prompt,
                response_text, tool_uses, usage, latency_ms,
                status, error_message, parent_trace_id, agent_profile_name
            ) VALUES (
                'fixture-trace-002', ?, 'gemini', 'gemini-2.0-flash',
                'test prompt two', 'response two', '[]', '{}', 300,
                'success', NULL, NULL, 'default'
            )
            """,
            (FIXED_TS,),
        )
        conn.execute(
            """
            INSERT INTO note_writes (
                write_id, created_at, operation, rel_path,
                bytes_before, bytes_after, content, trace_id
            ) VALUES (
                'fixture-write-001', ?, 'create', 'notes/example.md',
                0, 12, 'fixture body', 'fixture-trace-001'
            )
            """,
            (FIXED_TS,),
        )
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
