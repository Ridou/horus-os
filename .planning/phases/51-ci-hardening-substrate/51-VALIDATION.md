---
phase: 51
slug: ci-hardening-substrate
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-29
---

# Phase 51 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing v0.5 substrate) + GitHub Actions runner-level (`actionlint`) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`); `.github/workflows/ci.yml` for actionlint step |
| **Quick run command** | `pytest tests/test_contribution_gate_pitfalls/ -v` |
| **Full suite command** | `pytest -v && ruff check . && ruff format --check .` |
| **Estimated runtime** | ~8 seconds (3 new files, regex over 2 workflow files; actionlint adds ~5s in CI) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_contribution_gate_pitfalls/ -v` (≤8s)
- **After every plan wave:** Run `pytest -v && ruff check . && ruff format --check .` (~25s for the full pytest suite)
- **Before `/gsd-verify-work`:** Full suite must be green; ci.yml workflow-lint job must pass; `actionlint .github/workflows/` must exit 0 locally
- **Max feedback latency:** ~25 seconds for full suite; ~8 seconds for the targeted regression files

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 51-01-01 | 01 | 1 | CIHARD-04 | PITFALL-2 | Every third-party `uses:` is `@<40-hex>`; no `@v<N>` or `@main` survives in tree | regex+unit | `pytest tests/test_contribution_gate_pitfalls/test_pitfall_02_action_sha_pinning.py -v` | ❌ W0 | ⬜ pending |
| 51-01-02 | 01 | 1 | CIHARD-02 | — | Top-level `permissions: read-all` present on every workflow | yaml-struct | `pytest tests/test_contribution_gate_pitfalls/test_ci_hardening_workflow_structure.py::test_permissions_read_all_on_every_workflow -v` | ❌ W0 | ⬜ pending |
| 51-01-03 | 01 | 1 | CIHARD-03 | PITFALL-1 | Every `actions/checkout` step sets `persist-credentials: false` | yaml-struct | `pytest tests/test_contribution_gate_pitfalls/test_ci_hardening_workflow_structure.py::test_persist_credentials_false_on_every_checkout -v` | ❌ W0 | ⬜ pending |
| 51-01-04 | 01 | 1 | CIHARD-03 | PITFALL-1 | No `${{ github.event.* }}`, `${{ github.head_ref }}`, `${{ github.base_ref }}` interpolation in any `run:` shell | regex | `pytest tests/test_contribution_gate_pitfalls/test_ci_hardening_workflow_structure.py::test_no_event_interpolation_in_shells -v` | ❌ W0 | ⬜ pending |
| 51-01-05 | 01 | 1 | CIHARD-01 | PITFALL-1 | No workflow declares a `pull_request_target` trigger (v0.6 invariant) | regex | `pytest tests/test_contribution_gate_pitfalls/test_pitfall_01_pull_request_target.py -v` | ❌ W0 | ⬜ pending |
| 51-01-06 | 01 | 1 | CIHARD-05 | — | `actionlint` step in ci.yml `lint-and-test` job named `Run actionlint (CIHARD-05)` exits 0 | grep+CI | `grep -F "(CIHARD-05)" .github/workflows/ci.yml` + CI run | ❌ W0 | ⬜ pending |
| 51-01-07 | 01 | 1 | TEST-23 | PITFALL-1+2 | All three regression files exist and exit 0; directory `tests/test_contribution_gate_pitfalls/` contains exactly `__init__.py` + 3 test files | pytest-collect | `pytest tests/test_contribution_gate_pitfalls/ --collect-only -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Note: Plan/wave numbers are placeholders — the planner sets the canonical numbering. Task IDs reflect the expected single-plan single-wave shape; if the planner splits across waves, this table updates during planning.*

---

## Wave 0 Requirements

- [ ] `tests/test_contribution_gate_pitfalls/__init__.py` — empty package marker (new directory)
- [ ] `tests/test_contribution_gate_pitfalls/test_pitfall_01_pull_request_target.py` — regex over `.github/workflows/*.yml`, asserts no `on: pull_request_target:` trigger (covers CIHARD-01)
- [ ] `tests/test_contribution_gate_pitfalls/test_pitfall_02_action_sha_pinning.py` — regex over `uses:` lines, asserts every third-party reference is `@<40-hex>` (covers CIHARD-04)
- [ ] `tests/test_contribution_gate_pitfalls/test_ci_hardening_workflow_structure.py` — structural assertions for CIHARD-02 + CIHARD-03 (top-level `permissions:`, `persist-credentials: false`, no shell interpolation of `github.event.*`)
- [ ] No new framework install — pytest already in `[dev]` (v0.5 substrate)
- [ ] No new test dependency — research confirmed stdlib `re` parsing is sufficient (no PyYAML added)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `actionlint` step actually runs in CI on PR triggers (not just exists in YAML) | CIHARD-05 | Requires a CI run; cannot be asserted from pytest | Open a PR that intentionally violates an actionlint rule (e.g., bad expression syntax); verify the `lint-and-test` job fails with actionlint output |
| `pinact run --update` produces no diff against committed pins | CIHARD-04 (maintainer cadence) | Optional local maintainer command; not in CI per D-03 | Maintainer runs `pinact run --update` locally; expect zero-diff (all pins current) at lock time |

---

## Nyquist Validation Dimensions (8)

Per RESEARCH.md `## Validation Architecture`:

1. **Functional correctness** — `actionlint` exits 0 on `.github/workflows/`; three TEST-23 regression files exit 0 against the post-Phase-51 tree
2. **Security regression** — fork-PR fixture (synthetic workflow with `pull_request_target` + checkout-PR-head) FAILS `test_pitfall_01` as expected; positive fixture (clean workflow) PASSES
3. **Mutable-pin regression** — fixture workflow with `@v4` action ref FAILS `test_pitfall_02` as expected
4. **Performance** — TEST-23 suite runtime ≤8s (regex over 2 workflow files is O(LOC))
5. **Documentation** — every CIHARD requirement appears in REQUIREMENTS.md with phase 51 mapping; CHANGELOG `[Unreleased]` gains a v0.6 entry (deferred to Phase 60)
6. **Compatibility** — `ci.yml` job names byte-identical post-Phase-51 (`grep -c "^  lint-and-test:" ci.yml` returns 1; same for `install-smoke:`, `install-smoke-otel:`, `install-smoke-plugin:`); release_gate.py untouched
7. **Maintainability** — `pinact run --update` produces zero diff at lock time; quarterly maintainer cadence documented in Phase 56 RUNBOOK
8. **Validation itself** — each TEST-23 file includes at least one negative fixture (synthetic violating YAML inline) proving the scanner is non-vacuous; mirrors v0.5 TEST-21 layer-2 idiom

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (3 new test files + `__init__.py`)
- [ ] No watch-mode flags
- [ ] Feedback latency < 25s (full suite); < 8s (targeted)
- [ ] `nyquist_compliant: true` set in frontmatter (after Wave 0 complete + suite green)

**Approval:** pending
