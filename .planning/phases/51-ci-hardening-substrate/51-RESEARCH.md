# Phase 51: CI hardening substrate - Research

**Researched:** 2026-05-29
**Domain:** GitHub Actions supply-chain hardening (fork-PR secret-leak + mutable-tag retargeting), workflow lint integration, regression test surface
**Confidence:** HIGH (every action SHA verified via `gh api repos/{owner}/{repo}/git/matching-refs/tags/{prefix}`; every tool version verified against the upstream release page; every rule name verified against the actionlint v1.7.12 checks doc)

## Summary

Phase 51 is the precondition phase for the entire v0.6 Contribution Gate. Six locked decisions in 51-CONTEXT.md (D-01..D-06) already shape the work; this research fills in the technical specifics the planner needs to write task-level YAML diffs and test-file skeletons without any further lookup:

1. Exact 40-char commit SHAs for every action `uses:` line in the current `ci.yml` and `issue-claim-watcher.yml`, pinned at the most recent tag in each action's currently-used major line (zero-functional-change pins) AND at the most recent major (the upgrade-path option), so the planner can pick.
2. The current actionlint version, SHA, and its actual rule-name coverage — specifically which CIHARD requirements actionlint catches structurally and which require a custom regex / release-gate check Phase 51 must ship.
3. PyYAML availability in the project's `[dev]` extras (NOT present — Phase 51 must either add it or use stdlib-only `re` parsing per CONTEXT.md D-04 discretion).
4. The exact rhysd-vs-raven-actions tradeoff for actionlint invocation (rhysd ships NO action.yml; either raven-actions wrapper or inline binary download is the answer).
5. The Validation Architecture section for the eight Nyquist dimensions, per `.planning/config.json` `workflow.nyquist_validation: true`.

