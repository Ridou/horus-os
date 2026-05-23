"""Smoke tests for the horus-os package skeleton."""

from __future__ import annotations

import subprocess
import sys

import horus_os


def test_version_is_non_empty_string() -> None:
    assert isinstance(horus_os.__version__, str)
    assert len(horus_os.__version__) > 0


def test_cli_version_invocation_exits_zero() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "horus_os", "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "horus-os" in result.stdout


def test_cli_default_invocation_prints_help() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "horus_os"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "usage:" in result.stdout.lower()
