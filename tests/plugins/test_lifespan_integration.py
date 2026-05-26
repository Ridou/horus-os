"""FastAPI lifespan integration tests for the Phase 42 plugin pipeline.

Two scenarios:

* ``test_lifespan_continues_on_broken_plugin`` — inject the
  ``import_raises`` fixture via filesystem; build the FastAPI app;
  assert ``app.state.plugin_registry.error()`` contains the broken
  plugin AND the app's other surfaces still work byte-identically.
* ``test_lifespan_loads_healthy_plugin`` — inject the ``healthy``
  fixture; assert the plugin appears in
  ``app.state.plugin_registry.enabled()`` and the tool is registered
  on ``app.state.tool_registry``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from horus_os.plugins import PLUGIN_STATUS_ERROR, PLUGIN_STATUS_LOADED


@pytest.fixture
def lifespan_data_dir(tmp_path: Path) -> Path:
    """Initialize an isolated data_dir with the Phase 41 schema applied."""
    from horus_os.storage import Database

    data_dir = tmp_path / "horus_data"
    data_dir.mkdir()
    # The lifespan reads Config.load(data_dir).db_path; that resolves
    # to <data_dir>/horus.sqlite by default. Pre-init the DB so the
    # plugin pipeline has the v6 schema to write into.
    db = Database(data_dir / "horus.sqlite")
    db.init()
    return data_dir


def _healthy_manifest_hash() -> str:
    """Compute the manifest_hash for the healthy fixture's requested caps."""
    from horus_os.plugins.manifest import compute_manifest_hash

    return compute_manifest_hash(["filesystem.read"])


def _pre_grant_filesystem_read(
    data_dir: Path,
    plugin_name: str,
    plugin_version: str = "0.1.0",
) -> None:
    """Pre-grant filesystem.read for a fixture plugin.

    Phase 43 update: under default-deny PermissionGate, a plugin
    requesting any capability lands in ``error_phase='permission'``
    unless a grant row exists. Phase 42 tests assert specific
    error_phases (``'load'`` for ``import-raises``, ``'loaded'`` for
    ``healthy``); pre-granting the cap lets those plugins flow past
    the permission gate so the original assertions still hold.
    """
    from horus_os.plugins.permissions import PermissionService
    from horus_os.storage import Database

    db = Database(data_dir / "horus.sqlite")
    h = _healthy_manifest_hash()
    with db._connect() as conn:
        # plugins row must exist before plugin_capabilities FK CASCADE.
        conn.execute(
            """
            INSERT OR IGNORE INTO plugins
                (name, version, manifest_hash, enabled, installed_at, source)
            VALUES (?, ?, ?, 1, '2026-05-26T00:00:00Z', 'filesystem')
            """,
            (plugin_name, plugin_version, h),
        )
    PermissionService(db).grant(
        plugin_name, plugin_version, "filesystem.read",
        actor="system", manifest_hash=h,
    )


def _pre_grant_healthy(data_dir: Path) -> None:
    """Backwards-compat alias for the most common case."""
    _pre_grant_filesystem_read(data_dir, "healthy")


