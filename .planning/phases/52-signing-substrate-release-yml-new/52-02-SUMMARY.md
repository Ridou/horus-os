---
phase: 52
plan: "02"
subsystem: signing-substrate
tags: [ci, security, signing, sigstore, sbom-stub, gitsign, decision-file, wave-1, green-flip]
dependency_graph:
  requires:
    - "tests/test_release_yml_structure.py (Plan 01 Wave 0; nine RED structural assertions over release.yml)"
    - "tests/test_release_verification.py (Plan 01 Wave 0; SIGN-04 unit + integration + source-scan tests)"
    - "tests/test_release_md_stop_before_tag.py (Plan 01 Wave 0; SIGN-03 docs prose lint with pinned pre-edit baselines)"
    - "tests/test_decision_no_pypi.py (Plan 01 Wave 0; SIGN-05 decision-file + PROJECT.md cross-ref)"
    - "tests/fixtures/sigstore/canonical/README.md (Plan 01 Wave 0; rehearsal recording procedure placeholder)"
    - ".github/workflows/ci.yml (Phase 51; byte-identity reference for top-level read-all + per-job opt-in pattern + 40-char SHA-pin shape with trailing # vN.M.P comment)"
    - "scripts/release_gate.py (CheckResult dataclass + _print_result + argparse-enum dispatch precedent at lines 137-148, 634-640, 678-766)"
    - "scripts/lint_no_wallclock.py (stdlib-only Python script + subprocess shell-out precedent for the install-hint branch)"
    - "docs/RELEASE.md (existing STOP-BEFORE-TAG block; provides byte-identity baseline for steps 1-6 and 8-9)"
    - ".planning/PROJECT.md (existing Key Decisions table; provides 3-column shape Phase 52 appends one row to)"
  provides:
    - ".github/workflows/release.yml (NEW; single sign-and-attest job triggered on release.published; the SIGN-01 + SIGN-02 substrate Phase 53 inherits and Phase 57 cross-refs)"
    - "scripts/verify_release.py (NEW; stdlib-only five-check trust-chain verifier with SBOM stub; the SIGN-04 substrate Phase 53 flips to active)"
    - ".planning/decisions/no-pypi-in-v0.6.md (NEW; PyPI Trusted Publishing deferral rationale; the SIGN-05 substrate Phase 56 adds sibling decision files to)"
    - "docs/RELEASE.md step 6.5 + signed tag (MODIFIED; gitsign pre-flight check + git tag -s; the SIGN-03 substrate Phase 56 fills in via MAINTAINER-RUNBOOK.md)"
    - ".planning/PROJECT.md key-decisions row (MODIFIED; the SIGN-05 atomic counterpart to the decision file per D-09)"
    - ".planning/decisions/ directory (NEW; established by Phase 52 as the home for v0.6+ decision files; Phase 56 adds sigstore-keyless.md, no-cla.md, no-stale-bot.md, sbom-cyclonedx.md)"
  affects:
    - "Phase 53 (SBOM): the release.yml sigstore inputs glob is ready for a one-glob append (./dist/*.sbom.json); the verify_release.py SBOM stub is ready to flip from ok=None to active subprocess call"
    - "Phase 56 (RUNBOOK): docs/MAINTAINER-RUNBOOK.md forward reference in docs/RELEASE.md step 6.5 needs the gitsign one-time config content; .planning/decisions/ directory is established and Phase 56 adds sibling files"
    - "Phase 57 (release-gate extension): the literal sigstore/gh-action-sigstore-python in release.yml lets the release-workflow-signing-present check grep succeed; every uses: SHA-pinned lets the actions-pinned-by-sha check pass"
    - "Phase 58 (TEST-24 + rehearsal): the tests/fixtures/sigstore/canonical/ directory needs the binary .whl + .sigstore[.json] from a v0.6.0-rc1 rehearsal; the sibling tests/fixtures/sigstore/wrong_identity/ is the Phase 58 deliverable"
