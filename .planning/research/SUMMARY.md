# Project Research Summary

**Project:** horus-os v0.6 Contribution Gate
**Domain:** Supply-chain / contribution-readiness infrastructure (additive milestone on the v0.5 substrate: Python 3.11+ runtime, 5-job CI matrix, 8-check release gate, complete contributor-template scaffold)
**Researched:** 2026-05-29
**Confidence:** HIGH on stack picks and failure modes; MEDIUM on which specific differentiators are worth horus-os's CI minutes; HIGH on the anti-feature list.

## Executive Summary

v0.6 is NOT a feature milestone. It is a **trust-substrate** milestone: one external bit flips at v0.6.0 ship ("outside PRs welcome") and the infrastructure that makes that flip safe lands underneath it. The four research files agree on every load-bearing decision: keyless Sigstore signing via GitHub OIDC for wheels + sdists + tags, CycloneDX 1.6 JSON SBOMs generated against the installed-from-wheel venv, pip-audit on every PR with explicit ignore-list discipline, Dependabot for both `pip` and `github-actions` ecosystems with security-updates explicitly un-grouped, every action `uses:` line pinned to a 40-char SHA, a hard separation between `pull_request` (unprivileged, fork-safe) and `pull_request_target` / `workflow_run` (label-gated, secrets-bearing), and a coordinated atomic prose flip across STATUS.md + README.md + CONTRIBUTING.md + SECURITY.md + PR template + issue-claim-watcher deletion at the moment v0.6.0 ships.

The recommended path is a 10-phase build (51-60) that (1) hardens CI on `pull_request_target` and SHA-pins all third-party actions BEFORE anything else lands, (2) wires the signing + SBOM substrate in a NEW `.github/workflows/release.yml` file (not additions to `ci.yml`), (3) lights up supply-chain scanning, (4) extends `scripts/release_gate.py` from 8 to ~11-13 checks following the v0.5 Phase 49 extension idiom, (5) refreshes contributor + SECURITY docs with honest solo-maintainer SLO language, and (6) performs a soft launch with 3-5 invited contributors before the atomic gate flip. Every existing v0.5 byte-identity contract (15 invariants identified by ARCHITECTURE) must hold.

The dominant risks are well-known and well-mitigated by the recommended stack. Three are high-blast-radius and require requirements-time locks: **`pull_request_target` misuse** (Ultralytics 8.3.41-46 Dec 2024, "testedbefore" March 2026, Spotipy GHSA) leaks every secret on the first malicious fork PR; **mutable action tag pins** (tj-actions/changed-files CVE-2025-30066, ~23k repos compromised) defeat all other controls; **sigstore identity verification with wildcards or wrong issuer** silently accepts attacker-workflow signatures. All three are prevented by (a) NEVER using `pull_request_target` for fork code execution, (b) enforcing 40-char SHA pins via release-gate lint, (c) workflow-scoped exact-match identity in `scripts/verify_release.py` with negative tests.

## Key Findings

### Recommended Stack

Additive only: no changes to the validated v0.5 application stack. v0.6 adds CI-time and release-time tooling, none of which lands in the runtime `pyproject.toml` `dependencies` list. See STACK.md for full version + step-shape detail.

**Core technologies (v0.6 additions):**

- **`sigstore-python` (>=4.2.0,<5) via `sigstore/gh-action-sigstore-python@v3.x`** — keyless OIDC signing of wheels + sdists + SBOM JSON. Produces `.sigstore` bundles (NOT detached `.sig`). Workflow-scoped identity, ephemeral signing certificate, transparency-log inclusion proof inline.
- **`actions/attest-build-provenance@v4.1.0`** — generates SLSA Build L2 provenance attestations bound to the GitHub workflow identity. Verifiable via `gh attestation verify`. Free.
- **`cyclonedx-bom` (>=7.3.0,<8, command `cyclonedx-py`)** — generates CycloneDX 1.6 JSON SBOMs. Run via `cyclonedx-py environment` against a fresh `pip install <wheel>` venv (NOT `pip freeze` of a dev venv). Installed on-the-fly in `release.yml`; NOT added to `[dev]` extras.
- **`pip-audit` (>=2.10.0,<3) via `pypa/gh-action-pip-audit@v1.1.0`** — PyPA-blessed vulnerability scanner. Run dual-mode (`-s osv` AND `-s pypi`). Added to `[dev]` extras for local use.
- **`actions/dependency-review-action@v5.0.0`** — PR-time check on new dep introductions + license allowlist.
- **Dependabot v2** — `package-ecosystem: pip` (grouped routine bumps with cooldown, AI-SDK group to silence anthropic + google-genai churn) AND `package-ecosystem: github-actions` (SHA-pin refresh). Security-updates explicitly NOT grouped, one PR per CVE with a distinct `security-update` label.
- **`pinact` (>=4.0.0,<5)** — local maintainer tool that rewrites every `uses:` to a 40-char SHA pin.

