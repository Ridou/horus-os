"""INSTALL-04: runtime-dep downgrade refusal.

A wheel whose ``Requires-Dist: pydantic<2.0`` line excludes the
currently-installed pydantic version (the horus-os base pins
``pydantic>=2.7,<3``) is refused with
``PluginInstallError(phase='downgrade', reason='runtime_dep_downgrade')``
before Phase D. The message names the offending package + current
version + the spec that excluded it.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from horus_os.plugins import installer
from horus_os.plugins.installer import (
    PluginInstallError,
    check_no_downgrade,
    install_plugin,
)
from horus_os.storage import Database


def _make_db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "horus.sqlite3")
    db.init()
    return db


def test_check_no_downgrade_refuses_pydantic_downgrade(
    installer_fixture_wheels: dict[str, Path],
) -> None:
    """Direct unit test: the downgrade-wheel + a freeze showing pydantic 2.7 is refused."""
    downgrade_wheel = installer_fixture_wheels["wheel_downgrades_pydantic"]
    current_freeze = {"pydantic": "2.7.0", "packaging": "24.0"}
    with pytest.raises(PluginInstallError) as excinfo:
        check_no_downgrade(downgrade_wheel, current_freeze)
    assert excinfo.value.phase == "downgrade"
    assert excinfo.value.reason == "runtime_dep_downgrade"
    msg = str(excinfo.value).lower()
    assert "pydantic" in msg
    assert "2.7" in msg or "2.7.0" in msg


def test_check_no_downgrade_accepts_clean_wheel(
    installer_fixture_wheels: dict[str, Path],
) -> None:
    """The clean wheel's Requires-Dist: pydantic>=2.7,<3 satisfies a 2.7.0 environment."""
    clean_wheel = installer_fixture_wheels["wheel_clean"]
    current_freeze = {"pydantic": "2.7.0", "packaging": "24.0"}
    check_no_downgrade(clean_wheel, current_freeze)  # must not raise


def test_check_no_downgrade_skips_unrelated_packages(
    installer_fixture_wheels: dict[str, Path],
    tmp_path: Path,
) -> None:
    """Requires-Dist entries for non-runtime-dep packages are ignored."""
    import zipfile

    # Build a wheel with a Requires-Dist for a package not in
    # HORUS_OS_RUNTIME_DEPS — should pass through.
    wheel_path = tmp_path / "horus_example_other-0.1.0-py3-none-any.whl"
    dist_info = "horus_example_other-0.1.0.dist-info"
    with zipfile.ZipFile(wheel_path, "w") as zf:
        zf.writestr("horus-plugin.toml", b"")
        zf.writestr(
            f"{dist_info}/METADATA",
            b"Metadata-Version: 2.1\nName: horus-example-other\nVersion: 0.1.0\n"
            b"Requires-Dist: requests<2.0\n",
        )
        zf.writestr(f"{dist_info}/RECORD", b"")
    # requests is NOT in HORUS_OS_RUNTIME_DEPS, so this should not raise.
    check_no_downgrade(wheel_path, {"requests": "2.31.0", "pydantic": "2.7.0"})


def test_install_refuses_downgrade_wheel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    installer_fixture_wheels: dict[str, Path],
) -> None:
    """install_plugin refuses the downgrade-wheel before Phase D."""
    db = _make_db(tmp_path)
    downgrade_wheel = installer_fixture_wheels["wheel_downgrades_pydantic"]
    captured: list[tuple[str, ...]] = []

    def fake(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        captured.append(args)
        if args and args[0] == "download":
            for i, a in enumerate(args):
                if a == "--dest" and i + 1 < len(args):
                    dest = Path(args[i + 1])
                    dest.mkdir(parents=True, exist_ok=True)
                    shutil.copy(downgrade_wheel, dest / downgrade_wheel.name)
                    break
            return subprocess.CompletedProcess(args=list(args), returncode=0, stdout="", stderr="")
        if args and args[0] == "freeze":
            # Report pydantic 2.7.0 as installed so the downgrade gate has
            # a real version to compare against.
            return subprocess.CompletedProcess(
                args=list(args),
                returncode=0,
                stdout="pydantic==2.7.0\npackaging==24.0\n",
                stderr="",
            )
        return subprocess.CompletedProcess(args=list(args), returncode=0, stdout="", stderr="")

    monkeypatch.setattr(installer, "run_pip", fake)

    with pytest.raises(PluginInstallError) as excinfo:
        install_plugin(
            "horus-example-downgrade",
            db=db,
            allow_system_python=True,
            assume_yes=True,
        )
    assert excinfo.value.phase == "downgrade"
    # No Phase D ever ran.
    install_calls = [c for c in captured if c and c[0] == "install"]
    assert install_calls == []
