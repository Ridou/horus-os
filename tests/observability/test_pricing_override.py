"""Phase 34 Task 5: PRICE-04 unit-level proof.

Complements the e2e proof in tests/observability/test_cost_annotator_e2e.py
by exercising PricingTable(path=...) directly. Verifies the override
resolves the fixture's rates, does not leak into a sibling bundled
instance, and flows through the CostAnnotator math.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from horus_os.observability import CostAnnotator, PricingTable
from horus_os.observability.bus import LLMCallEvent


def _fixture(tmp_path: Path, model: str, input_per_million: float) -> Path:
    payload = {
        "version": "1",
        "updated_at": "2026-05-26",
        "release_version": "test",
        "models": {
            model: {
                "provider": "test",
                "input_per_million": input_per_million,
                "output_per_million": 0.0,
                "cache_write_per_million": 0.0,
                "cache_read_per_million": 0.0,
            }
        },
    }
    path = tmp_path / "pricing.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_override_path_resolves_fixture_rates(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path, model="test-model", input_per_million=42.0)
    table = PricingTable(path=fixture)
    pricing = table.get("test-model")
    assert pricing is not None
    assert pricing.input_per_million == pytest.approx(42.0)
    assert pricing.provider == "test"


def test_override_path_does_not_pollute_bundled(tmp_path: Path) -> None:
    """Constructing an override-backed table does not leak into bundled."""
    fixture = _fixture(tmp_path, model="test-model", input_per_million=42.0)
    override = PricingTable(path=fixture)
    bundled = PricingTable()
    # Override sees fixture; bundled does not.
    assert override.get("test-model") is not None
    assert bundled.get("test-model") is None
    # Bundled still resolves the seeded models.
    assert bundled.get("claude-sonnet-4-6") is not None


def test_cost_annotator_honors_override(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path, model="test-model", input_per_million=42.0)
    ann = CostAnnotator(PricingTable(path=fixture))
    evt = LLMCallEvent(
        trace_id="t1",
        iteration_idx=0,
        provider="test",
        model="test-model",
        input_tokens=1000,
        output_tokens=0,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
    )
    ann.on_event(evt)
    # 1000 * 42.0 / 1_000_000 = 0.042
    assert evt.cost_usd == pytest.approx(0.042, abs=1e-9)
    assert evt.pricing_missing is False
