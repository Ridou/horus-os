"""Pitfall 1: Default-allow capability grants normalize compromise.

See .planning/research/PITFALLS.md §"Pitfall 1" for the documented
threat model: any code path that defaults to "grant" instead of "deny"
makes plugin compromise a one-line refactor away. The Phase 43
``PermissionGate.resolve()`` partitioner and the ``CapabilityGuard``
default-deny enforcement at ``wrap_tool_handler`` together codify the
deny-first invariant; this regression test pins it down so a future
PR that flips the default fails before it can merge.

Three structural assertions:

1. The module constant ``DEFAULT_GRANT_POLICY`` literally equals
   ``"deny"`` — grep target for reviewers.
2. ``PermissionGate(db).resolve(spec)`` on a fresh DB (no grant rows)
   returns an empty granted set and a pending set covering every
   requested capability.
3. Calling a ``CapabilityGuard``-wrapped handler whose required cap is
   absent from the granted set raises ``PermissionDenied`` (Phase 43
   wrap-site enforcement).

The synthetic plugin spec comes from the tier-1 helper
``make_synthetic_plugin`` in ``tests/plugins/conftest.py``; no
discovery, no installer, no entry-point monkeypatch.
"""

from __future__ import annotations

import pytest

from horus_os.plugins.capability_catalog import Capability
from horus_os.plugins.permissions import (
    DEFAULT_GRANT_POLICY,
    CapabilityGuard,
    PermissionDenied,
    PermissionGate,
)
from horus_os.storage import Database
from tests.plugins.conftest import make_synthetic_plugin


def test_default_grant_policy_is_deny() -> None:
    """The module constant must literally be the string ``"deny"``."""
    assert DEFAULT_GRANT_POLICY == "deny"


def test_permission_gate_resolves_empty_grants_to_all_pending(
    pitfall_db: Database,
) -> None:
    """A fresh DB has no grant rows → every requested cap is pending."""
    spec, _module = make_synthetic_plugin(name="pitfall-01", capabilities=["filesystem.read"])
    gate = PermissionGate(pitfall_db)
    granted, pending = gate.resolve(spec)
    assert granted == set()
    assert pending == {Capability.FILESYSTEM_READ}


def test_capability_guard_raises_on_missing_grant() -> None:
    """A wrapped handler with no granted caps raises PermissionDenied."""
    guard = CapabilityGuard(
        plugin_name="pitfall-01",
        granted_capabilities=frozenset(),  # default-deny: nothing granted
    )

    def _handler() -> str:
        return "this should never run"

    wrapped = guard.wrap_tool_handler(_handler, required_cap=Capability.FILESYSTEM_READ)
    with pytest.raises(PermissionDenied) as excinfo:
        wrapped()
    assert excinfo.value.plugin_name == "pitfall-01"
    assert excinfo.value.capability == "filesystem.read"


def test_permission_gate_with_multiple_caps_all_pending(
    pitfall_db: Database,
) -> None:
    """Multi-cap spec on fresh DB: every cap lands in pending."""
    spec, _module = make_synthetic_plugin(
        name="pitfall-01-multi",
        capabilities=["filesystem.read", "net.outbound", "secrets.read"],
    )
    gate = PermissionGate(pitfall_db)
    granted, pending = gate.resolve(spec)
    assert granted == set()
    assert pending == {
        Capability.FILESYSTEM_READ,
        Capability.NET_OUTBOUND,
        Capability.SECRETS_READ,
    }
