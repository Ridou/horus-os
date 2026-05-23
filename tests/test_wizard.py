"""Tests for the setup wizard."""

from __future__ import annotations

import io
import json
import os
from pathlib import Path

import pytest

from horus_os.cli.wizard import (
    ENV_FILENAME,
    STATE_FILENAME,
    run_wizard,
)
from horus_os.config import Config


def _config(tmp_path: Path) -> Config:
    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    return cfg


def _always_ok(_key: str) -> tuple[bool, str | None]:
    return True, None


def _always_fail(_key: str) -> tuple[bool, str | None]:
    return False, "bad key"


def test_both_keys_validated_and_written(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    stdin = io.StringIO("sk-ant-abc\n" + "AIzaXYZ\n" + "a\n")
    stdout = io.StringIO()
    code = run_wizard(
        cfg,
        stdin=stdin,
        stdout=stdout,
        validators={"anthropic": _always_ok, "gemini": _always_ok},
    )
    assert code == 0
    env_text = (tmp_path / ENV_FILENAME).read_text()
    assert "ANTHROPIC_API_KEY=sk-ant-abc" in env_text
    assert "GEMINI_API_KEY=AIzaXYZ" in env_text


def test_skip_both_keys_writes_no_env(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    stdin = io.StringIO("\n\n")
    stdout = io.StringIO()
    code = run_wizard(
        cfg, stdin=stdin, stdout=stdout, validators={"anthropic": _always_ok, "gemini": _always_ok}
    )
    assert code == 0
    assert not (tmp_path / ENV_FILENAME).exists()
    assert "No keys were validated" in stdout.getvalue()


def test_only_anthropic_validated_sets_default(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    stdin = io.StringIO("sk-ant\n\n")
    stdout = io.StringIO()
    run_wizard(
        cfg,
        stdin=stdin,
        stdout=stdout,
        validators={"anthropic": _always_ok, "gemini": _always_ok},
    )
    reloaded = Config.load(tmp_path)
    assert reloaded.default_provider == "anthropic"
    assert "ANTHROPIC_API_KEY=sk-ant" in (tmp_path / ENV_FILENAME).read_text()


def test_only_gemini_validated_sets_default(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    stdin = io.StringIO("\nAIza\n")
    stdout = io.StringIO()
    run_wizard(
        cfg,
        stdin=stdin,
        stdout=stdout,
        validators={"anthropic": _always_ok, "gemini": _always_ok},
    )
    reloaded = Config.load(tmp_path)
    assert reloaded.default_provider == "gemini"


def test_validation_failure_does_not_write_env(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    stdin = io.StringIO("sk-bad\n\n")
    stdout = io.StringIO()
    run_wizard(
        cfg,
        stdin=stdin,
        stdout=stdout,
        validators={"anthropic": _always_fail, "gemini": _always_ok},
    )
    env_text = (tmp_path / ENV_FILENAME).read_text() if (tmp_path / ENV_FILENAME).exists() else ""
    assert "ANTHROPIC_API_KEY" not in env_text
    assert "Validation failed" in stdout.getvalue()


def test_state_file_records_progress(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    stdin = io.StringIO("sk-ant\nAIza\na\n")
    stdout = io.StringIO()
    run_wizard(
        cfg,
        stdin=stdin,
        stdout=stdout,
        validators={"anthropic": _always_ok, "gemini": _always_ok},
    )
    state = json.loads((tmp_path / STATE_FILENAME).read_text())
    assert state["anthropic_done"] is True
    assert state["gemini_done"] is True


def test_resume_skips_already_done_steps(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    (tmp_path / STATE_FILENAME).write_text(
        json.dumps({"anthropic_done": True, "gemini_done": False})
    )
    (tmp_path / ENV_FILENAME).write_text("ANTHROPIC_API_KEY=already\n")
    stdin = io.StringIO("AIza\na\n")
    stdout = io.StringIO()
    run_wizard(
        cfg,
        stdin=stdin,
        stdout=stdout,
        validators={"anthropic": _always_ok, "gemini": _always_ok},
    )
    captured = stdout.getvalue()
    assert "already configured, skipping" in captured
    env_text = (tmp_path / ENV_FILENAME).read_text()
    assert "ANTHROPIC_API_KEY=already" in env_text
    assert "GEMINI_API_KEY=AIza" in env_text


def test_env_file_mode_is_0600_on_posix(tmp_path: Path) -> None:
    if os.name != "posix":
        pytest.skip("POSIX-only test")
    cfg = _config(tmp_path)
    stdin = io.StringIO("sk-ant\n\n")
    stdout = io.StringIO()
    run_wizard(
        cfg,
        stdin=stdin,
        stdout=stdout,
        validators={"anthropic": _always_ok, "gemini": _always_ok},
    )
    env_path = tmp_path / ENV_FILENAME
    mode = env_path.stat().st_mode & 0o777
    assert mode == 0o600


def test_wizard_prints_provider_links(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    stdin = io.StringIO("\n\n")
    stdout = io.StringIO()
    run_wizard(
        cfg, stdin=stdin, stdout=stdout, validators={"anthropic": _always_ok, "gemini": _always_ok}
    )
    out = stdout.getvalue()
    assert "console.anthropic.com" in out
    assert "aistudio.google.com" in out


def test_default_provider_prompt_picks_gemini(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    stdin = io.StringIO("sk-ant\nAIza\ng\n")
    stdout = io.StringIO()
    run_wizard(
        cfg,
        stdin=stdin,
        stdout=stdout,
        validators={"anthropic": _always_ok, "gemini": _always_ok},
    )
    reloaded = Config.load(tmp_path)
    assert reloaded.default_provider == "gemini"
