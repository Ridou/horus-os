"""Top-level agent runtime entry points.

`run_agent` and `run_agent_async` dispatch one turn to the correct
provider module.

`run_agent_loop` orchestrates the multi-turn tool-use loop. There is
no abstraction layer above the provider SDKs; each provider exposes a
`Conversation` class with native message history, and this module's
only job is provider selection and uniform return shape.

Phase 33 adds observability capture: every `Conversation.send` inside
`run_agent_loop` publishes an `LLMCallEvent` to the process-wide
`ObservationBus`. The caller (server/api.py:chat) owns RunEndEvent
publication so the rollup UPDATE matches a traces row that
`db.record_trace` has already written.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncGenerator, Callable
from typing import Any

from horus_os._providers import _anthropic, _gemini
from horus_os._providers._stream_types import _StreamUsage
from horus_os.observability import get_observation_bus
from horus_os.observability.bus import LLMCallEvent
from horus_os.tools.delegation import IterationBudget
from horus_os.tools.loop import execute_tool_uses
from horus_os.tools.registry import ToolRegistry

# `ToolCallEvent` here is `horus_os.types.ToolCallEvent`, the streaming-surface
# event yielded by `run_agent_stream`. It is intentionally distinct from
# `horus_os.observability.bus.ToolCallEvent`, which is the persisted
# observability event. Both names exist for different concerns; do not
# replace this import without rewriting `run_agent_stream`.
from horus_os.types import AgentResult, Tool, ToolCallEvent, ToolResult

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


async def run_agent_stream(
    prompt: str,
    *,
    provider: str = "anthropic",
    model: str | None = None,
    max_tokens: int = 1024,
    system: str | None = None,
) -> AsyncGenerator[str | ToolCallEvent | _StreamUsage, None]:
    """Stream incremental tokens from one provider turn.

    Yields each text delta as a `str` as the model produces it, then any
    `ToolCallEvent` values observed in the final assembled response. This
    is a purely additive surface: existing `run_agent`, `run_agent_async`,
    and `run_agent_loop` are unchanged.

    Tool execution is intentionally not handled here. Streaming and tool
    dispatch do not compose in a single pass; callers that need tools
    must use `run_agent_loop`. `ToolCallEvent` is surfaced so consumers
    (CLI, dashboard) can observe a mid-flight tool request, not act on it.

    `_check_provider` runs when the generator body executes, which happens
    on the first `__anext__` call. Iteration is what triggers the
    `ValueError` for unknown providers.
    """
    _check_provider(provider)
    if provider == "anthropic":
        async for chunk in _anthropic.stream_anthropic_async(
            prompt,
            model=model or _anthropic.DEFAULT_MODEL,
            max_tokens=max_tokens,
            system=system,
        ):
            yield chunk
    else:
        async for chunk in _gemini.stream_gemini_async(
            prompt,
            model=model or _gemini.DEFAULT_MODEL,
            system=system,
        ):
            yield chunk


def _extract_usage(provider: str, usage: dict[str, Any]) -> tuple[int, int, int, int]:
    """Normalize per-provider usage dicts into the LLMCallEvent shape.

    Returns (input_tokens, output_tokens, cache_creation_input_tokens,
    cache_read_input_tokens). Anthropic surfaces all four keys directly;
    Gemini exposes only two and has no cache_* concept, so the cache
    fields are zero. Both providers return integers from the SDK, never
    floats; the call sites never see negative values.
    """
    if provider == "gemini":
        return (
            int(usage.get("prompt_token_count", 0) or 0),
            int(usage.get("candidates_token_count", 0) or 0),
            0,
            0,
        )
    # anthropic and any future provider that uses the Anthropic-shaped keys
    return (
        int(usage.get("input_tokens", 0) or 0),
        int(usage.get("output_tokens", 0) or 0),
        int(usage.get("cache_creation_input_tokens", 0) or 0),
        int(usage.get("cache_read_input_tokens", 0) or 0),
    )


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
    trace_id: str | None = None,
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

    `trace_id` (Phase 33) is the observability scope id used for the
    LLMCallEvents this loop publishes. When None, a fresh uuid4 hex is
    generated so legacy callers still get a trace_id-attached run. The
    caller that pre-generates the trace_id (server/api.py:chat) MUST
    pass the same value to `db.record_trace` and `RunEndEvent` so the
    persister's rollup UPDATE matches the row record_trace inserted.
    """
    _check_provider(provider)
    if budget is None and max_iterations < 1:
        raise ValueError("max_iterations must be >= 1")
    _budget = budget if budget is not None else IterationBudget(max_iterations)
    _trace_id = trace_id if trace_id is not None else uuid.uuid4().hex
    _bus = get_observation_bus()
    _model_str = model or ""
    conversation = _new_conversation(provider, model, system_prompt=system_prompt)
    tools = registry.list()

    def _publish_send(iteration_idx: int, send_args: dict[str, Any]) -> AgentResult:
        """Run one conversation.send call wrapped in observability capture.

        On success: publish a status="success" LLMCallEvent with usage
        extracted via _extract_usage. On exception: publish a
        status="error" event with zero tokens and the exception class
        name, then re-raise (observability never swallows the underlying
        error).
        """
        _t0 = time.perf_counter()
        try:
            _result = conversation.send(**send_args)
        except BaseException as exc:
            _latency_ms = int((time.perf_counter() - _t0) * 1000)
            _bus.publish(
                LLMCallEvent(
                    trace_id=_trace_id,
                    iteration_idx=iteration_idx,
                    provider=provider,
                    model=_model_str,
                    input_tokens=0,
                    output_tokens=0,
                    latency_ms=max(0, _latency_ms),
                    status="error",
                    error_type=type(exc).__name__,
                    error_message=type(exc).__name__,
                )
            )
            raise
        _latency_ms = int((time.perf_counter() - _t0) * 1000)
        _in, _out, _cc, _cr = _extract_usage(provider, _result.usage or {})
        # Pin the per-event model to the conversation's resolved model so
        # caller-omitted `model=None` still ends up with the provider's
        # default (matches conversation.model property contract).
        _resolved_model = getattr(conversation, "model", None) or _model_str
        _bus.publish(
            LLMCallEvent(
                trace_id=_trace_id,
                iteration_idx=iteration_idx,
                provider=provider,
                model=_resolved_model,
                input_tokens=_in,
                output_tokens=_out,
                cache_creation_input_tokens=_cc,
                cache_read_input_tokens=_cr,
                latency_ms=max(0, _latency_ms),
                status="success",
            )
        )
        return _result

    iteration_idx = 0
    result = _publish_send(iteration_idx, {"prompt": prompt, "tools": tools})
    while result.tool_uses:
        if not _budget.consume():
            break
        # Thread trace_id into execute_tool_uses so per-tool
        # ObsToolCallEvents share the run's trace_id (Phase 33 Task 3).
        outcomes = execute_tool_uses(registry, result, on_log=on_tool_result, trace_id=_trace_id)
        iteration_idx += 1
        result = _publish_send(iteration_idx, {"tool_results": outcomes, "tools": tools})
    # RunEndEvent is published by the caller (server/api.py:chat) AFTER
    # db.record_trace, so the persister rollup UPDATE matches an existing
    # traces row. See Phase 33 Task 4.
    return result
