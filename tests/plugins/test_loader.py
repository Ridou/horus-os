"""PluginLoader success-path + name-collision coverage.

Cases:

* (a) PluginSpec with one tool_entry -> loader registers a wrapped Tool;
  ``tool_registry.get(name)`` is not None; the wrapped handler is
  callable and returns the underlying tool's result (pass-through guard).
* (b) PluginSpec with one adapter_entry -> loader registers the adapter
  via ``adapter_registry.register``; entry visible in the registry.
* (c) PluginSpec with both a tool and an adapter -> both register in
  one ``load()`` call.
* (d) PluginSpec with a tool whose name collides with an already-registered
  tool -> ``ToolRegistry.register`` raises ValueError; loader catches,
  returns PluginLoadResult(status='error', error_phase='load', error
  includes 'already registered'); rollback unregisters every tool that
  partial-registered earlier in the same load() call.
"""

from __future__ import annotations

from horus_os.adapters.base import AdapterRegistry
from horus_os.plugins import LOAD_PHASE_ORDER, PluginLoader, PluginLoadResult
from horus_os.plugins.spec import CapabilityRequest, PluginSpec
from horus_os.tools.registry import ToolRegistry
from horus_os.types import Tool


def _make_spec(
    *,
    name: str = "healthy",
    tool_entries: tuple[tuple[str, str], ...] = (),
    adapter_entries: tuple[tuple[str, str], ...] = (),
    source: str = "entry_point",
) -> PluginSpec:
    """Construct a minimal PluginSpec for loader testing."""
    return PluginSpec(
        name=name,
        version="0.1.0",
        description="loader test fixture",
        author="horus-os contributors",
        license="Apache-2.0",
        horus_os_compat=">=0.5,<0.6",
        homepage=None,
        issue_tracker=None,
        tool_entries=tool_entries,
        adapter_entries=adapter_entries,
        capabilities=(CapabilityRequest(name="filesystem.read"),),
        source=source,
        source_detail="loader test",
        manifest_hash="deadbeef",
    )


def test_load_phase_order_is_canonical_tuple() -> None:
    assert LOAD_PHASE_ORDER == (
        "discover",
        "validate",
        "permission",
        "load",
        "start",
        "stop",
    )


def test_load_returns_result_dataclass_shape() -> None:
    """Smoke check: loading a no-op spec returns a valid PluginLoadResult."""
    spec = _make_spec()
    loader = PluginLoader(tool_registry=ToolRegistry(), adapter_registry=AdapterRegistry())
    result = loader.load(spec)
    assert isinstance(result, PluginLoadResult)
    assert result.status == "loaded"
    assert result.error_phase is None
    assert result.error is None
    assert result.registered_tools == ()
    assert result.registered_adapters == ()


def test_load_registers_one_tool() -> None:
    """Case (a): a spec with one tool_entry registers the tool."""
    spec = _make_spec(
        tool_entries=(("hello_tool", "tests.fixtures.broken_plugins.healthy:make_tool"),)
    )
    tool_registry = ToolRegistry()
    adapter_registry = AdapterRegistry()
    loader = PluginLoader(tool_registry=tool_registry, adapter_registry=adapter_registry)

    result = loader.load(spec)

    assert result.status == "loaded"
    assert result.registered_tools == ("hello_tool",)
    assert result.registered_adapters == ()
    tool = tool_registry.get("hello_tool")
    assert tool is not None
    # The wrapped handler is callable and returns the underlying tool's output.
    output = tool.handler(value="ping")  # type: ignore[misc]
    assert output == {"echo": {"value": "ping"}}


