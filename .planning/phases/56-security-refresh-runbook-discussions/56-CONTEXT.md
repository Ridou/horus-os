# Phase 56: SECURITY refresh + Runbook + Discussions - Context

**Gathered:** 2026-05-30
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped)

<domain>
## Phase Boundary

Refresh SECURITY.md disclosure flow with severity-tier SLOs and over-capacity language. Land `docs/MAINTAINER-RUNBOOK.md` as the single doc covering BOTH v0.6.0 release procedure AND post-flip operational playbook. Append one-time repo settings checklist to `docs/RELEASE.md`. Ship the rollback template. Document the GitHub Discussions enabling step.

</domain>

<canonical_refs>
## Canonical References

- `.planning/REQUIREMENTS.md` (SECDISC-01..04, RUNBOOK-01..02, DISCGH-01)
- `.planning/ROADMAP.md` (Phase 56)
- `SECURITY.md` (existing solo-maintenance text)
- `docs/RELEASE.md` (Phase 52 step 6.5 references docs/MAINTAINER-RUNBOOK.md)
- `.planning/phases/52-signing-substrate-release-yml-new/52-CONTEXT.md` (Phase 52 forward-references MAINTAINER-RUNBOOK as Phase 56 territory)
- CLAUDE.md (HR1 no PII; HR3 no em-dashes)

</canonical_refs>

<decisions>
## Implementation Decisions (7 requirements)

1. SECDISC-01: SECURITY.md "(not active yet)" section STAGED for Phase 59 deletion with comment marker; replacement active vulnerability-disclosure flow drafted in-place pointing at GHSA private reporting. Do NOT DELETE the existing paragraph.
2. SECDISC-02: Severity-tier SLOs in SECURITY.md: ack 7 days; critical 14d, high 30d, medium 90d, low no commitment; coordinated disclosure 90d default; over-capacity language explicit.
3. SECDISC-03: Supported-versions table covers v0.5.x and v0.6.x; clear retirement policy; "we publish at least one rehearsal GHSA" ritual documented.
4. SECDISC-04 + DISCGH-01: One-time GitHub repo settings checklist appended to docs/RELEASE.md: enable private vulnerability reporting, Dependabot alerts + security updates, secret scanning + push protection, Discussions. Each item has a `gh api` verification command.
5. RUNBOOK-01: NEW single docs/MAINTAINER-RUNBOOK.md covers both v0.6.0 release procedure AND post-flip operational playbook (freeze triggers, throttle triggers, burnout triggers, "is this PR worth my time?" decision matrix).
6. RUNBOOK-02: .planning/rollback/flip-gate-revert.md one-commit revert template; git apply-tested as part of Phase 58 rehearsal (we ship the template here, Phase 58 tests it).
7. DISCGH-01: GitHub Discussions enabling = one-time repo settings step documented in MAINTAINER-RUNBOOK.md; categories defined (General, Q&A, Show and Tell, Ideas). The pinned "Project Status" Discussion post is created at v0.6.0 ship as Phase 59 work (DISCGH-02 = Phase 59 territory).

</decisions>

<specifics>
## Specific Constraints

1. AUTONOMOUS RUN RULE: must NOT delete the existing "(not active yet)" SECURITY.md section. STAGE the marker only.
2. CLAUDE.md HR3: no em-dashes.

</specifics>

<deferred>
## Deferred Ideas

DISCGH-02 (pinned Discussion post) is Phase 59 territory.
The flip-gate-revert.md `git apply` test is Phase 58 territory.

</deferred>
