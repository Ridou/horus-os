"""Regression test: v8 -> v9 additive + idempotent migration.

Verifies that:
- A database stamped schema_version=8 upgrades to 9 on Database.init().
- The tasks table is created and is empty after upgrade.
- Pre-existing trace rows survive the upgrade (additive, not destructive).
- Calling init() a second time on a v9 database is a no-op (idempotent).
- A fresh Database.init() also produces schema_version=9 with a tasks table.
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


class TestV8ToV9Migration:
    """Additive + idempotent migration from schema version 8 to 9."""

    def test_v8_upgrades_to_v9(self, tmp_path):
        """A v8 database gains the tasks table and version bumps to 9."""
        db_path = str(tmp_path / "v8.db")

        # Bootstrap a minimal v8 database by running init() and then forcing
        # the schema_version back to 8 to simulate an existing v8 installation.
        db = Database(db_path)
        db.init()

        # Force version back to 8 to simulate a v8 database.
        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE schema_version SET version = 8")
        conn.execute("DROP TABLE IF EXISTS tasks")
        conn.commit()
        conn.close()

        assert _get_version(db_path) == 8
        assert not _table_exists(db_path, "tasks")

        # Insert a trace row to verify data survives the migration.
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO traces "
            "(trace_id, created_at, provider, model, prompt) "
            "VALUES ('test-trace-v8', '2026-01-01T00:00:00Z', 'anthropic', 'claude-3', 'hello')"
        )
        conn.commit()
        conn.close()

        # Run migration.
        db.init()

        assert _get_version(db_path) == 12
        assert _table_exists(db_path, "tasks"), "tasks table must exist after upgrade"
        assert _row_count(db_path, "tasks") == 0, "tasks table must be empty after upgrade"

        # Verify pre-existing trace row survived.
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT trace_id FROM traces WHERE trace_id = 'test-trace-v8'"
        ).fetchone()
        conn.close()
        assert row is not None, "pre-existing trace row must survive the v8->v9 migration"

    def test_v9_init_is_idempotent(self, tmp_path):
        """Calling init() twice on a v9 database raises nothing and keeps version at 9."""
        db_path = str(tmp_path / "v9_idempotent.db")
        db = Database(db_path)

        db.init()
        assert _get_version(db_path) == 12

        # Second call must not raise.
        db.init()
        assert _get_version(db_path) == 12, "version must stay at current after second init()"
        assert _table_exists(db_path, "tasks"), "tasks table must still exist"

    def test_fresh_init_creates_tasks_table(self, tmp_path):
        """A brand-new Database.init() creates the tasks table at schema_version 9."""
        db_path = str(tmp_path / "fresh.db")
        db = Database(db_path)
        db.init()

        assert _get_version(db_path) == 12
        assert _table_exists(db_path, "tasks"), "tasks table must exist on fresh init"
        assert _row_count(db_path, "tasks") == 0

    def test_save_task_insert_or_ignore(self, tmp_path):
        """save_task is a no-op on duplicate task_id (INSERT OR IGNORE)."""
        db_path = str(tmp_path / "save_task.db")
        db = Database(db_path)
        db.init()

        task = TaskRecord(
            task_id="demo-task-001",
            title="Test task",
            description="desc",
            status="pending",
            agent_profile_name=None,
            trace_id=None,
            is_demo_seed=False,
            created_at="",
            updated_at="",
        )
        db.save_task(task)
        db.save_task(task)  # duplicate - must be silent no-op

        rows = db.list_tasks()
        assert len(rows) == 1, "duplicate save_task must be a no-op"

    def test_list_tasks_status_filter(self, tmp_path):
        """list_tasks(status='pending') returns only pending tasks."""
        db_path = str(tmp_path / "list_tasks.db")
        db = Database(db_path)
        db.init()

        for i, status in enumerate(["pending", "running", "completed"]):
            db.save_task(
                TaskRecord(
                    task_id=f"task-{i}",
                    title=f"Task {i}",
                    description="",
                    status=status,
                    agent_profile_name=None,
                    trace_id=None,
                    is_demo_seed=False,
                    created_at="",
                    updated_at="",
                )
            )

        pending = db.list_tasks(status="pending")
        assert len(pending) == 1
        assert pending[0].status == "pending"

        all_tasks = db.list_tasks()
        assert len(all_tasks) == 3

    def test_delete_task_returns_bool(self, tmp_path):
        """delete_task returns True when deleted, False when not found."""
        db_path = str(tmp_path / "delete_task.db")
        db = Database(db_path)
        db.init()

        db.save_task(
            TaskRecord(
                task_id="task-to-delete",
                title="Delete me",
                description="",
                status="pending",
                agent_profile_name=None,
                trace_id=None,
                is_demo_seed=False,
                created_at="",
                updated_at="",
            )
        )

        assert db.delete_task("task-to-delete") is True
        assert db.delete_task("task-to-delete") is False

    def test_delete_trace_returns_bool(self, tmp_path):
        """delete_trace returns True when deleted, False when not found."""
        db_path = str(tmp_path / "delete_trace.db")
        db = Database(db_path)
        db.init()

        # Insert a trace row directly to test delete_trace.
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO traces "
            "(trace_id, created_at, provider, model, prompt) "
            "VALUES ('trace-del-001', '2026-01-01T00:00:00Z', 'anthropic', 'claude-3', 'hi')"
        )
        conn.commit()
        conn.close()

        assert db.delete_trace("trace-del-001") is True
        assert db.delete_trace("trace-del-001") is False

    def test_load_profile_icase(self, tmp_path):
        """load_profile_icase matches profiles case-insensitively."""
        db_path = str(tmp_path / "icase.db")
        db = Database(db_path)
        db.init()

        # The default profile is seeded as 'default' during init.
        profile = db.load_profile_icase("DEFAULT")
        assert profile is not None
        assert profile.name == "default"

        profile2 = db.load_profile_icase("Default")
        assert profile2 is not None
        assert profile2.name == "default"

        missing = db.load_profile_icase("nonexistent-xyz")
        assert missing is None
