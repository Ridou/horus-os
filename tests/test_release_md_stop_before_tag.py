"""SIGN-03 (Phase 52 Wave 0 RED-by-design): docs/RELEASE.md STOP-BEFORE-TAG prose lint.

Three production assertions cover SIGN-03 per VALIDATION.md row 3:

1. test_step_6_5_gitsign_inserted: a new step 6.5 referencing
   `git config --get gitsign.connectorID` is inserted BETWEEN
   existing step 6 (CI green confirmation) and existing step 7
   (the tag invocation). The step references
   `docs/MAINTAINER-RUNBOOK.md` (Phase 56 forward reference is
   acceptable per CONTEXT.md specifics).
2. test_step_7_uses_tag_dash_s: step 7 swaps the literal command
   from `git tag -a vN.M.P -m "vN.M.P - <milestone-name>"` to
   `git tag -s vN.M.P -m "vN.M.P - <milestone-name>"`. The `-s`
   flag tells git to invoke the configured signer (gitsign when
   `gitsign.connectorID` is set).
3. test_steps_1_through_6_and_8_through_9_byte_identical: the
   pre-edit prose for steps 1-6 (current `docs/RELEASE.md:122-141`)
   and steps 8-9 (current `docs/RELEASE.md:145-157`) remains
   byte-identical to the pinned baseline. Insertions allowed,
   mutations not (D-05; Phase 51 D-06 precedent;
   ARCHITECTURE.md byte-identity invariant for the STOP-BEFORE-TAG
   block).

All three production assertions are RED-by-design until Plan 02
edits `docs/RELEASE.md`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
RELEASE_MD_PATH = REPO_ROOT / "docs" / "RELEASE.md"


# Byte-identity baseline: the verbatim text of release-procedure
# steps 1 through 6 (Phase 52 D-05 / Phase 51 D-06 invariant; the
# check count in step 2 was updated from eight to fifteen when the
# release gate grew to 15 checks). Step 6.5 is inserted AFTER this
# block and BEFORE the step 7 line; this baseline must remain
# present verbatim in the file.
PRE_EDIT_STEPS_1_THROUGH_6 = (
    "1. Refresh `pricing.json` if its `updated_at` is older than 14\n"
    "   days (per the refreshing-pricing section above).\n"
    "1b. Regenerate `docs/manifest-v1.schema.json` via\n"
    "   `python scripts/build_manifest_schema.py` and commit the result\n"
    "   if there is a diff. The `docs-drift` gate refuses to tag\n"
    "   otherwise.\n"
    "2. Run `python scripts/release_gate.py`. Confirm exit 0 and all\n"
    "   fifteen checks pass.\n"
    "3. Bump the version to `N.M.P` in TWO places:\n"
    '   - `pyproject.toml` line 7: `version = "N.M.P"`.\n'
    '   - `src/horus_os/__init__.py`: `__version__ = "N.M.P"`.\n'
    "4. Promote `[Unreleased]` in `CHANGELOG.md` to\n"
    "   `[N.M.P] - YYYY-MM-DD` (Keep a Changelog 1.1.0 format with\n"
    "   Added / Changed / Fixed / Deprecated / Removed / Security\n"
    "   sections as applicable). Leave a fresh empty `[Unreleased]`\n"
    "   stub at the top for the next cycle.\n"
    "5. Commit the version bump and CHANGELOG promotion:\n"
    "   `chore(release): bump to N.M.P`.\n"
    "6. Push to `main`. Wait for CI green on the full 3-OS x 2-Python\n"
    "   matrix (`gh run list --branch main --limit 1`).\n"
)


# Byte-identity baseline: steps 8 and 9 from current docs/RELEASE.md
# lines 145-157. Plan 02 modifies step 7 (in between) but MUST NOT
# touch steps 8 or 9.
PRE_EDIT_STEPS_8_THROUGH_9 = (
    "8. Publish the GitHub Release. Extract the new CHANGELOG section\n"
    "   into a tmp file and hand it to `gh release create`:\n"
    "   ```\n"
    "   awk '/^## \\[N.M.P\\]/,/^## \\[/{print}' CHANGELOG.md | sed '$d' > /tmp/release-notes.md\n"
    "   gh release create vN.M.P \\\n"
    '     --title "vN.M.P - <milestone-name>" \\\n'
    "     --notes-file /tmp/release-notes.md\n"
    "   ```\n"
    "   If the awk extraction is fragile for this milestone, paste the\n"
    "   CHANGELOG section manually. Include a link to the migration\n"
    "   doc (`docs/MIGRATION-vX.Y-to-vN.M.md`) if one exists.\n"
    "9. Confirm the release is visible at\n"
    "   `https://github.com/Ridou/horus-os/releases/tag/vN.M.P`.\n"
)


# Load-bearing literals the production assertions grep for.
_GITSIGN_PREFLIGHT_LITERAL = "git config --get gitsign.connectorID"
_TAG_DASH_S_LITERAL = 'git tag -s vN.M.P -m "vN.M.P - <milestone-name>"'
_TAG_DASH_A_LITERAL = 'git tag -a vN.M.P -m "vN.M.P - <milestone-name>"'
_RUNBOOK_LITERAL = "docs/MAINTAINER-RUNBOOK.md"


@pytest.fixture(scope="module")
def release_text() -> str:
    """Load docs/RELEASE.md once per module, fail loudly if absent."""
    if not RELEASE_MD_PATH.is_file():
        pytest.fail(
            "docs/RELEASE.md does not exist. SIGN-03 cannot be evaluated "
            "without the source-of-truth release procedure document."
        )
    return RELEASE_MD_PATH.read_text(encoding="utf-8")


def test_step_6_5_gitsign_inserted(release_text: str) -> None:
    """SIGN-03 (D-05): step 6.5 references the gitsign pre-flight check.

    Asserts the literal `git config --get gitsign.connectorID` is in
    the doc AND positioned AFTER the pre-edit steps 1-6 block AND
    BEFORE the new `git tag -s` literal AND references the runbook
    file Phase 56 will land.
    """
    assert _GITSIGN_PREFLIGHT_LITERAL in release_text, (
        f"docs/RELEASE.md must insert step 6.5 referencing the literal "
        f"{_GITSIGN_PREFLIGHT_LITERAL!r} between current steps 6 and 7 "
        f"(SIGN-03 / D-05). Plan 02 lands this insertion."
    )
    pre_edit_index = release_text.find(PRE_EDIT_STEPS_1_THROUGH_6)
    gitsign_index = release_text.find(_GITSIGN_PREFLIGHT_LITERAL)
    tag_dash_s_index = release_text.find(_TAG_DASH_S_LITERAL)
    assert pre_edit_index != -1, (
        "Cannot locate the pre-edit steps 1-6 baseline in "
        "docs/RELEASE.md; the byte-identity invariant for the "
        "STOP-BEFORE-TAG block must hold (D-05; Phase 51 D-06)."
    )
    assert gitsign_index > pre_edit_index, (
        "The gitsign pre-flight literal must appear AFTER the "
        "pre-edit steps 1-6 block (SIGN-03 / D-05). Got "
        f"gitsign_index={gitsign_index}, pre_edit_index={pre_edit_index}."
    )
    if tag_dash_s_index != -1:
        assert gitsign_index < tag_dash_s_index, (
            "The gitsign pre-flight literal must appear BEFORE the "
            "'git tag -s' literal (SIGN-03 / D-05). Got "
            f"gitsign_index={gitsign_index}, "
            f"tag_dash_s_index={tag_dash_s_index}."
        )
    assert _RUNBOOK_LITERAL in release_text, (
        f"Step 6.5 must reference {_RUNBOOK_LITERAL!r} so the maintainer "
        f"reading RELEASE.md knows where to find the one-time gitsign "
        f"setup procedure (SIGN-03 / D-05; Phase 56 forward reference "
        f"is acceptable per CONTEXT.md specifics)."
    )


def test_step_7_uses_tag_dash_s(release_text: str) -> None:
    """SIGN-03 (D-05): step 7 swaps `git tag -a` to `git tag -s` verbatim."""
    assert _TAG_DASH_S_LITERAL in release_text, (
        f"docs/RELEASE.md step 7 must use the literal "
        f"{_TAG_DASH_S_LITERAL!r} (SIGN-03 / D-05). The `-s` flag "
        f"delegates signing to gitsign when `gitsign.connectorID` is "
        f"set."
    )
    assert _TAG_DASH_A_LITERAL not in release_text, (
        f"docs/RELEASE.md still contains the pre-edit literal "
        f"{_TAG_DASH_A_LITERAL!r}. Plan 02 must replace it with the "
        f"`-s` form (SIGN-03 / D-05; insertions allowed, mutations not, "
        f"but THIS literal IS the mutation Plan 02 must make)."
    )


def test_steps_1_through_6_and_8_through_9_byte_identical(release_text: str) -> None:
    """SIGN-03 (D-05; Phase 51 D-06): pre-edit baselines remain byte-identical.

    Insertions allowed, mutations not. The pre-edit prose for steps
    1-6 and steps 8-9 MUST remain present verbatim in the post-edit
    file (Phase 51 D-06 + ARCHITECTURE.md byte-identity invariant).
    """
    assert PRE_EDIT_STEPS_1_THROUGH_6 in release_text, (
        "Pre-edit steps 1-6 are NOT present verbatim in "
        "docs/RELEASE.md. Plan 02 must INSERT step 6.5 after this "
        "block; insertions allowed, mutations not (Phase 51 D-06 + "
        "Phase 52 D-05)."
    )
    assert PRE_EDIT_STEPS_8_THROUGH_9 in release_text, (
        "Pre-edit steps 8-9 are NOT present verbatim in "
        "docs/RELEASE.md. Plan 02 must NOT modify steps 8 or 9; "
        "insertions allowed, mutations not (Phase 51 D-06 + "
        "Phase 52 D-05)."
    )
