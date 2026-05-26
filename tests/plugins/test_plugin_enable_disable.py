"""ISOLATE-03 / per-plugin enable/disable persistence.

PluginRegistry.enable/disable flip the plugins.enabled column; the
discovery loop in create_app reads is_enabled and skips disabled
plugins before any validate/load/start step.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from horus_os.plugins import (
    PLUGIN_STATUS_DISABLED,
    PluginLoadResult,
    PluginRegistry,
)
from horus_os.plugins.spec import PluginSpec
from horus_os.storage import Database


def _make_spec(name: str) -> PluginSpec:
    return PluginSpec(
        name=name,
        version="0.1.0",
        description="",
        author="",
        license="Apache-2.0",
        horus_os_compat=">=0.5,<0.6",
        homepage=None,
        issue_tracker=None,
        tool_entries=(),
        adapter_entries=(),
        capabilities=(),
        source="filesystem",
        source_detail="",
        manifest_hash="synth",
    )


@pytest.fixture
def db_and_registry(tmp_path: Path) -> tuple[Database, PluginRegistry]:
    db = Database(tmp_path / "horus.sqlite3")
    db.init()
    return db, PluginRegistry(db=db)


def test_is_enabled_default_true(db_and_registry: tuple[Database, PluginRegistry]) -> None:
    """A freshly-registered plugin starts with enabled=1 by default."""
    _db, registry = db_and_registry
    registry.register(_make_spec("foo"))
    assert registry.is_enabled("foo") is True


def test_disable_persists_to_sql(db_and_registry: tuple[Database, PluginRegistry]) -> None:
    """disable(name) flips plugins.enabled to 0 in the SQL column."""
    db, registry = db_and_registry
    registry.register(_make_spec("foo"))
    new_state = registry.disable("foo")

    assert new_state is False
    with db._connect() as conn:
        row = conn.execute(
            "SELECT enabled FROM plugins WHERE name = 'foo'"
        ).fetchone()
        assert row["enabled"] == 0
    assert registry.is_enabled("foo") is False
    entry = registry.get("foo")
    assert entry is not None
    assert entry.status == PLUGIN_STATUS_DISABLED


def test_enable_restores(db_and_registry: tuple[Database, PluginRegistry]) -> None:
    """enable(name) flips plugins.enabled back to 1 + restores status to pending."""
    _db, registry = db_and_registry
    registry.register(_make_spec("foo"))
    registry.disable("foo")
    assert registry.is_enabled("foo") is False

    new_state = registry.enable("foo")
    assert new_state is True
    assert registry.is_enabled("foo") is True
    entry = registry.get("foo")
    assert entry is not None
    # Disabled → enabled flips status back to pending so the next
    # discover pass re-resolves it.
    assert entry.status == "pending"


def test_is_enabled_round_trip(db_and_registry: tuple[Database, PluginRegistry]) -> None:
    """enable/disable round-trip multiple times — column tracks accurately."""
    _db, registry = db_and_registry
    registry.register(_make_spec("foo"))

    for expected in [True, False, True, False, True]:
        if expected:
            registry.enable("foo")
        else:
            registry.disable("foo")
        assert registry.is_enabled("foo") is expected


def test_is_enabled_unknown_name_defaults_to_true(
    db_and_registry: tuple[Database, PluginRegistry],
) -> None:
    """is_enabled('never-registered') returns True so a first-discovery encounter loads."""
    _, registry = db_and_registry
    assert registry.is_enabled("never-registered") is True


def test_disable_skips_load_at_create_app(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """After disable(name), the next create_app pass skips load() for that plugin."""
    pytest.importorskip("fastapi")

    data_dir = tmp_path / "horus_data"
    data_dir.mkdir()
    db = Database(data_dir / "horus.sqlite")
    db.init()

    # Pre-register the plugin row + flip enabled=0 so the next
    # create_app pass should NOT call loader.load on it.
    pre_registry = PluginRegistry(db=db)
    pre_registry.register(_make_spec("foo"))
    pre_registry.disable("foo")

    spec = _make_spec("foo")

    def _fake_discover() -> tuple[list[object], list[object]]:
        return [spec], []

    load_calls: list[str] = []

    def _fake_load(self: object, s: object) -> PluginLoadResult:
        load_calls.append(s.name)
        return PluginLoadResult(status="loaded")

    monkeypatch.setattr(
        "horus_os.server.api.discover_plugins", _fake_discover,
    )
    monkeypatch.setattr(
        "horus_os.plugins.loader.PluginLoader.load", _fake_load,
    )

    from horus_os.server.api import create_app

    app = create_app(data_dir=data_dir)

    # PluginLoader.load was NOT invoked for the disabled plugin.
    assert "foo" not in load_calls

    # And the entry surfaces as status='disabled' in the registry.
    entry = app.state.plugin_registry.get("foo")
    assert entry is not None
    assert entry.status == PLUGIN_STATUS_DISABLED
