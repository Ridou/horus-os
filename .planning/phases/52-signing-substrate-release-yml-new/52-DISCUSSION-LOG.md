# Phase 52: Signing substrate (`release.yml` NEW) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-29
**Phase:** 52-signing-substrate-release-yml-new
**Mode:** `--auto` (no interactive prompts; recommended option auto-selected for each gray area)
**Areas discussed:** release.yml job structure, workflow permissions block, verify_release.py implementation shape, EXPECTED_IDENTITY pinning shape, gitsign STOP-BEFORE-TAG integration, attest-build-provenance invocation granularity, canonical fixture provenance, verify_release.py 5-check skeleton with deferred SBOM check, no-pypi-in-v0.6.md + PROJECT.md update timing, Phase 53 SBOM-signing input-glob coordination

---

## release.yml job structure (D-01)

| Option | Description | Selected |
|--------|-------------|----------|
| Single `sign-and-attest` job, sequential steps | One job on ubuntu-latest with build → sign → attest sequence. Preserves OIDC TTL budget; matches ARCHITECTURE.md §Q1 recommendation. | ✓ |
| Two jobs (build then sign-and-attest) | Build produces dist/, uploads as artifact; sign job downloads, signs. Adds round-trip risk. | |

**Auto choice:** Single job (recommended; matches ARCHITECTURE.md Q1; preserves 5-min OIDC budget per SIGN-01).
**Notes:** OIDC mint-to-sign deadline measured from sigstore-action invocation to bundle emission; build is outside that window but inside the total job runtime budget.

---

## Workflow permissions block (D-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Top-level `read-all` + per-job opt-in `id-token: write` + `contents: write` + `attestations: write` on sign-and-attest only | Mirrors Phase 51 CIHARD-02 least-privilege pattern. | ✓ |
| Workflow-level `id-token: write` | Simpler but violates least-privilege; breaks Phase 51 per-job opt-in convention. | |

**Auto choice:** Per-job opt-in (recommended; explicit SIGN-01 success criterion language: "per-job `id-token: write` only on signing job").

---

## verify_release.py implementation shape (D-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Stdlib-only Python script that shells out to `python -m sigstore verify identity` and `git verify-tag` | Mirrors release_gate.py stdlib contract; sigstore not added to runtime or dev deps. | ✓ |
| Direct `from sigstore import verify` Python import | Requires sigstore in `[dev]` extras (acceptable) or `[project.dependencies]` (forbidden by v0.6 zero-base-dep rule). | |

**Auto choice:** stdlib + subprocess (recommended; matches release_gate.py invariant).
**Notes:** Script prints clear install hint (`pip install sigstore`) and exits non-zero if `python -m sigstore` not on PATH.

---

## EXPECTED_IDENTITY pinning shape (D-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Hardcoded module-level constant; `--version` and `--cert-oidc-issuer` mandatory CLI args | No wildcards, no regex, no fallback. SIGN-04 explicit hard rule. | ✓ |
| JSON config file at `tests/fixtures/sigstore/identity.json` | Flexibility invites future drift; reintroduces PITFALL 3 risk. | |

**Auto choice:** Hardcoded constant (recommended; SIGN-04 language is explicit; PITFALL 3 is a known incident class).

---

## gitsign STOP-BEFORE-TAG integration (D-05)

| Option | Description | Selected |
|--------|-------------|----------|
| Both: insert NEW step 6.5 (gitsign pre-flight check) AND update step 7 command from `git tag -a` to `git tag -s` | Two insertions, zero mutations. Pre-flight catches "gitsign not configured" before signing prompt. | ✓ |
| Single-line swap (`-a` → `-s`) only | Misses the "gitsign not configured" failure mode PITFALL 11 explicitly names ("`git tag -s` that uses `-s` (GPG) instead of gitsign"). | |
| Custom `gitsign-tag` wrapper script | Adds new tool surface; gitsign already integrates via standard `git tag -s`. | |

**Auto choice:** Both (recommended; "insertions allowed, mutations not" discipline per Phase 51 D-06 + ARCHITECTURE.md byte-identity rule).

---

## actions/attest-build-provenance invocation granularity (D-06)

| Option | Description | Selected |
|--------|-------------|----------|
| Per-artifact `subject-path` invocations (one step per wheel, sdist) | Per-artifact verification maps 1:1 to CI step; isolates failures cleanly. | ✓ |
| Single `subject-path: 'dist/*'` glob | Terser but obscures which artifact failed if attestation hiccups on one. | |

**Auto choice:** Per-artifact (recommended; SIGN-02 language: "runs for every signed artifact").
**Notes:** Phase 53 appends a third invocation for `dist/*.sbom.json` when SBOM generation lands.

