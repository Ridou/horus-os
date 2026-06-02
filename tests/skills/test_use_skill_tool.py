"""Tests for the use_skill tool and progressive disclosure (Phase 74, SKILL-02).

The use_skill tool exposes a level-1 menu of skill names and descriptions only;
the body loads on call. An unknown name returns an error string (recoverable
through the loop, never a crashing exception). A prompt-template skill loads its
full body and runs, and the body was never present in the level-1 menu.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from horus_os.skills import SkillStore, use_skill_tool
from horus_os.tools.delegation import IterationBudget
from horus_os.tools.registry import ToolRegistry
from horus_os.types import AgentResult

PROMPT_SKILL = """---
name: summarize
description: Summarize a block of text into bullet points.
kind: prompt-template
---

# Summarize

SECRET_BODY_MARKER: read the text and produce three concise bullet points.
"""


class _ScriptedConversation:
    """Stand-in for a provider Conversation that returns scripted results."""

    def __init__(self, scripted: list[AgentResult]) -> None:
        self._scripted = list(scripted)
        self.sends: list[dict[str, Any]] = []

    def send(self, **kwargs: Any) -> AgentResult:
        self.sends.append(kwargs)
        if not self._scripted:
            return AgentResult(text="(done)", tool_uses=[], provider="anthropic", model="m")
        return self._scripted.pop(0)


def _factory(*queues: list[AgentResult]):
    queue_iter = iter(queues)

    def factory(provider: str, model: Any, *, system_prompt: Any = None) -> _ScriptedConversation:
        try:
            return _ScriptedConversation(next(queue_iter))
        except StopIteration:
            return _ScriptedConversation([])

    return factory


def _write(skills_dir: Path, filename: str, text: str) -> None:
    skills_dir.mkdir(parents=True, exist_ok=True)
    (skills_dir / filename).write_text(text, encoding="utf-8")


def _make_tool(store: SkillStore, **overrides: Any):
    kwargs: dict[str, Any] = {
        "store": store,
        "master_registry": ToolRegistry(),
        "agent_allowed_tools": None,
        "granted_capabilities": set(),
        "provider": "anthropic",
        "parent_trace_id": None,
        "budget": IterationBudget(5),
    }
    kwargs.update(overrides)
    return use_skill_tool(**kwargs)


def test_use_skill_tool_is_named_use_skill_with_name_param(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write(skills_dir, "summarize.md", PROMPT_SKILL)
    tool = _make_tool(SkillStore(skills_dir))
    assert tool.name == "use_skill"
    assert tool.parameters["required"] == ["name"]
    assert "name" in tool.parameters["properties"]
    assert "args" in tool.parameters["properties"]


def test_level_1_menu_lists_names_and_descriptions_only(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write(skills_dir, "summarize.md", PROMPT_SKILL)
    tool = _make_tool(SkillStore(skills_dir))
    # The menu carries the name and description.
    assert "summarize" in tool.description
    assert "Summarize a block of text" in tool.description
    # Progressive disclosure: the body marker must NEVER appear in the menu.
    assert "SECRET_BODY_MARKER" not in tool.description


def test_unknown_skill_returns_error_string_not_exception(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write(skills_dir, "summarize.md", PROMPT_SKILL)
    tool = _make_tool(SkillStore(skills_dir))
    assert tool.handler is not None
    out = tool.handler(name="does-not-exist")
    assert isinstance(out, str)
    assert "not found" in out.lower()
    assert "does-not-exist" in out


def test_prompt_template_skill_loads_body_and_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    skills_dir = tmp_path / "skills"
    _write(skills_dir, "summarize.md", PROMPT_SKILL)

    sub_loop_prompts: list[str] = []

    class _CapturingConversation(_ScriptedConversation):
        def send(self, **kwargs: Any) -> AgentResult:
            if "prompt" in kwargs and kwargs["prompt"] is not None:
                sub_loop_prompts.append(kwargs["prompt"])
            return super().send(**kwargs)

    def factory(provider: str, model: Any, *, system_prompt: Any = None):
        return _CapturingConversation(
            [
                AgentResult(
                    text="bullet points produced", tool_uses=[], provider="anthropic", model="m"
                )
            ]
        )

    monkeypatch.setattr("horus_os.agent._new_conversation", factory)

    tool = _make_tool(SkillStore(skills_dir))
    assert tool.handler is not None
    out = tool.handler(name="summarize")
    assert out == "bullet points produced"
    # The full body (level-2) was loaded and fed to the sub-loop.
    assert len(sub_loop_prompts) == 1
    assert "SECRET_BODY_MARKER" in sub_loop_prompts[0]