tech_stack:
  added:
    - "sigstore/gh-action-sigstore-python@04cffa1d795717b140764e8b640de88853c92acc v3.3.0 (CI-only; never enters pyproject.toml per D-03)"
    - "actions/attest-build-provenance@a2bbfa25375fe432b6a289bc6b6cd05ecd0c4c32 v4.1.0 (CI-only)"
  patterns:
    - "Top-level permissions: read-all + per-job opt-in (matches Phase 51 ci.yml convention)"
    - "Every uses: line SHA-pinned to 40-char hex with trailing # vN.M.P comment (Phase 51 pinact convention)"
    - "Per-artifact attest-build-provenance: one dist/*.whl invocation, one dist/*.tar.gz invocation (D-06)"
    - "Two-glob whitespace-separated sigstore inputs ready for Phase 53 SBOM glob append (D-10)"
    - "Stdlib-only Python script that shells out via subprocess (mirrors scripts/release_gate.py and lint_no_wallclock.py)"
    - "@dataclass(frozen=True) CheckResult with ok: bool | None (None = SKIPPED; PITFALL-1 + D-08 + D-04)"
    - "Module-import-time assert defends EXPECTED_IDENTITY_TEMPLATE {version} placeholder"
    - "Argparse required=True on both --version and --cert-oidc-issuer; explicit equality check against EXPECTED_ISSUER"
    - "Insertions allowed, mutations not on docs/RELEASE.md STOP-BEFORE-TAG block (Phase 51 D-06 byte-identity invariant)"
    - "Single-commit atomicity for decision file + PROJECT.md row + docs/RELEASE.md edits (D-09)"
key_files:
  created:
    - ".github/workflows/release.yml"
    - "scripts/verify_release.py"
    - ".planning/decisions/no-pypi-in-v0.6.md"
  modified:
    - "docs/RELEASE.md"
    - ".planning/PROJECT.md"
decisions:
  - "release.yml is ONE sign-and-attest job on ubuntu-latest with sequential checkout/setup-python/install-build/python -m build/sigstore-sign/attest-wheel/attest-sdist steps per D-01"
  - "Top-level permissions: read-all + per-job id-token/contents/attestations write on sign-and-attest only per D-02"
  - "verify_release.py is stdlib-only and shells out via subprocess to python -m sigstore + git + gh per D-03; sigstore NEVER added to pyproject.toml"
  - "EXPECTED_IDENTITY_TEMPLATE and EXPECTED_ISSUER hardcoded; --cert-oidc-issuer required and must equal EXPECTED_ISSUER per D-04"
  - "docs/RELEASE.md edits are two surgical insertions (step 6.5 between steps 6 and 7; tag -a to tag -s in step 7); steps 1-6 and 8-9 prose byte-identical to pre-edit baseline per D-05"
  - "Per-artifact attest-build-provenance: one for wheel glob, one for sdist glob per D-06"
  - "verify_release.py ships five-check skeleton; SBOM check returns CheckResult(ok=None) SKIPPED until Phase 53 per D-08"
  - "Decision file + PROJECT.md key-decisions table row land in the SAME commit per D-09 (SIGN-05 atomicity; commit ebf2a47)"
  - "Sigstore inputs are exactly ./dist/*.whl ./dist/*.tar.gz per D-10; Phase 53 appends ./dist/*.sbom.json (smallest possible diff)"
metrics:
  duration_minutes: 7
  completed: "2026-05-29"
  task_count: 3
  file_count: 5
  test_count_added: 0
  test_count_flipped_red_to_green: 16
  test_count_pass: 25
  test_count_skip: 2
---

# Phase 52 Plan 02: Signing-Substrate Wave 1 GREEN Flip Summary

Wave 1 lands the three NEW production files (`.github/workflows/release.yml`, `scripts/verify_release.py`, `.planning/decisions/no-pypi-in-v0.6.md`) plus two MODIFIED files (`docs/RELEASE.md` step 6.5 insertion + step 7 `-a` to `-s` swap, `.planning/PROJECT.md` key-decisions row append) that flip every Plan 01 RED-by-design production assertion GREEN. The v0.6 signing substrate is now end-to-end: a release-published trigger signs wheel + sdist via keyless OIDC, writes per-artifact SLSA Build L2 attestations, and the user-facing five-check trust-chain verifier orchestrates `python -m sigstore`, `git verify-tag`, and `gh release view` with hardcoded workflow-scoped identity pinning.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create .github/workflows/release.yml (SIGN-01 + SIGN-02) | `cb8a504` | .github/workflows/release.yml |
| 2 | Create scripts/verify_release.py five-check verifier (SIGN-04) | `615b754` | scripts/verify_release.py |
| 3 | Land no-pypi-in-v0.6 decision + RELEASE.md gitsign + PROJECT.md row (SIGN-03 + SIGN-05; atomic per D-09) | `ebf2a47` | .planning/decisions/no-pypi-in-v0.6.md, docs/RELEASE.md, .planning/PROJECT.md |

