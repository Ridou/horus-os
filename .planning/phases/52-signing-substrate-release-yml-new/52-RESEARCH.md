# Phase 52: Signing substrate (`release.yml` NEW) — Research

**Researched:** 2026-05-29
**Domain:** Supply-chain trust substrate (sigstore-python keyless OIDC artifact signing + SLSA Build L2 provenance + gitsign tag signing + user-facing 5-check trust-chain verifier)
**Confidence:** HIGH on action SHAs, sigstore-python CLI shape, attest-build-provenance v4 inputs, gitsign config, release-trigger semantics, project byte-identity invariants. MEDIUM on `.sigstore` bundle filename suffix (sigstore-python docs are ambiguous between `.sigstore` and `.sigstore.json`; both observed in different sources — planner picks the one the action actually emits at execution time and pins it in the fixture).

## Summary

Phase 52 lands a NEW `.github/workflows/release.yml` triggered on `release: types: [published]`, with one `sign-and-attest` job that (1) builds wheel+sdist, (2) signs via `sigstore/gh-action-sigstore-python` keyless OIDC, (3) emits SLSA Build L2 provenance via two per-artifact `actions/attest-build-provenance` invocations, plus a NEW `scripts/verify_release.py` that ships the full 5-check skeleton (wheel-signature, sdist-signature, tag-signature, sbom-signature STUB, changelog-cross-ref) and shells out to `python -m sigstore verify identity` + `git verify-tag` from stdlib only. Tag signing migrates from `git tag -a` to `git tag -s` with a new gitsign pre-flight check inserted at step 6.5 of the docs/RELEASE.md STOP-BEFORE-TAG block. PyPI Trusted Publishing deferral lands as `.planning/decisions/no-pypi-in-v0.6.md` referenced from a new PROJECT.md key-decisions row in the same commit. CONTEXT.md decisions D-01..D-10 are all confirmed implementable on current upstream stack versions.

**Primary recommendation:** Pin every `uses:` to the four SHAs in §Standard Stack, write release.yml with the exact step shape in §Architecture Patterns Pattern 1, model verify_release.py on `scripts/release_gate.py`'s `CheckResult` + `_print_result` + argparse-enum dispatch (lines 137-148, 634-640, 678-766), record the canonical fixture by pushing a `v0.6.0-rc1` tag to a maintainer fork ahead of plan execution, and treat the SBOM check #4 as a wired STUB returning `ok=None` until Phase 53 flips it.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Wheel + sdist signing | CI / Release workflow (GitHub Actions) | — | Keyless OIDC requires GitHub Actions OIDC issuer + `id-token: write`; cannot run locally |
| SLSA Build L2 provenance | CI / Release workflow (GitHub Actions) | GitHub Attestations API | `actions/attest-build-provenance` writes to GitHub's attestation store; bound to workflow identity |
| Tag signing | Maintainer workstation (local git) | sigstore Fulcio (transparency log) | `git tag -s` runs on the maintainer's machine; gitsign mints an ephemeral Fulcio cert via OAuth browser flow |
| User-facing trust verification | User workstation (post-install Python script) | sigstore-python CLI (subprocess) | `scripts/verify_release.py` is shipped in-repo so any cloner can run `python scripts/verify_release.py --version 0.6.0` without installing horus-os runtime deps |
| Trust-decision documentation | Project repo (decisions/ + PROJECT.md table) | — | `no-pypi-in-v0.6.md` + key-decisions table row is plain prose, no runtime/CI component |
| Canonical-fixture sourcing | Maintainer fork (release rehearsal) → committed test fixtures | — | Pre-recorded `.sigstore` bundle from a v0.6.0-rc1 rehearsal release is the test asset; live signing in test CI is forbidden (`id-token: write` in test runner = attack surface expansion) |

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** ONE job `sign-and-attest` on `ubuntu-latest`; sequential steps `checkout → setup-python 3.12 → install build → python -m build → sigstore-python sign with release-signing-artifacts: true → per-artifact attest-build-provenance`. Full chain MUST complete within 5 minutes of `id-token: write` OIDC mint (SIGN-01).
- **D-02:** Top-level `permissions: read-all`; per-job `{ id-token: write, contents: write, attestations: write }` only on `sign-and-attest`. (`id-token: write` for OIDC; `contents: write` for release-asset upload; `attestations: write` for GH attestation API.)
- **D-03:** `verify_release.py` is stdlib-only Python; shells out to `python -m sigstore verify identity` and `git verify-tag` via `subprocess.run(..., capture_output=True, check=False)`. Sigstore is NEVER added to runtime or `[dev]` deps; script prints `pip install sigstore` hint and exits non-zero if `python -m sigstore` is absent.
- **D-04:** `EXPECTED_IDENTITY_TEMPLATE = "https://github.com/Ridou/horus-os/.github/workflows/release.yml@refs/tags/{version}"` hardcoded module constant; `EXPECTED_ISSUER = "https://token.actions.githubusercontent.com"`; `--cert-oidc-issuer` flag MANDATORY (script refuses to run without it); `--version` flag MANDATORY (interpolates into template); NO wildcards, NO regex, NO fallback.
- **D-05:** `docs/RELEASE.md` STOP-BEFORE-TAG block gets TWO insertions: NEW step 6.5 (gitsign pre-flight `git config --get gitsign.connectorID` non-empty assert + reference to `docs/MAINTAINER-RUNBOOK.md` Phase 56), and step 7 command swap `git tag -a vN.M.P -m ...` → `git tag -s vN.M.P -m ...`. Existing steps 1-6 and 8-9 prose UNCHANGED.
- **D-06:** Per-artifact `actions/attest-build-provenance` invocations: one with `subject-path: 'dist/*.whl'`, one with `subject-path: 'dist/*.tar.gz'`. Phase 53 appends a third for `dist/*.sbom.json`.
- **D-07:** `tests/fixtures/sigstore/canonical/` seeded by pre-recorded `.sigstore` bundle from a maintainer-fork v0.6.0-rc1 rehearsal release. Wrong-identity fixture OWNED by Phase 58 (TEST-24).
- **D-08:** Full 5-check skeleton ships in Phase 52. Check #4 (sbom-signature) returns `ok=None` with diagnostic `SKIPPED — Phase 53 lands SBOM generation + signing` until Phase 53 flips the stub.
- **D-09:** `.planning/decisions/no-pypi-in-v0.6.md` + PROJECT.md key-decisions table row APPENDED in same atomic commit (SIGN-05 contract).
- **D-10:** release.yml sigstore-python `inputs:` in Phase 52 is exactly `./dist/*.whl ./dist/*.tar.gz` (two-glob whitespace-separated). Phase 53 APPENDS ` ./dist/*.sbom.json`.

### Claude's Discretion

- Exact SHA values for the four actions (planner uses `pinact run --update` OR `gh api repos/{owner}/{repo}/git/refs/tags/{tag}` — resolved in §Standard Stack of this RESEARCH.md with citations).
- `sigstore-python` action version range vs. specific pin (`>=4.2,<5` is the SIGN-01 contract; pinning the action SHA is the load-bearing decision — the library version range is a courtesy lower bound).
- Exact `gitsign` install instructions in `docs/MAINTAINER-RUNBOOK.md` (Phase 56 owns; Phase 52 forward-references).
- argparse subcommand vs. flag-only CLI shape for `verify_release.py` (research recommends flag-only mirroring `release_gate.py` precedent — see §Code Examples).

### Deferred Ideas (OUT OF SCOPE)

- SBOM generation step in release.yml — Phase 53 owns; sigstore `inputs:` glob WIDENS in Phase 53.
- `actions/attest-sbom` invocations — Phase 53.
- `release-workflow-signing-present` release-gate check — Phase 57. Phase 52 must ensure the literal `sigstore/gh-action-sigstore-python` appears in release.yml's `uses:` line so Phase 57's grep succeeds.
- `release-workflow-sbom-present` release-gate check — Phase 57.
- `actions-pinned-by-sha` release-gate check coverage of release.yml — Phase 57. Phase 52's contribution is ensuring every `uses:` in release.yml is SHA-pinned.
- Wrong-identity negative fixture + assertion (TEST-24) — Phase 58.
- PyPI Trusted Publishing wiring (PEP 807) — deferred to v0.7+ per D-09. Decision file lands in Phase 52; wiring itself is out of scope.
- Sigstore Rekor private deployment — out of scope for any v0.6 phase.
- `zizmor` workflow audit on release.yml — Phase 54.
- `docs/MAINTAINER-RUNBOOK.md` gitsign one-time setup content — Phase 56.
- `docs/POSTFLIP-PLAYBOOK.md` rollback — Phase 59.
- Release-rehearsal procedure prose in `docs/RELEASE.md` "Release rehearsal" subsection — Phase 58. Phase 52 ships the rehearsal ARTIFACT (the fixture); Phase 58 ships the PROCEDURE.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SIGN-01 | NEW `release.yml` on `release: published`; sigstore-python ≥4.2,<5 signs wheel+sdist+SBOM JSON via `gh-action-sigstore-python@<sha>`; `.sigstore` bundle (NOT detached `.sig`); sign within 5 min of OIDC mint | §Standard Stack table row 1+2; §Architecture Patterns Pattern 1; §Pitfall 1 (OIDC TTL); §Code Examples §1 |
| SIGN-02 | `actions/attest-build-provenance@<sha>` generates SLSA Build L2 provenance bound to workflow identity; verifiable via `gh attestation verify`; per-artifact | §Standard Stack table row 3; §Architecture Patterns Pattern 1; D-06 implementation; §Code Examples §1 (two attest steps) |
| SIGN-03 | Tag signing via `gitsign` (keyless OIDC); no GPG keypair; `docs/RELEASE.md` STOP-BEFORE-TAG documents the configured `git tag` invocation; tag verification uses workflow-scoped identity | §Standard Stack table row 4 (gitsign reference); §Architecture Patterns Pattern 2 (RELEASE.md insertions); §Code Examples §3 (gitsign config) |
| SIGN-04 | `scripts/verify_release.py` NEW with hardcoded `EXPECTED_IDENTITY` template; mandatory `--cert-oidc-issuer`; canonical fixture passes; wrong-identity fixture rejected (TEST-24 = Phase 58) | §Architecture Patterns Pattern 3 (verify_release.py skeleton); §Code Examples §2 (script shape); §Pitfall 1 mitigation; §Code Examples §4 (test pattern) |
| SIGN-05 | PyPI Trusted Publishing (PEP 807) OUT OF SCOPE; deferral in `.planning/decisions/no-pypi-in-v0.6.md`; referenced from PROJECT.md key-decisions table | §Architecture Patterns Pattern 4 (decision file shape); §Pitfall 3 (sequencing); D-09 atomic-commit requirement |

