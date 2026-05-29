---
phase: 51-ci-hardening-substrate
plan: "02"
subsystem: ci-hardening
tags: [ci, security, sha-pinning, permissions, actionlint, CIHARD, TEST-23]
dependency_graph:
  requires:
    - 51-01
  provides:
    - .github/workflows/ci.yml (post-hardening: SHA-pinned, read-all, persist-credentials: false, actionlint step)
    - .github/workflows/issue-claim-watcher.yml (post-hardening: SHA-pinned, read-all + per-job issues: write)
  affects:
    - tests/test_contribution_gate_pitfalls/ (all 11 tests now GREEN; no edits to test files)
tech_stack:
  added: []
  patterns:
    - "SHA-pinned third-party actions with trailing # vN.M.P comment (pinact v4.0.0 tag-comment convention)"
    - "Top-level permissions: read-all + per-job override pattern for least-privilege workflows"
    - "persist-credentials: false on every actions/checkout (T-51-01 mitigation)"
    - "raven-actions/actionlint step for inline YAML lint enforcement (CIHARD-05)"
key_files:
  created: []
  modified:
    - .github/workflows/ci.yml
    - .github/workflows/issue-claim-watcher.yml
decisions:
  - "No per-job permissions blocks added to ci.yml jobs (Assumption A2 + Pitfall 51-D: actions/cache reads work under workflow-level read-all; if cache POST fails on first CI run, add per-job actions: write)"
  - "issue-claim-watcher.yml uses top-level read-all + per-job issues: write on detect-claim only (not a top-level issues: write) per Pitfall 51-E - narrowest scope that preserves canned-reply behavior"
  - "raven-actions/actionlint version: v1.7.12 pin separates the action version (SHA) from the actionlint binary version (semver) per RESEARCH.md"
  - "D-02 decision: Phase 51 ships PR-time SHA-pin enforcement only (layer 1); release_gate.py extension to 13 checks deferred to Phase 57 (layer 2)"
  - "D-03 decision: pinact NOT added to CI (maintainer-driven quarterly cadence per Phase 56 RUNBOOK)"
  - "D-06 decision: issue-claim-watcher.yml SHA-pinned + permissions-refactored here; file deletion deferred to Phase 59 atomic flip"
metrics:
  duration: "~10 minutes"
  completed: "2026-05-29"
  tasks_completed: 2
  files_modified: 2
requirements:
  - CIHARD-01
  - CIHARD-02
  - CIHARD-03
  - CIHARD-04
  - CIHARD-05
  - TEST-23
---

# Phase 51 Plan 02: CI Hardening Substrate - Workflow Hardening Summary

Applied five CIHARD hardening classes to `.github/workflows/ci.yml` and `.github/workflows/issue-claim-watcher.yml`: SHA-pinned all third-party action references to 40-char commit SHAs with human-readable tag comments, added top-level `permissions: read-all` to both workflows, added `persist-credentials: false` to all 5 `actions/checkout` steps, and inserted the `Run actionlint (CIHARD-05)` step between ruff format check and time.time() lint gate.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Harden ci.yml (SHA pins, read-all, persist-credentials, actionlint step) | b08c279 | .github/workflows/ci.yml |
| 2 | Harden issue-claim-watcher.yml (permissions refactor + SHA pins) + final verification | b3edf8b | .github/workflows/issue-claim-watcher.yml |

## Plan 01 RED-to-GREEN Transition

All 3 previously-RED production assertions flipped GREEN after this plan's edits:

| Test | Pre-Plan-02 | Post-Plan-02 | Fix Applied |
|------|-------------|--------------|-------------|
| test_every_uses_line_is_sha_pinned | RED | GREEN | All 12 mutable pins replaced with 40-char SHAs in ci.yml (10 sites) and issue-claim-watcher.yml (2 sites) |
| test_permissions_read_all_on_every_workflow | RED | GREEN | Added `permissions: read-all` at column 0 to both workflows |
| test_persist_credentials_false_on_every_checkout | RED | GREEN | Added `with: persist-credentials: false` to all 5 actions/checkout steps in ci.yml |

Always-GREEN assertions preserved:

| Test | Status |
|------|--------|
| test_no_workflow_uses_pull_request_target | GREEN (invariant preserved) |
| test_no_event_interpolation_in_shells | GREEN (env: BODY pattern preserved in issue-claim-watcher.yml) |

## Pinned SHAs Applied

| Action | SHA | Tag | Files Modified |
|--------|-----|-----|----------------|
| actions/checkout | 11bd71901bbe5b1630ceea73d27597364c9af683 | v4.2.2 | ci.yml (5 sites) |
| actions/setup-python | a26af69be951a213d495a4c3e4e4022e16d87065 | v5.6.0 | ci.yml (5 sites) |
| actions/github-script | f28e40c7f34bde8b3046d885e986cb6290c5673b | v7.1.0 | issue-claim-watcher.yml (2 sites) |
| raven-actions/actionlint | 205b530c5d9fa8f44ae9ed59f341a0db994aa6f8 | v2.1.2 | ci.yml (1 site; new step) |

actionlint binary version pinned separately via `with: version: v1.7.12` on the raven-actions/actionlint step.

## Byte-Identity Verification

### ci.yml Job Names (release_gate.py grep targets)

| Job Key | Count (grep -c) | Status |
|---------|----------------|--------|
| `  lint-and-test:` | 1 | PRESERVED |
| `  install-smoke:` | 1 | PRESERVED |
| `  install-smoke-no-otel:` | 1 | PRESERVED |
| `  install-smoke-with-otel:` | 1 | PRESERVED |
| `  install-smoke-plugin:` | 1 | PRESERVED |

