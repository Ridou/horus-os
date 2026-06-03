# Phase 55: Contributor docs + templates - Context

**Gathered:** 2026-05-30
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Land all contributor-facing prose with gate-flip-toggle text STAGED for activation in Phase 59. CONTRIBUTING.md rewritten with honest solo-maintainer language. PR template gains a checklist (already there). Three issue templates land. CODEOWNERS path-scoped. `docs/TRIAGE.md` defines label taxonomy. `docs/LABEL-TAXONOMY.md` documents each label. Five rationale files land in `.planning/decisions/`.

</domain>

<canonical_refs>
## Canonical References

- `.planning/REQUIREMENTS.md` (CONTRIB-01..07)
- `.planning/ROADMAP.md` (Phase 55 section)
- `CONTRIBUTING.md` (existing v0.3 era prose; rewrite end-to-end)
- `.github/PULL_REQUEST_TEMPLATE.md` (already has NOTICE block + checklist; minor refresh)
- `.github/ISSUE_TEMPLATE/` (bug_report.yml + feature_request.yml + config.yml exist; rename to bug.yml + feature.yml + add security.yml)
- `.planning/decisions/no-pypi-in-v0.6.md` (Phase 52 D-09; one of the 5 rationale files)
- CLAUDE.md (HR3 no em-dashes; HR1 no PII)

</canonical_refs>

<decisions>
## Implementation Decisions

### Locked by REQUIREMENTS.md and ROADMAP.md (7 requirements)

1. CONTRIBUTING.md rewritten end-to-end: claim flow, branch policy, commit format, test/doc/CHANGELOG/license-header expectations, "aim to acknowledge within 7 days" SLO. Anti-features explicit: NO 24-hour SLA, NO CLA, Discord optional. NOTICE block STAGED with comment marker (CONTRIB-01).
2. `.github/PULL_REQUEST_TEMPLATE.md` checklist already exists; CONTRIB-02 has the file in good shape: tests added, docs updated, CHANGELOG entry, license header on new files. Reference CONTRIBUTING.md + CODE_OF_CONDUCT.md. NOTICE block STAGED for Phase 59 deletion (already in place).
3. `.github/ISSUE_TEMPLATE/`: three forms. Rename existing bug_report.yml -> bug.yml; feature_request.yml -> feature.yml; create security.yml (redirects to GHSA private vulnerability reporting); banners STAGED for Phase 59 flip (CONTRIB-03).
4. `.github/CODEOWNERS` NEW with PATH-SCOPED ownership; NO blanket `* @Ridou` (CONTRIB-04).
5. `docs/TRIAGE.md` NEW: label taxonomy <= 15 labels; good-first-issue rubric; weekly Sunday cadence; "may go silent up to 2 weeks" disclaimer; NO actions/stale (CONTRIB-05).
6. `docs/LABEL-TAXONOMY.md` NEW: label set + when each applies + saved-reply text (CONTRIB-06).
7. `.planning/decisions/` ships 5 rationale files: no-cla.md, no-stale-bot.md, sigstore-keyless.md, sbom-cyclonedx.md, no-pypi-in-v0.6.md (last exists from Phase 52). Referenced from CONTRIBUTING.md + PROJECT.md key-decisions table (CONTRIB-07).

### Claude's Discretion

Exact prose. Reuse existing CONTRIBUTING.md content where unchanged. STAGED markers use HTML comment `<!-- PHASE-59-FLIP: delete this block -->` patterns.

</decisions>

<specifics>
## Specific Constraints

1. AUTONOMOUS RUN RULE: must NOT modify the NOTICE block in PR template or "(not active yet)" in SECURITY.md or "Project status" / banner texts. Those are Phase 59 atomic flip commit territory. We STAGE comment markers but do NOT delete.
2. CLAUDE.md HR3: no em-dashes in any prose.
3. CLAUDE.md HR1: no PII other than the existing `Ridou/horus-os` GitHub handle/repo reference.

</specifics>

<deferred>
## Deferred Ideas

`docs/MAINTAINER-RUNBOOK.md` is Phase 56 territory; CONTRIBUTING.md may forward-reference it.

</deferred>
