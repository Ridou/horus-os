"""Tests for execute_tool_uses."""

from __future__ import annotations

from horus_os import (
    AgentResult,
    Tool,
    ToolRegistry,
    ToolResult,
    ToolUse,
    execute_tool_uses,
)


def _result(tool_uses: list[ToolUse]) -> AgentResult:
    return AgentResult(
        text="",
        tool_uses=tool_uses,
        provider="anthropic",
        model="claude-sonnet-4-6",
        usage={},
    )


def _registry_with(name: str, handler) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        Tool(name=name, description=name, parameters={"type": "object"}, handler=handler)
    )
    return registry


def test_empty_tool_uses_returns_empty_list() -> None:
    registry = ToolRegistry()
    outcomes = execute_tool_uses(registry, _result([]))
    assert outcomes == []


def test_single_tool_use_runs_handler() -> None:
    registry = _registry_with("echo", lambda **kwargs: kwargs.get("text", ""))
    use = ToolUse(id="tu_1", name="echo", input={"text": "hi"})
    outcomes = execute_tool_uses(registry, _result([use]))
    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert isinstance(outcome, ToolResult)
    assert outcome.tool_use_id == "tu_1"
    assert outcome.name == "echo"
    assert outcome.output == "hi"
    assert outcome.error is None
    assert outcome.latency_ms is not None
    assert outcome.latency_ms >= 0


def test_handler_exception_is_captured_in_error() -> None:
    def boom(**_):
        raise ValueError("explode")

    registry = _registry_with("boom", boom)
    outcomes = execute_tool_uses(registry, _result([ToolUse(id="tu_1", name="boom", input={})]))
    assert len(outcomes) == 1
    assert outcomes[0].output is None
    assert outcomes[0].error == "ValueError: explode"


def test_loop_continues_after_failure() -> None:
    registry = ToolRegistry()

    def fail(**_):
        raise RuntimeError("nope")

    registry.register(
        Tool(name="fail", description="", parameters={"type": "object"}, handler=fail)
    )
    registry.register(
        Tool(name="ok", description="", parameters={"type": "object"}, handler=lambda **_: "ran")
    )
    uses = [
        ToolUse(id="tu_1", name="fail", input={}),
        ToolUse(id="tu_2", name="ok", input={}),
    ]
    outcomes = execute_tool_uses(registry, _result(uses))
    assert len(outcomes) == 2
    assert outcomes[0].error == "RuntimeError: nope"
    assert outcomes[1].output == "ran"
    assert outcomes[1].error is None


def test_unknown_tool_use_becomes_error_outcome() -> None:
    registry = ToolRegistry()
    use = ToolUse(id="tu_1", name="ghost", input={})
    outcomes = execute_tool_uses(registry, _result([use]))
    assert len(outcomes) == 1
    assert outcomes[0].error is not None
    assert "ghost" in outcomes[0].error


def test_on_log_receives_each_outcome() -> None:
    registry = _registry_with("echo", lambda **kwargs: kwargs)
    logged: list[ToolResult] = []
    uses = [
        ToolUse(id="tu_1", name="echo", input={"n": 1}),
        ToolUse(id="tu_2", name="echo", input={"n": 2}),
    ]
    execute_tool_uses(registry, _result(uses), on_log=logged.append)
    assert [o.tool_use_id for o in logged] == ["tu_1", "tu_2"]


def test_on_log_exception_does_not_break_loop() -> None:
    registry = _registry_with("echo", lambda **kwargs: kwargs)

    def bad_logger(_: ToolResult) -> None:
        raise RuntimeError("logger blew up")

    outcomes = execute_tool_uses(
        registry,
        _result([ToolUse(id="tu_1", name="echo", input={})]),
        on_log=bad_logger,
    )
    assert len(outcomes) == 1
    assert outcomes[0].error is None
