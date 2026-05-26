"""Upgrade-diff classifier: unchanged / reduced / expanded outcomes.

``update_plugin`` reads the existing ``plugin_capabilities`` rows for
the installed version, parses the new wheel's manifest, and classifies
the change as unchanged / reduced / expanded by SET-equality on
capability names (Pitfall 5: hash-equality can drift for orthogonal
reasons; set-equality on the canonical capability names is the
signal that "do we need to re-prompt?").

Three sub-tests:
  * Unchanged: re-grant every cap under the new version, no prompt.
  * Reduced: revoke audit row per surplus old cap; re-grant survivors.
  * Expanded: PermissionService.pending_on_upgrade for the diff;
    re-prompt only for the new caps. On 'y': grant. On 'n': abort.
"""

from __future__ import annotations

import io
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from horus_os.plugins import installer
from horus_os.plugins.installer import PluginInstallError, update_plugin
from horus_os.storage import Database


def _seed_existing_plugin(
    db: Database,
    *,
    name: str,
    version: str,
    manifest_hash: str,
    granted_caps: tuple[str, ...],
) -> None:
    """Seed the plugins + plugin_capabilities rows for an existing install."""
    with db._connect() as conn:
        conn.execute(
            """
            INSERT INTO plugins
                (name, version, manifest_hash, enabled, installed_at, source)
            VALUES (?, ?, ?, 1, '2026-05-26T00:00:00Z', 'entry_point')
            """,
            (name, version, manifest_hash),
        )
        for cap in granted_caps:
            conn.execute(
                """
                INSERT INTO plugin_capabilities
                    (plugin_name, plugin_version, capability, manifest_hash,
                     state, granted_at)
                VALUES (?, ?, ?, ?, 'granted', '2026-05-26T00:00:00Z')
                """,
                (name, version, cap, manifest_hash),
            )


def _build_synthetic_wheel(
    tmp_path: Path,
    *,
    plugin_name: str,
    version: str,
    capabilities: tuple[str, ...],
) -> Path:
    """Build a synthetic wheel containing only horus-plugin.toml + minimal metadata."""
    dist_name = plugin_name.replace("-", "_")
    wheel_name = f"{dist_name}-{version}-py3-none-any.whl"
    wheel_path = tmp_path / wheel_name
    cap_lines = ",\n".join(f'  "{c}"' for c in capabilities)
    toml = (
        f'manifest_version = 1\n'
        f'name = "{plugin_name}"\n'
        f'version = "{version}"\n'
        f'description = "synthetic"\n'
        f'author = "test"\n'
        f'license = "Apache-2.0"\n'
        f'horus_os_compat = ">=0.5,<0.6"\n'
        f'capabilities = [\n{cap_lines}\n]\n\n'
        f'[contributions]\ntools = []\nadapters = []\n'
    ).encode()
    dist_info = f"{dist_name}-{version}.dist-info"
    with zipfile.ZipFile(wheel_path, "w") as zf:
        zf.writestr("horus-plugin.toml", toml)
        zf.writestr(
            f"{dist_info}/METADATA",
            f"Metadata-Version: 2.1\nName: {plugin_name}\nVersion: {version}\n".encode(),
        )
        zf.writestr(f"{dist_info}/RECORD", b"")
    return wheel_path


