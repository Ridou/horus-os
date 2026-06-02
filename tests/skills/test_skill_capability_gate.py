"""SK-1 capability gate tests (Phase 74, SKILL-03, T-74-08).

A prompt-template skill runs for any agent. A code-bearing skill refuses to run
unless the invoking agent profile holds the SKILL_EXEC grant. Default-deny: an
empty grant set blocks every code skill and runs nothing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from horus_os.plugins.capability_catalog import Capability
from horus_os.skills import SkillAuthorizationError, SkillExecutor, SkillStore, use_skill_tool
from horus_os.tools.delegation import IterationBudget
from horus_os.tools.registry import ToolRegistry
from horus_os.types import AgentResult

CODE_SKILL = """---
name: deploy
description: A code-bearing skill that runs embedded steps.
kind: code
---

# Deploy

Run the deployment steps.
"""

PROMPT_SKILL = """---
name: notes
description: A pure prompt-template skill.
kind: prompt-template
---

# Notes

Just instructions, no code.
"""


def _write(skills_dir: Path, filename: str, text: str) -> None:
    skills_dir.mkdir(parents=True, exist_ok=True)
    (skills_dir / filename).write_text(text, encoding="utf-8")


def _stub_run_agent_loop(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Stub run_agent_loop to record every prompt it is asked to run."""
    ran: list[str] = []

    def fake(prompt: str, **kwargs: Any) -> AgentResult:
        ran.append(prompt)
        return AgentResult(text="ran", tool_uses=[], provider="anthropic", model="m")

    monkeypatch.setattr("horus_os.agent.run_agent_loop", fake)
    return ran


def test_skill_exec_capability_member_and_description_present() -> None:
    # The import-time assert in capability_catalog guarantees the description
    # landed alongside the member; assert both ends explicitly here too.
    assert Capability.SKILL_EXEC == "skill.exec"
    from horus_os.plugins.capability_catalog import DESCRIPTIONS

    assert Capability.SKILL_EXEC in DESCRIPTIONS


def test_code_skill_without_grant_runs_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    skills_dir = tmp_path / "skills"
    _write(skills_dir, "deploy.md", CODE_SKILL)
    ran = _stub_run_agent_loop(monkeypatch)

    executor = SkillExecutor(
        store=SkillStore(skills_dir),
        master_registry=ToolRegistry(),
        agent_allowed_tools=None,
        granted_capabilities=set(),  # default-deny
    )
    with pytest.raises(SkillAuthorizationError):
        executor.run("deploy", budget=IterationBudget(5))
    # Nothing was executed.
    assert ran == []


def test_code_skill_with_grant_proceeds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    skills_dir = tmp_path / "skills"
    _write(skills_dir, "deploy.md", CODE_SKILL)
    ran = _stub_run_agent_loop(monkeypatch)

    executor = SkillExecutor(
        store=SkillStore(skills_dir),
        master_registry=ToolRegistry(),
        agent_allowed_tools=None,
        granted_capabilities={str(Capability.SKILL_EXEC)},
    )
    out = executor.run("deploy", budget=IterationBudget(5))
    assert out == "ran"
    assert len(ran) == 1


def test_prompt_template_skill_runs_without_any_grant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    skills_dir = tmp_path / "skills"
    _write(skills_dir, "notes.md", PROMPT_SKILL)
    ran = _stub_run_agent_loop(monkeypatch)

    executor = SkillExecutor(
        store=SkillStore(skills_dir),
        master_registry=ToolRegistry(),
        agent_allowed_tools=None,
        granted_capabilities=set(),  # no grants at all
    )
    out = executor.run("notes", budget=IterationBudget(5))
    assert out == "ran"
    assert len(ran) == 1


def test_use_skill_tool_returns_error_string_for_ungranted_code_skill(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    skills_dir = tmp_path / "skills"
    _write(skills_dir, "deploy.md", CODE_SKILL)
    ran = _stub_run_agent_loop(monkeypatch)

    tool = use_skill_tool(
        store=SkillStore(skills_dir),
        master_registry=ToolRegistry(),
        agent_allowed_tools=None,
        granted_capabilities=set(),
        budget=IterationBudget(5),
    )
    assert tool.handler is not None
    out = tool.handler(name="deploy")
    # The recoverable code-skill denial surfaces as an error string so the loop
    # captures it and the invocation still traces.
    assert isinstance(out, str)
    assert "deploy" in out
    assert str(Capability.SKILL_EXEC) in out
    assert ran == []
