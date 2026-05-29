# Phase 51: CI hardening substrate - Context

**Gathered:** 2026-05-29
**Status:** Ready for planning
**Mode:** `--auto` (recommended options auto-selected; user review encouraged before /gsd-plan-phase)

<domain>
## Phase Boundary

Phase 51 hardens every existing horus-os GitHub Actions workflow against the two highest-blast-radius supply-chain incidents documented in `.planning/research/PITFALLS.md`: fork-PR secret leakage via `pull_request_target` (Ultralytics 8.3.41/42 Dec 2024, "testedbefore" Mar 2026, Spotipy GHSA) and mutable action-tag pin retargeting (tj-actions/changed-files CVE-2025-30066, ~23k repos compromised). It is a precondition phase: every downstream v0.6 phase (52 signing, 53 SBOM+audit, 54 Dependabot, 57 release-gate, 58 soft launch, 59 gate flip) consumes the SHA-pin + `permissions:` baseline this phase establishes. v0.6 ships with ZERO `pull_request_target` triggers because v0.5 tests use recorded provider responses and require no live secrets in fork CI.

**Owns:** CIHARD-01..05, TEST-23.
**Touches files:** `.github/workflows/ci.yml`, `.github/workflows/issue-claim-watcher.yml`, `scripts/release_gate.py`, `pyproject.toml` (lint extras), new `tests/test_contribution_gate_pitfalls/` directory.
**Does NOT touch:** any runtime code under `src/horus_os/`, any pricing/SBOM/sigstore tooling (those are Phases 52-54).
**Does NOT rename:** `ci.yml` job names (`lint-and-test`, `install-smoke`, `install-smoke-otel`, `install-smoke-plugin` are byte-identity contracts grep'd by release_gate.py per Phase 49 idiom).

</domain>

<decisions>
## Implementation Decisions

### actionlint invocation shape

- **D-01:** `actionlint` runs as a **new step inside the existing `lint-and-test` job in `ci.yml`** (not a new workflow file). Step name: `Run actionlint (CIHARD-05)`. Placement: after `Run ruff format check`, before `time.time() lint gate`.
- **Why:** Single-workflow-file footprint preserves the `ci.yml`-job-name byte-identity contract. Mirrors precedent of `lint_no_wallclock.py` invocation at `ci.yml:42`. Actionlint is itself a lint, so the `lint-and-test` job is the right home.
- **Invocation:** `rhysd/actionlint@<40-char-sha>` action (download + run); SHA pinned per CIHARD-04. Fall-back consideration: if the action ships with an outdated binary at lock time, replace with inline `curl -fSL https://github.com/rhysd/actionlint/releases/download/v<X.Y.Z>/actionlint_<X.Y.Z>_linux_amd64.tar.gz | tar -xzf - actionlint && ./actionlint -color`. Decision deferred to planner; either is acceptable.

### SHA-pin enforcement mechanism

- **D-02:** The `actions-pinned-by-sha` enforcement lives in **TWO layers**, mirroring the v0.5 Phase 48 two-layer surface lock (ruff + source-tree grep):
  - **Layer 1 (every-PR, fast):** `actionlint` flags non-SHA pins via its `expression` + `pyflakes-like` rules; this also catches `${{ github.event.* }}` interpolation in shells (CIHARD-03).
  - **Layer 2 (release-time, defense-in-depth):** `scripts/release_gate.py` gains an `actions-pinned-by-sha` check (added in Phase 57, not Phase 51). The check uses a regex over every `.github/workflows/*.yml` file asserting that each `uses:` value matches `^[^@]+@[0-9a-f]{40}$` (or starts with `./` for local actions). Anything else (`@v4`, `@main`, `@master`, short SHA, branch ref) fails the gate.
- **Why:** Regex is consistent with the existing 8 release-gate checks (all grep/regex-based). Phase 57 is the right home for the release-gate addition because it owns the 8 to 13 extension. Phase 51's contribution is only the SHA-pin rewrite itself + actionlint's PR-time enforcement.

### `pinact` operational model

- **D-03:** `pinact` is **maintainer-driven, not CI-automated**. Documented in `docs/MAINTAINER-RUNBOOK.md` (Phase 56) as a quarterly cadence command (`pinact run --update`) plus on every Dependabot `github-actions` ecosystem PR review. NOT added as a CI auto-PR; NOT added to release_gate.py.
- **Why:** Auto-pinact would either (a) overwrite Dependabot's diff and confuse the review queue or (b) require its own workflow with `contents: write` permission, expanding attack surface. Maintainer-driven mirrors the v0.5 STOP-BEFORE-TAG opt-in pattern. Dependabot github-actions PRs already propose SHA bumps; pinact is the maintainer's tool to refresh on demand.

### TEST-23 regression-test surface organization

- **D-04:** TEST-23 ships as **three files** in `tests/test_contribution_gate_pitfalls/`, mirroring v0.5's TEST-17 1:1-with-PITFALLS shape:
  - `test_pitfall_01_pull_request_target.py` — asserts no workflow has a `pull_request_target` trigger AND no workflow has both `pull_request_target` + an `actions/checkout` of PR HEAD; covers CIHARD-01.
  - `test_pitfall_02_action_sha_pinning.py` — regex over every `.github/workflows/*.yml` asserting every third-party `uses:` is `@<40-hex>`; allows `./` local actions; covers CIHARD-04.
  - `test_ci_hardening_workflow_structure.py` — structural assertions: top-level `permissions:` present on every workflow (CIHARD-02), every `actions/checkout` step sets `persist-credentials: false` (CIHARD-03), no `${{ github.event.* }}` interpolation in any `run:` shell line (CIHARD-03).
- **Why:** v0.5's `tests/test_plugin_pitfalls/` directory pattern is the established precedent (TEST-17 shipped 42 tests across 12 files mapped 1:1 with PITFALLS.md numbers). Continuing this shape makes the v0.6 pitfall-to-test mapping recognizable to anyone who reviewed v0.5. Three files is the minimum that lets PITFALL-1 and PITFALL-2 tests stand alone (they are the highest-blast-radius pitfalls), while the structural assertions for CIHARD-02/03 cluster cleanly together.

### `pull_request_target` lint enforcement

- **D-05:** `pull_request_target` is gated at **two enforcement layers**:
  - **PR-time:** `actionlint` flags it (every PR); `test_pitfall_01_pull_request_target.py` regression-asserts absence in the workflow tree (every PR, fails CI on regression).
  - **Release-time:** `scripts/release_gate.py` `actions-pinned-by-sha` check (Phase 57) ALSO greps for `pull_request_target` and fails if present without a `# SECURITY:` comment guard + `safe-to-test` label gate (CIHARD-01 escape-hatch documented but unused in v0.6).
- **Why:** Belt-and-braces matches v0.5's docs-drift dual-enforcement pattern (build_manifest_schema.py + release_gate.py docs-drift check). PR-time catches regressions before they merge; release-time catches the case where someone adds a trigger between merge and tag. The escape hatch shape is documented now so that if v0.7+ needs `pull_request_target` for a specific reason (e.g., GitHub Pages deploy of fork-PR previews), the lint-rejection grammar already supports it.

### issue-claim-watcher.yml hardening in Phase 51 vs Phase 59 deletion

- **D-06:** `issue-claim-watcher.yml` **gets SHA-pinned and gains `permissions: read-all` in Phase 51**, THEN gets deleted in Phase 59's atomic gate flip.
- **Why:** Between Phase 51 (this) and Phase 59 (delete), there is a ~7-phase window during which `issue-claim-watcher.yml` will exist. If it has a non-SHA pin (`@v7`) in that window, it is exposed to the same tj-actions-style retargeting risk that CIHARD-04 protects against. The cost of SHA-pinning a file that will be deleted is one line of YAML diff; the cost of leaving it un-pinned for 7 phases is real supply-chain exposure. Pin it; delete it; move on.

### Claude's Discretion

- Exact `actionlint` invocation (action vs inline curl): planner decides based on action-availability at lock time and Phase 56 SHA-pin discipline.
- Exact SHA values for every action `uses:` rewrite: planner uses `pinact run --update` as the canonical resolver at plan-time (or queries `gh api repos/{owner}/{repo}/git/ref/tags/{tag}` for each pin).
- Whether the three regression tests use raw `yaml.safe_load` parsing or text/regex parsing: planner decides. Text/regex is cheaper and consistent with `scripts/release_gate.py`; YAML parsing is more robust to formatting variance. Either is acceptable.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope + requirements

- `.planning/REQUIREMENTS.md` §`### CI hardening (CIHARD)` — CIHARD-01..05 + TEST-23 (the 6 requirements this phase owns)
- `.planning/ROADMAP.md` §`### Phase 51: CI hardening substrate` — phase goal, success criteria, deps
- `.planning/PROJECT.md` §`## Current Milestone: v0.6 Contribution Gate` — milestone-level goal + the 8 v0.6 decisions to confirm

### Research substrate (v0.6 SUMMARY + 4 dimension docs)

- `.planning/research/SUMMARY.md` — executive map; **Top 3 pitfalls** and the lock-at-requirements-time decisions table directly inform Phase 51 choices
- `.planning/research/STACK.md` — `pinact` version + `actionlint` GHA step shape + `actions/checkout@<sha>` reference (CIHARD-04 tooling)
- `.planning/research/PITFALLS.md` §`PITFALL 1` and §`PITFALL 2` — the two pitfalls this phase mitigates; specific incident citations (Ultralytics, tj-actions/changed-files, "testedbefore" Mar 2026, Spotipy GHSA)
- `.planning/research/ARCHITECTURE.md` §`Backward-compat invariants` — 15 byte-identity contracts; Phase 51 must preserve `ci.yml` job NAMES + release_gate.py 8-check existing enum values

### Files Phase 51 modifies

- `.github/workflows/ci.yml` — 5-job CI surface; SHA-pin every `uses:`, add top-level `permissions: read-all`, add `persist-credentials: false` to every `actions/checkout`, add `Run actionlint` step in `lint-and-test`. Job NAMES unchanged.
- `.github/workflows/issue-claim-watcher.yml` — already has `permissions:`; SHA-pin its two `actions/github-script@v7` uses. Per D-06, get hardened now; deleted Phase 59.
- `pyproject.toml` — `[dev]` extras stays UNCHANGED in this phase (pip-audit lands Phase 53, not 51). `actionlint` is not a Python dep; it's a GHA action / binary.
- `tests/test_contribution_gate_pitfalls/__init__.py` (NEW)
- `tests/test_contribution_gate_pitfalls/test_pitfall_01_pull_request_target.py` (NEW)
- `tests/test_contribution_gate_pitfalls/test_pitfall_02_action_sha_pinning.py` (NEW)
- `tests/test_contribution_gate_pitfalls/test_ci_hardening_workflow_structure.py` (NEW)

### Phase precedent (v0.5 patterns to mirror)

- `.planning/phases/46-test-surface-three-tier-fixtures-pitfall-suite/` — tier-1/2/3 fixtures + 12 pitfall regression files; structural precedent for the v0.6 `tests/test_contribution_gate_pitfalls/` directory
- `.planning/phases/48-reference-plugin-horus-os-example-plugin/` — two-layer surface-lock pattern (ruff banned-api + pytest source-tree grep); analogous to the two-layer SHA-pin enforcement in D-02
- `scripts/release_gate.py` lines 137-148 (CheckResult shape), 680-756 (CLI flags) — Phase 57 will append `actions-pinned-by-sha` here; Phase 51 does NOT touch this file (deferral noted to avoid scope creep)
- `scripts/lint_no_wallclock.py` — precedent for a custom Python lint invoked from a CI step (`ci.yml:42`); model for actionlint integration if the action-form proves unreliable

### Decision files (Phase 56 will land these; flagged for reference)

- `.planning/decisions/sigstore-keyless.md` — explains the keyless-OIDC posture that Phase 51's SHA-pinning + `permissions:` baseline supports
- `.planning/decisions/no-cla.md`, `no-stale-bot.md`, `sbom-cyclonedx.md`, `no-pypi-in-v0.6.md` — v0.6 anti-feature lock-ins; not directly Phase 51 scope but documented to prevent re-litigation

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`scripts/lint_no_wallclock.py`** — the canonical pattern for a project-local Python lint invoked from a `ci.yml` step. If actionlint's action-form proves unreliable or its binary release lags, the planner can copy this script's shape (single-file Python lint, invoked as `python scripts/lint_actions.py`, exits non-zero on findings) for a thin actionlint wrapper. Not the recommended path (D-01), but a fallback.
- **`scripts/release_gate.py`** — the v0.5 Phase 49 extension idiom (8 checks, `CheckResult` shape, `--check` CLI enum). Phase 57 (not 51) will extend it for `actions-pinned-by-sha`. Phase 51's job is to LEAVE THIS FILE UNTOUCHED so the byte-identity invariant (15 of them in `.planning/research/ARCHITECTURE.md`) holds.
- **`tests/test_plugin_pitfalls/` directory** — v0.5 TEST-17's 12-file structure with `test_pitfall_NN_<name>.py` naming. v0.6's `tests/test_contribution_gate_pitfalls/` directly mirrors this.

### Established Patterns

- **3-OS × 2-Python matrix** in `ci.yml` — preserved byte-identically; CIHARD-02's `permissions: read-all` lands ABOVE the matrix `jobs:` block (workflow-level, not job-level).
- **Job names as byte-identity contracts** — `release_gate.py` greps `ci.yml` for `lint-and-test:`, `install-smoke:`, `install-smoke-otel:`, `install-smoke-plugin:`. Phase 51 must not rename. Adding a `permissions:` block, a `persist-credentials: false` line, or a new `Run actionlint` step inside an existing job is OK; renaming or removing a job is NOT.
- **Trigger discipline** — `ci.yml` currently triggers on `push: branches: [main]` + `pull_request: branches: [main]`. NOT `pull_request_target`. Phase 51 preserves this; CIHARD-01 ensures no future workflow accidentally drifts to `pull_request_target`.

### Integration Points

- **`.github/workflows/ci.yml` top-level** — `permissions: read-all` lands above `jobs:`. Per-job opt-in `permissions: contents: write` (or similar) inside any job that needs more.
- **`.github/workflows/ci.yml` `lint-and-test` job** — new `Run actionlint` step inserted after `Run ruff format check` (line ~39), before `time.time() lint gate` (line ~41).
- **Every `actions/checkout` step in both workflows** — `with: persist-credentials: false` added below the `uses:` line.
- **`tests/test_contribution_gate_pitfalls/` directory** — created here; Phase 58 will add the remaining v0.6 pitfall regression files (TEST-22 covers all 12 PITFALLS.md entries; Phase 51 ships the subset relevant to CIHARD).

</code_context>

<specifics>
## Specific Ideas

- **Phase 51 ships ZERO `pull_request_target` triggers in v0.6.** This is a hard substrate decision, not a temporary state. If a future v0.7+ phase ever wants this trigger, the `# SECURITY:` comment grammar + `safe-to-test` label-gate escape hatch is documented in CIHARD-01 but unused in v0.6.
- **`actionlint` step name MUST contain the literal `(CIHARD-05)` substring.** Mirrors v0.5's "(METRIC-05 / TEST-12)" labelling in `ci.yml:51`. Makes the regression test for CIHARD-05 simple: grep ci.yml for the literal `(CIHARD-05)`.
- **TEST-23's test files MUST live under `tests/test_contribution_gate_pitfalls/`, not `tests/test_plugin_pitfalls/`.** The v0.5 directory is for plugin pitfalls; v0.6 contribution-gate pitfalls are a separate concern with separate ownership in PITFALLS.md. Two directories, no co-mingling.

</specifics>

<deferred>
## Deferred Ideas

- **`actions-pinned-by-sha` release-gate check** — Phase 57 (REL-14). Phase 51 does the SHA rewrite; Phase 57 adds the regression-against-future-drift check.
- **`pinact` quarterly cadence documented in MAINTAINER-RUNBOOK.md** — Phase 56 (RUNBOOK-01).
- **`zizmor` workflow security audit** — Phase 54 (DEPBOT-03). Overlaps with `actionlint` but covers a different rule set (zizmor catches known-bad expression interpolation patterns; actionlint catches structural workflow errors). Both ship; both are cheap; no contention.
- **`pull_request_target` escape-hatch implementation** — documented in CIHARD-01 but no test fixture proves the `# SECURITY:` comment + `safe-to-test` label-gate grammar works because v0.6 has no `pull_request_target` trigger anywhere. If v0.7+ introduces one, that phase ships the fixture + tests.
- **Dependabot github-actions ecosystem** — Phase 54 (DEPBOT-01). Will propose SHA bumps against the pins Phase 51 lands. The two phases are sequenced (54 after 51) precisely so Dependabot has something useful to bump.

</deferred>

---

*Phase: 51-ci-hardening-substrate*
*Context gathered: 2026-05-29*