## Plan 01 RED-to-GREEN Transition

| Test File | Production Test | Wave 0 State | Wave 1 State | Flip Trigger |
|-----------|-----------------|--------------|--------------|--------------|
| test_release_yml_structure.py | test_release_yml_exists | RED | GREEN | Task 1: created .github/workflows/release.yml |
| test_release_yml_structure.py | test_on_release_published_trigger | RED | GREEN | Task 1: `on: release: types: [published]` |
| test_release_yml_structure.py | test_top_level_permissions_read_all | RED | GREEN | Task 1: `permissions: read-all` at column 0 |
| test_release_yml_structure.py | test_per_job_id_token_write | RED | GREEN | Task 1: per-job id-token/contents/attestations write |
| test_release_yml_structure.py | test_per_artifact_attest | RED | GREEN | Task 1: two attest-build-provenance invocations |
| test_release_yml_structure.py | test_sigstore_action_literal_present | RED | GREEN | Task 1: sigstore/gh-action-sigstore-python literal |
| test_release_yml_structure.py | test_sigstore_action_sha_pinned | RED | GREEN | Task 1: 40-char hex SHA on sigstore line |
| test_release_yml_structure.py | test_sigstore_step_timeout_minutes_5 | RED | GREEN | Task 1: timeout-minutes: 5 on sigstore step |
| test_release_yml_structure.py | test_every_uses_in_release_yml_sha_pinned | RED | GREEN | Task 1: every uses: is 40-char SHA-pinned |
| test_release_md_stop_before_tag.py | test_step_6_5_gitsign_inserted | RED | GREEN | Task 3: docs/RELEASE.md step 6.5 inserted |
| test_release_md_stop_before_tag.py | test_step_7_uses_tag_dash_s | RED | GREEN | Task 3: git tag -a swapped to git tag -s |
| test_release_md_stop_before_tag.py | test_steps_1_through_6_and_8_through_9_byte_identical | GREEN (preserved) | GREEN | Task 3: baseline preserved through insertion-only edit |
| test_decision_no_pypi.py | test_decision_file_exists | ERROR | GREEN | Task 3: .planning/decisions/no-pypi-in-v0.6.md created |
| test_decision_no_pypi.py | test_decision_file_has_terminator | ERROR | GREEN | Task 3: terminator literal landed |
| test_decision_no_pypi.py | test_project_md_references_decision_file | RED | GREEN | Task 3: .planning/PROJECT.md key-decisions row appended |
| test_release_verification.py | test_canonical_fixture_passes_wheel_check | SKIP | SKIP | binaries pending v0.6.0-rc1 rehearsal recording |
| test_release_verification.py | test_missing_issuer_refused | RED | GREEN | Task 2: argparse required=True for --cert-oidc-issuer |
| test_release_verification.py | test_wrong_issuer_refused | RED | GREEN | Task 2: explicit equality check + stderr diagnostic |
| test_release_verification.py | test_sbom_stub_returns_skipped | RED | GREEN | Task 2: check_sbom_signature returns ok=None |
| test_release_verification.py | test_full_run_all_checks_with_canonical_fixture | SKIP | SKIP | binaries pending v0.6.0-rc1 rehearsal recording |
| test_release_verification.py | test_expected_identity_template_invariant_is_documented | SKIP (script absent) | GREEN | Task 2: source contains `'refs/tags/{version}'` |
| test_release_verification.py | test_expected_issuer_constant_documented | SKIP (script absent) | GREEN | Task 2: source contains EXPECTED_ISSUER literal |
| test_release_verification.py | test_module_imports_cleanly | RED | GREEN | Task 2: byte-exact constants exposed at import time |
| test_release_verification.py | test_script_runs_via_subprocess | SKIP (script absent) | GREEN | Task 2: subprocess smoke against verify_release.py --check sbom |

**Wave 1 totals after flip:** 25 passed, 2 skipped, 0 failed, 0 errored (against the four Plan 01 test files); the two SKIPs are the canonical-fixture binary tests pending the v0.6.0-rc1 rehearsal recording (Manual-Only Verification per VALIDATION.md).

## Pinned SHAs Applied

