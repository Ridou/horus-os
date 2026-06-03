"""Pitfall 12 (PITFALLS.md): SECURITY.md SLOs the solo maintainer cannot meet.

The trap: SECURITY.md commits to a 24-hour acknowledgement and a 7-day
fix target for Critical CVEs. The solo maintainer cannot honor those
numbers; the first real CVE arrives, the SLOs are missed, the
maintainer panics, and the reporter sees a project that did not deliver
on its own commitments. Trust burned for the next reporter.

The Phase 56 fix: severity-tier SLOs with HONEST day targets
(Critical 14d, High 30d, Medium 90d, Low none) + an explicit
over-capacity escalation path (public follow-up issue if maintainer
goes silent for 7+ days post-acknowledgement).

This regression pins:
1. SECURITY.md documents severity-tier SLOs with day numbers (not hour numbers).
2. The Critical SLO is >= 7 days (the realistic floor for a solo maintainer).
3. SECURITY.md documents an over-capacity escalation path.
4. CODEOWNERS is path-scoped (NOT a blanket `* @Ridou` line that creates
   the appearance of multi-owner review without the substance).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SECURITY_MD = REPO_ROOT / "SECURITY.md"
CODEOWNERS = REPO_ROOT / ".github" / "CODEOWNERS"


def test_security_documents_severity_tier_slos() -> None:
    """SECURITY.md must document SLOs with explicit day numbers, not 24-hour promises."""
    text = SECURITY_MD.read_text(encoding="utf-8").lower()
    assert "severity" in text, "Pitfall 12: SECURITY.md must use severity-tier SLO language"
    # Critical / High / Medium tiers should be named
    for tier in ("critical", "high", "medium"):
        assert tier in text, f"Pitfall 12: SECURITY.md must name the {tier} severity tier"


def test_security_critical_slo_is_realistic() -> None:
    """Critical SLO must be >= 7 days; no 24-hour or '< 7 day' promise."""
    text = SECURITY_MD.read_text(encoding="utf-8").lower()
    # Extract a "critical ... N days" pattern. If found, N must be >= 7.
    # The Phase 56 contract: Critical 14 days from acknowledgement.
    match = re.search(r"critical[^:]*[:\(].{0,80}?(\d+)\s*days?", text, re.DOTALL)
    assert match is not None, (
        "Pitfall 12: SECURITY.md must declare an explicit day-numbered Critical SLO"
    )
    days = int(match.group(1))
    assert days >= 7, (
        f"Pitfall 12: Critical SLO {days}d is too aggressive for a solo maintainer; "
        f"v0.6 floor is 7 days, target is 14 (Phase 56)"
    )


def test_security_has_over_capacity_escalation_path() -> None:
    """SECURITY.md documents what to do when the maintainer goes silent."""
    text = SECURITY_MD.read_text(encoding="utf-8").lower()
    # Look for "over-capacity" or "follow-up" or "escalation" or "silent"
    assert (
        "over-capacity" in text
        or "follow-up" in text
        or "followup" in text
        or "goes silent" in text
        or "escalation" in text
    ), (
        "Pitfall 12: SECURITY.md must document an escalation path "
        "(public follow-up issue) when the maintainer goes silent"
    )


def test_codeowners_is_path_scoped_not_blanket() -> None:
    """CODEOWNERS must NOT have a blanket `* @<maintainer>` line."""
    text = CODEOWNERS.read_text(encoding="utf-8")
    offenders: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        # A blanket-owner line is `* @user` (the literal `*` pattern matches everything).
        # Allow `**/<path>` patterns; reject lone `*`.
        if re.match(r"^\*\s+@\S+", stripped):
            offenders.append(stripped)
    assert not offenders, (
        f"Pitfall 12: CODEOWNERS must be path-scoped, not blanket-owned; "
        f"a `* @user` line creates the appearance of multi-owner review without "
        f"the substance. Offenders: {offenders}"
    )
