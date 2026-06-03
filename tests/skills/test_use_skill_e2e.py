"""End-to-end use_skill flow (Phase 74, SKILL-02, SK-2, T-74-10/T-74-11).

A scripted provider returns a use_skill tool_use; the body sub-loop runs; a
tool_invocations row is written for the use_skill invocation under the run
trace_id (SKILL-02 "traced"). The level-1 menu in the tool description never
contains the skill body (progressive disclosure). Registration refuses a skill
whose name shadows a builtin tool (SK-2).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from horus_os import AgentResult, Database
from horus_os.agent import run_agent_loop
from horus_os.observability import get_observation_bus, reset_observation_bus_for_tests
from horus_os.observability.persist import SQLitePersister
from horus_os.skills import SkillStore, register_use_skill
from horus_os.tools import ToolRegistry
from horus_os.tools.delegation import IterationBudget
from horus_os.tools.registry import CollisionError
from horus_os.types import Tool, ToolUse

SKILL = """---
name: summarize
description: Summarize text into bullet points.
kind: prompt-template
---

# Summarize

LEVEL_2_BODY_MARKER: read the text and produce concise bullet points.
"""

SHADOW_SKILL = """---
name: read_note
description: A skill that tries to shadow the builtin read_note tool.
kind: prompt-template
---

# Shadow

Body.
"""


def _write(skills_dir: Path, filename: str, text: str) -> None:
    skills_dir.mkdir(parents=True, exist_ok=True)
    (skills_dir / filename).write_text(text, encoding="utf-8")


class _ScriptedConversation:
    """Turn 1 calls use_skill; later turns return text."""

    def __init__(self, scripted: list[AgentResult]) -> None:
        self._scripted = list(scripted)

    def send(self, **kwargs: Any) -> AgentResult:
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


def test_use_skill_invocation_writes_a_tool_invocations_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    skills_dir = tmp_path / "skills"
    _write(skills_dir, "summarize.md", SKILL)

    db = Database(tmp_path / "horus.sqlite")
    db.init()

    # Wire a fresh bus + persister so tool_invocations rows actually land.
    reset_observation_bus_for_tests()
    persister = SQLitePersister(db)
    get_observation_bus().subscribe(persister.on_event)

    # Seed the traces row so the persister has a target if a RUN_END fires.
    trace_id = db.record_trace("do work", AgentResult(text="seed", provider="anthropic", model="m"))

    # The top-level (coordinator) conversation calls use_skill on turn 1, then
    # finalizes on turn 2. The skill body sub-loop runs as the next conversation
    # and returns text immediately.
    coordinator = [
        AgentResult(
            text="",
            tool_uses=[ToolUse(id="tu_1", name="use_skill", input={"name": "summarize"})],
            provider="anthropic",
            model="m",
        ),
        AgentResult(text="final answer", tool_uses=[], provider="anthropic", model="m"),
    ]
    sub_loop = [AgentResult(text="bullets", tool_uses=[], provider="anthropic", model="m")]
    monkeypatch.setattr("horus_os.agent._new_conversation", _factory(coordinator, sub_loop))

    budget = IterationBudget(10)
    registry = ToolRegistry()
    registered = register_use_skill(
        registry,
        store=SkillStore(skills_dir),
        agent_allowed_tools=None,
        granted_capabilities=set(),
        parent_trace_id=trace_id,
        budget=budget,
    )
    assert registered is True

    # Progressive disclosure: the level-1 menu (the tool description the model
    # sees) carries the name + description but NEVER the body.
    use_skill = registry.get("use_skill")
    assert "summarize" in use_skill.description
    assert "LEVEL_2_BODY_MARKER" not in use_skill.description

    result = run_agent_loop(
        "do work",
        registry=registry,
        provider="anthropic",
        model="m",
        budget=budget,
        trace_id=trace_id,
    )
    assert result.text == "final answer"

    # SKILL-02 "traced": exactly one tool_invocations row for use_skill under
    # the run trace_id.
    with sqlite3.connect(str(db.path)) as conn:
        rows = conn.execute(
            "SELECT tool_name, trace_id, status FROM tool_invocations WHERE tool_name = 'use_skill'"
        ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "use_skill"
    assert rows[0][1] == trace_id
    assert rows[0][2] == "success"


def test_skill_shadowing_a_builtin_tool_is_refused(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write(skills_dir, "read_note.md", SHADOW_SKILL)

    registry = ToolRegistry()
    # A builtin read_note tool is already registered.
    registry.register(
        Tool(
            name="read_note",
            description="builtin read_note",
            parameters={"type": "object", "properties": {}},
            handler=lambda **_: "note",
        )
    )
    # SK-2: registering use_skill must refuse the colliding skill rather than
    # let it shadow the builtin.
    with pytest.raises(CollisionError) as exc:
        register_use_skill(
            registry,
            store=SkillStore(skills_dir),
            agent_allowed_tools=None,
            granted_capabilities=set(),
        )
    assert "read_note" in str(exc.value)


def test_install_with_no_skills_registers_no_use_skill_tool(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()  # exists but empty
    registry = ToolRegistry()
    registered = register_use_skill(
        registry,
        store=SkillStore(skills_dir),
        agent_allowed_tools=None,
        granted_capabilities=set(),
    )
    # No skills => no use_skill tool => byte-identical to before.
    assert registered is False
    assert "use_skill" not in registry
