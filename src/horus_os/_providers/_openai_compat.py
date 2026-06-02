"""OpenAI-compatible local provider for the horus-os agent runtime.

One adapter covers every OpenAI-compatible local server (Ollama,
llama.cpp server, vLLM, LM Studio) plus OpenRouter via the `openai`
SDK `base_url` override. It mirrors the `_anthropic.py` / `_gemini.py`
module surface name-for-name.

The `openai` SDK is imported lazily inside the call functions so the
package loads cleanly without the SDK installed, matching the
lazy-import idiom of the other provider modules.

LP-1 (PITFALLS.md): the OpenAI-compatible `/v1/chat/completions`
endpoint on Ollama silently drops tool-call blocks when
`stream=True`; the tool loop then receives no tool calls and the
agent gives a non-tool answer with no error. To keep tool calling
reliable, every request that carries a tools list is sent with
streaming disabled (the SDK default, non-stream) so buffered
tool_calls are returned intact. Tool dispatch always flows through
the buffered `Conversation` path. The standalone
`stream_openai_compat_async` exists only for the no-tools chat
surface that `run_agent_stream` drives.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncGenerator
from typing import Any

from horus_os._providers._stream_types import _StreamUsage
from horus_os.types import AgentResult, Tool, ToolCallEvent, ToolResult, ToolUse

# Loopback default per LP-4: never the literal "0.0.0.0", which would
# expose the local model API to the LAN.
DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_MODEL = ""
DEFAULT_MAX_TOKENS = 1024
# Most local servers ignore the API key but the SDK requires a non-empty
# string. This placeholder lets a local turn run with no cloud key set.
_PLACEHOLDER_API_KEY = "horus-local"


def _read_base_url(base_url: str | None = None) -> str:
    """Resolve the base_url: env var, then passed value, then loopback default."""
    return os.environ.get("HORUS_OS_LOCAL_BASE_URL") or base_url or DEFAULT_BASE_URL


def _read_api_key() -> str:
    """Resolve the api_key: env var, then the local placeholder fallback."""
    return os.environ.get("HORUS_OS_LOCAL_API_KEY") or _PLACEHOLDER_API_KEY


def _tools_to_openai(tools: list[Tool] | None) -> list[dict[str, Any]] | None:
    if not tools:
        return None
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }
        for tool in tools
    ]


def _parse_tool_call(call: Any) -> ToolUse:
    """Map one OpenAI tool_call entry into a ToolUse.

    `function.arguments` is a JSON string in the OpenAI contract, but some
    local servers hand back an already-parsed dict; both are accepted
    without double-parsing.
    """
    function = getattr(call, "function", None)
    raw_args = getattr(function, "arguments", None)
    if isinstance(raw_args, dict):
        parsed = raw_args
    elif raw_args:
        try:
            parsed = json.loads(raw_args)
        except (TypeError, ValueError):
            parsed = {}
    else:
        parsed = {}
    return ToolUse(
        id=getattr(call, "id", "") or "",
        name=getattr(function, "name", "") or "",
        input=dict(parsed or {}),
    )


def _parse_openai_response(response: Any, provider: str, model: str) -> AgentResult:
    text = ""
    tool_uses: list[ToolUse] = []
    choices = getattr(response, "choices", None) or []
    if choices:
        message = getattr(choices[0], "message", None)
        if message is not None:
            text = getattr(message, "content", None) or ""
            for call in getattr(message, "tool_calls", None) or []:
                tool_uses.append(_parse_tool_call(call))
    usage_obj = getattr(response, "usage", None)
    usage: dict[str, Any] = {}
    if usage_obj is not None:
        prompt_tokens = getattr(usage_obj, "prompt_tokens", None)
        completion_tokens = getattr(usage_obj, "completion_tokens", None)
        # Map onto the Anthropic-shaped keys agent._extract_usage reads.
        if prompt_tokens is not None:
            usage["input_tokens"] = prompt_tokens
        if completion_tokens is not None:
            usage["output_tokens"] = completion_tokens
    return AgentResult(
        text=text,
        tool_uses=tool_uses,
        provider=provider,
        model=model,
        usage=usage,
    )


def call_openai_compat(
    prompt: str,
    *,
    tools: list[Tool] | None = None,
    model: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    base_url: str | None = None,
    **kwargs: Any,
) -> AgentResult:
    """Sync call against an OpenAI-compatible local endpoint.

    Reads the base_url from `HORUS_OS_LOCAL_BASE_URL` (fallback to the
    passed base_url, then the loopback default) and the api_key from
    `HORUS_OS_LOCAL_API_KEY` (fallback to the local placeholder). No
    cloud key is required.
    """
    from openai import OpenAI

    chosen_model = model or DEFAULT_MODEL
    client = OpenAI(base_url=_read_base_url(base_url), api_key=_read_api_key())
    request: dict[str, Any] = {
        "model": chosen_model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    openai_tools = _tools_to_openai(tools)
    if openai_tools is not None:
        request["tools"] = openai_tools
    request.update(kwargs)
    # LP-1: stream is omitted (SDK default, non-stream) so buffered
    # tool_calls are returned intact instead of being dropped.
    response = client.chat.completions.create(**request)
    return _parse_openai_response(response, provider="local", model=chosen_model)


async def call_openai_compat_async(
    prompt: str,
    *,
    tools: list[Tool] | None = None,
    model: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    base_url: str | None = None,
    **kwargs: Any,
) -> AgentResult:
    """Async call against an OpenAI-compatible local endpoint."""
    from openai import AsyncOpenAI

    chosen_model = model or DEFAULT_MODEL
    client = AsyncOpenAI(base_url=_read_base_url(base_url), api_key=_read_api_key())
    request: dict[str, Any] = {
        "model": chosen_model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    openai_tools = _tools_to_openai(tools)
    if openai_tools is not None:
        request["tools"] = openai_tools
    request.update(kwargs)
    # LP-1: stream omitted (SDK default) so buffered tool_calls survive.
    response = await client.chat.completions.create(**request)
    return _parse_openai_response(response, provider="local", model=chosen_model)


async def stream_openai_compat_async(
    prompt: str,
    *,
    model: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    system: str | None = None,
    base_url: str | None = None,
) -> AsyncGenerator[str | ToolCallEvent | _StreamUsage, None]:
    """Stream incremental text tokens from a local endpoint, then any tool-call events.

    Mirrors the Anthropic / Gemini streaming surface: each text delta is
    yielded as a `str`, any tool-call events seen on the stream are
    yielded as `ToolCallEvent` values after the text, then a terminal
    `_StreamUsage` sentinel carrying the token counts is yielded last.

    LP-1: this streaming surface is used only for the no-tools chat path
    driven by `run_agent_stream`. Tool dispatch never goes through here
    because the OpenAI-compatible streaming endpoint can drop tool-call
    deltas; tool turns flow through the buffered `Conversation` path.
    """
    from openai import AsyncOpenAI

    client = AsyncOpenAI(base_url=_read_base_url(base_url), api_key=_read_api_key())
    messages: list[dict[str, Any]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    request: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
        "stream": True,
        # Ask the server to include usage on the terminal chunk so the SSE
        # handler can persist non-zero token counts (PITFALLS.md Pitfall 2).
        "stream_options": {"include_usage": True},
    }
    tool_events: list[ToolCallEvent] = []
    _tool_buffers: dict[int, dict[str, Any]] = {}
    _last_usage: Any = None
    stream = await client.chat.completions.create(**request)
    async for chunk in stream:
        chunk_usage = getattr(chunk, "usage", None)
        if chunk_usage is not None:
            _last_usage = chunk_usage
        for choice in getattr(chunk, "choices", None) or []:
            delta = getattr(choice, "delta", None)
            if delta is None:
                continue
            text = getattr(delta, "content", None)
            if text:
                yield text
            # Accumulate streamed tool-call argument fragments by index so a
            # no-tools stream that nonetheless surfaces a tool_call can still
            # be observed by consumers.
            for tc in getattr(delta, "tool_calls", None) or []:
                index = getattr(tc, "index", 0) or 0
                buf = _tool_buffers.setdefault(index, {"name": "", "arguments": ""})
                function = getattr(tc, "function", None)
                name = getattr(function, "name", None)
                if name:
                    buf["name"] = name
                args = getattr(function, "arguments", None)
                if args:
                    buf["arguments"] += args
    for buf in _tool_buffers.values():
        raw_args = buf["arguments"]
        try:
            parsed = json.loads(raw_args) if raw_args else {}
        except (TypeError, ValueError):
            parsed = {}
        tool_events.append(ToolCallEvent(name=buf["name"], input=dict(parsed or {})))
    for event in tool_events:
        yield event
    usage_dict: dict[str, Any] = {}
    if _last_usage is not None:
        prompt_tokens = getattr(_last_usage, "prompt_tokens", None)
        completion_tokens = getattr(_last_usage, "completion_tokens", None)
        if prompt_tokens is not None:
            usage_dict["input_tokens"] = prompt_tokens
        if completion_tokens is not None:
            usage_dict["output_tokens"] = completion_tokens
    yield _StreamUsage(usage=usage_dict)


class Conversation:
    """Multi-turn OpenAI-compatible conversation. Holds messages in the native SDK shape."""

    def __init__(self, *, model: str | None = None, system_prompt: str | None = None) -> None:
        from openai import OpenAI

        self._client = OpenAI(base_url=_read_base_url(), api_key=_read_api_key())
        self._model = model or DEFAULT_MODEL
        self._messages: list[dict[str, Any]] = []
        self._system_prompt = system_prompt or ""
        # OpenAI requires a system message in the messages list (unlike
        # Anthropic's top-level `system`), so insert it once up front.
        if self._system_prompt:
            self._messages.append({"role": "system", "content": self._system_prompt})
        # The assistant message (with its tool_calls) that produced the
        # tool_uses we are about to answer. Threaded back so the follow-up
        # turn references the same tool_call_id values.
        self._last_assistant_message: dict[str, Any] | None = None

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
            # Append the assistant message carrying the tool_calls, then one
            # tool message per result keyed by tool_call_id, matching the
            # OpenAI chat-completions multi-turn tool shape.
            if self._last_assistant_message is not None:
                self._messages.append(self._last_assistant_message)
            for r in tool_results:
                self._messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": r.tool_use_id,
                        "content": r.error if r.error is not None else str(r.output),
                    }
                )

        request: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": self._messages,
        }
        openai_tools = _tools_to_openai(tools)
        if openai_tools is not None:
            request["tools"] = openai_tools
        # LP-1: stream omitted (SDK default, non-stream) so buffered
        # tool_calls are never dropped on a tool-using turn.
        response = self._client.chat.completions.create(**request)
        result = _parse_openai_response(response, provider="local", model=self._model)
        self._last_assistant_message = _assistant_message_from_result(result)
        return result


def _assistant_message_from_result(result: AgentResult) -> dict[str, Any]:
    """Rebuild the assistant message in OpenAI shape from a parsed AgentResult.

    Carries the tool_calls forward so the next turn's `tool` messages
    reference matching tool_call_id values.
    """
    message: dict[str, Any] = {"role": "assistant", "content": result.text or ""}
    if result.tool_uses:
        message["tool_calls"] = [
            {
                "id": use.id,
                "type": "function",
                "function": {
                    "name": use.name,
                    "arguments": json.dumps(use.input),
                },
            }
            for use in result.tool_uses
        ]
    return message
