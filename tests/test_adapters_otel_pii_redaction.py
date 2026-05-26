"""TEST-13 PII-not-leaked test (Phase 38, Pitfall 7).

The two load-bearing assertions:

1. Default mode: an LLMCallEvent with `error_message` containing the
   literal `AKIAIOSFODNN7EXAMPLE` (the canonical AWS access key test
   fixture per Pitfall 7) produces a span where the literal substring
   does NOT appear in ANY attribute key or value.

2. Opt-in mode (`HORUS_OS_OTEL_CAPTURE_CONTENT=true`): the body
   attribute IS set, but the redactor strips the AWS key first; the
   literal substring STILL does NOT appear in any attribute.

Belt-and-braces: per-pattern opt-in assertions for sk-*, ghp_*, xoxb-*,
emails, and e164 phones. Plus a structural test that the body-attach
line lives INSIDE the `os.environ.get(CAPTURE_CONTENT_ENV) == "true"`
gate, NOT outside (defence against a future PR hoisting it).
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
    GEN_AI_USAGE_INPUT_TOKENS,
    HORUS_OS_COST_USD,
)
from horus_os.adapters.base import AdapterContext, AdapterRegistry
from horus_os.adapters.otel_adapter import (
    CAPTURE_CONTENT_ENV,
    OTLP_ENDPOINT_ENV,
    OtelAdapter,
)
from horus_os.config import Config
from horus_os.observability import (
    LLMCallEvent,
    get_observation_bus,
    reset_observation_bus_for_tests,
)

_CLOSED_PORT_ENDPOINT = "http://127.0.0.1:1"
_AWS_KEY_LITERAL = "AKIAIOSFODNN7EXAMPLE"


def _make_context(tmp_path: Path) -> AdapterContext:
    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    reg = AdapterRegistry()
    reg.register("otel")
    return AdapterContext(config=cfg, data_dir=tmp_path, registry=reg)


def _start_adapter_with_in_memory_exporter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[OtelAdapter, InMemorySpanExporter]:
    monkeypatch.setenv(OTLP_ENDPOINT_ENV, _CLOSED_PORT_ENDPOINT)
    reset_observation_bus_for_tests()
    ctx = _make_context(tmp_path)
    adapter = OtelAdapter()
    asyncio.run(adapter.start(ctx))
    assert adapter._provider is not None
    exporter = InMemorySpanExporter()
    adapter._provider.add_span_processor(SimpleSpanProcessor(exporter))
    return adapter, exporter


def _publish_error_event_with_message(message: str) -> None:
    get_observation_bus().publish(
        LLMCallEvent(
            trace_id="t-pii",
            iteration_idx=0,
            provider="anthropic",
            model="claude-sonnet-4-6",
            input_tokens=100,
            output_tokens=20,
            cost_usd=0.001,
            latency_ms=5,
            status="error",
            error_type="ValueError",
            error_message=message,
        )
    )


def _assert_literal_absent_everywhere(span, literal: str) -> None:
    """Defence-in-depth: the literal must not appear in keys OR values."""
    for key, value in span.attributes.items():
        assert literal not in key, f"literal leaked into attr key: {key}"
        assert literal not in str(value), f"literal leaked into attr value for key {key}: {value!r}"


def test_default_mode_strips_aws_key_literal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """THE LOAD-BEARING TEST-13 ASSERTION (default mode)."""
    monkeypatch.delenv(CAPTURE_CONTENT_ENV, raising=False)
    adapter, exporter = _start_adapter_with_in_memory_exporter(monkeypatch, tmp_path)
    try:
        _publish_error_event_with_message(
            f"user prompt was: my AWS key is {_AWS_KEY_LITERAL} rotate today"
        )
        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        span = spans[0]
        # (a) Numerical attrs still emit (the cost+token signal is the
        # whole point of the OTel adapter).
        assert GEN_AI_USAGE_INPUT_TOKENS in span.attributes
        assert HORUS_OS_COST_USD in span.attributes
        # (b) AWS key literal absent from every key AND value.
        _assert_literal_absent_everywhere(span, _AWS_KEY_LITERAL)
        # (c-f) None of the deprecated body-capture attribute keys
        # are present in default mode.
        attr_keys = set(span.attributes.keys())
        assert "gen_ai.output.messages" not in attr_keys
        assert "gen_ai.input.messages" not in attr_keys
        assert "gen_ai.prompt" not in attr_keys
        assert "gen_ai.completion" not in attr_keys
    finally:
        asyncio.run(adapter.stop())


def test_opt_in_mode_still_redacts_aws_key_literal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """THE SECOND LOAD-BEARING TEST-13 ASSERTION (opt-in mode)."""
    monkeypatch.setenv(CAPTURE_CONTENT_ENV, "true")
    adapter, exporter = _start_adapter_with_in_memory_exporter(monkeypatch, tmp_path)
    try:
        _publish_error_event_with_message(
            f"user prompt was: my AWS key is {_AWS_KEY_LITERAL} rotate today"
        )
        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        span = spans[0]
        # (a) Opt-in mode DID attach a body attribute.
        assert "gen_ai.output.messages" in span.attributes
        body = str(span.attributes["gen_ai.output.messages"])
        # (b) Body contains the redacted placeholder.
        assert "[REDACTED]" in body
        # (c) Body STILL does NOT contain the literal AWS key.
        assert _AWS_KEY_LITERAL not in body
        _assert_literal_absent_everywhere(span, _AWS_KEY_LITERAL)
        # (d) Surrounding context is preserved (surgical replacement).
        assert "user prompt was:" in body
        assert "rotate today" in body
    finally:
        asyncio.run(adapter.stop())


def test_opt_in_mode_redacts_sk_anthropic_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(CAPTURE_CONTENT_ENV, "true")
    adapter, exporter = _start_adapter_with_in_memory_exporter(monkeypatch, tmp_path)
    try:
        fake = "sk-ant-api03-" + "a" * 40
        _publish_error_event_with_message(f"please rotate {fake} when done")
        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        body = str(spans[0].attributes["gen_ai.output.messages"])
        assert fake not in body
        assert "[REDACTED]" in body
    finally:
        asyncio.run(adapter.stop())


def test_opt_in_mode_redacts_github_pat(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(CAPTURE_CONTENT_ENV, "true")
    adapter, exporter = _start_adapter_with_in_memory_exporter(monkeypatch, tmp_path)
    try:
        fake = "ghp_" + "c" * 36
        _publish_error_event_with_message(f"committed {fake} by accident")
        spans = exporter.get_finished_spans()
        body = str(spans[0].attributes["gen_ai.output.messages"])
        assert fake not in body
        assert "[REDACTED]" in body
    finally:
        asyncio.run(adapter.stop())


def test_opt_in_mode_redacts_slack_bot_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(CAPTURE_CONTENT_ENV, "true")
    adapter, exporter = _start_adapter_with_in_memory_exporter(monkeypatch, tmp_path)
    try:
        fake = "xoxb-fake-slack-token-body"
        _publish_error_event_with_message(f"bot token {fake} leaked")
        spans = exporter.get_finished_spans()
        body = str(spans[0].attributes["gen_ai.output.messages"])
        assert fake not in body
        assert "[REDACTED]" in body
    finally:
        asyncio.run(adapter.stop())


def test_opt_in_mode_redacts_email_address(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(CAPTURE_CONTENT_ENV, "true")
    adapter, exporter = _start_adapter_with_in_memory_exporter(monkeypatch, tmp_path)
    try:
        _publish_error_event_with_message("contact user@example.com please")
        spans = exporter.get_finished_spans()
        body = str(spans[0].attributes["gen_ai.output.messages"])
        assert "user@example.com" not in body
        assert "[REDACTED]" in body
    finally:
        asyncio.run(adapter.stop())


def test_opt_in_mode_redacts_e164_phone_number(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(CAPTURE_CONTENT_ENV, "true")
    adapter, exporter = _start_adapter_with_in_memory_exporter(monkeypatch, tmp_path)
    try:
        _publish_error_event_with_message("call +18582260766 today")
        spans = exporter.get_finished_spans()
        body = str(spans[0].attributes["gen_ai.output.messages"])
        assert "+18582260766" not in body
        assert "[REDACTED]" in body
    finally:
        asyncio.run(adapter.stop())


@pytest.mark.parametrize("flag_value", ["false", "1", "yes", "TRUE", "True", "0", ""])
def test_capture_content_env_value_other_than_true_stays_default_deny(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, flag_value: str
) -> None:
    """Only the EXACT lowercase string 'true' flips opt-in mode on."""
    monkeypatch.setenv(CAPTURE_CONTENT_ENV, flag_value)
    adapter, exporter = _start_adapter_with_in_memory_exporter(monkeypatch, tmp_path)
    try:
        _publish_error_event_with_message(f"my AWS key is {_AWS_KEY_LITERAL} oops")
        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        # Default-deny: no body attr; AWS literal absent everywhere.
        assert "gen_ai.output.messages" not in spans[0].attributes
        _assert_literal_absent_everywhere(spans[0], _AWS_KEY_LITERAL)
    finally:
        asyncio.run(adapter.stop())


def test_opt_in_mode_with_none_error_message_does_not_set_any_body_attr(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(CAPTURE_CONTENT_ENV, "true")
    adapter, exporter = _start_adapter_with_in_memory_exporter(monkeypatch, tmp_path)
    try:
        # status=success means error_message is None by default.
        get_observation_bus().publish(
            LLMCallEvent(
                trace_id="t-no-err",
                iteration_idx=0,
                provider="anthropic",
                model="claude-sonnet-4-6",
                input_tokens=10,
                output_tokens=5,
                latency_ms=1,
            )
        )
        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        # No body attr because there was no body to redact.
        assert "gen_ai.output.messages" not in spans[0].attributes
    finally:
        asyncio.run(adapter.stop())


_ADAPTER_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "horus_os" / "adapters" / "otel_adapter.py"
)


def test_grep_gate_no_set_attribute_with_event_content_in_default_path() -> None:
    """Structural defence: the body-attach line for gen_ai.output.messages
    MUST appear AFTER the CAPTURE_CONTENT_ENV gate line in the adapter
    source. If a future PR hoists the body-attach out of the gate, this
    structural test fails before the contract regresses.
    """
    lines = _ADAPTER_PATH.read_text().splitlines()
    gate_line_idx: int | None = None
    body_attach_line_idx: int | None = None
    for idx, line in enumerate(lines):
        if 'os.environ.get(CAPTURE_CONTENT_ENV) == "true"' in line:
            gate_line_idx = idx
        if 'set_attribute("gen_ai.output.messages"' in line:
            body_attach_line_idx = idx
    assert gate_line_idx is not None, (
        "Adapter source must contain a literal `os.environ.get(CAPTURE_CONTENT_ENV) "
        '== "true"` gate line.'
    )
    assert body_attach_line_idx is not None, (
        "Adapter source must contain exactly one "
        '`set_attribute("gen_ai.output.messages", ...)` call (the opt-in branch).'
    )
    assert body_attach_line_idx > gate_line_idx, (
        f"Body-attach line ({body_attach_line_idx}) must appear AFTER the "
        f"CAPTURE_CONTENT_ENV gate line ({gate_line_idx}); Pitfall 7 hoist-defence."
    )


def test_grep_gate_body_attach_appears_exactly_once_in_adapter_source() -> None:
    """Defence-in-depth: only ONE `set_attribute("gen_ai.output.messages", ...)`
    call should exist in the adapter source (the opt-in branch). A second
    occurrence would indicate the line was duplicated outside the gate.
    """
    source = _ADAPTER_PATH.read_text()
    assert source.count('set_attribute("gen_ai.output.messages"') == 1
