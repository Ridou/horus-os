"""Shared fixtures for the Phase 46 pitfall regression suite.

The pitfall tests under this directory consume two fixtures from the
parent conftest tree:

* ``make_synthetic_plugin`` (from ``tests/plugins/conftest.py``) — tier-1
  spec construction helper.
* The host fixtures (``fake_plugin_entry_points``, ``installed_db``)
  remain available via pytest's parent-conftest auto-discovery.

This sibling conftest adds:

* ``pitfall_db`` — a ``Database(tmp_path/'horus.sqlite3')`` instance
  with ``db.init()`` already called. Mirrors
  ``tests/plugins/conftest.py::installed_db``; named separately so
  pitfall tests have a stable fixture name documented at the suite
  level.

  Phase 46 deviation (Rule 1): the original plan specified an
  ``:memory:`` SQLite handle, but ``Database._connect`` opens a fresh
  connection per call (Phase 41 design) — so ``:memory:`` databases
  don't persist any schema across operations. The file-backed
  tmp_path handle behaves identically from the test's perspective
  (fresh DB per test, no cross-test state) and actually works against
  the production Database class.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from horus_os.storage import Database


@pytest.fixture
def pitfall_db(tmp_path: Path) -> Database:
    """Yield a fresh ``Database`` with the v6 schema applied.

    The DB file lives at ``tmp_path/horus.sqlite3``. Each test gets a
    fresh DB; pytest's tmp-path machinery owns the lifecycle.
    """
    db = Database(tmp_path / "horus.sqlite3")
    db.init()
    return db