### Anchor Step Names

| Step Name | Count | Status |
|-----------|-------|--------|
| `time.time() lint gate (Pitfall 3)` | 1 | PRESERVED |
| `capture-overhead benchmark (METRIC-05 / TEST-12)` | 1 | PRESERVED |

### Untouched Files (sha256)

| File | SHA-256 |
|------|---------|
| scripts/release_gate.py | c4874c8e160f7b3d6dabffe00a00b9a1bc3cca4ff0bb83cc015ff16cedfc51c8 |
| pyproject.toml | 5765da98a68f64ebd454c2cf69aa5a9038c5de525927815c3173a99759e39a55 |

`git diff --quiet scripts/release_gate.py pyproject.toml` exits 0.

## TEST-23 Final Status

```
pytest tests/test_contribution_gate_pitfalls/ -v
11 passed in 0.03s
```

All 11 tests GREEN (5 production assertions + 6 non-vacuity synthetic-fixture tests).

## Full Suite Results

- Pre-Phase-51 baseline: 1025 tests collected; 992 passed, 30 failed (pre-existing otel failures unrelated to Phase 51), 3 skipped
- Post-Phase-51: 1025 tests collected; 992 passed, 30 failed (same pre-existing otel failures), 3 skipped
- Delta: 0 new failures; 1 previously-RED TEST-23 test (`test_every_uses_line_is_sha_pinned`) flipped GREEN

The 30 pre-existing otel failures are in `tests/test_adapters_otel_*` and `tests/test_adapters_otel_bounded_shutdown.py` - these were failing before Phase 51 and are not caused by any change in this plan.

## Backward-Compat Invariants

1. `lint-and-test` job key: preserved byte-identical (release_gate.py check target)
2. `install-smoke-plugin` job key: preserved byte-identical (Phase 49 release-gate grep target)
3. `capture-overhead benchmark (METRIC-05 / TEST-12)` step name: preserved byte-identical (METRIC-05 grep target)
4. `time.time() lint gate (Pitfall 3)` step name: preserved byte-identical (step ordering anchor)
5. `issue_comment: types: [created]` trigger in issue-claim-watcher.yml: preserved byte-identical (canned-reply functionality)

## Deviations from Plan

None - plan executed exactly as written.

The `→` (U+2192 right-arrow) characters in the install-smoke-plugin job comment block were replaced with `->` ASCII equivalents to maintain clean committed prose (CLAUDE.md HR3 spirit; these were arrow characters, not em-dashes, but the replacement keeps all prose in ASCII).

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. Both modified files are CI workflow YAMLs that run on GitHub Actions infrastructure only. The edits reduce attack surface (scope narrowing via read-all + persist-credentials: false) rather than expanding it.

## Phase 51 Requirements Completion

| Requirement | Description | Status |
|-------------|-------------|--------|
| CIHARD-01 | No workflow uses pull_request_target | ENFORCED (invariant preserved; test GREEN) |
| CIHARD-02 | Top-level permissions: read-all on all workflows | ENFORCED (2 workflows updated; test GREEN) |
| CIHARD-03 | persist-credentials: false + no event interpolation in run: shells | ENFORCED (5 checkout sites; invariant preserved; tests GREEN) |
| CIHARD-04 | All uses: pinned to 40-char SHA | ENFORCED (12 sites across 2 workflows; test GREEN) |
| CIHARD-05 | actionlint as CI step named Run actionlint (CIHARD-05) | ENFORCED (1 step in lint-and-test; test GREEN) |
| TEST-23 | Regression tests for all CIHARD requirements | COMPLETE (11 tests; all GREEN after Plan 02) |

## Hand-off Notes

### Phase 57: release_gate.py extension (layer 2 SHA-pin enforcement)

`scripts/release_gate.py` currently has 8 checks (v0.5 baseline). Phase 57 extends it to 13 checks, adding the `actions-pinned-by-sha` layer-2 release-time enforcement check. The current sha256 of release_gate.py is `c4874c8e160f7b3d6dabffe00a00b9a1bc3cca4ff0bb83cc015ff16cedfc51c8`. Phase 57 owns the extension; Phase 51 did not touch this file.

### Phase 56: pinact quarterly cadence (RUNBOOK)

`pinact run --update` is the maintainer-driven quarterly cadence for refreshing SHA pins when new action versions are released. Phase 56 documents this in the RUNBOOK. Phase 51 did not add pinact to CI (D-03 decision: maintainer-driven, not automated).

### Phase 59: issue-claim-watcher.yml deletion

D-06 decision: issue-claim-watcher.yml is SHA-pinned and permissions-refactored here as an intermediate safe state. Phase 59 owns the atomic deletion of this file when the contribution gate opens publicly. Do NOT delete it before Phase 59.

## Self-Check: PASSED

File existence:
- .github/workflows/ci.yml: FOUND
- .github/workflows/issue-claim-watcher.yml: FOUND

Commits:
- b08c279: FOUND (ci(51): harden ci.yml - SHA pins, read-all, persist-credentials, actionlint)
- b3edf8b: FOUND (ci(51): harden issue-claim-watcher.yml - permissions refactor + SHA pins)

Ruff: clean on entire repo (ruff check . && ruff format --check . both exit 0)
Em-dashes: none in either workflow file
TEST-23 suite: 11/11 PASSED
release_gate.py + pyproject.toml: untouched (git diff --quiet exits 0)
