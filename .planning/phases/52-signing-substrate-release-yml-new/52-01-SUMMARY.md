---
phase: 52
plan: "01"
subsystem: signing-substrate
tags: [ci, security, signing, sigstore, regression-tests, wave-0, red-by-design]
dependency_graph:
  requires:
    - "docs/RELEASE.md (existing; provides byte-identity baseline for steps 1-6 + 8-9)"
    - ".planning/PROJECT.md (existing; provides 3-column Key Decisions table precedent)"
    - "tests/test_release_gate.py (existing; provides importlib.util.spec_from_file_location pattern)"
    - "tests/test_contribution_gate_pitfalls/test_pitfall_02_action_sha_pinning.py (Phase 51; provides _USES_PATTERN + _ALLOWED_REF SHA-pin regex)"
  provides:
    - "tests/test_release_yml_structure.py (12 tests; 9 production RED + 3 non-vacuity GREEN)"
    - "tests/test_release_md_stop_before_tag.py (3 tests; PRE_EDIT_STEPS_1_THROUGH_6 + PRE_EDIT_STEPS_8_THROUGH_9 byte-identity baselines)"
    - "tests/test_decision_no_pypi.py (3 tests; planning-side .planning/PROJECT.md cross-ref)"
    - "tests/test_release_verification.py (9 tests; 5 production + 2 non-vacuity helpers + 1 module-import + 1 subprocess smoke)"
    - "tests/fixtures/sigstore/canonical/README.md (recording-procedure documentation; binary fixtures pending v0.6.0-rc1 rehearsal)"
  affects:
    - "Plan 02 of Phase 52 (Wave 1): flips every RED production assertion GREEN by creating .github/workflows/release.yml + scripts/verify_release.py + .planning/decisions/no-pypi-in-v0.6.md; editing docs/RELEASE.md (insert step 6.5; swap step 7 from -a to -s); appending one row to .planning/PROJECT.md key-decisions table"
    - "Phase 53 (SBOM): widens release.yml sigstore inputs and flips the SBOM stub from SKIPPED to active"
    - "Phase 57 (release-gate extension): release-workflow-signing-present check greps for the sigstore-python literal this Wave 0 test pins"
    - "Phase 58 (TEST-24): sibling tests/fixtures/sigstore/wrong_identity/ directory following the canonical/ filename convention"
tech_stack:
  added: []
  patterns:
    - "stdlib re regex scanning over .github/workflows/release.yml (no PyYAML)"
    - "Path(__file__).resolve().parents[1] for top-level tests (one fewer than nested under tests/test_contribution_gate_pitfalls/)"
    - "@pytest.fixture(scope='module') loading docs/RELEASE.md and the decision file text once per module"
    - "importlib.util.spec_from_file_location to load scripts/verify_release.py in-process (mirrors tests/test_release_gate.py:31-46)"
    - "RED-by-design production assertions (Wave 0 signal; Plan 02 turns GREEN)"
    - "Non-vacuity synthetic fixtures (tmp_path); scanners proven to fire BEFORE Wave 1 production code lands"
    - "Cross-OS subprocess discipline: sys.executable, str(path), capture_output=True, text=True, check=False"
    - "encoding='utf-8' on every read_text() call (Windows cp1252 default avoidance)"
key_files:
  created:
    - "tests/test_release_yml_structure.py"
    - "tests/test_release_md_stop_before_tag.py"
    - "tests/test_decision_no_pypi.py"
    - "tests/test_release_verification.py"
    - "tests/fixtures/sigstore/canonical/README.md"
  modified: []