def test_load_rolls_back_on_name_collision() -> None:
    """Case (d): tool name collision -> error_phase='load', rollback intact.

    Pre-register a tool named ``hello_tool``; the loader's
    ``tool_registry.register`` call raises ValueError; the loader
    catches, returns ``PluginLoadResult(status='error', error_phase='load')``,
    and rolls back any tool that may have partial-registered earlier
    in the same load() call.
    """
    tool_registry = ToolRegistry()
    pre_existing = Tool(
        name="hello_tool",
        description="pre-existing",
        parameters={"type": "object", "properties": {}},
        handler=lambda **_kw: "pre-existing",
    )
    tool_registry.register(pre_existing)
    assert tool_registry.get("hello_tool") is pre_existing

    spec = _make_spec(
        tool_entries=(("hello_tool", "tests.fixtures.broken_plugins.healthy:make_tool"),)
    )
    loader = PluginLoader(tool_registry=tool_registry, adapter_registry=AdapterRegistry())

    result = loader.load(spec)

    assert result.status == "error"
    assert result.error_phase == "load"
    assert result.error is not None
    assert "already registered" in result.error
    assert result.registered_tools == ()
    assert result.registered_adapters == ()
    # The pre-existing tool is untouched; the collision attempt did not
    # overwrite it. The registry size stayed at 1 — no net change.
    assert tool_registry.get("hello_tool") is pre_existing
    assert len(tool_registry) == 1


def test_load_rolls_back_partial_registrations() -> None:
    """A spec with two tools where the second collides -> the first is rolled back.

    We register a tool named ``hello_tool`` first; the plugin's spec
    declares ``new_tool`` followed by ``hello_tool``. The loader
    registers ``new_tool``, then the collision on ``hello_tool`` fires,
    and rollback walks the list in reverse to unregister ``new_tool``.
    Net change to the registry: zero.
    """
    tool_registry = ToolRegistry()
    pre_existing = Tool(
        name="hello_tool",
        description="pre-existing",
        parameters={"type": "object", "properties": {}},
        handler=lambda **_kw: None,
    )
    tool_registry.register(pre_existing)
    assert len(tool_registry) == 1

    spec = _make_spec(
        tool_entries=(
            # First registers cleanly; gets rolled back on the collision.
            ("new_tool", "tests.plugins._loader_partial_fixture:make_new_tool"),
            # Second collides; triggers rollback.
            ("hello_tool", "tests.fixtures.broken_plugins.healthy:make_tool"),
        )
    )
    loader = PluginLoader(tool_registry=tool_registry, adapter_registry=AdapterRegistry())

    result = loader.load(spec)
    assert result.status == "error"
    assert result.error_phase == "load"
    # Net change to registry: zero (the partial registration was rolled back).
    assert len(tool_registry) == 1
    assert tool_registry.get("new_tool") is None
    assert tool_registry.get("hello_tool") is pre_existing


def test_load_failure_on_unimportable_module() -> None:
    """Spec pointing at a module that does not exist -> error_phase='load'.

    Mirrors the import-failure path the import_raises fixture exercises
    via test_loader_isolation.py, but uses a synthetic entry_point so
    the test does not depend on the fixture's filesystem layout.
    """
    spec = _make_spec(tool_entries=(("ghost_tool", "tests.plugins._nonexistent_module:make_tool"),))
    loader = PluginLoader(tool_registry=ToolRegistry(), adapter_registry=AdapterRegistry())

    result = loader.load(spec)

    assert result.status == "error"
    assert result.error_phase == "load"
    # The exception type makes it into the error string.
    assert "ModuleNotFoundError" in result.error or "ImportError" in result.error


def test_load_failure_on_factory_returning_wrong_type() -> None:
    """A factory that returns something other than Tool -> error_phase='load'."""
    spec = _make_spec(
        tool_entries=(("non_tool", "tests.plugins._loader_partial_fixture:make_non_tool"),)
    )
    loader = PluginLoader(tool_registry=ToolRegistry(), adapter_registry=AdapterRegistry())

    result = loader.load(spec)

    assert result.status == "error"
    assert result.error_phase == "load"
    assert "TypeError" in result.error


def test_load_failure_when_factory_tool_name_mismatch() -> None:
    """A factory that returns a Tool with a different name than declared -> ValueError."""
    spec = _make_spec(
        tool_entries=(
            ("declared_name", "tests.plugins._loader_partial_fixture:make_mismatched_tool"),
        )
    )
    loader = PluginLoader(tool_registry=ToolRegistry(), adapter_registry=AdapterRegistry())

    result = loader.load(spec)

    assert result.status == "error"
    assert result.error_phase == "load"
    assert "must match" in result.error
