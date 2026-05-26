"""INSTALL-01: venv gate refusal + --allow-system-python escape hatch.

When ``sys.prefix == sys.base_prefix`` and ``allow_system_python=False``,
``install_plugin`` raises ``PluginInstallError(phase='venv', ...)``
before any pip invocation. When ``allow_system_python=True``, the
installer proceeds past the venv gate and reaches Phase A
(``run_pip("download", ...)``).

Every test monkeypatches ``run_pip`` at the module boundary so no real
pip subprocess runs.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from horus_os.plugins import installer
from horus_os.plugins.installer import PluginInstallError, install_plugin
from horus_os.storage import Database


def _make_db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "horus.sqlite3")
    db.init()
    return db


def test_venv_refused_outside_venv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = _make_db(tmp_path)
    # Force sys.prefix == sys.base_prefix so is_venv() returns False.
    monkeypatch.setattr(installer.sys, "prefix", "/usr")
    monkeypatch.setattr(installer.sys, "base_prefix", "/usr")

    call_log: list[tuple[str, ...]] = []

    def fake_run_pip(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        call_log.append(args)
        return subprocess.CompletedProcess(args=list(args), returncode=0, stdout="", stderr="")

    monkeypatch.setattr(installer, "run_pip", fake_run_pip)

    with pytest.raises(PluginInstallError) as excinfo:
        install_plugin("anything==1.0", db=db, allow_system_python=False)
    assert excinfo.value.phase == "venv"
    assert "virtualenv" in str(excinfo.value)
    # Refusal landed BEFORE any pip invocation.
    assert call_log == []


def test_venv_refusal_mentions_escape_hatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = _make_db(tmp_path)
    monkeypatch.setattr(installer.sys, "prefix", "/usr")
    monkeypatch.setattr(installer.sys, "base_prefix", "/usr")

    monkeypatch.setattr(
        installer,
        "run_pip",
        lambda *a, **kw: subprocess.CompletedProcess(
            args=list(a), returncode=0, stdout="", stderr=""
        ),
    )

    with pytest.raises(PluginInstallError) as excinfo:
        install_plugin("anything==1.0", db=db, allow_system_python=False)
    # The message should mention --allow-system-python so users know
    # how to override.
    assert (
        "allow-system-python" in str(excinfo.value).lower()
        or "allow_system_python" in str(excinfo.value).lower()
    )


def test_allow_system_python_proceeds_past_venv_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With allow_system_python=True, Phase A reaches run_pip("download", ...).

    We stop the install early after Phase A by having the fake run_pip
    raise a sentinel error — we just need to prove the venv gate did
    not block the pipeline.
    """
    db = _make_db(tmp_path)
    monkeypatch.setattr(installer.sys, "prefix", "/usr")
    monkeypatch.setattr(installer.sys, "base_prefix", "/usr")

    captured_args: list[tuple[Any, ...]] = []

    class _Sentinel(Exception):
        pass

    def fake_run_pip(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        captured_args.append(args)
        # First call is pip download — raise so we don't continue.
        raise _Sentinel(f"reached pip with args={args!r}")

    monkeypatch.setattr(installer, "run_pip", fake_run_pip)

    with pytest.raises(_Sentinel):
        install_plugin("anything==1.0", db=db, allow_system_python=True)
    # Phase A was reached → first call must have been a "download" call.
    assert captured_args, "run_pip was never called; venv gate likely refused"
    assert captured_args[0][0] == "download"
