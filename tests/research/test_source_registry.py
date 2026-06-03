"""Tests for SourceRegistry and the [research] config fields.

Covers RESEARCH-03 (de-duplication by normalized URL) and the source-layer
half of RESEARCH-04 (hard cap via SourceBudgetExceeded), plus the config
round-trip for the new [research] section.
"""

from __future__ import annotations

import pytest

from horus_os.config import Config
from horus_os.research.registry import (
    Source,
    SourceBudgetExceeded,
    SourceRegistry,
    _normalize_url,
)


def test_exact_duplicate_url_is_deduplicated() -> None:
    reg = SourceRegistry(max_sources=10)
    idx1 = reg.register_source("https://a.test/x")
    idx2 = reg.register_source("https://a.test/x")
    assert idx1 == idx2 == 1
    assert reg.count() == 1


def test_normalization_dedups_trailing_slash_and_host_case() -> None:
    reg = SourceRegistry(max_sources=10)
    reg.register_source("https://a.test/x")
    reg.register_source("https://a.test/x/")
    reg.register_source("https://A.TEST/x")
    assert reg.count() == 1


def test_normalize_url_rule() -> None:
    # Lowercase scheme + host, strip one trailing slash, preserve path/query.
    assert _normalize_url("HTTPS://A.TEST/X/") == "https://a.test/X"
    assert _normalize_url("https://a.test/x?q=1") == "https://a.test/x?q=1"
    # Distinct paths stay distinct.
    assert _normalize_url("https://a.test/x") != _normalize_url("https://a.test/y")


def test_contains_only_true_for_registered_url() -> None:
    reg = SourceRegistry(max_sources=10)
    reg.register_source("https://a.test/x")
    assert reg.contains("https://a.test/x") is True
    assert reg.contains("https://a.test/x/") is True  # normalized match
    assert reg.contains("https://a.test/never") is False


def test_would_exceed_and_hard_cap_raises() -> None:
    reg = SourceRegistry(max_sources=2)
    reg.register_source("https://a.test/1")
    assert reg.would_exceed_source_budget() is False
    reg.register_source("https://a.test/2")
    assert reg.would_exceed_source_budget() is True
    with pytest.raises(SourceBudgetExceeded):
        reg.register_source("https://a.test/3")
    # The registry never silently grew past the cap.
    assert reg.count() == 2


def test_reregistering_known_url_does_not_trip_cap() -> None:
    reg = SourceRegistry(max_sources=1)
    reg.register_source("https://a.test/1", title="One")
    # Re-registering an existing URL is fine even at the cap.
    idx = reg.register_source("https://a.test/1")
    assert idx == 1
    assert reg.count() == 1


def test_ordered_sources_preserve_insertion_order() -> None:
    reg = SourceRegistry(max_sources=10)
    reg.register_source("https://a.test/1", title="One")
    reg.register_source("https://b.test/2", title="Two")
    ordered = reg.ordered_sources()
    assert [s.url for s in ordered] == ["https://a.test/1", "https://b.test/2"]
    assert all(isinstance(s, Source) for s in ordered)
    assert ordered[0].fetched_at  # ISO-8601 UTC stamp is set


def test_title_backfilled_on_reregister() -> None:
    reg = SourceRegistry(max_sources=10)
    reg.register_source("https://a.test/1")
    assert reg.ordered_sources()[0].title is None
    reg.register_source("https://a.test/1", title="Later title")
    assert reg.ordered_sources()[0].title == "Later title"


def test_index_of_returns_none_for_unknown() -> None:
    reg = SourceRegistry(max_sources=10)
    reg.register_source("https://a.test/1")
    assert reg.index_of("https://a.test/1") == 1
    assert reg.index_of("https://a.test/missing") is None


# ---------------------------------------------------------------------------
# Config [research] section
# ---------------------------------------------------------------------------


def test_config_research_defaults(tmp_path) -> None:
    cfg = Config.load(tmp_path)
    assert cfg.research_max_sources == 10
    assert cfg.research_max_iterations == 5


def test_config_reads_research_section(tmp_path) -> None:
    (tmp_path / "config.toml").write_text(
        "[research]\nmax_sources = 25\nmax_iterations = 8\n",
        encoding="utf-8",
    )
    cfg = Config.load(tmp_path)
    assert cfg.research_max_sources == 25
    assert cfg.research_max_iterations == 8


def test_config_round_trips_research_section(tmp_path) -> None:
    cfg = Config.with_defaults(tmp_path)
    cfg.research_max_sources = 30
    cfg.research_max_iterations = 9
    cfg.save()
    reloaded = Config.load(tmp_path)
    assert reloaded.research_max_sources == 30
    assert reloaded.research_max_iterations == 9
    # The section is present in the emitted TOML.
    assert "[research]" in (tmp_path / "config.toml").read_text(encoding="utf-8")
