"""CIHARD-02 + CIHARD-03: structural workflow hardening assertions.

Three structural checks against every .github/workflows/*.yml:

1. Top-level `permissions:` key is present (CIHARD-02).
2. Every `actions/checkout` step sets `persist-credentials: false`
   (CIHARD-03 first clause).
3. No `${{ github.event.* }}`, `${{ github.head_ref }}`, or
   `${{ github.base_ref }}` interpolation appears in any `run:`
   shell line (CIHARD-03 second clause).

These checks complement actionlint:
  - actionlint validates the contents of a `permissions:` block but
    does not flag absence; check (1) plugs that gap.
  - actionlint has no `persist-credentials` rule; check (2) plugs that.
  - actionlint's `expression` rule catches (3); check (3) is
    defense-in-depth against the rule being disabled by a
    `# actionlint:` ignore comment AND extends the surface to the
    github.head_ref/github.base_ref aliases that actionlint does NOT
    flag by default, per RESEARCH.md OQ-3 RESOLVED and PITFALLS.md
    Pitfall 1 documented threat model.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

# Matches `permissions:` at column 0 (workflow-level, not job-level).
# Job-level permissions are indented; this regex specifically rejects them.
_TOP_LEVEL_PERMISSIONS = re.compile(r"^permissions:\s*", re.MULTILINE)

# Matches a `uses: actions/checkout@...` line. Captures the leading
# whitespace (group 1) so we can scan the following `with:` block for
# persist-credentials.
_CHECKOUT_USES = re.compile(
    r"^(\s*)-?\s*uses:\s*actions/checkout@\S+",
    re.MULTILINE,
)

# Matches github.event.*, github.head_ref, or github.base_ref inside a
# ${{ ... }} expression. Per Open Question 3 RESOLVED: head_ref/base_ref
# aliases are in scope (PITFALLS.md Pitfall 1). The extended form covers:
#   - github.event.<any.nested.path> (Ultralytics CVE vector)
#   - github.head_ref (short alias for github.event.pull_request.head.ref)
#   - github.base_ref (short alias for github.event.pull_request.base.ref)
# Word boundaries (\b) on both ends prevent substring false positives.
_EVENT_INTERPOLATION = re.compile(
    r"\$\{\{\s*[^}]*\b(?:github\.event\.[a-zA-Z0-9_.\[\]'\"]+"
    r"|github\.head_ref|github\.base_ref)\b"
)


def _workflow_yaml_files() -> list[Path]:
    return sorted(WORKFLOWS_DIR.glob("*.yml"))


def _find_workflows_missing_top_level_permissions(workflows_dir: Path) -> list[Path]:
    """Return paths of workflows that lack a column-0 `permissions:` line."""
    offenders: list[Path] = []
    for workflow in sorted(workflows_dir.glob("*.yml")):
        text = workflow.read_text(encoding="utf-8")
        if not _TOP_LEVEL_PERMISSIONS.search(text):
            offenders.append(workflow)
    return offenders


def _find_checkouts_without_persist_credentials(
    workflows_dir: Path,
) -> list[tuple[Path, int]]:
    """Return (path, line_number) for every actions/checkout without persist-credentials: false."""
    offenders: list[tuple[Path, int]] = []
    for workflow in sorted(workflows_dir.glob("*.yml")):
        text = workflow.read_text(encoding="utf-8")
        for match in _CHECKOUT_USES.finditer(text):
            uses_line_start = match.start()
            # Search the next ~15 lines after the uses: line for the
            # `with: persist-credentials: false` block; checkout `with:`
            # blocks immediately follow the uses: line by convention.
            after = text[uses_line_start:]
            lookahead = "\n".join(after.splitlines()[:15])
            if "persist-credentials: false" not in lookahead:
                line_number = text[:uses_line_start].count("\n") + 1
                offenders.append((workflow, line_number))
    return offenders


def _find_event_interpolation_in_run_shells(
    workflows_dir: Path,
) -> list[tuple[Path, int, str]]:
    """Return (path, line_number, line_text) for run: shell lines with event interpolation.

    Scans github.event.*, github.head_ref, and github.base_ref expressions.
    Comment-only lines (stripped line starts with '#') are skipped per the
    comment-skip discipline from scripts/lint_no_wallclock.py line 90.
    """
    offenders: list[tuple[Path, int, str]] = []
    for workflow in sorted(workflows_dir.glob("*.yml")):
        text = workflow.read_text(encoding="utf-8")
        in_run_block = False
        run_block_indent = -1
        for line_number, raw_line in enumerate(text.splitlines(), start=1):
            # Skip pure comment lines so workflow documentation comments
            # mentioning ${{ github.event.* }} examples are not flagged.
            stripped = raw_line.strip()
            if stripped.startswith("#"):
                continue
            stripped_left = raw_line.lstrip()
            current_indent = len(raw_line) - len(stripped_left)
            # Detect the start of a `run: |` or `run: >` multi-line block.
            if re.match(r"^\s*-?\s*run:\s*[|>]", raw_line):
                in_run_block = True
                run_block_indent = current_indent
                continue
            # Detect a single-line `run: <command>` form.
            single_line_run = re.match(r"^\s*-?\s*run:\s*(.+)", raw_line)
            if single_line_run and not raw_line.rstrip().endswith(("|", ">")):
                if _EVENT_INTERPOLATION.search(single_line_run.group(1)):
                    offenders.append((workflow, line_number, raw_line.rstrip()))
                in_run_block = False
                continue
            # Inside a multi-line run block, lines are content until the
            # indentation drops to <= the run: key's indent.
            if in_run_block:
                if stripped_left == "" or current_indent <= run_block_indent:
                    in_run_block = False
                    continue
                if _EVENT_INTERPOLATION.search(raw_line):
                    offenders.append((workflow, line_number, raw_line.rstrip()))
    return offenders


# ---------------------------------------------------------------------------
# Production tests (expected RED in Wave 0; Plan 02 turns them GREEN)
# ---------------------------------------------------------------------------


def test_permissions_read_all_on_every_workflow() -> None:
    """CIHARD-02: every workflow has a top-level `permissions:` key."""
    raw_offenders = _find_workflows_missing_top_level_permissions(WORKFLOWS_DIR)
    offenders = [p.relative_to(REPO_ROOT) for p in raw_offenders]
    assert not offenders, (
        "Workflows without a top-level `permissions:` block (CIHARD-02):\n"
        + "\n".join(f"  {p}" for p in offenders)
        + "\nAdd `permissions: read-all` to the top of every workflow above `jobs:`."
    )


def test_persist_credentials_false_on_every_checkout() -> None:
    """CIHARD-03: every actions/checkout step has persist-credentials: false."""
    raw_offenders = _find_checkouts_without_persist_credentials(WORKFLOWS_DIR)
    offenders = [(p.relative_to(REPO_ROOT), ln) for p, ln in raw_offenders]
    assert not offenders, (
        "actions/checkout without persist-credentials: false (CIHARD-03):\n"
        + "\n".join(f"  {p}:{ln}" for p, ln in offenders)
        + "\nAdd `with:\\n  persist-credentials: false` to every actions/checkout step."
    )


def test_no_event_interpolation_in_shells() -> None:
    """CIHARD-03: no ${{ github.event.* }}, ${{ github.head_ref }}, or ${{ github.base_ref }}
    interpolation in run: shell lines. PITFALLS.md Pitfall 1 documents the head_ref/base_ref
    aliases as in-scope threat surface. The rule covers github.event.*, github.head_ref,
    and github.base_ref in a single non-capturing alternation."""
    raw_offenders = _find_event_interpolation_in_run_shells(WORKFLOWS_DIR)
    offenders = [(p.relative_to(REPO_ROOT), ln, txt) for p, ln, txt in raw_offenders]
    assert not offenders, (
        "${{ github.event.* }} interpolation in run: shell (CIHARD-03):\n"
        + "\n".join(f"  {p}:{ln}: {txt}" for p, ln, txt in offenders)
        + "\nPass the value via env: instead; see PITFALLS.md Pitfall 1."
    )


# ---------------------------------------------------------------------------
# Non-vacuity tests (synthetic fixtures; all must PASS in Wave 0)
# ---------------------------------------------------------------------------


def test_scanner_catches_synthetic_missing_permissions(tmp_path: Path) -> None:
    """Non-vacuity for CIHARD-02: the scanner flags a workflow with no top-level permissions.

    A synthetic workflow under tmp_path has no permissions: block. The
    helper must report exactly one offender, proving the regex is non-vacuous.
    """
    fake_wf_dir = tmp_path / ".github" / "workflows"
    fake_wf_dir.mkdir(parents=True)
    (fake_wf_dir / "fake.yml").write_text(
        "name: Test\non:\n  push:\n    branches: [main]\njobs:\n  test:\n    runs-on: ubuntu-latest\n",
        encoding="utf-8",
    )
    offenders = _find_workflows_missing_top_level_permissions(fake_wf_dir)
    assert len(offenders) == 1, (
        f"Expected exactly one offender for missing permissions; got {len(offenders)}: {offenders}"
    )


def test_scanner_catches_synthetic_checkout_without_persist_credentials(
    tmp_path: Path,
) -> None:
    """Non-vacuity for CIHARD-03 first clause: the scanner flags a checkout without persist-credentials.

    A synthetic workflow under tmp_path has an actions/checkout step with an
    empty `with:` block. The helper must report exactly one offender.
    """
    fake_wf_dir = tmp_path / ".github" / "workflows"
    fake_wf_dir.mkdir(parents=True)
    (fake_wf_dir / "fake.yml").write_text(
        "steps:\n"
        "  - name: Checkout\n"
        "    uses: actions/checkout@abc123def456abc123def456abc123def456abc123def\n"
        "    with:\n"
        "      fetch-depth: 0\n",
        encoding="utf-8",
    )
    offenders = _find_checkouts_without_persist_credentials(fake_wf_dir)
    assert len(offenders) == 1, (
        f"Expected exactly one offender for checkout without persist-credentials; "
        f"got {len(offenders)}: {offenders}"
    )


def test_scanner_catches_synthetic_event_interpolation(tmp_path: Path) -> None:
    """Non-vacuity for CIHARD-03 second clause (github.event.* branch).

    A synthetic workflow under tmp_path has a run: step with a
    ${{ github.event.pull_request.title }} interpolation. The helper must
    report exactly one offender, proving the github.event.* branch fires.
    """
    fake_wf_dir = tmp_path / ".github" / "workflows"
    fake_wf_dir.mkdir(parents=True)
    (fake_wf_dir / "fake.yml").write_text(
        "steps:\n  - name: Bad step\n    run: echo ${{ github.event.pull_request.title }}\n",
        encoding="utf-8",
    )
    offenders = _find_event_interpolation_in_run_shells(fake_wf_dir)
    assert len(offenders) == 1, (
        f"Expected exactly one offender for event interpolation; got {len(offenders)}: {offenders}"
    )


def test_scanner_catches_synthetic_head_ref_interpolation(tmp_path: Path) -> None:
    """Non-vacuity for CIHARD-03 second clause (head_ref alias branch, per OQ-3 RESOLVED).

    A synthetic workflow under tmp_path has a run: | block containing
    ${{ github.head_ref }}. The helper must report exactly one offender,
    proving the github.head_ref alternative in _EVENT_INTERPOLATION fires.
    Without this test, the head_ref/base_ref alternative would be silently
    untested even though the regex contains it.
    """
    fake_wf_dir = tmp_path / ".github" / "workflows"
    fake_wf_dir.mkdir(parents=True)
    (fake_wf_dir / "fake.yml").write_text(
        "steps:\n  - name: Bad step\n    run: |\n      echo ${{ github.head_ref }}\n",
        encoding="utf-8",
    )
    offenders = _find_event_interpolation_in_run_shells(fake_wf_dir)
    assert len(offenders) == 1, (
        f"Expected exactly one offender for head_ref interpolation; got {len(offenders)}: {offenders}"
    )
