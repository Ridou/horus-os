# Architecture Research — v0.6 Contribution Gate Integration

**Domain:** Open-source release/CI/contributor-trust infrastructure for a Python package (horus-os).
**Researched:** 2026-05-29.
**Mode:** Subsequent-milestone integration map (NOT greenfield).
**Confidence:** HIGH for integration points, MEDIUM for tool choices (sigstore vs cosign, CycloneDX vs SPDX — decision-time locks called out in PROJECT.md).

## Scope of this document

This is **not** a from-scratch architecture. v0.5.0 already ships a 5-job CI matrix, an 8-check release gate, a STOP-BEFORE-TAG release procedure in `docs/RELEASE.md`, and a working contributor template set under `.github/`. The v0.6 contribution gate adds:

1. Signed release artifacts (SIGN).
2. Supply-chain scanning + SBOMs (SUPPLY).
3. Fork-PR hardening (CIHARD).
4. Contributor docs + templates expansion (CONTRIB).
5. Security disclosure surface (SECDISC).
6. Release-gate extension (REL).

Every section below answers: **what file, what section of that file, what existing pattern from v0.4 Phase 38/39 or v0.5 Phase 49/50 is the precedent, and what backward-compat invariant must hold**.

---

## Current architecture (v0.5.0 substrate, must remain intact)

```
+----------------------------------------------------------+
|  Trigger surface                                          |
|  push:main / pull_request:main                            |
+----------------------+-----------------------------------+
                       |
                       v
+----------------------------------------------------------+
|  .github/workflows/ci.yml — single workflow, 5 jobs      |
|  +--------------------------------------------------+    |
|  |  lint-and-test  (3 OS x 2 py = 6 matrix entries) |    |
|  |  -- ruff + pytest + capture-overhead + CLI smoke |    |
|  +--------------------------------------------------+    |
|       | needs:                                            |
|       v                                                   |
|  +---------------------+ +---------------------------+    |
|  | install-smoke       | | install-smoke-no-otel     |    |
|  | (.[all] extras)     | | (.[dev] only)             |    |
|  +---------------------+ +---------------------------+    |
|  +---------------------+ +---------------------------+    |
|  | install-smoke-      | | install-smoke-plugin      |    |
|  | with-otel           | | (reference plugin)        |    |
|  | ([dev,otel])        | |                           |    |
|  +---------------------+ +---------------------------+    |
+----------------------------------------------------------+

+----------------------------------------------------------+
|  scripts/release_gate.py — local pre-tag gate            |
|  8 checks, exit 0 = green:                                |
|   1. pricing-freshness                                    |
|   2. ci-two-variant-smoke (greps ci.yml for two literals) |
|   3. wheel-pricing-bundle (python -m build + zipfile)     |
|   4. pytest                                               |
|   5. docs-drift (manifest schema)                         |
|   6. plugin-install-smoke-ci (greps ci.yml)               |
|   7. reference-plugin-manifest-valid                      |
|   8. v0-4-fixture-roundtrip                               |
+----------------------------------------------------------+

+----------------------------------------------------------+
|  docs/RELEASE.md — STOP-BEFORE-TAG manual procedure       |
|  Pre-flight -> release_gate.py -> version bump ->         |
|  CHANGELOG -> push -> wait CI -> git tag -a ->            |
|  gh release create                                        |
+----------------------------------------------------------+

+----------------------------------------------------------+
|  Contributor surface (.github/)                           |
|  PULL_REQUEST_TEMPLATE.md (50 lines, includes "PRs from   |
|    forks closed without review" NOTICE block)             |
|  ISSUE_TEMPLATE/                                          |
|    bug_report.yml (form)                                  |
|    feature_request.yml (form)                             |
|    config.yml (blank_issues_enabled: false; SECURITY      |
|      contact link to /security/advisories/new)            |
|  workflows/issue-claim-watcher.yml (canned reply bot)     |
|  CODEOWNERS -- DOES NOT EXIST                             |
+----------------------------------------------------------+

+----------------------------------------------------------+
|  Top-level governance                                     |
|  CONTRIBUTING.md (209 lines, "NOT accepting outside PRs") |
|  SECURITY.md (84 lines, GHSA disclosure already set up;   |
|    section "Contributor-pipeline security (not active     |
|    yet)" already wired to flip at v0.6)                   |
|  CODE_OF_CONDUCT.md (already in tree)                     |
|  STATUS.md ("solo development mode" TL;DR; v0.6 listed    |
|    as NOT PLANNED with TBD date)                          |
+----------------------------------------------------------+
```

**Byte-identity invariants v0.6 must preserve** (Phase 49 precedent — release_gate.py existing 8 checks are literal-string-greppable):

- `install-smoke-no-otel` and `install-smoke-with-otel` job names — `release_gate.py:130-131` greps for these literals.
- `install-smoke-plugin` job name — `release_gate.py:132` greps for this literal.
- 8 existing release-gate check names (`pricing-freshness`, `ci-two-variant-smoke`, `wheel-pricing-bundle`, `pytest`, `docs-drift`, `plugin-install-smoke-ci`, `reference-plugin-manifest-valid`, `v0-4-fixture-roundtrip`) — REL-11 contract is "existing checks stay green; new checks add on top."
- `--check` CLI choices set `{pricing,wheel,ci,tests,docs-drift,plugin-install,reference-manifest,fixture-roundtrip}` — v0.6 EXTENDS this enum, MUST NOT rename existing values.
- `docs/RELEASE.md` STOP-BEFORE-TAG block prose — v0.6 prepends new steps to the pre-tag list, MUST NOT mutate existing prose.
- `pyproject.toml` base `dependencies = ["pydantic>=2.7,<3", "packaging>=24.0"]` — v0.5 deliberately added these two; v0.6 SHOULD NOT add new runtime deps (signing/SBOM tooling lives in CI, not the runtime).

---

