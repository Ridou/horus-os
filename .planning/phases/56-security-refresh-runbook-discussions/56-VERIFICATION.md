---
phase: 56-security-refresh-runbook-discussions
verified: 2026-05-30T00:00:00Z
status: human_needed
score: 7/7 requirements verified
overrides_applied: 0
human_verification:
  - test: "git apply --check on .planning/rollback/flip-gate-revert.patch against a stale working tree"
    expected: "Phase 58 rehearsal generates the inverse patch from the planned Phase 59 flip and verifies `git apply --check` exits 0; after applying, the working tree matches the pre-flip state file-for-file."
    why_human: "RUNBOOK-02 second clause requires the rollback template to be `git apply`-tested as part of the Phase 58 release rehearsal. Phase 56 ships the template; Phase 58 generates and applies the inverse patch. Cannot run in CI today because the Phase 59 atomic flip commit does not exist yet."
  - test: "One-time GitHub repo settings: enable private vulnerability reporting, Dependabot alerts + security updates, secret scanning + push protection, Discussions"
    expected: "All toggles enabled per docs/RELEASE.md `One-time repo settings checklist`; verify via the listed `gh api` commands; create the four Discussions categories (General, Q&A, Show and Tell, Ideas) via the Settings UI."
    why_human: "Requires repo-admin token at the live `Ridou/horus-os` repo; cannot run in CI. One-time setup before Phase 59 v0.6.0 ship."
---

# Phase 56: SECURITY refresh + Runbook + Discussions Verification Report

**Phase Goal:** Refresh SECURITY.md, land MAINTAINER-RUNBOOK, ship rollback template, document repo-settings checklist + Discussions enabling.

**Verified:** 2026-05-30
**Status:** human_needed (2 items deferred to Phase 58 rehearsal + maintainer one-time settings work)

## Requirements Coverage

| # | Requirement | Status |
|---|-------------|--------|
| 1 | SECDISC-01: PHASE-59-FLIP staged marker; "(not active yet)" preserved | VERIFIED |
| 2 | SECDISC-02: severity-tier SLOs (7d ack; critical 14d/high 30d/medium 90d) + over-capacity escalation | VERIFIED |
| 3 | SECDISC-03: supported-versions covers v0.5.x + v0.6.x; rehearsal-GHSA ritual | VERIFIED |
| 4 | SECDISC-04: docs/RELEASE.md one-time repo-settings checklist with gh api commands | VERIFIED (3 human UAT item: live settings toggle on the repo) |
| 5 | RUNBOOK-01: MAINTAINER-RUNBOOK release procedure + post-flip operational playbook | VERIFIED |
| 6 | RUNBOOK-02: rollback template exists | VERIFIED (git apply test deferred to Phase 58 rehearsal) |
| 7 | DISCGH-01: Discussions enabling documented + 4 categories named | VERIFIED |

## Quality Gates

- pytest tests/test_security_runbook_substrate.py reports 17 passed
- ruff clean on the test file
- em-dash scan: empty on all 5 touched files (SECURITY.md, docs/MAINTAINER-RUNBOOK.md, docs/RELEASE.md, .planning/rollback/flip-gate-revert.md, tests/test_security_runbook_substrate.py)
- existing SECURITY.md "(not active yet)" block PRESERVED (autonomous-run rule)
- no modifications to README.md, STATUS.md, ROADMAP.md

## Human UAT (2 carry-forward items)

1. **Rollback template git-apply test** (Phase 58 rehearsal owns this; we ship the template now).
2. **One-time repo settings** (live admin work on Ridou/horus-os):
   - Enable private vulnerability reporting
   - Enable Dependabot alerts + security updates
   - Enable secret scanning + push protection
   - Enable Discussions + create 4 categories (General, Q&A, Show and Tell, Ideas)
