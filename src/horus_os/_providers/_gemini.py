"""Google Gemini provider for the horus-os agent runtime.

The `google.genai` SDK is imported lazily inside the call functions so
the package loads cleanly without the SDK installed.
"""

from __future__ import annotations

import os
from typing import Any

from horus_os.types import AgentResult, Tool, ToolUse

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
