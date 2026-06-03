"""Pitfall 6 (PITFALLS.md): CONTRIBUTING.md anti-patterns kill outside adoption.

The trap: a CONTRIBUTING.md that promises a 24-hour response time (the
solo maintainer cannot meet it), mandates a CLA (Apache 2.0 is
inbound-equals-outbound, no CLA needed), or makes a Discord join required
(GitHub Issues + Discussions is the canonical surface) all drive away
the first-time contributor before they read past line 50.

The Phase 55 fix codified honest expectations:
- "No 24-hour SLA" stated explicitly; the Sunday-triage cadence is
  documented with a "may go silent up to 2 weeks" honest caveat.
- No CLA. See .planning/decisions/no-cla.md.
- Discord is OPTIONAL; GitHub is the canonical surface.

This regression pins the negative-space contract: certain phrases that
would re-introduce the anti-pattern must NOT appear in CONTRIBUTING.md.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRIBUTING_MD = REPO_ROOT / "CONTRIBUTING.md"


def _content() -> str:
    return CONTRIBUTING_MD.read_text(encoding="utf-8")


def test_no_24_hour_sla_promise() -> None:
    """CONTRIBUTING.md must NOT promise a 24-hour response."""
    text = _content().lower()
    forbidden = [
        "within 24 hours",
        "24-hour response",
        "respond within 24",
        "24h sla",
        "24 hour sla",
    ]
    hits = [phrase for phrase in forbidden if phrase in text]
    # The phrase "no 24-hour SLA" IS allowed because it negates the anti-pattern.
    # Drop hits that appear inside a negating context.
    real_hits = []
    for phrase in hits:
        idx = text.find(phrase)
        # Check 12 chars BEFORE the phrase for a negation
        prefix = text[max(0, idx - 15) : idx]
        if "no " in prefix or "not " in prefix:
            continue
        real_hits.append(phrase)
    assert not real_hits, (
        f"Pitfall 6: CONTRIBUTING.md must not promise a 24-hour SLA the "
        f"solo maintainer cannot meet; found: {real_hits}"
    )


def test_no_cla_requirement() -> None:
    """CONTRIBUTING.md must NOT require a Contributor License Agreement."""
    text = _content().lower()
    # The phrase "no cla" or "no contributor license agreement" IS allowed.
    forbidden = [
        "sign the cla",
        "sign our cla",
        "sign a cla",
        "cla required",
        "cla is required",
        "must sign the cla",
    ]
    hits = [phrase for phrase in forbidden if phrase in text]
    assert not hits, (
        f"Pitfall 6: CONTRIBUTING.md must not require a CLA "
        f"(Apache 2.0 inbound-equals-outbound is sufficient); found: {hits}"
    )


def test_no_mandatory_discord_join() -> None:
    """CONTRIBUTING.md must NOT make Discord a prerequisite for contribution."""
    text = _content().lower()
    forbidden = [
        "join our discord",
        "join the discord",
        "must join discord",
        "discord required",
        "discord is required",
        "first, join discord",
    ]
    hits = [phrase for phrase in forbidden if phrase in text]
    assert not hits, (
        f"Pitfall 6: CONTRIBUTING.md must not require joining Discord "
        f"(GitHub Issues + Discussions is the canonical surface); found: {hits}"
    )


def test_honest_slo_language_present() -> None:
    """The honest 'aim to acknowledge within 7 days' SLO must be documented somewhere."""
    text = _content().lower()
    # The post-flip flow section is the right place; or the SLO subsection.
    assert "7 days" in text or "seven days" in text or "sunday triage" in text, (
        "Pitfall 6: CONTRIBUTING.md should document the honest SLO "
        "(Sunday-triage cadence or 7-day acknowledgement target)"
    )
