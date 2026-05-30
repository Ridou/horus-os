"""Pitfall 7 (PITFALLS.md): stale-bot eats real bugs; label taxonomy bloats.

Two distinct traps under one umbrella:

1. actions/stale auto-closes issues after silence. The closed issue
   becomes invisible to search; the bug regresses; a new contributor
   files a duplicate; the cycle repeats. v0.6 explicitly opts OUT
   (decision file .planning/decisions/no-stale-bot.md).

2. The label set grows uncontrollably (`needs-info`, `needs-decision`,
   `needs-design`, ... 40 labels nobody can remember). The fix is a
   hard cap of 15, documented in docs/LABEL-TAXONOMY.md.

This regression pins:
- No actions/stale workflow exists under .github/workflows/.
- docs/LABEL-TAXONOMY.md documents the 15-label cap.
- docs/TRIAGE.md mentions the no-stale-bot decision.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
LABEL_TAXONOMY_MD = REPO_ROOT / "docs" / "LABEL-TAXONOMY.md"
TRIAGE_MD = REPO_ROOT / "docs" / "TRIAGE.md"
NO_STALE_DECISION = REPO_ROOT / ".planning" / "decisions" / "no-stale-bot.md"


def test_no_actions_stale_workflow_present() -> None:
    """No workflow under .github/workflows/ uses actions/stale."""
    offenders: list[tuple[str, int, str]] = []
    for workflow in sorted(WORKFLOWS_DIR.glob("*.yml")):
        text = workflow.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "actions/stale" in line:
                offenders.append((workflow.name, line_number, line.rstrip()))
    assert not offenders, (
        "Pitfall 7: actions/stale must NOT be wired (see "
        ".planning/decisions/no-stale-bot.md). Offenders:\n"
        + "\n".join(f"  {n}:{ln}: {text}" for n, ln, text in offenders)
    )


def test_label_taxonomy_documents_hard_cap() -> None:
    """docs/LABEL-TAXONOMY.md documents a hard cap of 15 labels."""
    assert LABEL_TAXONOMY_MD.is_file(), "Pitfall 7: docs/LABEL-TAXONOMY.md must exist"
    text = LABEL_TAXONOMY_MD.read_text(encoding="utf-8").lower()
    assert "15" in text and ("cap" in text or "limit" in text or "maximum" in text), (
        "Pitfall 7: docs/LABEL-TAXONOMY.md must document the 15-label hard cap"
    )


def test_triage_doc_references_no_stale_bot() -> None:
    """docs/TRIAGE.md must reference the no-stale-bot decision (transparency)."""
    assert TRIAGE_MD.is_file(), "Pitfall 7: docs/TRIAGE.md must exist"
    text = TRIAGE_MD.read_text(encoding="utf-8").lower()
    assert "no-stale-bot" in text or "auto-close" in text or "actions/stale" in text, (
        "Pitfall 7: docs/TRIAGE.md must explicitly document the no-auto-close policy"
    )


def test_no_stale_bot_decision_file_exists() -> None:
    """The decision file .planning/decisions/no-stale-bot.md must be committed."""
    assert NO_STALE_DECISION.is_file(), (
        "Pitfall 7: .planning/decisions/no-stale-bot.md must document the rationale"
    )
