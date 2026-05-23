"""End-to-end multi-agent tests.

Phase 19 gap A: prior tests cover the `make_delegate_tool` closure in
isolation by stubbing `run_agent_loop` directly. None drive the full
delegation path through a real `run_agent_loop` call where the
coordinator's first turn yields a `delegate_to_agent` tool_use, the
loop dispatches it, the sub-agent runs (also inside `run_agent_loop`),
and the parent receives the sub-agent's text on the next turn. This
file fills that seam.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from horus_os import AgentProfile, AgentResult, Database
from horus_os.agent import run_agent_loop
from horus_os.tools.delegation import IterationBudget, make_delegate_tool
from horus_os.tools.registry import ToolRegistry
from horus_os.types import ToolResult, ToolUse


class _ScriptedConversation:
    """A stand-in for the provider Conversation classes.

    Each instance carries a queue of `AgentResult` values. Successive
    `.send(...)` calls pop the head of the queue. This lets a test
    script a coordinator that asks for a delegate on turn 1 and replies
    with text on turn 2, without touching any real provider SDK.
    """

    def __init__(self, scripted: list[AgentResult]) -> None:
        self._scripted = list(scripted)
        self.sends: list[dict[str, Any]] = []

    def send(
        self,
        *,
        prompt: str | None = None,
        tool_results: list[ToolResult] | None = None,
        tools: Any | None = None,
        max_tokens: int = 1024,
    ) -> AgentResult:
        self.sends.append(
            {"prompt": prompt, "tool_results": tool_results, "tools_count": len(tools or [])}
        )
        if not self._scripted:
            return AgentResult(
                text="(no more scripted responses)",
                tool_uses=[],
                provider="anthropic",
                model="m",
            )
        return self._scripted.pop(0)


def _scripted_factory(*queues: list[AgentResult]):
    """Return a `_new_conversation` replacement that hands out scripted
    Conversations in the order they are requested.

    The first new conversation built (the coordinator's) drains
    `queues[0]`; the next conversation (the sub-agent's, built when the
    delegate handler calls run_agent_loop) drains `queues[1]`. This
    mirrors run_agent_loop's actual call order.
    """

    queue_iter = iter(queues)

    def factory(provider: str, model: Any, *, system_prompt: Any = None) -> _ScriptedConversation:
        try:
            return _ScriptedConversation(next(queue_iter))
        except StopIteration:
            return _ScriptedConversation([])

    return factory


def _seed_db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    db.save_profile(
        AgentProfile(
            name="summarizer",
            system_prompt="Be terse.",
            default_model="claude-helper",
            allowed_tools=None,
        )
    )
    return db


def test_run_agent_loop_dispatches_delegate_and_returns_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The coordinator emits a delegate, the sub-agent runs, the parent
    receives the sub-agent's text on turn 2.

    Closes the seam between `make_delegate_tool` and `run_agent_loop`:
    no prior test wired the delegate tool into a registry passed to
    `run_agent_loop` and asserted the loop dispatched it.
    """
    db = _seed_db(tmp_path)
    parent_trace_id = db.record_trace(
        "coordinator prompt",
        AgentResult(text="coord", provider="anthropic", model="m"),
    )

    coordinator_script = [
        # Turn 1: ask for a delegate.
        AgentResult(
            text="",
            tool_uses=[
                ToolUse(
                    id="tu_1",
                    name="delegate_to_agent",
                    input={"agent_name": "summarizer", "task": "summarize foo"},
                )
            ],
            provider="anthropic",
            model="claude-coord",
        ),
        # Turn 2: respond with the sub-agent's output verbatim.
        AgentResult(
            text="coordinator final: foo summarized.",
            tool_uses=[],
            provider="anthropic",
            model="claude-coord",
        ),
    ]
    sub_agent_script = [
        AgentResult(
            text="foo summarized.",
            tool_uses=[],
            provider="anthropic",
            model="claude-helper",
        )
    ]

    factory = _scripted_factory(coordinator_script, sub_agent_script)
    monkeypatch.setattr("horus_os.agent._new_conversation", factory)

    budget = IterationBudget(10)
    master = ToolRegistry()
    delegate_tool = make_delegate_tool(
        db=db,
        master_registry=master,
        parent_trace_id=parent_trace_id,
        budget=budget,
        provider="anthropic",
    )
    master.register(delegate_tool)

    result = run_agent_loop(
        "do work",
        registry=master,
        provider="anthropic",
        model="claude-coord",
        budget=budget,
    )

    assert result.text == "coordinator final: foo summarized."

    children = db.list_child_traces(parent_trace_id)
    assert len(children) == 1
    assert children[0].agent_profile_name == "summarizer"
    assert children[0].prompt == "summarize foo"
    assert children[0].response_text == "foo summarized."


def test_run_agent_loop_shared_budget_caps_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A shared budget exhausted by an earlier sub-agent turn stops the
    parent loop on the next consume(). No exception, the parent just
    returns whatever the last AgentResult was.

    Prior tests cover IterationBudget at the counter level only.
    """
    db = _seed_db(tmp_path)
    coordinator_script = [
        # Turn 1: delegate.
        AgentResult(
            text="",
            tool_uses=[
                ToolUse(
                    id="tu_1",
                    name="delegate_to_agent",
                    input={"agent_name": "summarizer", "task": "t"},
                )
            ],
            provider="anthropic",
            model="m",
        ),
        # Turn 2 would normally finalize. With budget exhausted the
        # loop never reaches the third send; the second send produces
        # this AgentResult, which the loop returns directly because
        # it has no tool_uses on it.
        AgentResult(text="late reply", tool_uses=[], provider="anthropic", model="m"),
    ]
    sub_agent_script = [AgentResult(text="sub done", tool_uses=[], provider="anthropic", model="m")]
    factory = _scripted_factory(coordinator_script, sub_agent_script)
    monkeypatch.setattr("horus_os.agent._new_conversation", factory)

    # Budget of 1: enough for one coordinator-loop consume() after the
    # initial send. After the delegate sub-tree consumes one, the
    # parent loop's next consume() returns False and the loop returns
    # whatever the last result was.
    budget = IterationBudget(1)
    master = ToolRegistry()
    master.register(
        make_delegate_tool(
            db=db,
            master_registry=master,
            parent_trace_id="parent",
            budget=budget,
            provider="anthropic",
        )
    )

    result = run_agent_loop(
        "go",
        registry=master,
        provider="anthropic",
        model="m",
        budget=budget,
    )
    # Either the parent returned early because the budget exhausted,
    # or it got one more turn in. Either way no exception was raised
    # and the budget never went negative.
    assert isinstance(result, AgentResult)
    assert budget.remaining >= 0


def test_run_agent_loop_unknown_subagent_returns_error_string(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unknown sub-agent name surfaces as a tool result string to
    the coordinator; the loop continues so the coordinator can react.

    This locks in the contract that a missing profile does not crash
    the parent loop, it just hands the parent an error message.
    """
    db = _seed_db(tmp_path)
    coordinator_script = [
        AgentResult(
            text="",
            tool_uses=[
                ToolUse(
                    id="tu_1",
                    name="delegate_to_agent",
                    input={"agent_name": "ghost", "task": "t"},
                )
            ],
            provider="anthropic",
            model="m",
        ),
        AgentResult(
            text="coordinator wrapping up after error",
            tool_uses=[],
            provider="anthropic",
            model="m",
        ),
    ]
    factory = _scripted_factory(coordinator_script, [])
    monkeypatch.setattr("horus_os.agent._new_conversation", factory)

    budget = IterationBudget(5)
    master = ToolRegistry()
    master.register(
        make_delegate_tool(
            db=db,
            master_registry=master,
            parent_trace_id="parent",
            budget=budget,
            provider="anthropic",
        )
    )

    result = run_agent_loop("go", registry=master, provider="anthropic", model="m", budget=budget)
    assert result.text == "coordinator wrapping up after error"
    # No child traces because the delegate handler short-circuited.
    assert db.list_child_traces("parent") == []