| Owner/Repo | Version Tag | 40-char SHA | Verification Command Output |
|------------|-------------|-------------|-----------------------------|
| actions/checkout | v4.2.2 | `11bd71901bbe5b1630ceea73d27597364c9af683` | `gh api repos/actions/checkout/git/refs/tags/v4.2.2 --jq '.object.sha'` returns `11bd71901bbe5b1630ceea73d27597364c9af683` |
| actions/setup-python | v5.6.0 | `a26af69be951a213d495a4c3e4e4022e16d87065` | `gh api repos/actions/setup-python/git/refs/tags/v5.6.0 --jq '.object.sha'` returns `a26af69be951a213d495a4c3e4e4022e16d87065` |
| sigstore/gh-action-sigstore-python | v3.3.0 | `04cffa1d795717b140764e8b640de88853c92acc` | `gh api repos/sigstore/gh-action-sigstore-python/git/refs/tags/v3.3.0 --jq '.object.sha'` returns `04cffa1d795717b140764e8b640de88853c92acc` |
| actions/attest-build-provenance | v4.1.0 | `a2bbfa25375fe432b6a289bc6b6cd05ecd0c4c32` | `gh api repos/actions/attest-build-provenance/git/refs/tags/v4.1.0 --jq '.object.sha'` returns `a2bbfa25375fe432b6a289bc6b6cd05ecd0c4c32` |

All four SHAs match the RESEARCH.md Standard Stack values verified at planning time on 2026-05-29. The two attest-build-provenance SHAs are identical (one file, two invocations, per D-06 granularity).

## Byte-Identity Verification

