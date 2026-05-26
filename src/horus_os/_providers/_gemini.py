"""Google Gemini provider for the horus-os agent runtime.

The `google.genai` SDK is imported lazily inside the call functions so
the package loads cleanly without the SDK installed.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from typing import Any

from horus_os._providers._stream_types import _StreamUsage
from horus_os.types import AgentResult, Tool, ToolCallEvent, ToolResult, ToolUse

DEFAULT_MODEL = "gemini-2.5-flash"


def _read_api_key() -> str | None:
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def _tools_to_gemini(tools: list[Tool] | None) -> list[dict[str, Any]] | None:
    """Translate `Tool` objects into the Gemini function-declaration shape.

    Returned as a list of dicts ready to be wrapped into the SDK's
    `Tool(function_declarations=...)` structure inside the call function.
    """
    if not tools:
        return None
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        }
        for tool in tools
    ]


def _parse_gemini_response(response: Any, provider: str, model: str) -> AgentResult:
    text_parts: list[str] = []
    tool_uses: list[ToolUse] = []
    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        if content is None:
            continue
        for part in getattr(content, "parts", None) or []:
            text = getattr(part, "text", None)
            if text:
                text_parts.append(text)
            function_call = getattr(part, "function_call", None)
            if function_call is not None:
                tool_uses.append(
                    ToolUse(
                        id=getattr(function_call, "id", "") or "",
                        name=getattr(function_call, "name", "") or "",
                        input=dict(getattr(function_call, "args", {}) or {}),
                    )
                )
    usage_obj = getattr(response, "usage_metadata", None)
    usage: dict[str, Any] = {}
    if usage_obj is not None:
        for key in ("prompt_token_count", "candidates_token_count", "total_token_count"):
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


def _build_config(tools: list[Tool] | None, kwargs: dict[str, Any]) -> Any:
    """Compose a `GenerateContentConfig`, returning `None` when nothing custom is set."""
    from google.genai import types as genai_types

    gemini_tools = _tools_to_gemini(tools)
    config_kwargs: dict[str, Any] = {}
    if gemini_tools is not None:
        config_kwargs["tools"] = [genai_types.Tool(function_declarations=gemini_tools)]
    for key in ("temperature", "max_output_tokens", "top_p", "top_k", "system_instruction"):
        if key in kwargs:
            config_kwargs[key] = kwargs.pop(key)
    if not config_kwargs:
        return None
    return genai_types.GenerateContentConfig(**config_kwargs)


def call_gemini(
    prompt: str,
    *,
    tools: list[Tool] | None = None,
    model: str | None = None,
    **kwargs: Any,
) -> AgentResult:
    """Sync Gemini call. Reads `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) from the environment."""
    from google import genai

    chosen_model = model or DEFAULT_MODEL
    api_key = _read_api_key()
    client = genai.Client(api_key=api_key) if api_key else genai.Client()
    config = _build_config(tools, kwargs)
    request: dict[str, Any] = {"model": chosen_model, "contents": prompt}
    if config is not None:
        request["config"] = config
    request.update(kwargs)
    response = client.models.generate_content(**request)
    return _parse_gemini_response(response, provider="gemini", model=chosen_model)


async def call_gemini_async(
    prompt: str,
    *,
    tools: list[Tool] | None = None,
    model: str | None = None,
    **kwargs: Any,
) -> AgentResult:
    """Async Gemini call. Reads `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) from the environment."""
    from google import genai

    chosen_model = model or DEFAULT_MODEL
    api_key = _read_api_key()
    client = genai.Client(api_key=api_key) if api_key else genai.Client()
    config = _build_config(tools, kwargs)
    request: dict[str, Any] = {"model": chosen_model, "contents": prompt}
    if config is not None:
        request["config"] = config
    request.update(kwargs)
    response = await client.aio.models.generate_content(**request)
    return _parse_gemini_response(response, provider="gemini", model=chosen_model)


async def stream_gemini_async(
    prompt: str,
    *,
    model: str,
    system: str | None = None,
) -> AsyncGenerator[str | ToolCallEvent | _StreamUsage, None]:
    """Stream incremental text tokens from Gemini, then any tool-call events.

    Yields each non-empty `chunk.text` as a `str`. Function-call parts seen
    during iteration are buffered and yielded as `ToolCallEvent` values after
    the text stream completes, matching the Anthropic streaming surface. This
    function does not execute tools, by design.

    Phase 33: after the tool_call events, yields a terminal
    `_StreamUsage` sentinel carrying the final chunk's `usage_metadata`
    so the SSE handler can persist non-zero token counts (PITFALLS.md
    Pitfall 2). Gemini surfaces usage on the final chunk; we track the
    last-seen value and forward it.
    """
    from google import genai

    api_key = _read_api_key()
    client = genai.Client(api_key=api_key) if api_key else genai.Client()
    request: dict[str, Any] = {"model": model, "contents": prompt}
    if system:
        from google.genai import types as genai_types

        request["config"] = genai_types.GenerateContentConfig(system_instruction=system)
    tool_events: list[ToolCallEvent] = []
    _last_usage: Any = None
    async for chunk in client.aio.models.generate_content_stream(**request):
        if chunk.text:
            yield chunk.text
        # Gemini surfaces usage_metadata on the final chunk; track the
        # most recent non-None value so the terminal sentinel reflects
        # the canonical totals.
        chunk_usage = getattr(chunk, "usage_metadata", None)
        if chunk_usage is not None:
            _last_usage = chunk_usage
        for candidate in getattr(chunk, "candidates", None) or []:
            content = getattr(candidate, "content", None)
            for part in getattr(content, "parts", None) or []:
                fc = getattr(part, "function_call", None)
                if fc is not None:
                    tool_events.append(
                        ToolCallEvent(
                            name=getattr(fc, "name", "") or "",
                            input=dict(getattr(fc, "args", {}) or {}),
                        )
                    )
    for event in tool_events:
        yield event
    # Phase 33 terminal sentinel. Empty dict signals usage_metadata was
    # not present on any chunk; the SSE consumer falls back to a
    # char-count estimate so non-empty streams never persist zero.
    usage_dict: dict[str, Any] = {}
    if _last_usage is not None:
        for key in ("prompt_token_count", "candidates_token_count"):
            value = getattr(_last_usage, key, None)
            if value is not None:
                usage_dict[key] = value
    yield _StreamUsage(usage=usage_dict)


class Conversation:
    """Multi-turn Gemini conversation. Holds contents in the native SDK shape."""

    def __init__(self, *, model: str | None = None, system_prompt: str | None = None) -> None:
        from google import genai

        api_key = _read_api_key()
        self._client = genai.Client(api_key=api_key) if api_key else genai.Client()
        self._model = model or DEFAULT_MODEL
        self._contents: list[Any] = []
        self._last_model_content: Any = None
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
        **kwargs: Any,
    ) -> AgentResult:
        from google.genai import types as genai_types

        if prompt is None and tool_results is None:
            raise ValueError("Conversation.send requires either prompt or tool_results")
        if prompt is not None and tool_results is not None:
            raise ValueError("Conversation.send accepts prompt or tool_results, not both")

        if prompt is not None:
            self._contents.append(
                genai_types.Content(role="user", parts=[genai_types.Part(text=prompt)])
            )
        else:
            assert tool_results is not None
            if self._last_model_content is not None:
                self._contents.append(self._last_model_content)
            parts: list[Any] = []
            for r in tool_results:
                payload = {"content": str(r.output)} if r.error is None else {"error": r.error}
                parts.append(
                    genai_types.Part(
                        function_response=genai_types.FunctionResponse(
                            name=r.name, response=payload
                        )
                    )
                )
            self._contents.append(genai_types.Content(role="user", parts=parts))

        # Gemini's GenerateContentConfig accepts system_instruction. We pass
        # it on every send() so the system prompt is applied to every turn,
        # not only the first prompt. _build_config consumes it from kwargs.
        if self._system_prompt and "system_instruction" not in kwargs:
            kwargs["system_instruction"] = self._system_prompt
        config = _build_config(tools, kwargs)
        request: dict[str, Any] = {"model": self._model, "contents": self._contents}
        if config is not None:
            request["config"] = config
        response = self._client.models.generate_content(**request)
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            self._last_model_content = candidates[0].content
        return _parse_gemini_response(response, provider="gemini", model=self._model)
