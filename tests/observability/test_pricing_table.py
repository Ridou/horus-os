"""Phase 34 Task 2 tests: PricingTable + bundled pricing.json + package-data.

Covers the contract for the bundled pricing.json shape, importlib.resources
loading, override path loading, ModelPricing immutability, staleness math,
and the pyproject.toml package-data grep that proves the JSON ships in the
wheel (Pitfall 5 substrate).
"""

from __future__ import annotations

import dataclasses
import json
from datetime import date, datetime
from pathlib import Path

import pytest

from horus_os.observability import ModelPricing, PricingTable


def test_bundled_pricing_loads() -> None:
    table = PricingTable()
    expected = {
        "claude-sonnet-4-6": (3.00, 15.00, 3.75, 0.30, "anthropic"),
        "claude-opus-4-7": (15.00, 75.00, 18.75, 1.50, "anthropic"),
        "claude-haiku-4-5": (1.00, 5.00, 1.25, 0.10, "anthropic"),
        "gemini-2.5-flash": (0.30, 2.50, 0.00, 0.075, "google"),
        "gemini-2.5-pro": (1.25, 10.00, 0.00, 0.31, "google"),
    }
    for model, (inp, out, cwrite, cread, provider) in expected.items():
        pricing = table.get(model)
        assert pricing is not None, f"missing model {model!r} in bundled pricing.json"
        assert pricing.provider == provider
        assert pricing.input_per_million == pytest.approx(inp)
        assert pricing.output_per_million == pytest.approx(out)
        assert pricing.cache_write_per_million == pytest.approx(cwrite)
        assert pricing.cache_read_per_million == pytest.approx(cread)


def test_unknown_model_returns_none() -> None:
    table = PricingTable()
    assert table.get("never-released-3000-pro") is None


def test_metadata_fields_present() -> None:
    table = PricingTable()
    assert table.version == "1"
    assert table.updated_at == date(2026, 5, 26)
    assert table.release_version == "0.4.0"


def _write_fixture(
    tmp_path: Path,
    updated_at: str,
    models: dict | None = None,
) -> Path:
    payload = {
        "version": "1",
        "updated_at": updated_at,
        "release_version": "0.4.0",
        "models": models
        or {
            "fixture-model": {
                "provider": "test",
                "input_per_million": 1.0,
                "output_per_million": 2.0,
                "cache_write_per_million": 0.0,
                "cache_read_per_million": 0.0,
            }
        },
    }
    fixture = tmp_path / "pricing.json"
    fixture.write_text(json.dumps(payload), encoding="utf-8")
    return fixture


def test_is_stale_false_within_threshold(tmp_path: Path) -> None:
    now = datetime(2026, 5, 26, 12, 0, 0)
    fixture = _write_fixture(tmp_path, updated_at=(date(2026, 5, 16)).isoformat())
    table = PricingTable(path=fixture)
    assert table.is_stale(now, threshold_days=30) is False


def test_is_stale_true_past_threshold(tmp_path: Path) -> None:
    now = datetime(2026, 5, 26, 12, 0, 0)
    fixture = _write_fixture(tmp_path, updated_at=date(2026, 4, 11).isoformat())
    table = PricingTable(path=fixture)
    assert table.is_stale(now, threshold_days=30) is True


def test_updated_at_age_days(tmp_path: Path) -> None:
    now = datetime(2026, 5, 26, 12, 0, 0)
    fixture = _write_fixture(tmp_path, updated_at=date(2026, 5, 9).isoformat())
    table = PricingTable(path=fixture)
    assert table.updated_at_age_days(now) == 17


def test_modelpricing_is_frozen() -> None:
    fields = {f.name for f in dataclasses.fields(ModelPricing)}
    assert fields == {
        "provider",
        "input_per_million",
        "output_per_million",
        "cache_write_per_million",
        "cache_read_per_million",
    }
    pricing = ModelPricing(
        provider="anthropic",
        input_per_million=1.0,
        output_per_million=2.0,
        cache_write_per_million=0.0,
        cache_read_per_million=0.0,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        pricing.input_per_million = 99.0  # type: ignore[misc]


def test_package_data_grep() -> None:
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    contents = pyproject.read_text(encoding="utf-8")
    assert '"horus_os.observability" = ["pricing.json"]' in contents, (
        "pyproject.toml must wire pricing.json as package-data so the "
        "wheel ships the JSON; this guards Pitfall 5 substrate"
    )