| File or Section | Pre-Phase-52 State | Post-Phase-52 State | Status |
|------------------|---------------------|----------------------|--------|
| docs/RELEASE.md steps 1-6 (lines 122-141 pre-edit) | PRE_EDIT_STEPS_1_THROUGH_6 in tests/test_release_md_stop_before_tag.py | Same multi-line string present verbatim | byte-identical (insertion below preserves) |
| docs/RELEASE.md steps 8-9 (lines 145-157 pre-edit) | PRE_EDIT_STEPS_8_THROUGH_9 in tests/test_release_md_stop_before_tag.py | Same multi-line string present verbatim | byte-identical |
| .planning/PROJECT.md existing 4 rows (lines 76-81 pre-edit) | "Anthropic + Gemini ...", "CLI and web chat ...", "SQLite over Postgres ...", "Apache 2.0 license ..." | All four rows present unchanged; new row appended below | byte-identical (append-only) |
| pyproject.toml | (last touched in Phase 49) | (no change in Phase 52) | byte-identical (sigstore NEVER added per D-03; verified via `git diff pyproject.toml` returning empty) |
| .github/workflows/ci.yml | post-Phase-51 baseline | (no change in Phase 52) | byte-identical (Phase 52 owns the NEW release.yml file only; ci.yml is Phase 51's surface) |

## D-09 Atomicity Verification

```
$ git log -1 --name-only ebf2a47
commit ebf2a476e8df52d25ef3fc7c780508a870bc80c5
Author: Ridou <[redacted]>
Date:   Fri May 29 21:15:56 2026 +0800

    feat(52-02): land no-pypi-in-v0.6 decision + RELEASE.md gitsign + PROJECT.md key-decisions (SIGN-03 + SIGN-05)

.planning/PROJECT.md
.planning/decisions/no-pypi-in-v0.6.md
docs/RELEASE.md
```

Three files in one commit. The decision file, the PROJECT.md row, and the docs/RELEASE.md edits land atomically per D-09 / SIGN-05.

## Full Suite Results

```
$ pytest --tb=no -q
30 failed, 1017 passed, 5 skipped, 1 warning in 18.21s
```

The 30 failures are entirely in `tests/test_adapters_otel_pii_redaction.py` and are **pre-existing on main** (verified via `git worktree add /tmp/baseline origin/main && cd /tmp/baseline && pytest tests/test_adapters_otel_pii_redaction.py --tb=no -q` returning the same 15-30 failure set on the pre-Phase-51 baseline). Phase 52 changes do not touch `src/horus_os/adapters/otel_adapter.py`, `src/horus_os/observability/*`, or `tests/test_adapters_otel_pii_redaction.py`. Logged to `.planning/phases/52-signing-substrate-release-yml-new/deferred-items.md`.

Phase-52-scoped test deltas:

| Surface | Before Phase 52 Wave 1 | After Phase 52 Wave 1 |
|---------|------------------------|-------------------------|
| tests/test_release_yml_structure.py | 9 RED + 3 PASS | 12 PASS |
| tests/test_release_md_stop_before_tag.py | 2 RED + 1 PASS | 3 PASS |
| tests/test_decision_no_pypi.py | 1 RED + 2 ERROR | 3 PASS |
| tests/test_release_verification.py | 4 RED + 5 SKIP | 7 PASS + 2 SKIP (canonical-fixture rehearsal pending) |
| tests/test_contribution_gate_pitfalls/ (Phase 51 PR-time gate) | 11 PASS | 11 PASS (release.yml passes CIHARD-02 + CIHARD-03 + CIHARD-04 by construction) |

No new failures introduced by Phase 52 changes.

## Phase 52 Requirements Completion

| Requirement | Owner Task | Tests Flipped GREEN |
|-------------|------------|---------------------|
| SIGN-01 | Task 1 | test_release_yml_exists, test_on_release_published_trigger, test_top_level_permissions_read_all, test_per_job_id_token_write, test_sigstore_action_literal_present, test_sigstore_action_sha_pinned, test_sigstore_step_timeout_minutes_5, test_every_uses_in_release_yml_sha_pinned |
| SIGN-02 | Task 1 | test_per_artifact_attest (two attest-build-provenance invocations per D-06) |
| SIGN-03 | Task 3 | test_step_6_5_gitsign_inserted, test_step_7_uses_tag_dash_s, test_steps_1_through_6_and_8_through_9_byte_identical (preserved) |
| SIGN-04 | Task 2 | test_missing_issuer_refused, test_wrong_issuer_refused, test_sbom_stub_returns_skipped, test_module_imports_cleanly, test_expected_identity_template_invariant_is_documented, test_expected_issuer_constant_documented, test_script_runs_via_subprocess; test_canonical_fixture_passes_wheel_check and test_full_run_all_checks_with_canonical_fixture remain SKIPPED until v0.6.0-rc1 rehearsal recording |
| SIGN-05 | Task 3 | test_decision_file_exists, test_decision_file_has_terminator, test_project_md_references_decision_file |

All five SIGN-NN requirements have at least one production assertion flipped GREEN. The two SKIPPED tests are blocked on Manual-Only Verifications (VALIDATION.md row 1) and are explicitly out of scope for this plan per Plan 01 acceptance criteria.

## Deviations from Plan

None of substance. All three tasks executed exactly as written. Three minor mechanical notes:

1. `ruff format` reformatted `scripts/verify_release.py` (cosmetic line-wrap of one f-string concatenation; no semantic change). Tests still pass after format.
2. The initial release.yml carried the literal phrase "`timeout-minutes: 5`" inside a comment, which raised the raw-grep count to 2 even though only one structural occurrence existed. Re-worded the comment to "per-step five-minute timeout" so the literal appears exactly once (the acceptance criterion explicitly pins count == 1). The structural test (`test_sigstore_step_timeout_minutes_5`) was always passing because it walks the step block, not raw grep, but the documented acceptance count is now satisfied.
3. Pre-existing em-dashes in `.planning/PROJECT.md` lines 32-109 (predate Phase 52) were left in place per the deviation rule scope boundary. The newly-appended row at line 82 is em-dash-free as required by D-09 and CLAUDE.md HR3. Pre-existing failures in `tests/test_adapters_otel_pii_redaction.py` similarly fall outside Phase 52 scope (signing substrate); logged in `deferred-items.md`.

## Hand-off Notes

**For Phase 53 (SBOM generation + signing):**
- `release.yml` sigstore step's `inputs:` field is exactly `./dist/*.whl ./dist/*.tar.gz`. Append ` ./dist/*.sbom.json` (one whitespace-separated glob) to widen for SBOM coverage per D-10. No restructure needed.
- Insert the cyclonedx-py environment step between `python -m build` (step 4) and `Sign artifacts (sigstore keyless OIDC)` (step 5).
- Append a third `actions/attest-build-provenance` invocation with `subject-path: 'dist/*.sbom.json'` after the existing two (per D-06 per-artifact granularity).
- In `scripts/verify_release.py`, flip `check_sbom_signature` from the stub returning `CheckResult(ok=None, diagnostic="SKIPPED - Phase 53 lands SBOM generation + signing")` to an active subprocess call mirroring `_sigstore_verify`. The dispatch list and CLI choices tuple already include `"sbom"`; no parser changes needed. This is the surgical one-line + ~10-line function-body diff Phase 53 inherits.

**For Phase 56 (RUNBOOK + sibling decision files):**
- `docs/RELEASE.md` step 6.5 forward-references `docs/MAINTAINER-RUNBOOK.md`. Land the runbook with the gitsign one-time configuration prose (the four `git config --global ...` commands from RESEARCH.md Code Examples §3 lines 779-787).
- The `.planning/decisions/` directory now exists with one file. Phase 56 adds `sigstore-keyless.md`, `no-cla.md`, `no-stale-bot.md`, and `sbom-cyclonedx.md` siblings using the same shape (H1 heading + `**Decision (final, until revisited):**` terminator + cross-ref from `.planning/PROJECT.md` Key Decisions table append).

**For Phase 57 (release-gate extension):**
- `release.yml` contains the literal `sigstore/gh-action-sigstore-python` that the `release-workflow-signing-present` check greps for. Test against the file at `.github/workflows/release.yml`.
- Every `uses:` in `release.yml` is SHA-pinned to a 40-char hex commit. The `actions-pinned-by-sha` check can reuse Phase 51's `_USES_PATTERN` + `_ALLOWED_REF` regex against the new file.
- A future `no-pypi-token-secret` audit check (per PITFALLS.md Pitfall 9) can shell out to `gh secret list --json name` and assert no secret with `PYPI` in its name exists.

**For Phase 58 (TEST-24 + canonical-fixture binaries):**
- `tests/fixtures/sigstore/canonical/` has the README.md (Plan 01 deliverable). The binary `.whl` + `.sigstore[.json]` files land at v0.6.0-rc1 rehearsal time per VALIDATION.md Manual-Only Verifications row 1; instructions are in the README.
- The sibling `tests/fixtures/sigstore/wrong_identity/` directory is the Phase 58 TEST-24 deliverable. Use the same filename convention (`<wheel>.whl` + `<wheel>.whl.sigstore[.json]`); the wrong-identity bundle should be signed under a different workflow path (e.g., `someone-elses-repo/.github/workflows/release.yml@refs/tags/0.6.0-rc1`) so `verify_release.py` rejects it.

## Self-Check

File existence check:

```
FOUND: .github/workflows/release.yml
FOUND: scripts/verify_release.py
FOUND: .planning/decisions/no-pypi-in-v0.6.md
FOUND: docs/RELEASE.md (modified)
FOUND: .planning/PROJECT.md (modified)
```

Commit existence check:

```
FOUND: cb8a504 feat(52-02): add release.yml signing substrate (SIGN-01 + SIGN-02)
FOUND: 615b754 feat(52-02): add verify_release.py five-check trust-chain verifier (SIGN-04)
FOUND: ebf2a47 feat(52-02): land no-pypi-in-v0.6 decision + RELEASE.md gitsign + PROJECT.md key-decisions (SIGN-03 + SIGN-05)
```

Wave 1 verification re-run on demand:

```
$ pytest tests/test_release_verification.py tests/test_release_yml_structure.py \
         tests/test_release_md_stop_before_tag.py tests/test_decision_no_pypi.py --tb=no -q
25 passed, 2 skipped in 0.06s

$ pytest tests/test_contribution_gate_pitfalls/ --tb=no -q
11 passed in 0.02s

$ ruff check . && ruff format --check .
All checks passed!
242 files already formatted

$ git diff pyproject.toml
(empty, D-03 zero-base-dep hard rule honored)

$ python scripts/verify_release.py --version 0.6.0-rc1 \
    --cert-oidc-issuer https://token.actions.githubusercontent.com --check sbom
SKIP  sbom-signature: SKIPPED - Phase 53 lands SBOM generation + signing
$ echo $?
0

$ python scripts/verify_release.py --version 0.6.0-rc1
verify_release.py: error: the following arguments are required: --cert-oidc-issuer
$ echo $?
2

$ python scripts/verify_release.py --version 0.6.0-rc1 \
    --cert-oidc-issuer https://example.com/oauth
FAIL  verify_release: --cert-oidc-issuer must equal 'https://token.actions.githubusercontent.com', got 'https://example.com/oauth'
$ echo $?
1
```

## Self-Check: PASSED
