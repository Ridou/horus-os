"""Top-level agent runtime entry points.

`run_agent` and `run_agent_async` dispatch to the correct provider
module. There is no abstraction layer above the provider SDKs; this
module's only job is provider selection and a uniform return shape.
"""

from __future__ import annotations

from typing import Any

from horus_os._providers import _anthropic, _gemini
from horus_os.types import AgentResult, Tool

SUPPORTED_PROVIDERS = ("anthropic", "gemini")


def _check_provider(provider: str) -> None:
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Unknown provider {provider!r}. Supported providers: {SUPPORTED_PROVIDERS}"
        )


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
