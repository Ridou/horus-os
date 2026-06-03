"""Regression test: v12 -> v13 additive + idempotent migration.

This is the integration migration that lands the v0.8 skills system and the
gated-shell audit log on top of v0.7's v12 schema (which introduced the
`schedules` cron table). v0.7 shipped schema version 12 with `schedules`;
v0.8 adds two new tables, `skills` (Phase 74, SKILL-04) and
`shell_invocations` (Phase 75, SHELL-02), and bumps the schema to 13.

Verifies that:
- A database stamped schema_version=12 (with v0.7's schedules table and a
  pre-existing trace row) upgrades to 13 on Database.init().
- Both the skills table and the shell_invocations table are created and are
  empty after the upgrade.
- The pre-existing trace row and the v0.7 schedules table both survive the
  upgrade (additive, not destructive).
- Calling init() a second time on a v13 database is a no-op (idempotent).
- A fresh Database.init() produces schema_version=13 with skills,
  shell_invocations, AND schedules all present.
- init() creates no vectors.sqlite file: the vector index lives in a separate
  store with its own versioning, so the schema bump cannot ride into it
  (MIG-07).

SCHEMA_VERSION tripwire inventory (the v0.8 bump from 12 to 13 swept these
hardcoded current-schema-version expectation files in one commit so the suite
is never half bumped; a future bump must sweep the same set):
- src/horus_os/storage.py (SCHEMA_VERSION constant)
- scripts/install_smoke.py (SCHEMA_VERSION_EXPECTED)
- tests/test_install_smoke.py (schema_version== substring)
- tests/test_storage.py (post-init version assertions)
- tests/test_e2e_dashboard_composition.py (post-migration version assertion)
- tests/test_vector_index.py (live SCHEMA_VERSION assertion)
- tests/test_shell_invocation_storage.py (post-init version assertion)
- tests/test_v8_to_v9_migration.py
- tests/test_v9_to_v10_migration.py
- tests/test_v10_to_v11_migration.py
- tests/test_v11_to_v12_migration.py
- tests/test_v12_to_v13_migration.py (this guard)
- tests/plugins/test_v5_to_v6_migration.py
- tests/plugins/test_v6_to_v7_migration.py
- tests/docs/test_migration_v04_v05_schema_commands.py
- tests/test_plugin_pitfalls/test_pitfall_09_schema_migration_regression.py

CRITICAL: forced-down historical setup values (e.g. UPDATE schema_version SET
version = 8, or a v0.4 fixture pinned at version 5) must NOT change; only the
assertions about the CURRENT post-init schema version move to the new number.
"""

from __future__ import annotations

import sqlite3

from horus_os import storage
from horus_os.storage import SCHEMA_VERSION, Database


def _get_version(path: str) -> int:
    conn = sqlite3.connect(path)
    row = conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
    conn.close()
    return row[0] if row is not None else -1


def _table_exists(path: str, table_name: str) -> bool:
    conn = sqlite3.connect(path)
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    conn.close()
    return row is not None


def _row_count(path: str, table_name: str) -> int:
    conn = sqlite3.connect(path)
    row = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
    conn.close()
    return row[0] if row is not None else 0


