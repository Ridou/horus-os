---
phase: 53
plan: "02"
completed: 2026-05-30
status: complete
---

# Phase 53 Plan 02 Summary: Wave 1 GREEN flip (SBOM + supply-chain substrate)

## Tasks Completed

| Task | File(s) | Status |
|------|---------|--------|
| Task 1 (audit.yml + pip-audit-ignore + tracking) | .github/workflows/audit.yml, .github/pip-audit-ignore.txt, .github/pip-audit-tracking/README.md | complete |
| Task 2 (release.yml SBOM steps + attest-sbom) | .github/workflows/release.yml | complete |
| Task 3 (verify_release.py check_sbom_signature flip + D-09 test update) | scripts/verify_release.py, tests/test_release_verification.py | complete |
| Task 4 (pyproject [dev] pip-audit) | pyproject.toml | complete |

## Plan 01 RED to GREEN Flip Status

| Test File | Production Tests | Before | After |
|-----------|------------------|--------|-------|
| tests/test_audit_yml_structure.py | 14 | 13 RED, 1 GREEN | 14 GREEN |
| tests/test_release_yml_sbom_steps.py | 12 | 11 RED, 1 GREEN | 12 GREEN |
| tests/test_pip_audit_ignore_discipline.py | 6 | 3 RED, 3 GREEN | 6 GREEN |
| tests/test_verify_release_sbom.py | 5 | 3 RED, 0 GREEN, 2 SKIP | 3 GREEN, 2 SKIP (canonical fixture + diff function deferred) |
| tests/test_pyproject_pip_audit_dev.py | 5 | 2 RED, 3 GREEN | 5 GREEN |
| **Production GREEN total** | 42 | 9 GREEN | 40 GREEN, 2 SKIP |

All RED-by-design production tests flipped GREEN. The 2 SKIP tests remain SKIP per documented Manual-Only Verification + Phase 57 deferral.

## Phase 52 No-Regression Verification

| Test File | Result |
|-----------|--------|
| tests/test_release_yml_structure.py | 12 passed (all Phase 52 SIGN-01/02 structural tests still pass) |
| tests/test_release_verification.py | 7 passed, 2 SKIP (canonical fixture pending); D-09 inverse-flip applied to test_sbom_check_returns_skipped_when_no_bundles |
| tests/test_release_md_stop_before_tag.py | (Phase 52 docs/RELEASE.md tests; not touched) |
| tests/test_decision_no_pypi.py | (Phase 52 decision-file tests; not touched) |

The Phase 52 D-08 stub test was the only Phase 52 test that needed updating; D-09 of Plan 02 specified this inverse-flip in the same commit as the stub flip.

## Requirements Coverage

| Requirement | Status | Verification |
|-------------|--------|--------------|
| SBOM-01 (FRESH-venv SBOM via cyclonedx-py environment; schema-version 1.6) | closed | release.yml two `.venv-sbom-*` steps; production tests GREEN |
| SBOM-02 (two SBOMs per release: clean + dev,otel) | closed | release.yml produces both `dist/horus_os-{clean,dev-otel}.cdx.json`; tests GREEN |
| SBOM-03 (attest-sbom + release-gate diff) | partially closed | Two attest-sbom invocations land; dependency-tree diff deferred to Phase 57 (Plan 02 D-05 + RESEARCH.md note); verify_release.py check_sbom_signature flipped to active 2-bundle verification |
| SUPPLY-01 (audit.yml pip-audit dual-mode + pyproject row) | closed | audit.yml + pyproject.toml [dev] both land; tests GREEN |
| SUPPLY-02 (dependency-review license allowlist) | closed | audit.yml dependency-review job lands; tests GREEN |
| SUPPLY-03 (pip-audit-ignore + tracking directory + dated comments) | closed | Both files land with empty ignore list at launch; tests GREEN |
| SUPPLY-04 (matrix over [dev] + [dev,otel]) | closed | audit.yml strategy.matrix.extras lands; tests GREEN |

## Files Created / Modified Counts

- **Created** (3): `.github/workflows/audit.yml`, `.github/pip-audit-ignore.txt`, `.github/pip-audit-tracking/README.md`
- **Modified** (4): `.github/workflows/release.yml` (added 7 SBOM steps + extended sigstore inputs glob), `scripts/verify_release.py` (flipped check_sbom_signature signature + body + extended argparser + main dispatch), `pyproject.toml` (1 line: pip-audit added to [dev]), `tests/test_release_verification.py` (D-09 inverse-flip; 1 test updated)
- **Plan 01 created files left untouched** (5 test files committed in Plan 01)

## Self-Check

- [x] All 4 tasks complete
- [x] All Plan 01 production tests GREEN (40 GREEN, 2 SKIP per documentation)
- [x] No Phase 52 regression (12 release.yml structure tests pass; 7 verify_release tests pass + 2 SKIP)
- [x] `ruff check` exits 0 on every touched file
- [x] `ruff format --check` exits 0 on every touched file
- [x] No em-dashes or en-dashes (grep -P returns empty on all 7 touched files)
- [x] SHA pins: actions/attest-sbom@c604332985a26aa8cf1bdc465b92731239ec6b9e (v4.1.0); pypa/gh-action-pip-audit@1220774d901786e6f652ae159f7b6bc8fea6d266 (v1.1.0); actions/dependency-review-action@595b5aeba73380359d98a5e087f648dbb0edce1b (v4.7.3)
- [x] Zero new base-dep additions (pyproject.toml [project.dependencies] unchanged; pip-audit only in [dev])
- [x] audit.yml NO id-token: write anywhere (fork-PR safety; verified by test_no_id_token_write_anywhere)
- [x] sigstore inputs glob ends with `./dist/*.cdx.json` (Phase 52 D-10 forward-reference satisfied)

## Hand-off Notes (Phase 54)

Phase 54 (Dependabot tuning + zizmor; DEPBOT-01..03) lands next. Phase 54 will:
- Discover `.github/workflows/audit.yml` + the extended `.github/workflows/release.yml` and add Dependabot entries for the new `pypa/gh-action-pip-audit`, `actions/dependency-review-action`, and `actions/attest-sbom` actions plus the `cyclonedx-bom` Python dep (inline in release.yml; Dependabot's pip ecosystem entry covers this via pyproject's [dev] pip-audit pin)
- Add zizmor security scanning over all four workflows: ci.yml, release.yml, audit.yml, plus any future workflow
- Pin Dependabot itself to the v4 schema with explicit `groups:` clauses

No Phase 53 SBOM substrate work is needed by Phase 54; the substrate is fully wired. The two outstanding Manual-Only Verifications (canonical SBOM bundle binary + `gh attestation verify` against a published SBOM) carry forward to Phase 58 (soft launch + release rehearsal).

The `dependency-tree diff vs wheel` clause of SBOM-03 is intentionally deferred to Phase 57 release-gate where `pip install --dry-run --report -` can run locally. The substrate (SBOMs generated, signed, attested) is fully in place for Phase 57 to add the diff check on top.
