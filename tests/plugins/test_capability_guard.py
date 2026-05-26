"""CapabilityGuard.wrap_tool_handler: default-deny enforcement at the wrap site.

The Phase 42 stub returned every handler unchanged; Phase 43 returns
a wrapper that raises PermissionDenied on missing grants. The
``__horus_required_caps__`` attribute set by ``require_capability``
is the discoverable marker the wrapper consults; handlers without
that attribute pass through unchanged (back-compat for tools that
opt out of the capability surface).
"""

from __future__ import annotations

import pytest

from horus_os.plugins.api import require_capability
from horus_os.plugins.capability_catalog import Capability
from horus_os.plugins.permissions import CapabilityGuard, PermissionDenied


def test_wrap_tool_handler_no_grant_raises() -> None:
    @require_capability(Capability.FILESYSTEM_READ)
    def handler(*, value: str) -> dict[str, str]:
        return {"echo": value}

    guard = CapabilityGuard("foo", granted_capabilities=set())
    wrapped = guard.wrap_tool_handler(handler)

    with pytest.raises(PermissionDenied) as exc_info:
        wrapped(value="ping")

    assert exc_info.value.plugin_name == "foo"
    assert exc_info.value.capability == "filesystem.read"


def test_wrap_tool_handler_with_grant_passes() -> None:
    @require_capability(Capability.FILESYSTEM_READ)
    def handler(*, value: str) -> dict[str, str]:
        return {"echo": value}

    guard = CapabilityGuard("foo", granted_capabilities={Capability.FILESYSTEM_READ})
    wrapped = guard.wrap_tool_handler(handler)

    assert wrapped(value="ping") == {"echo": "ping"}


def test_wrap_tool_handler_no_required_caps_passes_through() -> None:
    """Handlers with no decorator marker bypass the gate (opt-in design)."""
    def handler(*, value: str) -> dict[str, str]:
        return {"echo": value}

    guard = CapabilityGuard("foo", granted_capabilities=set())
    wrapped = guard.wrap_tool_handler(handler)

    # No marker → wrapped is the handler itself (pass-through).
    assert wrapped is handler
    assert wrapped(value="ping") == {"echo": "ping"}


def test_wrap_tool_handler_with_required_cap_kwarg_raises() -> None:
    """Explicit required_cap kwarg works for shim closures that bind one cap."""
    def handler() -> str:
        return "ok"

    guard = CapabilityGuard("foo", granted_capabilities=set())
    wrapped = guard.wrap_tool_handler(handler, required_cap=Capability.NET_OUTBOUND)

    with pytest.raises(PermissionDenied) as exc_info:
        wrapped()
    assert exc_info.value.capability == "net.outbound"


def test_permission_denied_str_format() -> None:
    """str(PermissionDenied) contains BOTH the plugin name and the capability."""
    exc = PermissionDenied("foo", "filesystem.read")
    s = str(exc)
    assert "foo" in s
    assert "filesystem.read" in s


def test_wrap_handler_preserves_required_caps_attribute() -> None:
    """Wrapper exposes the same __horus_required_caps__ for dashboard introspection."""
    @require_capability(Capability.FILESYSTEM_READ, Capability.SECRETS_READ)
    def handler() -> int:
        return 0

    guard = CapabilityGuard(
        "foo",
        granted_capabilities={Capability.FILESYSTEM_READ, Capability.SECRETS_READ},
    )
    wrapped = guard.wrap_tool_handler(handler)
    caps = getattr(wrapped, "__horus_required_caps__", ())
    assert tuple(caps) == (Capability.FILESYSTEM_READ, Capability.SECRETS_READ)


def test_capability_guard_granted_capabilities_property_is_frozenset() -> None:
    guard = CapabilityGuard(
        "foo", granted_capabilities={Capability.FILESYSTEM_READ}
    )
    assert isinstance(guard.granted_capabilities, frozenset)
    assert guard.granted_capabilities == frozenset({Capability.FILESYSTEM_READ})
    assert guard.plugin_name == "foo"


def test_capability_guard_phase42_signature_still_works() -> None:
    """Phase 42 callers that pass ``capabilities`` as a tuple still construct cleanly."""
    guard = CapabilityGuard("foo", ("filesystem.read",))
    assert guard.plugin_name == "foo"
    assert guard.capabilities == ("filesystem.read",)
    # No grants supplied → default-deny on any wrapped handler.
    assert guard.granted_capabilities == frozenset()
