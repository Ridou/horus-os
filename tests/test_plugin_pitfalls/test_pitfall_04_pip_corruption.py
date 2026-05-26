"""Pitfall 4: `pip install`-wrapped installer can corrupt the host venv.

See .planning/research/PITFALLS.md §"Pitfall 4" for the documented
threat. The Phase 44 installer ships five guards that, together, make
host-venv corruption structurally impossible:

* ``test_installer_venv_refusal.py`` — refuse to install into the
  system Python; require an explicit ``--allow-system-python`` opt-in.
* ``test_installer_sdist_refusal.py`` — refuse sdist (source-tarball)
  installs; wheel-only.
* ``test_installer_pth_refusal.py`` — refuse wheels that carry a
  ``.pth`` file (since .pth files inject site-customization).
* ``test_installer_downgrade_refusal.py`` — refuse upgrades that
  downgrade horus-os-pinned dependencies (would corrupt the host).
* ``test_installer_rollback.py`` — every install is atomic; failure
  rolls back to the pre-install state, never leaves the venv in a
  half-installed state.

This file is a META-test: it asserts the five guard files still
exist as collectable pytest items. Accidental deletion of any of them
turns this assertion red before the regression can land. The actual
behavioral assertions live in the five files themselves; this meta
test sits one layer up.

The subprocess-based approach (``pytest --collect-only``) is the
canonical way to assert pytest can still find the tests; a plain
``os.path.exists`` would catch the file deletion but not a silent
collection error (e.g. a syntax error in one of the files).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER_GUARD_FILES = (
    "tests/plugins/test_installer_venv_refusal.py",
    "tests/plugins/test_installer_sdist_refusal.py",
    "tests/plugins/test_installer_pth_refusal.py",
    "tests/plugins/test_installer_downgrade_refusal.py",
    "tests/plugins/test_installer_rollback.py",
)


def test_installer_guard_files_exist_on_disk() -> None:
    """Layer 1: each Phase 44 installer guard file must exist on disk."""
    missing: list[str] = []
    for rel in INSTALLER_GUARD_FILES:
        candidate = REPO_ROOT / rel
        if not candidate.is_file():
            missing.append(rel)
    assert not missing, (
        f"Pitfall 4 META: missing installer guard file(s) {missing}. "
        "Phase 44 substrate has been deleted; Pitfall 4 regression no longer covered."
    )


def test_installer_guard_files_collect_without_errors() -> None:
    """Layer 2: pytest must still collect at least one test id per guard file.

    Subprocesses ``pytest --collect-only -q`` over the five guard
    files. Returns code 0 + at least one ``::test_`` marker per file.
    A silent syntax error or import failure trips return code 5
    (pytest's "no tests collected" exit) which makes this assertion
    red.
    """
    args = [
        sys.executable,
        "-m",
        "pytest",
        "--collect-only",
        "-q",
        "--no-header",
        *INSTALLER_GUARD_FILES,
    ]
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )
    assert result.returncode == 0, (
        f"Pitfall 4 META: pytest --collect-only failed (rc={result.returncode}). "
        f"stdout=\n{result.stdout}\nstderr=\n{result.stderr}"
    )
    # Each guard file should contribute at least one test id.
    stdout = result.stdout
    for rel in INSTALLER_GUARD_FILES:
        assert rel in stdout, (
            f"Pitfall 4 META: no test ids collected from {rel}. collect-only output:\n{stdout}"
        )