## Project Constraints (from CLAUDE.md)

The planner MUST honor these directives — they have the same authority as CONTEXT.md locked decisions.

- **No em-dashes in committed prose** (CLAUDE.md HR3). Affects: release.yml comments, verify_release.py docstrings + diagnostics, no-pypi-in-v0.6.md, PROJECT.md row, RELEASE.md step 6.5 prose, fixture README. Use commas, periods, or hyphens.
- **No PII / no real secrets / no contributor names** in committed text (CLAUDE.md HR1). Use placeholders like `your-api-key`, `your-project-name`. `EXPECTED_IDENTITY_TEMPLATE` literally contains `Ridou/horus-os` because that IS the project repo path (the load-bearing identity claim); this is the only contributor handle that appears in committed text by design.
- **Apache 2.0 license applies; new files do not need per-file header for v0.6** (CLAUDE.md HR2).
- **ruff lint + format MUST pass** (CLAUDE.md HR4). Run `ruff check .` and `ruff format --check .` before each commit. verify_release.py and any new tests must pass both.
- **pytest from repo root; 3-OS × 2-Python matrix** (CLAUDE.md HR5). `tests/test_release_verification.py` must run cleanly on ubuntu-latest, macos-latest, windows-latest under Python 3.11 and 3.12. Use `pathlib` everywhere; `sys.executable -m sigstore ...` to invoke the verifier (do not assume `python` is on `$PATH`).
- **Commits: present tense, conventional-commit prefix; reference phase** (CLAUDE.md HR6). Example: `feat(52): land release.yml signing substrate` or `docs(52): record PyPI deferral decision`.
- **`pip install -e '.[dev]'` is the canonical development install.** Sigstore CLI is NOT in `[dev]` (D-03); verify_release.py prints an install hint if absent.
- **Cross-OS path handling: pathlib, never raw string concatenation** (CLAUDE.md "Workflow expectations"). Tests use `pathlib.Path` for fixture paths.
- **`.planning/` is public** (CLAUDE.md "Workflow expectations"); the decision file lives there and is committed.

## Standard Stack

### Core

| Library / Action | Version | SHA (40-char) | Purpose | Source |
|------------------|---------|---------------|---------|--------|
| `actions/checkout` | v4.2.2 | `11bd71901bbe5b1630ceea73d27597364c9af683` | Checkout repo into runner | `[VERIFIED: ci.yml line 23 post-Phase-51]`; aligns with the Phase 51 pin already in use |
| `actions/setup-python` | v5.6.0 | `a26af69be951a213d495a4c3e4e4022e16d87065` | Provision Python 3.12 on runner | `[VERIFIED: ci.yml line 28 post-Phase-51]` |
| `sigstore/gh-action-sigstore-python` | v3.3.0 | `04cffa1d795717b140764e8b640de88853c92acc` | Keyless OIDC sign wheel + sdist; emit `.sigstore` bundle; auto-attach to GitHub Release | `[VERIFIED: gh api repos/sigstore/gh-action-sigstore-python/git/refs/tags/v3.3.0 → object.sha = 04cffa1d... (type: commit)]`; release page https://github.com/sigstore/gh-action-sigstore-python/releases/tag/v3.3.0 (2025-03-26) |
| `actions/attest-build-provenance` | v4.1.0 | `a2bbfa25375fe432b6a289bc6b6cd05ecd0c4c32` | SLSA Build L2 provenance attestation bound to workflow identity; writes to GH attestation API | `[VERIFIED: gh api repos/actions/attest-build-provenance/git/refs/tags/v4.1.0 → object.sha = a2bbfa25... (type: commit)]`; release page https://github.com/actions/attest-build-provenance/releases/tag/v4.1.0 (2025-02-26) |

**SLSA Build Level produced by `actions/attest-build-provenance@v4.1.0`:** Build L2. `[CITED: slsa.dev/spec/v1.0/levels — "L2 = hosted build platform with signed provenance, achievable via attest-build-provenance"; corroborated by .planning/research/STACK.md table row, lines 17-18, 25]`. SLSA L3 requires the `slsa-framework/slsa-github-generator` reusable workflow and is explicitly DEFERRED to v0.7+ per STACK.md line 261 (alternatives table).

**`sigstore-python` library version** (wrapped by the action): the SIGN-01 contract says `>=4.2,<5`. v3.3.0 of `gh-action-sigstore-python` ships `sigstore-python 4.2.0` internally `[CITED: .planning/research/STACK.md line 18 + line 310 "v3.x action pins to sigstore-python 4.2.0 internally"]`. Pinning the action SHA is the load-bearing decision; the library version range is a courtesy lower bound for the user's local `pip install sigstore` (D-03 hint).

### Supporting

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `gitsign` | Sigstore-for-git: keyless OIDC signing of git tags via Fulcio ephemeral cert | Maintainer workstation only; one-time `git config` setup; `git tag -s` then invokes gitsign instead of GPG. Phase 56 lands install/config prose in `docs/MAINTAINER-RUNBOOK.md`; Phase 52 forward-references that file from RELEASE.md step 6.5. |
| `sigstore` (Python package) | `python -m sigstore verify identity` CLI shelled out by verify_release.py | User workstation only; verify_release.py prints `pip install sigstore` hint if `python -m sigstore --version` fails (per D-03). NEVER added to `[project.dependencies]` or `[dev]` extras. |
| `gh` CLI | `verify_release.py` check #5 (changelog-cross-ref) shells out to `gh release view v<version> --json body --jq .body` | User workstation; verify_release.py prints `gh CLI install hint` (https://cli.github.com/) if absent. Already a maintainer tool per existing RELEASE.md step 8 (`gh release create`). |
| `git` CLI | `verify_release.py` check #3 shells out to `git verify-tag v<version>` | User workstation; ubiquitous; no install-hint branch needed (script can hard-fail with `git: command not found` from subprocess). |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `sigstore/gh-action-sigstore-python` (keyless OIDC) | `sigstore/cosign-installer` + `cosign sign-blob` | cosign is the right tool for OCI containers, not Python wheels. cosign's bundle format differs from sigstore-python's for blobs; pip and PEP 740 consume sigstore-python's format. REJECTED per `.planning/research/PITFALLS.md` Pitfall 3 line 100-102. |
| `actions/attest-build-provenance@v4` (SLSA L2) | `slsa-framework/slsa-github-generator/.github/workflows/generator_generic_slsa3.yml@v2.1.0` (SLSA L3) | SLSA L3 requires an isolated builder workflow (more setup, less debuggable). For v0.6 contribution-gate goals, L2 is sufficient. REJECTED for v0.6 per STACK.md line 261. v0.7+ may revisit. |
| Per-artifact `subject-path: 'dist/*.whl'` and `'dist/*.tar.gz'` (D-06) | Single `subject-path: 'dist/*'` glob | Single-glob is terser but obscures which artifact failed if attestation generation hiccups on one but not others. REJECTED per CONTEXT.md D-06: per-artifact gives 1:1 mapping between CI step and verifiable artifact. |
| `gitsign` for tag signing | `git tag -s` with maintainer-controlled GPG keypair | GPG requires key generation, key rotation discipline, key backup, public-key distribution. Leaked key = silent forgery risk. Keyless OIDC binds to the maintainer's GitHub identity (revocation = repo settings change). REJECTED per `.planning/research/PITFALLS.md` Pitfall 11 lines 484-486, 496-498. |
| Hardcoded `EXPECTED_IDENTITY` (D-04) | JSON config file at `tests/fixtures/sigstore/identity.json` | Config file invites future drift ("someone fixes verification by relaxing the regex"); reintroduces PITFALL 3 (wildcard identity silently accepts attacker signatures). REJECTED per CONTEXT.md D-04. |
| `release: types: [published]` trigger | `push: tags: ['v*.*.*']` | Tag-push trigger skips the human-confirmation gate (`gh release create` is step 8 of STOP-BEFORE-TAG). Release-published trigger fires AFTER step 8, preserving the maintainer's STOP point. REJECTED per CONTEXT.md domain + ARCHITECTURE.md §Q1 line 120. |
| 5-check shipped as 4 active + 1 added in Phase 53 | 5-check skeleton with stubbed check #4 (D-08) | 4-active approach forces Phase 53 to touch CLI enum, dispatch order, report formatter — more drift surface. Stub-flip approach is a single-line edit in Phase 53. REJECTED per CONTEXT.md D-08. |

**Installation:**

```bash
# CI side (in release.yml; install on the fly, NOT a dev/runtime dep):
python -m pip install --upgrade pip build

# User side (when running verify_release.py locally):
pip install sigstore   # printed as install hint by verify_release.py if absent
# git and gh are assumed; verify_release.py hard-fails with a clear diagnostic otherwise

# Maintainer side (one-time, before v0.6.0 tag push):
brew install gitsign   # macOS; Linux: go install github.com/sigstore/gitsign@latest
git config --global gpg.x509.program gitsign
git config --global gpg.format x509
git config --global tag.gpgSign true
git config --global gitsign.connectorID https://github.com/login/oauth
```

`[CITED: gitsign README — install + config snippet verbatim from https://github.com/sigstore/gitsign]`

**Version verification:**

```bash
# Re-resolve each action SHA at plan-time to confirm tag has not moved
# (defense against tj-actions-style retargeting, even on first-party actions):
gh api repos/sigstore/gh-action-sigstore-python/git/refs/tags/v3.3.0 --jq '.object.sha'
gh api repos/actions/attest-build-provenance/git/refs/tags/v4.1.0 --jq '.object.sha'
gh api repos/actions/checkout/git/refs/tags/v4.2.2 --jq '.object.sha'
gh api repos/actions/setup-python/git/refs/tags/v5.6.0 --jq '.object.sha'
```

