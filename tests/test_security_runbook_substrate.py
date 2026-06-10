"""Phase 56 SECDISC + RUNBOOK + DISCGH-01 substrate lint.

Lints the SECURITY.md refresh, docs/MAINTAINER-RUNBOOK.md, the rollback
template, and the docs/RELEASE.md repo-settings checklist additions.

The contribution gate flipped open on 2026-06-10. The pre-flip
tripwires (the PHASE-59-FLIP marker and the "(not active yet)" block)
are inverted: tests now assert the live contributor-pipeline section
and the current supported-versions window.

No em-dashes anywhere (CLAUDE.md HR3).
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SECURITY_MD = REPO_ROOT / "SECURITY.md"
RUNBOOK = REPO_ROOT / "docs" / "MAINTAINER-RUNBOOK.md"
ROLLBACK = REPO_ROOT / ".planning" / "rollback" / "flip-gate-revert.md"
RELEASE_MD = REPO_ROOT / "docs" / "RELEASE.md"


# SECDISC-01..03


def test_security_md_phase_59_flip_executed() -> None:
    """The gate flipped 2026-06-10: the staged marker must be gone."""
    text = SECURITY_MD.read_text(encoding="utf-8")
    assert "PHASE-59-FLIP" not in text, (
        "SECDISC-01: the PHASE-59-FLIP staged-marker comment must be removed now that the "
        "contribution gate is open"
    )


def test_security_md_contributor_pipeline_live() -> None:
    """Post-flip invariant: the contributor-pipeline section is live, not '(not active yet)'."""
    text = SECURITY_MD.read_text(encoding="utf-8")
    assert "Contributor-pipeline security (not active yet)" not in text, (
        "The '(not active yet)' framing must stay deleted after the 2026-06-10 gate flip"
    )
    assert "## Contributor-pipeline security" in text, (
        "SECURITY.md must keep a live 'Contributor-pipeline security' section describing the "
        "fork-PR token restrictions and CI-before-review gate"
    )


def test_security_md_severity_slos() -> None:
    text = SECURITY_MD.read_text(encoding="utf-8")
    for literal in ("Severity", "14 days", "30 days", "90 days"):
        assert literal in text, f"SECDISC-02: SECURITY.md missing {literal!r}"


def test_security_md_ack_within_7_days() -> None:
    text = SECURITY_MD.read_text(encoding="utf-8")
    assert "within 7 days" in text, "SECDISC-02: SECURITY.md must declare ack within 7 days"


def test_security_md_over_capacity_language() -> None:
    text = SECURITY_MD.read_text(encoding="utf-8")
    assert "security-update" in text, (
        "SECDISC-02: SECURITY.md must declare the over-capacity escalation label"
    )
    assert "security-update-followup" not in text, (
        "SECDISC-02: the escalation label is the taxonomy's 'security-update' "
        "(docs/LABEL-TAXONOMY.md hard cap of 15); 'security-update-followup' does not exist"
    )


def test_security_md_supported_versions() -> None:
    text = SECURITY_MD.read_text(encoding="utf-8")
    for literal in ("0.8.x", "0.7.x", "< 0.7"):
        assert literal in text, (
            f"SECDISC-03: SECURITY.md supported-versions table missing {literal!r}"
        )


def test_security_md_rehearsal_ghsa_ritual() -> None:
    text = SECURITY_MD.read_text(encoding="utf-8")
    assert "rehearsal GitHub Security Advisory" in text or "rehearsal GHSA" in text, (
        "SECDISC-03: SECURITY.md must document the rehearsal-advisory ritual"
    )


# RUNBOOK-01


def test_runbook_exists() -> None:
    assert RUNBOOK.is_file(), "RUNBOOK-01: docs/MAINTAINER-RUNBOOK.md must exist"


def test_runbook_release_procedure_section() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    for literal in (
        "gitsign.connectorID",
        "git tag -s",
        "release.yml",
        "attest-build-provenance",
        "attest-sbom",
    ):
        assert literal in text, (
            f"RUNBOOK-01: MAINTAINER-RUNBOOK release procedure missing {literal!r}"
        )


def test_runbook_post_flip_playbook_section() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    for literal in ("Freeze triggers", "Throttle triggers", "Burnout triggers", "decision matrix"):
        assert literal in text, (
            f"RUNBOOK-01: MAINTAINER-RUNBOOK post-flip playbook missing {literal!r}"
        )


# RUNBOOK-02


def test_rollback_template_exists() -> None:
    assert ROLLBACK.is_file(), "RUNBOOK-02: .planning/rollback/flip-gate-revert.md must exist"


def test_rollback_template_documents_method() -> None:
    text = ROLLBACK.read_text(encoding="utf-8")
    for literal in ("git revert", "git apply", "issue-claim-watcher.yml"):
        assert literal in text, f"RUNBOOK-02: rollback template missing {literal!r}"


# SECDISC-04 + DISCGH-01: repo-settings checklist


def test_release_md_repo_settings_checklist() -> None:
    text = RELEASE_MD.read_text(encoding="utf-8")
    assert "One-time repo settings checklist" in text, (
        "SECDISC-04: docs/RELEASE.md must contain 'One-time repo settings checklist' section"
    )


def test_release_md_settings_use_gh_api() -> None:
    text = RELEASE_MD.read_text(encoding="utf-8")
    # The checklist must include at least 3 gh api commands for the verifiable toggles
    count = text.count("gh api")
    assert count >= 3, (
        f"SECDISC-04: docs/RELEASE.md checklist must include >= 3 gh api commands; got {count}"
    )


def test_release_md_private_vuln_reporting_documented() -> None:
    text = RELEASE_MD.read_text(encoding="utf-8")
    assert "private_vulnerability_reporting" in text, (
        "SECDISC-04: repo-settings checklist must reference private_vulnerability_reporting"
    )


def test_release_md_discussions_documented() -> None:
    text = RELEASE_MD.read_text(encoding="utf-8")
    assert "has_discussions" in text, (
        "DISCGH-01: repo-settings checklist must document Discussions enabling"
    )


def test_runbook_discussions_categories() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    for literal in ("General", "Q&A", "Show and Tell", "Ideas"):
        assert literal in text, (
            f"DISCGH-01: MAINTAINER-RUNBOOK must define Discussions category {literal!r}"
        )
