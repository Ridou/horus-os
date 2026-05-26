"""INSTALL-03: sdist refusal + --allow-sdist escape hatch.

When ``pip download`` returns only a ``.tar.gz`` (no ``.whl``),
``install_plugin`` raises ``PluginInstallError(phase='sdist', ...)``
before Phase D. The message cites Pitfall 4 / ``setup.py`` arbitrary
code execution so the refusal is auditable.

With ``allow_sdist=True``, the pipeline continues past the sdist gate.
"""

from __future__ import annotations

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


def _fake_run_pip_factory(
    download_artifacts: list[Path],
) -> callable[..., subprocess.CompletedProcess[str]]:
    """Build a fake ``run_pip`` that pretends to download artifacts.

    On the first ``download`` call, copies each path in
    ``download_artifacts`` into the ``--dest`` directory passed via
    args, then returns a successful CompletedProcess. Every other call
    returns a successful empty CompletedProcess (so ``pip freeze`` etc.
    return harmless stdout).
    """

    def fake(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        if args and args[0] == "download":
            # Find --dest <path>.
            dest = None
            for i, a in enumerate(args):
                if a == "--dest" and i + 1 < len(args):
                    dest = Path(args[i + 1])
                    break
            if dest is not None:
                dest.mkdir(parents=True, exist_ok=True)
                for src in download_artifacts:
                    shutil.copy(src, dest / src.name)
        return subprocess.CompletedProcess(args=list(args), returncode=0, stdout="", stderr="")

    return fake


def test_sdist_only_refused_by_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    installer_fixture_wheels: dict[str, Path],
) -> None:
    db = _make_db(tmp_path)
    sdist_path = installer_fixture_wheels["sdist_only"]

    fake = _fake_run_pip_factory([sdist_path])
    monkeypatch.setattr(installer, "run_pip", fake)

    with pytest.raises(PluginInstallError) as excinfo:
        install_plugin(
            "horus-example-sdist",
            db=db,
            allow_sdist=False,
            allow_system_python=True,
            assume_yes=True,
        )
    assert excinfo.value.phase == "sdist"
    msg = str(excinfo.value).lower()
    assert "setup.py" in msg or "arbitrary code execution" in msg


def test_allow_sdist_proceeds_past_sdist_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    installer_fixture_wheels: dict[str, Path],
) -> None:
    """With --allow-sdist, the pipeline continues past the sdist gate.

    The next gate after the sdist gate is ``_find_wheel`` which returns
    None for an sdist-only download → the installer raises a different
    error (``no_wheel_in_download``). We assert on that error rather
    than the original sdist refusal so the assertion proves we got
    past the sdist gate.
    """
    db = _make_db(tmp_path)
    sdist_path = installer_fixture_wheels["sdist_only"]

    fake = _fake_run_pip_factory([sdist_path])
    monkeypatch.setattr(installer, "run_pip", fake)

    with pytest.raises(PluginInstallError) as excinfo:
        install_plugin(
            "horus-example-sdist",
            db=db,
            allow_sdist=True,
            allow_system_python=True,
            assume_yes=True,
        )
    assert excinfo.value.phase != "sdist"
    assert excinfo.value.phase == "download"
    assert excinfo.value.reason == "no_wheel_in_download"
