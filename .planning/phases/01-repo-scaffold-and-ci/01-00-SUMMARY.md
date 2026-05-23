---
phase: 01-repo-scaffold-and-ci
plan: "00"
subsystem: project-skeleton
tags: [repo-scaffold, ci, pyproject, ruff, pytest, github-actions]

# Dependency graph
requires: []
provides:
  - "Python project skeleton with src/ layout that supports `pip install -e .` and console_scripts entry"
  - "ruff lint configuration covering 7 rule sets (E, W, F, I, B, UP, RUF)"
  - "pytest config wired through pyproject.toml"
  - "CI matrix on 3 OSes (Ubuntu, macOS, Windows) by 2 Python versions (3.11, 3.12)"
  - "`horus-os --version` and `python -m horus_os --version` both functional"
affects:
  - "Phase 02 (agent runtime core), can now import and ship code in src/horus_os/"
  - "All future phases inherit the ruff + pytest + CI pipeline"

# Tech tracking
tech-stack:
  added:
    - "ruff (dev dep) for lint and format"
    - "pytest (dev dep) for unit tests"
  patterns:
    - "src/ layout, not flat package, so `pip install -e .` does not leak the project root into the import path"
    - "Console entry point via `[project.scripts]` so `horus-os` is on PATH after install"
    - "All linting rules declared in pyproject.toml so the same config drives local dev and CI"

key-files:
  created:
    - "pyproject.toml, 56 lines, full project metadata + dev extras + ruff + pytest config"
    - "src/horus_os/__init__.py, 5 lines, __version__ and __all__"
    - "src/horus_os/__main__.py, 31 lines, argparse-based CLI stub"
    - "tests/__init__.py, empty, makes tests/ a package"
    - "tests/test_smoke.py, 31 lines, 3 smoke tests"
    - ".github/workflows/ci.yml, 45 lines, lint + format + test + cli-smoke matrix"
  modified:
    - ".gitignore, added Python build artifacts and local SQLite patterns"

key-decisions:
  - "Apache-2.0 license, declared in pyproject.toml `[project] license` and via SPDX classifier"
  - "Python 3.11 minimum, gives access to typed dict syntax (`list[str] | None`) without `from __future__ import annotations` headache, and matches the user base of modern Python"
  - "src/ layout, prevents the common bug where tests pick up the source tree by accident rather than the installed package"
  - "ruff handles both lint and format, eliminates the black + flake8 + isort dependency stack"
  - "Direct argparse for the CLI stub, defers Typer or Click decision to phase 07 when the CLI gains real subcommands"
  - "Console script name `horus-os` (with hyphen), package name `horus_os` (with underscore), per PEP 8 + PyPI norms"

patterns-established:
  - "All pyproject.toml-driven tooling, one file for project metadata, deps, lint config, test config"
  - "GitHub Actions matrix with `fail-fast: false`, so a Windows-only regression does not hide Ubuntu/macOS results"
  - "Tests invoke CLI through subprocess, not through direct import of the main function, so the test surface matches the user surface"

requirements-completed:
  - CORE-01  # Local verification passed on macOS; CI covers Ubuntu and Windows on first push
  - TEST-01  # ruff lint pipeline functional
  - TEST-02  # pytest pipeline functional

# Metrics
duration: 18m
completed: 2026-05-23
commit-count: 1
test-count: 3
lint-issues: 0