decisions:
  - "Top-level test placement (REPO_ROOT = Path(__file__).resolve().parents[1]) per CONTEXT.md canonical_refs line 168; mirrors tests/test_release_gate.py shape rather than the nested tests/test_contribution_gate_pitfalls/ shape (which uses parents[2])"
  - "Pre-edit STOP-BEFORE-TAG prose for steps 1-6 (lines 122-141) and 8-9 (lines 145-157) is pinned as Python multi-line string constants inside test_release_md_stop_before_tag.py to enforce the insertions-allowed-mutations-not byte-identity invariant (D-05; Phase 51 D-06 precedent)"
  - "Binary fixture files (.whl + .sigstore[.json]) are out of scope for Plan 01; only the canonical/ directory + README.md placeholder ships now. Tests that exercise the canonical bundle pytest.skip() until binaries land at v0.6.0-rc1 rehearsal recording time per VALIDATION.md Manual-Only Verifications row 1. Module-import + argparse-machinery production tests remain RED-by-design now."
  - "importlib.util in-process load (mirrors tests/test_release_gate.py:31-46) so tests can call mod.check_sbom_signature() etc. directly without subprocess overhead; OPTIONAL Pattern C subprocess shell-out smoke test is also included (mirrors tests/test_lint_no_wallclock.py:20-32)"
  - "Cross-ref test in test_decision_no_pypi.py reads the planning-side .planning/PROJECT.md (NOT top-level PROJECT.md) per D-09 + RESEARCH.md Pattern 4; the existing 3-column Key Decisions table at .planning/PROJECT.md:74-81 is the precedent shape Plan 02 appends to"
  - "Aggregated scanner _scan_release_yml(workflows_dir: Path) parametrized on workflows_dir so the three non-vacuity synthetic-fixture tests can write minimal release.yml files to tmp_path and exercise the scanner directly (mirrors Phase 51 Plan 01 51-01-SUMMARY.md Non-Vacuity Coverage pattern)"
metrics:
  duration_minutes: 7
  completed: "2026-05-29"
  task_count: 2
  file_count: 5
  test_count_added: 27
  production_red_count: 16
  green_count: 4
  skip_count: 5
  error_count: 2
---

# Phase 52 Plan 01: Signing-Substrate Wave 0 RED-by-Design Test Scaffolding Summary

Wave 0 test infrastructure for Phase 52 lands five new files that scan for, but do not create, the Phase 52 production artifacts. Production assertions are RED-by-design; Plan 02 (Wave 1) flips them GREEN by creating `.github/workflows/release.yml`, `scripts/verify_release.py`, `.planning/decisions/no-pypi-in-v0.6.md`, editing `docs/RELEASE.md` (insert step 6.5; swap step 7 from `git tag -a` to `git tag -s`), and appending one row to `.planning/PROJECT.md` key-decisions table.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Three RED scaffolds for SIGN-01..03 + SIGN-05 (workflow + docs + decision file) | `cbba23e` | tests/test_release_yml_structure.py, tests/test_release_md_stop_before_tag.py, tests/test_decision_no_pypi.py |
| 2 | verify_release.py RED scaffold + canonical fixture-dir README | `d108ace` | tests/test_release_verification.py, tests/fixtures/sigstore/canonical/README.md |

## Production Assertions: RED vs GREEN State

