"""PricingTable: per-million USD rates with cache-aware fields.

Backs the Phase 34 CostAnnotator. The bundled `pricing.json` ships as
package data; users can override via `HORUS_OS_PRICING_PATH` env var or
the `[pricing] path` key in `config.toml`. The override path is plumbed
through `Config.pricing_path` and passed into `PricingTable(path=...)`
at `create_app` boot.

Schema mirrors the field-naming convention from LiteLLM's
`model_prices_and_context_window.json` so contributors refreshing the
bundled file at release time can mechanically diff against the upstream
canonical (Pitfall 5 sync-against-source strategy).

The table self-discloses its `updated_at` so the Phase 36 dashboard can
render a staleness banner: yellow at 30-60 days old, red past 90 days.
`is_stale(now, threshold_days)` pins the boolean contract; the Phase 39
release CI gate will refuse to tag when `updated_at` is older than 14
days from the tag date.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from importlib import resources
from pathlib import Path


@dataclass(frozen=True)
class ModelPricing:
    """Per-million USD rates for one model.

    All four rates are independent. Cache-write is what Anthropic charges
    when you write a cacheable prefix into the SDK's prompt-caching
    layer; cache-read is the discounted rate (typically ~10% of input)
    when subsequent calls hit that cached prefix. Gemini does not bill
    for cache-write at the v2.5 API surface, hence the 0.00 in the
    bundled file; cache-read still applies via context caching.
    """

    provider: str
    input_per_million: float
    output_per_million: float
    cache_write_per_million: float
    cache_read_per_million: float


class PricingTable:
    """Lookup of (model name) -> ModelPricing plus staleness metadata.

    Loads the bundled `pricing.json` via `importlib.resources` when
    `path` is None; otherwise reads from `path`. The bundled file is
    shipped as package-data via `[tool.setuptools.package-data]` in
    `pyproject.toml`. Construction is cheap and synchronous; the table
    is intended to be built once at `create_app` boot and held for the
    process lifetime.

    The override path lets users (a) ship their own newer rates between
    horus-os releases without forking, and (b) load a fixture in tests
    so the bundled file is not the source of truth for behavior under
    test (Pitfall 5: tests must touch their own fixture, not hardcode
    package data into the cost path).
    """

    def __init__(self, path: Path | None = None) -> None:
        if path is None:
            raw = (
                resources.files("horus_os.observability")
                .joinpath("pricing.json")
                .read_text(encoding="utf-8")
            )
        else:
            raw = Path(path).read_text(encoding="utf-8")
        payload = json.loads(raw)
        self.version: str = str(payload["version"])
        self.updated_at: date = date.fromisoformat(payload["updated_at"])
        self.release_version: str = str(payload["release_version"])
        self._models: dict[str, ModelPricing] = {
            name: ModelPricing(
                provider=str(spec["provider"]),
                input_per_million=float(spec["input_per_million"]),
                output_per_million=float(spec["output_per_million"]),
                cache_write_per_million=float(spec["cache_write_per_million"]),
                cache_read_per_million=float(spec["cache_read_per_million"]),
            )
            for name, spec in (payload.get("models") or {}).items()
        }

    def get(self, model: str) -> ModelPricing | None:
        """Return the ModelPricing for `model`, or None when unknown.

        Returning None on unknown is the Pitfall 5 contract: NULL is
        honest, zero is a lie. CostAnnotator inspects this for the
        pricing_missing flag path.
        """
        return self._models.get(model)

    def is_stale(self, now: datetime, threshold_days: int = 30) -> bool:
        """Return True when (now - updated_at) strictly exceeds threshold_days.

        Boundary contract pinned by tests: 29 days = False, 30 days =
        False, 31 days = True. The Phase 36 dashboard banner reads this
        flag at the 30-day threshold; the Phase 39 release CI gate
        reads it at 14 days to block stale releases.
        """
        age_days = (now.date() - self.updated_at).days
        return age_days > threshold_days

    def updated_at_age_days(self, now: datetime) -> int:
        """Return the integer day count between `now` and `updated_at`.

        Used by the Phase 36 dashboard banner copy. Yellow at 30-60
        days, red past 90 days; Phase 36 switches on this value.
        """
        return (now.date() - self.updated_at).days


__all__ = ["ModelPricing", "PricingTable"]
