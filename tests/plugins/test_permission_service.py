"""PermissionService.grant / revoke / pending_on_upgrade audit-log coverage.

Each mutator persists the state change AND appends a row to
plugin_capability_grants_log. The CHECK constraint on the ``actor``
column refuses anything outside ``{'cli','dashboard','system'}``.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from horus_os.plugins.permissions import PermissionService
from horus_os.storage import Database


def _make_db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "horus.sqlite3")
    db.init()
    # Insert the plugins row so the plugin_capabilities FK has a target.
    with db._connect() as conn:
        conn.execute(
            """
            INSERT INTO plugins (name, version, manifest_hash, enabled, installed_at, source)
            VALUES ('foo', '1.0', 'hash1', 1, '2026-05-26T00:00:00Z', 'filesystem')
            """
        )
    return db


def _log_rows(db: Database, plugin_name: str) -> list[sqlite3.Row]:
    with db._connect() as conn:
        rows = conn.execute(
            """
            SELECT plugin_name, plugin_version, capability, action,
                   manifest_hash, actor, timestamp
            FROM plugin_capability_grants_log
            WHERE plugin_name = ?
            ORDER BY id ASC
            """,
            (plugin_name,),
        ).fetchall()
    return list(rows)


def _capability_row(db: Database, plugin_name: str, version: str, cap: str) -> sqlite3.Row | None:
    with db._connect() as conn:
        return conn.execute(
            """
            SELECT plugin_name, plugin_version, capability, manifest_hash, state, granted_at
            FROM plugin_capabilities
            WHERE plugin_name = ? AND plugin_version = ? AND capability = ?
            """,
            (plugin_name, version, cap),
        ).fetchone()


def test_grant_appends_log_row(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    svc = PermissionService(db)
    svc.grant("foo", "1.0", "filesystem.read", actor="cli", manifest_hash="hash1")

    row = _capability_row(db, "foo", "1.0", "filesystem.read")
    assert row is not None
    assert row["state"] == "granted"
    assert row["manifest_hash"] == "hash1"
    assert row["granted_at"] is not None

    logs = _log_rows(db, "foo")
    assert len(logs) == 1
    assert logs[0]["action"] == "granted"
    assert logs[0]["actor"] == "cli"
    assert logs[0]["capability"] == "filesystem.read"
    assert logs[0]["manifest_hash"] == "hash1"
    assert logs[0]["timestamp"]  # non-empty


def test_revoke_appends_log_row(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    svc = PermissionService(db)
    svc.grant("foo", "1.0", "filesystem.read", actor="cli", manifest_hash="hash1")
    svc.revoke("foo", "1.0", "filesystem.read", actor="dashboard")

    row = _capability_row(db, "foo", "1.0", "filesystem.read")
    assert row is not None
    assert row["state"] == "revoked"

    logs = _log_rows(db, "foo")
    assert len(logs) == 2
    assert logs[0]["action"] == "granted"
    assert logs[1]["action"] == "revoked"
    assert logs[1]["actor"] == "dashboard"
    # Revoke carries forward the existing manifest_hash so history is intact.
    assert logs[1]["manifest_hash"] == "hash1"


def test_pending_on_upgrade_appends_log_row(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    svc = PermissionService(db)
    svc.pending_on_upgrade(
        "foo", "1.0", "1.1",
        {"filesystem.read"}, "newhash",
        actor="system",
    )

    row = _capability_row(db, "foo", "1.1", "filesystem.read")
    assert row is not None
    assert row["state"] == "pending"
    assert row["manifest_hash"] == "newhash"
    assert row["granted_at"] is None

    logs = _log_rows(db, "foo")
    assert len(logs) == 1
    assert logs[0]["action"] == "pending_on_upgrade"
    assert logs[0]["actor"] == "system"
    assert logs[0]["manifest_hash"] == "newhash"
    assert logs[0]["plugin_version"] == "1.1"


def test_log_actor_check_constraint(tmp_path: Path) -> None:
    """Actor outside {cli, dashboard, system} raises IntegrityError."""
    db = _make_db(tmp_path)
    svc = PermissionService(db)
    with pytest.raises(sqlite3.IntegrityError):
        svc.grant("foo", "1.0", "filesystem.read", actor="attacker", manifest_hash="hash1")


def test_grant_is_idempotent_re_grant_same_hash(tmp_path: Path) -> None:
    """Granting the same cap twice updates the row + appends a SECOND log entry."""
    db = _make_db(tmp_path)
    svc = PermissionService(db)
    svc.grant("foo", "1.0", "filesystem.read", actor="cli", manifest_hash="hash1")
    svc.grant("foo", "1.0", "filesystem.read", actor="cli", manifest_hash="hash1")
    logs = _log_rows(db, "foo")
    assert len(logs) == 2  # two grants recorded (history matters)
    row = _capability_row(db, "foo", "1.0", "filesystem.read")
    assert row is not None
    assert row["state"] == "granted"