def test_lifespan_continues_on_broken_plugin(
    fake_plugin_entry_points,
    tmp_plugin_dir: Path,
    install_broken_fixture,
    lifespan_data_dir: Path,
) -> None:
    """A broken plugin must NOT crash FastAPI startup; pre-v0.5 routes unchanged."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from horus_os.server.api import create_app

    sys.modules.pop("tests.fixtures.broken_plugins.import_raises", None)
    install_broken_fixture("import_raises")
    # Phase 43: pre-grant so the failure path lands at 'load' (the
    # phase the fixture is designed to exercise) rather than at
    # 'permission' (which would mask the LOAD-phase isolation that
    # this test pins).
    _pre_grant_filesystem_read(lifespan_data_dir, "import-raises")

    app = create_app(data_dir=lifespan_data_dir)
    with TestClient(app) as client:
        # Health route returns 200 even though a plugin failed to load.
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    # plugin_registry exists and contains the import-raises plugin
    # under status='error' with error_phase='load'.
    plugin_registry = app.state.plugin_registry
    entry = plugin_registry.get("import-raises")
    assert entry is not None
    assert entry.status == PLUGIN_STATUS_ERROR
    assert entry.error_phase == "load"
    assert "RuntimeError" in (entry.error_message or "")

    # Adapters route still serves the v0.3 shape byte-identically.
    with TestClient(app) as client:
        r = client.get("/api/adapters")
        assert r.status_code == 200
        body = r.json()
        assert "adapters" in body
        assert isinstance(body["adapters"], list)


def test_lifespan_loads_healthy_plugin(
    fake_plugin_entry_points,
    tmp_plugin_dir: Path,
    install_broken_fixture,
    lifespan_data_dir: Path,
) -> None:
    """A healthy plugin lands in app.state.plugin_registry.enabled()."""
    pytest.importorskip("fastapi")
    from horus_os.server.api import create_app

    install_broken_fixture("healthy")
    _pre_grant_healthy(lifespan_data_dir)

    app = create_app(data_dir=lifespan_data_dir)

    plugin_registry = app.state.plugin_registry
    enabled = [e.name for e in plugin_registry.enabled()]
    assert "healthy" in enabled
    healthy_entry = plugin_registry.get("healthy")
    assert healthy_entry is not None
    assert healthy_entry.status == PLUGIN_STATUS_LOADED
    assert "hello_tool" in healthy_entry.registered_tools

    # The healthy plugin's tool is in the master tool_registry.
    tool_registry = app.state.tool_registry
    tool = tool_registry.get("hello_tool")
    assert tool is not None
    assert callable(tool.handler)
    # The handler is wrapped through the (pass-through) CapabilityGuard
    # so calling it returns the underlying tool's output.
    output = tool.handler(value="echo me back")
    assert output == {"echo": {"value": "echo me back"}}


def test_lifespan_three_registries_attached(
    fake_plugin_entry_points,
    tmp_plugin_dir: Path,
    lifespan_data_dir: Path,
) -> None:
    """app.state carries adapter_registry, tool_registry, plugin_registry."""
    pytest.importorskip("fastapi")
    from horus_os.server.api import create_app

    app = create_app(data_dir=lifespan_data_dir)
    assert hasattr(app.state, "adapter_registry")
    assert hasattr(app.state, "tool_registry")
    assert hasattr(app.state, "plugin_registry")
    # Zero plugins installed -> empty plugin registry.
    assert app.state.plugin_registry.all() == []


def test_lifespan_with_all_broken_fixtures_still_starts(
    fake_plugin_entry_points,
    tmp_plugin_dir: Path,
    install_broken_fixture,
    lifespan_data_dir: Path,
) -> None:
    """All four broken fixtures + the healthy control: FastAPI starts cleanly."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from horus_os.server.api import create_app

    sys.modules.pop("tests.fixtures.broken_plugins.import_raises", None)

    install_broken_fixture("bad_toml")
    install_broken_fixture("schema_fail")
    install_broken_fixture("import_raises")
    install_broken_fixture("tool_raises_registration")
    install_broken_fixture("healthy")
    _pre_grant_healthy(lifespan_data_dir)
    # Phase 43: also pre-grant the load-phase fixtures so they reach
    # the load step the original Phase 42 test was designed to verify.
    _pre_grant_filesystem_read(lifespan_data_dir, "import-raises")
    _pre_grant_filesystem_read(lifespan_data_dir, "tool-raises-registration")

    app = create_app(data_dir=lifespan_data_dir)

    with TestClient(app) as client:
        r = client.get("/api/health")
        assert r.status_code == 200

    plugin_registry = app.state.plugin_registry
    error_names = {e.name for e in plugin_registry.error()}
    assert {"bad_toml", "schema_fail", "import-raises", "tool-raises-registration"} <= error_names
    enabled_names = {e.name for e in plugin_registry.enabled()}
    assert "healthy" in enabled_names
