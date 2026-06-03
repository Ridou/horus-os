"""Regression test: v11 -> v12 additive + idempotent migration.

Verifies that:
- A database stamped schema_version=11 upgrades to 12 on Database.init().
- The schedules table is created and is empty after upgrade.
- Pre-existing trace rows survive the upgrade (additive, not destructive).
- Calling init() a second time on a v12 database is a no-op (idempotent).
- A fresh Database.init() also produces schema_version=12 with a schedules table.
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


class TestV11ToV12Migration:
    """Additive + idempotent migration from schema version 11 to 12."""

    def test_v11_upgrades_to_v12(self, tmp_path):
        """A v11 database gains the schedules table and version bumps to 12."""
        db_path = str(tmp_path / "v11.db")

        # Bootstrap a minimal v11 database by running init() and then forcing
        # the schema_version back to 11 to simulate an existing v11 installation.
        db = Database(db_path)
        db.init()

        # Force version back to 11 to simulate a v11 database.
        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE schema_version SET version = 11")
        conn.execute("DROP TABLE IF EXISTS schedules")
        conn.commit()
        conn.close()

        assert _get_version(db_path) == 11
        assert not _table_exists(db_path, "schedules")

        # Insert a trace row to verify data survives the migration.
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO traces "
            "(trace_id, created_at, provider, model, prompt) "
            "VALUES ('test-trace-v11', '2026-01-01T00:00:00Z', 'anthropic', 'claude-3', 'hello')"
        )
        conn.commit()
        conn.close()

        # Run migration.
        db.init()

        assert _get_version(db_path) == 12
        assert _table_exists(db_path, "schedules"), "schedules table must exist after upgrade"
        assert _row_count(db_path, "schedules") == 0, "schedules table must be empty after upgrade"

        # Verify pre-existing trace row survived.
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT trace_id FROM traces WHERE trace_id = 'test-trace-v11'"
        ).fetchone()
        conn.close()
        assert row is not None, "pre-existing trace row must survive the v11->v12 migration"

    def test_v12_init_is_idempotent(self, tmp_path):
        """Calling init() twice on a v12 database raises nothing and keeps version at 12."""
        db_path = str(tmp_path / "v12_idempotent.db")
        db = Database(db_path)

        db.init()
        assert _get_version(db_path) == 12

        # Second call must not raise.
        db.init()
        assert _get_version(db_path) == 12, "version must stay at 12 after second init()"
        assert _table_exists(db_path, "schedules"), "schedules table must still exist"

    def test_fresh_init_creates_schedules_table(self, tmp_path):
        """A brand-new Database.init() creates the schedules table at schema_version 12."""
        db_path = str(tmp_path / "fresh.db")
        db = Database(db_path)
        db.init()

        assert _get_version(db_path) == 12
        assert _table_exists(db_path, "schedules"), "schedules table must exist on fresh init"
        assert _row_count(db_path, "schedules") == 0

    def test_create_schedule_round_trips(self, tmp_path):
        """create_schedule then get_schedule round-trips the stored fields with defaults."""
        db_path = str(tmp_path / "sched_rt.db")
        db = Database(db_path)
        db.init()

        db.create_schedule(
            "morning-brief",
            cron_expression="0 9 * * *",
            agent_profile_name="default",
            prompt="Summarize the day ahead.",
        )
        record = db.get_schedule("morning-brief")
        assert record is not None
        assert record.name == "morning-brief"
        assert record.cron_expression == "0 9 * * *"
        assert record.agent_profile_name == "default"
        assert record.prompt == "Summarize the day ahead."
        assert record.catch_up_policy == "coalesce"
        assert record.enabled == 1

    def test_update_schedule_run_persists_state(self, tmp_path):
        """update_schedule_run persists last_run_at, next_run_at, and last_trace_id."""
        db_path = str(tmp_path / "sched_run.db")
        db = Database(db_path)
        db.init()

        db.create_schedule(
            "ping",
            cron_expression="* * * * *",
            agent_profile_name="default",
            prompt="ping",
        )
        db.update_schedule_run(
            "ping",
            last_run_at="2026-01-01T00:00:00Z",
            next_run_at="2026-01-01T00:01:00Z",
            last_trace_id="trace-123",
        )
        record = db.get_schedule("ping")
        assert record is not None
        assert record.last_run_at == "2026-01-01T00:00:00Z"
        assert record.next_run_at == "2026-01-01T00:01:00Z"
        assert record.last_trace_id == "trace-123"

    def test_list_enabled_schedules_filters_disabled(self, tmp_path):
        """list_enabled_schedules returns only rows where enabled=1."""
        db_path = str(tmp_path / "sched_enabled.db")
        db = Database(db_path)
        db.init()

        db.create_schedule(
            "on", cron_expression="* * * * *", agent_profile_name="default", prompt="on"
        )
        db.create_schedule(
            "off", cron_expression="* * * * *", agent_profile_name="default", prompt="off"
        )
        db.set_schedule_enabled("off", False)

        enabled = db.list_enabled_schedules()
        names = {s.name for s in enabled}
        assert "on" in names
        assert "off" not in names
