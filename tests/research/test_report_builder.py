"""Tests for the citation-validating ReportBuilder.

Covers RESEARCH-04 (cited report), RESEARCH-03 (de-dup carried into the
reference list), and DR-2 (no citation can point at a URL not in the session
SourceRegistry).
"""

from __future__ import annotations

import pytest

from horus_os.research.registry import SourceRegistry
from horus_os.research.report import ReportBuilder, Section, UnverifiedCitation


def _registry(*urls: str) -> SourceRegistry:
    reg = SourceRegistry(max_sources=100)
    for i, url in enumerate(urls, start=1):
        reg.register_source(url, title=f"Source {i}")
    return reg


def test_inline_citations_and_reference_list() -> None:
    reg = _registry("https://a.test/1", "https://b.test/2")
    sections = [
        Section(
            heading="Findings",
            body="Claim one [[https://a.test/1]]. Claim two [[https://b.test/2]].",
        )
    ]
    out = ReportBuilder().render("My Topic", sections, reg)
    assert "# My Topic" in out
    assert "## Findings" in out
    assert "Claim one [1]." in out
    assert "Claim two [2]." in out
    assert "## References" in out
    assert "1. Source 1 - https://a.test/1" in out
    assert "2. Source 2 - https://b.test/2" in out


def test_reference_list_one_entry_per_registered_source_in_order() -> None:
    reg = _registry("https://a.test/1", "https://b.test/2")
    sections = [Section(heading="S", body="x [[https://b.test/2]] y [[https://a.test/1]]")]
    out = ReportBuilder().render("T", sections, reg)
    refs = [ln for ln in out.splitlines() if ln and ln[0].isdigit()]
    # Two entries, in registry order (1 then 2), each carrying title + URL.
    assert refs[0].startswith("1. Source 1 - https://a.test/1")
    assert refs[1].startswith("2. Source 2 - https://b.test/2")


def test_unverified_citation_rejected_by_default() -> None:
    reg = _registry("https://a.test/1")
    sections = [Section(heading="S", body="bad [[https://hallucinated.test/x]]")]
    with pytest.raises(UnverifiedCitation):
        ReportBuilder().render("T", sections, reg)


def test_unverified_url_never_appears_as_clean_reference_under_flag_policy() -> None:
    reg = _registry("https://a.test/1")
    sections = [
        Section(
            heading="S",
            body="good [[https://a.test/1]] bad [[https://hallucinated.test/x]]",
        )
    ]
    out = ReportBuilder().render("T", sections, reg, policy="flag")
    # The verified citation renders; the hallucinated URL is flagged, not cited.
    assert "good [1]" in out
    assert "## References" in out
    assert "https://a.test/1" in out
    assert "## Flagged citations" in out
    assert "https://hallucinated.test/x" in out
    # The bad URL is never a numbered reference entry.
    ref_block = out.split("## References")[1].split("## Flagged")[0]
    assert "hallucinated.test" not in ref_block


def test_duplicate_citations_collapse_to_one_reference_and_reuse_index() -> None:
    reg = _registry("https://a.test/1")
    sections = [Section(heading="S", body="a [[https://a.test/1]] b [[https://a.test/1/]]")]
    out = ReportBuilder().render("T", sections, reg)
    # Both markers map to the same [1] index (normalized dedup).
    assert out.count("[1]") == 2
    # Exactly one reference-list entry for the URL.
    assert out.count("1. Source 1 - https://a.test/1") == 1


def test_uncited_registered_source_not_listed() -> None:
    reg = _registry("https://a.test/1", "https://b.test/2")
    sections = [Section(heading="S", body="only one [[https://a.test/1]]")]
    out = ReportBuilder().render("T", sections, reg)
    assert "https://a.test/1" in out
    # b.test/2 was registered but never cited, so it is not in the references.
    assert "https://b.test/2" not in out


def test_unknown_policy_rejected() -> None:
    reg = _registry("https://a.test/1")
    with pytest.raises(ValueError):
        ReportBuilder().render("T", [Section("S", "x")], reg, policy="bogus")