### Expected Features

See FEATURES.md for full T1-T20 / D1-D15 / A1-A12 enumeration.

**Must have (table stakes, T1-T20):**

- T1-T2 Keyless artifact signing + SLSA Build L2 attestations
- T3 Signed git tags via gitsign with OIDC
- T4 SBOM at release: CycloneDX 1.6 JSON, signed + attached
- T5 pip-audit on every PR with explicit ignore-list at `.github/pip-audit-ignore.txt`
- T6 Dependabot config for both ecosystems, grouped routine, ungrouped security
- T7 SHA-pinned actions enforced via release-gate lint
- T8 Fork-PR hardening: `pull_request_target` ABSENT or metadata-only
- T9-T10 First-time-contributor approval gate + branch protection
- T11-T16 Doc refreshes: SECURITY.md SLO with severity tiers, CONTRIBUTING.md banner flip + claim flow, PR template NOTICE deletion, CODEOWNERS path-scoped, CODE_OF_CONDUCT reporting channel
- T17-T20 Atomic gate flip in ONE commit at v0.6.0

**Should have (differentiators worth shipping in v0.6):**

- D6 `docs/TRIAGE.md` with label taxonomy ≤15 hard cap
- D7 Dependency Review action (cheap; bundle with T5)
- D8 `zizmor` audit for workflow security static analysis
- D11-D12 Discussions enabled with pinned "Project Status" post
- D15 `docs/MAINTAINER-RUNBOOK.md` / `docs/POSTFLIP-PLAYBOOK.md`

**Defer to v0.6.x / v0.7+:** SLSA L3 provenance, OpenSSF Scorecard (wait 2 weeks post-flip), CodeQL as required PR check, `safe-to-test` label gate (only if v0.7+ needs live secrets), auto-merge Dependabot grouped PRs.

**Anti-features (explicitly NOT shipped, named to prevent re-litigation):**

- No CLA (Apache 2.0 patent grant + inbound=outbound suffices; CLA blocks drive-bys)
- No mandatory DCO (GitHub web UI cannot append `-s`; optional fallback only)
- No `pull_request_target` + checkout-PR-head (Ultralytics / Spotipy attack class)
- No mandatory Discord/Slack join
- No `actions/stale` auto-close (Drew DeVault + Jacob Tomlinson critique)
- No coverage gate
- No GPG long-lived signing key as primary
- No hosted SBOM SaaS (paid; violates anti-goal)
- No `safety` (Pyup paid tier; pip-audit is the only valid choice)
- PyPI Trusted Publishing OUT OF SCOPE for v0.6 (project does not publish to PyPI); **requirements-time decision** whether v0.6 expands scope

### Architecture Approach

Subsequent-milestone integration, not greenfield. Every change extends an existing v0.5 file or follows an established v0.5 idiom. See ARCHITECTURE.md for the 9-question integration map and 15 byte-identity invariants.

**Major components:**

1. **`release.yml` (NEW)** — triggered by `on: release: types: [published]`. Sign + SBOM + attest. Sequential steps: build then mint OIDC then sign within 5 minutes (TTL ~10 min) then verify against EXPECTED identity then generate SBOM then attest-sbom then upload atomically.
2. **`audit.yml` (NEW)** — PR-time supply-chain gate. `permissions: contents: read`, `persist-credentials: false`. pip-audit dual-run + dependency-review-action with license allowlist (Apache-2.0, MIT, BSD-2/3, ISC, PSF-2.0).
3. **`ci.yml` (existing)** — UNCHANGED job names (`install-smoke-no-otel`, `install-smoke-with-otel`, `install-smoke-plugin` are byte-identity contracts). v0.6 adds `permissions: read-all` + SHA-pins every existing `uses:`, but does NOT rename/remove jobs.
4. **`release_gate.py` extension (8 to ~11-13 checks)** — Phase 49 idiom. New checks: `release-workflow-signing-present`, `release-workflow-sbom-present`, `audit-workflow-present`, `local-pip-audit-clean`, `dependabot-config-present`, `actions-pinned-by-sha`. `--check` enum APPENDED (existing 8 values NEVER renamed). Two-tier: pre-merge local <10s, pre-release network ~60s.
5. **`verify_release.py` (NEW)** — five-check user-facing trust-chain verifier with workflow-scoped EXACT-match identity (no wildcards/regex).
6. **Contributor doc + template surface** — coordinated single-commit edits at v0.6.0 ship.

