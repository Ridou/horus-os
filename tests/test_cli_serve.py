"""Tests for `horus-os serve` (stub)."""

from __future__ import annotations

import io

from horus_os.__main__ import main


def test_serve_stub_prints_message_and_exits_zero() -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = main(["serve"], stdout=stdout, stderr=stderr)
    assert code == 0
    assert "not yet implemented" in stdout.getvalue()
    assert stderr.getvalue() == ""


def test_top_level_no_command_prints_help() -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = main([], stdout=stdout, stderr=stderr)
    assert code == 0
    assert "usage:" in stdout.getvalue().lower()
    assert "init" in stdout.getvalue()
    assert "traces" in stdout.getvalue()
    assert "serve" in stdout.getvalue()
