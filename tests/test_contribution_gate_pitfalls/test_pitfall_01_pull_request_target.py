"""Pitfall 1 (PITFALLS.md): pull_request_target + checkout-PR-head leaks every secret.

CIHARD-01: v0.6 ships ZERO pull_request_target triggers. This regression
asserts that no workflow under .github/workflows/ uses the trigger, and
no workflow that DID use it (none exist in v0.6) checks out PR-head
under that trigger.

The escape-hatch grammar (# SECURITY: comment + safe-to-test label gate)
is documented in CIHARD-01 but unused in v0.6. If v0.7+ adds a workflow
that needs pull_request_target, this test grows a positive-case branch
asserting the escape-hatch comment + label-gate are present.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

# Catches: "on: pull_request_target:", "on:\n  pull_request_target:",
# "on: [pull_request_target, push]", "on:\n  - pull_request_target".
# Anchored against word boundary to avoid matching e.g. "my_pull_request_target_test".
_TRIGGER_PATTERN = re.compile(r"\bpull_request_target\b")


def test_no_workflow_uses_pull_request_target() -> None:
    """Every .github/workflows/*.yml file must NOT contain pull_request_target."""
    offenders: list[tuple[Path, int, str]] = []
    for workflow in sorted(WORKFLOWS_DIR.glob("*.yml")):
        text = workflow.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            # Skip full-line comments so docs/explanations in comments
            # do not trip the assertion. Inline comments after the trigger
            # name are not a concern because pull_request_target is YAML
            # structural, not a comment-allowed position.
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if _TRIGGER_PATTERN.search(line):
                offenders.append((workflow.relative_to(REPO_ROOT), line_number, line.rstrip()))
    assert not offenders, (
        "pull_request_target trigger found in:\n"
        + "\n".join(f"  {p}:{ln}: {text}" for p, ln, text in offenders)
        + "\nv0.6 ships ZERO pull_request_target triggers (CIHARD-01)."
    )