**Critical backward-compat invariants (15 byte-identity contracts; load-bearing ones):**

- `ci.yml` job names grep'd by release_gate.py: UNCHANGED
- `release_gate.py` 8 existing `--check` enum values: APPENDED, never renamed
- `release_gate.py` exit codes (0/1) and env-var contract
- `docs/RELEASE.md` STOP-BEFORE-TAG 9-step sequence: insertions allowed, mutations not
- `pyproject.toml` base `dependencies`: v0.6 adds NOTHING (signing/SBOM/audit is CI-time)
- `[dev]` extras gets ONE addition: `pip-audit>=2.10,<3`
- 3-OS × 2-Python matrix shape: per CLAUDE.md hard rule 5
- `tests/fixtures/v0_4_database.sqlite3` and perf baselines: untouched

### Critical Pitfalls

See PITFALLS.md for full 12-pitfall enumeration with incident citations. Top 3 highest-blast-radius:

1. **`pull_request_target` + checkout-PR-head leaks every secret on the first malicious fork PR** (PITFALL 1). Ultralytics 8.3.41/42 Dec 2024, Spotipy GHSA, "testedbefore" March 2026. Prevention: `pull_request_target` FORBIDDEN by default; lint rejects any usage without SECURITY-comment + `safe-to-test` label gate + label auto-strip on push; `permissions: read-all` workflow-default; NO `${{ github.event.* }}` interpolation in `run:` shell. Owner: CIHARD-01..03. Phase 51-52 BEFORE the flip.
2. **Mutable action tag pin (`@v4`) is the same as not pinning** (PITFALL 2). tj-actions/changed-files CVE-2025-30066 retargeted 350+ tags, ~23k repos. Prevention: 40-char SHA pin on every third-party `uses:`; release-gate lint enforces; `@main`/`@master` forbidden for third-party; Dependabot github-actions maintains SHA freshness. Owner: CIHARD-04..05. Phase 51 + 55.
3. **Sigstore verification with wildcard identity or missing issuer silently accepts attacker signatures** (PITFALL 3). sigstore-python uses EXACT match. Prevention: `EXPECTED_IDENTITY = "https://github.com/Ridou/horus-os/.github/workflows/release.yml@refs/tags/{version}"`, no wildcards/regex, mandatory `--cert-oidc-issuer`, negative test REJECTS wrong-identity fixture, sign within 5 minutes of OIDC mint, `.sigstore` bundle format only. Owner: SIGN-01..03. Phase 53.

**Next tier:**

4. **SBOM lists install-time resolved deps, not what the wheel contains** (PITFALL 4). Prevention: generate against `pip install <wheel>` in fresh venv; CycloneDX 1.6 JSON locked; release-gate diffs SBOM against published wheel.
5. **pip-audit false positives + Dependabot grouping hides CVE PRs** (PITFALL 5). Prevention: dated-comment ignore-list discipline; tracking files for unfixable transitives; security-updates UN-grouped with distinct label.
6. **CONTRIBUTING.md promises 24h, mandates CLA, mandates Slack** (PITFALL 6). Prevention: "aim to acknowledge within 7 days"; no CLA; Discord optional; CODEOWNERS path-scoped.
7. **PyPI Trusted Publishing not wired before flip** (PITFALL 9, IF PyPI in v0.6 scope). **Requirements-time decision.**
8. **Gate flip has no rollback plan** (PITFALL 10). Prevention: `.planning/rollback/flip-gate-revert.md` one-commit-revert template; `docs/POSTFLIP-PLAYBOOK.md` decision matrix; soft launch with 3-5 invited contributors; `accepted-for-review` throttle for first 30 days.

## Implications for Roadmap

**Lock-at-requirements-time decisions (all four files flag these):**

