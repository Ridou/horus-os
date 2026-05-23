"""Anthropic provider for the horus-os agent runtime.

The `anthropic` SDK is imported lazily inside the call functions so
the package loads cleanly without the SDK installed.
"""

from __future__ import annotations

from typing import Any

from horus_os.types import AgentResult, Tool, ToolUse

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 1024


def _tools_to_anthropic(tools: list[Tool] | None) -> list[dict[str, Any]] | None:
    if not tools:
        return None
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.parameters,
        }
        for tool in tools
    ]


def _parse_anthropic_response(response: Any, provider: str, model: str) -> AgentResult:
    text_parts: list[str] = []
    tool_uses: list[ToolUse] = []
    for block in getattr(response, "content", []) or []:
        block_type = getattr(block, "type", None)
        if block_type == "text":
            text_parts.append(getattr(block, "text", ""))
        elif block_type == "tool_use":
            tool_uses.append(
                ToolUse(
                    id=getattr(block, "id", ""),
                    name=getattr(block, "name", ""),
                    input=dict(getattr(block, "input", {}) or {}),
                )
            )
    usage_obj = getattr(response, "usage", None)
    usage: dict[str, Any] = {}
    if usage_obj is not None:
        for key in (
            "input_tokens",
            "output_tokens",
            "cache_creation_input_tokens",
            "cache_read_input_tokens",
        ):
            value = getattr(usage_obj, key, None)
            if value is not None:
                usage[key] = value
    return AgentResult(
        text="".join(text_parts),
        tool_uses=tool_uses,
        provider=provider,
        model=model,
        usage=usage,
    )


def call_anthropic(
    prompt: str,
    *,
    tools: list[Tool] | None = None,
    model: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    **kwargs: Any,
) -> AgentResult:
    """Sync Anthropic call. Reads `ANTHROPIC_API_KEY` from the environment."""
    from anthropic import Anthropic

    chosen_model = model or DEFAULT_MODEL
    client = Anthropic()
    request: dict[str, Any] = {
        "model": chosen_model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    anthropic_tools = _tools_to_anthropic(tools)
    if anthropic_tools is not None:
        request["tools"] = anthropic_tools
    request.update(kwargs)
    response = client.messages.create(**request)
    return _parse_anthropic_response(response, provider="anthropic", model=chosen_model)


async def call_anthropic_async(
    prompt: str,
    *,
    tools: list[Tool] | None = None,
    model: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    **kwargs: Any,
) -> AgentResult:
    """Async Anthropic call. Reads `ANTHROPIC_API_KEY` from the environment."""
    from anthropic import AsyncAnthropic

    chosen_model = model or DEFAULT_MODEL
    client = AsyncAnthropic()
    request: dict[str, Any] = {
        "model": chosen_model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    anthropic_tools = _tools_to_anthropic(tools)
    if anthropic_tools is not None:
        request["tools"] = anthropic_tools
    request.update(kwargs)
    response = await client.messages.create(**request)
    return _parse_anthropic_response(response, provider="anthropic", model=chosen_model)