---

## Canonical fixture provenance (D-07)

| Option | Description | Selected |
|--------|-------------|----------|
| Pre-recorded `.sigstore` bundle from a `v0.6.0-rc1` rehearsal release on a fork | Doubles as PITFALL 11 release-rehearsal discipline; no `id-token: write` in test runner. | ✓ |
| Live-sign in CI test setup | Requires `id-token: write` in test workflow; expands attack surface; forbidden by CIHARD-02. | |
| Copy a public sigstore-python project's bundle | Identity wouldn't match horus-os's EXPECTED_IDENTITY; test would always fail or require an EXPECTED_IDENTITY workaround. | |

**Auto choice:** Pre-recorded rehearsal bundle (recommended; canonical sigstore-python testing pattern; aligns with PITFALL 11 rehearsal discipline).
**Notes:** Wrong-identity fixture under `tests/fixtures/sigstore/wrong_identity/` owned by Phase 58 (TEST-24).

---

## verify_release.py 5-check skeleton with deferred SBOM check (D-08)

| Option | Description | Selected |
|--------|-------------|----------|
| Ship full 5-check skeleton in Phase 52 with check #4 (sbom-signature) returning `SKIPPED — Phase 53 lands SBOM generation + signing` until Phase 53 flips the stub | Preserves 5-check shape as Phase 52 deliverable; Phase 53's edit is a stub flip + 3 lines. | ✓ |
| Ship 4 active checks in Phase 52; Phase 53 inserts the 5th | Requires Phase 53 to touch dispatch order, CLI enum, report formatter — more drift surface. | |

**Auto choice:** Full skeleton with stubbed SBOM check (recommended; ROADMAP success criterion #4 says "5-check user-facing trust-chain verifier" in present tense for Phase 52).

---

## no-pypi-in-v0.6.md + PROJECT.md update timing (D-09)

| Option | Description | Selected |
|--------|-------------|----------|
| Both land in Phase 52, same commit | SIGN-05 couples them ("decision file referenced from PROJECT.md key-decisions table"); single-commit landing matches Phase 51 atomic-doc discipline. | ✓ |
| Decision file here; PROJECT.md update deferred to Phase 56 (docs refresh) | Splits SIGN-05 across two phases; risks docs drift; complicates any Phase 57 cross-check. | |

**Auto choice:** Both in Phase 52 (recommended; SIGN-05 is one requirement, one phase, one commit).

---

## Phase 53 SBOM-signing input-glob coordination (D-10)

| Option | Description | Selected |
|--------|-------------|----------|
| Phase 52 sigstore inputs: `./dist/*.whl ./dist/*.tar.gz`; Phase 53 APPENDS `./dist/*.sbom.json` | Smallest possible Phase 53 diff (one append); separation of concerns clean. | ✓ |
| Phase 52 signs SBOMs proactively (stub-generates empty SBOM) | Adds no-value scaffolding; conditional branching; worse than Phase 53 appending one glob. | |

**Auto choice:** Append-only coordination (recommended; preserves separation between Phase 52 signing substrate and Phase 53 SBOM substrate).

---

## Claude's Discretion

- Exact 40-char SHA values for `sigstore/gh-action-sigstore-python`, `actions/attest-build-provenance`, `actions/checkout`, `actions/setup-python`: planner resolves at plan-time via `pinact run --update` or `gh api repos/.../git/ref/tags/...`. CIHARD-04 invariant (40-char SHA pin) is non-negotiable.
- Whether `sigstore-python` action version pin is range (`>=4.2,<5`) or exact (`==4.2.0`): planner decides. The action SHA pin is the load-bearing decision; the library version is a courtesy lower bound.
- `gitsign` install instructions content for `docs/MAINTAINER-RUNBOOK.md`: Phase 56 owns; Phase 52 only forward-references.
- `verify_release.py` argparse subcommand vs flag-only CLI: planner decides. Either matches existing precedent.

## Deferred Ideas

(See CONTEXT.md `<deferred>` section for full list. Highlights: SBOM generation + signing → Phase 53; release-gate signing/SBOM-presence checks → Phase 57; wrong-identity negative test → Phase 58; PyPI Trusted Publishing → v0.7+; gitsign install runbook content → Phase 56.)

## Scope Creep Avoided

No scope-creep moments to log — `--auto` mode auto-resolves from the recommended option and bounds discussion to HOW questions strictly inside the SIGN-01..05 envelope. SBOM generation, release-gate extension, wrong-identity test, and runbook content are all called out as deferred to their owning phases per ROADMAP execution order.
