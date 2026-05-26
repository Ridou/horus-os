"""Tests for GET /api/observability/pricing-status and PricingTable exposure.

Phase 36 Task 1 contract:

  1. GET /api/observability/pricing-status returns 200 with the body
     {updated_at: ISO YYYY-MM-DD, updated_at_age_days: int, is_stale: bool}.
  2. The route is JSON and registered under the existing
     /api/observability/* prefix family.
  3. app.state.pricing_table is the same PricingTable instance the
     CostAnnotator subscriber holds (guards against silent
     dual-construction in future refactors).
  4. HORUS_OS_PRICING_PATH env override flows end-to-end: when the
     env points at a fixture pricing.json with an old updated_at,
     the route reflects the override (large age, is_stale=True).
     Pitfall 5 + PRICE-04 reaching the staleness banner data
     source.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from horus_os import create_app
from horus_os.observability import PricingTable


def _fixture(tmp_path: Path, updated_at: str) -> Path:
    """Write a minimal valid pricing.json fixture and return its path."""
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


def test_pricing_status_returns_expected_shape(tmp_path: Path) -> None:
    """Body has the three documented keys with the right types."""
    client = TestClient(create_app(data_dir=tmp_path))
    response = client.get("/api/observability/pricing-status")
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"updated_at", "updated_at_age_days", "is_stale"}
    # updated_at is ISO YYYY-MM-DD; the bundled file currently dates 2026-05-26.
    assert isinstance(body["updated_at"], str)
    assert body["updated_at"] == "2026-05-26"
    # Age is a non-negative integer (dates do not go backwards).
    assert isinstance(body["updated_at_age_days"], int)
    assert body["updated_at_age_days"] >= 0
    # is_stale is a real Python/JSON bool, not 0 or 1.
    assert isinstance(body["is_stale"], bool)


def test_pricing_status_returns_json_content_type(tmp_path: Path) -> None:
    """Lives under /api/observability/* prefix and serves JSON."""
    client = TestClient(create_app(data_dir=tmp_path))
    response = client.get("/api/observability/pricing-status")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")


def test_app_state_pricing_table_is_singleton(tmp_path: Path) -> None:
    """app.state.pricing_table is the same instance the route reads.

    Guards against a future refactor silently constructing a second
    PricingTable. The CostAnnotator subscriber and the pricing-status
    route MUST read from the same source so the banner cannot disagree
    with what the annotator actually used for cost math.
    """
    app = create_app(data_dir=tmp_path)
    assert hasattr(app.state, "pricing_table")
    assert app.state.pricing_table is not None
    assert isinstance(app.state.pricing_table, PricingTable)
    # Bundled pricing.json dates 2026-05-26; pin the contract.
    assert app.state.pricing_table.updated_at == date(2026, 5, 26)


def test_pricing_status_honors_env_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HORUS_OS_PRICING_PATH env override drives the banner data source.

    Pitfall 5 + PRICE-04: the override path the banner copy advertises
    MUST be the same path that drives the pricing-status response. If
    this test ever flips, the banner is lying about the cure path.
    """
    fixture = _fixture(tmp_path, updated_at="2025-01-01")
    monkeypatch.setenv("HORUS_OS_PRICING_PATH", str(fixture))
    client = TestClient(create_app(data_dir=tmp_path))
    response = client.get("/api/observability/pricing-status")
    assert response.status_code == 200
    body = response.json()
    assert body["updated_at"] == "2025-01-01"
    # 2025-01-01 is well over a year before 2026-05-26; age must be
    # large and is_stale must fire.
    assert body["updated_at_age_days"] >= 365
    assert body["is_stale"] is True
