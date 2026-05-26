"""Tests for the Phase 36 pricing-staleness banner.

Pitfall 5 contract: when pricing.json.updated_at is more than 30 days
old, the Observability tab displays a banner with the age in days and
the override-path token "HORUS_OS_PRICING_PATH" verbatim so the
cure is one cp-and-edit operation away. Yellow at 30-89 days, red at
90+. Banner failure is silent so a slow pricing-status route never
blocks the panels.

Tests 1-3 are HTML-marker tests pinning the JS function name, the
override-path copy, and the threshold values. Tests 4-5 are
integration tests against /api/observability/pricing-status proving
the data flow from PricingTable through the route into the banner.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from horus_os import create_app


def _fixture(tmp_path: Path, updated_at: str) -> Path:
    payload = {
        "version": "1",
        "updated_at": updated_at,
        "release_version": "test",
        "models": {
            "test-model": {
                "provider": "test",
                "input_per_million": 1.0,
                "output_per_million": 1.0,
                "cache_write_per_million": 0.0,
                "cache_read_per_million": 0.0,
            }
        },
    }
    path = tmp_path / "pricing.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_banner_render_function_and_override_copy(tmp_path: Path) -> None:
    """JS function name + override-path token + endpoint reference + thresholds."""
    body = TestClient(create_app(data_dir=tmp_path)).get("/").text
    # JS function name appears (definition + call from loadObservability).
    assert "renderStalenessBanner" in body
    # Pitfall 5: override-path token MUST be verbatim so the cure is
    # one cp-and-edit operation away.
    assert "HORUS_OS_PRICING_PATH" in body
    # Endpoint the banner fetches.
    assert "/api/observability/pricing-status" in body
    # Threshold constants in the JS.
    assert "< 30" in body
    assert "< 90" in body


def test_banner_css_classes_defined(tmp_path: Path) -> None:
    """The .obs-banner.yellow and .obs-banner.red CSS rules are populated."""
    body = TestClient(create_app(data_dir=tmp_path)).get("/").text
    assert ".obs-banner.yellow" in body
    assert ".obs-banner.red" in body


def test_banner_copy_prefix_present(tmp_path: Path) -> None:
    """Pitfall 5: banner copy starts with 'Pricing data is' (N interpolated)."""
    body = TestClient(create_app(data_dir=tmp_path)).get("/").text
    assert "Pricing data is" in body


def test_pricing_status_integration_stale_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Env-override fixture with old updated_at flows through to is_stale=True.

    Proves the banner will render red when the data warrants. If the
    HORUS_OS_PRICING_PATH override silently broke, this test would
    fail before the banner ever shipped (Pitfall 5 + T-36-06).
    """
    fixture = _fixture(tmp_path, updated_at="2025-01-01")
    monkeypatch.setenv("HORUS_OS_PRICING_PATH", str(fixture))
    response = TestClient(create_app(data_dir=tmp_path)).get(
        "/api/observability/pricing-status"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_stale"] is True
    # 2025-01-01 is >= 90 days before today regardless of small clock
    # drift; the banner will render red.
    assert body["updated_at_age_days"] >= 90


def test_pricing_status_bundled_freshness_consistency(tmp_path: Path) -> None:
    """Bundled pricing.json freshness matches PricingTable.is_stale(30).

    Pinning to internal consistency (route value == PricingTable's
    own answer) instead of a hardcoded boolean keeps the test stable
    over time: when the bundled file ages past 30 days, both sides
    flip together and the test still passes.
    """
    from datetime import UTC, datetime

    app = create_app(data_dir=tmp_path)
    expected = app.state.pricing_table.is_stale(datetime.now(UTC), 30)
    expected_age = app.state.pricing_table.updated_at_age_days(datetime.now(UTC))
    response = TestClient(app).get("/api/observability/pricing-status")
    body = response.json()
    assert body["is_stale"] is expected
    # Age can drift by 1 day if the test crosses midnight UTC; allow tolerance.
    assert abs(body["updated_at_age_days"] - expected_age) <= 1
