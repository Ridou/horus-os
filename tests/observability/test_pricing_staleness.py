"""Phase 34 Task 5: PRICE-05 staleness banner substrate.

Pins the is_stale boundary at 29 / 30 / 31 days and the
updated_at_age_days arithmetic at 60 and 90 days. The Phase 36
dashboard reads the boolean for the banner color (yellow at 30-60,
red past 90); the Phase 39 release CI gate reads is_stale at 14 days
to refuse stale releases. Pinning the boundary here prevents drift.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from horus_os.observability import PricingTable

NOW = datetime(2026, 5, 26, 12, 0, 0)


def _fixture(tmp_path: Path, updated_at: date) -> Path:
    payload = {
        "version": "1",
        "updated_at": updated_at.isoformat(),
        "release_version": "test",
        "models": {
            "anything": {
                "provider": "test",
                "input_per_million": 0.0,
                "output_per_million": 0.0,
                "cache_write_per_million": 0.0,
                "cache_read_per_million": 0.0,
            }
        },
    }
    path = tmp_path / "pricing.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_is_stale_at_29_days(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path, updated_at=(NOW.date() - timedelta(days=29)))
    table = PricingTable(path=fixture)
    assert table.is_stale(NOW, threshold_days=30) is False


def test_is_stale_at_30_days(tmp_path: Path) -> None:
    """Boundary contract: strictly past 30 days flips True; 30 itself is False."""
    fixture = _fixture(tmp_path, updated_at=(NOW.date() - timedelta(days=30)))
    table = PricingTable(path=fixture)
    assert table.is_stale(NOW, threshold_days=30) is False


def test_is_stale_at_31_days(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path, updated_at=(NOW.date() - timedelta(days=31)))
    table = PricingTable(path=fixture)
    assert table.is_stale(NOW, threshold_days=30) is True


def test_updated_at_age_days_boundary(tmp_path: Path) -> None:
    """Pin 60 and 90 day arithmetic for the Phase 36 banner switch points."""
    fixture_60 = _fixture(tmp_path, updated_at=(NOW.date() - timedelta(days=60)))
    table_60 = PricingTable(path=fixture_60)
    assert table_60.updated_at_age_days(NOW) == 60

    fixture_90 = tmp_path / "pricing_90.json"
    fixture_90.write_text(
        json.dumps(
            {
                "version": "1",
                "updated_at": (NOW.date() - timedelta(days=90)).isoformat(),
                "release_version": "test",
                "models": {},
            }
        ),
        encoding="utf-8",
    )
    table_90 = PricingTable(path=fixture_90)
    assert table_90.updated_at_age_days(NOW) == 90