| Test File | Production Test | Wave 0 State | Wave 1 Flip Trigger |
|-----------|------------------|--------------|----------------------|
| test_release_yml_structure.py | test_release_yml_exists | RED | Plan 02 creates `.github/workflows/release.yml` |
| test_release_yml_structure.py | test_on_release_published_trigger | RED | Plan 02 writes `on: release: types: [published]` |
| test_release_yml_structure.py | test_top_level_permissions_read_all | RED | Plan 02 writes `permissions: read-all` at column 0 |
| test_release_yml_structure.py | test_per_job_id_token_write | RED | Plan 02 writes per-job `id-token: write`, `contents: write`, `attestations: write` |
| test_release_yml_structure.py | test_per_artifact_attest | RED | Plan 02 writes TWO `actions/attest-build-provenance@<sha>` invocations |
| test_release_yml_structure.py | test_sigstore_action_literal_present | RED | Plan 02 writes the `sigstore/gh-action-sigstore-python` literal |
| test_release_yml_structure.py | test_sigstore_action_sha_pinned | RED | Plan 02 pins to a 40-char hex commit SHA |
| test_release_yml_structure.py | test_sigstore_step_timeout_minutes_5 | RED | Plan 02 adds `timeout-minutes: 5` to the sigstore step |
| test_release_yml_structure.py | test_every_uses_in_release_yml_sha_pinned | RED | Plan 02 SHA-pins every `uses:` per CIHARD-04 |
| test_release_md_stop_before_tag.py | test_step_6_5_gitsign_inserted | RED | Plan 02 inserts step 6.5 between current steps 6 and 7 |
| test_release_md_stop_before_tag.py | test_step_7_uses_tag_dash_s | RED | Plan 02 swaps `git tag -a` to `git tag -s` |
| test_release_md_stop_before_tag.py | test_steps_1_through_6_and_8_through_9_byte_identical | GREEN | Baseline already matches RELEASE.md; Plan 02 must preserve |
| test_decision_no_pypi.py | test_decision_file_exists | ERROR (RED) | Plan 02 creates `.planning/decisions/no-pypi-in-v0.6.md` |
| test_decision_no_pypi.py | test_decision_file_has_terminator | ERROR (RED) | Plan 02 lands the `**Decision (final, until revisited):**` block |
| test_decision_no_pypi.py | test_project_md_references_decision_file | RED | Plan 02 appends one row to `.planning/PROJECT.md` Key Decisions table |
| test_release_verification.py | test_canonical_fixture_passes_wheel_check | SKIP | v0.6.0-rc1 rehearsal recording (Manual-Only Verification) |
| test_release_verification.py | test_missing_issuer_refused | RED | Plan 02 creates `scripts/verify_release.py` with `required=True` argparse |
| test_release_verification.py | test_wrong_issuer_refused | RED | Plan 02 wires the issuer-mismatch refusal path |
| test_release_verification.py | test_sbom_stub_returns_skipped | RED | Plan 02 lands the SBOM stub returning `ok=None` + `Phase 53` diagnostic |
| test_release_verification.py | test_full_run_all_checks_with_canonical_fixture | SKIP | v0.6.0-rc1 rehearsal recording (Manual-Only Verification) |
| test_release_verification.py | test_expected_identity_template_invariant_is_documented | SKIP | Plan 02 lands the script (then this becomes GREEN via source-scan) |
| test_release_verification.py | test_expected_issuer_constant_documented | SKIP | Plan 02 lands the script (then this becomes GREEN via source-scan) |
| test_release_verification.py | test_module_imports_cleanly | RED | Plan 02 lands the script with byte-exact EXPECTED_IDENTITY_TEMPLATE + EXPECTED_ISSUER |
| test_release_verification.py | test_script_runs_via_subprocess | SKIP | Plan 02 lands the script (then GREEN via subprocess smoke) |

RED-by-design totals: 16 FAIL, 2 ERROR (fixture-level), 5 SKIP (canonical fixtures + script absent), 4 PASS (3 non-vacuity scanners + 1 pre-edit baseline). 27 tests collected total.

## Non-Vacuity Coverage

Each scanner is proven to fire on a known violation written to `tmp_path` before any production code lands. This is the Phase 51 Plan 01 pattern (51-01-SUMMARY.md §Non-Vacuity Coverage); without it, a typo in the regex would silently allow violations through.

| Scanner | Non-Vacuity Test | Synthetic Violation | Wave 0 State |
|---------|------------------|---------------------|--------------|
| Missing top-level `permissions: read-all` | test_scanner_catches_synthetic_missing_permissions | tmp_path/release.yml with no `permissions:` line | PASS |
| Mutable tag pin in `uses:` | test_scanner_catches_synthetic_sha_violation | tmp_path/release.yml with `uses: actions/checkout@v4` | PASS |
| Missing per-artifact attest invocation | test_scanner_catches_synthetic_missing_attest | tmp_path/release.yml with only ONE `attest-build-provenance` line | PASS |

The verify_release.py test file does NOT need non-vacuity synthetic scanners because its production assertions exercise the script's runtime behavior directly (argparse, SystemExit, exit codes, fixture verification) rather than scanning text patterns. Its analogous non-vacuity is the source-scan tests `test_expected_identity_template_invariant_is_documented` and `test_expected_issuer_constant_documented`, which would catch a Plan 02 implementation that DROPPED the load-bearing literals (`'refs/tags/{version}'` placeholder and the issuer URL) from the script source even if the runtime tests still passed by accident.

## Test Collection Counts

```
$ pytest --collect-only -q tests/test_release_verification.py tests/test_release_yml_structure.py tests/test_release_md_stop_before_tag.py tests/test_decision_no_pypi.py
...
27 tests collected in 0.03s
```

Per-file breakdown:

| File | Tests | Production (RED + GREEN) | Non-Vacuity (GREEN now) | Skip (now) |
|------|-------|---------------------------|-------------------------|------------|
| tests/test_release_yml_structure.py | 12 | 9 RED | 3 PASS | 0 |
| tests/test_release_md_stop_before_tag.py | 3 | 2 RED + 1 GREEN (pre-edit baseline) | 0 | 0 |
| tests/test_decision_no_pypi.py | 3 | 1 RED + 2 ERROR (fixture absent = RED-by-design) | 0 | 0 |
| tests/test_release_verification.py | 9 | 4 RED + 5 SKIP | 0 (source-scan helpers below skip) | 5 |

