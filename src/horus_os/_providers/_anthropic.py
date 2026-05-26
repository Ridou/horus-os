"""Anthropic provider for the horus-os agent runtime.

The `anthropic` SDK is imported lazily inside the call functions so
the package loads cleanly without the SDK installed.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from horus_os._providers._stream_types import _StreamUsage
from horus_os.types import AgentResult, Tool, ToolCallEvent, ToolResult, ToolUse

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


async def stream_anthropic_async(
    prompt: str,
    *,
    model: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    system: str | None = None,
) -> AsyncGenerator[str | ToolCallEvent | _StreamUsage, None]:
    """Stream incremental text tokens from Anthropic, then any tool-call events.

    Yields each text delta as a `str`. After the text stream completes, the
    final message is inspected and any `tool_use` blocks are emitted as
    `ToolCallEvent` values so consumers can observe them. This function does
    not execute tools, by design. See `run_agent_loop` for tool dispatch.

    Phase 33: after the tool_use blocks (or the last text chunk when no
    tool_use is present), yields a terminal `_StreamUsage` sentinel
    carrying `final_msg.usage` so the SSE handler can persist non-zero
    token counts (PITFALLS.md Pitfall 2). Existing consumers that
    iterate only for str / ToolCallEvent will see the sentinel as an
    unknown chunk type, which they should ignore; the SSE handler
    isinstance-checks for it explicitly.
    """
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic()
    request: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        request["system"] = system
    async with client.messages.stream(**request) as stream:
        async for text in stream.text_stream:
            yield text
        final_msg = await stream.get_final_message()
        for block in getattr(final_msg, "content", []) or []:
            if getattr(block, "type", None) == "tool_use":
                yield ToolCallEvent(
                    name=getattr(block, "name", ""),
                    input=dict(getattr(block, "input", {}) or {}),
                )
        # Phase 33 terminal sentinel: extract the Anthropic usage shape
        # off the final message so the SSE handler can persist real
        # token counts. Empty dict signals "no usage available" and the
        # consumer falls back to a char-count estimate.
        usage_dict: dict[str, Any] = {}
        usage_obj = getattr(final_msg, "usage", None)
        if usage_obj is not None:
            for key in (
                "input_tokens",
                "output_tokens",
                "cache_creation_input_tokens",
                "cache_read_input_tokens",
            ):
                value = getattr(usage_obj, key, None)
                if value is not None:
                    usage_dict[key] = value
        yield _StreamUsage(usage=usage_dict)


class Conversation:
    """Multi-turn Anthropic conversation. Holds message history in the native SDK shape."""

    def __init__(self, *, model: str | None = None, system_prompt: str | None = None) -> None:
        from anthropic import Anthropic

        self._client = Anthropic()
        self._model = model or DEFAULT_MODEL
        self._messages: list[dict[str, Any]] = []
        self._last_assistant_content: list[Any] = []
        self._system_prompt = system_prompt or ""

    @property
    def model(self) -> str:
        return self._model

    def send(
        self,
        *,
        prompt: str | None = None,
        tool_results: list[ToolResult] | None = None,
        tools: list[Tool] | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> AgentResult:
        if prompt is None and tool_results is None:
            raise ValueError("Conversation.send requires either prompt or tool_results")
        if prompt is not None and tool_results is not None:
            raise ValueError("Conversation.send accepts prompt or tool_results, not both")
        if prompt is not None:
            self._messages.append({"role": "user", "content": prompt})
        else:
            assert tool_results is not None
            if self._last_assistant_content:
                self._messages.append(
                    {"role": "assistant", "content": self._last_assistant_content}
                )
            content_blocks: list[dict[str, Any]] = []
            for r in tool_results:
                block: dict[str, Any] = {
                    "type": "tool_result",
                    "tool_use_id": r.tool_use_id,
                    "content": r.error if r.error is not None else str(r.output),
                }
                if r.error is not None:
                    block["is_error"] = True
                content_blocks.append(block)
            self._messages.append({"role": "user", "content": content_blocks})

        request: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": self._messages,
        }
        # Anthropic requires `system` on every messages.create call, so it
        # must be sent on every send() turn (not just the first prompt).
        if self._system_prompt:
            request["system"] = self._system_prompt
        anthropic_tools = _tools_to_anthropic(tools)
        if anthropic_tools is not None:
            request["tools"] = anthropic_tools
        response = self._client.messages.create(**request)
        self._last_assistant_content = list(getattr(response, "content", []) or [])
        return _parse_anthropic_response(response, provider="anthropic", model=self._model)
