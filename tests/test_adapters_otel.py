"""Core OtelAdapter contract tests (Phase 38, OTEL-02 / OTEL-05).

Uses OTel's `InMemorySpanExporter` so spans materialize in-process for
assertion. The test fixture mounts a synchronous span processor with
an in-memory exporter ALONGSIDE the production BatchSpanProcessor;
PITFALLS.md §Pitfall 7 line 346 explicitly allows the synchronous
variant inside dedicated unit tests of the exporter.

The deprecated body-capture attribute names
(`gen_ai.prompt` / `gen_ai.completion` / `gen_ai.input.messages` /
`gen_ai.output.messages`) are asserted ABSENT from every default-mode
span AND ABSENT from the adapter source via a grep gate. Pitfall 7
default-deny posture at both runtime and code-review layers.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

pytest.importorskip("opentelemetry")

from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from horus_os._observability.semconv import (
    ERROR_TYPE,
    GEN_AI_OPERATION_NAME,
    GEN_AI_REQUEST_MODEL,
    GEN_AI_SYSTEM,
    GEN_AI_USAGE_CACHED_TOKENS,
    GEN_AI_USAGE_INPUT_TOKENS,
    GEN_AI_USAGE_OUTPUT_TOKENS,
    HORUS_OS_COST_USD,
)
from horus_os.adapters.base import AdapterContext, AdapterRegistry
from horus_os.adapters.otel_adapter import OTLP_ENDPOINT_ENV, OtelAdapter
from horus_os.config import Config
from horus_os.observability import (
    LLMCallEvent,
    RunEndEvent,
    ToolCallEvent,
    get_observation_bus,
    reset_observation_bus_for_tests,
)

_CLOSED_PORT_ENDPOINT = "http://127.0.0.1:1"


def _make_context(tmp_path: Path) -> AdapterContext:
    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    reg = AdapterRegistry()
    reg.register("otel")
    return AdapterContext(config=cfg, data_dir=tmp_path, registry=reg)


def _start_adapter_with_in_memory_exporter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[OtelAdapter, InMemorySpanExporter, AdapterContext]:
    """Bring up the adapter and attach an in-memory exporter for assertions."""
    monkeypatch.setenv(OTLP_ENDPOINT_ENV, _CLOSED_PORT_ENDPOINT)
    reset_observation_bus_for_tests()
    ctx = _make_context(tmp_path)
    adapter = OtelAdapter()
    asyncio.run(adapter.start(ctx))
    assert adapter._provider is not None, "start did not mount a TracerProvider"
    exporter = InMemorySpanExporter()
    # SimpleSpanProcessor is allowed in test fixtures (Pitfall 7 line 346
    # acceptable exception); it runs ALONGSIDE the production
    # BatchSpanProcessor so the in-memory queue fills synchronously
    # while the BSP keeps its bounded-shutdown contract intact.
    adapter._provider.add_span_processor(SimpleSpanProcessor(exporter))
    return adapter, exporter, ctx


def _publish_anthropic_success_event() -> None:
    get_observation_bus().publish(
        LLMCallEvent(
            trace_id="t1",
            iteration_idx=0,
            provider="anthropic",
            model="claude-sonnet-4-6",
            input_tokens=1000,
            output_tokens=200,
            cache_read_input_tokens=500,
            cost_usd=0.006150,
            latency_ms=12,
            status="success",
        )
    )


def test_default_span_attributes_match_canonical_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """THE LOAD-BEARING OTEL-05 TEST.

    Exported span attributes are EXACTLY the 7 canonical keys for a
    success case (no error.type). All 8 keys appear only on failure
    events (test below).
    """
    adapter, exporter, _ctx = _start_adapter_with_in_memory_exporter(monkeypatch, tmp_path)
    try:
        _publish_anthropic_success_event()
        spans = exporter.get_finished_spans()
        assert len(spans) == 1, f"expected 1 span, got {len(spans)}"
        span = spans[0]
        attr_keys = set(span.attributes.keys())
        assert attr_keys == {
            GEN_AI_SYSTEM,
            GEN_AI_OPERATION_NAME,
            GEN_AI_REQUEST_MODEL,
            GEN_AI_USAGE_INPUT_TOKENS,
            GEN_AI_USAGE_OUTPUT_TOKENS,
            GEN_AI_USAGE_CACHED_TOKENS,
            HORUS_OS_COST_USD,
        }
        assert span.attributes[GEN_AI_SYSTEM] == "anthropic"
        assert span.attributes[GEN_AI_OPERATION_NAME] == "chat"
        assert span.attributes[GEN_AI_REQUEST_MODEL] == "claude-sonnet-4-6"
        assert span.attributes[GEN_AI_USAGE_INPUT_TOKENS] == 1000
        assert span.attributes[GEN_AI_USAGE_OUTPUT_TOKENS] == 200
        assert span.attributes[GEN_AI_USAGE_CACHED_TOKENS] == 500
        assert span.attributes[HORUS_OS_COST_USD] == 0.006150
    finally:
        asyncio.run(adapter.stop())


def test_gemini_provider_normalizes_to_google_genai(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    adapter, exporter, _ctx = _start_adapter_with_in_memory_exporter(monkeypatch, tmp_path)
    try:
        get_observation_bus().publish(
            LLMCallEvent(
                trace_id="t2",
                iteration_idx=0,
                provider="gemini",
                model="gemini-2.5-flash",
                input_tokens=10,
                output_tokens=5,
                latency_ms=1,
            )
        )
        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].attributes[GEN_AI_SYSTEM] == "google_genai"
    finally:
        asyncio.run(adapter.stop())


def test_error_event_sets_error_type_attribute(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    adapter, exporter, _ctx = _start_adapter_with_in_memory_exporter(monkeypatch, tmp_path)
    try:
        get_observation_bus().publish(
            LLMCallEvent(
                trace_id="t3",
                iteration_idx=0,
                provider="anthropic",
                model="claude-sonnet-4-6",
                input_tokens=10,
                output_tokens=0,
                latency_ms=1,
                status="error",
                error_type="AuthenticationError",
                error_message="auth failed; classname only per Phase 33",
            )
        )
        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].attributes[ERROR_TYPE] == "AuthenticationError"
        # error.message is NEVER attached. Per Pitfall 7 default-deny,
        # no body content attribute is set in default mode.
        attr_keys = set(spans[0].attributes.keys())
        assert "error.message" not in attr_keys
    finally:
        asyncio.run(adapter.stop())


def test_unknown_model_with_null_cost_omits_horus_os_cost_usd_attribute(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    adapter, exporter, _ctx = _start_adapter_with_in_memory_exporter(monkeypatch, tmp_path)
    try:
        get_observation_bus().publish(
            LLMCallEvent(
                trace_id="t4",
                iteration_idx=0,
                provider="anthropic",
                model="claude-sonnet-4-99-unknown",
                input_tokens=10,
                output_tokens=5,
                cost_usd=None,
                pricing_missing=True,
                latency_ms=1,
            )
        )
        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        # Pitfall 5 contract: absence carries the meaning. NEVER set to 0.
        assert HORUS_OS_COST_USD not in spans[0].attributes
    finally:
        asyncio.run(adapter.stop())


def test_zero_cache_tokens_omits_cached_tokens_attribute(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    adapter, exporter, _ctx = _start_adapter_with_in_memory_exporter(monkeypatch, tmp_path)
    try:
        get_observation_bus().publish(
            LLMCallEvent(
                trace_id="t5",
                iteration_idx=0,
                provider="anthropic",
                model="claude-sonnet-4-6",
                input_tokens=10,
                output_tokens=5,
                cache_read_input_tokens=0,
                latency_ms=1,
            )
        )
        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert GEN_AI_USAGE_CACHED_TOKENS not in spans[0].attributes
    finally:
        asyncio.run(adapter.stop())


def test_deprecated_and_content_attrs_never_emitted_in_default_mode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """THE LOAD-BEARING OTEL-05 NEGATIVE TEST.

    Default mode: NONE of the deprecated body-capture attribute keys
    appear in any exported span, regardless of event shape.
    """
    adapter, exporter, _ctx = _start_adapter_with_in_memory_exporter(monkeypatch, tmp_path)
    try:
        _publish_anthropic_success_event()
        # Also an error event to cover the alternate branch.
        get_observation_bus().publish(
            LLMCallEvent(
                trace_id="t-err",
                iteration_idx=1,
                provider="anthropic",
                model="claude-sonnet-4-6",
                input_tokens=1,
                output_tokens=0,
                latency_ms=1,
                status="error",
                error_type="TimeoutError",
                error_message="this would be a body in opt-in mode",
            )
        )
        spans = exporter.get_finished_spans()
        forbidden = {
            "gen_ai.prompt",
            "gen_ai.completion",
            "gen_ai.input.messages",
            "gen_ai.output.messages",
        }
        for span in spans:
            attr_keys = set(span.attributes.keys())
            overlap = attr_keys & forbidden
            assert overlap == set(), f"span {span.name} has forbidden default-mode keys: {overlap}"
    finally:
        asyncio.run(adapter.stop())


_ADAPTER_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "horus_os" / "adapters" / "otel_adapter.py"
)


def test_grep_gate_no_deprecated_attribute_literals_in_adapter_source() -> None:
    """Code-level defence: the deprecated body-capture literal names
    appear AT MOST once in the adapter source (the single opt-in
    body-attach line in Task 5 will use "gen_ai.output.messages").
    For the post-Task-4 state with no opt-in path yet, the count is 0
    for all four; for the post-Task-5 state, "gen_ai.output.messages"
    is 1 (inside the opt-in gate) and the other three remain 0.
    """
    source = _ADAPTER_PATH.read_text()
    assert source.count("gen_ai.prompt") == 0
    assert source.count("gen_ai.completion") == 0
    assert source.count("gen_ai.input.messages") == 0
    # "gen_ai.output.messages" allowed at most once (Task 5 opt-in line).
    assert source.count("gen_ai.output.messages") <= 1


def test_subscription_unwires_on_stop(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Publish, stop, publish again. Exporter sees exactly 1 span."""
    adapter, exporter, _ctx = _start_adapter_with_in_memory_exporter(monkeypatch, tmp_path)
    _publish_anthropic_success_event()
    assert len(exporter.get_finished_spans()) == 1
    asyncio.run(adapter.stop())
    # Now publish AGAIN; the subscription is gone so no new span.
    _publish_anthropic_success_event()
    # The exporter is bound to the provider that stop() drained; even
    # if a future bug re-subscribed, the post-stop provider would be
    # None. Either way the count stays at 1.
    assert len(exporter.get_finished_spans()) == 1


