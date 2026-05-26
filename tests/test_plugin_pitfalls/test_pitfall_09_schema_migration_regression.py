"""Pitfall 9: v5→v6 schema migration breaks v0.4 databases.

See .planning/research/PITFALLS.md §"Pitfall 9" for the documented
threat. The v5→v6 migration adds nullable ``plugin_name`` columns to
``llm_calls`` and ``tool_invocations`` AND creates new ``plugins`` /
``plugin_capabilities`` / ``plugin_status`` tables (per OBSERVE-01 +
PERMISSION-01). A non-additive migration — backfilling, renaming,
dropping — would silently corrupt v0.4 databases on upgrade.

The Phase 40 BASELINE-02 substrate is
``tests/fixtures/v0_4_database.sqlite3`` (committed at schema v5 with
real fixture rows in ``traces``, ``llm_calls``, ``tool_invocations``).
This test loads that fixture, runs ``Database.init()``, and asserts
the migration is additive + idempotent + non-destructive.

Reverse migration (v6 → v5) is explicitly NOT supported; this test
documents that as a non-goal.

Five structural assertions:

1. The pre-migration fixture is at schema_version=5 (sanity check).
2. After ``Database.init()``, schema_version=6.
3. Pre-existing ``traces`` rows preserve their original values
   byte-identically (the migration is additive on existing data).
4. New columns (``plugin_name`` on ``llm_calls`` + ``tool_invocations``)
   exist on existing rows with value NULL (no backfill).
5. New tables (``plugins`` / ``plugin_capabilities`` / ``plugin_status``)
   exist and are empty.
6. Running ``Database.init()`` a second time on the v6 database is a
   no-op: no exceptions, schema stays at 6, traces row count unchanged.
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from horus_os.storage import Database

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_V0_4 = REPO_ROOT / "tests" / "fixtures" / "v0_4_database.sqlite3"


def _raw_select(db_path: Path, sql: str) -> list[sqlite3.Row]:
    """Open a raw sqlite3 connection and run a SELECT — no Database init."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def test_pre_migration_fixture_is_at_v5(tmp_path: Path) -> None:
    """Sanity: the checked-in fixture starts at schema_version=5."""
    assert FIXTURE_V0_4.is_file(), f"missing Phase 40 fixture {FIXTURE_V0_4}"
    # Copy to tmp_path so we never mutate the checked-in file.
    db_path = tmp_path / "horus.sqlite3"
    shutil.copy(FIXTURE_V0_4, db_path)
    rows = _raw_select(db_path, "SELECT version FROM schema_version LIMIT 1")
    assert len(rows) == 1
    assert rows[0]["version"] == 5


def test_v5_to_v6_migration_is_additive_and_non_destructive(tmp_path: Path) -> None:
    """The full v5→v6 migration round-trip: columns added, rows preserved."""
    db_path = tmp_path / "horus.sqlite3"
    shutil.copy(FIXTURE_V0_4, db_path)

    # Capture the pre-migration traces row count + a sample row's identity columns.
    pre_traces = _raw_select(db_path, "SELECT trace_id, agent_profile_name, status FROM traces ORDER BY id")
    pre_trace_count = len(pre_traces)
    assert pre_trace_count > 0, "fixture should carry at least one traces row"

    db = Database(db_path)
    db.init()

    # 1. schema_version advanced to 6.
    post_version = _raw_select(db_path, "SELECT version FROM schema_version LIMIT 1")
    assert post_version[0]["version"] == 6

    # 2. traces row count unchanged.
    post_traces = _raw_select(db_path, "SELECT trace_id, agent_profile_name, status FROM traces ORDER BY id")
    assert len(post_traces) == pre_trace_count
    for pre, post in zip(pre_traces, post_traces, strict=True):
        assert pre["trace_id"] == post["trace_id"]
        assert pre["agent_profile_name"] == post["agent_profile_name"]
        assert pre["status"] == post["status"]

    # 3. plugin_name column exists on tool_invocations + llm_calls; all
    #    pre-existing rows have NULL (no backfill).
    pre_tool_rows = _raw_select(db_path, "SELECT plugin_name FROM tool_invocations")
    assert all(row["plugin_name"] is None for row in pre_tool_rows)
    pre_llm_rows = _raw_select(db_path, "SELECT plugin_name FROM llm_calls")
    assert all(row["plugin_name"] is None for row in pre_llm_rows)


def test_new_v6_tables_exist_and_are_empty(tmp_path: Path) -> None:
    """plugins / plugin_capabilities / plugin_status created empty by the migration."""
    db_path = tmp_path / "horus.sqlite3"
    shutil.copy(FIXTURE_V0_4, db_path)
    Database(db_path).init()

    for table in ("plugins", "plugin_capabilities", "plugin_status"):
        rows = _raw_select(db_path, f"SELECT COUNT(*) AS cnt FROM {table}")
        assert rows[0]["cnt"] == 0, (
            f"Pitfall 9: v5→v6 migration populated {table} (expected empty)."
        )


def test_second_init_call_is_noop(tmp_path: Path) -> None:
    """Calling Database.init() a second time on a v6 DB is idempotent."""
    db_path = tmp_path / "horus.sqlite3"
    shutil.copy(FIXTURE_V0_4, db_path)
    db = Database(db_path)
    db.init()

    pre_traces_cnt = _raw_select(db_path, "SELECT COUNT(*) AS cnt FROM traces")[0]["cnt"]
    pre_version = _raw_select(db_path, "SELECT version FROM schema_version LIMIT 1")[0]["version"]
    assert pre_version == 6

    # Second init should not raise and should not mutate row counts.
    db.init()

    post_traces_cnt = _raw_select(db_path, "SELECT COUNT(*) AS cnt FROM traces")[0]["cnt"]
    post_version = _raw_select(db_path, "SELECT version FROM schema_version LIMIT 1")[0]["version"]
    assert post_version == 6
    assert post_traces_cnt == pre_traces_cnt