| Decision | Recommended Lock | Why |
|----------|------------------|-----|
| Signing identity | sigstore-python (NOT cosign); gitsign or `git tag -s` (pick one) | sigstore-python is PEP 740 / `pip install` aligned; cosign is for containers (PITFALL 3) |
| SBOM format | CycloneDX 1.6 JSON | PyPA-adjacent; PyPI PEP 740 consumes CycloneDX; SPDX has thinner Python tooling |
| Scanner | pip-audit only (NO `safety`) | `safety` paid-tier violates anti-goal; dual-run `-s osv` + `-s pypi` |
| Fork-PR gating | NO secrets in fork CI; `pull_request_target` ABSENT | v0.5 tests use recorded responses; `safe-to-test` deferred |
| PyPI Trusted Publishing | DEFER to v0.7+ unless milestone scope expands | OUT OF SCOPE per STACK + ARCHITECTURE |
| CLA / DCO | NO CLA; DCO optional only | Apache 2.0 sufficient |
| Stale-bot | NO `actions/stale` | Drew DeVault critique |
| Conduct reporting | GHSA `[conduct]` title route (reuses existing infra) OR dedicated email | Lock now |
| `claim:` label automation | Defer; maintainer-assigns-by-comment | Wait for data |

### Phase 51: CI hardening substrate

**Rationale:** PITFALL 1 + 2 are highest-blast-radius; their fixes are pure-infrastructure and must land BEFORE STATUS.md ever says "open."
**Delivers:** Workflow YAML lint (`pull_request_target` audit, `actions/checkout` ref audit, no-shell-interpolation via actionlint); `permissions: read-all` top-level on `ci.yml`; every existing `uses:` SHA-pinned via `pinact run`; SHA-pin lint added to `release_gate.py`; pin-freshness warning.
**Addresses:** T7, T8.
**Avoids:** PITFALLS 1, 2.

### Phase 52: Fork-PR CI split (optional, label-gate scaffolding)

**Rationale:** ONLY if a v0.7+ test will need secrets. **Recommended: SKIP and consolidate with Phase 51** since v0.5 tests use recorded responses.

### Phase 53: Signing substrate (release.yml NEW)

**Rationale:** Foundational artifact-trust deliverable. Must precede Phase 58 (release-gate). Sign step at position 2 (OIDC TTL ~10 min).
**Delivers:** `.github/workflows/release.yml`; sigstore-python wheel + sdist + SBOM signing; `actions/attest-build-provenance@v4.1.0` SLSA L2; workflow-scoped `EXPECTED_IDENTITY` in `scripts/verify_release.py`; negative-identity test; expired-token test; gitsign for tag signing OR `git tag -s` documented (one-character change in `docs/RELEASE.md`).
**Avoids:** PITFALLS 3, 9, 11.

### Phase 54: SBOM + supply-chain scan substrate

**Rationale:** Independent of Phase 53 in execution; both consume `release.yml` substrate. **Can run parallel with Phase 53** (mirrors v0.5 Phase 44 || 45).
**Delivers:** `cyclonedx-py environment` in `release.yml` against installed-from-wheel venv; CycloneDX 1.6 JSON locked; two-SBOM convention (clean + `[dev,otel]`); `audit.yml` NEW with `pypa/gh-action-pip-audit@v1.1.0` dual-run + `dependency-review-action@v5` with license allowlist; `.github/pip-audit-ignore.txt` mandatory dated comments; `.github/pip-audit-tracking/` directory.
**Avoids:** PITFALLS 4, 5.

### Phase 55: Dependabot tuning + zizmor

**Rationale:** Dependabot github-actions only meaningfully bumps SHA-pinned references (Phase 51 prereq). Security-update exclusion must land BEFORE Dependabot opens its first grouped-security PR.
**Delivers:** `.github/dependabot.yml` with both ecosystems; `applies-to: version-updates` on groups; `security-update` label + template; `zizmor` workflow.
**Avoids:** PITFALLS 2, 5.

### Phase 56: Contributor docs + templates (staged)

**Rationale:** Can run parallel with Phase 57. All prose lands BUT gate-flip toggle prose is STAGED, ACTIVATED in Phase 60.
**Delivers:** CONTRIBUTING.md rewrite (claim flow, 7-day acknowledgement SLA, anti-goals, NO 24h, NO CLA, Discord optional); PR template NOTICE staged for deletion + CONTRIBUTING/CoC checkbox; issue templates banners staged; `.github/CODEOWNERS` NEW (path-scoped: workflows, secrets handling, release gate, security policy, NOT `* @Ridou`); CODE_OF_CONDUCT reporting channel; `docs/TRIAGE.md` NEW (label taxonomy ≤15 hard cap, `good-first-issue` rubric, weekly Sunday cadence, "may go silent up to 2 weeks" disclaimer); `docs/LABEL-TAXONOMY.md`; decision files `.planning/decisions/no-cla.md`, `no-stale-bot.md`, `sigstore-keyless.md`, `sbom-cyclonedx.md`.
**Avoids:** PITFALLS 6, 7, 12.