Document the verified SHA + publication date in the plan; the SHAs in §Standard Stack above were resolved on 2026-05-29 via `gh api` (commit type, not annotated-tag type, so the SHA is the dereferenced commit hash usable directly in `uses:`).

## Architecture Patterns

### System Architecture Diagram

```
                            release.yml (NEW)
                       triggered: release.published
                                │
                                v
  ┌──────────────────────────────────────────────────────────────┐
  │  sign-and-attest job (ubuntu-latest)                         │
  │  permissions: { id-token: write, contents: write,            │
  │                 attestations: write }                        │
  │                                                              │
  │  step 1: actions/checkout (persist-credentials: false)       │
  │  step 2: actions/setup-python (3.12, cache: pip)             │
  │  step 3: pip install build                                   │
  │  step 4: python -m build  → dist/*.whl + dist/*.tar.gz       │
  │  step 5: sigstore-python sign                                │
  │           inputs: ./dist/*.whl ./dist/*.tar.gz               │
  │           release-signing-artifacts: true                    │
  │           → mints OIDC token internally                      │
  │           → emits .sigstore bundles                          │
  │           → attaches bundles to the triggering Release       │
  │  step 6: attest-build-provenance (wheel)                     │
  │           subject-path: 'dist/*.whl'                         │
  │           → writes attestation to GH attestation API         │
  │  step 7: attest-build-provenance (sdist)                     │
  │           subject-path: 'dist/*.tar.gz'                      │
  └──────────────────────────────────────────────────────────────┘
                                │
                                │ (5-minute OIDC budget elapses here)
                                v
                  ┌──────────────────────────────┐
                  │  GitHub Release page         │
                  │  - dist/*.whl                │
                  │  - dist/*.tar.gz             │
                  │  - dist/*.whl.sigstore       │
                  │  - dist/*.tar.gz.sigstore    │
                  │  + GH attestations API       │
                  └──────────────────────────────┘

                                ║
                                ║ (parallel surface, maintainer workstation, one-time)
                                v
   maintainer one-time gitsign setup → tag.gpgSign = true
                                │
                                v
   docs/RELEASE.md STOP-BEFORE-TAG step 6 (push to main, CI green)
   docs/RELEASE.md STOP-BEFORE-TAG step 6.5 (NEW)
     git config --get gitsign.connectorID  → must be non-empty
   docs/RELEASE.md STOP-BEFORE-TAG step 7 (MODIFIED)
     git tag -s vN.M.P -m "..."    ← was: git tag -a vN.M.P -m "..."
     git push origin vN.M.P
   docs/RELEASE.md STOP-BEFORE-TAG step 8 (gh release create)
                                │
                                v
              release.yml fires; signing chain begins

                                ║
                                ║ (user verification path, post-install)
                                v
  scripts/verify_release.py  (NEW; stdlib-only; subprocess to external tools)
     --version 0.6.0  --cert-oidc-issuer https://token.actions.githubusercontent.com
     [--check {wheel|sdist|tag|sbom|changelog}]
     ├─ check #1 wheel-signature   → subprocess: python -m sigstore verify identity ...
     ├─ check #2 sdist-signature   → subprocess: python -m sigstore verify identity ...
     ├─ check #3 tag-signature     → subprocess: git verify-tag v<version>
     ├─ check #4 sbom-signature    → STUB (ok=None) until Phase 53
     └─ check #5 changelog-cross-ref → subprocess: gh release view + grep CHANGELOG.md
```

### Recommended Project Structure

```
.github/workflows/
  release.yml                                       # NEW
  ci.yml                                            # UNTOUCHED (post-Phase-51)
  issue-claim-watcher.yml                           # UNTOUCHED (deletion in Phase 59)

scripts/
  verify_release.py                                 # NEW (stdlib-only; ~200 lines)
  release_gate.py                                   # UNTOUCHED (Phase 57 extension)
  lint_no_wallclock.py                              # UNTOUCHED (reference precedent)

tests/
  test_release_verification.py                      # NEW (~100 lines; positive-fixture path only)
  fixtures/sigstore/
    canonical/
      README.md                                     # NEW (documents the rehearsal recording procedure)
      horus_os-0.6.0rc1-py3-none-any.whl            # NEW (artifact from v0.6.0-rc1 rehearsal)
      horus_os-0.6.0rc1-py3-none-any.whl.sigstore   # NEW (bundle from same rehearsal)
    # wrong_identity/ ships in Phase 58 (TEST-24); NOT this phase

.planning/decisions/                                # NEW directory (first decision file)
  no-pypi-in-v0.6.md                                # NEW (1-page rationale)

docs/
  RELEASE.md                                        # MODIFIED (step 6.5 inserted + step 7 command swap)
  MAINTAINER-RUNBOOK.md                             # NOT YET (Phase 56 creates; Phase 52 forward-refs only)

PROJECT.md                                          # MODIFIED (NEW key-decisions row appended)
```

### Pattern 1: release.yml job shape (D-01, D-02, D-06, D-10)

**What:** One sequential job that builds, signs, attests — no inter-job artifact upload, OIDC token mint happens inside the sigstore-python action and the sign step completes within 5 minutes of mint (the SIGN-01 budget).

**When to use:** Once per release. Trigger fires AFTER the maintainer runs `gh release create vN.M.P --notes-file /tmp/release-notes.md` (step 8 of docs/RELEASE.md STOP-BEFORE-TAG). The release.published event preserves the human-confirmation gate.

**Example:** see §Code Examples §1.

### Pattern 2: docs/RELEASE.md STOP-BEFORE-TAG insertions (D-05)

**What:** Two surgical insertions into the 9-step STOP-BEFORE-TAG sequence:

1. **NEW step 6.5** between existing step 6 (push + CI-green confirmation) and existing step 7 (tag creation):
   ```
   6.5. Confirm `gitsign` is configured. Run
        `git config --get gitsign.connectorID` and confirm the
        output is non-empty (typically
        `https://github.com/login/oauth`). If empty, follow the
        one-time gitsign setup in `docs/MAINTAINER-RUNBOOK.md`.
        Do not proceed to step 7 until configured.
   ```

2. **MODIFIED step 7 command line** — only the literal `git tag -a` → `git tag -s` substitution; surrounding prose unchanged:
   ```diff
   - `git tag -a vN.M.P -m "vN.M.P - <milestone-name>"`.
   + `git tag -s vN.M.P -m "vN.M.P - <milestone-name>"`.
   ```

**When to use:** This pattern is the byte-identity contract per ARCHITECTURE.md line 102 ("STOP-BEFORE-TAG block prose — v0.6 prepends new steps to the pre-tag list, MUST NOT mutate existing prose"). Insertions are allowed; mutations to steps 1-6 and 8-9 are forbidden. Phase 51 D-06 carries this discipline forward.

### Pattern 3: verify_release.py 5-check skeleton with stubbed check #4 (D-03, D-04, D-08)

**What:** A stdlib-only Python script modeled on `scripts/release_gate.py`:

- `@dataclass(frozen=True) class CheckResult: name: str; ok: bool | None; diagnostic: str` (lines 137-148 of release_gate.py)
- Module-level `EXPECTED_IDENTITY_TEMPLATE = "https://github.com/Ridou/horus-os/.github/workflows/release.yml@refs/tags/{version}"` and `EXPECTED_ISSUER = "https://token.actions.githubusercontent.com"` constants (hardcoded; never read from config)
- Per-check function with signature `def check_<name>(...) -> CheckResult:` (mirrors release_gate.py §1-8 functions)
- argparse with `--version` (REQUIRED), `--cert-oidc-issuer` (REQUIRED — script refuses without it), `--check {wheel|sdist|tag|sbom|changelog}` (optional, runs all if absent), `--bundle PATH`, `--artifact PATH` (test-mode injection of fixture paths)
- Dispatch list in `main()` mirroring release_gate.py:716-759 dispatch shape
- `_print_result` formatter mirroring release_gate.py:634-640 (`OK`/`FAIL`/`SKIP` prefix)
- Check #4 returns `CheckResult(name="sbom-signature", ok=None, diagnostic="SKIPPED — Phase 53 lands SBOM generation + signing")`
- Module-import-time `assert "refs/tags/{version}" in EXPECTED_IDENTITY_TEMPLATE` defends against accidental edits that break the workflow-scoped identity contract

**When to use:** Default invocation runs all 5 checks; `--check` runs one. Returns exit 0 only when no check has `ok=False` (skipped checks are not failures). Test-mode invocation via `tests/test_release_verification.py` feeds the canonical fixture paths via `--bundle` and `--artifact` and asserts exit 0.

**Example:** see §Code Examples §2.

### Pattern 4: `.planning/decisions/no-pypi-in-v0.6.md` + PROJECT.md key-decisions row (D-09, SIGN-05)

**What:** A short (≤ 1 page) rationale file in a new `.planning/decisions/` directory, ending with a `**Decision (final, until revisited):**` block; referenced from PROJECT.md's key-decisions table (`.planning/PROJECT.md` line 74). Both land in the SAME COMMIT (SIGN-05 atomicity).

**When to use:** Phase 52 establishes the `.planning/decisions/` directory; Phase 56 lands sibling files (`sigstore-keyless.md`, `no-cla.md`, `no-stale-bot.md`, `sbom-cyclonedx.md`). All decision files follow the same prose shape: one paragraph stating the decision, one paragraph stating the rationale, one paragraph stating the conditions under which to revisit, one terminating `**Decision (final, until revisited):**` line.

**Example:** see §Code Examples §5.

### PROJECT.md key-decisions table exact format

The existing table at `.planning/PROJECT.md` line 74-81 has this shape:

```markdown
## Key Decisions

