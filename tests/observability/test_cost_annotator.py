"""Phase 34 Task 3 tests: CostAnnotator subscriber with cache-aware math.

Mutates LLMCallEvent in place. NULL on unknown models (never 0; Pitfall 5).
Cache-aware computation per the four-rate Anthropic / Gemini shape.
"""

from __future__ import annotations

import pytest

from horus_os.observability import CostAnnotator, PricingTable
from horus_os.observability.bus import LLMCallEvent, RunEndEvent, ToolCallEvent


def _annotator() -> CostAnnotator:
    return CostAnnotator(PricingTable())


def test_non_llm_event_ignored() -> None:
    ann = _annotator()
    tool_evt = ToolCallEvent(
        trace_id="t1",
        tool_name="noop",
        latency_ms=10,
        status="success",
    )
    run_evt = RunEndEvent(trace_id="t1", latency_ms=10)
    # Should not raise. Should not add any attributes.
    ann.on_event(tool_evt)
    ann.on_event(run_evt)
    assert not hasattr(tool_evt, "cost_usd")
    assert not hasattr(run_evt, "cost_usd")


def test_known_model_computes_cache_aware_cost() -> None:
    ann = _annotator()
    evt = LLMCallEvent(
        trace_id="t1",
        iteration_idx=0,
        provider="anthropic",
        model="claude-sonnet-4-6",
        input_tokens=1000,
        output_tokens=200,
        cache_read_input_tokens=500,
        cache_creation_input_tokens=0,
    )
    ann.on_event(evt)
    # 1000*3.00 + 200*15.00 + 500*0.30 + 0*3.75 = 3000+3000+150+0 = 6150
    # 6150 / 1_000_000 = 0.00615 -> 6dp = 0.006150
    assert evt.cost_usd == pytest.approx(0.006150, abs=1e-9)
    assert evt.pricing_missing is False


def test_unknown_model_sets_null_cost() -> None:
    ann = _annotator()
    evt = LLMCallEvent(
        trace_id="t1",
        iteration_idx=0,
        provider="anthropic",
        model="never-released-3000-pro",
        input_tokens=1000,
        output_tokens=200,
    )
    ann.on_event(evt)
    # Pitfall 5: literal None, never 0 or 0.0.
    assert evt.cost_usd is None
    assert evt.pricing_missing is True


def test_unknown_model_explicitly_not_zero() -> None:
    """Belt-and-braces Pitfall 5: cost_usd must be None, never 0 or 0.0."""
    ann = _annotator()
    evt = LLMCallEvent(
        trace_id="t1",
        iteration_idx=0,
        provider="google",
        model="missing-from-table",
        input_tokens=42,
        output_tokens=42,
    )
    ann.on_event(evt)
    assert evt.cost_usd is None
    # The next two are redundant with the `is None` check, but they
    # encode the intent so a future refactor that returns 0.0 fails
    # loudly here instead of silently mispricing.
    assert evt.cost_usd != 0
    assert evt.cost_usd != 0.0
    assert evt.pricing_missing is True


def test_cache_creation_tokens_included() -> None:
    """Cache-write rate is distinct from cache-read; both must be billed."""
    ann = _annotator()
    evt = LLMCallEvent(
        trace_id="t1",
        iteration_idx=0,
        provider="anthropic",
        model="claude-sonnet-4-6",
        input_tokens=0,
        output_tokens=0,
        cache_creation_input_tokens=1000,
        cache_read_input_tokens=0,
    )
    ann.on_event(evt)
    # 1000 * 3.75 / 1_000_000 = 0.00375
    assert evt.cost_usd == pytest.approx(0.00375, abs=1e-9)
    assert evt.pricing_missing is False


def test_rounding_to_6_decimals() -> None:
    """Pick inputs that produce a long-decimal raw cost; assert 6dp round."""
    ann = _annotator()
    # 1 input token at $0.30/M raw = 0.0000003 (raw 7-decimal value).
    # round(0.0000003, 6) = 0 (Python rounds half-to-even and the value
    # is below 5e-7), but check the rounding is applied at 6dp not 9dp.
    # Use 333 input tokens at $3/M to land at raw = 333*3/1e6 = 0.000999
    # which is exact at 6dp. To force a rounding effect, use 333 cache
    # reads on Gemini Flash at $0.075/M:
    #   raw = 333 * 0.075 / 1e6 = 24.975e-6 = 0.000024975 -> round 6dp
    #   = 0.000025
    evt = LLMCallEvent(
        trace_id="t1",
        iteration_idx=0,
        provider="google",
        model="gemini-2.5-flash",
        input_tokens=0,
        output_tokens=0,
        cache_read_input_tokens=333,
    )
    ann.on_event(evt)
    assert evt.cost_usd == pytest.approx(0.000025, abs=1e-9)
    assert evt.pricing_missing is False


def test_known_model_clears_pricing_missing() -> None:
    """Re-annotating an event that was previously flagged must clear the flag."""
    ann = _annotator()
    evt = LLMCallEvent(
        trace_id="t1",
        iteration_idx=0,
        provider="anthropic",
        model="claude-sonnet-4-6",
        input_tokens=100,
        output_tokens=100,
        pricing_missing=True,
    )
    ann.on_event(evt)
    assert evt.pricing_missing is False
    assert evt.cost_usd is not None