### Phase 57: SECURITY.md disclosure flow refresh

**Rationale:** Parallel with Phase 56. SECURITY.md "(not active yet)" section deletion staged here, activated in Phase 60.
**Delivers:** "(not active yet)" section staged for deletion; "aim to" SLO with severity tiers (critical 14d, high 30d, medium 90d, low no commitment); coordinated disclosure 90-day default; over-capacity acknowledgement pattern; supported-versions table refreshed; `docs/MAINTAINER-RUNBOOK.md` or `docs/POSTFLIP-PLAYBOOK.md` (release procedure, freeze triggers, burnout triggers, repo-settings appended to `docs/RELEASE.md`); test-advisory ritual documented.
**Avoids:** PITFALLS 11, 12.

### Phase 58: Release-gate extension (8 to 11-13 checks)

**Rationale:** Phase 49 idiom. MUST come after 53-55. Two-tier execution prevents flaky pre-merge.
**Delivers:** 3-5 new release-gate checks (recommended cut: `release-workflow-signing-present`, `release-workflow-sbom-present`, `local-pip-audit-clean`; optional: `audit-workflow-present`, `dependabot-config-present`, `actions-pinned-by-sha`); `--check` enum APPENDED; env-var override; new test file; two-tier split with offline-mode + retry-with-cap; structured JSON report; `scripts/verify_release.py` 5-check trust-chain.
**Avoids:** PITFALLS 8, 11, all earlier (gate is enforcement layer).

### Phase 59: Soft launch + release rehearsal

**Rationale:** Last opportunity to identify friction BEFORE the public flip.
**Delivers:** 3-5 invited-contributor sample PRs end-to-end; friction patched; CHANGELOG credits; `v0.6.0-rc1` release rehearsal on fork; `.planning/rollback/flip-gate-revert.md` ready.
**Avoids:** PITFALL 10.

### Phase 60: Gate flip + v0.6.0 release

**Rationale:** Single atomic commit lands all external-bit-flip prose changes.
**Delivers:** Atomic commit: STATUS.md TL;DR + milestone row to SHIPPED; README "Project status" rewrite + badge to v0.6.0; CONTRIBUTING.md NOTICE deletion activated; PR template NOTICE deletion activated; SECURITY.md "(not active yet)" deletion activated; `issue-claim-watcher.yml` deleted; saved replies updated; `docs/POSTFLIP-PLAYBOOK.md`; `accepted-for-review` throttle active for 30 days; pinned Discussion announcement; version bumps; CHANGELOG promotion; release_gate.py 11-13/N green; tag pushed (gitsign-signed); release.yml runs; GitHub Release with all artifacts atomically attached.
**Avoids:** PITFALLS 10, 11.

### Phase Ordering Rationale

- **Phase 51 MUST land first** — PITFALL 1 + 2 hardening is precondition for everything else.
- **Phases 53 || 54** parallel — both consume Phase 51 substrate but not each other.
- **Phase 55 after 51** — Dependabot github-actions only works against SHA pins; security-update ungrouping must land BEFORE first grouped PR.
- **Phases 56 || 57** parallel — different files. Decision files land in Phase 56 BEFORE docs they inform.
- **Phase 58 after 53-55** — new checks grep files those phases create.
- **Phase 59 before 60** — rehearsal is dress rehearsal for flip.
- **Phase 60 lands AS A SINGLE ATOMIC COMMIT** — contributors never see contradictory signals.

### Research Flags

Phases likely needing deeper research during planning:

- **Phase 53 (signing):** sigstore-python identity-verification semantics, gitsign vs `git tag -s` decision, PyPI Trusted Publishing IF in scope.
- **Phase 55 (Dependabot):** grouped-security-updates beta semantics evolve; pip-audit dual-run timing budget.
- **Phase 58 (release-gate extension):** two-tier split + offline-mode design (patterns not well-documented in any single source).

Phases with standard patterns (skip research-phase):

