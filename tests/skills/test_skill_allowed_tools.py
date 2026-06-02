"""SK-3 allowed_tools enforcement tests (Phase 74, SKILL-03, T-74-09).

A skill body's sub-tool calls dispatch through a registry filtered to the
invoking agent's allowed_tools (intersected with the skill's own). A sub-tool
outside that intersection is ABSENT from the filtered registry, so dispatch
raises a KeyError out of the registry rather than silently succeeding. A
sub-tool inside the intersection succeeds. There is no trusted bypass: the
executor reuses _filter_registry, the same primitive delegation uses.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from horus_os.skills import SkillExecutor, SkillStore
from horus_os.skills.executor import _intersect_allowed_tools
from horus_os.tools.delegation import IterationBudget
from horus_os.tools.registry import ToolRegistry
from horus_os.types import AgentResult, Tool, ToolUse

SKILL_CALLS_SECRET = """---
name: caller
description: A skill whose body calls a tool.
kind: prompt-template
---

# Caller

Call the secret tool.
"""


def _write(skills_dir: Path, text: str) -> None:
    skills_dir.mkdir(parents=True, exist_ok=True)
    (skills_dir / "caller.md").write_text(text, encoding="utf-8")


def _make_tool(name: str, calls: list[str] | None = None) -> Tool:
    def _handler(**_: Any) -> str:
        if calls is not None:
            calls.append(name)
        return f"{name}-output"

    return Tool(
        name=name,
        description=name,
        parameters={"type": "object", "properties": {}},
        handler=_handler,
    )


class _ToolThenDoneConversation:
    """Turn 1 asks for a tool; turn 2 returns text once the result comes back.

    The turn-2 text echoes the tool_result so a test can assert whether the
    sub-tool ran or whether the registry refused it.
    """

    def __init__(self, tool_name: str) -> None:
        self._turn = 0
        self._tool_name = tool_name

    def send(self, **kwargs: Any) -> AgentResult:
        self._turn += 1
        if self._turn == 1:
            return AgentResult(
                text="",
                tool_uses=[ToolUse(id="tu_1", name=self._tool_name, input={})],
                provider="anthropic",
                model="m",
            )
        # Surface the tool outcome the loop captured so the test can assert on
        # whether the call succeeded or was refused by the filtered registry.
        results = kwargs.get("tool_results") or []
        echoed = ""
        if results:
            r = results[0]
            echoed = r.error if r.error is not None else str(r.output)
        return AgentResult(text=echoed, tool_uses=[], provider="anthropic", model="m")


def _master_registry(calls: list[str] | None = None) -> ToolRegistry:
    master = ToolRegistry()
    master.register(_make_tool("safe_tool", calls))
    master.register(_make_tool("secret_tool", calls))
    return master


# ---------------------------------------------------------------------------
# _intersect_allowed_tools (the SK-3 floor primitive)
# ---------------------------------------------------------------------------


def test_intersect_agent_none_skill_none_is_none() -> None:
    assert _intersect_allowed_tools(None, None) is None


def test_intersect_agent_none_skill_list_narrows_to_skill() -> None:
    assert _intersect_allowed_tools(None, ["a", "b"]) == ["a", "b"]


def test_intersect_agent_list_skill_none_is_agent_floor() -> None:
    assert _intersect_allowed_tools(["a", "b"], None) == ["a", "b"]


def test_intersect_is_the_overlap_preserving_agent_order() -> None:
    assert _intersect_allowed_tools(["a", "b", "c"], ["c", "a"]) == ["a", "c"]


def test_skill_cannot_widen_agent_tool_set() -> None:
    # A skill that lists a tool the agent does not allow cannot gain it.
    assert _intersect_allowed_tools(["a"], ["a", "b", "secret"]) == ["a"]


# ---------------------------------------------------------------------------
# End-to-end SK-3: a body sub-tool call honors the agent floor.
# ---------------------------------------------------------------------------


def test_skill_calling_tool_outside_allowed_tools_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    skills_dir = tmp_path / "skills"
    _write(skills_dir, SKILL_CALLS_SECRET)
    monkeypatch.setattr(
        "horus_os.agent._new_conversation",
        lambda *a, **k: _ToolThenDoneConversation("secret_tool"),
    )

    calls: list[str] = []
    executor = SkillExecutor(
        store=SkillStore(skills_dir),
        master_registry=_master_registry(calls),
        agent_allowed_tools=["safe_tool"],  # secret_tool NOT allowed
        granted_capabilities=set(),
    )
    # The body's sub-tool call to secret_tool hits a filtered registry that
    # does not contain it, so the registry raises KeyError (the authorization
    # error). The error surfaces as the tool outcome; the secret_tool handler
    # NEVER runs (no silent success, no trusted bypass).
    out = executor.run("caller", budget=IterationBudget(5))
    assert "secret_tool" not in calls
    assert "KeyError" in out
    assert "secret_tool" in out


def test_skill_calling_allowed_tool_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    skills_dir = tmp_path / "skills"
    _write(skills_dir, SKILL_CALLS_SECRET)
    monkeypatch.setattr(
        "horus_os.agent._new_conversation",
        lambda *a, **k: _ToolThenDoneConversation("safe_tool"),
    )

    calls: list[str] = []
    executor = SkillExecutor(
        store=SkillStore(skills_dir),
        master_registry=_master_registry(calls),
        agent_allowed_tools=["safe_tool"],  # safe_tool IS allowed
        granted_capabilities=set(),
    )
    out = executor.run("caller", budget=IterationBudget(5))
    # The allowed tool ran and produced its output.
    assert calls == ["safe_tool"]
    assert out == "safe_tool-output"


def test_executor_dispatches_through_filtered_registry_not_a_bypass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The sub-loop receives a registry produced by _filter_registry, proving
    there is no direct-handler bypass of the allowed_tools floor (SK-3)."""
    skills_dir = tmp_path / "skills"
    _write(skills_dir, SKILL_CALLS_SECRET)

    captured: dict[str, Any] = {}

    def fake_run_agent_loop(prompt: str, **kwargs: Any) -> AgentResult:
        captured["registry"] = kwargs["registry"]
        captured["budget"] = kwargs.get("budget")
        return AgentResult(text="ok", tool_uses=[], provider="anthropic", model="m")

    monkeypatch.setattr("horus_os.agent.run_agent_loop", fake_run_agent_loop)

    shared_budget = IterationBudget(7)
    executor = SkillExecutor(
        store=SkillStore(skills_dir),
        master_registry=_master_registry(),
        agent_allowed_tools=["safe_tool"],
        granted_capabilities=set(),
    )
    executor.run("caller", budget=shared_budget)

    scoped = captured["registry"]
    assert "safe_tool" in scoped
    assert "secret_tool" not in scoped
    # The shared budget is threaded through so the skill cannot escape the run.
    assert captured["budget"] is shared_budget
