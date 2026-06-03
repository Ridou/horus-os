"""Tests for the shell_invocations audit table (Phase 75, SHELL-02).

The table is additive within schema v13: it is created by CREATE TABLE IF NOT
EXISTS on a fresh init and on an older fixture upgrade, with no extra
SCHEMA_VERSION change beyond the v12 -> v13 bump that introduced it.
record_shell_invocation / list_shell_invocations mirror the
record_note_write / list_note_writes pair exactly.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from horus_os.storage import SCHEMA_VERSION, Database
from horus_os.types import ShellInvocation


def _table_exists(path: str, table_name: str) -> bool:
    conn = sqlite3.connect(path)
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    conn.close()
    return row is not None


def test_fresh_init_creates_shell_invocations_table(tmp_path: Path) -> None:
    db_path = tmp_path / "horus.sqlite"
    db = Database(db_path)
    db.init()
    assert _table_exists(str(db_path), "shell_invocations")


def test_shell_invocations_table_added_on_v11_upgrade_without_schema_bump(
    tmp_path: Path,
) -> None:
    """A v11 fixture gains shell_invocations on init() and lands at the current schema (13)."""
    db_path = str(tmp_path / "v11.db")
    db = Database(db_path)
    db.init()

    # Simulate a pre-shell-table v11 installation: roll the version back and
    # drop the additive table so init() must recreate it.
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE schema_version SET version = 11")
    conn.execute("DROP TABLE IF EXISTS shell_invocations")
    conn.commit()
    conn.close()
    assert not _table_exists(db_path, "shell_invocations")

    db.init()

    assert _table_exists(db_path, "shell_invocations")
    # The table is additive within v13; the version lands at the current pin.
    conn = sqlite3.connect(db_path)
    version = conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()[0]
    conn.close()
    assert version == SCHEMA_VERSION == 13


def test_record_and_list_round_trip(tmp_path: Path) -> None:
    db = Database(tmp_path / "horus.sqlite")
    db.init()

    invocation_id = db.record_shell_invocation(
        command="echo hello",
        exit_code=0,
        stdout_truncated="hello\n",
        working_directory=str(tmp_path / "shell"),
        trace_id="trace-1",
    )
    assert isinstance(invocation_id, str)
    assert len(invocation_id) == 32  # uuid4 hex

    rows = db.list_shell_invocations()
    assert len(rows) == 1
    row = rows[0]
    assert isinstance(row, ShellInvocation)
    assert row.invocation_id == invocation_id
    assert row.command == "echo hello"
    assert row.exit_code == 0
    assert row.stdout_truncated == "hello\n"
    assert row.working_directory == str(tmp_path / "shell")
    assert row.trace_id == "trace-1"
    assert row.created_at.endswith("Z")


def test_list_returns_newest_first(tmp_path: Path) -> None:
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    db.record_shell_invocation(
        command="first", exit_code=0, stdout_truncated="", working_directory="."
    )
    db.record_shell_invocation(
        command="second", exit_code=0, stdout_truncated="", working_directory="."
    )

    rows = db.list_shell_invocations()
    assert [r.command for r in rows] == ["second", "first"]


def test_timeout_run_records_null_exit_code(tmp_path: Path) -> None:
    """A timed-out run is recorded with exit_code None (SHELL-02)."""
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    db.record_shell_invocation(
        command="sleep 99",
        exit_code=None,
        stdout_truncated="",
        working_directory=".",
    )
    rows = db.list_shell_invocations()
    assert rows[0].exit_code is None
