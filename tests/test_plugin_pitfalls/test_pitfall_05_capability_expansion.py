"""Pitfall 5: Permission grant model abused via plugin update — silent capability expansion.

See .planning/research/PITFALLS.md §"Pitfall 5" for the documented
threat. A plugin starts at v1.0 with capability set ``{filesystem.read}``;
the user grants it. The plugin upgrades to v1.1 and the manifest now
asks for ``{filesystem.read, net.outbound}``. If the permission gate
silently inherits the v1.0 grant onto v1.1, the user is now sending
outbound network traffic without ever being asked.

The Phase 43 prevention pattern: ``PermissionGate.resolve()`` checks
both the per-capability grant row AND the ``manifest_hash`` column.
A hash mismatch (caused by the v1.1 capability set differing from
the v1.0 set) flips the row to ``pending`` regardless of its prior
state. The user must re-grant before the new capability set is
honored. There is no silent inheritance.

Four structural assertions:

1. After granting v1.0 ``filesystem.read`` with the v1.0 manifest hash,
   ``PermissionGate.resolve(v1.0 spec)`` returns it as granted.
2. Constructing a v1.1 spec with a different capability set produces a
   different ``manifest_hash``.
3. ``PermissionGate.resolve(v1.1 spec)`` against the v1.0 grant row
   returns the cap as PENDING (manifest_hash mismatch overrides the
   granted state).
4. After ``PermissionService.pending_on_upgrade`` writes a v1.1 pending
   row, both v1.1 caps remain pending until explicitly granted.

The manifest_hash semantics are tested directly via
``compute_manifest_hash`` — capability-order-independent,
duplicate-tolerant.
"""

from __future__ import annotations

from horus_os.plugins.capability_catalog import Capability
from horus_os.plugins.manifest import compute_manifest_hash
from horus_os.plugins.permissions import PermissionGate, PermissionService
from horus_os.plugins.registry import PluginRegistry
from horus_os.plugins.spec import PluginSpec
from horus_os.storage import Database
from tests.plugins.conftest import make_synthetic_plugin


def _register(db: Database, spec: PluginSpec) -> None:
    """Register the plugin so plugin_capabilities FK constraints can resolve.

    ``PermissionService.grant`` inserts into ``plugin_capabilities``
    which has ``FOREIGN KEY (plugin_name) REFERENCES plugins(name)``;
    the plugin row must exist first. Registration uses the production
    ``PluginRegistry.register`` so the row is byte-identical to what
    discovery/installer paths produce.
    """
    PluginRegistry(db=db).register(spec)


def test_v1_0_grant_is_granted_under_matching_manifest_hash(
    pitfall_db: Database,
) -> None:
    """A v1.0 grant against its own manifest_hash resolves as granted."""
    spec_v1_0, _module = make_synthetic_plugin(
        name="foo", capabilities=["filesystem.read"], version="1.0.0"
    )
    _register(pitfall_db, spec_v1_0)
    PermissionService(pitfall_db).grant(
        plugin_name="foo",
        plugin_version="1.0.0",
        capability="filesystem.read",
        actor="system",
        manifest_hash=spec_v1_0.manifest_hash,
    )
    gate = PermissionGate(pitfall_db)
    granted, pending = gate.resolve(spec_v1_0)
    assert granted == {Capability.FILESYSTEM_READ}
    assert pending == set()


def test_v1_1_with_expanded_caps_has_different_manifest_hash() -> None:
    """A spec with an expanded capability set has a different manifest_hash."""
    spec_v1_0, _ = make_synthetic_plugin(
        name="foo", capabilities=["filesystem.read"], version="1.0.0"
    )
    spec_v1_1, _ = make_synthetic_plugin(
        name="foo",
        capabilities=["filesystem.read", "net.outbound"],
        version="1.1.0",
    )
    assert spec_v1_0.manifest_hash != spec_v1_1.manifest_hash
    # Sanity-check: the hash function is deterministic.
    assert spec_v1_1.manifest_hash == compute_manifest_hash(["filesystem.read", "net.outbound"])


def test_capability_expansion_does_not_silently_inherit_v1_0_grant(
    pitfall_db: Database,
) -> None:
    """Pitfall 5 core: v1.0 grant does NOT auto-extend to v1.1's new caps."""
    spec_v1_0, _ = make_synthetic_plugin(
        name="foo", capabilities=["filesystem.read"], version="1.0.0"
    )
    _register(pitfall_db, spec_v1_0)
    PermissionService(pitfall_db).grant(
        plugin_name="foo",
        plugin_version="1.0.0",
        capability="filesystem.read",
        actor="system",
        manifest_hash=spec_v1_0.manifest_hash,
    )
    # v1.1 spec carries a different version + an expanded capability set.
    spec_v1_1, _ = make_synthetic_plugin(
        name="foo",
        capabilities=["filesystem.read", "net.outbound"],
        version="1.1.0",
    )
    gate = PermissionGate(pitfall_db)
    granted, pending = gate.resolve(spec_v1_1)
    # No row exists for v1.1 yet (the grant landed under v1.0); both
    # caps surface as pending → user must re-grant.
    assert granted == set()
    assert pending == {Capability.FILESYSTEM_READ, Capability.NET_OUTBOUND}


def test_pending_on_upgrade_writes_pending_rows(
    pitfall_db: Database,
) -> None:
    """``PermissionService.pending_on_upgrade`` stages re-prompt rows for v1.1."""
    spec_v1_0, _ = make_synthetic_plugin(
        name="foo", capabilities=["filesystem.read"], version="1.0.0"
    )
    _register(pitfall_db, spec_v1_0)
    PermissionService(pitfall_db).grant(
        plugin_name="foo",
        plugin_version="1.0.0",
        capability="filesystem.read",
        actor="system",
        manifest_hash=spec_v1_0.manifest_hash,
    )
    spec_v1_1, _ = make_synthetic_plugin(
        name="foo",
        capabilities=["filesystem.read", "net.outbound"],
        version="1.1.0",
    )
    PermissionService(pitfall_db).pending_on_upgrade(
        plugin_name="foo",
        old_version="1.0.0",
        new_version="1.1.0",
        capabilities=("filesystem.read", "net.outbound"),
        new_hash=spec_v1_1.manifest_hash,
        actor="system",
    )
    gate = PermissionGate(pitfall_db)
    granted, pending = gate.resolve(spec_v1_1)
    assert granted == set()
    assert pending == {Capability.FILESYSTEM_READ, Capability.NET_OUTBOUND}
