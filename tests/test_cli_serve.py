"""Tests for `horus-os serve`."""

from __future__ import annotations

import io
import sys
from typing import Any

import pytest

from horus_os.__main__ import main
from horus_os.cli import serve_cmd


def test_top_level_no_command_prints_help() -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = main([], stdout=stdout, stderr=stderr)
    assert code == 0
    assert "usage:" in stdout.getvalue().lower()
    assert "init" in stdout.getvalue()
    assert "traces" in stdout.getvalue()
    assert "serve" in stdout.getvalue()
    assert "run" in stdout.getvalue()


def test_serve_invokes_uvicorn(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class _FakeUvicorn:
        @staticmethod
        def run(app: Any, **kwargs: Any) -> None:
            captured["app"] = app
            captured.update(kwargs)

    monkeypatch.setitem(sys.modules, "uvicorn", _FakeUvicorn)
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = main(
        ["serve", "--host", "0.0.0.0", "--port", "9000"],
        stdout=stdout,
        stderr=stderr,
    )
    assert code == 0
    assert "Serving horus-os on http://0.0.0.0:9000" in stdout.getvalue()
    assert captured["host"] == "0.0.0.0"
    assert captured["port"] == 9000
    assert captured["app"] is not None


def test_serve_reports_missing_dashboard_extra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import = (
        serve_cmd.__builtins__["__import__"]
        if isinstance(serve_cmd.__builtins__, dict)
        else __import__
    )

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "uvicorn":
            raise ImportError("No module named 'uvicorn'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = main(["serve"], stdout=stdout, stderr=stderr)
    assert code == 2
    assert "[dashboard]" in stderr.getvalue()
