"""Top-level agent runtime entry points.

`run_agent` and `run_agent_async` dispatch one turn to the correct
provider module.

`run_agent_loop` orchestrates the multi-turn tool-use loop. There is
no abstraction layer above the provider SDKs; each provider exposes a
`Conversation` class with native message history, and this module's
only job is provider selection and uniform return shape.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from horus_os._providers import _anthropic, _gemini
from horus_os.tools.delegation import IterationBudget
from horus_os.tools.loop import execute_tool_uses
from horus_os.tools.registry import ToolRegistry
from horus_os.types import AgentResult, Tool, ToolResult

SUPPORTED_PROVIDERS = ("anthropic", "gemini")


def _check_provider(provider: str) -> None:
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Unknown provider {provider!r}. Supported providers: {SUPPORTED_PROVIDERS}"
        )


def _new_conversation(
    provider: str,
    model: str | None,
    *,
    system_prompt: str | None = None,
) -> Any:
    if provider == "anthropic":
        return _anthropic.Conversation(model=model, system_prompt=system_prompt)
    return _gemini.Conversation(model=model, system_prompt=system_prompt)


def run_agent(
    prompt: str,
    *,
    provider: str = "anthropic",
    tools: list[Tool] | None = None,
    model: str | None = None,
    **kwargs: Any,
) -> AgentResult:
    """Run one agent turn synchronously against the chosen provider."""
    _check_provider(provider)
    if provider == "anthropic":
        return _anthropic.call_anthropic(prompt, tools=tools, model=model, **kwargs)
    return _gemini.call_gemini(prompt, tools=tools, model=model, **kwargs)


async def run_agent_async(
    prompt: str,
    *,
    provider: str = "anthropic",
    tools: list[Tool] | None = None,
    model: str | None = None,
    **kwargs: Any,
) -> AgentResult:
    """Run one agent turn asynchronously against the chosen provider."""
    _check_provider(provider)
    if provider == "anthropic":
        return await _anthropic.call_anthropic_async(prompt, tools=tools, model=model, **kwargs)
    return await _gemini.call_gemini_async(prompt, tools=tools, model=model, **kwargs)


def run_agent_loop(
    prompt: str,
    *,
    registry: ToolRegistry,
    provider: str = "anthropic",
    model: str | None = None,
    max_iterations: int = 10,
    budget: IterationBudget | None = None,
    system_prompt: str | None = None,
    on_tool_result: Callable[[ToolResult], None] | None = None,
) -> AgentResult:
    """Run the multi-turn tool-use loop.

    Sends `prompt`, executes any tool_uses the model returns through
    `registry`, sends the tool_results back, and repeats until the
    model returns a text-only response or the iteration budget is
    exhausted.

    `budget` is an optional `IterationBudget` shared across a delegation
    tree. When None a fresh budget of `max_iterations` is created so
    existing single-agent callers behave unchanged. When provided,
    `max_iterations` is ignored.

    `system_prompt` is forwarded to the provider's Conversation and
    applied on every turn.

    `on_tool_result` (if provided) is called with each ToolResult as
    it is captured. Logger exceptions are swallowed by
    `execute_tool_uses`.
    """
    _check_provider(provider)
    if budget is None and max_iterations < 1:
        raise ValueError("max_iterations must be >= 1")
    _budget = budget if budget is not None else IterationBudget(max_iterations)
    conversation = _new_conversation(provider, model, system_prompt=system_prompt)
    tools = registry.list()
    result = conversation.send(prompt=prompt, tools=tools)
    while result.tool_uses:
        if not _budget.consume():
            break
        outcomes = execute_tool_uses(registry, result, on_log=on_tool_result)
        result = conversation.send(tool_results=outcomes, tools=tools)
    return result
