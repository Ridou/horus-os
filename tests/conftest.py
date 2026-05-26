"""Top-level conftest: installer_e2e marker gating + tier-3 clean_venv fixture.

The default ``pytest`` invocation NEVER spawns a venv and NEVER calls
pip. Tier-3 tests are opt-in via the ``--run-installer-e2e`` CLI flag;
without the flag, every ``@pytest.mark.installer_e2e``-marked test is
skipped at collection time AND the ``clean_venv`` fixture raises
``pytest.skip`` on first access (defense in depth).

Why a separate top-level conftest?

* ``tests/plugins/conftest.py`` is scoped to ``tests/plugins/``. Tier-3
  ``installer_e2e`` tests may live anywhere under ``tests/`` — including
  ``tests/test_plugin_pitfalls/`` for Pitfall 11's host-venv isolation
  assertion.
* The ``--run-installer-e2e`` flag must be registered via
  ``pytest_addoption`` at the top level so the option resolves the same
  way regardless of which directory ``pytest`` is invoked against.

Phase 46 TEST-16 substrate.
"""

from __future__ import annotations

import sys
import venv
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

# Resolve the repo root via this file's location: tests/conftest.py.
REPO_ROOT = Path(__file__).resolve().parent.parent


# --- CLI option ------------------------------------------------------------


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the ``--run-installer-e2e`` flag (default off)."""
    parser.addoption(
        "--run-installer-e2e",
        action="store_true",
        default=False,
        help=(
            "Enable tier-3 installer_e2e tests (creates a fresh venv per "
            "session and runs `pip install -e <repo>`; ~30s session startup, "
            "~5s per test). Off by default; CI nightly job opts in."
        ),
    )


# --- Collection-time skip --------------------------------------------------


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip every ``installer_e2e``-marked item unless --run-installer-e2e is set."""
    if config.getoption("--run-installer-e2e"):
        return
    skip_marker = pytest.mark.skip(
        reason="requires --run-installer-e2e flag (slow tier-3 venv tests)"
    )
    for item in items:
        if "installer_e2e" in item.keywords:
            item.add_marker(skip_marker)


# --- Tier-3 clean_venv fixture ---------------------------------------------


@dataclass
class CleanVenv:
    """Handle to a tier-3 fresh-venv environment.

    ``python`` — absolute path to the venv's python interpreter.
    ``site_packages`` — absolute path to the venv's ``site-packages``.
    ``tmp_dir`` — the venv's root directory (parent of ``bin/``).
    """

    python: Path
    site_packages: Path
    tmp_dir: Path


def _find_site_packages(venv_root: Path) -> Path:
    """Locate the site-packages directory inside a freshly created venv.

    POSIX layout: ``<venv>/lib/python<X.Y>/site-packages``.
    Windows layout: ``<venv>/Lib/site-packages``.
    The fixture only runs on the CI nightly job (Linux + macOS today),
    but the Windows path is included for forward-compat with the Phase
    49 release gate.
    """
    candidates = list(venv_root.rglob("site-packages"))
    if not candidates:
        raise FileNotFoundError(f"no site-packages directory found under {venv_root}")
    return candidates[0]


@pytest.fixture(scope="session")
def clean_venv(
    request: pytest.FixtureRequest,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[CleanVenv]:
    """Tier-3 fixture: create a fresh venv + pip-install the repo once per session.

    Guarded: if ``--run-installer-e2e`` is absent, raise
    ``pytest.skip`` on first access. This is defense in depth alongside
    the collection-time skip in ``pytest_collection_modifyitems`` — a
    misconfigured test that depends on this fixture without the marker
    still fails loud.

    The venv is created under ``tmp_path_factory.getbasetemp() /
    "clean_venv"`` via ``venv.create(..., with_pip=True)``. The repo is
    installed in editable mode (``pip install -e <repo_root>``).
    Cold-start cost: ~30s; amortized across every tier-3 test in the
    session.
    """
    if not request.config.getoption("--run-installer-e2e"):
        pytest.skip("clean_venv requires --run-installer-e2e flag")

    venv_root = tmp_path_factory.getbasetemp() / "clean_venv"
    if not venv_root.exists():
        venv.create(venv_root, with_pip=True, clear=False, symlinks=False)
        # Locate the venv python; POSIX has bin/python, Windows has Scripts/python.exe.
        bin_dir = venv_root / "bin"
        if not bin_dir.exists():
            bin_dir = venv_root / "Scripts"
        venv_python = bin_dir / ("python.exe" if sys.platform == "win32" else "python")
        if not venv_python.exists():
            raise FileNotFoundError(f"could not locate venv python under {venv_root}")
        # pip install -e <repo_root> — this is the only pip invocation
        # the test surface ever performs. The repo's runtime deps install
        # transitively.
        import subprocess

        subprocess.run(
            [str(venv_python), "-m", "pip", "install", "-e", str(REPO_ROOT)],
            check=True,
            cwd=str(REPO_ROOT),
        )
    else:
        bin_dir = venv_root / "bin"
        if not bin_dir.exists():
            bin_dir = venv_root / "Scripts"
        venv_python = bin_dir / ("python.exe" if sys.platform == "win32" else "python")

    site_packages = _find_site_packages(venv_root)
    yield CleanVenv(
        python=venv_python,
        site_packages=site_packages,
        tmp_dir=venv_root,
    )
