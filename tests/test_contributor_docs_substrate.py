"""Phase 55 CONTRIB-01..07 substrate lint.

Lints the contributor-docs + templates substrate landed in Phase 55:
decision files, CODEOWNERS, issue templates, CONTRIBUTING.md refresh,
docs/TRIAGE.md + docs/LABEL-TAXONOMY.md, PROJECT.md key-decisions table.

The contribution gate flipped open on 2026-06-10. The pre-flip
tripwires (PHASE-59-FLIP markers, the closed-status notice blocks)
are inverted: tests now assert the OPEN state and that the closed
prose stays gone.

No em-dashes anywhere (CLAUDE.md HR3).
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

DECISIONS_DIR = REPO_ROOT / ".planning" / "decisions"
EXPECTED_DECISIONS = [
    "no-cla.md",
    "no-stale-bot.md",
    "sigstore-keyless.md",
    "sbom-cyclonedx.md",
    "no-pypi-in-v0.6.md",
]

CODEOWNERS = REPO_ROOT / ".github" / "CODEOWNERS"
ISSUE_TEMPLATES = REPO_ROOT / ".github" / "ISSUE_TEMPLATE"
PR_TEMPLATE = REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"
CONTRIBUTING = REPO_ROOT / "CONTRIBUTING.md"
TRIAGE = REPO_ROOT / "docs" / "TRIAGE.md"
LABEL_TAXONOMY = REPO_ROOT / "docs" / "LABEL-TAXONOMY.md"
PROJECT_MD = REPO_ROOT / ".planning" / "PROJECT.md"


# CONTRIB-07: 5 decision files


def test_all_five_decision_files_exist() -> None:
    missing = [name for name in EXPECTED_DECISIONS if not (DECISIONS_DIR / name).is_file()]
    assert not missing, f"CONTRIB-07: missing decision files: {missing}"


def test_each_decision_file_has_decision_heading() -> None:
    for name in EXPECTED_DECISIONS:
        path = DECISIONS_DIR / name
        text = path.read_text(encoding="utf-8")
        assert "## Decision" in text, f"{name}: must contain '## Decision' heading"


# CONTRIB-04: path-scoped CODEOWNERS, no blanket


def test_codeowners_exists() -> None:
    assert CODEOWNERS.is_file(), "CONTRIB-04: .github/CODEOWNERS must exist"


def test_codeowners_no_blanket_ownership() -> None:
    text = CODEOWNERS.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.strip().startswith("#") or not line.strip():
            continue
        # First whitespace-separated token is the pattern
        parts = line.split()
        if not parts:
            continue
        pattern = parts[0]
        assert pattern != "*", f"CONTRIB-04: blanket '* @Ridou' forbidden; offending line: {line!r}"


def test_codeowners_path_scoped_entries() -> None:
    text = CODEOWNERS.read_text(encoding="utf-8")
    required_paths = [
        "/.github/workflows/",
        "/scripts/release_gate.py",
        "/scripts/verify_release.py",
        "/SECURITY.md",
        "/.planning/",
    ]
    missing = [p for p in required_paths if p not in text]
    assert not missing, f"CONTRIB-04: CODEOWNERS missing path entries: {missing}"


# CONTRIB-03: 3 issue templates


def test_three_issue_templates_exist() -> None:
    for name in ("bug.yml", "feature.yml", "security.yml"):
        path = ISSUE_TEMPLATES / name
        assert path.is_file(), f"CONTRIB-03: {path} must exist"


def test_security_template_redirects_to_ghsa() -> None:
    path = ISSUE_TEMPLATES / "security.yml"
    text = path.read_text(encoding="utf-8")
    assert "/security/advisories/new" in text, (
        "CONTRIB-03: security template must redirect to GHSA private vulnerability reporting"
    )


def test_old_issue_template_names_removed() -> None:
    for name in ("bug_report.yml", "feature_request.yml"):
        path = ISSUE_TEMPLATES / name
        assert not path.is_file(), (
            f"CONTRIB-03: legacy {name} must be removed (renamed to {name.split('_')[0]}.yml)"
        )


# CONTRIB-05: docs/TRIAGE.md


def test_triage_md_exists() -> None:
    assert TRIAGE.is_file(), "CONTRIB-05: docs/TRIAGE.md must exist"


def test_triage_md_documents_cadence() -> None:
    text = TRIAGE.read_text(encoding="utf-8")
    for literal in ("good-first-issue", "Sunday", "2 weeks"):
        assert literal in text, f"CONTRIB-05: TRIAGE.md must mention {literal!r}"


def test_triage_md_mentions_no_stale_bot() -> None:
    text = TRIAGE.read_text(encoding="utf-8")
    assert "actions/stale" in text, (
        "CONTRIB-05: TRIAGE.md must explicitly mention NO actions/stale auto-close"
    )


# CONTRIB-06: docs/LABEL-TAXONOMY.md


def test_label_taxonomy_md_exists() -> None:
    assert LABEL_TAXONOMY.is_file(), "CONTRIB-06: docs/LABEL-TAXONOMY.md must exist"


def test_label_taxonomy_documents_labels() -> None:
    text = LABEL_TAXONOMY.read_text(encoding="utf-8")
    for literal in ("type:bug", "type:feature", "security-update", "good-first-issue", "wontfix"):
        assert literal in text, f"CONTRIB-06: LABEL-TAXONOMY.md must document {literal!r}"


def test_label_taxonomy_has_saved_replies() -> None:
    text = LABEL_TAXONOMY.read_text(encoding="utf-8")
    # Section header + at least 4 saved-reply scenarios
    assert "Saved replies" in text or "saved replies" in text.lower(), (
        "CONTRIB-06: LABEL-TAXONOMY.md must have a Saved replies section"
    )
    for scenario in ("Claim accepted", "Claim conflict", "Missing repro", "Stale-but-real bug"):
        assert scenario in text, (
            f"CONTRIB-06: LABEL-TAXONOMY.md must have saved reply for {scenario!r}"
        )


# CONTRIB-01: CONTRIBUTING.md refresh


def test_contributing_md_phase_59_flip_executed() -> None:
    """The gate flipped 2026-06-10: the staged marker must be gone."""
    text = CONTRIBUTING.read_text(encoding="utf-8")
    assert "PHASE-59-FLIP:" not in text, (
        "CONTRIB-01: the PHASE-59-FLIP staged-marker comment must be removed now that the "
        "contribution gate is open"
    )


def test_contributing_md_declares_open_status() -> None:
    """Post-flip invariant: CONTRIBUTING.md declares contributions open, not closed."""
    text = CONTRIBUTING.read_text(encoding="utf-8")
    assert "Status: open for contributions" in text, (
        "CONTRIBUTING.md must carry the 'Status: open for contributions' heading after the "
        "2026-06-10 gate flip"
    )
    assert "Status: not currently accepting outside contributions" not in text, (
        "The pre-flip closed-status heading must stay deleted after the gate flip"
    )


def test_contributing_md_has_7_day_slo() -> None:
    text = CONTRIBUTING.read_text(encoding="utf-8")
    assert "aim to acknowledge within 7 days" in text.lower(), (
        "CONTRIB-01: CONTRIBUTING.md must declare the 'aim to acknowledge within 7 days' SLO"
    )


def test_contributing_md_has_claim_flow() -> None:
    text = CONTRIBUTING.read_text(encoding="utf-8")
    assert (
        "Comment to claim, maintainer assigns" in text
        or "comment to claim, maintainer assigns" in text.lower()
    ), "CONTRIB-01: CONTRIBUTING.md must document the claim flow"


def test_contributing_md_anti_features() -> None:
    text = CONTRIBUTING.read_text(encoding="utf-8")
    for literal in ("No CLA", "No 24-hour SLA", "No `actions/stale`", "Discord is optional"):
        assert literal in text, f"CONTRIB-01: CONTRIBUTING.md must declare anti-feature {literal!r}"


def test_contributing_md_related_decisions_section() -> None:
    text = CONTRIBUTING.read_text(encoding="utf-8")
    assert "## Related decisions" in text, (
        "CONTRIB-01: CONTRIBUTING.md must contain a 'Related decisions' section"
    )
    for name in EXPECTED_DECISIONS:
        assert f".planning/decisions/{name}" in text, (
            f"CONTRIB-01: CONTRIBUTING.md Related decisions section must link to {name}"
        )


# CONTRIB-07: PROJECT.md key-decisions table refresh


def test_project_md_key_decisions_table_has_all_five() -> None:
    text = PROJECT_MD.read_text(encoding="utf-8")
    for name in EXPECTED_DECISIONS:
        assert f".planning/decisions/{name}" in text, (
            f"CONTRIB-07: .planning/PROJECT.md key-decisions table must reference {name}"
        )


# CONTRIB-02: PR template invariants (post-flip: the closed NOTICE block stays gone)


def test_pr_template_notice_block_removed() -> None:
    """Post-flip invariant: the closed-to-PRs NOTICE block is gone and stays gone."""
    text = PR_TEMPLATE.read_text(encoding="utf-8")
    assert "NOTICE: horus-os is in a solo development phase" not in text, (
        "The PR template's closed-to-PRs NOTICE block must stay deleted after the "
        "2026-06-10 gate flip"
    )
    assert "Thanks for contributing" in text, (
        "The PR template must open with the contributor-welcome comment that replaced "
        "the closed NOTICE block"
    )


def test_pr_template_checklist_complete() -> None:
    """CONTRIB-02: PR template already has tests, docs, CHANGELOG, license-header checklist items."""
    text = PR_TEMPLATE.read_text(encoding="utf-8")
    for literal in (
        "ruff check",
        "ruff format --check",
        "pytest",
        "CHANGELOG.md",
        "No em-dashes",
        "No personal information",
    ):
        assert literal in text, f"CONTRIB-02: PR template missing checklist item {literal!r}"
