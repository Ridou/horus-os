"""Tests for ToolRegistry."""

from __future__ import annotations

import pytest

from horus_os import Tool, ToolRegistry


def _tool(name: str = "echo", with_handler: bool = True) -> Tool:
    return Tool(
        name=name,
        description=f"{name} tool",
        parameters={"type": "object"},
        handler=(lambda **kwargs: kwargs) if with_handler else None,
    )


def test_register_and_get() -> None:
    registry = ToolRegistry()
    tool = _tool()
    registry.register(tool)
    assert registry.get("echo") is tool
    assert "echo" in registry
    assert len(registry) == 1


def test_register_rejects_duplicate_by_default() -> None:
    registry = ToolRegistry()
    registry.register(_tool())
    with pytest.raises(ValueError, match="already registered"):
        registry.register(_tool())


def test_register_replace_allows_overwrite() -> None:
    registry = ToolRegistry()
    a = _tool()
    b = _tool()
    registry.register(a)
    registry.register(b, replace=True)
    assert registry.get("echo") is b


def test_get_returns_none_for_unknown() -> None:
    assert ToolRegistry().get("nope") is None


def test_list_returns_all_tools_in_insertion_order() -> None:
    registry = ToolRegistry()
    a, b, c = _tool("a"), _tool("b"), _tool("c")
    registry.register(a)
    registry.register(b)
    registry.register(c)
    assert [t.name for t in registry.list()] == ["a", "b", "c"]


def test_unregister_removes_tool() -> None:
    registry = ToolRegistry()
    registry.register(_tool())
    registry.unregister("echo")
    assert "echo" not in registry
    registry.unregister("not_registered")  # no-op, must not raise


def test_invoke_calls_handler_with_input_dict() -> None:
    registry = ToolRegistry()
    captured: dict = {}

    def handler(**kwargs):
        captured.update(kwargs)
        return "ok"

    registry.register(
        Tool(name="t", description="t", parameters={"type": "object"}, handler=handler)
    )
    result = registry.invoke("t", {"a": 1, "b": "x"})
    assert result == "ok"
    assert captured == {"a": 1, "b": "x"}


def test_invoke_unknown_tool_raises_keyerror() -> None:
    with pytest.raises(KeyError, match="not registered"):
        ToolRegistry().invoke("nope", {})


def test_invoke_handler_less_tool_raises_runtimeerror() -> None:
    registry = ToolRegistry()
    registry.register(_tool(with_handler=False))
    with pytest.raises(RuntimeError, match="no handler"):
        registry.invoke("echo", {})
