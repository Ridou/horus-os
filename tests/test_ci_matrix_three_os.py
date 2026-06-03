"""Regression guard for the three-OS hard gate matrix (REL-16 criterion 1, D-06).

The v0.7 milestone constraint is a three-OS hard gate: CI must be green on
macOS, Ubuntu, and Windows for both Python 3.11 and 3.12 with all of the new
optional extras exercised. The actual cross-OS GREEN is a GitHub Actions result
that only a push can produce, so it is tracked as a post-push CI / human-verified
item (D-06). This test cannot and does not produce that cross-OS green.

What this test DOES guard is that the matrix is WIRED: it reads
``.github/workflows/ci.yml`` via pathlib (the same tomllib/pathlib repo-file
idiom that ``tests/test_install_smoke.py`` uses for ``pyproject.toml``) and
asserts the OS matrix lists all three OS literals, the Python-version matrix
lists both 3.11 and 3.12, the install-smoke job installs the ``[all]`` extras,
and the four install-smoke job names are all present. The test fails if a future
maintainer drops an OS, a Python version, or the all-extras install-smoke job,
which would silently weaken the three-OS hard gate before a release.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_CI_YML_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"

# The three OS runners the hard gate requires.
_REQUIRED_OS = ("ubuntu-latest", "macos-latest", "windows-latest")
# Both Python versions the hard gate requires.
_REQUIRED_PYTHON = ("3.11", "3.12")
# The literal install command the dedicated all-extras install-smoke job runs.
# This is the same token release_gate-style presence checks would expect; if the
# job stops installing the full optional surface, the all-extras smoke is gone.
_ALL_EXTRAS_INSTALL_TOKEN = "pip install '.[all]'"
# The four install-smoke job names. install-smoke installs '.[all]';
# install-smoke-no-otel / install-smoke-with-otel pin the [otel] contract;
# install-smoke-plugin pins the Phase 49 TEST-20 plugin matrix.
_REQUIRED_SMOKE_JOBS = (
    "install-smoke",
    "install-smoke-no-otel",
    "install-smoke-with-otel",
    "install-smoke-plugin",
)


def _read_ci_yml() -> str:
    assert _CI_YML_PATH.is_file(), f"ci.yml not found at {_CI_YML_PATH}"
    return _CI_YML_PATH.read_text(encoding="utf-8")


def test_os_matrix_covers_three_runners() -> None:
    """ci.yml lists ubuntu-latest, macos-latest, AND windows-latest (D-06)."""
    text = _read_ci_yml()
    missing = [os_literal for os_literal in _REQUIRED_OS if os_literal not in text]
    assert missing == [], (
        f"ci.yml is missing OS runner(s) {missing}; the three-OS hard gate "
        "(REL-16 criterion 1) requires ubuntu-latest, macos-latest, and windows-latest"
    )
    # The matrix line itself must enumerate all three on one os: line so a
    # maintainer cannot satisfy the substring check by mentioning a runner in
    # prose alone.
    os_matrix_lines = [
        line for line in text.splitlines() if "os:" in line and "ubuntu-latest" in line
    ]
    assert any(
        all(os_literal in line for os_literal in _REQUIRED_OS) for line in os_matrix_lines
    ), "no `os:` matrix line enumerates all three of ubuntu-latest, macos-latest, windows-latest"


def test_python_matrix_covers_both_versions() -> None:
    """ci.yml lists Python 3.11 AND 3.12 in the matrix (D-06)."""
    text = _read_ci_yml()
    missing = [py for py in _REQUIRED_PYTHON if f'"{py}"' not in text]
    assert missing == [], (
        f"ci.yml is missing Python version(s) {missing}; the three-OS hard gate "
        "requires both 3.11 and 3.12"
    )
    python_matrix_lines = [line for line in text.splitlines() if "python-version:" in line]
    assert any(all(f'"{py}"' in line for py in _REQUIRED_PYTHON) for line in python_matrix_lines), (
        "no `python-version:` matrix line enumerates both 3.11 and 3.12"
    )


def test_install_smoke_installs_all_extras() -> None:
    """The install-smoke job installs the [all] extras (REL-16 criterion 1)."""
    text = _read_ci_yml()
    assert _ALL_EXTRAS_INSTALL_TOKEN in text, (
        f"ci.yml does not contain the all-extras install token "
        f"{_ALL_EXTRAS_INSTALL_TOKEN!r}; the install-smoke job must install the full "
        "optional surface so the three-OS gate exercises the new extras"
    )


def test_all_four_install_smoke_jobs_present() -> None:
    """All four install-smoke job names are wired into the matrix (D-06)."""
    text = _read_ci_yml()
    missing = [job for job in _REQUIRED_SMOKE_JOBS if job not in text]
    assert missing == [], (
        f"ci.yml is missing install-smoke job(s) {missing}; the install matrix "
        "must keep install-smoke, install-smoke-no-otel, install-smoke-with-otel, "
        "and install-smoke-plugin so the [all] surface and the [otel] / plugin "
        "contracts stay exercised on every OS"
    )


def test_smoke_jobs_run_on_three_os_matrix() -> None:
    """Each install-smoke matrix block carries the full 3-OS x 2-Python grid (D-06).

    The cross-OS GREEN is a post-push CI result this test cannot produce; this
    only asserts the matrix is WIRED so the install-smoke jobs cannot silently
    drop to a single OS or a single Python version between releases.
    """
    text = _read_ci_yml()
    # Every matrix block that enumerates the os list must enumerate all three OS;
    # likewise every python-version MATRIX line must list both versions. The
    # whole-file assertions above already prove presence; this guards the per-job
    # matrix DECLARATION lines so a single weakened block is caught.
    #
    # Scope to the matrix-declaration lines only. The setup-python step also has
    # a `python-version: ${{ matrix.python-version }}` interpolation line that
    # carries no literals; those are excluded by requiring a `[` (the YAML inline
    # list that holds the version literals).
    os_lines = [
        line for line in text.splitlines() if line.strip().startswith("os:") and "[" in line
    ]
    assert os_lines, "ci.yml has no `os:` matrix declaration lines at all"
    for line in os_lines:
        for os_literal in _REQUIRED_OS:
            assert os_literal in line, (
                f"an `os:` matrix line omits {os_literal!r}: {line.strip()!r}; "
                "every job must run on all three OS"
            )
    py_lines = [
        line
        for line in text.splitlines()
        if line.strip().startswith("python-version:") and "[" in line
    ]
    assert py_lines, "ci.yml has no `python-version:` matrix declaration lines at all"
    for line in py_lines:
        for py in _REQUIRED_PYTHON:
            assert f'"{py}"' in line, (
                f"a `python-version:` matrix line omits {py!r}: {line.strip()!r}; "
                "every job must run on both Python versions"
            )
