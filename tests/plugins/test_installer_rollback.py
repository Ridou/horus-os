"""Phase D + E failure rollback: pip uninstall -y + DELETE plugins row.

When Phase E's ``discover_plugins`` call raises (or the verify gate
otherwise fails), the installer:

1. Calls ``pip uninstall -y <name>`` to undo the install.
2. DELETEs the plugins row (CASCADE removes plugin_capabilities + plugin_status).
3. Re-raises the PluginInstallError.

Post-rollback ``pip freeze`` sha256 must equal the pre-install
snapshot. The test simulates the freeze hash equality by having the
fake run_pip return identical freeze stdout on pre- and post-rollback
calls.
"""

from __future__ import annotations

import hashlib
import io
import shutil
import subprocess
from pathlib import Path

import pytest

from horus_os.plugins import installer
from horus_os.plugins.installer import PluginInstallError, install_plugin
from horus_os.storage import Database


def _make_db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "horus.sqlite3")
    db.init()
    return db


def test_phase_e_failure_triggers_rollback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    installer_fixture_wheels: dict[str, Path],
) -> None:
    db = _make_db(tmp_path)
    clean_wheel = installer_fixture_wheels["wheel_clean"]

    captured: list[tuple[str, ...]] = []
    state = {"installed": False}
    pre_freeze = "pydantic==2.7.0\npackaging==24.0\n"
    post_freeze = "pydantic==2.7.0\npackaging==24.0\nhorus-example-clean==0.1.0\n"

    def fake(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        captured.append(args)
        if args and args[0] == "download":
            for i, a in enumerate(args):
                if a == "--dest" and i + 1 < len(args):
                    dest = Path(args[i + 1])
                    dest.mkdir(parents=True, exist_ok=True)
                    shutil.copy(clean_wheel, dest / clean_wheel.name)
                    break
            return subprocess.CompletedProcess(args=list(args), returncode=0, stdout="", stderr="")
        if args and args[0] == "freeze":
            stdout = post_freeze if state["installed"] else pre_freeze
            return subprocess.CompletedProcess(
                args=list(args), returncode=0, stdout=stdout, stderr=""
            )
        if args and args[0] == "install":
            state["installed"] = True
            return subprocess.CompletedProcess(args=list(args), returncode=0, stdout="", stderr="")
        if args and args[0] == "uninstall":
            state["installed"] = False  # rollback restored pre-install freeze
            return subprocess.CompletedProcess(args=list(args), returncode=0, stdout="", stderr="")
        return subprocess.CompletedProcess(args=list(args), returncode=0, stdout="", stderr="")

    monkeypatch.setattr(installer, "run_pip", fake)

    # Force discover_plugins to raise so Phase E fails.
    def boom(*a, **kw):
        raise RuntimeError("Phase E synthetic failure")

    monkeypatch.setattr(installer, "discover_plugins", boom)

    stdin = io.StringIO("y\n")
    stdout = io.StringIO()
    with pytest.raises(PluginInstallError) as excinfo:
        install_plugin(
            "horus-example-clean",
            db=db,
            allow_system_python=True,
            assume_yes=False,
            stdin=stdin,
            stdout=stdout,
        )
    assert excinfo.value.phase == "verify"

    # Rollback called pip uninstall -y.
    uninstall_calls = [c for c in captured if c and c[0] == "uninstall"]
    assert len(uninstall_calls) == 1
    assert "-y" in uninstall_calls[0]
    assert "horus-example-clean" in uninstall_calls[0]

    # Plugins row deleted (cascade clears plugin_capabilities + plugin_status).
    with db._connect() as conn:
        plugin_rows = conn.execute(
            "SELECT * FROM plugins WHERE name = ?", ("horus-example-clean",)
        ).fetchall()
        cap_rows = conn.execute(
            "SELECT * FROM plugin_capabilities WHERE plugin_name = ?",
            ("horus-example-clean",),
        ).fetchall()
        status_rows = conn.execute(
            "SELECT * FROM plugin_status WHERE plugin_name = ?",
            ("horus-example-clean",),
        ).fetchall()
    assert plugin_rows == []
    assert cap_rows == []
    assert status_rows == []

    # Post-rollback freeze sha256 equals pre-install sha256.
    pre_hash = hashlib.sha256(pre_freeze.encode("utf-8")).hexdigest()
    # Simulate the operator calling pip freeze after rollback.
    post_rollback = fake("freeze", check=False).stdout
    post_hash = hashlib.sha256(post_rollback.encode("utf-8")).hexdigest()
    assert post_hash == pre_hash