## v0.6 integration map (answers to all 9 architecture questions)

### Q1 — Where do signing steps live in ci.yml?

**Recommendation: NEW workflow file `.github/workflows/release.yml`, NOT additions to `ci.yml`.**

```
.github/workflows/
  ci.yml          (existing; PR + push:main -- runs on every commit)
  release.yml     (NEW; on: release.types: [published] -- runs once per tag)
  issue-claim-watcher.yml (existing; deleted at gate-flip in Phase 59)
```

**Trigger:** `on: release: types: [published]` (not `on: push: tags:`). The release-published trigger means signing happens AFTER `gh release create` lands in the manual STOP-BEFORE-TAG sequence, preserving the human-confirmation gate `docs/RELEASE.md` already documents. This matches the sigstore-python `release-signing-artifacts` mode where the action uploads bundles to the existing release page rather than racing to mint one.

**Required permissions block in release.yml:**

```yaml
permissions:
  id-token: write       # OIDC token for sigstore keyless signing
  contents: write       # upload signed bundles to the release
  attestations: write   # actions/attest-build-provenance writes
```

**Job shape (one job, sequential steps):**

```yaml
jobs:
  sign-and-attest:
    runs-on: ubuntu-latest    # signing does NOT need 3-OS matrix
    steps:
      - actions/checkout@v4
      - actions/setup-python@v5  (3.12)
      - run: python -m pip install build
      - run: python -m build       # produces dist/*.whl + dist/*.tar.gz
      - uses: sigstore/gh-action-sigstore-python
        with:
          inputs: ./dist/*.whl ./dist/*.tar.gz
          release-signing-artifacts: true    # auto-uploads .sigstore bundles
      - uses: actions/attest-build-provenance
        with:
          subject-path: 'dist/*'
      - uses: actions/attest-sbom            # see Q2
        with:
          subject-path: 'dist/*'
          sbom-path: sbom.cdx.json
```

**Why a separate workflow, not new jobs in ci.yml:**

1. `ci.yml` runs on `pull_request: branches:[main]` — fork PRs would trigger signing attempts, fail on missing OIDC, and pollute CI runs.
2. `release.yml` runs ONCE per release, not on every commit. Embedding it in ci.yml means every PR pays the wheel-build cost.
3. Separation maps to the `release_gate.py` philosophy: ci.yml proves the CODE is shippable; release.yml proves the ARTIFACTS are signed. Two distinct contracts.
4. Existing precedent: the project already separates ci.yml from issue-claim-watcher.yml on trigger boundaries (CI events vs issue events). release.yml extends the same "one workflow per trigger class" pattern.

**Signed git tags:** Git tag signing happens in the human STOP-BEFORE-TAG sequence on the maintainer's workstation (`git tag -s vN.M.P` or `git tag -a vN.M.P` with GPG configured in git). This is a `docs/RELEASE.md` prose update (one line, change `git tag -a` to `git tag -s`), not a CI change.

**Precedent cited:** v0.5 Phase 49 added a NEW job (`install-smoke-plugin`) to ci.yml because the contract was "every commit must pass this." v0.6 SIGN's contract is "every shipped artifact must carry this," which is a release-time concern. Different trigger then different workflow file. The same logic that puts `release_gate.py` outside CI (it's a maintainer-runs-once-per-tag tool, see docs/RELEASE.md "## Why the release gate exists") puts signing in `release.yml`.

---

### Q2 — Where does SBOM generation live?

**Recommendation: NEW workflow step inside `release.yml`, NOT a new `scripts/build_sbom.py`.**

**File path:** `.github/workflows/release.yml`, step between `python -m build` and `sigstore/gh-action-sigstore-python`.

**Tool:** `cyclonedx-py` (the official CycloneDX Python generator). Format choice CycloneDX per PROJECT.md:43-44 ("Likely CycloneDX (Python tooling more mature)"). Final lock-in is a requirements-time decision the roadmapper carries forward.

**Step shape:**

```yaml
- name: Generate SBOM (CycloneDX)
  run: |
    python -m pip install cyclonedx-bom
    python -m cyclonedx_py environment --output-format JSON --output-file sbom.cdx.json
```

**Where the SBOM lands:**

- **Primary:** Attached to the GitHub Release as a release asset via `gh release upload vN.M.P sbom.cdx.json` (same surface as the signed bundles).
- **Secondary:** Signed via `actions/attest-sbom` (writes to the GitHub attestation API; queryable via `gh attestation verify`).
- **NOT stored in:** the wheel itself (would bloat package), `dist/` permanently (CI ephemeral), or `docs/` (would drift between releases).

**Why no `scripts/build_sbom.py`:**

1. SBOM generation needs the FINAL installed environment for the release artifact, which only exists after `python -m build`. Wrapping a one-line `cyclonedx-py` invocation in a stdlib-only Python script (the `release_gate.py` convention) buys nothing.
2. `release_gate.py` carries a stdlib-only contract (line 88: "Pure stdlib"). cyclonedx-py is a third-party package, so it can't live there.
3. There IS a `scripts/build_manifest_schema.py` precedent for "regenerate-this-artifact" scripts (Phase 47), but the manifest schema is a SOURCE artifact committed to the repo; the SBOM is an OUTPUT artifact attached to the release. Different lifecycle, different home.

**Precedent cited:** Phase 38 OtelAdapter chose to live behind an optional `[otel]` extra rather than be added to base deps for the same reason: the SBOM tooling is a release-time concern, not a runtime concern. Just as `opentelemetry-sdk` does not appear in base `dependencies`, `cyclonedx-bom` does not need to either; it's a CI-time pip install in the release workflow.

---

### Q3 — How does scripts/release_gate.py absorb new checks?

**Recommendation: Same 8 to N extension pattern Phase 49 used for the v0.4 to v0.5 4 to 8 jump.** Add new functions, extend the `--check` enum, extend the docstring's numbered list, extend the env-var override list.