Full pytest output (truncated):

```
============== 16 failed, 4 passed, 5 skipped, 2 errors in 0.11s ===============
```

## Requirements Coverage

| Requirement | Test File | Tests Pinning the Contract |
|-------------|-----------|----------------------------|
| SIGN-01 (sigstore action + OIDC budget + permissions) | tests/test_release_yml_structure.py | test_on_release_published_trigger, test_top_level_permissions_read_all, test_per_job_id_token_write, test_sigstore_action_literal_present, test_sigstore_action_sha_pinned, test_sigstore_step_timeout_minutes_5, test_every_uses_in_release_yml_sha_pinned |
| SIGN-02 (per-artifact attestation) | tests/test_release_yml_structure.py | test_per_artifact_attest (TWO `attest-build-provenance` invocations per D-06) |
| SIGN-03 (gitsign STOP-BEFORE-TAG) | tests/test_release_md_stop_before_tag.py | test_step_6_5_gitsign_inserted, test_step_7_uses_tag_dash_s, test_steps_1_through_6_and_8_through_9_byte_identical |
| SIGN-04 (verify_release.py 5-check verifier) | tests/test_release_verification.py | test_canonical_fixture_passes_wheel_check, test_missing_issuer_refused, test_wrong_issuer_refused, test_sbom_stub_returns_skipped, test_full_run_all_checks_with_canonical_fixture, test_expected_identity_template_invariant_is_documented, test_expected_issuer_constant_documented, test_module_imports_cleanly, test_script_runs_via_subprocess |
| SIGN-05 (no-pypi-in-v0.6 decision file + PROJECT.md cross-ref) | tests/test_decision_no_pypi.py | test_decision_file_exists, test_decision_file_has_terminator, test_project_md_references_decision_file |

## Hand-off Notes (what Plan 02 must create to flip each RED assertion GREEN)

Plan 02 (Wave 1) consumes this test surface and creates the following production artifacts. Each item maps 1:1 to the RED assertions above.

1. **Create `.github/workflows/release.yml`** with:
   - `on: release: types: [published]` trigger ONLY (no `push: tags:`, no `workflow_dispatch:`)
   - Top-level `permissions: read-all` at column 0
   - One job named `sign-and-attest` running on `ubuntu-latest`
   - Per-job permissions `id-token: write`, `contents: write`, `attestations: write`
   - Steps: actions/checkout (SHA-pinned + `persist-credentials: false`), actions/setup-python (SHA-pinned), pip install build, `python -m build`, `sigstore/gh-action-sigstore-python@<40-hex>` with `timeout-minutes: 5` and `inputs: ./dist/*.whl ./dist/*.tar.gz` and `release-signing-artifacts: true`, TWO `actions/attest-build-provenance@<40-hex>` invocations (one wheel, one sdist)
   - Every `uses:` line SHA-pinned to a 40-char hex commit (CIHARD-04 inheritance)
2. **Create `scripts/verify_release.py`** (stdlib only) with:
   - Module docstring + `from __future__ import annotations` + stdlib imports + `REPO_ROOT = Path(__file__).resolve().parent.parent`
   - Hardcoded constants: `EXPECTED_IDENTITY_TEMPLATE = "https://github.com/Ridou/horus-os/.github/workflows/release.yml@refs/tags/{version}"` and `EXPECTED_ISSUER = "https://token.actions.githubusercontent.com"`
   - Module-import-time assertion: `assert "refs/tags/{version}" in EXPECTED_IDENTITY_TEMPLATE` (PITFALL 1 defense)
   - `@dataclass(frozen=True) CheckResult` (copy verbatim from `scripts/release_gate.py:137-148`)
   - Five check functions: `check_wheel_signature`, `check_sdist_signature`, `check_tag_signature`, `check_sbom_signature` (returns `CheckResult(name='sbom-signature', ok=None, diagnostic='SKIPPED - Phase 53 lands SBOM generation + signing')`), `check_changelog_cross_ref`
   - `_print_result` formatter (copy verbatim from `scripts/release_gate.py:634-640`)
   - `main(argv)` with `--version` (required=True), `--cert-oidc-issuer` (required=True; compare equals EXPECTED_ISSUER; on mismatch `parser.error(...)` to exit non-zero with stderr citing EXPECTED_ISSUER), `--bundle`, `--artifact`, `--check {wheel|sdist|tag|sbom|changelog}` dispatch
