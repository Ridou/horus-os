# Phase 51: CI hardening substrate - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-29
**Phase:** 51-ci-hardening-substrate
**Mode:** `--auto` (no user prompts; recommended options auto-selected; alternatives logged here for audit)
**Areas discussed:** actionlint invocation shape, SHA-pin enforcement mechanism, pinact operational model, TEST-23 regression-test surface organization, pull_request_target lint enforcement, issue-claim-watcher.yml hardening timing

---

## actionlint invocation shape

| Option | Description | Selected |
|--------|-------------|----------|
| New step in `lint-and-test` job | Add `Run actionlint (CIHARD-05)` step inside ci.yml's existing lint-and-test job. Single workflow file footprint; job-name byte-identity preserved. | ✓ |
| Standalone `actionlint.yml` workflow | New top-level workflow file for actionlint only. More files but cleaner job-isolation. | |
| Inline curl download + binary execution | Skip the action wrapper; download the binary in the step itself. Avoids one third-party action dependency. | |

**User's choice:** Auto-selected (option 1 — new step in lint-and-test)
**Notes:** `rhysd/actionlint@<sha>` action recommended; inline curl is fallback if action becomes unreliable at lock time. Step name MUST contain literal `(CIHARD-05)` for grep-based regression tests.

---

## SHA-pin enforcement mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Two-layer (actionlint + release-gate regex) | actionlint at PR-time + scripts/release_gate.py regex at release-time. Mirrors v0.5 Phase 48 two-layer surface lock. | ✓ |
| Single layer (actionlint only) | Trust the PR-time check; no release-gate hook. Lower cost. | |
| Single layer (release-gate regex only) | Skip actionlint; gate enforces at release. Misses PR-time signal. | |

**User's choice:** Auto-selected (option 1 — two-layer)
**Notes:** The release-gate `actions-pinned-by-sha` check lands in Phase 57, not Phase 51. Phase 51's only contribution is the SHA rewrite itself + actionlint PR-time enforcement.

---

## pinact operational model

| Option | Description | Selected |
|--------|-------------|----------|
| Maintainer-driven (quarterly + Dependabot review) | `pinact run --update` is a documented manual command, run quarterly + on each Dependabot github-actions PR review. | ✓ |
| CI auto-PR (weekly cron) | A workflow runs pinact on a schedule and opens a PR. Requires `contents: write`; expands attack surface. | |
| Pre-commit hook | pinact runs locally on every commit touching `.github/workflows/`. Inconsistent across contributor environments. | |

**User's choice:** Auto-selected (option 1 — maintainer-driven)
**Notes:** Documented in `docs/MAINTAINER-RUNBOOK.md` (Phase 56). Dependabot github-actions already proposes SHA bumps; pinact is for manual refresh on demand. Mirrors v0.5 STOP-BEFORE-TAG opt-in posture.

---

## TEST-23 regression-test surface organization

| Option | Description | Selected |
|--------|-------------|----------|
| Three files (PITFALL-01, PITFALL-02, structural) | `test_pitfall_01_pull_request_target.py` + `test_pitfall_02_action_sha_pinning.py` + `test_ci_hardening_workflow_structure.py`. Mirrors v0.5 TEST-17 1:1-with-PITFALLS shape. | ✓ |
| One monolithic file | `test_ci_hardening.py` with all assertions. Lower file count but worse pitfall-to-test traceability. | |
| Five files (one per CIHARD req) | `test_cihard_01.py..test_cihard_05.py`. Maximum granularity; weak signal for which PITFALL is being regression-tested. | |

**User's choice:** Auto-selected (option 1 — three files)
**Notes:** PITFALL 1 + PITFALL 2 are the two highest-blast-radius pitfalls and deserve standalone files. CIHARD-02/03 are structural workflow-shape assertions and cluster cleanly into a third file. Files MUST live under `tests/test_contribution_gate_pitfalls/`, NOT `tests/test_plugin_pitfalls/`.

---

## pull_request_target lint enforcement

| Option | Description | Selected |
|--------|-------------|----------|
| Both layers (PR-time test + release-gate check) | Belt-and-braces. test_pitfall_01 + actionlint catch at PR; release_gate.py catches at tag. | ✓ |
| PR-time only | One layer is sufficient if discipline holds. Cheaper but less defense-in-depth. | |
| Release-gate only | Catches the case where someone adds the trigger between merge and tag, but lets bad PRs merge. | |

**User's choice:** Auto-selected (option 1 — both layers)
**Notes:** Matches v0.5's docs-drift dual-enforcement pattern (build_manifest_schema.py + release_gate.py docs-drift check). Escape-hatch grammar (`# SECURITY:` comment + `safe-to-test` label gate) is documented in CIHARD-01 but unused in v0.6.

---

## issue-claim-watcher.yml hardening timing

| Option | Description | Selected |
|--------|-------------|----------|
| SHA-pin in Phase 51, delete in Phase 59 | Harden the file now even though it gets deleted at gate-flip. Eliminates the ~7-phase exposure window. | ✓ |
| Skip Phase 51 hardening; delete only in Phase 59 | Save the SHA-pin diff since the file is deleted soon anyway. Leaves ~7 phases of supply-chain exposure. | |
| Delete in Phase 51 instead of Phase 59 | Pull the deletion forward. Inconsistent with FLIP-01's atomic-commit rule. | |

**User's choice:** Auto-selected (option 1 — pin now, delete later)
**Notes:** Phase 51-to-Phase 59 is ~7 phases; tj-actions-style retargeting is a real risk in that window. Cost of SHA-pinning a soon-deleted file is one line of YAML diff; cost of leaving it unpinned is real exposure. Pin it; delete it; move on.

---

## Claude's Discretion

The following implementation details are intentionally left to the planner. CONTEXT.md notes them under `### Claude's Discretion`:

- **Exact `actionlint` invocation form** (action vs inline curl): depends on action-availability at lock time.
- **Exact SHA values for every action `uses:` rewrite:** planner uses `pinact run --update` or `gh api` at plan-time to resolve.
- **Whether the three regression tests use `yaml.safe_load` or text/regex parsing:** either is acceptable; text/regex is cheaper and consistent with `scripts/release_gate.py`; YAML is more robust to formatting variance.

## Deferred Ideas

Ideas surfaced during analysis that belong in other phases (captured here to prevent loss):

- **`actions-pinned-by-sha` release-gate check** — deferred to Phase 57 (REL-14). Phase 51 does the SHA rewrite; Phase 57 adds the regression check.
- **`pinact` quarterly cadence documented in `docs/MAINTAINER-RUNBOOK.md`** — deferred to Phase 56 (RUNBOOK-01).
- **`zizmor` workflow security audit** — deferred to Phase 54 (DEPBOT-03). Overlaps with actionlint but covers different rule classes.
- **`pull_request_target` escape-hatch fixture + test** — only ships if a future v0.7+ phase introduces a legitimate `pull_request_target` use case.
- **Dependabot github-actions ecosystem PRs** — deferred to Phase 54 (DEPBOT-01). Will propose SHA bumps against the pins Phase 51 lands.

---

*Phase: 51-ci-hardening-substrate*
*Log written: 2026-05-29*