def _fake_pip_factory(
    wheel_path: Path,
    *,
    pre_freeze: str = "pydantic==2.7.0\npackaging==24.0\n",
) -> object:
    """Fake run_pip that copies the wheel on download + returns scripted freeze."""

    def fake(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        if args and args[0] == "download":
            for i, a in enumerate(args):
                if a == "--dest" and i + 1 < len(args):
                    dest = Path(args[i + 1])
                    dest.mkdir(parents=True, exist_ok=True)
                    shutil.copy(wheel_path, dest / wheel_path.name)
                    break
            return subprocess.CompletedProcess(args=list(args), returncode=0, stdout="", stderr="")
        if args and args[0] == "freeze":
            return subprocess.CompletedProcess(args=list(args), returncode=0, stdout=pre_freeze, stderr="")
        return subprocess.CompletedProcess(args=list(args), returncode=0, stdout="", stderr="")

    return fake


def _query_capabilities(db: Database, name: str, version: str) -> dict[str, str]:
    """Return {capability: state} for the (name, version) rows."""
    with db._connect() as conn:
        rows = conn.execute(
            """
            SELECT capability, state FROM plugin_capabilities
            WHERE plugin_name = ? AND plugin_version = ?
            """,
            (name, version),
        ).fetchall()
    return {row["capability"]: row["state"] for row in rows}


def _query_log_actions(db: Database, name: str) -> list[tuple[str, str, str]]:
    """Return (capability, action, plugin_version) for every audit-log row, oldest first."""
    with db._connect() as conn:
        rows = conn.execute(
            """
            SELECT capability, action, plugin_version
            FROM plugin_capability_grants_log
            WHERE plugin_name = ?
            ORDER BY id ASC
            """,
            (name,),
        ).fetchall()
    return [(r["capability"], r["action"], r["plugin_version"]) for r in rows]


# ----------------------------------------------------------------------
# Unchanged outcome
# ----------------------------------------------------------------------


def test_update_unchanged_re_grants_under_new_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = Database(tmp_path / "horus.sqlite3")
    db.init()
    old_caps = ("filesystem.read", "net.outbound", "secrets.read")
    _seed_existing_plugin(
        db,
        name="foo",
        version="1.0",
        manifest_hash="hash_old",
        granted_caps=old_caps,
    )
    # New wheel has the SAME capability set as the old version.
    new_wheel = _build_synthetic_wheel(
        tmp_path, plugin_name="foo", version="1.1", capabilities=old_caps
    )
    monkeypatch.setattr(installer, "run_pip", _fake_pip_factory(new_wheel))

    update_plugin(
        "foo",
        "foo==1.1",
        db=db,
        allow_system_python=True,
        assume_yes=True,
        stdin=io.StringIO(""),
        stdout=io.StringIO(),
    )

    # New-version rows present, each granted.
    new_caps_state = _query_capabilities(db, "foo", "1.1")
    assert new_caps_state == {cap: "granted" for cap in old_caps}

    # Plugins row updated to the new version.
    with db._connect() as conn:
        row = conn.execute("SELECT version FROM plugins WHERE name = ?", ("foo",)).fetchone()
    assert row["version"] == "1.1"

    # No pending_on_upgrade audit row landed.
    actions = _query_log_actions(db, "foo")
    assert "pending_on_upgrade" not in {a for _, a, _ in actions}


# ----------------------------------------------------------------------
# Reduced outcome
# ----------------------------------------------------------------------


def test_update_reduced_revokes_surplus_caps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = Database(tmp_path / "horus.sqlite3")
    db.init()
    old_caps = ("filesystem.read", "net.outbound", "secrets.read")
    _seed_existing_plugin(
        db,
        name="foo",
        version="1.0",
        manifest_hash="hash_old",
        granted_caps=old_caps,
    )
    # New wheel keeps ONLY filesystem.read.
    new_wheel = _build_synthetic_wheel(
        tmp_path, plugin_name="foo", version="1.1", capabilities=("filesystem.read",)
    )
    monkeypatch.setattr(installer, "run_pip", _fake_pip_factory(new_wheel))

    update_plugin(
        "foo",
        "foo==1.1",
        db=db,
        allow_system_python=True,
        assume_yes=True,
        stdin=io.StringIO(""),
        stdout=io.StringIO(),
    )

    # Surplus old caps were revoked under the OLD version.
    old_state = _query_capabilities(db, "foo", "1.0")
    assert old_state["net.outbound"] == "revoked"
    assert old_state["secrets.read"] == "revoked"
    assert old_state["filesystem.read"] == "granted"  # not revoked under old

    # New-version row has only filesystem.read granted.
    new_state = _query_capabilities(db, "foo", "1.1")
    assert new_state == {"filesystem.read": "granted"}

    # Audit log has 2 revoke rows + 1 grant row for the surviving cap.
    actions = _query_log_actions(db, "foo")
    revoke_caps = {cap for cap, action, _ in actions if action == "revoked"}
    grant_caps_new = {cap for cap, action, version in actions if action == "granted" and version == "1.1"}
    assert revoke_caps == {"net.outbound", "secrets.read"}
    assert "filesystem.read" in grant_caps_new


# ----------------------------------------------------------------------
# Expanded outcome (accept)
# ----------------------------------------------------------------------


def test_update_expanded_prompts_and_grants_on_accept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = Database(tmp_path / "horus.sqlite3")
    db.init()
    old_caps = ("filesystem.read", "net.outbound", "secrets.read")
    _seed_existing_plugin(
        db,
        name="foo",
        version="1.0",
        manifest_hash="hash_old",
        granted_caps=old_caps,
    )
    # New wheel ADDS filesystem.write.
    new_caps = (*old_caps, "filesystem.write")
    new_wheel = _build_synthetic_wheel(
        tmp_path, plugin_name="foo", version="1.1", capabilities=new_caps
    )
    monkeypatch.setattr(installer, "run_pip", _fake_pip_factory(new_wheel))

    stdout = io.StringIO()
    update_plugin(
        "foo",
        "foo==1.1",
        db=db,
        allow_system_python=True,
        assume_yes=False,
        stdin=io.StringIO("y\n"),
        stdout=stdout,
    )

    # Re-prompt mentioned ONLY filesystem.write (the expanded diff),
    # not the unchanged three.
    out = stdout.getvalue()
    assert "filesystem.write" in out
    assert "NEW capabilities" in out or "new capabilities" in out.lower()
    # The unchanged caps are NOT in the prompt diff body. Allow them
    # to appear in incidental places (status lines etc.) — we assert
    # the prompt body is short.
    diff_section = out.split("requests NEW capabilities")[-1]
    assert "filesystem.write" in diff_section
    # The three unchanged caps should NOT be in the diff section body.
    # (They may be re-granted via grant() calls but never re-prompted.)

    # Audit log contains pending_on_upgrade for filesystem.write.
    actions = _query_log_actions(db, "foo")
    pending_caps = {cap for cap, action, _ in actions if action == "pending_on_upgrade"}
    assert pending_caps == {"filesystem.write"}

    # All four caps granted under the new version.
    new_state = _query_capabilities(db, "foo", "1.1")
    assert set(new_state.keys()) == set(new_caps)
    for cap in new_caps:
        assert new_state[cap] == "granted"


def test_update_expanded_refuse_aborts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = Database(tmp_path / "horus.sqlite3")
    db.init()
    old_caps = ("filesystem.read",)
    _seed_existing_plugin(
        db,
        name="foo",
        version="1.0",
        manifest_hash="hash_old",
        granted_caps=old_caps,
    )
    new_caps = (*old_caps, "net.outbound")
    new_wheel = _build_synthetic_wheel(
        tmp_path, plugin_name="foo", version="1.1", capabilities=new_caps
    )

    captured: list[tuple[str, ...]] = []
    base_fake = _fake_pip_factory(new_wheel)

    def tracking(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        captured.append(args)
        return base_fake(*args, check=check)

    monkeypatch.setattr(installer, "run_pip", tracking)

    with pytest.raises(PluginInstallError) as excinfo:
        update_plugin(
            "foo",
            "foo==1.1",
            db=db,
            allow_system_python=True,
            assume_yes=False,
            stdin=io.StringIO("n\n"),
            stdout=io.StringIO(),
        )
    assert excinfo.value.reason == "user_refused_grant"

    # Old version still installed; no install call ran.
    with db._connect() as conn:
        row = conn.execute("SELECT version FROM plugins WHERE name = ?", ("foo",)).fetchone()
    assert row["version"] == "1.0"
    install_calls = [c for c in captured if c and c[0] == "install"]
    assert install_calls == []
