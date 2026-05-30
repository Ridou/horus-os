"""Pitfall 5 (PITFALLS.md): Dependabot CVE PRs get buried in a weekly minor-bump group.

The trap: applies-to: all-updates (or applies-to: security-updates) on a
Dependabot group means a real CVE-bumping PR is silently rolled up with
the routine weekly fastapi/pytest/ruff bumps. The maintainer reviews "11
deps bumped in one PR" as a chore-tier PR; the CVE buried inside gets the
same level of attention as the ruff patch bump. Days to hours of unaudited
exposure.

The Phase 54 DEPBOT-02 fix: every Dependabot group declares
`applies-to: version-updates` (NOT all-updates, NOT security-updates).
Security updates are explicitly UNGROUPED — every CVE gets its own PR
labelled `security-update`.

This regression pins:

1. .github/dependabot.yml contains zero `applies-to: security-updates`
   declarations on any non-comment line.
2. .github/dependabot.yml contains zero `applies-to: all-updates`
   declarations on any non-comment line.
3. Every group block contains an explicit `applies-to: version-updates`
   line (the positive contract: groups are FOR routine bumps only).
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPENDABOT_YML = REPO_ROOT / ".github" / "dependabot.yml"


def _non_comment_lines() -> list[str]:
    return [
        line
        for line in DEPENDABOT_YML.read_text(encoding="utf-8").splitlines()
        if not line.strip().startswith("#")
    ]


def test_no_applies_to_security_updates() -> None:
    """DEPBOT-02 hard rule: no group may absorb security-updates."""
    bad = [line for line in _non_comment_lines() if "applies-to: security-updates" in line]
    assert not bad, (
        f"Pitfall 5: dependabot.yml must NOT group security-updates "
        f"(every CVE gets its own PR); found: {bad}"
    )


def test_no_applies_to_all_updates() -> None:
    """DEPBOT-02 hard rule: no group may absorb all-updates either."""
    bad = [line for line in _non_comment_lines() if "applies-to: all-updates" in line]
    assert not bad, (
        f"Pitfall 5: dependabot.yml must NOT use applies-to: all-updates "
        f"(security-updates would be folded in silently); found: {bad}"
    )


def test_every_group_declares_version_updates() -> None:
    """Each group block in dependabot.yml has an explicit applies-to: version-updates."""
    # Count group declarations (look for the `groups:` section + each group key).
    # Each group key is followed within ~3 lines by `applies-to: version-updates`.
    # Structural assertion: the number of `applies-to:` lines equals the number of
    # `patterns:` lines (one applies-to per group, and every group has patterns).
    applies_lines = [line for line in _non_comment_lines() if "applies-to:" in line]
    patterns_lines = [line for line in _non_comment_lines() if "patterns:" in line]
    assert len(applies_lines) == len(patterns_lines), (
        f"Pitfall 5: every group must declare applies-to: version-updates; "
        f"found {len(applies_lines)} applies-to entries but {len(patterns_lines)} "
        f"group blocks (patterns: lines)"
    )
    # And every applies-to is version-updates
    for line in applies_lines:
        assert "version-updates" in line, (
            f"Pitfall 5: group declares non-version-updates scope: {line!r}"
        )
