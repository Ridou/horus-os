---
phase: 58
phase_name: soft-launch-release-rehearsal
status: human_needed
verified: 2026-05-30T11:40:00Z
requirements:
  total: 5
  satisfied: 3
  partial: 1
  human_needed: 2
---

# Phase 58: Verification Report

**Status:** human_needed (2 carry-forward UAT items)

## Per-Requirement Coverage

| Requirement | Status | Evidence |
|-------------|--------|----------|
| TEST-22 (12+ pitfall regression tests) | satisfied | `tests/test_contribution_gate_pitfalls/test_pitfall_{01..12}_*.py` (12 files, 1:1 to PITFALLS.md). 49 tests green. |
| TEST-24 (wrong-identity sigstore negative fixture) | partial | Negative fixture landed: `tests/fixtures/sigstore/wrong-identity/{README.md,wrong-identity-bundle.sigstore.json}` + `tests/test_verify_release_wrong_identity.py` (5 tests, 4 pass + 1 skipif sigstore CLI). CANONICAL positive-case fixture awaits v0.6.0-rc1 rehearsal recording (human UAT). |
| TEST-25 (install-smoke matrix byte-identical) | satisfied | `.github/workflows/ci.yml` still contains `install-smoke-no-otel`, `install-smoke-with-otel`, `install-smoke-plugin` job names (grep-confirmed). Existing job names unchanged; Phase 58 added no renames. |
| TEST-26 (3-5 invited contributors land sample PRs) | human_needed | Requires inviting outside contributors and observing PRs land through the new audit.yml + release.yml + verify_release.py pipeline. Cannot be completed autonomously. |
| FLIP-02 (first-time-contributor branch-protection setting) | human_needed | Requires UI-only configuration in GitHub Settings; no `gh api` mutation path exists for the "Require approval for first-time contributors" setting. Cannot be completed autonomously. |

## Test Counts

- New tests added Phase 58: 17 (10 pitfall files + 5 wrong-identity + 1 module-level smoke).
- New pitfall test files: 10 (pitfalls 3-12; 1 + 2 pre-existing).
- All test files pass `ruff check` + `ruff format --check`.

## Outstanding Human UAT Items

These items carry forward to the v0.6.0-rc1 release-rehearsal session
(documented in detail in `.planning/v0.6-rehearsal-ready.md`):

1. **TEST-24 canonical fixture recording:** Record positive-case sigstore
   bundle from a real release.yml run on a fork. Commit to
   `tests/fixtures/sigstore/canonical/`. Drop the SKIP guard on
   `tests/test_release_verification.py::test_canonical_fixture_passes_wheel_check`.
2. **TEST-24 wrong-identity fixture upgrade (optional but recommended):**
   Replace the hand-crafted stub at `tests/fixtures/sigstore/wrong-identity/`
   with a real sigstore bundle recorded from the same rehearsal on a
   different fork identity. Gives the negative test cryptographic teeth.
3. **TEST-26 invited-contributor rehearsal:** 3-5 invited contributors
   land sample PRs through the full pipeline. Document friction findings.
4. **FLIP-02 branch-protection setting:** Toggle in GitHub Settings UI.
5. **RUNBOOK-02 rollback git-apply test:** Run
   `git apply --check .planning/rollback/flip-gate-revert.md` against a
   stale tree (a checkout at the Phase 56 head) and capture the log.

## Files Created / Modified

### Created (autonomous)

- `.planning/phases/58-soft-launch-release-rehearsal/58-CONTEXT.md`
- `tests/test_contribution_gate_pitfalls/test_pitfall_03_sigstore_identity_exact_match.py`
- `tests/test_contribution_gate_pitfalls/test_pitfall_04_sbom_install_time_resolved.py`
- `tests/test_contribution_gate_pitfalls/test_pitfall_05_dependabot_security_grouping.py`
- `tests/test_contribution_gate_pitfalls/test_pitfall_06_contributing_anti_patterns.py`
- `tests/test_contribution_gate_pitfalls/test_pitfall_07_stale_bot_and_label_taxonomy.py`
- `tests/test_contribution_gate_pitfalls/test_pitfall_08_release_gate_offline_fallback.py`
- `tests/test_contribution_gate_pitfalls/test_pitfall_09_no_pypi_trusted_publishing.py`
- `tests/test_contribution_gate_pitfalls/test_pitfall_10_gate_flip_rollback.py`
- `tests/test_contribution_gate_pitfalls/test_pitfall_11_trust_chain_completeness.py`
- `tests/test_contribution_gate_pitfalls/test_pitfall_12_security_slo_realism.py`
- `tests/fixtures/sigstore/wrong-identity/README.md`
- `tests/fixtures/sigstore/wrong-identity/wrong-identity-bundle.sigstore.json`
- `tests/test_verify_release_wrong_identity.py`

### Modified

None (Phase 58 is purely additive).

## Commits

- 74d6227 docs(58): create CONTEXT for soft launch + release rehearsal phase
- 590a803 test(58-01): pitfall regression suite (pitfalls 3 through 12)
- d4cd3e5 test(58-02): wrong-identity sigstore negative fixture + verify_release test
