"""Tests for `horus-os run` subcommand."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from horus_os.__main__ import main
from horus_os.cli import run_cmd
from horus_os.types import AgentResult, ToolUse


def _runcli(argv: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = main(argv, stdout=stdout, stderr=stderr)
    return code, stdout.getvalue(), stderr.getvalue()


def _init_installation(tmp_path: Path) -> None:
    _runcli(["init", "--data-dir", str(tmp_path)])


def test_run_requires_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_installation(tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    code, _out, err = _runcli(["run", "hi", "--data-dir", str(tmp_path)])
    assert code == 2
    assert "ANTHROPIC_API_KEY" in err


def test_run_rejects_unknown_provider_via_argparse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_installation(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    # argparse enforces --provider choices before run_run is called and
    # invokes sys.exit(2). We catch SystemExit and confirm the exit code.
    with pytest.raises(SystemExit) as excinfo:
        _runcli(["run", "hi", "--provider", "openai", "--data-dir", str(tmp_path)])
    assert excinfo.value.code == 2


def test_run_requires_init_for_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    code, _out, err = _runcli(["run", "hi", "--data-dir", str(tmp_path)])
    assert code == 1
    assert "horus-os init" in err


def test_run_happy_path_records_trace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_installation(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")

    captured: dict = {}

    def fake_loop(prompt, *, registry, provider, model, max_iterations, on_tool_result):
        captured["prompt"] = prompt
        captured["provider"] = provider
        captured["model"] = model
        return AgentResult(
            text="hello world",
            tool_uses=[],
            provider=provider,
            model=model,
            usage={"input_tokens": 1, "output_tokens": 2},
        )

    monkeypatch.setattr(run_cmd, "run_agent_loop", fake_loop)
    code, out, err = _runcli(["run", "hi", "--data-dir", str(tmp_path)])
    assert code == 0
    assert err == ""
    assert "hello world" in out
    assert captured["prompt"] == "hi"
    assert captured["provider"] == "anthropic"
    assert captured["model"] == "claude-sonnet-4-6"

    # Confirm the trace landed
    from horus_os import Database

    db = Database(tmp_path / "horus.sqlite")
    traces = db.list_traces()
    assert len(traces) == 1
    assert traces[0].prompt == "hi"


def test_run_no_record_skips_trace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_installation(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    monkeypatch.setattr(
        run_cmd,
        "run_agent_loop",
        lambda *a, **k: AgentResult(text="x", provider="anthropic", model="m"),
    )
    code, _out, _err = _runcli(["run", "hi", "--data-dir", str(tmp_path), "--no-record"])
    assert code == 0

    from horus_os import Database

    db = Database(tmp_path / "horus.sqlite")
    assert db.list_traces() == []


def test_run_error_path_records_error_trace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_installation(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")

    def boom(*_, **__):
        raise RuntimeError("provider down")

    monkeypatch.setattr(run_cmd, "run_agent_loop", boom)
    code, _out, err = _runcli(["run", "hi", "--data-dir", str(tmp_path)])
    assert code == 1
    assert "provider down" in err

    from horus_os import Database

    db = Database(tmp_path / "horus.sqlite")
    traces = db.list_traces()
    assert len(traces) == 1
    assert traces[0].status == "error"
    assert "provider down" in (traces[0].error_message or "")


def test_run_prints_tool_summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_installation(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")

    def fake_loop(prompt, *, registry, provider, model, max_iterations, on_tool_result):
        from horus_os.types import ToolResult

        outcome = ToolResult(tool_use_id="tu_1", name="echo", output="hi", error=None, latency_ms=3)
        on_tool_result(outcome)
        return AgentResult(
            text="finished",
            tool_uses=[ToolUse(id="tu_1", name="echo", input={})],
            provider=provider,
            model=model,
            usage={},
        )

    monkeypatch.setattr(run_cmd, "run_agent_loop", fake_loop)
    code, out, _err = _runcli(["run", "hi", "--data-dir", str(tmp_path)])
    assert code == 0
    assert "echo" in out
    assert "1 tool calls" in out


def test_run_uses_gemini_when_provider_overridden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_installation(tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    captured: dict = {}

    def fake_loop(prompt, *, registry, provider, model, **_):
        captured["provider"] = provider
        captured["model"] = model
        return AgentResult(text="ok", provider=provider, model=model)

    monkeypatch.setattr(run_cmd, "run_agent_loop", fake_loop)
    code, _out, _err = _runcli(["run", "hi", "--data-dir", str(tmp_path), "--provider", "gemini"])
    assert code == 0
    assert captured["provider"] == "gemini"
    assert captured["model"] == "gemini-2.5-flash"
