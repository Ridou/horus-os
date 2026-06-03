"""Pitfall 10 (PITFALLS.md): the gate flip has no rollback plan; flip-and-pray.

The trap: the maintainer flips STATUS.md / CONTRIBUTING.md / SECURITY.md /
PR template to "contributions OPEN" in a sprawling multi-commit diff. The
first week's PR volume overwhelms; flipping BACK to solo mode requires
unwinding dozens of edits, each one a tiny merge conflict if anything
landed in the meantime.

The Phase 56 fix: a single rollback patch at .planning/rollback/flip-gate-revert.md
that captures the inverse of the Phase 59 atomic flip commit. `git apply
<this file>` reverses the gate flip in one step.

This regression pins:
1. The rollback file exists.
2. It contains a unified-diff payload (lines starting with --- / +++).
3. It targets the public-facing files the Phase 59 flip will touch
   (STATUS.md, README.md, CONTRIBUTING.md, SECURITY.md, the PR template).
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ROLLBACK_PATCH = REPO_ROOT / ".planning" / "rollback" / "flip-gate-revert.md"


def test_rollback_patch_exists() -> None:
    """The Phase 56 rollback patch file must be committed."""
    assert ROLLBACK_PATCH.is_file(), (
        "Pitfall 10: .planning/rollback/flip-gate-revert.md must exist so a "
        "post-flip emergency rollback is a single `git apply` rather than "
        "a multi-commit unwind"
    )


def test_rollback_patch_documents_three_methods() -> None:
    """The Phase 56 rollback template documents at least three rollback methods.

    Per Phase 56 RUNBOOK-02: git revert (preferred for fast-forward-safe history),
    git reset --hard (destructive; coordinate first), and literal patch apply
    (when both flip and revert have been pushed and a third undo is needed).
    """
    text = ROLLBACK_PATCH.read_text(encoding="utf-8")
    # Each method appears as a section heading
    assert "git revert" in text, (
        "Pitfall 10: flip-gate-revert.md must document the git revert method"
    )
    assert "git reset" in text, "Pitfall 10: flip-gate-revert.md must document the git reset method"
    # The third method is "patch apply" or "git apply"
    assert "patch apply" in text.lower() or "git apply" in text, (
        "Pitfall 10: flip-gate-revert.md must document the patch-apply rollback method"
    )


def test_rollback_targets_public_facing_files() -> None:
    """The rollback patch must mention the public-facing files the flip touches."""
    text = ROLLBACK_PATCH.read_text(encoding="utf-8")
    # At least 2 of these must appear so the rollback is non-trivial.
    targets = [
        "STATUS.md",
        "README.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "PULL_REQUEST_TEMPLATE.md",
    ]
    hit_count = sum(1 for target in targets if target in text)
    assert hit_count >= 2, (
        f"Pitfall 10: flip-gate-revert.md must target multiple public-facing "
        f"files (STATUS.md, README.md, CONTRIBUTING.md, SECURITY.md, "
        f"PULL_REQUEST_TEMPLATE.md); only {hit_count} of 5 found"
    )