def test_run_end_event_does_not_emit_span(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    adapter, exporter, _ctx = _start_adapter_with_in_memory_exporter(monkeypatch, tmp_path)
    try:
        get_observation_bus().publish(RunEndEvent(trace_id="r1", latency_ms=10))
        spans = exporter.get_finished_spans()
        assert len(spans) == 0
    finally:
        asyncio.run(adapter.stop())


def test_tool_call_event_does_not_emit_span(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    adapter, exporter, _ctx = _start_adapter_with_in_memory_exporter(monkeypatch, tmp_path)
    try:
        get_observation_bus().publish(
            ToolCallEvent(
                trace_id="tc1",
                tool_name="echo",
                latency_ms=1,
                status="success",
            )
        )
        spans = exporter.get_finished_spans()
        assert len(spans) == 0
    finally:
        asyncio.run(adapter.stop())


def test_span_name_follows_chat_model_convention(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    adapter, exporter, _ctx = _start_adapter_with_in_memory_exporter(monkeypatch, tmp_path)
    try:
        _publish_anthropic_success_event()
        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "chat claude-sonnet-4-6"
    finally:
        asyncio.run(adapter.stop())


def test_registry_touch_on_span_emission(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A successful emission bumps last_activity_at on the registry."""
    adapter, _exporter, ctx = _start_adapter_with_in_memory_exporter(monkeypatch, tmp_path)
    try:
        entry_before = ctx.registry.get("otel")
        assert entry_before is not None
        before = entry_before.last_activity_at
        _publish_anthropic_success_event()
        entry_after = ctx.registry.get("otel")
        assert entry_after is not None
        after = entry_after.last_activity_at
        assert after is not None and after != before
    finally:
        asyncio.run(adapter.stop())
