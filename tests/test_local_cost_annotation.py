"""LLM-04 / PITFALLS LP-2 regression: local-provider runs are free, not NULL.

A provider == "local" LLMCallEvent must annotate to cost_usd == 0.0 (a real
float zero, distinguished from NULL) and pricing_missing == False, without
raising, regardless of token counts or whether the local model name is in the
bundled pricing table. This proves the local branch keeps an unrecognized
local model out of the Pitfall 5 None path so the dashboard renders
"local (free)" rather than "pricing unknown".

The control cases pin that the cloud pricing paths are unchanged: an unknown
cloud model still annotates to cost_usd is None + pricing_missing True
(Pitfall 5), and a known cloud model still computes a positive cost.
"""

from __future__ import annotations

from horus_os.observability import CostAnnotator, PricingTable
from horus_os.observability.bus import LLMCallEvent


def _annotator() -> CostAnnotator:
    return CostAnnotator(PricingTable())


def test_local_provider_annotates_real_zero_without_raising() -> None:
    """LP-2: local run -> cost_usd == 0.0 (real zero), pricing_missing False."""
    ann = _annotator()
    evt = LLMCallEvent(
        trace_id="t1",
        iteration_idx=0,
        provider="local",
        model="llama3.1:8b",
        input_tokens=1000,
        output_tokens=500,
    )
    # Must not raise on an unrecognized local model name.
    ann.on_event(evt)
    # Strict float-zero equality, not "falsy": LLM-04 distinguishes 0.0 from NULL.
    assert evt.cost_usd == 0.0
    assert isinstance(evt.cost_usd, float)
    assert evt.cost_usd is not None
    assert evt.pricing_missing is False


def test_local_zero_ignores_token_counts() -> None:
    """Token volume is irrelevant: a local run is free no matter the usage."""
    ann = _annotator()
    evt = LLMCallEvent(
        trace_id="t1",
        iteration_idx=0,
        provider="local",
        model="qwen2.5:32b",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        cache_creation_input_tokens=500_000,
        cache_read_input_tokens=500_000,
    )
    ann.on_event(evt)
    assert evt.cost_usd == 0.0
    assert evt.pricing_missing is False


def test_unknown_cloud_model_still_null() -> None:
    """Control: unknown cloud model keeps cost_usd None + pricing_missing True."""
    ann = _annotator()
    evt = LLMCallEvent(
        trace_id="t1",
        iteration_idx=0,
        provider="anthropic",
        model="never-released-3000-pro",
        input_tokens=1000,
        output_tokens=500,
    )
    ann.on_event(evt)
    # Pitfall 5 intact: literal None, never 0 or 0.0.
    assert evt.cost_usd is None
    assert evt.pricing_missing is True


def test_known_cloud_model_still_priced() -> None:
    """Control: a known cloud model still computes a positive cache-aware cost."""
    ann = _annotator()
    evt = LLMCallEvent(
        trace_id="t1",
        iteration_idx=0,
        provider="anthropic",
        model="claude-sonnet-4-6",
        input_tokens=1000,
        output_tokens=500,
    )
    ann.on_event(evt)
    assert evt.cost_usd is not None
    assert evt.cost_usd > 0
    assert evt.pricing_missing is False


def test_pricing_table_resolves_local_sentinel_to_zero() -> None:
    """Defense in depth: a by-name lookup of "local" resolves to zero rates."""
    table = PricingTable()
    local = table.get("local")
    assert local is not None
    assert local.provider == "local"
    assert local.input_per_million == 0
    assert local.output_per_million == 0
    assert local.cache_write_per_million == 0
    assert local.cache_read_per_million == 0
