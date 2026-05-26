"""PermissionGate.resolve: granted vs pending partition matrix.

PERMISSION-02 / Pitfall 5 (upgrade re-prompt) is the central behavior:
manifest_hash mismatch flips a previously-granted row to pending.

Five scenarios:
  * resolve_all_granted: every requested cap has a matching granted row.
  * resolve_first_install: no rows at all → every cap lands pending.
  * resolve_hash_mismatch: granted rows exist but for an old manifest_hash.
  * resolve_revoked_acts_as_deny: revoked rows are NOT granted.
  * resolve_partial: mixed grant matrix.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from horus_os.plugins.capability_catalog import Capability
from horus_os.plugins.permissions import PermissionGate
from horus_os.plugins.spec import CapabilityRequest, PluginSpec
from horus_os.storage import Database


def _make_db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "horus.sqlite3")
    db.init()
    return db


def _insert_grant(
    db: Database,
    plugin_name: str,
    plugin_version: str,
    capability: str,
    *,
    state: str,
    manifest_hash: str,
) -> None:
    with db._connect() as conn:
        # plugins row must exist first because plugin_capabilities FK CASCADEs from it.
        conn.execute(
            """
            INSERT OR IGNORE INTO plugins
                (name, version, manifest_hash, enabled, installed_at, source)
            VALUES (?, ?, ?, 1, '2026-05-26T00:00:00Z', 'filesystem')
            """,
            (plugin_name, plugin_version, manifest_hash),
        )
        conn.execute(
            """
            INSERT INTO plugin_capabilities
                (plugin_name, plugin_version, capability, manifest_hash, state, granted_at)
            VALUES (?, ?, ?, ?, ?, '2026-05-26T00:00:00Z')
            """,
            (plugin_name, plugin_version, capability, manifest_hash, state),
        )


def _make_spec(
    name: str,
    version: str,
    capabilities: tuple[str, ...],
    manifest_hash: str,
) -> PluginSpec:
    return PluginSpec(
        name=name,
        version=version,
        description="",
        author="",
        license="Apache-2.0",
        horus_os_compat=">=0.5,<0.6",
        homepage=None,
        issue_tracker=None,
        tool_entries=(),
        adapter_entries=(),
        capabilities=tuple(CapabilityRequest(name=c) for c in capabilities),
        source="filesystem",
        source_detail="",
        manifest_hash=manifest_hash,
    )


def test_resolve_all_granted(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    _insert_grant(db, "foo", "1.0", "filesystem.read",
                  state="granted", manifest_hash="hash1")
    _insert_grant(db, "foo", "1.0", "net.outbound",
                  state="granted", manifest_hash="hash1")

    spec = _make_spec("foo", "1.0", ("filesystem.read", "net.outbound"), "hash1")
    gate = PermissionGate(db)
    granted, pending = gate.resolve(spec)

    assert granted == {Capability.FILESYSTEM_READ, Capability.NET_OUTBOUND}
    assert pending == set()


def test_resolve_first_install(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    spec = _make_spec("foo", "1.0", ("filesystem.read", "secrets.read"), "hash1")

    gate = PermissionGate(db)
    granted, pending = gate.resolve(spec)

    assert granted == set()
    assert pending == {Capability.FILESYSTEM_READ, Capability.SECRETS_READ}


def test_resolve_hash_mismatch(tmp_path: Path) -> None:
    """PERMISSION-02 / Pitfall 5: previously granted but new manifest_hash → pending."""
    db = _make_db(tmp_path)
    _insert_grant(db, "foo", "1.0", "filesystem.read",
                  state="granted", manifest_hash="old_hash")

    spec = _make_spec("foo", "1.0", ("filesystem.read",), "new_hash")
    gate = PermissionGate(db)
    granted, pending = gate.resolve(spec)

    assert granted == set()
    assert pending == {Capability.FILESYSTEM_READ}


def test_resolve_revoked_acts_as_deny(tmp_path: Path) -> None:
    """A revoked row must NOT count as granted; it lands in pending."""
    db = _make_db(tmp_path)
    _insert_grant(db, "foo", "1.0", "net.outbound",
                  state="revoked", manifest_hash="hash1")

    spec = _make_spec("foo", "1.0", ("net.outbound",), "hash1")
    gate = PermissionGate(db)
    granted, pending = gate.resolve(spec)

    assert granted == set()
    assert pending == {Capability.NET_OUTBOUND}


def test_resolve_partial(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    _insert_grant(db, "foo", "1.0", "filesystem.read",
                  state="granted", manifest_hash="hash1")
    _insert_grant(db, "foo", "1.0", "net.outbound",
                  state="granted", manifest_hash="hash1")
    # secrets.read is requested but has no row at all → pending.

    spec = _make_spec("foo", "1.0",
                      ("filesystem.read", "net.outbound", "secrets.read"),
                      "hash1")
    gate = PermissionGate(db)
    granted, pending = gate.resolve(spec)

    assert granted == {Capability.FILESYSTEM_READ, Capability.NET_OUTBOUND}
    assert pending == {Capability.SECRETS_READ}


def test_resolve_unknown_capability_raises_value_error(tmp_path: Path) -> None:
    """A spec requesting a name outside the closed enum fails early."""
    db = _make_db(tmp_path)
    spec = _make_spec("foo", "1.0", ("not_a_real_capability",), "hash1")
    gate = PermissionGate(db)
    with pytest.raises(ValueError):
        gate.resolve(spec)
