"""``horus-os plugins list`` output shape (tabular default + --json).

Seeds the test DB with two plugins (one loaded, one error), runs
``run_plugins`` with a synthetic Namespace, and asserts on the
captured stdout. Empty plugins table renders ``(no plugins installed)``
in tabular mode and ``[]`` in JSON mode.
"""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path

import pytest

from horus_os.cli.plugins_cmd import run_plugins
from horus_os.storage import Database


def _make_db_with_plugins(tmp_path: Path) -> Database:
    db_path = tmp_path / "horus.sqlite3"
    db = Database(db_path)
    db.init()
    with db._connect() as conn:
        conn.execute(
            """
            INSERT INTO plugins
                (name, version, manifest_hash, enabled, installed_at, source)
            VALUES ('alpha', '1.0.0', 'hash-alpha', 1, '2026-05-26T00:00:00Z', 'entry_point')
            """
        )
        conn.execute(
            """
            INSERT INTO plugins
                (name, version, manifest_hash, enabled, installed_at, source)
            VALUES ('beta', '0.2.1', 'hash-beta', 0, '2026-05-26T00:00:00Z', 'filesystem')
            """
        )
        conn.execute(
            """
            INSERT INTO plugin_status
                (plugin_name, status, error_phase, error_message, last_seen)
            VALUES ('alpha', 'loaded', NULL, NULL, '2026-05-26T00:00:00Z')
            """
        )
        conn.execute(
            """
            INSERT INTO plugin_status
                (plugin_name, status, error_phase, error_message, last_seen)
            VALUES ('beta', 'error', 'load', 'something broke', '2026-05-26T00:00:00Z')
            """
        )
    return db


def _make_args(**overrides) -> argparse.Namespace:
    """Build a minimal Namespace for the list verb."""
    base: dict = {"plugins_command": "list", "json": False, "data_dir": None}
    base.update(overrides)
    return argparse.Namespace(**base)


def _run_list(
    db: Database, monkeypatch: pytest.MonkeyPatch, *, json_flag: bool
) -> tuple[int, str, str]:
    """Run run_plugins with a synthetic args + bypass Config.load."""
    args = _make_args(json=json_flag)

    # Stub Config.load to point at our test DB.
    from horus_os import config as config_mod

    class FakeConfig:
        db_path = db.path

    monkeypatch.setattr(config_mod.Config, "load", staticmethod(lambda data_dir=None: FakeConfig()))

    stdout = io.StringIO()
    stderr = io.StringIO()
    rc = run_plugins(args, stdout=stdout, stderr=stderr)
    return rc, stdout.getvalue(), stderr.getvalue()


def test_list_tabular_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = _make_db_with_plugins(tmp_path)
    rc, out, err = _run_list(db, monkeypatch, json_flag=False)
    assert rc == 0
    assert err == ""
    # Header columns appear in stable order.
    assert "name" in out
    assert "version" in out
    assert "status" in out
    assert "enabled" in out
    # Both plugins rendered.
    assert "alpha" in out
    assert "beta" in out
    assert "1.0.0" in out
    assert "0.2.1" in out
    assert "loaded" in out
    assert "error" in out
    # Sorted by name → alpha appears before beta.
    assert out.find("alpha") < out.find("beta")


def test_list_json_returns_parseable_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = _make_db_with_plugins(tmp_path)
    rc, out, _ = _run_list(db, monkeypatch, json_flag=True)
    assert rc == 0
    data = json.loads(out)
    assert isinstance(data, list)
    assert len(data) == 2
    by_name = {row["name"]: row for row in data}
    assert by_name["alpha"]["version"] == "1.0.0"
    assert by_name["alpha"]["status"] == "loaded"
    assert by_name["alpha"]["enabled"] is True
    assert by_name["alpha"]["manifest_hash"] == "hash-alpha"
    assert by_name["alpha"]["source"] == "entry_point"
    assert "installed_at" in by_name["alpha"]
    assert by_name["beta"]["status"] == "error"
    assert by_name["beta"]["enabled"] is False


def test_list_empty_tabular(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "horus.sqlite3"
    db = Database(db_path)
    db.init()
    rc, out, _ = _run_list(db, monkeypatch, json_flag=False)
    assert rc == 0
    assert out == "(no plugins installed)\n"


def test_list_empty_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "horus.sqlite3"
    db = Database(db_path)
    db.init()
    rc, out, _ = _run_list(db, monkeypatch, json_flag=True)
    assert rc == 0
    assert out.strip() == "[]"
