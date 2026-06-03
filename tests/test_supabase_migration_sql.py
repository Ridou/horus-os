"""SUPA-03: Supabase migration SQL integrity checks.

These tests parse supabase/migrations/001_initial.sql with regex and assert the
hard security invariants required by SUPA-03:

- Every CREATE TABLE has a matching ALTER TABLE ... ENABLE ROW LEVEL SECURITY.
- Every table has a "service_role_only" deny-all policy.
- The check_rls_status() helper function is present for doctor --supabase.

No network, no live Supabase connection.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from horus_os.storage import SCHEMA_SQL

REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_FILE = REPO_ROOT / "supabase" / "migrations" / "001_initial.sql"

# Tables synced from local SQLite to Supabase (SYNC_TABLES in supabase_adapter.py).
SYNCED_TABLES = ("traces", "agent_profiles", "tasks")


def _read_sql() -> str:
    return MIGRATION_FILE.read_text(encoding="utf-8")


def _column_names(sql: str, table: str) -> set[str]:
    """Return the set of column names declared in a CREATE TABLE block.

    Parses only the first line of each comma-separated entry inside the
    parentheses, so a leading identifier that is a SQL keyword (PRIMARY, CHECK,
    UNIQUE, FOREIGN, CONSTRAINT) is excluded as a table-level constraint rather
    than a column.
    """
    match = re.search(
        rf"CREATE TABLE IF NOT EXISTS\s+{re.escape(table)}\s*\((.*?)\n\s*\)\s*;",
        sql,
        re.DOTALL,
    )
    if match is None:
        raise AssertionError(f"CREATE TABLE for {table!r} not found")
    body = match.group(1)
    keywords = {"PRIMARY", "CHECK", "UNIQUE", "FOREIGN", "CONSTRAINT"}
    columns: set[str] = set()
    depth = 0
    # Split top-level commas only (CHECK (...) clauses contain commas/parens).
    current: list[str] = []
    entries: list[str] = []
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            entries.append("".join(current))
            current = []
        else:
            current.append(ch)
    if current:
        entries.append("".join(current))
    for entry in entries:
        token = entry.strip().split()
        if not token:
            continue
        name = token[0]
        if name.upper() in keywords:
            continue
        columns.add(name)
    return columns


def test_migration_file_exists() -> None:
    """The migration file must exist before the other tests run."""
    assert MIGRATION_FILE.exists(), (
        f"Migration file not found: {MIGRATION_FILE}\n"
        "Run plan 03 to create supabase/migrations/001_initial.sql."
    )


def test_every_create_table_has_enable_rls() -> None:
    """Every CREATE TABLE in the migration must have ENABLE ROW LEVEL SECURITY.

    This test would fail if a new table were added without the matching
    ALTER TABLE ... ENABLE ROW LEVEL SECURITY statement (SUPA-03).
    """
    sql = _read_sql()

    tables = set(re.findall(r"CREATE TABLE IF NOT EXISTS\s+(\w+)", sql))
    rls_tables = set(re.findall(r"ALTER TABLE\s+(\w+)\s+ENABLE ROW LEVEL SECURITY", sql))

    missing = tables - rls_tables
    assert missing == set(), (
        f"Tables missing ENABLE ROW LEVEL SECURITY: {sorted(missing)}\n\n"
        "Every table in the Supabase migration must have RLS enabled so the "
        "anon key cannot read all rows when policies are absent (SUPA-03)."
    )


def test_each_table_has_deny_all_policy() -> None:
    """Every table in the migration must have a service_role_only deny-all policy."""
    sql = _read_sql()

    tables = list(re.findall(r"CREATE TABLE IF NOT EXISTS\s+(\w+)", sql))

    missing: list[str] = []
    for table in tables:
        # Look for a service_role_only policy targeting this table.
        # The pattern: CREATE POLICY "service_role_only" ON <table>
        pattern = rf'CREATE POLICY\s+"service_role_only"\s+ON\s+{re.escape(table)}'
        if not re.search(pattern, sql):
            missing.append(table)

    assert missing == [], (
        f"Tables without 'service_role_only' deny-all policy: {missing}\n\n"
        "Each table needs a deny-all policy for anon/authenticated roles so that "
        "only service_role (which has BYPASSRLS) can write (SUPA-03)."
    )


def test_check_rls_status_function_present() -> None:
    """The check_rls_status() function must be defined in the migration.

    This function is called by `horus-os doctor --supabase` via
    POST /rest/v1/rpc/check_rls_status to report per-table RLS status.
    """
    sql = _read_sql()

    assert "check_rls_status" in sql, (
        "check_rls_status() function not found in migration SQL.\n"
        "The function is required for `horus-os doctor --supabase` to report "
        "per-table RLS status via the PostgREST RPC endpoint."
    )


@pytest.mark.parametrize("table", SYNCED_TABLES)
def test_remote_columns_mirror_local_minus_id(table: str) -> None:
    """Each synced remote table must mirror the local columns minus the surrogate id.

    This is the load-bearing drift guard (Phase 65 CR-01): the sync adapter POSTs
    every local column except `id`, and PostgREST rejects any column the remote
    table does not declare. If the local SCHEMA_SQL and the Postgres migration
    ever diverge for a synced table, this test fails before a live Supabase call
    would 400.
    """
    local_cols = _column_names(SCHEMA_SQL, table) - {"id"}
    remote_cols = _column_names(_read_sql(), table)

    only_local = local_cols - remote_cols
    only_remote = remote_cols - local_cols
    assert local_cols == remote_cols, (
        f"column drift for synced table {table!r} between local SCHEMA_SQL and "
        f"supabase/migrations/001_initial.sql.\n"
        f"  local-only (missing remotely, would 400 on POST): {sorted(only_local)}\n"
        f"  remote-only (extra remote columns): {sorted(only_remote)}"
    )