class TestV12ToV13Migration:
    """Additive + idempotent migration from schema version 12 to 13."""

    def test_v12_upgrades_to_v13(self, tmp_path):
        """A v12 database gains skills + shell_invocations and version bumps to 13."""
        db_path = str(tmp_path / "v12.db")

        # Bootstrap a v13 database, then force it back to a v0.7-shaped v12: keep
        # the schedules table (v0.7 shipped it at v12), drop the v0.8 tables, and
        # stamp the version back to 12 to simulate an existing v0.7 installation.
        db = Database(db_path)
        db.init()

        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE schema_version SET version = 12")
        conn.execute("DROP TABLE IF EXISTS skills")
        conn.execute("DROP TABLE IF EXISTS shell_invocations")
        conn.commit()
        conn.close()

        assert _get_version(db_path) == 12
        assert _table_exists(db_path, "schedules"), "v0.7 schedules table must be present at v12"
        assert not _table_exists(db_path, "skills")
        assert not _table_exists(db_path, "shell_invocations")

        # Insert a trace row to verify data survives the migration.
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO traces "
            "(trace_id, created_at, provider, model, prompt) "
            "VALUES ('test-trace-v12', '2026-01-01T00:00:00Z', 'anthropic', 'claude-3', 'hello')"
        )
        # Insert a schedules row to prove the v0.7 cron data survives too.
        conn.execute(
            "INSERT INTO schedules "
            "(name, cron_expression, agent_profile_name, prompt, created_at, updated_at) "
            "VALUES ('nightly', '0 0 * * *', 'default', 'recap', "
            "'2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
        )
        conn.commit()
        conn.close()

        # Run migration.
        db.init()

        assert _get_version(db_path) == 13
        assert _table_exists(db_path, "skills"), "skills table must exist after upgrade"
        assert _row_count(db_path, "skills") == 0, "skills table must be empty after upgrade"
        assert _table_exists(db_path, "shell_invocations"), (
            "shell_invocations table must exist after upgrade"
        )
        assert _row_count(db_path, "shell_invocations") == 0, (
            "shell_invocations table must be empty after upgrade"
        )

        # Verify the pre-existing trace row survived (additive, not destructive).
        conn = sqlite3.connect(db_path)
        trace_row = conn.execute(
            "SELECT trace_id FROM traces WHERE trace_id = 'test-trace-v12'"
        ).fetchone()
        # Verify the v0.7 schedules table and its row survived.
        sched_row = conn.execute("SELECT name FROM schedules WHERE name = 'nightly'").fetchone()
        conn.close()
        assert trace_row is not None, "pre-existing trace row must survive the v12->v13 migration"
        assert _table_exists(db_path, "schedules"), "v0.7 schedules table must survive the upgrade"
        assert sched_row is not None, "pre-existing schedules row must survive the upgrade"

    def test_v13_init_is_idempotent(self, tmp_path):
        """Calling init() twice on a v13 database raises nothing and keeps version at 13."""
        db_path = str(tmp_path / "v13_idempotent.db")
        db = Database(db_path)

        db.init()
        assert _get_version(db_path) == 13

        # Second call must not raise.
        db.init()
        assert _get_version(db_path) == 13, "version must stay at 13 after second init()"
        assert _table_exists(db_path, "skills"), "skills table must still exist"
        assert _table_exists(db_path, "shell_invocations"), (
            "shell_invocations table must still exist"
        )

    def test_fresh_init_creates_v13_tables(self, tmp_path):
        """A brand-new Database.init() creates skills, shell_invocations, and schedules at v13."""
        db_path = str(tmp_path / "fresh.db")
        db = Database(db_path)
        db.init()

        assert _get_version(db_path) == 13
        assert _table_exists(db_path, "skills"), "skills table must exist on fresh init"
        assert _row_count(db_path, "skills") == 0
        assert _table_exists(db_path, "shell_invocations"), (
            "shell_invocations table must exist on fresh init"
        )
        assert _row_count(db_path, "shell_invocations") == 0
        assert _table_exists(db_path, "schedules"), (
            "v0.7 schedules table must still exist on a fresh v13 init"
        )

    def test_init_creates_no_vectors_sqlite(self, tmp_path):
        """MIG-07: the v12->v13 bump must not create or touch any vectors.sqlite.

        The vector index lives in a separate store with its own versioning, so a
        schema bump on the trace database cannot silently alter vector state.
        """
        db_path = tmp_path / "horus.sqlite"
        db = Database(db_path)
        db.init()

        assert not (tmp_path / "vectors.sqlite").exists(), (
            "init() must not create a vectors.sqlite (MIG-07: vector store is separate)"
        )


def test_schema_version_is_thirteen():
    """Tripwire guard: pin the live SCHEMA_VERSION at 13.

    When the next contributor bumps the schema, this assertion fails first and
    points them at the tripwire inventory documented in this module's docstring.
    """
    assert SCHEMA_VERSION == 13, (
        "SCHEMA_VERSION changed; sweep every hardcoded current-version "
        "expectation file in this module's tripwire inventory in one commit."
    )
    assert storage.SCHEMA_VERSION == 13


def test_fresh_init_reports_on_disk_version_thirteen(tmp_path):
    """A freshly initialized database reports on-disk schema version 13."""
    db_path = str(tmp_path / "anchor.db")
    Database(db_path).init()
    assert _get_version(db_path) == 13