**Three new v0.6 checks to add (REL contract):**

| # | Check name | What it asserts | Greps / probes |
|---|------------|-----------------|----------------|
| 9 | `release-workflow-signing-present` | `.github/workflows/release.yml` exists AND contains the literal `sigstore/gh-action-sigstore-python` | grep, no Python import |
| 10 | `release-workflow-sbom-present` | `.github/workflows/release.yml` contains the literal `cyclonedx_py` (or `cyclonedx-bom`) | grep |
| 11 | `pip-audit-clean` | `python -m pip_audit --strict` against the installed `[all]` extras exits 0 | subprocess |
| 12 | `dependabot-config-present` (optional) | `.github/dependabot.yml` exists with `package-ecosystem: pip` AND `package-ecosystem: github-actions` entries | grep |

Pick three for REL-13 (matching the cardinality jump Phase 49 made, 4 new checks). Recommended cut: ship #9, #10, #11. Drop #12 to Phase polish or merge into #9 (the release workflow's existence implies Dependabot wiring).

**File edits to scripts/release_gate.py:**

1. **Docstring (lines 1-93):** Extend "Runs EIGHT checks" to "Runs ELEVEN checks (4 v0.4 + 4 v0.5 + 3 v0.6)." Add three new numbered sections, copying the prose shape from sections 5-8 (the v0.5 additions in Phase 49). Each new docstring section names the file path, the contract, and the pitfall it closes.

2. **New constants (after line 134):**
   ```python
   DEFAULT_RELEASE_YML_PATH = REPO_ROOT / ".github" / "workflows" / "release.yml"
   RELEASE_LITERAL_SIGSTORE = "sigstore/gh-action-sigstore-python"
   RELEASE_LITERAL_SBOM = "cyclonedx_py"
   ```

3. **Three new `check_*` functions** following the existing function signature contract:
   - `check_release_workflow_signing_present(release_yml_path: Path) -> CheckResult` cloning the shape of `check_ci_two_variant_smoke_present` (lines 229-256). Pure grep, no subprocess.
   - `check_release_workflow_sbom_present(release_yml_path: Path) -> CheckResult` same shape.
   - `check_pip_audit_clean(repo_root: Path) -> CheckResult` cloning the shape of `check_pytest_pass` (lines 307-330). subprocess.run with capture_output, tail 20 lines on failure.

4. **`--check` argparse enum (lines 685-694):** Add `"release-signing"`, `"release-sbom"`, `"pip-audit"` to the `choices` tuple. PRESERVE the existing 8 values byte-identical (REL-11 contract).

5. **Path-override env vars (after line 670):** Add `_resolved_release_yml_path()` mirroring the `_resolved_ci_yml_path()` shape (lines 650-654), reading `HORUS_OS_RELEASE_YML_PATH_OVERRIDE`. Required for hermetic tests (`tests/test_release_gate_v0_6_checks.py`).

6. **`main()` dispatch (lines 718-759):** Append three new `if selected in (None, "release-signing"):` blocks. PRESERVE the ordering of existing dispatch (v0.4 checks first, v0.5 checks second, v0.6 checks third). Phase 49 added v0.5 checks AFTER v0.4 checks in the dispatch list; Phase XX (the v0.6 release-gate-extension phase) appends v0.6 after v0.5.

7. **Skip-env support:** Add `HORUS_OS_RELEASE_GATE_SKIP_PIP_AUDIT` to mirror `HORUS_OS_RELEASE_GATE_SKIP_BUILD` semantics for the one new subprocess-heavy check.

**Test surface:** New `tests/test_release_gate_v0_6_checks.py` cloning the shape of the existing v0.5 test (referenced in Phase 49 success criteria). Each new check needs (a) one happy-path test, (b) one negative-path test using the env-var path-override to point at a mutated file.

**Precedent cited:**
- Phase 49 Task 1 ("scripts/release_gate.py extension (4 new checks)", ROADMAP.md:512) is the exact precedent. Same shape, same idioms.
- The 4-to-8 jump (Phase 49) and 8-to-11 jump (v0.6) both preserve the literal-string-grep idiom for the CI-shape checks. Greppability is the contract: the gate runs in <5s on a clean checkout because it reads files and runs one subprocess (pytest), and v0.6 adds at most one more subprocess (pip-audit).

---

### Q4 — Fork-PR safety: how does ci.yml split?

**Recommendation: One workflow file `ci.yml`, two-tier job split via the `if:` guard on per-job permissions and trigger source. NOT a separate `ci-public.yml` + `ci-trusted.yml`.**

**Reasoning, why one file not two:**

