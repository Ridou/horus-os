"""TEST-19 broken-plugin coverage: discovery + load failure containment.

Each of the four broken fixtures surfaces a distinct error_phase
without ever raising out of ``discover_plugins()`` /
``PluginLoader.load()``:

* bad_toml -> error_phase='discover' (manifest fails TOML parse;
  loader is never reached).
* schema_fail -> error_phase='validate' (manifest fails pydantic;
  loader is never reached).
* import_raises -> error_phase='load' (module raises at import).
* tool_raises_registration -> error_phase='load' (factory raises
  during registration; rollback unregisters partial state).

A fifth test ("isolation guarantee") runs all five fixtures (four
broken + the healthy control) through the same discover+load pass
and asserts:

* The healthy control still loads (status='loaded').
* The four broken fixtures appear as status='error' with the right
  error_phase.
* The full lifespan never raises out.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from horus_os.adapters.base import AdapterRegistry
from horus_os.plugins import (
    PLUGIN_STATUS_ERROR,
    PLUGIN_STATUS_LOADED,
    PluginLoader,
    PluginRegistry,
    discover_plugins,
)
from horus_os.tools.registry import ToolRegistry


def _run_full_pipeline(
    tool_registry: ToolRegistry,
    adapter_registry: AdapterRegistry,
) -> PluginRegistry:
    """Run the lifespan-shaped discover+load pipeline over the current source.

    Mirrors the FastAPI lifespan body in src/horus_os/server/api.py
    so the isolation guarantee here matches the production code path.
    """
    plugin_registry = PluginRegistry(db=None)
    loader = PluginLoader(tool_registry=tool_registry, adapter_registry=adapter_registry)

    specs, errors = discover_plugins()
    for err in errors:
        plugin_registry.register_discovery_error(
            err.name,
            source=err.source,
            source_detail=err.source_detail,
            error_phase=err.error_phase,
            error_message=err.error_message,
        )
    for spec in specs:
        plugin_registry.register(spec)
        result = loader.load(spec)
        if result.status == "loaded":
            plugin_registry.mark_loaded(
                spec.name,
                registered_tools=result.registered_tools,
                registered_adapters=result.registered_adapters,
            )
        else:
            plugin_registry.mark_error(
                spec.name,
                result.error_phase or "load",
                result.error or "",
            )
    return plugin_registry


def test_bad_toml_fixture_surfaces_as_discover_error(
    fake_plugin_entry_points,
    tmp_plugin_dir: Path,
    install_broken_fixture,
) -> None:
    install_broken_fixture("bad_toml")

    registry = _run_full_pipeline(ToolRegistry(), AdapterRegistry())

    entry = registry.get("bad_toml")
    assert entry is not None
    assert entry.status == PLUGIN_STATUS_ERROR
    assert entry.error_phase == "discover"


def test_schema_fail_fixture_surfaces_as_validate_error(
    fake_plugin_entry_points,
    tmp_plugin_dir: Path,
    install_broken_fixture,
) -> None:
    install_broken_fixture("schema_fail")

    registry = _run_full_pipeline(ToolRegistry(), AdapterRegistry())

    entry = registry.get("schema_fail")
    assert entry is not None
    assert entry.status == PLUGIN_STATUS_ERROR
    assert entry.error_phase == "validate"


def test_import_raises_fixture_surfaces_as_load_error(
    fake_plugin_entry_points,
    tmp_plugin_dir: Path,
    install_broken_fixture,
) -> None:
    """import_raises: module raises at import; loader's importlib call catches.

    The fixture has been imported lazily by no test in this session yet,
    so the import fires the first time PluginLoader.load() resolves the
    entry_point. The catch-all in load() converts to error_phase='load'.

    Note: if a PRIOR test in this session imported the module, Python's
    import cache surfaces a different error path. We isolate by ensuring
    the module is not cached at the start of this test.
    """
    import sys

    sys.modules.pop("tests.fixtures.broken_plugins.import_raises", None)
    install_broken_fixture("import_raises")

    registry = _run_full_pipeline(ToolRegistry(), AdapterRegistry())

    entry = registry.get("import-raises")
    assert entry is not None, f"expected import-raises entry; got {registry.names()!r}"
    assert entry.status == PLUGIN_STATUS_ERROR
    assert entry.error_phase == "load"
    assert "RuntimeError" in (entry.error_message or "")


def test_tool_raises_registration_fixture_surfaces_as_load_error(
    fake_plugin_entry_points,
    tmp_plugin_dir: Path,
    install_broken_fixture,
) -> None:
    """tool_raises_registration: factory raises ValueError during registration."""
    install_broken_fixture("tool_raises_registration")

    tool_registry = ToolRegistry()
    pre_count = len(tool_registry)
    registry = _run_full_pipeline(tool_registry, AdapterRegistry())

    entry = registry.get("tool-raises-registration")
    assert entry is not None
    assert entry.status == PLUGIN_STATUS_ERROR
    assert entry.error_phase == "load"
    assert "ValueError" in (entry.error_message or "")
    # Rollback intact — no net new entries in the tool registry.
    assert len(tool_registry) == pre_count


def test_isolation_guarantee_with_all_five_fixtures(
    fake_plugin_entry_points,
    tmp_plugin_dir: Path,
    install_broken_fixture,
) -> None:
    """Four broken + one healthy: healthy still loads; broken ones surface as error.

    This is the canonical TEST-19 acceptance check: the isolation
    guarantee holds when broken plugins live next to healthy ones in
    the same discovery pass.
    """
    import sys

    sys.modules.pop("tests.fixtures.broken_plugins.import_raises", None)

    install_broken_fixture("bad_toml")
    install_broken_fixture("schema_fail")
    install_broken_fixture("import_raises")
    install_broken_fixture("tool_raises_registration")
    install_broken_fixture("healthy")

    tool_registry = ToolRegistry()
    registry = _run_full_pipeline(tool_registry, AdapterRegistry())

    healthy = registry.get("healthy")
    assert healthy is not None
    assert healthy.status == PLUGIN_STATUS_LOADED
    assert healthy.error_phase is None
    assert "hello_tool" in healthy.registered_tools
    # The hello_tool ended up in the master tool_registry.
    assert tool_registry.get("hello_tool") is not None

    for name, expected_phase in [
        ("bad_toml", "discover"),
        ("schema_fail", "validate"),
        ("import-raises", "load"),
        ("tool-raises-registration", "load"),
    ]:
        entry = registry.get(name)
        assert entry is not None, f"{name} not in registry; have {registry.names()!r}"
        assert entry.status == PLUGIN_STATUS_ERROR, f"{name} status={entry.status!r}"
        assert entry.error_phase == expected_phase, (
            f"{name} error_phase={entry.error_phase!r} expected {expected_phase!r}"
        )

    # Error view excludes the healthy plugin.
    error_names = {e.name for e in registry.error()}
    assert "healthy" not in error_names
    assert {"bad_toml", "schema_fail", "import-raises", "tool-raises-registration"} <= error_names

    # Enabled view contains only the healthy plugin.
    assert [e.name for e in registry.enabled()] == ["healthy"]


def test_discover_plugins_never_raises_with_all_broken_fixtures(
    fake_plugin_entry_points,
    tmp_plugin_dir: Path,
    install_broken_fixture,
) -> None:
    """The DISCOVERY-01 / ISOLATE-01 contract: discover_plugins() never raises out."""
    install_broken_fixture("bad_toml")
    install_broken_fixture("schema_fail")

    try:
        specs, errors = discover_plugins()
    except Exception as exc:
        pytest.fail(f"discover_plugins() raised: {type(exc).__name__}: {exc}")

    assert isinstance(specs, list)
    assert isinstance(errors, list)
    assert len(errors) >= 2
    error_phases = {e.error_phase for e in errors}
    assert {"discover", "validate"} <= error_phases
