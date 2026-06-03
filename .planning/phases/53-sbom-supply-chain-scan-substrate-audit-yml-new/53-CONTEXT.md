# Phase 53: SBOM + supply-chain scan substrate (`audit.yml` NEW) - Context

**Gathered:** 2026-05-30
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Add release-time SBOM generation and PR-time supply-chain scanning. SBOMs are CycloneDX 1.6 JSON generated against a FRESH `pip install <wheel>` venv (NOT `pip freeze` of the dev venv); two per release (clean + `[dev,otel]`); both signed via sigstore in the same `release.yml` job from Phase 52; SBOM attestations bind contents to the wheel. `audit.yml` NEW runs `pip-audit` dual-mode on every PR plus `dependency-review-action` with a license allowlist. `pip-audit` added to `[dev]` extras, the ONE base-dep-extras change in v0.6.

</domain>

<canonical_refs>
## Canonical References

- `.planning/REQUIREMENTS.md` (v0.6 section: SBOM-01, SBOM-02, SBOM-03, SUPPLY-01, SUPPLY-02, SUPPLY-03, SUPPLY-04)
- `.planning/ROADMAP.md` (Phase 53 section)
- `.planning/STATE.md` (load-bearing constraints, especially #1 + #6)
- `CLAUDE.md` (project hard rules)
- `.github/workflows/release.yml` (extended from Phase 52)
- `.github/workflows/ci.yml` (existing install-smoke two-variant convention)
- `scripts/release_gate.py` (Phase 49 idiom; check enum extended in Phase 57, not here)
- `pyproject.toml` (`[project.optional-dependencies]` dev extras)
- Phase 51 PLAN/SUMMARY (SHA-pin baseline + workflow-lint discipline)
- Phase 52 PLAN/SUMMARY (signing substrate, release.yml job that this phase extends)

</canonical_refs>

<decisions>
## Implementation Decisions

### Locked by REQUIREMENTS.md and ROADMAP.md

1. `release.yml` (extended from Phase 52) runs `cyclonedx-py environment` (cyclonedx-bom >=7.3,<8) against a FRESH `pip install <wheel>` venv (NOT `pip freeze` of the dev venv); CycloneDX 1.6 JSON format locked; SBOM signed via sigstore-python in the same job that signs the wheel (SBOM-01).
2. Two SBOMs ship per release: clean install (`pip install <wheel>`) AND extras install (`pip install <wheel>[dev,otel]`); both attached to the GitHub Release alongside their `.sigstore` bundles; matches existing two-variant install-smoke convention (SBOM-02).
3. `actions/attest-sbom@<40-char-sha>` generates SBOM attestations bound to the artifact each SBOM describes; release-gate diffs SBOM contents against the published wheel's actual installed dependency tree; a fixture test asserts the gate fails when the SBOM is stale relative to the wheel (SBOM-03).
4. NEW `.github/workflows/audit.yml` triggers on every PR with `permissions: contents: read` + `persist-credentials: false`; runs `pypa/gh-action-pip-audit@<40-char-sha>` (pip-audit >=2.10,<3) dual-mode (`-s osv` AND `-s pypi`); failures block merge; `pip-audit` added to `[dev]` extras for local use (the single base-dep-extras change in v0.6) (SUPPLY-01).
5. `actions/dependency-review-action@<40-char-sha>` runs on every PR with explicit license allowlist (Apache-2.0, MIT, BSD-2-Clause, BSD-3-Clause, ISC, PSF-2.0); rejects new deps under unlisted licenses; rejection produces a PR comment naming the offending dep + license (SUPPLY-02).
6. `.github/pip-audit-ignore.txt` enforces mandatory dated-comment discipline: every entry includes a `# YYYY-MM-DD: <reason>` line; release-gate rejects undated entries; `.github/pip-audit-tracking/` directory carries fix-tracking docs for unfixable transitives (one file per ignored CVE) (SUPPLY-03).
7. `pip-audit` runs on BOTH `[dev]` AND `[dev,otel]` install variants in `audit.yml`; matches the Phase 39 OTel-variant precedent + the existing two-variant install-smoke pattern (SUPPLY-04).

### Claude's Discretion
Remaining implementation choices (file layout, helper function naming, test fixture organization) are at Claude's discretion within the locked requirements. Follow existing codebase patterns from prior phases (51, 52).

</decisions>

<code_context>
## Existing Code Insights

Codebase context will be gathered during plan-phase research. See PATTERNS.md after planning.

</code_context>

<specifics>
## Specific Constraints (from STATE.md load-bearing list)

1. `pyproject.toml` base `[project.dependencies]` adds NOTHING in v0.6. Phase 53 alone adds `pip-audit>=2.10,<3` to `[dev]` extras.
2. `ci.yml` job names `install-smoke-no-otel`, `install-smoke-with-otel`, `install-smoke-plugin` are byte-identity contracts. This phase does not rename them.
3. `release_gate.py` 8 existing `--check` enum values are APPENDED to, never renamed. The 5 new checks land in Phase 57, not here.
4. Every third-party `uses:` SHA-pinned to 40-char commit; tj-actions/changed-files CVE-2025-30066 is the cited incident. All new `uses:` lines in `audit.yml` plus the new SBOM step in `release.yml` follow this rule.
5. SBOM-01 FRESH-venv rule: SBOM is generated against a `pip install <wheel>` venv, never `pip freeze` of the dev venv. This rule is enforced by the release-gate diff in SBOM-03.

</specifics>

<deferred>
## Deferred Ideas

None for this phase.

</deferred>