- **Phase 51 (CI hardening):** SHA-pinning + actionlint well-trodden.
- **Phase 56 (contributor docs):** prose against existing v0.5 scaffold; exemplar list comprehensive.
- **Phase 57 (SECURITY refresh):** targeted edits to existing file.
- **Phase 59 (soft launch + rehearsal):** maintainer-driven.
- **Phase 60 (atomic flip):** Phase 50 precedent.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Every version verified against PyPI or upstream release page; step shapes verified against Context7 / official GitHub docs |
| Features | HIGH on table-stakes + anti-features; MEDIUM on borderline differentiators | Exemplar repos cover the bar; borderline calls (CodeQL required, SLSA L3, safe-to-test) explicitly flagged |
| Architecture | HIGH on integration points; MEDIUM on tool choices PROJECT.md flags for requirements-time locking | Every change maps to precedent phase (38, 39, 47, 48, 49, 50); 15 byte-identity invariants enumerated |
| Pitfalls | HIGH on failure modes (verified against published 2024-2026 incidents); MEDIUM on first-week probability; LOW on solo-maintainer SLO numbers | Pitfall-to-Phase mapping complete |

**Overall confidence:** HIGH.

### Gaps to Address

- **PyPI publishing in v0.6 yes/no.** STACK + ARCHITECTURE recommend defer; FEATURES treats T1-T2 as table-stakes IF publishing happens; PITFALL 9 sequencing applies IF in scope. **Requirements-definer must lock before Phase 53 plans.**
- **Tag signing mechanism: gitsign vs `git tag -s`.** ARCHITECTURE recommends one-character change in `docs/RELEASE.md`; PITFALL 11 + decision file recommend gitsign with OIDC. Affects whether maintainer needs local GPG keypair in scope.
- **`safe-to-test` label gate actually needed in v0.6?** v0.5 tests use recorded responses. **Recommendation: NO; defer scaffolding to v0.7 if ever.**
- **Conduct reporting channel:** GHSA-private-advisory `[conduct]` title route vs dedicated email. ARCHITECTURE leans GHSA route. Lock at requirements time.
- **Number of new release-gate checks.** STACK proposes 5; ARCHITECTURE recommends 3 for cleanest cut. **Recommendation: ship 3-5 depending on greppable redundancy tolerance.**
- **`docs/MAINTAINER-RUNBOOK.md` vs `docs/POSTFLIP-PLAYBOOK.md` naming/scope.** **Recommendation: ONE doc covering both release procedure AND freeze/burnout triggers.**

## Sources

### Primary (HIGH confidence)

- **Context7:** `/sigstore/docs`, `/pypa/pip-audit`, `/cyclonedx/cyclonedx-python-lib`
- **PyPI release pages:** sigstore 4.2.0, pip-audit 2.10.0, cyclonedx-bom 7.3.0, safety (paid-tier confirmed)
- **GitHub release pages:** attest-build-provenance v4.1.0, gh-action-sigstore-python v3.3.0, gh-action-pip-audit v1.1.0, dependency-review-action v5.0.0, pinact v4.0.0
- **Official docs:** GitHub Actions security-hardening, PyPI digital attestations (PEP 740), PEP 807 Trusted Publishing, slsa.dev v1.0
- **Existing horus-os files:** PROJECT.md, ci.yml, release_gate.py, RELEASE.md, pyproject.toml, SECURITY.md, STATUS.md, CONTRIBUTING.md, PR template

### Secondary (MEDIUM confidence)

- 2024-2026 supply-chain incidents: Ultralytics 8.3.41-46 (PyPI Blog, Wiz, Snyk); tj-actions CVE-2025-30066 (Unit 42, Cycode, Harness); "testedbefore" March 2026 (#179107); Spotipy GHSA-h25v-8c87-rvm8; sigstore-java GHSA-jp26-88mw-89qr; Wiz LiteLLM TeamPCP
- Best practices: GitHub Security Lab (pwn-requests, untrusted-input), StepSecurity, Trail of Bits, Sbomify 2026 PyPI scan (1.58% adoption, ALL CycloneDX)
- CLA/DCO: Ben Balter, Open Source Guides "Maintaining Balance," OSI/Socket survey
- Stale-bot critiques: Drew DeVault, Jacob Tomlinson, Curtis Newton IEEE study
- Exemplar repos: pypa/sampleproject, pypa/pip-audit, sigstore/sigstore-python, pydantic, httpx, black, uv, cpython, devguide, numpy, dependabot-core

### Tertiary (LOW confidence, needs validation at planning time)

- Specific solo-maintainer SLO numbers
- First-week PR-volume estimates (throttle triggers: 25 PRs, 75 issues)
- OpenSSF Scorecard initial target (7.5+)

---
*Research completed: 2026-05-29*
*Ready for roadmap: yes*
