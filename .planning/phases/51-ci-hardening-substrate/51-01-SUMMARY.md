---
phase: 51-ci-hardening-substrate
plan: "01"
subsystem: ci-hardening
tags: [ci, security, regression-tests, cihard, TEST-23]
dependency_graph:
  requires: []
  provides:
    - tests/test_contribution_gate_pitfalls/__init__.py
    - tests/test_contribution_gate_pitfalls/test_pitfall_01_pull_request_target.py
    - tests/test_contribution_gate_pitfalls/test_pitfall_02_action_sha_pinning.py
    - tests/test_contribution_gate_pitfalls/test_ci_hardening_workflow_structure.py
  affects:
    - .github/workflows/ci.yml (scanned; Plan 02 will update it)
    - .github/workflows/issue-claim-watcher.yml (scanned; Plan 02 will update it)
tech_stack:
  added: []
  patterns:
    - "stdlib re regex scanning over .github/workflows/*.yml (no PyYAML)"
    - "sorted() glob iteration for cross-OS determinism"
    - "helper functions parametrized on workflows_dir for non-vacuity tmp_path tests"
    - "RED-by-design production assertions (Wave 0 signal; Plan 02 turns GREEN)"
key_files:
  created:
    - tests/test_contribution_gate_pitfalls/__init__.py
    - tests/test_contribution_gate_pitfalls/test_pitfall_01_pull_request_target.py
    - tests/test_contribution_gate_pitfalls/test_pitfall_02_action_sha_pinning.py
    - tests/test_contribution_gate_pitfalls/test_ci_hardening_workflow_structure.py
  modified: []
decisions:
  - "Used helper functions _scan_workflow_dir / _find_*() parametrized on workflows_dir so non-vacuity tests reuse scanner logic against tmp_path fixtures"
  - "Extended _EVENT_INTERPOLATION to cover github.head_ref and github.base_ref per OQ-3 RESOLVED in RESEARCH.md"
  - "test_scanner_accepts_synthetic_local_action_ref tests the ./ allowlist branch (Pitfall 51-C coverage)"
  - "test_scanner_catches_synthetic_head_ref_interpolation ensures the head_ref/base_ref alternative in _EVENT_INTERPOLATION is non-vacuously tested"
metrics:
  duration: "~5 minutes"
  completed: "2026-05-29"
  tasks_completed: 2
  files_created: 4
requirements:
  - TEST-23
  - CIHARD-01
  - CIHARD-03
  - CIHARD-04
---

# Phase 51 Plan 01: CI Hardening Substrate - Contribution Gate Test Scaffolding Summary

Wave 0 regression test suite under `tests/test_contribution_gate_pitfalls/` using stdlib re
scanning over `.github/workflows/*.yml` - four-file scaffolding for CIHARD-01, CIHARD-03,
and CIHARD-04 enforcement at PR-time with non-vacuity synthetic fixtures.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Package marker + test_pitfall_01 + test_pitfall_02 | 29b42ca | tests/test_contribution_gate_pitfalls/__init__.py, test_pitfall_01_pull_request_target.py, test_pitfall_02_action_sha_pinning.py |
| 2 | test_ci_hardening_workflow_structure.py (CIHARD-02 + CIHARD-03) | ea7d0e7 | tests/test_contribution_gate_pitfalls/test_ci_hardening_workflow_structure.py |

## Production Assertions: RED vs GREEN State

### PASSING assertions (already-compliant invariants - Wave 0 GREEN)

| Test | Requirement | Why PASSING |
|------|-------------|-------------|
| test_no_workflow_uses_pull_request_target | CIHARD-01 | Neither ci.yml nor issue-claim-watcher.yml contains pull_request_target |
| test_no_event_interpolation_in_shells | CIHARD-03 second clause | issue-claim-watcher.yml passes github.event.comment.body via env: BODY, not directly in run: shell |

### FAILING assertions (RED-by-design - Plan 02 turns GREEN)

| Test | Requirement | Why FAILING (expected) |
|------|-------------|------------------------|
| test_every_uses_line_is_sha_pinned | CIHARD-04 | ci.yml has 10 mutable pins (@v4/@v5); issue-claim-watcher.yml has 2 (@v7) |
| test_permissions_read_all_on_every_workflow | CIHARD-02 | ci.yml has no top-level permissions: block |
| test_persist_credentials_false_on_every_checkout | CIHARD-03 first clause | All 5 actions/checkout steps in ci.yml lack persist-credentials: false |

## Non-Vacuity Coverage (all PASS)

All six non-vacuity synthetic-fixture tests pass, proving each scanner fires on known violations:

| Test | Scanner Proven Non-Vacuous |
|------|---------------------------|
| test_scanner_catches_synthetic_sha_violation | CIHARD-04 mutable-pin regex |
| test_scanner_accepts_synthetic_local_action_ref | CIHARD-04 local-action allowlist (./ branch) |
| test_scanner_catches_synthetic_missing_permissions | CIHARD-02 top-level permissions regex |
| test_scanner_catches_synthetic_checkout_without_persist_credentials | CIHARD-03 persist-credentials lookahead |
| test_scanner_catches_synthetic_event_interpolation | CIHARD-03 github.event.* branch |
| test_scanner_catches_synthetic_head_ref_interpolation | CIHARD-03 github.head_ref/base_ref branch (OQ-3 RESOLVED) |

## Test Collection Counts

```
pytest tests/test_contribution_gate_pitfalls/ --collect-only -q
11 tests collected
```

- test_pitfall_01_pull_request_target.py: 1
- test_pitfall_02_action_sha_pinning.py: 3
- test_ci_hardening_workflow_structure.py: 7

## Deviations from Plan

None - plan executed exactly as written.

The `_scan_workflow_dir` helper in test_pitfall_02 and the three `_find_*` helpers in
test_ci_hardening_workflow_structure are parametrized on `workflows_dir: Path` exactly as
specified in the plan's `<action>` block, enabling non-vacuity tests to use tmp_path.

## Self-Check: PASSED

File existence:
- tests/test_contribution_gate_pitfalls/__init__.py: FOUND
- tests/test_contribution_gate_pitfalls/test_pitfall_01_pull_request_target.py: FOUND
- tests/test_contribution_gate_pitfalls/test_pitfall_02_action_sha_pinning.py: FOUND
- tests/test_contribution_gate_pitfalls/test_ci_hardening_workflow_structure.py: FOUND

Commits:
- 29b42ca: FOUND (test(51): add contribution-gate pitfall tests 01+02 and package marker)
- ea7d0e7: FOUND (test(51): add CIHARD-02+03 structural workflow assertion tests)

Ruff: clean on all 4 files
Em-dashes: none in any file
parents[2]: present in all scanner files
