"""Regression test: v9 -> v10 additive + idempotent migration.

Verifies that:
- A database stamped schema_version=9 upgrades to 10 on Database.init().
- The discord_feedback table is created and is empty after upgrade.
- Pre-existing trace rows survive the upgrade (additive, not destructive).
- Calling init() a second time on a v10 database is a no-op (idempotent).
- A fresh Database.init() also produces schema_version=10 with a discord_feedback table.
"""

from __future__ import annotations

import sqlite3

from horus_os.storage import Database, TaskRecord


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


class TestV9ToV10Migration:
    """Additive + idempotent migration from schema version 9 to 10."""

    def test_v9_upgrades_to_v10(self, tmp_path):
        """A v9 database gains the discord_feedback table and version bumps to 10."""
        db_path = str(tmp_path / "v9.db")

        # Bootstrap a minimal v9 database by running init() and then forcing
        # the schema_version back to 9 to simulate an existing v9 installation.
        db = Database(db_path)
        db.init()

        # Force version back to 9 to simulate a v9 database.
        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE schema_version SET version = 9")
        conn.execute("DROP TABLE IF EXISTS discord_feedback")
        conn.commit()
        conn.close()

        assert _get_version(db_path) == 9
        assert not _table_exists(db_path, "discord_feedback")

        # Insert a trace row to verify data survives the migration.
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO traces "
            "(trace_id, created_at, provider, model, prompt) "
            "VALUES ('test-trace-v9', '2026-01-01T00:00:00Z', 'anthropic', 'claude-3', 'hello')"
        )
        conn.commit()
        conn.close()

        # Run migration.
        db.init()

        assert _get_version(db_path) == 12
        assert _table_exists(db_path, "discord_feedback"), (
            "discord_feedback table must exist after upgrade"
        )
        assert _row_count(db_path, "discord_feedback") == 0, (
            "discord_feedback table must be empty after upgrade"
        )

        # Verify pre-existing trace row survived.
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT trace_id FROM traces WHERE trace_id = 'test-trace-v9'"
        ).fetchone()
        conn.close()
        assert row is not None, "pre-existing trace row must survive the v9->v10 migration"

    def test_v10_init_is_idempotent(self, tmp_path):
        """Calling init() twice on a v10 database raises nothing and keeps version at 10."""
        db_path = str(tmp_path / "v10_idempotent.db")
        db = Database(db_path)

        db.init()
        assert _get_version(db_path) == 12

        # Second call must not raise.
        db.init()
        assert _get_version(db_path) == 12, "version must stay at 12 after second init()"
        assert _table_exists(db_path, "discord_feedback"), "discord_feedback table must still exist"

    def test_fresh_init_creates_discord_feedback_table(self, tmp_path):
        """A brand-new Database.init() creates the discord_feedback table at schema_version 10."""
        db_path = str(tmp_path / "fresh.db")
        db = Database(db_path)
        db.init()

        assert _get_version(db_path) == 12
        assert _table_exists(db_path, "discord_feedback"), (
            "discord_feedback table must exist on fresh init"
        )
        assert _row_count(db_path, "discord_feedback") == 0

    def test_save_discord_feedback_last_reaction_wins(self, tmp_path):
        """save_discord_feedback uses INSERT OR REPLACE so the second call wins."""
        db_path = str(tmp_path / "feedback.db")
        db = Database(db_path)
        db.init()

        # Save a positive reaction.
        db.save_discord_feedback(
            message_id="msg-001",
            channel_id="chan-001",
            user_id="user-001",
            emoji="thumbsup",
            positive=True,
        )

        # Save a negative reaction for the same (message_id, user_id) - last wins.
        db.save_discord_feedback(
            message_id="msg-001",
            channel_id="chan-001",
            user_id="user-001",
            emoji="thumbsdown",
            positive=False,
        )

        # Must have exactly one row and it must reflect the second call.
        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT positive, emoji FROM discord_feedback WHERE message_id='msg-001' AND user_id='user-001'"
        ).fetchall()
        conn.close()

        assert len(rows) == 1, (
            "INSERT OR REPLACE must leave exactly one row per (message_id, user_id)"
        )
        assert rows[0][0] == 0, "positive must be 0 (second call was negative)"
        assert rows[0][1] == "thumbsdown", "emoji must reflect the second call"

    def test_update_task_status(self, tmp_path):
        """update_task_status changes the status on an existing task and returns True."""
        db_path = str(tmp_path / "update_status.db")
        db = Database(db_path)
        db.init()

        task = TaskRecord(
            task_id="task-status-001",
            title="Status test task",
            description="desc",
            status="pending",
            agent_profile_name=None,
            trace_id=None,
            is_demo_seed=False,
            created_at="",
            updated_at="",
        )
        db.save_task(task)

        # Update to running.
        result = db.update_task_status("task-status-001", "running")
        assert result is True, "update_task_status must return True when a row was updated"

        tasks = db.list_tasks()
        assert len(tasks) == 1
        assert tasks[0].status == "running", "task status must be updated to 'running'"

        # Update on missing task_id returns False.
        result = db.update_task_status("nonexistent-task-id", "completed")
        assert result is False, "update_task_status must return False when no row was found"