1. Two workflow files create a duplication trap: every CI change must land in two places, and the `release_gate.py` literal-string check (`install-smoke-plugin` lives in `ci.yml`) would have to track which file the job moved to.
2. GitHub Actions supports per-job permissions and per-job `if:` guards. The splitting can be done inline.
3. The 5 existing jobs all run safely on fork PRs today (they install + lint + test from the fork's code, with NO secrets). The hardening is about (a) which jobs receive secrets, (b) which jobs run on every PR vs only on labeled/trusted PRs.

**Tier A (runs on EVERY PR, including untrusted forks), no secrets:**

- `lint-and-test`, read-only of fork code, no secrets needed.
- `install-smoke`, fresh install from fork code, no secrets.
- `install-smoke-no-otel`, same.
- `install-smoke-with-otel`, same.
- `install-smoke-plugin`, same; reference plugin lives in-repo.

(All five existing jobs are Tier A. No fork-PR risk today because none consume secrets.)

**Tier B (runs ONLY on push:main or labeled PR with `safe-to-test`), may consume secrets:**

- NEW `supply-chain-audit` job, runs `pip-audit`, may upload SARIF to GitHub Security tab (requires `security-events: write`).
- Future Tier B candidates: any job that needs to push to a registry, post to external services, or read repo secrets.

**Tier B guard pattern (YAML structure):**

```yaml
supply-chain-audit:
  if: |
    github.event_name == 'push' ||
    (github.event_name == 'pull_request' &&
     github.event.pull_request.head.repo.full_name == github.repository) ||
    (github.event_name == 'pull_request' &&
     contains(github.event.pull_request.labels.*.name, 'safe-to-test'))
  runs-on: ubuntu-latest
  permissions:
    security-events: write   # only this job, not the whole workflow
    contents: read
  steps:
    - ...
```

**Top-level workflow guard:** Set `permissions: read-all` at the workflow level (REVOKES the default fork-write surface), then opt-in to write per job. This is the GitHub-recommended "least-privilege per job" pattern.

**Pinned action versions by SHA:** Apply across the whole workflow file. `actions/checkout@v4` becomes `actions/checkout@<40-char-sha>  # v4.x.y`. Comment marks the human-readable version. Dependabot's `package-ecosystem: github-actions` raises PRs to bump the SHAs.

**Why NOT `pull_request_target`:** It runs against the BASE branch's workflow code with secrets attached. Known footgun pattern (Pwn Requests). The `if:`-guard pattern above achieves the same gating without that risk surface.

**Two-file alternative (rejected):** `ci-public.yml` (fork-safe) + `ci-trusted.yml` (`on: pull_request_target` or workflow_run trigger). Rejected because (a) `pull_request_target` is exactly the footgun we're avoiding, (b) the file-split forces release_gate.py to grep two files for the install-smoke literals, breaking the Phase 49 simple grep contract.

**Precedent cited:** ci.yml today already has per-job `needs:` and per-step `if: runner.os != 'Windows'` guards (lines 211, 218, Phase 49 added them for the Windows-vs-bash shell split). v0.6 extends the same per-job `if:` discipline to the trigger axis.

---

### Q5 — Where do contributor templates live?

**Recommendation: Extend the existing `.github/` tree. NO new top-level docs.** v0.5 already shipped a near-complete contributor surface; v0.6 polishes specific gaps and FLIPS prose from "not accepting" to "open."

**Files to MODIFY (existing):**

| Path | Change | Precedent |
|------|--------|-----------|
| `.github/PULL_REQUEST_TEMPLATE.md` | Remove the HTML-comment NOTICE block (lines 1-11) that says "PRs from forks will be acknowledged and closed without review." Keep the rest (sections, checklist) byte-identical. | Phase 50 gate-flip pattern, the prose flip is one targeted edit. |
| `.github/ISSUE_TEMPLATE/bug_report.yml` | Verify all fields are present (OS / Python / horus-os version). Likely no edits. | Existing v0.5 form. |
| `.github/ISSUE_TEMPLATE/feature_request.yml` | Verify; likely no edits. | Existing v0.5 form. |
| `.github/ISSUE_TEMPLATE/config.yml` | Keep as-is. `blank_issues_enabled: false` + the SECURITY contact link to `/security/advisories/new` is correct for v0.6. | No change. |
| `CONTRIBUTING.md` (top-level, 209 lines) | Significant rewrite: remove "NOT accepting outside PRs" notice. Add CLAIM-FLOW section (how to claim an issue, paired with disabling `.github/workflows/issue-claim-watcher.yml`). Add BRANCH-POLICY section. Add COMMIT-FORMAT section (already partly there; codify per CLAUDE.md hard rules, conventional-commit prefix, no em-dashes, no PII). Add TEST/DOC-EXPECTATIONS section. Add TRIAGE-SLA section (or split to a new doc, see below). | Phase 47 expanded `docs/PLUGINS.md` from scratch; same prose-discipline applies here. |
| `SECURITY.md` (top-level, 84 lines) | Update the "Supported versions" table (currently shows v0.3.x as the supported line, must roll to v0.5.x then v0.6.x). DELETE the "Contributor-pipeline security (not active yet)" section (lines 58-65), this is the exact section the project staged for v0.6 deletion. | This section was DESIGNED to be deleted at v0.6, see line 58 "(not active yet)". The deletion is the gate flip. |
| `STATUS.md` (top-level, 204 lines) | TL;DR section (lines 13-25) rewrites from "solo development mode / Outside pull requests are NOT being merged" to the v0.6 "open for contributions" prose. Milestone-timeline table row `v0.6+ Contribution gate` flips State from NOT PLANNED to SHIPPED with the tag. | Phase 50 STATE.md roll-forward precedent, single targeted edit, dated. |
| `README.md` | Add a "Contributing" section with CTAs (link to CONTRIBUTING.md, link to good-first-issues label, link to Discussions). Update any "not accepting PRs" prose that mirrors the SECURITY.md / STATUS.md notice. | Phase 47 README updates are the shape precedent. |
| `.github/workflows/issue-claim-watcher.yml` | DISABLE or DELETE. The "claim language not honored" canned reply contradicts the gate-flip. Delete the workflow file. | This workflow exists to enforce the solo-dev policy; it gets removed when that policy ends. |
| `CHANGELOG.md` | `[0.6.0]` section under Added: signing, SBOM, pip-audit, Dependabot, CODEOWNERS, fork-PR hardening. Under Removed: solo-dev NOTICE on PR template, issue-claim-watcher.yml. | Phase 50 CHANGELOG promotion is the shape precedent (RELEASE.md step 4). |

**Files to CREATE (new):**

| Path | Purpose | Precedent |
|------|---------|-----------|
| `.github/CODEOWNERS` | Single-line file: `* @Ridou` (the sole maintainer) OR per-directory ownership if v0.6 brings additional reviewers. Required for "review requested automatically on PR open." | First-time file; the pattern is GitHub-standard. |
| `.github/ISSUE_TEMPLATE/security_advisory.yml` (OPTIONAL) | Redundant with the existing config.yml contact-link to `/security/advisories/new`. RECOMMENDED: do NOT add. The contact link is the right UX. | Existing config.yml decision is correct. |
| `.github/dependabot.yml` | Two ecosystems: `pip` (weekly, base + each optional extra), `github-actions` (weekly, for action SHA bumps). | New file; standard GitHub pattern. |
| `docs/TRIAGE.md` (or fold into CONTRIBUTING.md) | Triage SLA, label taxonomy, response-time expectations. Recommendation: fold into CONTRIBUTING.md to keep the doc count down. | Phase 47 chose to ship a separate `docs/PLUGIN-SECURITY.md` rather than expanding `docs/PLUGINS.md`, but that was because PLUGIN-SECURITY has a distinct audience (security-conscious users). TRIAGE has the same audience as CONTRIBUTING (would-be contributors), so in-document is better. |

**Issue templates: forms vs markdown.** The existing files (`bug_report.yml`, `feature_request.yml`) are FORMS (`.yml` extension, `name: / description: / body: -` shape). Forms are the GitHub-recommended modern pattern. STAY with forms; do NOT regress to markdown templates. The single new template (security advisory) is NOT needed because the contact link is better.

**Precedent cited:** Phase 47 (docs trio: PLUGINS.md, PLUGIN-SECURITY.md, MIGRATION-v0.4-to-v0.5.md) is the precedent for "land a coordinated doc-set in one phase." v0.6 does the same for CONTRIBUTING + SECURITY + STATUS + README + CHANGELOG as ONE coordinated edit, all dated 2026-DD-DD on the v0.6.0 tag day.

---

### Q6 — Where does SECURITY.md go (what does v0.6 add)?

SECURITY.md ALREADY EXISTS at the repo root (84 lines). GitHub Security Advisories ALREADY documented as the reporting channel (lines 18-21). The private vulnerability reporting GitHub setting (Settings -> Security -> "Private vulnerability reporting") is enabled implicitly by the SECURITY.md reference to `/security/advisories/new`.

**v0.6 changes to SECURITY.md:**

1. **Supported-versions table (lines 8-11):** Update to v0.5.x or v0.6.x (the latest minor). PRE-1.0 policy ("only latest minor receives fixes") is correct; only the version number rolls.
2. **Delete the "Contributor-pipeline security (not active yet)" section (lines 58-65).** This whole section was staged for deletion AT the v0.6 gate flip, the prose says "When the project opens for contributions" which is exactly this milestone.
3. **Add a "Response SLO" subsection** under "Reporting a vulnerability", e.g. "acknowledge within 48 hours, triage within 7 days, fix-or-document-mitigation within 30 days for high-severity." The existing prose (lines 30-32) has soft language ("expect a response in the advisory thread within 14 days"); v0.6 firms it.
4. **Add a "CVE coordination notes" subsection**, point to how GHSA to CVE upgrades work, who files (maintainer auto-fills via the GHSA UI). One paragraph.

**v0.6 changes to GitHub repo settings (NOT in committed files; document in docs/RELEASE.md or a new docs/MAINTAINER.md):**

- Confirm "Private vulnerability reporting" is enabled at Settings -> Security.
- Confirm "Secret scanning" + "Push protection" are enabled.
- Confirm "Code scanning" is enabled (pip-audit results upload as SARIF, if Tier B job exists).
- Confirm "Dependabot alerts" + "Dependabot security updates" are enabled.

**Where to document the maintainer-applied settings:** Either append a "Repo settings checklist" section to `docs/RELEASE.md` (mirroring its existing maintainer-checklist shape) OR create a new `docs/MAINTAINER.md` for one-time-setup vs per-release procedures.

**Recommendation:** Append to `docs/RELEASE.md` under a new top-level section `## One-time repo settings (apply once, verify each release)`. This keeps the maintainer doc count low and follows the established "everything pre-tag in RELEASE.md" pattern.

**Precedent cited:** docs/RELEASE.md already carries the "Why the release gate exists" prose section (lines 169-193) that mixes prose-rationale with procedure. Adding a "Repo settings" section follows the same idiom.

---

### Q7 — Where does the gate flip land?

The "gate flip" is a coordinated set of file edits dated to the v0.6.0 tag day. Single commit (or single PR) lands all of them so the tag and the public-facing prose ship atomically.

**Mandatory file edits at v0.6.0 ship:**

| File | Edit | Lines |
|------|------|-------|
| `STATUS.md` | TL;DR rewrite. Milestone table row. Last-updated date bump. | Tight diff, ~15 lines. |
| `README.md` | "Project status" prose flip. Add "Contributing" section with CTAs. | ~10-20 lines. |
| `CONTRIBUTING.md` | Remove "NOT accepting" notice. Add CLAIM-FLOW + BRANCH-POLICY + TRIAGE. | Significant rewrite. |
| `SECURITY.md` | Delete lines 58-65. Bump supported-versions table. Add SLO subsection. | ~20 lines. |
| `.github/PULL_REQUEST_TEMPLATE.md` | Delete HTML-comment NOTICE block (lines 1-11). | 11 lines. |
| `.github/workflows/issue-claim-watcher.yml` | Delete file. | Whole file. |
| `pyproject.toml` line 7 | `version = "0.6.0"` | 1 line. |
| `src/horus_os/__init__.py` | `__version__ = "0.6.0"` | 1 line. |
| `CHANGELOG.md` | `[Unreleased]` -> `[0.6.0] - YYYY-MM-DD`; fresh empty `[Unreleased]` stub. | Phase 50 idiom. |
| `.planning/STATE.md` | Milestone roll-forward to next milestone or sentinel "no active milestone yet." | Phase 50 idiom. |

**Maintainer-applied GitHub repo settings at v0.6.0 tag time (documented in docs/RELEASE.md, NOT in code):**

- Enable branch protection on `main` (require PR, require status checks: all 5 ci.yml jobs + the new supply-chain Tier B job, require linear history).
- Enable "Require signed commits" on `main` (optional but matches the signing posture).
- Add `good-first-issue`, `help-wanted`, `safe-to-test`, `triage` labels (required for the fork-PR hardening guard).
- Confirm Discussions is enabled (the issue-template config.yml links to it).

**Precedent cited:**
- Phase 50 STATE.md roll-forward (`milestone` to next, `progress.percent` reset) is the documented pattern from docs/RELEASE.md "## Post-release" (lines 160-167).
- CHANGELOG `[Unreleased]` to `[N.M.P] - YYYY-MM-DD` is docs/RELEASE.md step 4 (lines 134-137).
- The PR-template NOTICE deletion is a single-commit atomic edit, same shape as Phase 49 adding `install-smoke-plugin` to ci.yml.

---

### Q8 — Build order (8-12 phases)

**Hard dependency rule:** the release-gate extension (Q3) CANNOT land before the artifacts it asserts exist. release-signing-workflow-present check (#9) requires release.yml in tree; pip-audit-clean check (#11) requires pip-audit to be a runnable subprocess. Therefore release-gate extension is downstream of signing + supply-chain.

**Recommended phase order (10 phases, mirroring v0.5's Phases 40-50 cardinality):**

```
Phase 51  v0.6 baseline + research lock-in
          (Mirror of v0.5 Phase 40. Lock decisions: sigstore-python vs
          cosign, CycloneDX vs SPDX, pip-audit vs safety. Commit
          tests/perf/v0_5_baseline.json if any perf surface added.
          Pure infrastructure; no behavior change.)
   |
   v
Phase 52  Signing workflow (release.yml)
          (NEW .github/workflows/release.yml: sigstore-python action,
          actions/attest-build-provenance. Dry-run on a fake test
          release. id-token: write permission. SIGN-01..SIGN-03.)
   |
   v
Phase 53  SBOM generation
          (Extend release.yml with cyclonedx-py step + actions/attest-sbom.
          Sample SBOM committed under docs/ as a reference. Verification
          procedure documented. SUPPLY-01.)
   |
   v
Phase 54  Supply-chain scanning (Dependabot + pip-audit)
          (.github/dependabot.yml NEW. pip-audit step in ci.yml as a
          Tier-B-eligible job, runs on push:main + main-branch PRs.
          SUPPLY-02, SUPPLY-03.)
   |
   v
Phase 55  Fork-PR hardening (action pinning + Tier A/B split)
          (Pin every uses: in ci.yml + release.yml to SHA. Add the if:
          guard pattern on the pip-audit job (Phase 54 output) so it
          becomes Tier B. Top-level permissions: read-all in both
          workflow files. CIHARD-01..CIHARD-03.)
   |
   v
Phase 56  Contributor docs + templates expansion
          (CONTRIBUTING.md rewrite, README.md "Contributing" section,
          .github/CODEOWNERS NEW, PR template NOTICE removal staged
          as a code-only edit not yet flipping the prose, see Phase 59.
          CONTRIB-01..CONTRIB-04.)
   |
   v
Phase 57  SECURITY.md expansion + repo-settings doc
          (SECURITY.md SLO + CVE-coordination sections. docs/RELEASE.md
          new "One-time repo settings" section. The "Contributor-pipeline
          security (not active yet)" deletion is staged here, BUT the
          actual prose flip is Phase 59. SECDISC-01..SECDISC-02.)
   |
   v
Phase 58  Release-gate extension (release_gate.py 8 -> 11)
          (Add check_release_workflow_signing_present, _sbom_present,
          _pip_audit_clean. Extend --check enum. Tests cloned from
          Phase 49's test idiom. REL-13.)
   |
   v
Phase 59  Three-OS hard gate + gate flip + release
          (Mirror of Phase 49 + Phase 50 combined. CI green on full
          matrix + new pip-audit job. release_gate.py 11/11 green.
          THEN the atomic gate-flip commit: STATUS.md TL;DR, README CTA,
          CONTRIBUTING NOTICE deletion, PR-template NOTICE deletion,
          SECURITY contributor-pipeline section deletion, issue-claim-
          watcher.yml deletion, version bump to 0.6.0, CHANGELOG
          promotion. STOP-BEFORE-TAG block in the phase SUMMARY.
          REL-14, all CONTRIB-* and SECDISC-* validated.)
```

**Optional consolidations to hit 8 phases:**
- Merge 51 into 52 (baseline + first delivery in one).
- Merge 54 into 55 (pip-audit + hardening as one CI-pass).
- Merge 56 + 57 (the docs flip is naturally one PR).

**Optional expansions to hit 12 phases:**
- Split 52 into signing-the-workflow and signing-the-tag (separate concerns).
- Split 56 into CONTRIBUTING vs CODEOWNERS vs README (three small PRs).

**10 phases is the cleanest cut.** Matches v0.5's 11-phase cardinality without padding.

**Hard dependencies (why this order):**

1. **52 -> 58.** release_gate.py check `release-workflow-signing-present` greps release.yml for `sigstore/gh-action-sigstore-python`. The file must exist before the check can pass.
2. **53 -> 58.** Same logic; `release-workflow-sbom-present` greps for `cyclonedx_py`.
3. **54 -> 58.** `pip-audit-clean` shells out to `python -m pip_audit`. pip-audit must be a known dependency the gate can install.
4. **52 -> 55.** Action-pinning sweep includes both ci.yml AND release.yml. release.yml has to exist to be pinned.
5. **54 -> 55.** The pip-audit job is the first NEW Tier B job. Tier A/B classification framework lands when the first Tier B job needs it.
6. **57 -> 59.** SECURITY.md "Contributor-pipeline" deletion is part of the gate flip. The other SECURITY edits (SLO, CVE) can land earlier in Phase 57 without the gate flip.
7. **56 -> 59.** CONTRIBUTING rewrite delivers the CLAIM-FLOW prose; the actual NOTICE deletion in PULL_REQUEST_TEMPLATE.md is part of the gate-flip commit in Phase 59.
8. **58 -> 59.** Phase 59 cannot tag if release_gate.py is not 11/11 green.

**Parallel opportunities (mirroring v0.5's 44 || 45 precedent):**
- Phase 53 (SBOM) || Phase 54 (pip-audit + Dependabot). Both consume the release.yml substrate from Phase 52 but do not depend on each other.
- Phase 56 (contributor docs) || Phase 57 (SECURITY expansion). Different files, no cross-edits.

---

### Q9 — Backward-compat constraints

**v0.5 surfaces that v0.6 MUST NOT break (byte-identity contracts):**

1. **`.github/workflows/ci.yml` job names** — the literals `install-smoke-no-otel`, `install-smoke-with-otel`, `install-smoke-plugin` must remain in the file. `release_gate.py:130-132` greps for them. (Renaming any breaks `ci-two-variant-smoke` or `plugin-install-smoke-ci` checks.)

2. **`install-smoke-plugin` job behavior** — the steps that pip-install the reference plugin, init the DB, and run `scripts/install_smoke_plugin.py` must continue to run on the same 3-OS x 2-Python matrix. v0.6 can ADD steps (e.g. verify signature on a built artifact) but cannot remove the existing 7 steps.

3. **`install-smoke` job (the `.[all]` extras variant)** — exists separately from the `-no-otel` and `-with-otel` variants because each proves a distinct extras-combination contract. Do not collapse.

4. **`scripts/release_gate.py` exit code semantics** — `0` on full pass, `1` on any fail (lines 763-765). v0.6's new checks must follow the same `CheckResult.ok` Boolean discipline and not introduce a new exit code.

5. **`scripts/release_gate.py` `--check` enum values** — the 8 existing values (`pricing`, `wheel`, `ci`, `tests`, `docs-drift`, `plugin-install`, `reference-manifest`, `fixture-roundtrip`) MUST remain. New values append; existing values do not rename.

6. **`scripts/release_gate.py` env-var contract** — `HORUS_OS_PRICING_MAX_AGE_DAYS`, `HORUS_OS_RELEASE_GATE_SKIP_BUILD`, `HORUS_OS_RELEASE_GATE_SKIP_TESTS`, and the five path-override variables remain operational. New env vars append.

7. **`docs/RELEASE.md` STOP-BEFORE-TAG block** — the 9-step "Release procedure" sequence (lines 118-157) can grow new steps (insertions) but the existing steps cannot mutate. Mainly: step 7 (`git tag -a vN.M.P`) can change to `git tag -s` if signed tags are mandated, one-character change.

8. **`pyproject.toml` base `dependencies`** — `["pydantic>=2.7,<3", "packaging>=24.0"]` (lines 25-28). v0.6 SHOULD NOT add to this list (signing/SBOM/audit tooling is CI-time, not runtime). If a hard requirement emerges, it gets called out as REL-DDDD.

9. **`pyproject.toml` optional-dependencies** — `[anthropic, gemini, dashboard, discord, slack, calendar, otel, all, dev]` (lines 30-62). The `all` group enumerates the union; if any extra changes, `all` updates in lock-step (current pattern). v0.6 likely does not touch this.

10. **`.github/ISSUE_TEMPLATE/config.yml`** — `blank_issues_enabled: false`. Preserve. The contact-link list can grow but the existing two entries (Discussions, Security advisory) stay.

11. **`.github/PULL_REQUEST_TEMPLATE.md` sections** — once the NOTICE HTML-comment block is deleted, the remaining sections (`## What this PR does`, `## Why`, `## Test plan`, `## Checklist`, `## Notes for reviewers`) and the Checklist items stay. v0.6 may add a `[ ] No em-dashes` and `[ ] No PII` items (they're already there per lines 43-44).

12. **`docs/manifest-v1.schema.json` + `MANIFEST_V1_SCHEMA`** — the v0.5 docs-drift check (`release_gate.py:338-411`) gates these byte-identical. v0.6 has zero plugin-manifest work; this contract holds automatically.

13. **`tests/fixtures/v0_4_database.sqlite3`** — never mutated, copied to tempfile by the gate (release_gate.py:512-517). v0.6 schema work is also zero; this fixture stays as-is. If v0.6 happens to introduce a v6->v7 migration, the fixture round-trip test extends (per v0.5 Phase 49 precedent).

14. **`tests/perf/v0_4_baseline.json` + `tests/perf/v0_5_baseline.json`** (if it exists) — the capture-overhead benchmark uses these as pinned references. v0.6 does not touch perf; these stay.

15. **Python 3.11 + 3.12 + 3-OS matrix** — non-negotiable per CLAUDE.md "Hard rules" item 5. v0.6 ADDS no new OS or Python version; the matrix shape is the contract.

**Things v0.6 explicitly DOES change (not byte-compat, but called-out):**

- `.github/PULL_REQUEST_TEMPLATE.md` deletes its 11-line NOTICE block (gate flip).
- `.github/workflows/issue-claim-watcher.yml` is deleted.
- `SECURITY.md` deletes its 8-line "(not active yet)" section.
- `STATUS.md` TL;DR rewrites (lines 13-25).
- `CONTRIBUTING.md` rewrites large portions.
- `pyproject.toml` line 7 + `src/horus_os/__init__.py` `__version__` bump to `0.6.0`.

All of these are EXPECTED, DOCUMENTED diffs that the user sees in the v0.6.0 GitHub Release notes.

---

## Anti-patterns to reject (v0.6-specific)

### Anti-Pattern A: Sign in ci.yml

**What it would look like:** New `sign-artifacts` job in ci.yml with `if: github.ref_type == 'tag'`.
**Why wrong:** ci.yml triggers on `push: branches: [main]` and `pull_request: branches: [main]`, neither receives tag pushes. The `if:` guard would silently always be false. Also: sigstore action requires `id-token: write` permission; granting that workflow-wide opens the signing surface to every PR's actions.
**Do instead:** Separate `release.yml` triggered by `on: release: types: [published]`.

### Anti-Pattern B: cosign with stored signing keys

**What it would look like:** Maintainer-held cosign keypair, password in repo secret.
**Why wrong:** Key rotation burden, secret-exposure risk on every workflow run, no audit trail. PROJECT.md:42 already biases to keyless OIDC sigstore.
**Do instead:** sigstore-python with GitHub-OIDC keyless signing, identity tied to the workflow run, transparency-log entry on Rekor, no key to lose.

### Anti-Pattern C: pull_request_target for fork CI

**What it would look like:** `on: pull_request_target` to run Tier B jobs on fork PRs with repo secrets.
**Why wrong:** Runs against the BASE branch's workflow code with secrets attached. Classic "Pwn Requests" attack surface, fork PR can edit workflow files in its head, but `pull_request_target` ignores those edits and runs base. The fork modifies non-workflow code to exfiltrate secrets via the workflow run.
**Do instead:** `if:` guard on `pull_request` events combining `head.repo.full_name == repository` (in-repo PR) with `contains(labels, 'safe-to-test')` (maintainer-blessed fork PR). Maintainer must apply the label after a code review pass.

### Anti-Pattern D: Two workflow files (ci-public + ci-trusted)

**What it would look like:** Split jobs into `.github/workflows/ci-public.yml` (untrusted) + `.github/workflows/ci-trusted.yml` (trusted).
**Why wrong:** release_gate.py's literal-string greps assume `ci.yml`. Splitting forces the gate to grep two files (Phase 49 contract assumes one). Also: every CI change must land twice.
**Do instead:** Inline `if:` guards per job; one ci.yml.

### Anti-Pattern E: Adding cyclonedx-bom to base pyproject dependencies

**What it would look like:** `dependencies = ["pydantic>=2.7,<3", "packaging>=24.0", "cyclonedx-bom>=4.0"]`.
**Why wrong:** SBOM generation is a CI-time concern. Users running `pip install horus-os` should not pull a CycloneDX runtime they never use. Mirror of Phase 38's correct call to gate `opentelemetry-*` behind `[otel]`.
**Do instead:** `pip install cyclonedx-bom` step inside `release.yml` only.

### Anti-Pattern F: Renaming any existing release_gate.py check

**What it would look like:** Rename `pricing-freshness` to `pricing-card-freshness` to be more descriptive.
**Why wrong:** v0.6 phase SUMMARYs, v0.5 phase SUMMARYs, docs/RELEASE.md, and any tooling that parses gate output (none today, but the option exists) all assume the 8 existing names. The contract is "checks add; checks do not rename."
**Do instead:** Append new checks; preserve existing names verbatim.

### Anti-Pattern G: New top-level docs for v0.6

**What it would look like:** New `CONTRIBUTING-v2.md` or `GOVERNANCE.md` or `MAINTAINERS.md` at repo root.
**Why wrong:** CONTRIBUTING.md already exists at top level and is the conventional contributor-doc location. Adding parallel files fragments the contributor surface and breaks the "one doc per audience" discipline Phase 47 set (PLUGINS for plugin authors, PLUGIN-SECURITY for security users, MIGRATION for upgraders).
**Do instead:** Expand CONTRIBUTING.md in place. Add `docs/TRIAGE.md` ONLY if the triage prose exceeds what fits naturally in CONTRIBUTING.

---

## Sources

- `/Users/santino/Projects/horus-os/.planning/PROJECT.md` (v0.6 milestone scope + decision-time locks).
- `/Users/santino/Projects/horus-os/.github/workflows/ci.yml` (current 5-job structure).
- `/Users/santino/Projects/horus-os/scripts/release_gate.py` (existing 8 checks, docstring, dispatch).
- `/Users/santino/Projects/horus-os/docs/RELEASE.md` (STOP-BEFORE-TAG sequence).
- `/Users/santino/Projects/horus-os/pyproject.toml` (base deps + extras + ruff config).
- `/Users/santino/Projects/horus-os/ARCHITECTURE.md` (v0.3-baseline architecture; unchanged for v0.6).
- `/Users/santino/Projects/horus-os/.planning/ROADMAP.md` (Phase 38, 39, 47, 48, 49, 50 precedent for "release-gate extension," "docs trio," "STOP-BEFORE-TAG block," "three-OS install gate").
- `/Users/santino/Projects/horus-os/SECURITY.md` (existing disclosure surface; "(not active yet)" section staged for v0.6 deletion).
- `/Users/santino/Projects/horus-os/STATUS.md` (existing solo-dev TL;DR; v0.6 row marked NOT PLANNED).
- `/Users/santino/Projects/horus-os/.github/PULL_REQUEST_TEMPLATE.md` (existing template with NOTICE block to delete at gate flip).
- `/Users/santino/Projects/horus-os/.github/ISSUE_TEMPLATE/{bug_report.yml,feature_request.yml,config.yml}` (existing v0.5 form set).
- `/Users/santino/Projects/horus-os/CONTRIBUTING.md` (existing 209 lines, needs rewrite for CLAIM-FLOW + BRANCH-POLICY).
- [Sigstore CI Quickstart](https://docs.sigstore.dev/quickstart/quickstart-ci/).
- [gh-action-sigstore-python](https://github.com/sigstore/gh-action-sigstore-python).
- [actions/attest-build-provenance](https://github.com/actions/attest).
- [CycloneDX/cyclonedx-python](https://github.com/CycloneDX/cyclonedx-python).
- [Creating SBOM attestations in GitHub Actions](https://andrewlock.net/creating-sbom-attestations-in-github-actions/).

---
*Architecture research for: horus-os v0.6 Contribution Gate, release/CI/contributor-trust integration.*
*Researched: 2026-05-29.*
