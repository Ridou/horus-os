"""MIG-05 coverage: v5 -> v6 schema upgrade against the v0.4 fixture.

Asserts:
  - The v0.4 fixture is pinned at schema_version=5 (sanity).
  - Running ``Database.init()`` upgrades the fixture to v6.
  - The three new tables exist (plugins, plugin_capabilities, plugin_status)
    with the expected column shape.
  - Both new NULLABLE plugin_name columns exist on llm_calls and
    tool_invocations.
  - The idx_tool_invocations_plugin index exists.
  - Pre-migration rows are byte-identical after the upgrade (Pitfall 9).
  - plugin_name is NULL on every pre-migration row.
  - Running init() twice is a no-op (idempotent).
  - A fresh database initializes at v6 with the same shape.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from horus_os.storage import SCHEMA_VERSION, Database

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "v0_4_database.sqlite3"

# Pre-migration v5 table list (sanity-check the fixture is what we think it is).
V5_TABLES = {
    "traces",
    "llm_calls",
    "tool_invocations",
    "note_writes",
    "agent_profiles",
    "schema_version",
}

# Tables that pre-existed in v5 and must survive byte-identically.
ROW_PRESERVED_TABLES = (
    "traces",
    "note_writes",
    "agent_profiles",
)
# Tables with a new plugin_name column added in v6 — preservation is
# verified via SELECT of every column EXCEPT plugin_name.
ROW_PRESERVED_TABLES_EXCEPT_PLUGIN_NAME = (
    "llm_calls",
    "tool_invocations",
)


def _hash_rows(conn: sqlite3.Connection, table: str, exclude_cols: tuple[str, ...] = ()) -> str:
    """Deterministically hash all rows in a table.

    Columns in ``exclude_cols`` are dropped from the comparison so the
    added-in-v6 plugin_name column does not invalidate the equality
    check between pre- and post-migration row contents.
    """
    cols = [
        row[1] for row in conn.execute(f"PRAGMA table_info({table})") if row[1] not in exclude_cols
    ]
    col_list = ", ".join(cols)
    rows = conn.execute(f"SELECT {col_list} FROM {table} ORDER BY rowid").fetchall()
    payload = json.dumps([list(r) for r in rows], sort_keys=True, default=str).encode()
    return hashlib.sha256(payload).hexdigest()


@pytest.fixture
def upgraded_db(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """Copy fixture to tmp_path, snapshot pre-row hashes, upgrade, return both."""
    dest = tmp_path / "db.sqlite3"
    shutil.copy(FIXTURE_PATH, dest)

    # Pre-upgrade: snapshot.
    pre_hashes: dict[str, str] = {}
    with sqlite3.connect(str(dest)) as conn:
        # Sanity: fixture is v5.
        v = conn.execute("SELECT version FROM schema_version").fetchone()[0]
        assert v == 5, f"fixture must be pinned at v5; got {v}"
        for tbl in ROW_PRESERVED_TABLES:
            pre_hashes[tbl] = _hash_rows(conn, tbl)
        for tbl in ROW_PRESERVED_TABLES_EXCEPT_PLUGIN_NAME:
            # No plugin_name to exclude pre-upgrade — same hash with empty exclude.
            pre_hashes[tbl] = _hash_rows(conn, tbl)

    # Upgrade.
    db = Database(dest)
    db.init()

    return dest, pre_hashes


# --- Sanity / shape --------------------------------------------------------


def test_schema_version_constant_is_six() -> None:
    assert SCHEMA_VERSION == 6


def test_fixture_upgrades_cleanly(upgraded_db: tuple[Path, dict[str, str]]) -> None:
    db_path, _ = upgraded_db
    with sqlite3.connect(str(db_path)) as conn:
        v = conn.execute("SELECT version FROM schema_version").fetchone()[0]
        assert v == 6


def test_new_tables_exist(upgraded_db: tuple[Path, dict[str, str]]) -> None:
    db_path, _ = upgraded_db
    expected = {"plugins", "plugin_capabilities", "plugin_status"}
    with sqlite3.connect(str(db_path)) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN (?, ?, ?)",
            ("plugins", "plugin_capabilities", "plugin_status"),
        ).fetchall()
        found = {r[0] for r in rows}
    assert found == expected


def test_new_tables_have_correct_columns(upgraded_db: tuple[Path, dict[str, str]]) -> None:
    db_path, _ = upgraded_db
    expected_columns: dict[str, set[str]] = {
        "plugins": {
            "name",
            "version",
            "manifest_hash",
            "enabled",
            "installed_at",
            "source",
        },
        "plugin_capabilities": {
            "plugin_name",
            "plugin_version",
            "capability",
            "manifest_hash",
            "state",
            "granted_at",
        },
        "plugin_status": {
            "plugin_name",
            "status",
            "error_phase",
            "error_message",
            "last_seen",
        },
    }
    with sqlite3.connect(str(db_path)) as conn:
        for table, expected in expected_columns.items():
            cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            assert cols == expected, f"{table} columns mismatch: expected {expected}, got {cols}"


def test_new_columns_exist_on_llm_calls(upgraded_db: tuple[Path, dict[str, str]]) -> None:
    db_path, _ = upgraded_db
    with sqlite3.connect(str(db_path)) as conn:
        info = list(conn.execute("PRAGMA table_info(llm_calls)"))
    plugin_name_rows = [r for r in info if r[1] == "plugin_name"]
    assert len(plugin_name_rows) == 1
    row = plugin_name_rows[0]
    # PRAGMA table_info columns: (cid, name, type, notnull, dflt_value, pk)
    assert row[2].upper() == "TEXT"
    assert row[3] == 0, "plugin_name must be NULLABLE (notnull=0)"


def test_new_columns_exist_on_tool_invocations(upgraded_db: tuple[Path, dict[str, str]]) -> None:
    db_path, _ = upgraded_db
    with sqlite3.connect(str(db_path)) as conn:
        info = list(conn.execute("PRAGMA table_info(tool_invocations)"))
    plugin_name_rows = [r for r in info if r[1] == "plugin_name"]
    assert len(plugin_name_rows) == 1
    row = plugin_name_rows[0]
    assert row[2].upper() == "TEXT"
    assert row[3] == 0, "plugin_name must be NULLABLE (notnull=0)"


def test_new_index_exists(upgraded_db: tuple[Path, dict[str, str]]) -> None:
    db_path, _ = upgraded_db
    with sqlite3.connect(str(db_path)) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
            ("idx_tool_invocations_plugin",),
        ).fetchall()
    assert len(rows) == 1


# --- Row preservation (Pitfall 9) ------------------------------------------


def test_existing_rows_preserved_byte_identical(upgraded_db: tuple[Path, dict[str, str]]) -> None:
    db_path, pre_hashes = upgraded_db
    with sqlite3.connect(str(db_path)) as conn:
        for tbl in ROW_PRESERVED_TABLES:
            post_hash = _hash_rows(conn, tbl)
            assert post_hash == pre_hashes[tbl], f"{tbl} rows changed during v5 -> v6 migration"
        for tbl in ROW_PRESERVED_TABLES_EXCEPT_PLUGIN_NAME:
            # Exclude the new column for fair comparison.
            post_hash = _hash_rows(conn, tbl, exclude_cols=("plugin_name",))
            assert post_hash == pre_hashes[tbl], (
                f"{tbl} pre-existing column values changed during v5 -> v6 migration"
            )


def test_plugin_name_is_null_on_pre_migration_rows(
    upgraded_db: tuple[Path, dict[str, str]],
) -> None:
    db_path, _ = upgraded_db
    with sqlite3.connect(str(db_path)) as conn:
        rows = conn.execute("SELECT plugin_name FROM llm_calls").fetchall()
        assert len(rows) >= 1, "fixture must seed at least one llm_calls row"
        assert all(r[0] is None for r in rows)
        rows = conn.execute("SELECT plugin_name FROM tool_invocations").fetchall()
        assert len(rows) >= 1, "fixture must seed at least one tool_invocations row"
        assert all(r[0] is None for r in rows)


# --- Idempotency -----------------------------------------------------------


def test_idempotent_replay(upgraded_db: tuple[Path, dict[str, str]]) -> None:
    db_path, _ = upgraded_db
    # Re-run init on the already-upgraded DB; should be a no-op.
    db = Database(db_path)
    db.init()
    with sqlite3.connect(str(db_path)) as conn:
        v = conn.execute("SELECT version FROM schema_version").fetchone()[0]
        assert v == 6
        # No spurious rows in any of the new tables.
        for tbl in ("plugins", "plugin_capabilities", "plugin_status"):
            n = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
            assert n == 0, f"{tbl} should be empty after idempotent replay"
        # Schema_version still has exactly one row.
        n = conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]
        assert n == 1


# --- Fresh DB path ---------------------------------------------------------


def test_fresh_database_initializes_at_v6(tmp_path: Path) -> None:
    """A fresh DB (no schema_version row) lands at v6 directly via SCHEMA_SQL."""
    fresh = tmp_path / "fresh.sqlite3"
    db = Database(fresh)
    db.init()
    with sqlite3.connect(str(fresh)) as conn:
        v = conn.execute("SELECT version FROM schema_version").fetchone()[0]
        assert v == 6
        tables = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {"plugins", "plugin_capabilities", "plugin_status"}.issubset(tables)
        # plugin_name columns exist on both observability tables.
        llm_cols = {r[1] for r in conn.execute("PRAGMA table_info(llm_calls)")}
        assert "plugin_name" in llm_cols
        tool_cols = {r[1] for r in conn.execute("PRAGMA table_info(tool_invocations)")}
        assert "plugin_name" in tool_cols
        # The new index exists.
        idx_rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
            ("idx_tool_invocations_plugin",),
        ).fetchall()
        assert len(idx_rows) == 1


def test_fresh_database_path_matches_upgraded_database_path(tmp_path: Path) -> None:
    """The end-state shape of a fresh v6 DB equals an upgraded v5 -> v6 DB."""
    upgraded = tmp_path / "upgraded.sqlite3"
    shutil.copy(FIXTURE_PATH, upgraded)
    Database(upgraded).init()

    fresh = tmp_path / "fresh.sqlite3"
    Database(fresh).init()

    with sqlite3.connect(str(upgraded)) as u_conn, sqlite3.connect(str(fresh)) as f_conn:
        u_tables = {
            r[0] for r in u_conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        f_tables = {
            r[0] for r in f_conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert u_tables == f_tables

        for tbl in (
            "plugins",
            "plugin_capabilities",
            "plugin_status",
            "llm_calls",
            "tool_invocations",
        ):
            u_cols = {r[1] for r in u_conn.execute(f"PRAGMA table_info({tbl})")}
            f_cols = {r[1] for r in f_conn.execute(f"PRAGMA table_info({tbl})")}
            assert u_cols == f_cols, f"{tbl} columns diverge: upgraded={u_cols}, fresh={f_cols}"


# --- Pitfall 9 negative guards --------------------------------------------


def test_no_drop_or_rename_in_migration_block() -> None:
    """The v5 -> v6 migration block must be additive only."""
    storage_src = (
        Path(__file__).resolve().parent.parent.parent / "src" / "horus_os" / "storage.py"
    ).read_text()
    # Extract the v5 -> v6 block: from the `# v5 -> v6` comment marker until
    # the next un-indented closing of init() / next top-level statement.
    start = storage_src.find("# v5 -> v6")
    assert start != -1, "v5 -> v6 migration block not found in storage.py"
    end = storage_src.find("# The parent_trace_id index", start)
    assert end != -1
    block = storage_src[start:end]
    # Strip comment lines so prose discussion of "DROP" / "RENAME" doesn't
    # false-positive the grep.
    code_lines = [line for line in block.splitlines() if not line.lstrip().startswith("#")]
    code = "\n".join(code_lines)
    assert "DROP" not in code.upper(), "v5 -> v6 block must not contain DROP"
    assert "RENAME" not in code.upper(), "v5 -> v6 block must not contain RENAME"
    assert "NOT NULL" not in code.upper(), "v5 -> v6 block must not ADD COLUMN with NOT NULL"
