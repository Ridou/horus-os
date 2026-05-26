"""INSTALL-03 (continued): .pth refusal via RECORD inspection.

A wheel whose RECORD contains a ``.pth`` entry is refused with
``PluginInstallError(phase='pth', reason='pth_in_record')`` before
Phase D. The refusal happens after manifest validation (so the spec
is real) but before any pip install runs.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from horus_os.plugins import installer
from horus_os.plugins.installer import (
    PluginInstallError,
    check_no_pth,
    install_plugin,
)
from horus_os.storage import Database


def _make_db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "horus.sqlite3")
    db.init()
    return db


def test_check_no_pth_direct_on_pth_wheel(
    installer_fixture_wheels: dict[str, Path],
) -> None:
    """Direct unit test on the helper."""
    pth_wheel = installer_fixture_wheels["wheel_with_pth"]
    with pytest.raises(PluginInstallError) as excinfo:
        check_no_pth(pth_wheel)
    assert excinfo.value.phase == "pth"
    assert excinfo.value.reason == "pth_in_record"
    # The offending filename should appear in the message.
    assert "__path_hack__.pth" in str(excinfo.value)


def test_check_no_pth_accepts_clean_wheel(
    installer_fixture_wheels: dict[str, Path],
) -> None:
    """Clean wheel should not raise."""
    clean_wheel = installer_fixture_wheels["wheel_clean"]
    check_no_pth(clean_wheel)


def test_install_refuses_wheel_with_pth(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    installer_fixture_wheels: dict[str, Path],
) -> None:
    """install_plugin refuses the pth-wheel before Phase D.

    The fake run_pip records its argv list; we assert that no
    'install' call ever happens.
    """
    db = _make_db(tmp_path)
    pth_wheel = installer_fixture_wheels["wheel_with_pth"]
    captured: list[tuple[str, ...]] = []

    def fake(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        captured.append(args)
        if args and args[0] == "download":
            for i, a in enumerate(args):
                if a == "--dest" and i + 1 < len(args):
                    dest = Path(args[i + 1])
                    dest.mkdir(parents=True, exist_ok=True)
                    shutil.copy(pth_wheel, dest / pth_wheel.name)
                    break
        return subprocess.CompletedProcess(args=list(args), returncode=0, stdout="", stderr="")

    monkeypatch.setattr(installer, "run_pip", fake)

    with pytest.raises(PluginInstallError) as excinfo:
        install_plugin(
            "horus-example-pth",
            db=db,
            allow_system_python=True,
            assume_yes=True,
        )
    assert excinfo.value.phase == "pth"
    # Critical assertion: no install call ever ran.
    install_calls = [c for c in captured if c and c[0] == "install"]
    assert install_calls == [], f"unexpected pip install call(s) before Phase D: {install_calls!r}"
