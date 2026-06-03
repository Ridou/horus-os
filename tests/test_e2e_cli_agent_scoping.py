"""CLI `--agent` end-to-end tests for the buffered path.

Phase 19 gap D: `tests/test_cli_run.py` covers the streaming path with
`--agent` (system_prompt and default_model forward correctly). The
buffered path (`--no-stream --agent X`) is not covered for the
allowed_tools forwarding contract.

The v0.2 contract is: the CLI does NOT pre-filter the master registry
by the profile's `allowed_tools`. That filtering is the
`make_delegate_tool` handler's responsibility when a sub-agent gets
spawned. The CLI just forwards the profile's `system_prompt` and
`default_model`. This file pins that contract so a future refactor
that quietly pre-filters the registry surfaces as a test failure.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest

from horus_os import AgentResult, Database
from horus_os.__main__ import main
from horus_os.cli import run_cmd


def _runcli(argv: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = main(argv, stdout=stdout, stderr=stderr)
    return code, stdout.getvalue(), stderr.getvalue()


def _init_installation(tmp_path: Path) -> None:
    _runcli(["init", "--data-dir", str(tmp_path)])


def _create_profile(
    tmp_path: Path,
    *,
    name: str,
    system_prompt: str,
    model: str,
    allowed_tools: str | None = None,
) -> None:
    argv = [
        "agents",
        "create",
        "--name",
        name,
        "--system-prompt",
        system_prompt,
        "--model",
        model,
        "--data-dir",
        str(tmp_path),
    ]
    if allowed_tools is not None:
        argv.extend(["--allowed-tools", allowed_tools])
    code, _out, err = _runcli(argv)
    assert code == 0, err


def test_buffered_run_with_agent_forwards_system_prompt_and_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The buffered run path (`--no-stream --agent X`) forwards the
    profile's system_prompt and default_model into run_agent_loop and
    tags the recorded trace with the profile name.

    Phase 15 Plan 02 tested this on the streaming path only. The
    buffered path mirrors the same precedence and trace tagging.
    """
    _init_installation(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    _create_profile(
        tmp_path,
        name="terse",
        system_prompt="Be terse.",
        model="claude-sonnet-4-6",
    )

    captured: dict[str, Any] = {}

    def fake_loop(
        prompt: str,
        *,
        registry: Any,
        provider: str,
        model: str,
        max_iterations: int,
        on_tool_result: Any,
        system_prompt: str | None = None,
    ) -> AgentResult:
        captured["prompt"] = prompt
        captured["registry"] = registry
        captured["provider"] = provider
        captured["model"] = model
        captured["system_prompt"] = system_prompt
        return AgentResult(text="ok", tool_uses=[], provider=provider, model=model, usage={})

    monkeypatch.setattr(run_cmd, "run_agent_loop", fake_loop)
    code, _out, err = _runcli(
        ["run", "hi", "--data-dir", str(tmp_path), "--no-stream", "--agent", "terse"]
    )
    assert code == 0, err
    assert captured["system_prompt"] == "Be terse."
    assert captured["model"] == "claude-sonnet-4-6"

    db = Database(tmp_path / "horus.sqlite")
    # A fresh init seeds one example demo trace; filter it out so this asserts
    # only on the trace this run recorded.
    traces = [t for t in db.list_traces() if t.provider != "example"]
    assert len(traces) == 1
    assert traces[0].agent_profile_name == "terse"


def test_buffered_run_does_not_prefilter_registry_by_allowed_tools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The CLI does NOT narrow the master registry by the profile's
    allowed_tools. The full registry reaches run_agent_loop unchanged.

    Rationale: the top-level call is the user's loop, not a sub-agent
    invocation. The allowed_tools filter only matters when this
    profile is delegated to via `make_delegate_tool`. A future
    refactor that pre-filters the registry at the CLI boundary would
    silently break library users who rely on the master registry
    being available to the top-level model. This test guards against
    that drift.
    """
    _init_installation(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    _create_profile(
        tmp_path,
        name="scoped",
        system_prompt="Limited.",
        model="claude-sonnet-4-6",
        allowed_tools="read_file",
    )

    captured: dict[str, Any] = {}

    def fake_loop(
        prompt: str,
        *,
        registry: Any,
        provider: str,
        model: str,
        max_iterations: int,
        on_tool_result: Any,
        system_prompt: str | None = None,
    ) -> AgentResult:
        captured["tools"] = {t.name for t in registry.list()}
        captured["system_prompt"] = system_prompt
        return AgentResult(text="ok", tool_uses=[], provider=provider, model=model, usage={})

    monkeypatch.setattr(run_cmd, "run_agent_loop", fake_loop)
    code, _out, err = _runcli(
        ["run", "hi", "--data-dir", str(tmp_path), "--no-stream", "--agent", "scoped"]
    )
    assert code == 0, err
    # The full default registry reached the loop, not just `read_file`.
    # The default registry includes read_file, list_notes, search_notes,
    # read_note, create_note, and append_note.
    assert "read_file" in captured["tools"]
    assert "list_notes" in captured["tools"]
    assert "search_notes" in captured["tools"]
    assert "create_note" in captured["tools"]
    assert len(captured["tools"]) >= 6
    # And the profile's system_prompt did reach the loop.
    assert captured["system_prompt"] == "Limited."