| Decision | Rationale | Status |
|----------|-----------|--------|
| Anthropic + Gemini, no abstraction layer | Both providers have first-class SDK support and well-documented APIs. ... | accepted (v0.1) |
| ...                                       | ...                                                                       | ...             |
```

**Phase 52 appends one row at the table end (no row reordering, no edits to existing rows):**

```markdown
| No PyPI publishing in v0.6 (Trusted Publishing PEP 807 deferred) | horus-os does not currently publish to PyPI. Standing up Trusted Publishing requires a PyPI project + maintainer setup outside the v0.6 contribution-gate scope. Decision documented in `.planning/decisions/no-pypi-in-v0.6.md`. | accepted (v0.6) |
```

(No em-dashes; placeholder rendered as `deferred` not `—`. Status column convention: `accepted (vX.Y)` matches all existing rows.)

### Anti-Patterns to Avoid

- **Two-job (build then sign) workflow split.** Loses dist artifact context between jobs (requires `actions/upload-artifact` round-trip); risks OIDC TTL breach for the build → sign gap (Pitfall 1). REJECTED per CONTEXT.md D-01 rationale.
- **Workflow-level `id-token: write`.** Lets every job mint OIDC tokens; violates least-privilege; breaks CIHARD-02 per-job opt-in pattern. Use per-job opt-in on `sign-and-attest` only.
- **Wildcards in `EXPECTED_IDENTITY` (`*`, `.*`, regex).** sigstore-python uses EXACT match for `--cert-identity`; cosign uses regex via `--certificate-identity-regexp`. Mixing the two semantic models is the exact bug class Pitfall 1 prevents.
- **Reading `EXPECTED_IDENTITY` from a JSON config file.** Invites future drift; reintroduces Pitfall 1 risk. Hardcoded constant only.
- **Detached `.sig` + `.crt` signatures.** Require network round-trip to fetch the Rekor inclusion proof at verify time; `.sigstore` bundles include the proof inline. PEP 740 consumes bundles, not detached sigs.
- **Signing the wheel before building it.** Build MUST precede sigstore-python action (the action signs whatever is at the `inputs:` path); attest-build-provenance MUST come after sigstore-python (attestations bind to the existing signed artifact). Step order is load-bearing.
- **Adding `sigstore` to `[project.dependencies]` or `[dev]` extras.** Violates the v0.6 zero-base-dep rule (pyproject.toml base adds nothing; `[dev]` adds only `pip-audit` in Phase 53). verify_release.py shells out and prints an install hint.
- **Mutating any existing prose in docs/RELEASE.md steps 1-6 or 8-9.** Insertions only; the byte-identity contract per ARCHITECTURE.md line 102 + Phase 51 D-06.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Keyless OIDC signing of release artifacts | Custom GitHub Actions OIDC token exchange + Fulcio cert request + signing + Rekor inclusion-proof upload | `sigstore/gh-action-sigstore-python@<sha>` | The action handles the full OIDC → Fulcio → sign → Rekor round-trip in one step; rolling this by hand reintroduces every Pitfall 1 failure mode (TTL breach, wrong-issuer, wildcard-identity, detached vs bundle). |
| SLSA provenance generation | Custom SLSA v1.0 predicate JSON construction + signing + GitHub attestation API client | `actions/attest-build-provenance@<sha>` | The action emits a predicate compliant with SLSA Build L2 schema, signs it via the same Fulcio/Rekor path, and writes to the GH attestation API. Manual construction would need to track SLSA schema drift across versions. |
| Git tag signing without long-lived GPG | Custom `gpg` keypair management + key rotation + key distribution to all users | `gitsign` keyless OIDC | Long-lived GPG keys leak, rot, and need rotation. gitsign binds tag signatures to the maintainer's GitHub OIDC identity; verification = check workflow path; revocation = repo settings change. |
| Sigstore bundle verification | Custom `.sigstore` bundle parser + Fulcio cert chain validation + Rekor inclusion-proof verification | `python -m sigstore verify identity` (subprocess) | The CLI handles cert-chain trust-root logic, inclusion-proof verification, identity SAN parsing, OIDC issuer extension parsing. The bundle format is non-trivial protobuf; a hand-rolled parser would drift from the spec on every sigstore-protobuf-specs update. |
| Tag signature verification | Custom CMS / x509 cert verification | `git verify-tag` (subprocess) | git's verify-tag delegates to the configured gpg.x509.program (which is gitsign post-setup) and returns standard exit codes. |
| GitHub Release notes fetching | Custom GitHub REST API client + JSON parsing | `gh release view v<version> --json body --jq .body` (subprocess) | gh CLI handles auth, pagination, rate limits, response parsing. The user likely already has gh installed (maintainer's release procedure uses it at step 8). |
| `EXPECTED_IDENTITY_TEMPLATE` interpolation | Custom string template engine | `EXPECTED_IDENTITY_TEMPLATE.format(version=...)` (str.format) | Python's `str.format` handles `{version}` substitution; the rest of the template is byte-identical. |

**Key insight:** Every cryptographic primitive in the trust chain has at least one shipped, well-maintained, security-reviewed implementation. The verify_release.py shape is intentionally an ORCHESTRATOR (subprocess + parse exit codes + format report), not a CRYPTOGRAPHIC LIBRARY. The orchestrator can ship in stdlib-only Python; the crypto must not be hand-rolled.

## Runtime State Inventory

**Trigger applicability check:** Phase 52 is a *greenfield workflow addition* (new file `release.yml`) with one prose modification (docs/RELEASE.md insertions per D-05). There is no rename, no string-replace migration, no schema migration. This section applies the rename/refactor lens to confirm nothing is hiding.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — verified. No database/cache/datastore stores any string this phase introduces. `tests/fixtures/sigstore/canonical/` is committed test fixtures, not runtime data. | None |
| Live service config | **Phase 56 dependency:** the `gitsign.connectorID` value lives in the maintainer's `~/.gitconfig` (machine-local, NOT in repo git config) — this is set by the maintainer running the one-time config commands documented in `docs/MAINTAINER-RUNBOOK.md` (Phase 56 owns the content). Phase 52 only FORWARD-REFERENCES the runbook from RELEASE.md step 6.5. No service config in repo. | None for Phase 52; Phase 56 lands the runbook content |
| OS-registered state | None — verified. release.yml is a GitHub Actions workflow file; not OS-registered. gitsign is a Go binary installed via brew/go; brew/Homebrew tracks installation but Phase 52 does not add any brew-tap or system-service registration. | None |
| Secrets / env vars | **`GITHUB_TOKEN`** (auto-provisioned by GH Actions; `contents: write` scope on `sign-and-attest` job allows release-asset upload). No project-managed secret name; no `.env` change. **`PYPI_API_TOKEN`** is EXPLICITLY NOT created in v0.6 (D-09 + Pitfall 3 mitigation: any pre-existing `PYPI_*` secret would invalidate the deferral). | None for Phase 52; Phase 57 release-gate may add a `no-pypi-token-secret` audit check |
| Build artifacts | `dist/*.whl` and `dist/*.tar.gz` are produced by `python -m build` inside CI runner (ephemeral; cleaned up at job end except for what's attached to the Release). `dist/*.sigstore` bundle files are co-produced by sigstore-python. The GH Release page is the canonical artifact location after the workflow finishes. | None — release.yml itself manages artifact lifecycle |

**Canonical question answered:** After release.yml lands and the first v0.6.0-rc1 rehearsal release runs, what runtime systems carry state from Phase 52? Only: (1) the GitHub Release page asset list, (2) the GitHub attestation API entries for the rehearsal release, (3) the maintainer's local `~/.gitconfig` (gitsign config), (4) the committed `tests/fixtures/sigstore/canonical/` directory. All are intended outcomes; none constitute hidden state.

## Common Pitfalls

### Pitfall 1: Sigstore verification with wildcard identity OR wrong issuer silently accepts attacker signatures

**What goes wrong:** sigstore-python uses EXACT match for `--cert-identity`. cosign uses regex via `--certificate-identity-regexp`. A verifier author who learns one tool's semantics and reaches for the other gets the wrong contract. Worst case: `--cert-identity 'https://github.com/Ridou/horus-os/*'` (intended wildcard) actually matches the literal `*` character and silently fails open against any GitHub-signed sigstore signature — including an attacker's signature from their fork.

**Why it happens:** Tools diverge on identity semantics. Documentation warning is in prose, not in a CLI error.

**How to avoid:**
- EXPECTED_IDENTITY_TEMPLATE is a hardcoded module constant with `{version}` as the ONLY substitution (D-04 enforcement)
- `--cert-oidc-issuer` flag is MANDATORY on verify_release.py CLI; script refuses to run without it
- Module-import-time `assert` defends `"refs/tags/{version}" in EXPECTED_IDENTITY_TEMPLATE` against accidental edits
- Phase 58 TEST-24 wrong-identity fixture (sibling of Phase 52's canonical fixture) MUST cause verify_release.py to exit non-zero

**Warning signs:** Any `--cert-identity` value containing `*`, `.*`, regex metacharacters, or a trailing slash. Any verification call without `--cert-oidc-issuer`. A "verification passed" message against an artifact signed by a different workflow path.

**Phase 52 mitigation:** Hardcoded `EXPECTED_IDENTITY_TEMPLATE` + mandatory issuer flag + module-import assertion. Phase 58 lands the wrong-identity negative test.

### Pitfall 2: OIDC token expires mid-build → sigstore sign step fails with `identity token expired`

**What goes wrong:** Sigstore's keyless flow exchanges a GitHub Actions OIDC token (TTL ~10 min) for a short-lived Fulcio cert. If the build between "token-issued" and "sign-step" exceeds the token TTL, sign fails with `OIDCError: token expired`.

**Why it happens:** Long build phase + retry-with-backoff on a flaky test + the sign step is treated as "one step in a long build" rather than "the first thing after a fresh token mint."

**How to avoid:**
- D-01 step order: build (≤ 90s) → sign (≤ 30s) → attest. No tests, no docs build, no network calls between build and sign.
- The sigstore-python action mints the OIDC token INTERNALLY (its first action is the OIDC exchange); the 5-minute budget starts inside the action, not at workflow start.
- Per-step `timeout-minutes: 5` on the sigstore-python step bounds the failure mode (a hung sign step does not silently consume the full 10-min token).

**Warning signs:** The sign step appears later than position 5 in the workflow (after build + setup-python + checkout + install + build). Sign step exit message contains `expired`, `Unauthorized`, or `OIDC`.

**Phase 52 mitigation:** Job step ordering per D-01 (build at step 4; sign at step 5; attest at steps 6-7); per-step `timeout-minutes: 5` on the sigstore-python step.

### Pitfall 3: Signed tag with unsigned Release artifacts breaks the trust chain (PITFALLS.md Pitfall 11)

**What goes wrong:** Maintainer runs `git tag -s v0.6.0 && git push --tags`, then the Release workflow runs and somehow forgets to attach `.sigstore` bundles. Downstream user verifies the tag (passes), downloads wheel, runs sigstore verify, fails ("no bundle found").

**Why it happens:** Multi-step release flow; any single skipped step produces drift. Tag-signing and artifact-signing are conceptually separate concerns that must be jointly enforced.

**How to avoid:**
- `sigstore/gh-action-sigstore-python` with `release-signing-artifacts: true` AUTO-uploads `.sigstore` bundles to the triggering Release (verified verbatim from the action README: "`release-signing-artifacts` controls whether or not `sigstore-python` uploads signing artifacts to the release publishing event that triggered this run"). No second-step upload required.
- Release.yml's job runs on `release: published` (not `push: tags`), so the workflow physically cannot fire until the maintainer's `gh release create` lands the wheel+sdist on the Release page; the sign step uploads the bundles alongside what's already there.
- Phase 57's `release-workflow-signing-present` release-gate check ensures the literal `sigstore/gh-action-sigstore-python` appears in release.yml — preventing accidental removal between releases.
- verify_release.py checks BOTH the tag (check #3) AND the wheel signature (check #1) AND the sdist signature (check #2); user running `python scripts/verify_release.py --version 0.6.0 --cert-oidc-issuer ...` catches any cross-artifact gap.

**Warning signs:** GH Release page has wheel attached but no `.sigstore` next to it. `git verify-tag v0.6.0` exits 0 but `python -m sigstore verify identity ...` exits 1.

**Phase 52 mitigation:** D-01 single-job atomicity (no inter-job artifact upload that could be skipped); `release-signing-artifacts: true` (action handles upload, not a separate step that could be omitted); verify_release.py 5-check skeleton (cross-validates).

### Pitfall 4: `.sigstore` bundle naming convention drift between sigstore-python versions

**What goes wrong:** sigstore-python's documentation shows output as `<filename>.sigstore.json` in some places and `<filename>.sigstore` in others. The gh-action-sigstore-python README does not explicitly document the convention. If verify_release.py expects `wheel.whl.sigstore` and the action produces `wheel.whl.sigstore.json`, the verifier cannot find the bundle.

**Why it happens:** sigstore-python is in version flux (4.x line); the bundle filename suffix has historically been `.sigstore` in v3.x and the docs reference both `.sigstore` and `.sigstore.json` in v4.x examples. The action wraps the library; the action's emitted filename is determined by the library version pinned in v3.3.0 (sigstore-python 4.2.0).

**How to avoid:**
- During the v0.6.0-rc1 rehearsal recording (D-07), the maintainer observes the EXACT filename the action produces and pins it in the canonical fixture directory.
- verify_release.py accepts the bundle path via `--bundle PATH` CLI flag (test-mode injection); the production code path determines the bundle path by glob (`dist/*.whl.sigstore*` matches both suffixes) and asserts exactly one bundle per artifact, failing with a clear diagnostic if zero or multiple match.
- `tests/fixtures/sigstore/canonical/README.md` documents the observed naming convention from the rehearsal so future maintainers re-recording the fixture know what to commit.

**Warning signs:** `tests/test_release_verification.py` fails with "bundle not found" against a fixture that exists on disk. Maintainer rehearsal produces a filename different from what verify_release.py greps for.

**Phase 52 mitigation:** Glob-tolerant bundle path resolution in verify_release.py; rehearsal-time observation pinned in fixture directory README; `--bundle PATH` injection for tests.

### Pitfall 5: PyPI Trusted Publishing sequencing — a leaked PYPI_API_TOKEN would invalidate the v0.6 trust posture

**What goes wrong:** If `secrets.PYPI_API_TOKEN` exists in the repo's secrets at v0.6.0 ship (even unused), an attacker who breaches CI could exfiltrate it and upload poisoned packages. PEP 807 Trusted Publishing is the v0.7+ answer; for v0.6, the deferral means SETTING UP the token is OUT OF SCOPE — the absence of the token IS the v0.6 posture.

**How to avoid:**
- D-09 lands the `.planning/decisions/no-pypi-in-v0.6.md` decision file in Phase 52 documenting WHY no token exists in v0.6.
- The PROJECT.md key-decisions table row makes the decision discoverable in one place.
- Phase 57 release-gate may add a `no-pypi-token-secret` check that shells out to `gh secret list --json name` and asserts no secret with `PYPI` in its name exists (cited in PITFALLS.md Pitfall 9 line 414). Phase 52 does NOT add this check; Phase 57 owns release-gate extension.

**Warning signs:** Maintainer creates `secrets.PYPI_API_TOKEN` without removing the deferral decision. PyPI publishing PR opens in v0.6.x without flipping the decision file.

**Phase 52 mitigation:** Decision file + key-decisions row land atomically (D-09). Phase 57 may add the release-gate audit.

## Code Examples

### Example 1: `.github/workflows/release.yml` (full file)

```yaml
# Source: synthesized from .planning/research/ARCHITECTURE.md §Q1 lines 109-164,
# CONTEXT.md D-01..D-10, and Phase 51 conventions in .github/workflows/ci.yml.
# Every action `uses:` SHA-pinned per CIHARD-04; permissions per CIHARD-02.

name: release

on:
  release:
    types: [published]

permissions: read-all

jobs:
  sign-and-attest:
    name: sign-and-attest
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: write
      attestations: write
    steps:
      - name: Check out repository
        uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
        with:
          persist-credentials: false

      - name: Set up Python 3.12
        uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v5.6.0
        with:
          python-version: "3.12"

      - name: Install build
        run: |
          python -m pip install --upgrade pip
          python -m pip install build

      - name: Build wheel and sdist
        run: python -m build

      - name: Sign artifacts (sigstore keyless OIDC)
        uses: sigstore/gh-action-sigstore-python@04cffa1d795717b140764e8b640de88853c92acc # v3.3.0
        timeout-minutes: 5
        with:
          inputs: ./dist/*.whl ./dist/*.tar.gz
          release-signing-artifacts: true

      - name: Attest wheel (SLSA Build L2 provenance)
        uses: actions/attest-build-provenance@a2bbfa25375fe432b6a289bc6b6cd05ecd0c4c32 # v4.1.0
        with:
          subject-path: 'dist/*.whl'

      - name: Attest sdist (SLSA Build L2 provenance)
        uses: actions/attest-build-provenance@a2bbfa25375fe432b6a289bc6b6cd05ecd0c4c32 # v4.1.0
        with:
          subject-path: 'dist/*.tar.gz'
```

**Notes for the planner:**
- The `permissions: read-all` top-level + per-job opt-in pattern matches `.github/workflows/ci.yml` line 9 exactly (the Phase 51 baseline). No deviation.
- The `# vN.M.P` trailing comment on every `uses:` line matches the Phase 51 pinact convention.
- `timeout-minutes: 5` on the sigstore step bounds the OIDC-budget exposure per Pitfall 2.
- `release-signing-artifacts: true` is the action default (per gh-action-sigstore-python action.yml). Setting it explicitly makes the contract self-documenting and survives action default-changes.
- The `inputs:` value is the two-glob whitespace-separated form per gh-action-sigstore-python README ("`inputs` argument also supports file globbing"; "Multiple lines are fine"). Phase 53 appends ` ./dist/*.sbom.json` to this exact string.
- NO em-dashes in any comment in this file (CLAUDE.md HR3).

### Example 2: `scripts/verify_release.py` skeleton

```python
"""Phase 52 SIGN-04: user-facing 5-check trust-chain verifier.

Shipped stdlib-only. Shells out to `python -m sigstore verify identity`
and `git verify-tag` and `gh release view` to perform actual verification.
No third-party imports.

Source: synthesized from CONTEXT.md D-03, D-04, D-08; modeled on the
`scripts/release_gate.py` CheckResult dataclass (lines 137-148), the
_print_result formatter (lines 634-640), the argparse dispatch shape
(lines 678-766), and the lazy-subprocess discipline of
`scripts/lint_no_wallclock.py`.

CLI:
  python scripts/verify_release.py
    --version vN.M.P                       (REQUIRED)
    --cert-oidc-issuer URL                 (REQUIRED; must equal EXPECTED_ISSUER)
    [--check {wheel|sdist|tag|sbom|changelog}]  (optional; runs all if absent)
    [--bundle PATH]                        (test mode: inject fixture bundle path)
    [--artifact PATH]                      (test mode: inject fixture artifact path)

Exit 0 only when no check has ok=False. Skipped checks (ok=None) do not
fail the gate.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

EXPECTED_IDENTITY_TEMPLATE = (
    "https://github.com/Ridou/horus-os/.github/workflows/release.yml"
    "@refs/tags/{version}"
)
EXPECTED_ISSUER = "https://token.actions.githubusercontent.com"

# Defense: catches accidental edits that break the workflow-scoped identity contract.
assert "refs/tags/{version}" in EXPECTED_IDENTITY_TEMPLATE, (
    "EXPECTED_IDENTITY_TEMPLATE corrupted: must contain 'refs/tags/{version}'"
)


@dataclass(frozen=True)
class CheckResult:
    """One check outcome.

    ok is True on pass, False on fail, None on skip.
    diagnostic is empty on pass, a one-line failure reason on fail,
    or a skip reason on skip.
    """

    name: str
    ok: bool | None
    diagnostic: str


def _print_result(result: CheckResult) -> None:
    if result.ok is True:
        print(f"OK    {result.name}: {result.diagnostic}")
    elif result.ok is False:
        print(f"FAIL  {result.name}: {result.diagnostic}")
    else:
        print(f"SKIP  {result.name}: {result.diagnostic}")


def _assert_sigstore_cli_available() -> CheckResult | None:
    """Return None when sigstore CLI is on PATH; otherwise a failure CheckResult."""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "sigstore", "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (FileNotFoundError, OSError) as exc:
        return CheckResult(
            name="sigstore-cli-available",
            ok=False,
            diagnostic=(
                f"python -m sigstore not available ({type(exc).__name__}). "
                "Install hint: pip install sigstore"
            ),
        )
    if proc.returncode != 0:
        return CheckResult(
            name="sigstore-cli-available",
            ok=False,
            diagnostic=(
                f"python -m sigstore --version exited {proc.returncode}. "
                "Install hint: pip install sigstore"
            ),
        )
    return None


def check_wheel_signature(
    version: str,
    cert_oidc_issuer: str,
    bundle_path: Path,
    artifact_path: Path,
) -> CheckResult:
    """Pass when `python -m sigstore verify identity` against the wheel bundle exits 0."""
    cli_check = _assert_sigstore_cli_available()
    if cli_check is not None:
        return CheckResult(
            name="wheel-signature", ok=False, diagnostic=cli_check.diagnostic
        )
    expected_identity = EXPECTED_IDENTITY_TEMPLATE.format(version=version)
    proc = subprocess.run(
        [
            sys.executable, "-m", "sigstore", "verify", "identity",
            "--cert-identity", expected_identity,
            "--cert-oidc-issuer", cert_oidc_issuer,
            "--bundle", str(bundle_path),
            str(artifact_path),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    if proc.returncode == 0:
        return CheckResult(
            name="wheel-signature",
            ok=True,
            diagnostic=f"verified against {expected_identity}",
        )
    tail = (proc.stderr or proc.stdout).strip().splitlines()[-3:]
    return CheckResult(
        name="wheel-signature",
        ok=False,
        diagnostic=(
            f"sigstore verify exited {proc.returncode}; last stderr: "
            + " | ".join(tail)
        ),
    )


def check_sdist_signature(...) -> CheckResult:  # same shape as wheel
    ...


def check_tag_signature(version: str) -> CheckResult:
    """Pass when `git verify-tag v<version>` exits 0 in the repo working tree."""
    tag = f"v{version}"
    proc = subprocess.run(
        ["git", "verify-tag", tag],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if proc.returncode == 0:
        return CheckResult(
            name="tag-signature",
            ok=True,
            diagnostic=f"git verify-tag {tag} passed",
        )
    tail = (proc.stderr or proc.stdout).strip().splitlines()[-3:]
    return CheckResult(
        name="tag-signature",
        ok=False,
        diagnostic=(
            f"git verify-tag {tag} exited {proc.returncode}; last stderr: "
            + " | ".join(tail)
        ),
    )


def check_sbom_signature(version: str) -> CheckResult:
    """STUB: Phase 53 lands SBOM generation + signing."""
    return CheckResult(
        name="sbom-signature",
        ok=None,
        diagnostic="SKIPPED - Phase 53 lands SBOM generation + signing",
    )


def check_changelog_cross_ref(version: str) -> CheckResult:
    """Pass when GH Release body matches the [N.M.P] section of CHANGELOG.md."""
    # ... shells out to: gh release view v<version> --json body --jq .body
    # ... and greps CHANGELOG.md for the [N.M.P] section
    ...


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="User-facing trust-chain verifier for a horus-os release.",
    )
    parser.add_argument("--version", required=True,
                        help="Release version (e.g. 0.6.0).")
    parser.add_argument("--cert-oidc-issuer", required=True,
                        help=f"OIDC issuer URL. MUST equal {EXPECTED_ISSUER}.")
    parser.add_argument("--check",
                        choices=("wheel", "sdist", "tag", "sbom", "changelog"),
                        default=None,
                        help="Run only the named check.")
    parser.add_argument("--bundle", type=Path, default=None,
                        help="Path to .sigstore bundle (test mode).")
    parser.add_argument("--artifact", type=Path, default=None,
                        help="Path to artifact file (test mode).")
    args = parser.parse_args(argv)

    if args.cert_oidc_issuer != EXPECTED_ISSUER:
        print(
            f"FAIL  verify_release: --cert-oidc-issuer must equal {EXPECTED_ISSUER!r}, "
            f"got {args.cert_oidc_issuer!r}",
            file=sys.stderr,
        )
        return 1

    results: list[CheckResult] = []

    if args.check in (None, "wheel"):
        results.append(check_wheel_signature(...))
    if args.check in (None, "sdist"):
        results.append(check_sdist_signature(...))
    if args.check in (None, "tag"):
        results.append(check_tag_signature(args.version))
    if args.check in (None, "sbom"):
        results.append(check_sbom_signature(args.version))
    if args.check in (None, "changelog"):
        results.append(check_changelog_cross_ref(args.version))

    for result in results:
        _print_result(result)

    any_failed = any(r.ok is False for r in results)
    return 1 if any_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

### Example 3: maintainer one-time gitsign config (for docs/MAINTAINER-RUNBOOK.md, Phase 56)

```bash
# Source: gitsign README https://github.com/sigstore/gitsign (verbatim quote)
# Phase 52 forward-references this from docs/RELEASE.md step 6.5; the actual
# prose lives in docs/MAINTAINER-RUNBOOK.md (Phase 56). Included here for
# planner reference only.

# Install (macOS):
brew install gitsign
# Install (Linux):
go install github.com/sigstore/gitsign@latest

# Configure (one-time, global git config):
git config --global gpg.x509.program gitsign
git config --global gpg.format x509
git config --global tag.gpgSign true
git config --global gitsign.connectorID https://github.com/login/oauth

# Verify configuration:
git config --get gitsign.connectorID
# Expected output: https://github.com/login/oauth (or similar OIDC issuer URL)
```

When `git tag -s vN.M.P -m "..."` runs after this setup, git delegates to `gitsign` (via `gpg.x509.program`); gitsign opens a browser for OAuth, mints a Fulcio cert, signs the tag, returns. `git verify-tag vN.M.P` verifies via the same x509 path. `[CITED: https://github.com/sigstore/gitsign README]`

### Example 4: `tests/test_release_verification.py` (positive-path only; wrong-identity test is Phase 58)

```python
"""Phase 52 SIGN-04: positive-path tests for scripts/verify_release.py.

Tests the canonical fixture in tests/fixtures/sigstore/canonical/ verifies
green. Wrong-identity fixture + negative test are owned by Phase 58 (TEST-24).

Cross-OS: uses pathlib for all paths; sys.executable for the script invocation
so the Windows pytest matrix does not blow up on missing `python` PATH entry.

Source: synthesized from CONTEXT.md D-07 fixture shape and the
tests/test_release_gate_v0_5_checks.py subprocess + dataclass introspection
patterns (lines 26-55).
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_DIR = REPO_ROOT / "tests" / "fixtures" / "sigstore" / "canonical"

# Recording-time version (D-07 + specifics line 209): the rehearsal release
# was tagged v0.6.0-rc1 on the maintainer's fork, so the fixture verifies
# against EXACTLY this version string. Future re-recordings using a different
# rc tag must update this constant + the README.md alongside the fixture.
CANONICAL_VERSION = "0.6.0-rc1"
EXPECTED_ISSUER = "https://token.actions.githubusercontent.com"


def _resolve_fixture_paths() -> tuple[Path, Path]:
    """Return (artifact_path, bundle_path) for the canonical fixture.

    Tolerates both .sigstore and .sigstore.json bundle suffixes (Pitfall 4
    mitigation; the actual suffix is pinned at rehearsal-recording time
    in tests/fixtures/sigstore/canonical/README.md).
    """
    artifacts = sorted(CANONICAL_DIR.glob("*.whl"))
    if len(artifacts) != 1:
        pytest.skip(
            f"expected exactly 1 .whl in {CANONICAL_DIR}, found {len(artifacts)}"
        )
    artifact = artifacts[0]
    bundle_candidates = (
        artifact.with_suffix(artifact.suffix + ".sigstore"),
        artifact.with_suffix(artifact.suffix + ".sigstore.json"),
    )
    for candidate in bundle_candidates:
        if candidate.exists():
            return artifact, candidate
    pytest.skip(
        f"no .sigstore or .sigstore.json bundle found alongside {artifact.name}"
    )


def test_canonical_fixture_verifies_green() -> None:
    """The canonical wheel + bundle pass --check wheel."""
    artifact, bundle = _resolve_fixture_paths()
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "verify_release.py"),
            "--version", CANONICAL_VERSION,
            "--cert-oidc-issuer", EXPECTED_ISSUER,
            "--check", "wheel",
            "--bundle", str(bundle),
            "--artifact", str(artifact),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert proc.returncode == 0, (
        f"verify_release.py exited {proc.returncode}; "
        f"stdout: {proc.stdout!r}; stderr: {proc.stderr!r}"
    )
    assert "OK    wheel-signature" in proc.stdout


def test_missing_cert_oidc_issuer_flag_refuses() -> None:
    """SIGN-04 contract: script REFUSES to run without --cert-oidc-issuer."""
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "verify_release.py"),
            "--version", CANONICAL_VERSION,
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert proc.returncode != 0
    # argparse error or our explicit refusal both acceptable
    assert "cert-oidc-issuer" in (proc.stderr + proc.stdout).lower()


def test_wrong_issuer_refuses() -> None:
    """The mandatory issuer must EQUAL EXPECTED_ISSUER; mismatch refuses."""
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "verify_release.py"),
            "--version", CANONICAL_VERSION,
            "--cert-oidc-issuer", "https://attacker.example.com",
            "--check", "wheel",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert proc.returncode != 0


def test_sbom_check_returns_skipped() -> None:
    """D-08: check #4 returns ok=None pending Phase 53."""
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "verify_release.py"),
            "--version", CANONICAL_VERSION,
            "--cert-oidc-issuer", EXPECTED_ISSUER,
            "--check", "sbom",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert proc.returncode == 0  # SKIPPED is not a failure
    assert "SKIP" in proc.stdout
    assert "Phase 53" in proc.stdout
```

### Example 5: `.planning/decisions/no-pypi-in-v0.6.md` (full file)

```markdown
# Decision: PyPI Trusted Publishing deferred to v0.7+

**Phase:** 52 (Signing substrate)
**Status:** Accepted (v0.6)
**Date:** 2026-XX-XX (set by planner at commit time)

## Context

PyPI Trusted Publishing (PEP 807) is a keyless publishing mechanism that
exchanges a GitHub Actions OIDC token for a single-use PyPI upload
credential, eliminating the need for a long-lived `PYPI_API_TOKEN` secret
in repository settings.

The v0.6 Contribution Gate milestone wires the artifact-signing,
attestation, and trust-verification substrate that PyPI Trusted Publishing
would build on. The question for v0.6 is whether to also publish to PyPI.

## Decision

horus-os does NOT publish to PyPI in v0.6. The `.github/workflows/release.yml`
job from Phase 52 signs wheel + sdist and attaches them to the GitHub
Release. Users install from the Release page or from source. No PyPI
project exists; no `PYPI_API_TOKEN` is created.

## Rationale

1. **Scope discipline.** The v0.6 milestone is contribution-gate readiness,
   not distribution expansion. Adding PyPI publishing widens the surface
   without serving the v0.6 goal.
2. **No-token posture is stronger than configured-Trusted-Publishing.** A
   project with NO `PYPI_API_TOKEN` secret in repository settings has no
   token to leak. The v0.6 supply-chain posture is "the secret does not
   exist," which is strictly stronger than "the secret exists but is rotated."
3. **Cleanup cost asymmetry.** Setting up a PyPI project under the wrong
   account and then migrating it later is harder than waiting until v0.7+
   to set it up correctly the first time.

## Conditions for revisit

Revisit when:
- A v0.7+ phase explicitly scopes PyPI publishing with PEP 807 Trusted
  Publishing (NOT API token).
- The PyPI project + maintainer setup is documented in
  `docs/MAINTAINER-RUNBOOK.md`.
- `scripts/release_gate.py` gains a `no-pypi-token-secret` check that
  asserts no `PYPI*` secret exists in repository settings.

## References

- `.planning/research/PITFALLS.md` Pitfall 9 (PyPI Trusted Publishing sequencing)
- PEP 807 https://peps.python.org/pep-0807/
- PyPI blog 2024-11-14 "PyPI now supports digital attestations"

**Decision (final, until revisited):** No PyPI publishing in v0.6. Sigstore-signed
wheel + sdist on GitHub Release is the only v0.6 distribution path.
```

(NO em-dashes in this prose; uses hyphens and commas only. CLAUDE.md HR3.)

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Long-lived GPG keypair for tag signing | gitsign keyless OIDC tag signing | Sigstore 1.0 GA 2022; gitsign GA 2023 | No key rotation; identity is workflow-scoped not personal; leak = revoke GH OAuth grant |
| Long-lived PyPI API tokens for publishing | PEP 807 Trusted Publishing (OIDC exchange) | PEP 807 finalized late 2024; PyPI shipped support same window | Tokens eliminated; publishing identity is workflow-scoped; PEP 740 attestation auto-attached |
| Detached `.sig` + `.crt` files for artifact signing | `.sigstore` bundle (signature + cert + Rekor inclusion proof inline) | sigstore-python 2.x → 3.x bundle format consolidation 2023-2024 | Offline verification once bundle is local; PEP 740 references bundles, not `.sig` |
| Workflow YAML lint as optional | `actionlint` + `zizmor` as CI-blocking gates | 2024-2026 supply-chain incident wave (Ultralytics, tj-actions, "testedbefore") | Phase 51 lands actionlint; Phase 54 lands zizmor; both block merge on findings |
| `@v4` mutable tag pins on GitHub Actions | 40-char SHA pin + trailing `# vN.M.P` comment | tj-actions/changed-files CVE-2025-30066 (~23k repos compromised); now industry default | `pinact` rewrites; Dependabot github-actions ecosystem refreshes; release-gate `actions-pinned-by-sha` check (Phase 57) defends |
| SLSA L1 (no provenance) for Python releases | SLSA Build L2 via `actions/attest-build-provenance` | actions/attest-build-provenance v4 GA 2024; GitHub Attestations GA 2024 | Free; verifiable via `gh attestation verify`; one-step workflow integration |

**Deprecated / outdated for this phase:**
- `cosign sign-blob` for Python artifact signing → use `sigstore-python` (PEP 740 alignment, identity model)
- `safety` (Pyup paid tier) for vuln scanning → use `pip-audit` (Phase 53 owns; not Phase 52)
- v2.x `sigstore` Python library (EOL) → `sigstore` ≥4.2 (current; SIGN-01 contract)
- `actions/attest-build-provenance@v3` and prior (different underlying implementation; v4 wraps `actions/attest`) → v4.1.0+

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `.sigstore` bundle filename emitted by `sigstore/gh-action-sigstore-python@v3.3.0` is `<artifact>.sigstore` (NOT `<artifact>.sigstore.json`) — sigstore-python 4.x docs use both spellings; the action's actual emission must be observed at rehearsal time | §Pitfall 4; §Code Examples §4 fixture-path resolution | If wrong: verify_release.py glob mismatch → fixture not found → tests fail; mitigation built in (glob tolerates both suffixes; rehearsal pins the actual suffix in fixture README) |
| A2 | The `release.published` event fires on pre-release tag types (e.g., `v0.6.0-rc1`) so the v0.6.0-rc1 rehearsal triggers the same release.yml that the production v0.6.0 will trigger | §Pitfall 4 rehearsal flow; D-07 | LOW: GitHub docs explicitly confirm "pre-releases that are published" fire the event `[VERIFIED: docs.github.com Events that trigger workflows §release]`. Caveat: if maintainer creates the rehearsal release as a DRAFT first, the event fires when the draft is promoted to published. |
| A3 | `git verify-tag` on a gitsign-signed tag returns exit 0 when the cert chain validates, even without verify_release.py explicitly invoking `gitsign verify` | §Pattern 3 check #3 | MEDIUM: gitsign README recommends `gitsign verify` over `git verify-tag` because git's verify-tag does not pass identity info to the verifier. Verify_release.py's check #3 may need to shell out to `gitsign verify-tag --certificate-identity <expected> --certificate-oidc-issuer <expected> v<version>` rather than `git verify-tag` to get full identity verification. Planner must confirm at implementation time which command produces the workflow-scoped identity assertion. |
| A4 | sigstore-python 4.2.0 CLI exits 0 on verification success and non-zero on failure (the standard Unix convention; not documented in the README excerpt but consistent with subprocess-CLI conventions across the Python ecosystem) | §Code Examples §2 dispatch logic | LOW: subprocess-CLI exit-code convention is near-universal; verify_release.py treats any non-zero as failure. If sigstore-python returns more granular codes (e.g., 2 = invalid args, 3 = verification fail), verify_release.py groups them all as "failure" with the stderr tail as diagnostic — acceptable for v0.6. |
| A5 | The `gh release view v<version> --json body --jq .body` command works on a release that was created with `--notes-file` (i.e., the body field is populated, not null) | §Pattern 3 check #5; §Code Examples §2 (check_changelog_cross_ref) | LOW: gh release view documented to return the body field; existing RELEASE.md step 8 explicitly uses `--notes-file`, so the body is populated. |
| A6 | The maintainer is willing to push a `v0.6.0-rc1` tag to a fork (NOT origin) to record the canonical fixture per D-07 | §Pitfall 4 mitigation; D-07 | LOW: D-07 + PITFALLS.md Pitfall 11 line 515 explicitly call for this; the rehearsal IS the recording session. If the maintainer cannot use a fork, an alternative is a separate dedicated rehearsal-only branch on origin with a clearly-named pre-release tag (e.g., `v0.6.0-rc1-fixture-recording`). |

**Assumptions verified before submission:**
- Action SHAs (A1's parent claim about correct tag→SHA mapping): all four verified via `gh api repos/{owner}/{repo}/git/refs/tags/{tag} --jq '.object.sha'` on 2026-05-29 (see §Standard Stack table source column).
- `release: types: [published]` semantics including pre-release firing: verified against https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows#release.
- `actions/attest-build-provenance@v4.1.0` accepts glob in `subject-path`: verified via action.yml inspection ("May contain a glob pattern or list of paths").
- `sigstore/gh-action-sigstore-python@v3.3.0` inputs are whitespace-separated globs: verified via README ("`inputs` argument also supports file globbing"; "Multiple lines are fine").
- `release-signing-artifacts` default: verified `true` per action.yml input declarations.

## Open Questions

1. **`.sigstore` bundle filename suffix (`.sigstore` vs `.sigstore.json`).**
   - What we know: sigstore-python README + docs/signing.md reference both `.sigstore.json` (newer convention) AND `.sigstore` (legacy). The gh-action-sigstore-python v3.3.0 README does not pin the convention.
   - What's unclear: the actual emission of v3.3.0 with sigstore-python 4.2.0 internally.
   - Recommendation: pin at rehearsal-recording time. Plan task: maintainer runs the rehearsal, observes the actual filename, commits the fixture with that exact name, documents the name in fixture README.md. verify_release.py uses a glob (`*.sigstore*`) that tolerates either.

2. **`git verify-tag` vs `gitsign verify-tag` for check #3.**
   - What we know: `git verify-tag` is the canonical git command and delegates to the configured `gpg.x509.program`. gitsign README recommends `gitsign verify-tag` over `git verify-tag` because git does not pass identity-context flags through.
   - What's unclear: whether `git verify-tag` provides sufficient identity verification for the v0.6 trust model, or whether verify_release.py check #3 should specifically shell out to `gitsign verify-tag --certificate-identity <expected> --certificate-oidc-issuer <expected> v<version>` to get workflow-scoped identity verification (matching the wheel/sdist checks #1+2 semantics).
   - Recommendation: planner reads the current gitsign README at plan-time and picks the more-strict command. If `gitsign verify-tag` is the recommended path, verify_release.py's check #3 shells out to it AND prints a clear install hint (`go install github.com/sigstore/gitsign@latest` or `brew install gitsign`) if absent — mirroring the sigstore-CLI install-hint pattern.

3. **CHANGELOG cross-ref normalization (check #5).**
   - What we know: CHANGELOG.md uses Keep a Changelog 1.1.0 format (header line: `## [0.6.0] - 2026-XX-XX`). GH Release body is created with `--notes-file` from an awk-extracted section.
   - What's unclear: exact whitespace/newline normalization required so the cross-ref is robust to GH's body rendering and the maintainer's hand-edits.
   - Recommendation: plan task: implementer writes a small helper that strips trailing whitespace per line + collapses runs of blank lines and compares. If mismatch, diagnostic prints the first 5 lines of diff. Acceptable for v0.6; refinement can ship in a v0.6.x patch if false-positives observed.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `gh` CLI | release.yml workflow (`gh release create` happens BEFORE this workflow fires; not invoked from inside); verify_release.py check #5 | ✓ (CI runner pre-installed; user expected to install) | latest | verify_release.py prints install hint and marks check #5 as failed with "gh not on PATH; install: https://cli.github.com/" |
| `git` CLI | verify_release.py check #3; sign-and-attest job's checkout step | ✓ (CI runner pre-installed; ubiquitous on developer machines) | latest | None — `git` is a hard requirement; hard-fail diagnostic if absent |
| Python 3.12 (CI runner) | release.yml setup-python step | ✓ (ubuntu-latest runner; provisioned by actions/setup-python) | 3.12 | None — pinned in release.yml |
| `sigstore` Python package | verify_release.py checks #1, #2 (and #4 in Phase 53) | ✗ on bare user install; needs `pip install sigstore` | ≥4.2,<5 (SIGN-01 contract for user-installed library; same library wrapped by gh-action-sigstore-python v3.3.0 in CI) | verify_release.py prints `pip install sigstore` hint and marks check #1/#2 as failed with the hint in the diagnostic |
| `gitsign` (maintainer workstation only) | Step 7 of docs/RELEASE.md (signed tag creation); possibly check #3 (open question 2) | ✗ on most workstations; one-time `brew install gitsign` or `go install github.com/sigstore/gitsign@latest` | latest | Phase 52 forward-references `docs/MAINTAINER-RUNBOOK.md` (Phase 56) for install + config instructions; STOP-BEFORE-TAG step 6.5 catches the "not configured" failure mode before `git tag -s` is invoked |
| `python -m build` | release.yml step 4 | ✓ (installed at step 3 of release.yml) | latest | None — installed inline |

**Missing dependencies with no fallback:**
- None blocking; `git` is the only hard dep without fallback and is universally present.

**Missing dependencies with fallback:**
- `sigstore` CLI: verify_release.py prints install hint
- `gh` CLI: verify_release.py prints install hint for check #5
- `gitsign`: STOP-BEFORE-TAG step 6.5 pre-flight catches missing config

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (existing project framework; not new) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (existing) |
| Quick run command | `pytest tests/test_release_verification.py -v` |
| Full suite command | `pytest -v` (from repo root) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SIGN-01 | release.yml exists; contains `sigstore/gh-action-sigstore-python` literal; SHA-pinned; sigstore step has `timeout-minutes: 5`; on `release: published` trigger; top-level `permissions: read-all`; per-job `id-token: write` | structural (workflow YAML lint) | `pytest tests/test_release_yml_structure.py -v` (NEW; Wave 0 gap) | ❌ Wave 0 |
| SIGN-02 | release.yml contains TWO `actions/attest-build-provenance@<sha>` invocations (one for `dist/*.whl`, one for `dist/*.tar.gz`); both SHA-pinned to v4.1.0; per-job `attestations: write` | structural | `pytest tests/test_release_yml_structure.py::test_per_artifact_attest -v` (Wave 0 gap) | ❌ Wave 0 |
| SIGN-03 | docs/RELEASE.md STOP-BEFORE-TAG block: step 6.5 inserted (contains `gitsign.connectorID`); step 7 uses `git tag -s` (NOT `git tag -a`); steps 1-6 and 8-9 prose UNCHANGED (byte-identity hash assertion) | structural (docs lint) | `pytest tests/test_release_md_stop_before_tag.py -v` (NEW; Wave 0 gap) | ❌ Wave 0 |
| SIGN-04 | verify_release.py module-level `EXPECTED_IDENTITY_TEMPLATE` and `EXPECTED_ISSUER` constants present and byte-identical to spec; argparse refuses without `--cert-oidc-issuer`; argparse refuses without `--version`; refuses on mismatched issuer; canonical fixture passes `--check wheel`; SBOM check returns SKIPPED | unit + integration | `pytest tests/test_release_verification.py -v` | ❌ Wave 0 |
| SIGN-05 | `.planning/decisions/no-pypi-in-v0.6.md` exists; matches expected structure (Context, Decision, Rationale, Conditions for revisit, Decision-final block); PROJECT.md key-decisions table contains a row referencing `no-pypi-in-v0.6.md` | structural | `pytest tests/test_decision_no_pypi.py -v` (NEW; Wave 0 gap) | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_release_verification.py tests/test_release_yml_structure.py tests/test_release_md_stop_before_tag.py tests/test_decision_no_pypi.py -v` (subset; ≤ 30 s)
- **Per wave merge:** `pytest -v` (full suite; ~ 2 minutes on Ubuntu CI)
- **Phase gate:** Full suite GREEN before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_release_verification.py` — covers SIGN-04 (5 tests: canonical-fixture pass, missing-issuer refuse, wrong-issuer refuse, SBOM-stub returns SKIPPED, full-run all-checks)
- [ ] `tests/test_release_yml_structure.py` — covers SIGN-01 + SIGN-02 (5 tests: file-exists, on-release-published, top-level permissions, per-job permissions, both attest-build-provenance present, sigstore literal present, sigstore SHA-pinned, timeout-minutes set, every-uses-sha-pinned)
- [ ] `tests/test_release_md_stop_before_tag.py` — covers SIGN-03 (3 tests: step 6.5 inserted with gitsign connector-id phrase, step 7 uses tag-s not tag-a, steps 1-6 + 8-9 byte-identical to a pre-edit baseline string)
- [ ] `tests/test_decision_no_pypi.py` — covers SIGN-05 (3 tests: decision file exists, decision file has terminating "Decision (final, until revisited):" line, PROJECT.md key-decisions table contains a row referencing the decision file path)
- [ ] `tests/fixtures/sigstore/canonical/README.md` — documents the rehearsal recording procedure + observed bundle filename suffix
- [ ] `tests/fixtures/sigstore/canonical/*.whl` + `tests/fixtures/sigstore/canonical/*.whl.sigstore[.json]` — committed artifact + bundle from v0.6.0-rc1 rehearsal

*(Framework install: none — pytest already in `[dev]` extras per existing project conventions.)*

## Sources

### Primary (HIGH confidence)

- `gh api repos/sigstore/gh-action-sigstore-python/git/refs/tags/v3.3.0 --jq '.object.sha'` → `04cffa1d795717b140764e8b640de88853c92acc` (resolved 2026-05-29)
- `gh api repos/actions/attest-build-provenance/git/refs/tags/v4.1.0 --jq '.object.sha'` → `a2bbfa25375fe432b6a289bc6b6cd05ecd0c4c32` (resolved 2026-05-29)
- `https://raw.githubusercontent.com/sigstore/gh-action-sigstore-python/v3.3.0/action.yml` — verified all 12 input fields verbatim
- `https://raw.githubusercontent.com/actions/attest-build-provenance/v4.1.0/action.yml` — verified all 11 input fields verbatim; confirmed `subject-path` accepts globs
- `https://raw.githubusercontent.com/sigstore/gh-action-sigstore-python/v3.3.0/README.md` — confirmed `inputs:` accepts whitespace-separated globs; `release-signing-artifacts: true` uploads to triggering Release
- `https://github.com/sigstore/sigstore-python/blob/main/README.md` — `sigstore verify identity` CLI shape with `--cert-identity`, `--cert-oidc-issuer`, `--bundle`, `FILE_OR_DIGEST` positional
- `https://github.com/sigstore/gitsign` (README) — install + `git config` commands verbatim; `connectorID` value examples; `git tag -s` integration via `gpg.x509.program`
- `https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows#release` — `release: published` trigger semantics; fires on pre-releases when published; does NOT fire on draft creation
- `.github/workflows/ci.yml` (post-Phase-51) — byte-identity reference for top-level `permissions: read-all`, per-job opt-in, SHA-pin format with trailing `# vN.M.P`, `persist-credentials: false`
- `scripts/release_gate.py` — CheckResult dataclass + per-check function shape + argparse-enum dispatch + `_print_result` formatter + env-var path-override pattern
- `scripts/lint_no_wallclock.py` — stdlib-only subprocess pattern precedent
- `.planning/research/STACK.md`, `.planning/research/ARCHITECTURE.md`, `.planning/research/PITFALLS.md` (v0.6 research substrate)

### Secondary (MEDIUM confidence)

- `.planning/phases/51-ci-hardening-substrate/51-02-SUMMARY.md` — SHA-pin convention; raven-actions/actionlint precedent; persist-credentials enforcement
- `https://slsa.dev/spec/v1.0/levels` — SLSA Build L2 definition (corroborated via STACK.md table)
- gitsign README verification recommendation `gitsign verify` over `git verify-tag` — flagged in Open Question 2

### Tertiary (LOW confidence; flagged in Assumptions Log)

- sigstore-python `.sigstore` vs `.sigstore.json` bundle filename suffix (A1) — mitigated by glob-tolerant resolution + rehearsal-time pinning
- sigstore-python CLI exit code semantics (A4) — not documented in README; standard Unix convention assumed

## Metadata

**Confidence breakdown:**
- Standard stack (SHAs + action input shapes + version compatibility): HIGH — all four SHAs verified via `gh api`; both action.yml files inspected verbatim; sigstore-python CLI shape confirmed via README; gitsign config verified via README
- Architecture (release.yml job shape; verify_release.py skeleton; RELEASE.md insertions; decision file shape; PROJECT.md row): HIGH — directly derived from CONTEXT.md D-01..D-10 + ARCHITECTURE.md §Q1 + existing release_gate.py + lint_no_wallclock.py precedents
- Pitfalls (workflow-scoped identity, OIDC TTL, trust-chain coupling, bundle filename, PyPI deferral): HIGH on failure modes (cited PITFALLS.md sections + 2024-2026 incident chronology); MEDIUM on the bundle filename suffix specifically (Assumption A1 + Open Question 1)
- Test surface (Validation Architecture + Wave 0 gaps): HIGH — modeled on existing tests/test_release_gate_v0_5_checks.py + tests/test_contribution_gate_pitfalls/test_ci_hardening_workflow_structure.py patterns

**Research date:** 2026-05-29
**Valid until:** 2026-06-28 (30 days; action SHAs may drift if upstream cuts new releases; re-verify via `gh api` at plan-time if execution slips past valid-until)
