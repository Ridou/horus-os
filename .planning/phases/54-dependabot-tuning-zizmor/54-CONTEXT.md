# Phase 54: Dependabot tuning + zizmor - Context

**Gathered:** 2026-05-30
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Configure Dependabot v2 for both `pip` and `github-actions` ecosystems with security-updates explicitly UN-grouped so CVE PRs never hide inside weekly grouped bumps. Add `zizmor` static-analysis workflow as a second layer of workflow-security enforcement complementing `actionlint`.

</domain>

<canonical_refs>
## Canonical References

- `.planning/REQUIREMENTS.md` (DEPBOT-01, DEPBOT-02, DEPBOT-03)
- `.planning/ROADMAP.md` (Phase 54 section)
- `.planning/STATE.md` (load-bearing constraints)
- `CLAUDE.md` (project hard rules)
- `.github/workflows/ci.yml` (Phase 51 actionlint job is the existing layer this complements)
- `.github/workflows/audit.yml` (Phase 53; Dependabot github-actions covers its uses: lines)
- `.github/workflows/release.yml` (Phase 52 + 53; Dependabot covers its uses: lines)
- `pyproject.toml` (Dependabot pip groups bucket the existing extras)

</canonical_refs>

<decisions>
## Implementation Decisions

### Locked by REQUIREMENTS.md and ROADMAP.md

1. `.github/dependabot.yml` v2 with `package-ecosystem: pip` configured with four groups: `ai-sdks` (anthropic + google-genai to silence dual-SDK churn), `otel`, `web-stack`, `dev-tools`; cooldown 3 days default, 14 days majors; `applies-to: version-updates` on every group (DEPBOT-01).
2. `.github/dependabot.yml` also configures `package-ecosystem: github-actions` for SHA-pin refresh on a weekly cadence (DEPBOT-01).
3. Security updates explicitly UN-grouped: NO `applies-to: security-updates` matcher on any group; one PR per CVE; security PRs carry `security-update` label (label defined in `docs/LABEL-TAXONOMY.md` from Phase 55; OK to reference forward). Fixture test asserts no group has `applies-to: security-updates` (DEPBOT-02).
4. `zizmor` workflow runs on every PR + on `.github/workflows/**` edits; findings block merge; covers known-bad expression interpolation patterns that actionlint does not flag; complements not duplicates Phase 51 actionlint (DEPBOT-03).

### Claude's Discretion

Specific group package lists within the four buckets; zizmor workflow filename (`.github/workflows/zizmor.yml`); SHA pin for the zizmor action (resolve at execute time).

</decisions>

<code_context>
## Existing Code Insights

Codebase context gathered at execute time. Mirrors Phase 53 RESEARCH.md SHA-pin lookup procedure.

</code_context>

<specifics>
## Specific Constraints (from STATE.md)

1. Zero base-dep change (Phase 53 added the one allowed [dev] extras change).
2. ci.yml job names byte-identity contracts (Phase 54 does not rename or remove).
3. release_gate.py 8 check enum byte-identical (Phase 57 appends, not 54).
4. Every third-party `uses:` SHA-pinned (CIHARD-04). zizmor workflow follows the rule.

</specifics>

<deferred>
## Deferred Ideas

None for this phase.

</deferred>