3. **Create `.planning/decisions/no-pypi-in-v0.6.md`** with the literal `**Decision (final, until revisited):**` terminator block. Short (≤200 lines). Use the prose shape from RESEARCH.md §Decision-file shape.
4. **Edit `docs/RELEASE.md`**: INSERT step 6.5 (literal `git config --get gitsign.connectorID` referencing `docs/MAINTAINER-RUNBOOK.md`) BETWEEN current step 6 (lines 140-141) and current step 7 (lines 142-144). SWAP step 7 from `git tag -a vN.M.P -m "vN.M.P - <milestone-name>"` to `git tag -s vN.M.P -m "vN.M.P - <milestone-name>"`. DO NOT modify steps 1-6 or steps 8-9 (byte-identity invariant per Phase 51 D-06 + Phase 52 D-05; test_steps_1_through_6_and_8_through_9_byte_identical enforces).
5. **Edit `.planning/PROJECT.md`**: APPEND one row to the existing Key Decisions table at lines 74-81. The row must contain the literal substring `.planning/decisions/no-pypi-in-v0.6.md` (test_project_md_references_decision_file enforces).

After Plan 02 lands, the full Wave 0 verification sequence should report 27 tests collected, 0 failed, ~21 passed, and 6 SKIPPED (the canonical-fixture binary tests remain skipped until v0.6.0-rc1 rehearsal recording per VALIDATION.md Manual-Only Verifications row 1). The 4 non-vacuity tests and the byte-identity baseline test remain PASS throughout.

## Deviations from Plan

None. The plan executed exactly as written. All acceptance criteria met:

- 5 Wave 0 files created and committed (4 test files + 1 fixture README)
- Each test file uses `Path(__file__).resolve().parents[1]` (top-level, not nested)
- Every test follows cross-OS subprocess discipline (`sys.executable`, `str(path)`, `capture_output=True, text=True, check=False`, `encoding="utf-8"`)
- No em-dashes / en-dashes in any new file (verified via Python char scan; CLAUDE.md HR3)
- Ruff lint + format both pass on all 4 test files
- Production assertions are RED-by-design (the production files they scan do not exist yet in Wave 0)
- Non-vacuity synthetic-fixture tests PASS NOW, proving each scanner fires on a known violation
- Test infrastructure is provably ready for Plan 02 to flip GREEN

Ruff auto-formatting changed 3 files (cosmetic line-wrapping only; no semantic changes). Not a deviation, just the standard `ruff format` post-write step.

## Self-Check

File existence check (all 5 files in worktree):

```
FOUND: tests/test_release_yml_structure.py
FOUND: tests/test_release_md_stop_before_tag.py
FOUND: tests/test_decision_no_pypi.py
FOUND: tests/test_release_verification.py
FOUND: tests/fixtures/sigstore/canonical/README.md
```

Commit existence check (both commits in git log):

```
FOUND: cbba23e (test(52-01): add Wave 0 RED scaffolds for SIGN-01..03 + SIGN-05)
FOUND: d108ace (test(52-01): add verify_release.py RED scaffold + canonical fixture-dir README)
```

Wave 0 verification sequence (re-run on demand):

```
$ pytest tests/test_release_verification.py tests/test_release_yml_structure.py tests/test_release_md_stop_before_tag.py tests/test_decision_no_pypi.py -v
============== 16 failed, 4 passed, 5 skipped, 2 errors in 0.11s ===============

$ ruff check tests/test_release_verification.py tests/test_release_yml_structure.py tests/test_release_md_stop_before_tag.py tests/test_decision_no_pypi.py
All checks passed!

$ ruff format --check tests/test_release_verification.py tests/test_release_yml_structure.py tests/test_release_md_stop_before_tag.py tests/test_decision_no_pypi.py
4 files already formatted
```

Existing-suite sanity check (tests/test_release_gate.py + tests/test_lint_no_wallclock.py):

```
============================== 13 passed in 0.21s ==============================
```

No regressions in adjacent existing tests.

## Self-Check: PASSED
