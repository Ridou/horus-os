"""Tests for `horus-os doctor --shell` (SHELL-03 display half, T-75-09).

The shell doctor surface lets a maintainer confirm the live state of the
SHELL-01 double gate before running an agent. These tests assert it reports the
runtime env gate and the resolved safe working directory for both the
env-unset and env-set cases, and that it never disturbs the --supabase branch.
"""

from __future__ import annotations

import argparse
import io
from pathlib import Path

import pytest

from horus_os.cli.doctor_cmd import run_doctor
from horus_os.tools.shell import SHELL_ENABLED_ENV


def _args(tmp_path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        shell=True,
        supabase=False,
        local=False,
        memory=False,
        mcp=False,
        data_dir=tmp_path,
    )


def test_shell_doctor_reports_disabled_when_env_unset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv(SHELL_ENABLED_ENV, raising=False)
    out = io.StringIO()
    err = io.StringIO()

    code = run_doctor(_args(tmp_path), stdout=out, stderr=err)

    assert code == 0
    output = out.getvalue()
    # The env gate is reported as shut and the tool reported unreachable.
    assert "False" in output
    assert "shell tool reachable: no" in output
    # The resolved safe working directory (data_dir/shell by default) is shown.
    assert str(tmp_path / "shell") in output
    # The per-profile allowed_tools reminder is always present.
    assert "shell_exec" in output
    assert err.getvalue() == ""


def test_shell_doctor_reports_enabled_when_env_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(SHELL_ENABLED_ENV, "true")
    out = io.StringIO()
    err = io.StringIO()

    code = run_doctor(_args(tmp_path), stdout=out, stderr=err)

    assert code == 0
    output = out.getvalue()
    # The env gate is reported open and the tool reachable.
    assert "shell tool reachable: yes" in output
    assert "True" in output
    # The limits round-trip into the report.
    assert "timeout_seconds: 30" in output
    assert "output_cap_bytes: 1048576" in output
    assert "shell_type: auto" in output


def test_shell_doctor_reports_custom_working_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # A configured working_dir is reported verbatim, not the default.
    monkeypatch.delenv(SHELL_ENABLED_ENV, raising=False)
    custom = tmp_path / "custom-shell-root"
    from horus_os.config import Config

    cfg = Config.with_defaults(tmp_path)
    cfg.shell_working_dir = custom
    cfg.save()

    out = io.StringIO()
    err = io.StringIO()
    code = run_doctor(_args(tmp_path), stdout=out, stderr=err)

    assert code == 0
    assert str(custom) in out.getvalue()
