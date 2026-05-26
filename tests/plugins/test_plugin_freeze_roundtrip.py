"""INSTALL-04: pip freeze sha256 round-trip.

Three branches of the freeze sha256 check:

* Branch A (success): pre-freeze missing the plugin; post-freeze
  includes the new package AND horus-os runtime deps unchanged →
  install succeeds, plugins row inserted with status='pending'.
* Branch B (silent rollback): pre-freeze == post-freeze (pip reported
  install success but nothing actually landed) → fail with
  ``PluginInstallError(reason='silent_rollback')`` + rollback.
* Branch C (runtime dep changed): post-freeze shows pydantic
  downgraded from 2.7.0 to 2.6.0 → fail + automatic rollback +
  plugins row never persisted past the failure.
"""

from __future__ import annotations

import io
import shutil
import subprocess
from pathlib import Path

import pytest

from horus_os.plugins import installer
from horus_os.plugins.installer import (
    PluginInstallError,
    install_plugin,
    parse_freeze,
    pip_freeze_sha256,
)
from horus_os.plugins.spec import PluginSpec
from horus_os.storage import Database


def _make_db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "horus.sqlite3")
    db.init()
    return db


def _stub_discover_returns(spec_name: str):
    def fake_discover(*a, **kw):
        spec = PluginSpec(
            name=spec_name,
            version="0.1.0",
            description="",
            author="a",
            license="Apache-2.0",
            horus_os_compat=">=0.5,<0.6",
            homepage=None,
            issue_tracker=None,
            tool_entries=(),
            adapter_entries=(),
            capabilities=(),
            source="entry_point",
            source_detail="",
            manifest_hash="h",
        )
        return [spec], []

    return fake_discover


def test_parse_freeze_handles_common_shapes() -> None:
    """parse_freeze parses ``==`` and ``@`` lines + ignores blanks/comments."""
    text = (
        "pydantic==2.7.0\n"
        "packaging==24.0\n"
        "# this is a comment\n"
        "\n"
        "horus-os @ file:///tmp/build/horus-os\n"
    )
    parsed = parse_freeze(text)
    assert parsed["pydantic"] == "2.7.0"
    assert parsed["packaging"] == "24.0"
    assert parsed["horus-os"] == ""


def test_pip_freeze_sha256_is_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    """Same stdout → same hash."""

    def fake(*args, check: bool = True):
        return subprocess.CompletedProcess(
            args=list(args), returncode=0, stdout="pydantic==2.7.0\n", stderr=""
        )

    monkeypatch.setattr(installer, "run_pip", fake)
    a = pip_freeze_sha256()
    b = pip_freeze_sha256()
    assert a == b


def _build_fake_pip(
    wheel_path: Path,
    *,
    pre_freeze: str,
    post_freeze: str,
) -> callable[..., subprocess.CompletedProcess[str]]:
    """Build a fake run_pip with controlled freeze stdout pre/post install."""
    state = {"installed": False}

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
            stdout = post_freeze if state["installed"] else pre_freeze
            return subprocess.CompletedProcess(
                args=list(args), returncode=0, stdout=stdout, stderr=""
            )
        if args and args[0] == "install":
            state["installed"] = True
            return subprocess.CompletedProcess(args=list(args), returncode=0, stdout="", stderr="")
        if args and args[0] == "uninstall":
            state["installed"] = False
            return subprocess.CompletedProcess(args=list(args), returncode=0, stdout="", stderr="")
        return subprocess.CompletedProcess(args=list(args), returncode=0, stdout="", stderr="")

    return fake


def test_branch_a_success_inserts_plugins_row(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    installer_fixture_wheels: dict[str, Path],
) -> None:
    db = _make_db(tmp_path)
    clean_wheel = installer_fixture_wheels["wheel_clean"]
    pre = "pydantic==2.7.0\npackaging==24.0\n"
    post = "pydantic==2.7.0\npackaging==24.0\nhorus-example-clean==0.1.0\n"
    monkeypatch.setattr(
        installer, "run_pip", _build_fake_pip(clean_wheel, pre_freeze=pre, post_freeze=post)
    )
    monkeypatch.setattr(
        installer, "discover_plugins", _stub_discover_returns("horus-example-clean")
    )

    name = install_plugin(
        "horus-example-clean",
        db=db,
        allow_system_python=True,
        assume_yes=True,
        stdin=io.StringIO(""),
        stdout=io.StringIO(),
    )
    assert name == "horus-example-clean"

    with db._connect() as conn:
        plugin_row = conn.execute(
            "SELECT name, version, manifest_hash FROM plugins WHERE name = ?",
            ("horus-example-clean",),
        ).fetchone()
        status_row = conn.execute(
            "SELECT status FROM plugin_status WHERE plugin_name = ?",
            ("horus-example-clean",),
        ).fetchone()
    assert plugin_row is not None
    assert plugin_row["name"] == "horus-example-clean"
    assert status_row is not None
    assert status_row["status"] == "pending"


def test_branch_b_silent_rollback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    installer_fixture_wheels: dict[str, Path],
) -> None:
    """pre == post freeze → silent_rollback + rollback."""
    db = _make_db(tmp_path)
    clean_wheel = installer_fixture_wheels["wheel_clean"]
    same = "pydantic==2.7.0\npackaging==24.0\n"
    monkeypatch.setattr(
        installer, "run_pip", _build_fake_pip(clean_wheel, pre_freeze=same, post_freeze=same)
    )
    monkeypatch.setattr(
        installer, "discover_plugins", _stub_discover_returns("horus-example-clean")
    )

    with pytest.raises(PluginInstallError) as excinfo:
        install_plugin(
            "horus-example-clean",
            db=db,
            allow_system_python=True,
            assume_yes=True,
            stdin=io.StringIO(""),
            stdout=io.StringIO(),
        )
    assert excinfo.value.phase == "verify"
    assert excinfo.value.reason == "silent_rollback"

    # Rollback removed the plugins row.
    with db._connect() as conn:
        rows = conn.execute(
            "SELECT * FROM plugins WHERE name = ?", ("horus-example-clean",)
        ).fetchall()
    assert rows == []


def test_branch_c_runtime_dep_changed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    installer_fixture_wheels: dict[str, Path],
) -> None:
    """post-freeze shows pydantic downgraded → runtime_dep_changed + rollback."""
    db = _make_db(tmp_path)
    clean_wheel = installer_fixture_wheels["wheel_clean"]
    pre = "pydantic==2.7.0\npackaging==24.0\n"
    post = "pydantic==2.6.0\npackaging==24.0\nhorus-example-clean==0.1.0\n"
    monkeypatch.setattr(
        installer, "run_pip", _build_fake_pip(clean_wheel, pre_freeze=pre, post_freeze=post)
    )
    monkeypatch.setattr(
        installer, "discover_plugins", _stub_discover_returns("horus-example-clean")
    )

    with pytest.raises(PluginInstallError) as excinfo:
        install_plugin(
            "horus-example-clean",
            db=db,
            allow_system_python=True,
            assume_yes=True,
            stdin=io.StringIO(""),
            stdout=io.StringIO(),
        )
    assert excinfo.value.phase == "verify"
    assert excinfo.value.reason == "runtime_dep_changed"
    # Plugins row never persisted past the failure.
    with db._connect() as conn:
        rows = conn.execute(
            "SELECT * FROM plugins WHERE name = ?", ("horus-example-clean",)
        ).fetchall()
    assert rows == []
