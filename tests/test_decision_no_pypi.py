"""SIGN-05 (Phase 52 Wave 0 RED-by-design): no-pypi-in-v0.6 decision file + cross-ref.

Three production assertions cover SIGN-05 per VALIDATION.md row 5:

1. test_decision_file_exists: `.planning/decisions/no-pypi-in-v0.6.md`
   is present and non-empty. Phase 52 establishes the
   `.planning/decisions/` directory with this as its first file
   (CONTEXT.md canonical_refs documents this).
2. test_decision_file_has_terminator: the file contains the literal
   `**Decision (final, until revisited):**` terminator block. This
   is the load-bearing convention from CONTEXT.md code_context for
   the decision-file shape.
3. test_project_md_references_decision_file: the planning-side
   `.planning/PROJECT.md` key-decisions table contains the literal
   substring `.planning/decisions/no-pypi-in-v0.6.md`. Per D-09 and
   RESEARCH.md Pattern 4, the table being appended is the existing
   3-column table at `.planning/PROJECT.md:74-81` (not the top-level
   `PROJECT.md`).

All three production assertions are RED-by-design until Plan 02
lands the decision file and edits `.planning/PROJECT.md`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DECISION_PATH = REPO_ROOT / ".planning" / "decisions" / "no-pypi-in-v0.6.md"
# Per D-09 and RESEARCH.md Pattern 4: the key-decisions table being
# appended is the existing 3-column table inside .planning/PROJECT.md
# (NOT the top-level PROJECT.md). The top-level PROJECT.md is a
# distribution-facing README pointer; the planning-side file owns
# the decision-tracking table.
PROJECT_MD_PATH = REPO_ROOT / ".planning" / "PROJECT.md"

_TERMINATOR_LITERAL = "**Decision (final, until revisited):**"
_DECISION_FILE_REF = ".planning/decisions/no-pypi-in-v0.6.md"


@pytest.fixture(scope="module")
def decision_text() -> str:
    """Load .planning/decisions/no-pypi-in-v0.6.md once, fail loudly if absent."""
    if not DECISION_PATH.is_file():
        pytest.fail(
            f".planning/decisions/no-pypi-in-v0.6.md does not exist. "
            f"SIGN-05 (D-09) requires this decision file. Phase 52 "
            f"Plan 02 must create it. Expected at "
            f"{DECISION_PATH.relative_to(REPO_ROOT)}."
        )
    return DECISION_PATH.read_text(encoding="utf-8")


def test_decision_file_exists(decision_text: str) -> None:
    """SIGN-05 (D-09): the decision file is committed and non-empty."""
    assert decision_text.strip(), (
        ".planning/decisions/no-pypi-in-v0.6.md is empty. SIGN-05 "
        "requires a substantive decision document (≤200 lines per "
        "CONTEXT.md code_context decision-file shape convention)."
    )


def test_decision_file_has_terminator(decision_text: str) -> None:
    """SIGN-05 (CONTEXT.md decision-file convention): contains the terminator literal."""
    assert _TERMINATOR_LITERAL in decision_text, (
        f"Decision file must contain the literal {_TERMINATOR_LITERAL!r} "
        f"block per the decision-file shape convention in CONTEXT.md "
        f"code_context. This is the load-bearing terminator the "
        f"shape contract documents."
    )


def test_project_md_references_decision_file() -> None:
    """SIGN-05 (D-09): the planning-side PROJECT.md table references the decision file path."""
    if not PROJECT_MD_PATH.is_file():
        pytest.fail(
            f".planning/PROJECT.md not found at "
            f"{PROJECT_MD_PATH.relative_to(REPO_ROOT)}. SIGN-05 "
            f"requires this file to host the key-decisions table that "
            f"references the decision file (existing 3-column table "
            f"at .planning/PROJECT.md lines 74-81 per RESEARCH.md "
            f"Pattern 4)."
        )
    project_text = PROJECT_MD_PATH.read_text(encoding="utf-8")
    assert _DECISION_FILE_REF in project_text, (
        f".planning/PROJECT.md key-decisions table must contain a row "
        f"referencing the literal path {_DECISION_FILE_REF!r} per "
        f"SIGN-05 / D-09. The existing 3-column Key Decisions table at "
        f".planning/PROJECT.md lines 74-81 is the precedent shape; "
        f"Plan 02 appends one row that references this decision file."
    )