**Primary recommendation:** Pin every action to a 40-char SHA at the **last patch of the major already in use** (`actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683` # v4.2.2, `actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065` # v5.6.0, `actions/github-script@f28e40c7f34bde8b3046d885e986cb6290c5673b` # v7.1.0). This is the zero-functional-change rewrite that delivers CIHARD-04 without coupling to a major version bump. Major upgrades (v6 of checkout in particular) are a separate, optional concern flagged in §`State of the Art` below — recommend deferring to a Dependabot PR after Phase 54 ships the github-actions ecosystem updater. Add `actionlint` via `raven-actions/actionlint@205b530c5d9fa8f44ae9ed59f341a0db994aa6f8` # v2.1.2 as a new step in the `lint-and-test` job (D-01 already locked it as a step; this confirms the wrapper SHA). Ship `tests/test_contribution_gate_pitfalls/` with the three files D-04 locked, using stdlib `re` parsing (not PyYAML) — Phase 51 does NOT add PyYAML to `[dev]`; the brittleness CONTEXT.md flagged is mitigated by reading the workflow files as text and using anchored line-level regexes (precedent: `scripts/release_gate.py` is stdlib-only and uses string-grep extensively).

---

## Architectural Responsibility Map

Phase 51 modifies only CI infrastructure and adds Python regression tests. No runtime tier is touched. The "tier" axis below is the contribution-gate enforcement layer.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| `pull_request_target` forbidden across all workflows (CIHARD-01) | PR-time: pytest regression (`test_pitfall_01_pull_request_target.py`) | Release-time: `release_gate.py` `actions-pinned-by-sha` check (Phase 57, NOT 51) | D-05 locks dual-layer. Phase 51 ships PR-time only; Phase 57 adds release-time. actionlint does NOT detect `pull_request_target` use; custom test is mandatory. |
| Top-level `permissions: read-all` on every workflow (CIHARD-02) | PR-time: pytest regression (`test_ci_hardening_workflow_structure.py`) | actionlint structural validation of the block's contents | actionlint validates the contents of an existing `permissions:` block; it does NOT flag the absence of one. Regression test asserts presence at the top of every `.github/workflows/*.yml`. |
| `actions/checkout` with `persist-credentials: false` (CIHARD-03) | PR-time: pytest regression (same file as CIHARD-02) | none in Phase 51 | actionlint has no check for this. Custom assertion only. |
| No `${{ github.event.* }}` in `run:` shells (CIHARD-03) | PR-time: actionlint `expression` rule (covers `untrusted-inputs` class) | PR-time: pytest regression (defense-in-depth) | actionlint's `expression` rule is the canonical detector for this class. Regression test catches the case where someone disables the rule via `# actionlint:` comment. |
| Every third-party `uses:` is `@<40-hex>` (CIHARD-04) | PR-time: pytest regression (`test_pitfall_02_action_sha_pinning.py`) | Release-time: `release_gate.py` (Phase 57) | actionlint does NOT enforce SHA-pinning. Custom regex over every `uses:` line. The Phase 57 release-gate addition is documented in CONTEXT.md D-02 and is NOT in scope for Phase 51. |
| `actionlint` runs on every PR (CIHARD-05) | PR-time: new `Run actionlint (CIHARD-05)` step in `lint-and-test` job | none | D-01 locks the step shape. The step name carries the literal `(CIHARD-05)` substring for grep-checkability per `<specifics>` block in CONTEXT.md. |

**Key insight:** actionlint covers ONE of the five CIHARD requirements (the `${{ github.event.* }}` interpolation case, via its `expression` rule). The other four — `pull_request_target` ban, missing top-level permissions, missing `persist-credentials: false`, non-SHA action pin — are NOT actionlint rules. Phase 51's regression test trio is therefore not redundant with actionlint; it is the primary enforcement for four out of five requirements.

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CIHARD-01 | `pull_request_target` FORBIDDEN by default; v0.6 ships ZERO instances | §`Pitfall 1 enforcement`, §`Code Examples`/`test_pitfall_01` |
| CIHARD-02 | Top-level `permissions: read-all` on ci.yml + (future) audit.yml + release.yml; per-job opt-in writes | §`Permissions semantics`, §`Code Examples`/structural test |
| CIHARD-03 | Every `actions/checkout` step sets `persist-credentials: false`; no `${{ github.event.* }}` in `run:` shells | §`Pitfall 1 enforcement` (interpolation), §`Code Examples`/structural test (persist-credentials) |
| CIHARD-04 | Every third-party `uses:` pinned to 40-char commit SHA | §`Resolved Action SHAs` (every current pin's SHA), §`Code Examples`/`test_pitfall_02` |
| CIHARD-05 | `actionlint` runs on every PR via the `lint-and-test` job; failures block merge | §`actionlint integration shape`, §`Code Examples`/CIHARD-05 step |
| TEST-23 | Workflow-lint regression test enforces CIHARD-01..05 via the three test files locked in D-04 | §`TEST-23 file shapes`, all three §`Code Examples` |

---

## Project Constraints (from CLAUDE.md)

The planner MUST honor these directives from `./CLAUDE.md`. They are not negotiable:

| Directive | Source | Phase 51 implication |
|-----------|--------|---------------------|
| No PII in committed text | CLAUDE.md "Hard rules" #1 | All YAML comments + test docstrings use placeholders only |
| Apache 2.0 license | CLAUDE.md "Hard rules" #2 | New files in `tests/test_contribution_gate_pitfalls/` need no per-file header (v0.1 policy) |
| No em-dashes in committed prose | CLAUDE.md "Hard rules" #3 | All test docstrings, YAML comments, and the `actionlint` step name use commas/periods/hyphens only |
| ruff lint + format | CLAUDE.md "Hard rules" #4 | New `.py` files must pass `ruff check` and `ruff format --check`. Test docstrings follow existing module style. |
| pytest from repo root, 3-OS × 2-Python | CLAUDE.md "Hard rules" #5 | The three TEST-23 files MUST be collectible by the default pytest invocation; they MUST pass on all 3 OS / 2 Python combinations |
| Conventional commits, present tense | CLAUDE.md "Hard rules" #6 | Phase 51 commits use `feat(51): ...`, `test(51): ...`, `ci(51): ...` prefixes |
| `pathlib`, no string concat | CLAUDE.md "Workflow expectations" | TEST-23 file iteration over `.github/workflows/*.yml` uses `Path(__file__).resolve().parents[2] / ".github" / "workflows"` not f-string paths |

---

## User Constraints (from CONTEXT.md)

### Locked Decisions

The six decisions in 51-CONTEXT.md `<decisions>` are locked. Planner uses these verbatim:

- **D-01 (actionlint invocation):** `actionlint` runs as a new step inside the existing `lint-and-test` job in `ci.yml`. Step name: `Run actionlint (CIHARD-05)`. Placement: after `Run ruff format check` (line 39), before `time.time() lint gate` (line 41). Invocation via a SHA-pinned action (planner picks action vs inline binary; this research recommends `raven-actions/actionlint@<sha>` as the action form — see §`actionlint integration shape`).
- **D-02 (SHA-pin enforcement):** Two layers. Layer 1 (every-PR, fast): actionlint + the new `test_pitfall_02_action_sha_pinning.py` regression test. Layer 2 (release-time): `release_gate.py` `actions-pinned-by-sha` check — added in **Phase 57**, NOT this phase. Phase 51's contribution is the SHA-pin rewrite + PR-time enforcement only.
- **D-03 (`pinact` is maintainer-driven):** `pinact` is documented in `docs/MAINTAINER-RUNBOOK.md` (Phase 56) as a quarterly maintenance command. NOT a CI auto-PR. NOT a release-gate check.
- **D-04 (TEST-23 three-file split):** `tests/test_contribution_gate_pitfalls/` ships with three files: `test_pitfall_01_pull_request_target.py`, `test_pitfall_02_action_sha_pinning.py`, `test_ci_hardening_workflow_structure.py`. YAML-parse-vs-regex is Claude's discretion (this research recommends stdlib-only `re` parsing — see §`PyYAML decision`).
- **D-05 (`pull_request_target` dual-layer):** PR-time = actionlint + `test_pitfall_01_pull_request_target.py`. Release-time = `release_gate.py` Phase 57 addition. Escape-hatch grammar (`# SECURITY:` comment + `safe-to-test` label gate) documented in CIHARD-01 but UNUSED in v0.6 because no workflow needs `pull_request_target`.
- **D-06 (`issue-claim-watcher.yml` hardened then deleted Phase 59):** Phase 51 SHA-pins it AND adds `permissions: read-all` at the top (downgrading the current top-level `permissions: issues: write` to per-job opt-in). Phase 59 deletes the entire file. The ~7-phase window between 51 and 59 must NOT leave the file un-pinned.

### Claude's Discretion

- Exact `actionlint` invocation (action vs inline curl): recommended `raven-actions/actionlint@205b530c5d9fa8f44ae9ed59f341a0db994aa6f8` # v2.1.2 — see §`actionlint integration shape` for the rationale.
- Exact SHA values for every action `uses:` rewrite: provided in §`Resolved Action SHAs`. Planner copies verbatim.
- Whether the three regression tests use `yaml.safe_load` or `re` text parsing: recommended `re` text parsing — see §`PyYAML decision`. Both approaches are documented; the regex shapes are provided in §`Code Examples`.

### Deferred Ideas (OUT OF SCOPE for Phase 51)

- `actions-pinned-by-sha` release-gate check → Phase 57 (REL-14).
- `pinact` quarterly cadence in `MAINTAINER-RUNBOOK.md` → Phase 56 (RUNBOOK-01).
- `zizmor` workflow security audit → Phase 54 (DEPBOT-03). Complements actionlint; both ship.
- `pull_request_target` escape-hatch implementation (the `# SECURITY:` + `safe-to-test` grammar) → documented in CIHARD-01, no test fixture proves it works because v0.6 has zero `pull_request_target` triggers.
- Dependabot github-actions ecosystem → Phase 54 (DEPBOT-01). Will propose SHA bumps against Phase 51's pins.
- Major-version upgrades (`actions/checkout@v6` etc.) → defer to a Dependabot PR after Phase 54 ships. Phase 51 stays on the v4/v5/v7 lines already in tree.

---

## Standard Stack

### Core (Phase 51 additions)

| Tool | Version | Purpose | Why Standard | Provenance |
|------|---------|---------|--------------|------------|
| `actionlint` (rhysd/actionlint, the actual linter) | `v1.7.12` (2026-03-30) | Workflow YAML lint: catches expression-injection, malformed shell, unknown event filters | de-facto GitHub-Actions linter; ~7.3k stars; the upstream Sigstore docs and most Python project CI use it | `[VERIFIED: gh api repos/rhysd/actionlint/releases]` — release 2026-03-30 |
| `raven-actions/actionlint` (the GHA wrapper around the rhysd binary) | `v2.1.2` (2026-03-02) | GitHub Action that downloads + caches the actionlint binary, adds problem-matchers for inline annotations | rhysd does NOT publish an action.yml. Raven Actions is the recognized community wrapper with binary caching + problem-matchers + cross-OS support | `[VERIFIED: gh api repos/raven-actions/actionlint/git/refs/tags/v2.1.2]` — SHA `205b530c5d9fa8f44ae9ed59f341a0db994aa6f8` |
| `pinact` (suzuki-shunsuke/pinact) | `v4.0.0` (2026-05-25) | Local maintainer tool to rewrite `uses:` tags to `@<sha>` with trailing `# vN.M.P` comment | Go binary; `pinact run --check` mode is CI-friendly; Phase 56 documents the quarterly cadence | `[VERIFIED: WebFetch github.com/suzuki-shunsuke/pinact/releases]` — v4.0.0 May 25 2026 |

### Supporting (no Python deps added in Phase 51)

| Item | Status | Rationale |
|------|--------|-----------|
| PyYAML | NOT added | Stdlib `re` is sufficient for the three TEST-23 files; PyYAML is currently present in the dev venv only because of an unrelated transitive install. Adding it to `[dev]` for three lint tests is unjustified scope-creep. See §`PyYAML decision`. |
| `pip-audit` | NOT added (Phase 53) | Per CONTEXT.md: pip-audit lands in Phase 53, NOT this phase. |
| `cyclonedx-bom` | NOT added (Phase 53) | Same; release-time only. |

### Resolved Action SHAs

The three actions currently in tree, each pinned at the most-recent tag in its current major line (zero-functional-change pin) AND at the most-recent major (the upgrade option). `[VERIFIED: gh api repos/{owner}/{repo}/git/matching-refs/tags/{prefix}]` — every SHA below is the 40-char commit hash returned by the GitHub git-refs API on 2026-05-29.

| Action | Current pin (in ci.yml / issue-claim-watcher.yml) | Recommended pin (same major) | SHA | Tag date | Major-upgrade option (NOT recommended for Phase 51) |
|--------|---------------------------------------------------|------------------------------|-----|----------|-----------------------------------------------------|
| `actions/checkout` | `@v4` | `@v4.2.2` | `11bd71901bbe5b1630ceea73d27597364c9af683` | 2024-10 | `@v6.0.2` SHA `de0fac2e4500dabe0009e67214ff5f5447ce83dd` (2026-01-09); requires Node 24 runner; v6+ stores credentials under `$RUNNER_TEMP` instead of `.git/config` (better default; `persist-credentials: false` then becomes belt-and-braces) |
| `actions/setup-python` | `@v5` | `@v5.6.0` | `a26af69be951a213d495a4c3e4e4022e16d87065` | latest in v5 line | `@v6.2.0` SHA `a309ff8b426b58ec0e2a45f0f869d46889d02405` (2026-01-22) |
| `actions/github-script` | `@v7` (used twice in issue-claim-watcher.yml) | `@v7.1.0` | `f28e40c7f34bde8b3046d885e986cb6290c5673b` | latest in v7 line | `@v9.0.0` SHA `3a2844b7e9c422d3c10d287c895573f7108da1b3` (2026-04-09) — BREAKING: `@actions/github` v9 is ESM-only; D-06 already locks the file for Phase 59 deletion so an upgrade here is wasted work |

**Recommendation:** Use the "same major" pins. The major-upgrade option exists for the planner's awareness but introduces scope outside Phase 51's contract ("harden, do not change behavior"). Dependabot github-actions in Phase 54 is the right vehicle for any major bump.

**`raven-actions/actionlint`:**

| Action | Pin | SHA | Tag date |
|--------|-----|-----|----------|
| `raven-actions/actionlint` | `@v2.1.2` | `205b530c5d9fa8f44ae9ed59f341a0db994aa6f8` | 2026-03-02 |

### Tag-comment convention

Every SHA-pinned `uses:` line gets a trailing `# vN.M.P` comment per the convention documented in PITFALLS.md §`Pitfall 2` and §`STACK.md`. Example:

```yaml
- uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
```

The trailing comment is REQUIRED for human reviewability and is what pinact v4.0.0 enforces (per the v4.0.0 release notes: "Required version comments: SHAs without version comments now trigger validation errors").

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `raven-actions/actionlint@<sha>` action | Inline `bash <(curl https://raw.githubusercontent.com/rhysd/actionlint/v1.7.12/scripts/download-actionlint.bash)` | The inline form pins to actionlint version but not to a commit SHA on the download script. CIHARD-04 wants every external invocation SHA-pinned; the action form satisfies this cleanly. |
| `raven-actions/actionlint` | `reviewdog/action-actionlint` | reviewdog is a heavier wrapper aimed at PR-comment review; raven-actions is the minimal wrapper. The project does NOT need PR-comment review for actionlint (the standard error-on-fail behavior is sufficient). |
| `raven-actions/actionlint` | `super-linter/super-linter` (bundles actionlint among ~50 linters) | super-linter is too broad; it would pull in shell, JS, YAML, Markdown linters the project does NOT want. Single-purpose actionlint is the right scope. |
| Stdlib `re` parsing in TEST-23 | `yaml.safe_load` via PyYAML | PyYAML adds a dep to `[dev]` (~750KB wheel) for three test files. See §`PyYAML decision` for the full analysis. |
| Pin to `v4.2.2` (same major) | Pin to `v6.0.2` (major upgrade) | v6 of checkout has materially better default credential handling (stores under `$RUNNER_TEMP`, not `.git/config`). The upgrade is genuinely worth it eventually, but mixing a major upgrade into a hardening phase couples two concerns. Defer to Dependabot. |

**Installation (local maintainer only, NOT in CI):**

```bash
# pinact — Go binary; installed by maintainer, NOT by CI:
brew install pinact   # or: gh release download v4.0.0 -R suzuki-shunsuke/pinact -p '*.tar.gz'
```

**Version verification commands** (planner runs these at plan-execution time to re-confirm the SHAs are still current; pin date `[VERIFIED: 2026-05-29]`):

```bash
# Sanity-check the recommended SHAs (should print the tag refs from §Resolved Action SHAs):
gh api repos/actions/checkout/git/matching-refs/tags/v4.2.2
gh api repos/actions/setup-python/git/matching-refs/tags/v5.6.0
gh api repos/actions/github-script/git/matching-refs/tags/v7.1.0
gh api repos/raven-actions/actionlint/git/matching-refs/tags/v2.1.2

# If the SHA returned does NOT match the one in §Resolved Action SHAs,
# stop. Either the tag was force-moved (CIHARD-04 incident) or this
# RESEARCH.md is stale. In either case, escalate before pinning.
```

---

## Architecture Patterns

### Workflow-file enforcement layers

```
                +-------------------------------------------+
                |  Phase 51 enforcement surface             |
                +-------------------------------------------+
                                  |
        +-------------------------+-----------------------+
        |                                                 |
        v                                                 v
+--------------------+                +------------------------------------+
|  PR-time (fast)    |                |  Release-time (Phase 57, NOT 51)   |
|  Lives in ci.yml   |                |  Lives in scripts/release_gate.py  |
+--------------------+                +------------------------------------+
| actionlint step    |                | actions-pinned-by-sha check        |
| (CIHARD-05)        |                | (REL-14, defense in depth)         |
+--------------------+                +------------------------------------+
| pytest:            |
|   test_pitfall_01  | <-- CIHARD-01 (pull_request_target)
|   test_pitfall_02  | <-- CIHARD-04 (SHA pinning)
|   test_ci_hard...  | <-- CIHARD-02 (permissions) + CIHARD-03 (persist-credentials + interpolation)
+--------------------+
        |
        v
+--------------------------------------------------------+
|  Files Phase 51 modifies (.github/workflows/)          |
|  + ci.yml (SHA-pin + permissions: read-all + actionlint step + persist-credentials: false on every checkout)
|  + issue-claim-watcher.yml (SHA-pin + permissions: read-all top-level + per-job issues: write)
+--------------------------------------------------------+
```

### actionlint integration shape

D-01 already locks: actionlint runs as a NEW step in `lint-and-test`, named `Run actionlint (CIHARD-05)`, between `Run ruff format check` and the `time.time() lint gate`. This research recommends:

- **Form:** `raven-actions/actionlint@205b530c5d9fa8f44ae9ed59f341a0db994aa6f8` # v2.1.2 (the community wrapper). Reasons:
  - rhysd/actionlint does NOT ship an `action.yml` `[VERIFIED: gh api repos/rhysd/actionlint/contents/action.yml -> 404]`. The "action" form would require either a community wrapper or an inline binary download.
  - raven-actions caches the binary across runs `[CITED: github.com/raven-actions/actionlint action.yml]`, which keeps the new step's wall-clock cost below 2s on warm cache.
  - raven-actions ships problem-matchers `[CITED: same source]`, so actionlint findings surface as GitHub annotations on the PR diff. Required because the actionlint exit-1 alone is not the most discoverable failure mode for a contributor.
  - The action is itself SHA-pinned to v2.1.2 (CIHARD-04 self-consistency).

- **Step shape (planner will adapt this to the live ci.yml):**

```yaml
      - name: Run actionlint (CIHARD-05)
        uses: raven-actions/actionlint@205b530c5d9fa8f44ae9ed59f341a0db994aa6f8 # v2.1.2
        with:
          version: v1.7.12  # pin the actionlint binary version itself
```

- **Why NOT inline binary download:** `bash <(curl https://raw.githubusercontent.com/rhysd/actionlint/main/scripts/download-actionlint.bash) v1.7.12` works but introduces a curl-pipe-to-bash anti-pattern; the script is unpinned (`main` branch). The action form pins both the wrapper AND the binary version explicitly.

- **What actionlint covers (from `[VERIFIED: rhysd/actionlint v1.7.12 docs/checks.md via WebFetch]`):**
  - The `expression` rule catches `${{ github.event.* }}` interpolation inside `run:` shells — covers part of CIHARD-03.
  - The `permissions` rule validates the syntax + values of an existing `permissions:` block. It does NOT flag the ABSENCE of one at the top level. CIHARD-02 needs the regression test.
  - Generic checks: syntax errors, malformed shell (shellcheck integration), unknown event names, glob patterns, runner labels, expired action references.

- **What actionlint does NOT cover:**
  - `pull_request_target` detection as a security risk (it validates the EVENT NAME is real, not that you should not use it). CIHARD-01 needs the regression test.
  - SHA-pin vs tag-pin enforcement. CIHARD-04 needs the regression test (and Phase 57's release-gate check).
  - `persist-credentials: false` on `actions/checkout`. CIHARD-03's persist-credentials clause needs the regression test.

### Permissions semantics (CIHARD-02)

`permissions: read-all` at the workflow level downgrades the default `GITHUB_TOKEN` from "every scope is write by default" to "every scope is read." Per-job opt-in upgrades any specific scope a job needs. The relevant interactions are:

1. **Top-level placement.** The `permissions:` key lands ABOVE `jobs:` in the YAML, OUTSIDE any individual job. This is the workflow-level scope.

2. **`actions/setup-python` cache + `actions/cache` interaction.** The current `ci.yml` `lint-and-test` job uses `cache: pip` on `actions/setup-python@v5`. Under the hood, `actions/setup-python` invokes `actions/cache` to read/write the pip cache. The cache action only needs `actions: read` (which is included in `read-all`). `[CITED: actions/cache action.yml]` confirms cache reads need no write permission. No per-job downgrade required.

3. **`issue-claim-watcher.yml` write scope.** That workflow currently has top-level `permissions: issues: write` (line 17-18 of the file). Phase 51 should refactor to top-level `permissions: read-all`, then per-job `permissions: issues: write` on the `detect-claim` job. This makes the file consistent with the contribution-gate's least-privilege baseline. The behavior is unchanged.

4. **`contents: write` for the lint-and-test job:** the existing job does NOT push, comment, or write artifacts. `read-all` is sufficient.

```yaml
# ci.yml top-level shape after Phase 51:
name: CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
permissions: read-all    # CIHARD-02 — workflow-level least-privilege
jobs:
  lint-and-test:
    # no per-job permissions block needed (read-all is sufficient)
    ...
```

```yaml
# issue-claim-watcher.yml top-level shape after Phase 51:
name: Issue claim watcher
on:
  issue_comment:
    types: [created]
permissions: read-all   # CIHARD-02 — top-level least-privilege
jobs:
  detect-claim:
    permissions:
      issues: write     # per-job opt-in for the canned-reply behavior
    if: >-
      github.event.issue.state == 'open'
      ...
```

### `persist-credentials: false` shape (CIHARD-03)

Every `actions/checkout` step in both workflows gets a `with:` block:

```yaml
      - name: Check out repository
        uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
        with:
          persist-credentials: false
```

For `actions/checkout@v4`, the default is `persist-credentials: true`, which writes the `GITHUB_TOKEN` into `.git/config`. Any later step in the same job can `cat .git/config` to exfiltrate it. The Phase 51 contract is: no job in either workflow pushes back to the repo, so `persist-credentials: false` is the safe default `[CITED: PITFALLS.md Pitfall 1 §How to avoid]`.

### TEST-23 file shapes

D-04 locks: three files in `tests/test_contribution_gate_pitfalls/`. Each file follows the v0.5 `tests/test_plugin_pitfalls/` precedent: module docstring referencing the pitfall, structural assertions one-per-`def`, no fixtures from `tests/plugins/conftest.py` (this directory is independent), uses stdlib `re` for workflow-text parsing.

Per CLAUDE.md: every test file uses `pathlib.Path(__file__).resolve().parents[2] / ".github" / "workflows"` for repo-root resolution. Glob: `Path(workflows_dir).glob("*.yml")`. Iteration is sorted for deterministic test output.

See §`Code Examples` for the three concrete test skeletons.

### Recommended Project Structure (Phase 51 additions only)

```
tests/
└── test_contribution_gate_pitfalls/                     # NEW directory
    ├── __init__.py                                       # NEW (marker file only)
    ├── test_pitfall_01_pull_request_target.py            # NEW (CIHARD-01 enforcement)
    ├── test_pitfall_02_action_sha_pinning.py             # NEW (CIHARD-04 enforcement)
    └── test_ci_hardening_workflow_structure.py           # NEW (CIHARD-02 + CIHARD-03 enforcement)
.github/workflows/
    ├── ci.yml                                            # MODIFIED (SHA-pins, permissions, persist-credentials, actionlint step)
    └── issue-claim-watcher.yml                           # MODIFIED (SHA-pins, top-level permissions: read-all, per-job permissions)
```

`pyproject.toml` is NOT modified by Phase 51. The `pyproject.toml` line in CONTEXT.md `<files Phase 51 modifies>` notes it stays UNCHANGED.

### PyYAML decision

CONTEXT.md leaves the YAML-parser-vs-regex choice to Claude's discretion. This research recommends **stdlib `re` parsing, no PyYAML**, on six grounds:

1. **PyYAML is not in `[dev]` extras.** `pyproject.toml:56-62` `[project.optional-dependencies].dev` lists only `fastapi`, `httpx`, `pytest`, `pytest-asyncio`, `ruff`. `[VERIFIED: read pyproject.toml]`. The PyYAML 6.0.3 that happens to be present in `.venv/` is `Required-by: <empty>` `[VERIFIED: pip show pyyaml]` — a stale install from a prior experiment, not a declared dep. Tests must NOT rely on it.
2. **Adding PyYAML to `[dev]` for three lint tests is scope-creep.** CONTEXT.md `<files Phase 51 modifies>` is explicit: `pyproject.toml` `[dev]` extras stays UNCHANGED. `pip-audit` is the only `[dev]` change in v0.6 and it ships in Phase 53.
3. **`scripts/release_gate.py` is stdlib-only and uses grep/regex extensively** `[CITED: ARCHITECTURE.md §Q3 and existing 8 checks]`. Phase 51's regression tests should follow the same idiom for consistency with the v0.5 docs-drift / install-smoke-grep pattern. Phase 57 will extend the same idiom into the release gate; Phase 51 establishes it in the test surface.
4. **Workflow YAML is small and well-formatted in this repo.** `ci.yml` is ~225 lines; `issue-claim-watcher.yml` is ~85 lines. Anchored line-level regexes (e.g., `^on:\s*pull_request_target:?\s*$` for the trigger detection, `^\s*-\s*uses:\s*([^@]+)@(\S+?)(\s|$)` for the `uses:` capture) are robust against the formatting variance that exists in practice (only two files, both maintainer-written).
5. **The brittleness CONTEXT.md flagged in `<decisions>` D-04** is mitigated by writing the regex against the actual content, not a hypothetical YAML feature surface. Examples:
   - `pull_request_target`: the only ways to spell this in YAML are `on: pull_request_target:` (multi-line) or `on: [pull_request_target, ...]` (flow). Both are caught by a single regex: `r"(?m)^\s*(?:on:\s*\[[^\]]*pull_request_target|on:\s*pull_request_target|\s+- pull_request_target)\b"`. Or, simpler: `r"\bpull_request_target\b"` over the raw text plus a comment-stripping pass.
   - `uses:` line: `re.compile(r"^\s*-?\s*uses:\s*([^@\s#]+)@(\S+)", re.MULTILINE)`. The captured ref is then matched against `^[0-9a-f]{40}$` OR the path starts with `./`.
6. **Stdlib `re` keeps the tests 3-OS portable with no native-extension surface.** PyYAML wheels exist for all 3 OS × 2 Python combos, but every additional dep is a CI matrix entry that can fail.

If the planner disagrees and prefers YAML parsing, the fallback path is to declare PyYAML in `[dev]` as a one-line `pyproject.toml` edit. This research's recommendation is to NOT do that. The regex shapes in §`Code Examples` are correct against the actual workflow content.

### Anti-Patterns to Avoid

- **`pinact` in CI.** D-03 already rejects this. `pinact run --update` in a workflow would need `contents: write` to push, expanding the very attack surface CIHARD is closing.
- **Two-file actionlint config.** `actionlint.yaml` config exists, but Phase 51 does NOT need it — the default ruleset covers everything we want plus things we welcome (shellcheck integration, expression linting). Avoid configuration drift.
- **Wildcard-matching `uses:` in TEST-23.** Test must match the LITERAL 40-hex-char pattern. A regex like `re.compile(r"@[a-f0-9]+")` would accept short SHAs (`@abc123d`). The correct anchor is `re.compile(r"^[0-9a-f]{40}$")`.
- **Inline-curl-bash for actionlint.** See §`actionlint integration shape`. The wrapper action form is what CIHARD-04 wants.
- **Renaming `ci.yml` job names.** Per ARCHITECTURE.md §`Backward-compat invariants` items 1-3 and CONTEXT.md `<domain>`: `lint-and-test`, `install-smoke`, `install-smoke-no-otel`, `install-smoke-with-otel`, `install-smoke-plugin` are byte-identity contracts grep'd by `release_gate.py`. Phase 51 adds steps inside these jobs; it does not rename or remove jobs.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML parsing for the regression tests | Custom recursive descent parser | Anchored `re` patterns (see §`Code Examples`) | The full-YAML grammar is overkill for the targeted checks Phase 51 needs. |
| Workflow lint | Hand-rolled rule engine | `actionlint` via `raven-actions/actionlint@<sha>` | actionlint already implements 40+ checks including the `expression` rule for CIHARD-03 |
| SHA resolution at plan-time | Manual `git ls-remote` parsing | `gh api repos/{owner}/{repo}/git/matching-refs/tags/{prefix}` | The matching-refs endpoint returns the 40-char commit SHA directly; pinact uses the same call internally |
| Persist-credentials enforcement | Custom OAuth-token-handling logic | `actions/checkout` `persist-credentials: false` input | The input has existed since checkout v3.4.0 and is the GitHub-blessed mitigation |
| Top-level least-privilege | Custom `GITHUB_TOKEN` scoping logic | `permissions: read-all` workflow-level key | This is the GitHub-Actions-native idiom |

**Key insight:** every CIHARD enforcement has a first-class GitHub Actions feature backing it; Phase 51's job is to USE these features correctly, not to invent new ones. The single net-new artifact is the three TEST-23 regression files (which test that the features ARE configured correctly).

---

## Common Pitfalls

### Pitfall 51-A: actionlint covers fewer CIHARD requirements than it appears to

**What goes wrong:** Planner assumes actionlint catches the entire CIHARD-01..05 surface and skips the regression test files.
**Why it happens:** actionlint's docs are written from a "general workflow correctness" stance, not a "supply-chain-security-tool" stance. The `expression` rule (which catches `github.event.*` interpolation) is genuinely there, but `pull_request_target` detection, `persist-credentials` enforcement, SHA-pin enforcement, and missing-top-level-permissions detection are all NOT in actionlint.
**How to avoid:** Trust the mapping table in §`Architectural Responsibility Map`. The three TEST-23 files cover four of the five CIHARD requirements; actionlint covers one (CIHARD-03's `${{ github.event.* }}` clause).
**Warning signs:** A task description that says "actionlint covers CIHARD-04" — that is wrong; the planner should cite the `expression` rule by name for CIHARD-03 and the regression test by file name for the others.

### Pitfall 51-B: SHA pin to `@v4` (the moving tag), not `@v4.2.2` (the immutable tag)

**What goes wrong:** Planner writes the YAML as `uses: actions/checkout@v4` and the SHA-pin regression test passes (because the test only checks for the presence of `@<40-hex>`-shaped refs and an `@v4` ref isn't 40 hex chars... wait, that fails). OR planner writes `actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5` (the SHA `v4` resolves to TODAY), which is correct-looking and even passes the regex, but is the SAME risk that `@v4` was, just with a longer-looking string — the maintainer of `actions/checkout` can force-update `v4` tomorrow and we are pointing at whatever SHA that lands at.
**Why it happens:** `@v4` and `@v4.2.2` both look "pinned" in the YAML, and `gh api git/refs/tags/v4` returns A commit SHA, just not the one we want to pin to.
**How to avoid:** Pin to the SHA of the most-recent IMMUTABLE patch tag (`v4.2.2`, not `v4`). Use `gh api repos/{owner}/{repo}/git/matching-refs/tags/v4.2` and pick the highest tag in the result. Verify with the date: `actions/checkout v4.2.2` was tagged in 2024-10 and has not moved; `v4` was last force-moved by the maintainer in late 2024 to point at v4.3.x. §`Resolved Action SHAs` lists the correct immutable SHAs.
**Warning signs:** A pinned SHA where the trailing tag comment is `# v4` (the moving tag). The comment should always be the specific patch (`# v4.2.2`).

### Pitfall 51-C: TEST-23 false-positive on `./local-action` refs

**What goes wrong:** Phase 51 has no local actions (no `.github/actions/` directory). But Phase 54+ might. The TEST-23 regex must allow `./` prefixes from the start.
**Why it happens:** The naive regex `^[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+@[0-9a-f]{40}$` rejects `./.github/actions/foo` because the `./` doesn't match. Future contributors then either disable the test or work around it ugly.
**How to avoid:** The regex shape in §`Code Examples` for `test_pitfall_02_action_sha_pinning.py` matches `./` prefix as a first-class branch:
```python
ALLOWED = re.compile(r"^(?:\.[/\\].+|[^@\s]+@[0-9a-f]{40})$")
```
**Warning signs:** A test failure on a local action reference that should pass.

### Pitfall 51-D: `permissions: read-all` workflow-level conflicts with `actions/cache` inside `actions/setup-python`

**What goes wrong:** Planner sees `actions/setup-python@v5` with `cache: pip` and worries it needs `actions: write`. They add per-job `permissions: contents: read, actions: write` and lose the least-privilege baseline.
**Why it happens:** The interaction is non-obvious. `actions/cache` does need write to populate the cache, BUT the `actions: read` scope (which is in `read-all`) is sufficient for cache READS, and cache WRITES to the per-run scope do not need `actions: write` (they use the per-run `ACTIONS_CACHE_URL` which is auto-provisioned). `[CITED: GitHub docs for permissions scopes — actions/cache only requires actions: read for ordinary use]`.
**How to avoid:** Leave the `lint-and-test` job with NO per-job permissions block. The workflow-level `read-all` is sufficient. Run CI; observe cache hits/misses; confirm no permission errors.
**Warning signs:** A first CI run with "no matching cache key" but the job still completes — that is the cold-cache case, not a permissions failure. A permissions failure would be a clear "permission denied" error on the cache POST.

### Pitfall 51-E: `issue-claim-watcher.yml` permissions refactor changes behavior

**What goes wrong:** Planner refactors from top-level `permissions: issues: write` to top-level `permissions: read-all` + per-job `permissions: issues: write`. They miss that `actions/github-script` needs the `issues: write` scope to call `github.rest.issues.createComment`.
**Why it happens:** The current file has the write scope at the top, so every job inherits it. Moving it to per-job MUST land on the `detect-claim` job, not on a wrapper.
**How to avoid:** The shape in §`Architecture Patterns` `### Permissions semantics` is correct. Verify with the actionlint `permissions` rule, which validates that the inputs to `actions/github-script` can access the operations it calls.
**Warning signs:** Test/local invocation of the canned-reply path returns "Resource not accessible by integration."

---

## Runtime State Inventory

Phase 51 is NOT a rename / refactor / migration phase. There is no runtime state to inventory. The phase adds new files (tests) and modifies existing CI YAML. No data stores, no live service config, no OS-registered state, no secrets-by-name, no build artifacts are touched.

This section is intentionally minimal per the research template ("Include this section for rename/refactor/migration phases only").

---

## Environment Availability

Phase 51 is a pure CI + Python-test phase. The relevant dependencies:

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11 + 3.12 | TEST-23 (regression tests) + ci.yml `lint-and-test` job | ✓ | (3-OS × 2-py matrix already proven by v0.5) | none — already required by the project |
| `pytest>=8.0` | TEST-23 file collection | ✓ | (in `[dev]` extras) | none |
| GitHub Actions (`actions/checkout`, `actions/setup-python`) | ci.yml structure | ✓ | per §`Resolved Action SHAs` | none — already used |
| `raven-actions/actionlint` action | CIHARD-05 step | ✓ at runtime | v2.1.2 SHA `205b530c...` | inline binary download (less preferred, documented in §`actionlint integration shape`) |
| `pinact` (LOCAL maintainer use only) | NOT a Phase 51 dep | optional | v4.0.0 | hand-edit SHAs (the planner does this once for Phase 51) |
| PyYAML | NOT a Phase 51 dep | n/a (rejected per §`PyYAML decision`) | n/a | stdlib `re` (recommended path) |
| `actionlint` binary on the runner | runtime (downloaded by `raven-actions/actionlint`) | ✓ (action handles download + cache) | v1.7.12 (pinned via `with: version:`) | none |

**Missing dependencies with no fallback:** none.

**Missing dependencies with fallback:** PyYAML — the fallback is stdlib `re`, which is RECOMMENDED, not a fallback.

---

## Code Examples

These are verified shapes against the project's existing code conventions. The planner adapts them to the live ci.yml.

### CIHARD-05 — `actionlint` step in `lint-and-test`

```yaml
# Inserted into .github/workflows/ci.yml between
# "Run ruff format check" (line 39) and "time.time() lint gate" (line 41).
      - name: Run actionlint (CIHARD-05)
        uses: raven-actions/actionlint@205b530c5d9fa8f44ae9ed59f341a0db994aa6f8 # v2.1.2
        with:
          version: v1.7.12
```

The step name contains the literal `(CIHARD-05)` substring per CONTEXT.md `<specifics>`. The step uses `with: version:` to pin the actionlint binary itself (the wrapper action handles binary download + caching).

### CIHARD-04 — example `uses:` rewrite

```yaml
# Before (anywhere in ci.yml):
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip
          cache-dependency-path: pyproject.toml

# After (Phase 51):
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
        with:
          persist-credentials: false              # CIHARD-03
      - uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v5.6.0
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip
          cache-dependency-path: pyproject.toml
```

### CIHARD-02 — top-level `permissions:` placement

```yaml
# .github/workflows/ci.yml header after Phase 51:
name: CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
permissions: read-all
jobs:
  lint-and-test:
    name: lint+test / ${{ matrix.os }} / Python ${{ matrix.python-version }}
    ...
```

### CIHARD-02 + CIHARD-04 — `issue-claim-watcher.yml` after Phase 51

```yaml
name: Issue claim watcher

on:
  issue_comment:
    types: [created]

permissions: read-all                              # CIHARD-02 — top-level least-privilege

jobs:
  detect-claim:
    permissions:                                   # CIHARD-02 — per-job opt-in
      issues: write
    if: >-
      github.event.issue.state == 'open'
      && github.event.comment.user.type != 'Bot'
      && github.event.comment.user.login != github.event.repository.owner.login
    runs-on: ubuntu-latest
    steps:
      - name: Check for claim language
        ...
      - name: Skip if already replied on this thread
        id: dedupe
        if: steps.check.outputs.matched == 'true'
        uses: actions/github-script@f28e40c7f34bde8b3046d885e986cb6290c5673b # v7.1.0
        ...
      - name: Post canned reply
        if: steps.check.outputs.matched == 'true' && steps.dedupe.outputs.already == 'false'
        uses: actions/github-script@f28e40c7f34bde8b3046d885e986cb6290c5673b # v7.1.0
        ...
```

The two `actions/github-script@v7` uses share the same SHA pin. The `actions/checkout` step is NOT present in this workflow (issue_comment triggers don't need it).

### TEST-23 file 1 — `test_pitfall_01_pull_request_target.py`

```python
"""Pitfall 1 (PITFALLS.md): pull_request_target + checkout-PR-head leaks every secret.

CIHARD-01: v0.6 ships ZERO pull_request_target triggers. This regression
asserts that no workflow under .github/workflows/ uses the trigger, and
no workflow that DID use it (none exist in v0.6) checks out PR-head
under that trigger.

The escape-hatch grammar (# SECURITY: comment + safe-to-test label gate)
is documented in CIHARD-01 but unused in v0.6. If v0.7+ adds a workflow
that needs pull_request_target, this test grows a positive-case branch
asserting the escape-hatch comment + label-gate are present.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

# Catches: "on: pull_request_target:", "on:\n  pull_request_target:",
# "on: [pull_request_target, push]", "on:\n  - pull_request_target".
# Anchored against word boundary to avoid matching e.g. "my_pull_request_target_test".
_TRIGGER_PATTERN = re.compile(r"\bpull_request_target\b")


def test_no_workflow_uses_pull_request_target() -> None:
    """Every .github/workflows/*.yml file must NOT contain pull_request_target."""
    offenders: list[tuple[Path, int, str]] = []
    for workflow in sorted(WORKFLOWS_DIR.glob("*.yml")):
        text = workflow.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            # Skip full-line comments so docs/explanations in comments
            # do not trip the assertion. Inline comments after the trigger
            # name are not a concern because pull_request_target is YAML
            # structural, not a comment-allowed position.
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if _TRIGGER_PATTERN.search(line):
                offenders.append((workflow.relative_to(REPO_ROOT), line_number, line.rstrip()))
    assert not offenders, (
        "pull_request_target trigger found in:\n"
        + "\n".join(f"  {p}:{ln}: {text}" for p, ln, text in offenders)
        + "\nv0.6 ships ZERO pull_request_target triggers (CIHARD-01)."
    )
```

### TEST-23 file 2 — `test_pitfall_02_action_sha_pinning.py`

```python
"""Pitfall 2 (PITFALLS.md): mutable action tag pin is the same as not pinning.

CIHARD-04: every third-party `uses:` is pinned to a 40-char commit SHA.
Allowed forms:
  - foo/bar@<40-hex>     (third-party SHA-pin)
  - ./local-action        (in-repo composite action; allowed)
  - ./<path>              (in-repo composite action; allowed)

Rejected forms:
  - foo/bar@v4            (tag-pin; mutable)
  - foo/bar@main          (branch-pin; mutable)
  - foo/bar@master        (branch-pin; mutable)
  - foo/bar@abc123d       (short SHA; ambiguous)
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

# Captures the (path)@(ref) portion of a `uses:` line. Tolerates leading
# whitespace and the optional list-marker dash. Stops at whitespace or
# the start of a trailing comment.
_USES_PATTERN = re.compile(r"^\s*-?\s*uses:\s*([^@\s#]+)@(\S+)", re.MULTILINE)

# Allowed: either a local action path (starts with ./) or a 40-char hex SHA.
_ALLOWED_REF = re.compile(r"^[0-9a-f]{40}$")


def _is_local_action(path: str) -> bool:
    return path.startswith("./") or path.startswith(".\\")


def test_every_uses_line_is_sha_pinned() -> None:
    """Every `uses:` line in every workflow must be SHA-pinned or local."""
    offenders: list[tuple[Path, str, str]] = []
    for workflow in sorted(WORKFLOWS_DIR.glob("*.yml")):
        text = workflow.read_text(encoding="utf-8")
        for match in _USES_PATTERN.finditer(text):
            path, ref = match.group(1), match.group(2)
            if _is_local_action(path):
                continue
            if not _ALLOWED_REF.match(ref):
                offenders.append((workflow.relative_to(REPO_ROOT), path, ref))
    assert not offenders, (
        "Non-SHA action pins found (CIHARD-04 requires 40-char commit SHA):\n"
        + "\n".join(f"  {p}: {path}@{ref}" for p, path, ref in offenders)
    )
```

### TEST-23 file 3 — `test_ci_hardening_workflow_structure.py`

```python
"""CIHARD-02 + CIHARD-03: structural workflow hardening assertions.

Three structural checks against every .github/workflows/*.yml:

1. Top-level `permissions:` key is present (CIHARD-02).
2. Every `actions/checkout` step sets `persist-credentials: false`
   (CIHARD-03 first clause).
3. No `${{ github.event.* }}` interpolation appears in any `run:`
   shell line (CIHARD-03 second clause).

These checks complement actionlint:
  - actionlint validates the contents of a `permissions:` block but
    does not flag absence; check (1) plugs that gap.
  - actionlint has no `persist-credentials` rule; check (2) plugs that.
  - actionlint's `expression` rule catches (3); check (3) is
    defense-in-depth against the rule being disabled by a
    `# actionlint:` ignore comment.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

# Matches `permissions:` at column 0 (workflow-level, not job-level).
# Job-level permissions are indented; this regex specifically rejects them.
_TOP_LEVEL_PERMISSIONS = re.compile(r"^permissions:\s*", re.MULTILINE)

# Matches a `uses: actions/checkout@...` line. Captures the start position
# so we can scan the following `with:` block for persist-credentials.
_CHECKOUT_USES = re.compile(
    r"^(\s*)-?\s*uses:\s*actions/checkout@\S+",
    re.MULTILINE,
)

# Matches github.event.* inside a ${{ ... }} expression.
_EVENT_INTERPOLATION = re.compile(r"\$\{\{\s*[^}]*\bgithub\.event\.[a-zA-Z0-9_.\[\]'\"]+")


def _workflow_yaml_files() -> list[Path]:
    return sorted(WORKFLOWS_DIR.glob("*.yml"))


def test_every_workflow_has_top_level_permissions() -> None:
    """CIHARD-02: every workflow has a top-level `permissions:` key."""
    offenders: list[Path] = []
    for workflow in _workflow_yaml_files():
        text = workflow.read_text(encoding="utf-8")
        if not _TOP_LEVEL_PERMISSIONS.search(text):
            offenders.append(workflow.relative_to(REPO_ROOT))
    assert not offenders, (
        "Workflows without a top-level `permissions:` block (CIHARD-02):\n"
        + "\n".join(f"  {p}" for p in offenders)
    )


def test_every_checkout_sets_persist_credentials_false() -> None:
    """CIHARD-03: every actions/checkout step has persist-credentials: false."""
    offenders: list[tuple[Path, int]] = []
    for workflow in _workflow_yaml_files():
        text = workflow.read_text(encoding="utf-8")
        for match in _CHECKOUT_USES.finditer(text):
            indent = match.group(1)
            uses_line_start = match.start()
            # Search the next ~15 lines after the uses: line for the
            # `with: persist-credentials: false` block; checkout `with:`
            # blocks immediately follow the uses: line by convention.
            after = text[uses_line_start:]
            lookahead = "\n".join(after.splitlines()[:15])
            if f"persist-credentials: false" not in lookahead:
                line_number = text[:uses_line_start].count("\n") + 1
                offenders.append((workflow.relative_to(REPO_ROOT), line_number))
    assert not offenders, (
        "actions/checkout without persist-credentials: false (CIHARD-03):\n"
        + "\n".join(f"  {p}:{ln}" for p, ln in offenders)
    )


def test_no_github_event_interpolation_in_run_shells() -> None:
    """CIHARD-03: no ${{ github.event.* }} interpolation in run: shell lines."""
    offenders: list[tuple[Path, int, str]] = []
    for workflow in _workflow_yaml_files():
        text = workflow.read_text(encoding="utf-8")
        in_run_block = False
        run_block_indent = -1
        for line_number, raw_line in enumerate(text.splitlines(), start=1):
            stripped_left = raw_line.lstrip()
            current_indent = len(raw_line) - len(stripped_left)
            # Detect the start of a `run: |` or `run: >` block.
            if re.match(r"^\s*-?\s*run:\s*[|>]", raw_line):
                in_run_block = True
                run_block_indent = current_indent
                continue
            # Detect a single-line `run: <command>` form.
            single_line_run = re.match(r"^\s*-?\s*run:\s*(.+)", raw_line)
            if single_line_run and not raw_line.rstrip().endswith(("|", ">")):
                if _EVENT_INTERPOLATION.search(single_line_run.group(1)):
                    offenders.append(
                        (workflow.relative_to(REPO_ROOT), line_number, raw_line.rstrip())
                    )
                in_run_block = False
                continue
            # Inside a multi-line run block, lines are content until the
            # indentation drops to <= the run: key's indent.
            if in_run_block:
                if stripped_left == "" or current_indent <= run_block_indent:
                    in_run_block = False
                    continue
                if _EVENT_INTERPOLATION.search(raw_line):
                    offenders.append(
                        (workflow.relative_to(REPO_ROOT), line_number, raw_line.rstrip())
                    )
    assert not offenders, (
        "${{ github.event.* }} interpolation in run: shell (CIHARD-03):\n"
        + "\n".join(f"  {p}:{ln}: {text}" for p, ln, text in offenders)
        + "\nPass the value via env: instead; see PITFALLS.md Pitfall 1."
    )
```

### `tests/test_contribution_gate_pitfalls/__init__.py`

```python
# Marker file for the Phase 51 + 58 contribution-gate pitfall regression suite.
# See .planning/research/PITFALLS.md for the documented pitfalls.
# Phase 51 ships the CIHARD-related subset (PITFALL 1 + PITFALL 2 + structural);
# Phase 58 fills in the remaining pitfall-to-test 1:1 mapping (TEST-22).
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `actions/checkout@v4` (Node 20, credentials in `.git/config`) | `actions/checkout@v6.0.2` (Node 24, credentials under `$RUNNER_TEMP`) | v6.0.0 released 2025-Q4 | Material reduction in `persist-credentials` attack surface. Phase 51 stays on v4 (zero-functional-change pin); Dependabot bumps to v6 later. |
| `actions/setup-python@v5` | `actions/setup-python@v6.2.0` | v6.0.0 released ~2026-01 | Node 24 runtime. No functional change for our use case. |
| `actions/github-script@v7` | `actions/github-script@v9.0.0` | 2026-04-09 | BREAKING: `@actions/github` v9 ESM-only. D-06 deletes the file Phase 59; upgrade is wasted work. |
| `pinact` v3 (always-update, `-review` option) | `pinact` v4.0.0 (required version comments, `-fix=false` semantics) | 2026-05-25 | v4 enforces the `# vN.M.P` trailing comment convention this research already uses. |
| Single-layer SHA-pin enforcement (release-gate-only) | Two-layer enforcement (PR-time pytest + release-time release_gate.py) | v0.6 contribution-gate design | D-02 locked. PITFALL 2 documents the rationale. |
| `actionlint` v1.7.x (current) | `actionlint` v1.7.12 (newest patch line) | 2026-03-30 | Adds timezone-aware schedule checks, deployment-environment validation. Not directly used by Phase 51 but the binary is current. |

**Deprecated / out:**
- `safety` (the Pyup tool) — paid-account requirement; off-limits per project anti-goal. NOT Phase 51 scope (Phase 53 ships `pip-audit`).
- Mutable tag pins like `@v4` — actively prohibited by CIHARD-04. PITFALL 2 is the citation.
- Long-lived `PYPI_API_TOKEN` secrets — out of scope for Phase 51 entirely; PyPI publishing is deferred per `.planning/decisions/no-pypi-in-v0.6.md`.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `raven-actions/actionlint` is actively maintained as of 2026-05 (v2.1.2 released 2026-03-02 is the latest stable). | Standard Stack / actionlint integration shape | If the project goes unmaintained between research and Phase 56's runbook update, switch to inline binary download (documented fallback). LOW risk. |
| A2 | `actions/cache` reads (used internally by `actions/setup-python@v5` `cache: pip`) work under workflow-level `permissions: read-all` without per-job `actions: write` opt-in. | Architecture Patterns / Permissions semantics | If wrong, the lint-and-test job's pip cache write would fail with a permission error on the first run. Quick fix: add `permissions: actions: write` to the job. MEDIUM risk; will be caught immediately on CI execution. |
| A3 | The three TEST-23 regex patterns in §`Code Examples` are robust against the actual formatting of `ci.yml` + `issue-claim-watcher.yml` as they will exist after Phase 51's rewrite. | Code Examples / TEST-23 file shapes | If wrong, a test fails on the first CI run after the rewrite. Quick fix: tighten/loosen the regex. LOW risk because the regexes are matched against the actual file content shown in this RESEARCH.md. |
| A4 | Phase 51 has no local actions (no `.github/actions/` directory exists at plan-time). | Common Pitfalls / Pitfall 51-C | If wrong, the `./` allowlist in `test_pitfall_02_action_sha_pinning.py` is still correct; nothing breaks. ZERO risk. |
| A5 | The `actionlint` `expression` rule in v1.7.12 catches `${{ github.event.* }}` interpolation in `run:` shells exactly as documented; no special config required to enable it. | actionlint integration shape | If wrong, CIHARD-03's second clause has only the `test_ci_hardening_workflow_structure.py` enforcement (no defense-in-depth from actionlint). LOW risk; the rule is the canonical detector for this case per the rhysd v1.7.12 checks doc. |
| A6 | PyYAML is NOT a transitive of any current `[dev]` dep on any of the 3 OS × 2 Python combos. | PyYAML decision | If wrong (e.g., PyYAML becomes a transitive of `pytest-asyncio` or `httpx` on some platform), the `re`-based tests still pass; nothing depends on PyYAML's absence. ZERO risk. |
| A7 | Node 20 runners are still available on GitHub-hosted runners through at least 2026-Q4. | Resolved Action SHAs (the v4 vs v6 choice) | If Node 20 retires before v0.6 ships, all `@v4`-line pins fail and Phase 51 must upgrade to v6 immediately. LOW risk per GitHub's typical Node-runtime sunset cadence (~12+ months notice). |

**Confirmation needed before plan execution:**
- A2 should be confirmed by a dry-run of the modified `ci.yml` on a feature branch before Phase 51 merges. The dry-run is part of the planner's verification step.
- A5 should be confirmed by adding a deliberate offending workflow snippet to a fixture test and verifying actionlint flags it (this can be a one-line addition to `test_ci_hardening_workflow_structure.py` if the planner wants extra assurance).

---

## Open Questions

1. **Should Phase 51 ship a tiny custom `scripts/lint_actions_pinned_by_sha.py` (mirror of `scripts/lint_no_wallclock.py`) as a third enforcement layer, in addition to actionlint + the regression test?**
   - What we know: D-02 already specifies two layers (PR-time pytest + release-time release_gate.py Phase 57). The pytest layer is what `test_pitfall_02_action_sha_pinning.py` provides; it runs on every PR via the standard `pytest -v` invocation in `lint-and-test`.
   - What's unclear: A separate `scripts/lint_actions_pinned_by_sha.py` would add a CI step (`python scripts/lint_actions_pinned_by_sha.py`) that is functionally identical to the pytest assertion. The pytest layer is already cheap (sub-second), and adding a third layer that duplicates the second is theater.
   - Recommendation: **DO NOT ship a custom script.** The three-file TEST-23 surface + actionlint is sufficient for PR-time; Phase 57 will add release-time enforcement in `release_gate.py`. The lint_no_wallclock.py precedent applies when there is no pytest equivalent; here the pytest test IS the equivalent and is more idiomatic for the project's test-as-lint pattern (see `tests/test_lint_no_wallclock.py` which is the pytest backstop for the script-based lint).

2. **Does Phase 51 need to add a fixture workflow that DELIBERATELY contains every banned pattern, so the tests have positive-case coverage (asserts the test catches the violation)?**
   - What we know: The TEST-23 tests assert NEGATIVE — "no workflow has X." Without a positive fixture, a bug in the regex (e.g., `re.compile(r"pull-request-target")` instead of `pull_request_target`) would silently pass every CI run.
   - What's unclear: A fixture file under `tests/test_contribution_gate_pitfalls/fixtures/bad_workflow.yml` could be loaded by a parametrized test asserting the regex flags it. But this is meta-testing the test.
   - Recommendation: **Defer to Phase 58.** TEST-22 (Phase 58) ships the broader pitfall-to-test 1:1 mapping; positive-case fixture coverage is the kind of test-the-test surface that belongs there, not in the initial Phase 51 ship. If the planner wants positive fixtures in Phase 51, a single `tests/test_contribution_gate_pitfalls/fixtures/known_bad_workflow.txt` (not `.yml` — keep it out of `.github/workflows/` so the file itself does NOT trigger the regression) is acceptable scope. NOT required.

3. **Should the regex in `test_no_github_event_interpolation_in_run_shells` also flag `${{ github.head_ref }}` (the legacy SHA-injection vector documented in PITFALLS.md §Pitfall 1)?**
   - What we know: `github.head_ref` is set from the same untrusted source as `github.event.pull_request.head.ref` for PR triggers. The Ultralytics CVE used `github.event.pull_request.head.ref`, but `github.head_ref` is the shorter / more commonly used alias.
   - What's unclear: CIHARD-03 specifically calls out `${{ github.event.* }}` interpolation. `github.head_ref` is in the `github` context but not under `github.event`. A strict reading would not include it.
   - Recommendation: **EXTEND** the regex to cover both forms. The threat model is identical; the strict-CIHARD-03-reading misses half the surface. The regex change: `_EVENT_INTERPOLATION = re.compile(r"\$\{\{\s*[^}]*\b(?:github\.event\.[a-zA-Z0-9_.\[\]'\"]+|github\.head_ref|github\.base_ref)\b")`. Document in the test docstring that the rule covers the documented Pitfall 1 surface AND the `head_ref`/`base_ref` aliases.

---

## Validation Architecture

Per `.planning/config.json` `workflow.nyquist_validation: true`, Phase 51 ships VALIDATION.md (downstream of this RESEARCH). The eight Nyquist dimensions for this phase:

### Dimension 1 — Functional correctness
- **What:** Every CIHARD requirement (01..05) is enforced by at least one runtime check (actionlint step OR pytest regression OR both).
- **How verified:** `pytest tests/test_contribution_gate_pitfalls/ -v` exits 0 against the modified workflows. Six tests: 1 in `test_pitfall_01`, 1 in `test_pitfall_02`, 3 in `test_ci_hardening_workflow_structure`. CI `lint-and-test` job runs them on every PR.
- **Pass criterion:** All six tests green on all 3 OS × 2 Python = 6 matrix entries.

### Dimension 2 — Security regression
- **What:** A workflow file that drifts to ANY of the five banned patterns (`pull_request_target`, missing top-level `permissions:`, missing `persist-credentials: false`, `${{ github.event.* }}` in `run:`, non-SHA `uses:`) fails the test.
- **How verified:** Manual mutation test — temporarily flip ONE pattern in `ci.yml`, confirm at least one test fails, revert. Documented in the verification step but NOT a permanent fixture (per Open Question 2's deferral).
- **Pass criterion:** Each banned pattern is caught by the corresponding regex on first invocation.

### Dimension 3 — Compatibility (3-OS × 2-Python matrix)
- **What:** The new tests pass on Ubuntu, macOS, Windows × Python 3.11, 3.12.
- **How verified:** `ci.yml` `lint-and-test` job's matrix already covers this. The tests use `pathlib` and stdlib `re` only (CLAUDE.md compliant), so 3-OS portability is structural.
- **Pass criterion:** Matrix green (6/6 entries).

### Dimension 4 — Performance
- **What:** The three regression tests add < 1s to the existing pytest run.
- **How verified:** `pytest tests/test_contribution_gate_pitfalls/ --durations=10` shows per-test wall-clock < 200ms each (regex over ~310 lines of YAML total).
- **Pass criterion:** Sub-1s aggregate; the actionlint step adds < 5s on warm cache.

### Dimension 5 — Documentation
- **What:** Every CIHARD requirement is traceable through a doc string in the test file, a comment in the workflow YAML, or a section in CONTRIBUTING.md (Phase 55) / MAINTAINER-RUNBOOK.md (Phase 56).
- **How verified:** grep the test files for each CIHARD-NN ID; grep the workflow YAML for each ID. Phase 55+56 prose linkage is out of Phase 51 scope but documented as a downstream traceability requirement.
- **Pass criterion:** Every CIHARD ID appears in at least one Phase 51 file (test or YAML); the planner verifies.

### Dimension 6 — Regression (against v0.5)
- **What:** No v0.5 byte-identity invariant is broken: `ci.yml` job names unchanged; `release_gate.py` UNTOUCHED; `pyproject.toml` `[dev]` unchanged; existing 5 CI jobs still green.
- **How verified:** `git diff` review confirms no removal/rename of: `lint-and-test`, `install-smoke`, `install-smoke-no-otel`, `install-smoke-with-otel`, `install-smoke-plugin` job names. `release_gate.py` `git diff` shows zero changes. `pyproject.toml` `git diff` shows zero changes.
- **Pass criterion:** All 1011 v0.5 tests still pass; `release_gate.py` 8/8 still green; `git diff scripts/release_gate.py pyproject.toml` empty.

### Dimension 7 — Maintainability
- **What:** A new contributor (post-flip Phase 59) can add a new workflow under `.github/workflows/` and have the three regression tests + actionlint catch every CIHARD violation automatically. The pattern is self-extending without phase-specific scaffolding.
- **How verified:** Add a no-op workflow `.github/workflows/test_new_workflow.yml` with a banned pattern; confirm the tests fail; remove. (Optional manual verification, NOT a permanent fixture.)
- **Pass criterion:** Tests are file-glob-driven (`WORKFLOWS_DIR.glob("*.yml")`), so any new workflow is auto-checked. Confirmed by inspection.

### Dimension 8 — Validation itself (meta)
- **What:** The validation gates above are themselves tested. The `actionlint` step in `lint-and-test` fails the job on a workflow lint error (not just a warning). The three pytest regressions fail the CI job (not just print a warning).
- **How verified:** `raven-actions/actionlint` has `fail-on-error: true` as the default (`[VERIFIED: action.yml input default]`). pytest exits non-zero on assertion failure (standard behavior). CI job failure blocks merge per the existing branch protection (configured at the GitHub repo level; verified in Phase 56's MAINTAINER-RUNBOOK).
- **Pass criterion:** A simulated regression (per Dimension 2) causes the CI job to fail and the PR to be unmergable.

---

## Sources

### Primary (HIGH confidence — verified via tool)

- `[VERIFIED: gh api repos/actions/checkout/git/matching-refs/tags/v4]` — `actions/checkout` v4 series SHAs; v4.2.2 = `11bd71901bbe5b1630ceea73d27597364c9af683`.
- `[VERIFIED: gh api repos/actions/checkout/releases/latest]` — v6.0.2 (2026-01-09), SHA `de0fac2e4500dabe0009e67214ff5f5447ce83dd`.
- `[VERIFIED: gh api repos/actions/setup-python/git/matching-refs/tags/v5]` — v5.6.0 = `a26af69be951a213d495a4c3e4e4022e16d87065`.
- `[VERIFIED: gh api repos/actions/github-script/git/matching-refs/tags/v7]` — v7.1.0 = `f28e40c7f34bde8b3046d885e986cb6290c5673b`.
- `[VERIFIED: gh api repos/raven-actions/actionlint/git/refs/tags/v2.1.2]` — SHA `205b530c5d9fa8f44ae9ed59f341a0db994aa6f8`.
- `[VERIFIED: gh api repos/rhysd/actionlint/releases]` — v1.7.12 published 2026-03-30; SHA `914e7df21a07ef503a81201c76d2b11c789d3fca`.
- `[VERIFIED: gh api repos/rhysd/actionlint/contents/action.yml -> 404]` — confirms rhysd does NOT ship an action.yml; community wrapper required.
- `[VERIFIED: pip show pyyaml]` — local venv has PyYAML 6.0.3 but `Required-by:` empty (stale install, not a declared dep of any current `[dev]` package).
- `[VERIFIED: read pyproject.toml lines 56-62]` — `[dev]` extras do NOT include PyYAML.
- `[VERIFIED: read .github/workflows/ci.yml]` — current trigger shape (`push:` + `pull_request:` both branches `[main]`; no `pull_request_target`); 5 jobs (`lint-and-test`, `install-smoke`, `install-smoke-no-otel`, `install-smoke-with-otel`, `install-smoke-plugin`); all `uses:` lines pinned to MOVING tags (`@v4`, `@v5`).
- `[VERIFIED: read .github/workflows/issue-claim-watcher.yml]` — current top-level `permissions: issues: write`; two `actions/github-script@v7` uses (lines 44, 64); no `actions/checkout`.
- `[VERIFIED: read scripts/lint_no_wallclock.py]` — pattern for stdlib-only Python lint invoked from CI; ~115 lines; uses `pathlib` + manual triple-quote state machine.
- `[VERIFIED: read .planning/research/PITFALLS.md §Pitfall 1 + §Pitfall 2]` — Ultralytics 8.3.41/42 (Dec 2024), Spotipy GHSA-h25v-8c87-rvm8, "testedbefore" March 2026, tj-actions/changed-files CVE-2025-30066 (~23k repos).
- `[VERIFIED: read .planning/research/ARCHITECTURE.md §Backward-compat invariants 1-15]` — 15 byte-identity contracts; Phase 51's job NAMES + release_gate.py + pyproject.toml unchanged.

### Secondary (MEDIUM confidence — single authoritative source)

- `[CITED: github.com/rhysd/actionlint/blob/v1.7.12/docs/checks.md]` — `expression` rule catches `${{ github.event.* }}` in `run:`; `permissions` rule validates contents but not absence; `action` rule covers deprecated runners but NOT SHA-pin enforcement.
- `[CITED: github.com/raven-actions/actionlint/blob/main/action.yml]` — `version`, `matcher`, `cache`, `fail-on-error` inputs; defaults to caching the binary across runs.
- `[CITED: github.com/suzuki-shunsuke/pinact releases]` — v4.0.0 (2026-05-25) breaking changes: `-review` removed, required version comments, `-diff`/`-check` aliases for `-fix=false`.
- `[CITED: github.com/actions/checkout/blob/v6.0.2/action.yml]` — `runs.using: node24`; supports `persist-credentials: false` input.
- `[CITED: github.com/actions/checkout/blob/v4.3.1/action.yml]` — `runs.using: node20`; supports `persist-credentials: false`.
- `[CITED: docs.zizmor.sh/audits/]` — `actions/checkout` v6+ stores credentials under `$RUNNER_TEMP`, NOT `.git/config`; materially reduces persist-credentials attack surface even without explicit `persist-credentials: false`.
- `[CITED: PITFALLS.md §Pitfall 1 "How to avoid"]` — `actions/checkout@... with: persist-credentials: false` is the canonical mitigation per GitHub Security Lab.

### Tertiary (LOW confidence — flagged for plan-time re-verification)

- `[ASSUMED]` — `actions/cache` (used internally by `actions/setup-python@v5 cache: pip`) functions under workflow-level `permissions: read-all` without per-job `actions: write`. See Assumption A2.
- `[ASSUMED]` — The TEST-23 regex patterns are robust against the actual formatting of `ci.yml` + `issue-claim-watcher.yml` after Phase 51's rewrite. See Assumption A3.
- `[ASSUMED]` — `actionlint` `expression` rule does not require special config to enable; it is on by default in v1.7.12. See Assumption A5.

---

## Metadata

**Confidence breakdown:**
- Standard stack (action SHAs + actionlint + pinact versions): **HIGH** — every version verified via `gh api` or upstream release page on 2026-05-29.
- Architecture (enforcement layers, permissions semantics, TEST-23 shape): **HIGH** — CONTEXT.md D-01..D-06 lock the structural decisions; this research fills in the technical specifics with cited sources.
- Pitfalls (51-A through 51-E): **HIGH** — each pitfall is grounded in either CIHARD-NN requirement text, PITFALLS.md citation, or an explicit interaction with an existing v0.5 invariant.
- Code Examples (TEST-23 file shapes, YAML diffs): **MEDIUM-HIGH** — the regex patterns are written against the actual workflow content shown in this RESEARCH.md, but the cross-OS robustness assumption (A3) should be confirmed on a feature branch before the phase merges.
- Validation Architecture: **HIGH** — all eight Nyquist dimensions map to concrete, automatable verification.

**Research date:** 2026-05-29
**Valid until:** 2026-06-28 (30-day window; SHAs verified on 2026-05-29 should be re-confirmed by the planner at plan-execution time if more than ~30 days pass)

**Research scope discipline:** This RESEARCH.md does NOT discuss `scripts/release_gate.py` extension (Phase 57), `pinact` runbook cadence (Phase 56), `pip-audit` integration (Phase 53), `zizmor` (Phase 54), or the gate-flip prose changes (Phase 59). Each is a separate phase with its own RESEARCH; cross-references appear only where Phase 51's decisions depend on the downstream phase's contract (e.g., Phase 57's `actions-pinned-by-sha` is the release-time half of D-02's two-layer design).
