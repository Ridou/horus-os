"""Regression test: v10 -> v11 additive + idempotent migration.

Verifies that:
- A database stamped schema_version=10 upgrades to 11 on Database.init().
- The sync_cursors table is created and is empty after upgrade.
- Pre-existing trace rows survive the upgrade (additive, not destructive).
- Calling init() a second time on a v11 database is a no-op (idempotent).
- A fresh Database.init() also produces schema_version=12 with a sync_cursors table.
"""

from __future__ import annotations

import sqlite3

from horus_os.storage import Database


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


class TestV10ToV11Migration:
    """Additive + idempotent migration from schema version 10 to 11."""

    def test_v10_upgrades_to_v11(self, tmp_path):
        """A v10 database gains the sync_cursors table and version bumps to 11."""
        db_path = str(tmp_path / "v10.db")

        # Bootstrap a minimal v10 database by running init() and then forcing
        # the schema_version back to 10 to simulate an existing v10 installation.
        db = Database(db_path)
        db.init()

        # Force version back to 10 to simulate a v10 database.
        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE schema_version SET version = 10")
        conn.execute("DROP TABLE IF EXISTS sync_cursors")
        conn.commit()
        conn.close()

        assert _get_version(db_path) == 10
        assert not _table_exists(db_path, "sync_cursors")

        # Insert a trace row to verify data survives the migration.
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO traces "
            "(trace_id, created_at, provider, model, prompt) "
            "VALUES ('test-trace-v10', '2026-01-01T00:00:00Z', 'anthropic', 'claude-3', 'hello')"
        )
        conn.commit()
        conn.close()

        # Run migration.
        db.init()

        assert _get_version(db_path) == 12
        assert _table_exists(db_path, "sync_cursors"), "sync_cursors table must exist after upgrade"
        assert _row_count(db_path, "sync_cursors") == 0, (
            "sync_cursors table must be empty after upgrade"
        )

        # Verify pre-existing trace row survived.
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT trace_id FROM traces WHERE trace_id = 'test-trace-v10'"
        ).fetchone()
        conn.close()
        assert row is not None, "pre-existing trace row must survive the v10->v11 migration"

    def test_v11_init_is_idempotent(self, tmp_path):
        """Calling init() twice on a v11 database raises nothing and keeps version at 11."""
        db_path = str(tmp_path / "v11_idempotent.db")
        db = Database(db_path)

        db.init()
        assert _get_version(db_path) == 12

        # Second call must not raise.
        db.init()
        assert _get_version(db_path) == 12, "version must stay at 12 after second init()"
        assert _table_exists(db_path, "sync_cursors"), "sync_cursors table must still exist"

    def test_fresh_init_creates_sync_cursors_table(self, tmp_path):
        """A brand-new Database.init() creates the sync_cursors table at schema_version 12."""
        db_path = str(tmp_path / "fresh.db")
        db = Database(db_path)
        db.init()

        assert _get_version(db_path) == 12
        assert _table_exists(db_path, "sync_cursors"), "sync_cursors table must exist on fresh init"
        assert _row_count(db_path, "sync_cursors") == 0
