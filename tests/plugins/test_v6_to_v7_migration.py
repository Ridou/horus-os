"""v6 -> v7 schema upgrade: three NULLABLE persona columns on agent_profiles.

Mirrors the v5 -> v6 migration test shape. Asserts:
  - A database stored at version 6 whose agent_profiles lacks the new
    columns upgrades to version 7 on ``Database.init()``.
  - The three new columns (color, description, soul_path) now exist.
  - A pre-existing agent_profiles row is preserved with NULL on every new
    column (additive, no backfill).
  - A fresh database initializes at version 7 with the columns present.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from horus_os.storage import SCHEMA_VERSION, Database

# agent_profiles as it shipped at schema v6: no color / description / soul_path.
V6_AGENT_PROFILES_SQL = """
CREATE TABLE schema_version (version INTEGER NOT NULL PRIMARY KEY);
INSERT INTO schema_version (version) VALUES (6);
CREATE TABLE agent_profiles (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL UNIQUE,
    system_prompt TEXT NOT NULL DEFAULT '',
    default_model TEXT,
    allowed_tools TEXT,
    memory_scope  TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
INSERT INTO agent_profiles (name, system_prompt, created_at, updated_at)
VALUES ('legacy', 'You are a helpful assistant.', '2026-01-01T00:00:00Z',
        '2026-01-01T00:00:00Z');
"""

NEW_COLUMNS = ("color", "description", "soul_path")


def _build_v6_db(path: Path) -> None:
    with sqlite3.connect(str(path)) as conn:
        conn.executescript(V6_AGENT_PROFILES_SQL)


def test_schema_version_constant_is_eight() -> None:
    assert SCHEMA_VERSION == 13


def test_v6_database_upgrades_to_v7(tmp_path: Path) -> None:
    db_path = tmp_path / "horus.sqlite"
    _build_v6_db(db_path)

    Database(db_path).init()

    with sqlite3.connect(str(db_path)) as conn:
        version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
        assert version == 13


def test_new_columns_exist_after_upgrade(tmp_path: Path) -> None:
    db_path = tmp_path / "horus.sqlite"
    _build_v6_db(db_path)

    Database(db_path).init()

    with sqlite3.connect(str(db_path)) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(agent_profiles)")}
    for col in NEW_COLUMNS:
        assert col in cols, f"{col} missing after v6 -> v7 upgrade"


def test_existing_row_preserved_with_null_new_columns(tmp_path: Path) -> None:
    db_path = tmp_path / "horus.sqlite"
    _build_v6_db(db_path)

    Database(db_path).init()

    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT name, system_prompt, color, description, soul_path "
            "FROM agent_profiles WHERE name = 'legacy'"
        ).fetchone()
    assert row is not None
    assert row["name"] == "legacy"
    assert row["system_prompt"] == "You are a helpful assistant."
    assert row["color"] is None
    assert row["description"] is None
    assert row["soul_path"] is None


def test_fresh_database_initializes_at_v7(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.sqlite"
    Database(db_path).init()

    with sqlite3.connect(str(db_path)) as conn:
        version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
        assert version == 13
        cols = {row[1] for row in conn.execute("PRAGMA table_info(agent_profiles)")}
    for col in NEW_COLUMNS:
        assert col in cols


def test_idempotent_replay(tmp_path: Path) -> None:
    db_path = tmp_path / "horus.sqlite"
    _build_v6_db(db_path)

    db = Database(db_path)
    db.init()
    db.init()

    with sqlite3.connect(str(db_path)) as conn:
        version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
        assert version == 13
        count = conn.execute(
            "SELECT COUNT(*) FROM agent_profiles WHERE name = 'legacy'"
        ).fetchone()[0]
        assert count == 1
