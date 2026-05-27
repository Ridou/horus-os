"""In-process tests for the four reference-plugin scenarios.

Covers:

(a) ``echo_text_tool`` raises ``PermissionDenied`` without
    ``Capability.FILESYSTEM_READ``, returns file content with it.
(b) ``lookup_secret_tool`` raises ``PermissionDenied`` without
    ``Capability.SECRETS_READ``; returns None on a missing env var
    and the env var value when set.
(c) ``ExampleAdapter.start(ctx)`` and ``stop()`` each complete inside
    the Phase 43 ``asyncio.wait_for(timeout=2.0)`` ceiling.
(d) The shipped ``horus-plugin.toml`` validates against
    ``MANIFEST_V1_SCHEMA`` and yields a ``PluginSpec`` with two tools
    and one adapter.

These tests run under the host repo's pytest invocation. The plugin's
``src/`` is TEST-21-locked to ``from horus_os.plugins.api`` imports;
test code lives under ``tests/`` and is exempt by design — these tests
import a small amount of internal surface
(``horus_os.plugins.permissions`` for ``CapabilityGuard``) that plugin
PRODUCTION code is not allowed to touch.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest
from horus_os_example_plugin.adapter import ExampleAdapter
from horus_os_example_plugin.tools import echo_text_tool, lookup_secret_tool

# Test-only internal imports (exempt from TEST-21; the surface lock
# applies to src/, not tests/).
from horus_os.plugins.api import Capability, PluginContext
from horus_os.plugins.manifest import validate_manifest
from horus_os.plugins.permissions import CapabilityGuard, PermissionDenied

# Resolve the underlying impl callable from each Tool factory once, so
# the tier-1 tests can drive the function directly without going through
# the loader's CapabilityGuard wrap site (which is the loader-level
# integration concern, not the per-handler unit concern).
_echo_impl = echo_text_tool().handler
_lookup_impl = lookup_secret_tool().handler

REF_PLUGIN_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REF_PLUGIN_ROOT / "src" / "horus_os_example_plugin" / "horus-plugin.toml"


def _build_context(granted: set[Capability], tmp_path: Path) -> PluginContext:
    """Build a ``PluginContext`` for tier-1 in-process tests."""
    guard = CapabilityGuard(
        plugin_name="horus-os-example-plugin",
        capabilities=("filesystem.read", "secrets.read"),
        granted_capabilities=granted,
    )
    return PluginContext(
        plugin_name="horus-os-example-plugin",
        plugin_version="0.1.0",
        data_dir=tmp_path,
        guard=guard,
    )


def test_echo_text_tool_denied_without_grant(tmp_path: Path) -> None:
    """Scenario (a) — denied path: missing FILESYSTEM_READ raises PermissionDenied."""
    ctx = _build_context(granted=set(), tmp_path=tmp_path)
    target = tmp_path / "secret.txt"
    target.write_text("hello", encoding="utf-8")
    with pytest.raises(PermissionDenied) as exc_info:
        _echo_impl(ctx, str(target))
    assert exc_info.value.plugin_name == "horus-os-example-plugin"
    assert exc_info.value.capability == "filesystem.read"


def test_echo_text_tool_returns_content_with_grant(tmp_path: Path) -> None:
    """Scenario (a) — granted path: returns the file's text content."""
    ctx = _build_context(granted={Capability.FILESYSTEM_READ}, tmp_path=tmp_path)
    target = tmp_path / "note.txt"
    target.write_text("reference plugin payload", encoding="utf-8")
    result = _echo_impl(ctx, str(target))
    assert result == "reference plugin payload"


def test_lookup_secret_tool_denied_and_granted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scenario (b) — denied raises; granted returns None on missing key and str when set."""
    # Denied path.
    ctx_denied = _build_context(granted=set(), tmp_path=tmp_path)
    with pytest.raises(PermissionDenied) as exc_info:
        _lookup_impl(ctx_denied, "HORUS_OS_EXAMPLE_KEY")
    assert exc_info.value.capability == "secrets.read"

    # Granted path with missing key -> None (not an exception).
    monkeypatch.delenv("HORUS_OS_EXAMPLE_KEY", raising=False)
    ctx_granted = _build_context(granted={Capability.SECRETS_READ}, tmp_path=tmp_path)
    assert _lookup_impl(ctx_granted, "HORUS_OS_EXAMPLE_KEY") is None

    # Granted path with key set -> the env var value.
    monkeypatch.setenv("HORUS_OS_EXAMPLE_KEY", "ref-value")
    assert _lookup_impl(ctx_granted, "HORUS_OS_EXAMPLE_KEY") == "ref-value"


def test_example_adapter_start_stop_bounded(tmp_path: Path) -> None:
    """Scenario (c) — start and stop each complete inside the 2-second ceiling."""
    adapter = ExampleAdapter()
    assert adapter.name == "example_adapter"

    # Use a synthetic AdapterContext-shaped object; ExampleAdapter does
    # not introspect any field of the context in start/stop, so a bare
    # object suffices for this lifecycle-timing test.
    ctx = object()

    async def _drive_lifecycle() -> tuple[float, float]:
        t0 = time.perf_counter()
        await asyncio.wait_for(adapter.start(ctx), timeout=2.0)
        t_start = time.perf_counter() - t0
        t1 = time.perf_counter()
        await asyncio.wait_for(adapter.stop(), timeout=2.0)
        t_stop = time.perf_counter() - t1
        return t_start, t_stop

    t_start, t_stop = asyncio.run(_drive_lifecycle())
    # Each hook completes in milliseconds in practice; the contract is
    # "inside 2 seconds" but we assert a tighter 1.5s to catch drift.
    assert t_start < 1.5, f"start took {t_start:.3f}s, expected < 1.5s"
    assert t_stop < 1.5, f"stop took {t_stop:.3f}s, expected < 1.5s"


def test_manifest_validates_with_two_tools_and_one_adapter() -> None:
    """Scenario (d) — manifest round-trips through MANIFEST_V1_SCHEMA."""
    assert MANIFEST_PATH.is_file(), f"manifest missing: {MANIFEST_PATH}"
    spec = validate_manifest(MANIFEST_PATH.read_bytes())
    assert spec.name == "horus-os-example-plugin"
    assert spec.version == "0.1.0"
    assert {c.name for c in spec.capabilities} == {
        "filesystem.read",
        "secrets.read",
    }
    tool_names = {t[0] for t in spec.tool_entries}
    assert tool_names == {"echo_text_tool", "lookup_secret_tool"}
    adapter_names = {a[0] for a in spec.adapter_entries}
    assert adapter_names == {"example_adapter"}
