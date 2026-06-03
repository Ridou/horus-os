# Phase 52: Signing substrate (`release.yml` NEW) - Context

**Gathered:** 2026-05-29
**Status:** Ready for planning
**Mode:** `--auto` (recommended options auto-selected; user review encouraged before /gsd-plan-phase)

<domain>
## Phase Boundary

Phase 52 lands the keyless artifact and tag signing substrate for v0.6 on a NEW `.github/workflows/release.yml` file (not additions to `ci.yml`). It signs wheel + sdist via `sigstore/gh-action-sigstore-python` keyless OIDC, emits SLSA Build L2 provenance via `actions/attest-build-provenance`, configures `gitsign` for tag signing (no long-lived GPG keypair), ships `scripts/verify_release.py` as the user-facing 5-check trust-chain verifier with workflow-scoped EXACT-match identity, and records the PyPI Trusted Publishing deferral decision. The Phase 51 substrate (top-level `permissions: read-all` + 40-char SHA-pinning convention + `persist-credentials: false` on every checkout + `Run actionlint (CIHARD-05)` PR-time enforcement) is a HARD precondition: every `uses:` in the new `release.yml` is SHA-pinned, `permissions: read-all` is top-level with `id-token: write` opt-in only on the signing job, and the new workflow file is itself subject to the PR-time actionlint gate.

**Owns:** SIGN-01, SIGN-02, SIGN-03, SIGN-04, SIGN-05.
**Touches files (NEW):** `.github/workflows/release.yml`, `scripts/verify_release.py`, `.planning/decisions/no-pypi-in-v0.6.md`, `tests/fixtures/sigstore/canonical/` (positive fixture + README), `tests/test_release_verification.py` (verifier unit tests on the canonical fixture).
**Touches files (MODIFIED):** `docs/RELEASE.md` (STOP-BEFORE-TAG block — add gitsign pre-flight step + swap `git tag -a` to `git tag -s`), `PROJECT.md` (key-decisions table — append `no-pypi-in-v0.6` row referencing the decision file).
**Does NOT touch:** `.github/workflows/ci.yml` (Phase 51 owns the existing CI matrix; no signing concerns belong there), `scripts/release_gate.py` (Phase 57 owns the 8 → 13 extension including `release-workflow-signing-present`), `.github/workflows/audit.yml` (Phase 53 owns), any `dist/*.sbom.json` generation (Phase 53 owns SBOM generation; release.yml's signing-input glob is widened in Phase 53 to include SBOM files), `src/horus_os/` runtime code, `pyproject.toml` runtime deps (signing is CI-only — no `sigstore` added to `[project.dependencies]` or `[dev]`).
**Does NOT add:** any `pull_request_target` trigger (CIHARD-01 holds; release.yml triggers only on `release: types: [published]`), any long-lived GPG keypair (gitsign keyless-OIDC is the lock per `.planning/decisions/sigstore-keyless.md`), any wildcard or regex in `EXPECTED_IDENTITY` (SIGN-04 hard rule per PITFALL 3).
**Job naming:** `release.yml` introduces ONE job named `sign-and-attest`. This name has no byte-identity contract obligation yet (it's a new file), but Phase 57's `release-workflow-signing-present` check will grep release.yml for the literal `sigstore/gh-action-sigstore-python` string — NOT the job name — so the substring is the load-bearing identifier.

</domain>

<decisions>
## Implementation Decisions

All decisions below were auto-selected from the recommended option per `--auto` mode. Each entry includes the alternative considered and why the recommended choice won. Planner is free to override at planning time with stated rationale.

### release.yml job structure

- **D-01:** `release.yml` ships as **ONE job named `sign-and-attest`** running on `ubuntu-latest` (signing does NOT need the 3-OS matrix; OIDC + sigstore Fulcio is single-platform). Sequential steps: (1) `actions/checkout`, (2) `actions/setup-python` Python 3.12, (3) `python -m pip install --upgrade pip build`, (4) `python -m build` producing `dist/*.whl + dist/*.tar.gz`, (5) `sigstore/gh-action-sigstore-python` signing `./dist/*.whl ./dist/*.tar.gz` with `release-signing-artifacts: true` (auto-uploads `.sigstore` bundles to the GitHub Release), (6) `actions/attest-build-provenance` for each artifact (per D-06). The full chain from OIDC mint (step 5 implicit) to signature emission MUST complete within 5 minutes (SIGN-01 success criterion; OIDC token TTL ~10 min per PITFALL 3).
- **Why:** ARCHITECTURE.md §Q1 explicitly recommends single-job sequential-step shape. Splitting into build + sign jobs loses dist artifact context between jobs (would need `actions/upload-artifact` round-trip, adding fragility for no gain). The 5-minute OIDC-to-sign budget is preserved only when build and sign live in one job (no inter-job artifact upload overhead).
- **Alternative rejected:** Two-job (build then sign) — adds artifact-upload round-trip + risks OIDC TTL breach.

### Workflow permissions block

- **D-02:** `release.yml` declares **top-level `permissions: read-all`** (matches Phase 51 ci.yml + issue-claim-watcher.yml convention), with per-job opt-in **`permissions: { id-token: write, contents: write, attestations: write }`** ONLY on the `sign-and-attest` job. `id-token: write` is the minimum sigstore-python needs to mint the Fulcio cert; `contents: write` is needed for `release-signing-artifacts: true` to upload `.sigstore` bundles to the existing GitHub Release page; `attestations: write` is needed for `actions/attest-build-provenance` to publish to the GitHub attestation API.
- **Why:** Per-job least-privilege scoping matches CIHARD-02 (Phase 51) discipline. SIGN-01 success criterion explicitly says "per-job `id-token: write` only on signing job". No other job in this workflow needs elevated permissions because there is no other job.
- **Alternative rejected:** Workflow-level `id-token: write` — would also work but violates least-privilege and breaks CIHARD-02's per-job opt-in pattern.

### `verify_release.py` implementation shape

- **D-03:** `scripts/verify_release.py` is a **stdlib-only Python script that shells out** to `python -m sigstore verify identity` and `git verify-tag` via `subprocess.run(..., capture_output=True, check=False)`. It mirrors `scripts/release_gate.py`'s stdlib-only contract (`scripts/release_gate.py:88` discipline). The script's only third-party dependency at runtime is the user's `pip install sigstore` (script prints a clear install hint and exits non-zero if `python -m sigstore` is not on `$PATH`).
- **Why:** release_gate.py established the stdlib-only invariant for `scripts/`. Verifying the trust chain MUST be runnable by anyone who clones the repo without imposing a sigstore runtime dependency on horus-os itself. The subprocess shape also produces deterministic exit codes per check (matches release_gate.py's `CheckResult` shape), making the 5-check report trivial to format.
- **Alternative rejected:** Direct `from sigstore import verify` Python import — would require `sigstore` in either `[project.dependencies]` (forbidden by v0.6 zero-base-dep rule; PROJECT.md key decision) or `[dev]` extras (acceptable but couples developer install to the verifier).

### `EXPECTED_IDENTITY` pinning shape

- **D-04:** `EXPECTED_IDENTITY` is a **hardcoded module-level constant** in `verify_release.py`:
  ```python
  EXPECTED_IDENTITY_TEMPLATE = "https://github.com/Ridou/horus-os/.github/workflows/release.yml@refs/tags/{version}"
  EXPECTED_ISSUER = "https://token.actions.githubusercontent.com"
  ```
  The `{version}` placeholder is interpolated from the mandatory `--version vN.M.P` CLI argument (the script REFUSES to run without it). The `--cert-oidc-issuer` CLI flag is ALSO mandatory and MUST equal `EXPECTED_ISSUER` exactly (the script refuses if the caller passes a different issuer string). No wildcards. No regex. No fallback.
- **Why:** SIGN-04 success criterion is explicit: "no wildcards, no regex; mandatory `--cert-oidc-issuer` flag; the script refuses to run without the issuer flag". Reading the identity from a JSON config file would invite future drift (someone "fixes" verification by relaxing the identity pattern) and reintroduce PITFALL 3 ("Sigstore verification with wildcard identity silently accepts attacker signatures"). Hardcoded is the only safe shape.
- **Alternative rejected:** JSON config file at `tests/fixtures/sigstore/identity.json` — flexibility = drift risk; PITFALL 3 is a known incident class.

### `gitsign` integration in STOP-BEFORE-TAG

- **D-05:** `docs/RELEASE.md` STOP-BEFORE-TAG block (the existing pre-tag checklist at `docs/RELEASE.md:10-49`) gets **TWO insertions** (per Phase 51 D-06's "insertions allowed, mutations not" discipline for the STOP-BEFORE-TAG sequence):
  - **NEW step 6.5** (inserted between current step 6 "Push to main + wait for CI green" and current step 7 "Create the annotated tag"): "Confirm `gitsign` is configured. Run `git config --get gitsign.connectorID` and assert non-empty output. If empty, follow the one-time gitsign setup in `docs/MAINTAINER-RUNBOOK.md` (Phase 56 lands this file). DO NOT proceed to step 7 until configured."
  - **Step 7 prose update:** swap the literal command from `git tag -a vN.M.P -m "vN.M.P - <milestone-name>"` to `git tag -s vN.M.P -m "vN.M.P - <milestone-name>"`. The `-s` flag tells git to invoke the configured signer (gitsign when `gitsign.connectorID` is set) to produce a signed tag. Push remains `git push origin vN.M.P`.
- **Why:** SIGN-03 success criterion mandates "no long-lived GPG keypair required" and "RELEASE.md STOP-BEFORE-TAG block documents the gitsign-configured `git tag` invocation". The pre-flight check (step 6.5) catches "gitsign not configured" before the maintainer types `git tag -s` (which would otherwise fall back to GPG and either fail loudly or succeed with the wrong signer). Two insertions, zero mutations to existing prose — preserves the byte-identity contract for steps 1-6 (per Phase 51 D-06 + ARCHITECTURE.md §"STOP-BEFORE-TAG block prose — v0.6 prepends new steps to the pre-tag list, MUST NOT mutate existing prose").
- **Alternative rejected:** Single-line swap (`-a` → `-s`) without the pre-flight check — misses the "gitsign not configured" failure mode that PITFALL 11 explicitly calls out ("A `git tag -s` in the release docs that uses `-s` (GPG) instead of gitsign. Stale instruction; update").

### `actions/attest-build-provenance` invocation granularity

- **D-06:** SLSA Build L2 attestations use **per-artifact `subject-path` invocations** (one `actions/attest-build-provenance@<sha>` step per artifact class), not a single `subject-path: 'dist/*'` glob:
  ```yaml
  - name: Attest wheel
    uses: actions/attest-build-provenance@<40-char-sha>
    with:
      subject-path: 'dist/*.whl'
  - name: Attest sdist
    uses: actions/attest-build-provenance@<40-char-sha>
    with:
      subject-path: 'dist/*.tar.gz'
  ```
  Phase 53 will append a third invocation for `dist/*.sbom.json` when it lands SBOM generation.
- **Why:** SIGN-02 success criterion is explicit: "runs for every signed artifact (wheel, sdist, both SBOMs)". Per-artifact invocations make per-artifact verification (`gh attestation verify <file>`) map 1:1 to a CI step; a failed attestation isolates to one artifact class without ambiguity. The `dist/*` glob would technically work but obscures which artifact failed if attestation generation hiccups on one but not others.
- **Alternative rejected:** Single `subject-path: 'dist/*'` — terser but less debuggable; loses 1:1 mapping between CI step and verifiable artifact.

### Canonical fixture provenance for verify_release.py tests

- **D-07:** `tests/fixtures/sigstore/canonical/` is seeded with a **pre-recorded `.sigstore` bundle from a horus-os release rehearsal** (recorded once by the maintainer running `release.yml` against a `v0.6.0-rc1` tag on a fork, per PITFALL 11 "release rehearsal" discipline; bundle + matching wheel artifact committed to the fixture directory along with a `README.md` documenting the recording procedure). The fixture is `wheel.sigstore` + `wheel.whl` paired so `tests/test_release_verification.py` can run `python scripts/verify_release.py --version 0.6.0-rc1 --cert-oidc-issuer https://token.actions.githubusercontent.com --bundle tests/fixtures/sigstore/canonical/wheel.sigstore --artifact tests/fixtures/sigstore/canonical/wheel.whl` and assert exit 0. The wrong-identity fixture under `tests/fixtures/sigstore/wrong_identity/` is owned by Phase 58 (TEST-24); Phase 52 ships ONLY the positive canonical fixture per ROADMAP Phase 52 success criterion #4.
- **Why:** CI cannot live-sign without OIDC (and shouldn't — that would require `id-token: write` in the test runner, expanding attack surface). Pre-recorded bundles are the canonical sigstore-python testing pattern. Recording from a `v0.6.0-rc1` rehearsal tag on a fork doubles as the release-rehearsal discipline PITFALL 11 mandates ("Before the actual tag push, the maintainer runs the entire release workflow against a `v0.6.0-rc1` tag on a fork"). The fixture is therefore both a test asset AND the artifact of a release-rehearsal dry run.
- **Alternative rejected:** Live-signing in CI test setup — requires `id-token: write` in test workflow, expanding attack surface; also forbidden by CIHARD-02 per-job permission discipline.

### `verify_release.py` 5-check skeleton with deferred SBOM check

- **D-08:** `verify_release.py` ships in Phase 52 with the **full 5-check skeleton**:
  1. `wheel-signature` — `python -m sigstore verify identity --cert-identity <EXPECTED_IDENTITY> --cert-oidc-issuer <EXPECTED_ISSUER> --bundle <wheel.sigstore> <wheel.whl>` exit 0.
  2. `sdist-signature` — same shape against `<sdist.tar.gz.sigstore>` + `<sdist.tar.gz>`.
  3. `tag-signature` — `git verify-tag v<version>` exit 0 in the repo working tree (or fresh clone if `--clone <url>` passed).
  4. `sbom-signature` — **STUB returning `SKIPPED — Phase 53 lands SBOM generation + signing`** until Phase 53 lands the SBOM signing step. Stub is wired (the check function exists, the result row prints) so Phase 53 only needs to flip the stub to active, not insert a new check.
  5. `changelog-cross-ref` — fetches `gh release view v<version> --json body --jq .body` and asserts the body matches the `[N.M.P] - YYYY-MM-DD` section extracted from `CHANGELOG.md` (textual cross-ref; whitespace-normalized).
  Default invocation runs all 5 checks; `--check {wheel|sdist|tag|sbom|changelog}` runs one. Skeleton is locked here; Phase 53 ONLY flips the SBOM stub from SKIPPED to active.
- **Why:** ROADMAP Phase 52 success criterion #4 says "5-check user-facing trust-chain verifier" — present tense in Phase 52, so the 5-check shape MUST exist in this phase. Shipping the SBOM check as a wired stub (instead of "Phase 53 adds the 5th check later") preserves the 5-check shape as a Phase 52 deliverable AND lets Phase 53's planner make a minimal, surgical edit (flip stub to active; add 3 lines invoking `python -m sigstore verify identity` against `<sbom.sigstore>` + `<sbom.cdx.json>`) rather than re-architecting the script. Mirrors v0.5's REL-12-then-REL-13 incremental-extension pattern.
- **Alternative rejected:** Ship 4 active checks in Phase 52, let Phase 53 insert the 5th — requires Phase 53 to touch the dispatch order, the CLI enum, the report formatter; more drift surface than flipping one stub.

### `.planning/decisions/no-pypi-in-v0.6.md` + PROJECT.md update both land in this phase

- **D-09:** Both the decision file (`.planning/decisions/no-pypi-in-v0.6.md` — explains why PyPI Trusted Publishing PEP 807 is out of scope for v0.6: horus-os does not currently publish to PyPI, no `PYPI_API_TOKEN` exists, v0.7+ may revisit) AND the PROJECT.md key-decisions table row referencing it land in Phase 52, in the same commit. SIGN-05 success criterion couples them ("decision file referenced from PROJECT.md key-decisions table"); splitting across phases breaks the requirement.
- **Why:** SIGN-05 is one requirement, one phase, one commit. Deferring the PROJECT.md update to Phase 56 (docs refresh) would split SIGN-05's deliverable across two phases and complicate Phase 57's release-gate extension (which may grow a `no-pypi-decision-file-exists` cross-check; that check would otherwise fail between Phase 52 and Phase 56). Single-commit landing matches Phase 51's "atomic doc-or-code" discipline.
- **Alternative rejected:** Decision file here; PROJECT.md update in Phase 56 — splits SIGN-05; risks docs drift between phases.

### Phase 53 SBOM-signing input-glob coordination

- **D-10:** `release.yml`'s sigstore-python `inputs:` value in Phase 52 is exactly **`./dist/*.whl ./dist/*.tar.gz`** (two-glob whitespace-separated form per sigstore-python action docs). Phase 53 will WIDEN this to `./dist/*.whl ./dist/*.tar.gz ./dist/*.sbom.json` (append, not rewrite) when it adds the SBOM generation step ahead of the sign step. Phase 52 does NOT introduce `dist/*.sbom.json` because Phase 53 owns SBOM generation (separation of concerns; ROADMAP §"Phase 53 ... SBOM signing in `release.yml` runs after Phase 52 lands the sign step").
- **Why:** Phase 53 lands the `cyclonedx-py environment` step that produces `dist/*.sbom.json`. Phase 52's release.yml sign step MUST be ready to accept the additional glob without restructuring. Whitespace-separated glob list is the documented sigstore-python action input shape and is the smallest possible Phase 53 diff (one append, no reshape).
- **Alternative rejected:** Phase 52 signs SBOMs proactively — would need Phase 52 to stub-generate an empty SBOM (no value) OR conditionally skip (added branching); both worse than Phase 53 appending one glob.

### Claude's Discretion

- **Exact SHA values** for `sigstore/gh-action-sigstore-python@<sha>`, `actions/attest-build-provenance@<sha>`, `actions/checkout@<sha>`, `actions/setup-python@<sha>`: planner resolves at plan-time via `pinact run --update` (the Phase 51 D-03-documented maintainer tool) or via `gh api repos/{owner}/{repo}/git/ref/tags/{tag}` per pin. The 40-char SHA invariant is non-negotiable (CIHARD-04, Phase 51).
- **Whether `sigstore-python` action version range is `>=4.2,<5` or a specific minor (e.g. `==4.2.0`)**: planner decides. SIGN-01 specifies `>=4.2,<5`. The action wraps the Python library; pinning the action SHA is the load-bearing decision; the library version range is a courtesy lower bound.
- **Exact `gitsign` install instructions in `docs/MAINTAINER-RUNBOOK.md`**: Phase 56 owns the runbook content; Phase 52 only references it from RELEASE.md step 6.5. If Phase 52 lands before Phase 56, the RELEASE.md reference is a forward reference (acceptable; phases land sequentially and the runbook will exist by ship time per ROADMAP order 51 → (52 ∥ 53) → 54 → (55 ∥ 56) → 57 → 58 → 59).
- **`verify_release.py` argparse subcommand vs flag-only CLI**: planner decides. Subcommand (e.g. `verify_release.py verify --version ...`) is more extensible; flag-only (`verify_release.py --version ...`) matches release_gate.py. Either is acceptable.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope + requirements

- `.planning/REQUIREMENTS.md` §`### Sigstore signing (SIGN)` (lines 395-399 region) — SIGN-01..05 (the 5 requirements this phase owns)
- `.planning/ROADMAP.md` §`### Phase 52: Signing substrate (\`release.yml\` NEW)` — phase goal, success criteria, deps; mirrors this CONTEXT.md's `<domain>` block
- `.planning/PROJECT.md` §`## Current Milestone: v0.6 Contribution Gate` — milestone-level goal + the 8 v0.6 decisions table (Phase 52 appends the `no-pypi-in-v0.6` row per D-09)

### Research substrate (v0.6 SUMMARY + 4 dimension docs)

- `.planning/research/SUMMARY.md` — executive map; signing identity matrix; PyPI Trusted Publishing deferral rationale; per-phase rationale block for Phase 53 (the original numbering — research SUMMARY's "Phase 53" is the same phase this CONTEXT.md is for; the v0.6 roadmap consolidated 52↔53 numbering)
- `.planning/research/STACK.md` — `sigstore-python` version pin + `sigstore/gh-action-sigstore-python` action shape + `actions/attest-build-provenance` reference + `gitsign` install reference
- `.planning/research/PITFALLS.md` §`### Pitfall 3` (lines 90-130) and §`### Pitfall 9` (lines 388-415) and §`### Pitfall 11` (lines 473-516) — the three pitfalls this phase mitigates; specific incident citations (Ultralytics, sigstore-java GHSA-jp26-88mw-89qr, PEP 740 attestation rollout, gitsign vs GPG)
- `.planning/research/ARCHITECTURE.md` §`Q1 — Where do signing steps live in ci.yml?` (lines 109-164) and §`Q2 — Where does SBOM generation live?` (lines 168-198) — the canonical job-shape recommendation for `release.yml` + 15 byte-identity invariants (signing/SBOM tooling MUST NOT enter base `dependencies`)

### Phase 51 substrate (HARD precondition)

- `.planning/phases/51-ci-hardening-substrate/51-CONTEXT.md` — Phase 51 decisions D-01..D-06; in particular D-02 (two-layer SHA-pin enforcement) and D-06 (issue-claim-watcher.yml hardening) define the conventions release.yml inherits
- `.planning/phases/51-ci-hardening-substrate/51-02-SUMMARY.md` — the 40-char SHA-pin pattern with trailing `# vN.M.P` comment (pinact v4.0.0 tag-comment convention) Phase 52 mirrors on every `uses:` in release.yml
- `.github/workflows/ci.yml` — the post-Phase-51 byte-identity reference for top-level `permissions: read-all` placement, per-job `persist-credentials: false` shape, and `Run actionlint` step naming convention

### Files Phase 52 creates (NEW)

- `.github/workflows/release.yml` — NEW; single `sign-and-attest` job; triggers on `release: types: [published]`
- `scripts/verify_release.py` — NEW; stdlib-only; 5-check trust-chain verifier with hardcoded `EXPECTED_IDENTITY` (D-04, D-08)
- `.planning/decisions/no-pypi-in-v0.6.md` — NEW; explains PEP 807 Trusted Publishing deferral (D-09)
- `tests/fixtures/sigstore/canonical/` — NEW directory; `wheel.sigstore` + `wheel.whl` + `README.md` documenting the rehearsal recording procedure (D-07)
- `tests/test_release_verification.py` — NEW; verifies the canonical fixture passes `verify_release.py`; canonical-only (wrong-identity test owned by Phase 58 / TEST-24)

### Files Phase 52 modifies

- `docs/RELEASE.md` — STOP-BEFORE-TAG block; ADD step 6.5 (gitsign pre-flight check) BETWEEN existing steps 6 and 7; UPDATE step 7 command from `git tag -a` to `git tag -s` (D-05). Steps 1-6 and 8-9 prose UNCHANGED.
- `PROJECT.md` — key-decisions table; APPEND row `no-pypi-in-v0.6 | OUT for v0.6 | .planning/decisions/no-pypi-in-v0.6.md` (D-09). Existing table rows UNCHANGED.

### Files Phase 52 explicitly does NOT touch

- `.github/workflows/ci.yml` — Phase 51 owns; release.yml is a NEW file, not an extension
- `scripts/release_gate.py` — Phase 57 owns 8 → 13 check extension; Phase 52's release.yml signature is detected by Phase 57's `release-workflow-signing-present` check via grep for the literal `sigstore/gh-action-sigstore-python`
- `pyproject.toml` — zero base-dep changes in v0.6 (Phase 53 owns the single `[dev]` extras addition of `pip-audit`); `sigstore` is NEVER added to runtime or dev deps; verify_release.py shells out to `python -m sigstore` and prints an install hint if absent (D-03)
- `tests/fixtures/sigstore/wrong_identity/` — Phase 58 owns (TEST-24); Phase 52 ships ONLY the canonical positive fixture

### Phase precedent (v0.5 + v0.6 patterns to mirror)

- `scripts/release_gate.py` lines 178-484 — `CheckResult` shape + per-check function signature contract; `verify_release.py` mirrors this shape one-for-one for its 5 checks
- `scripts/release_gate.py` lines 680-697 — `--check` argparse enum pattern; `verify_release.py` uses the same `choices=(...)` pattern with `("wheel", "sdist", "tag", "sbom", "changelog")`
- `scripts/lint_no_wallclock.py` — minimal stdlib-only Python lint precedent; verify_release.py inherits the "stdlib only, subprocess to external tools" discipline
- `tests/test_contribution_gate_pitfalls/` (Phase 51 created) — directory naming convention for v0.6 substrate tests; verify_release.py's tests live at `tests/test_release_verification.py` (top-level, not nested) because it tests one script, not a pitfall class
- `.planning/decisions/` — directory does NOT exist yet at time of this CONTEXT writing; Phase 52 is the FIRST phase to land a decision file here. Phase 56 lands additional decision files (sigstore-keyless.md, no-cla.md, no-stale-bot.md, sbom-cyclonedx.md) per ROADMAP. The directory structure is therefore established by Phase 52.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`scripts/release_gate.py`** — the canonical stdlib-only Python script pattern for `scripts/`. `verify_release.py` clones its shape: `CheckResult` namedtuple/dataclass, per-check function with `(input_path: Path) -> CheckResult` signature, `_print_result` formatter, argparse `--check` enum, dispatch list in `main()`. The release_gate.py shape is stable across v0.4 Phase 39 and v0.5 Phase 49 extensions; using it for verify_release.py keeps the script-surface idiom consistent.
- **`scripts/release_gate.py` `check_pytest_pass` function (lines 307-330)** — the canonical subprocess-with-capture pattern (tail 20 lines on failure, structured exit-code handling). verify_release.py's `check_wheel_signature` and `check_sdist_signature` mirror this exactly, shelling out to `python -m sigstore verify identity` with `capture_output=True, check=False`, then parsing stdout for the success line.
- **`scripts/lint_no_wallclock.py`** — fallback precedent if `python -m sigstore` is not on `$PATH`; verify_release.py prints a clear install hint (`"pip install sigstore"`) and exits with diagnostic-only output rather than a misleading verification failure.
- **`docs/RELEASE.md` STOP-BEFORE-TAG block** (lines 10-49 of the current file) — the human-confirmation gate sequence. Phase 52 inserts step 6.5 between existing steps 6 and 7 and updates the literal command in step 7 from `git tag -a` to `git tag -s`. The "insertions allowed, mutations not" discipline carries over from Phase 51 D-06 (`docs/RELEASE.md` STOP-BEFORE-TAG block byte-identity invariant per ARCHITECTURE.md line 102).
- **`.github/workflows/ci.yml`** (post-Phase 51) — the byte-identity reference for: top-level `permissions: read-all` placement (line 9), per-job opt-in pattern, every-`uses:`-is-SHA-pinned-with-trailing-`# vN.M.P`-comment, `persist-credentials: false` on every `actions/checkout`. release.yml inherits all four conventions.

### Established Patterns

- **One workflow per trigger class** — `ci.yml` for `push: + pull_request:`, `issue-claim-watcher.yml` for `issue_comment:`, release.yml for `release: published`. This is the v0.5-established convention; ARCHITECTURE.md §Q1 explicitly cites it as the rationale for a SEPARATE release.yml file rather than additions to ci.yml.
- **`HORUS_OS_*_PATH_OVERRIDE` env vars for hermetic tests** — release_gate.py uses `HORUS_OS_RELEASE_GATE_*` env vars to override path defaults for testing. verify_release.py adopts the same idiom: `HORUS_OS_VERIFY_RELEASE_BUNDLE_OVERRIDE`, `HORUS_OS_VERIFY_RELEASE_ARTIFACT_OVERRIDE`, etc. (planner can finalize the exact env-var names).
- **Per-artifact attestation 1:1 with per-artifact verification** — the v0.4 OtelAdapter ships per-event-class observation methods rather than a single `observe(event)`. release.yml mirrors that granularity: per-artifact `attest-build-provenance` invocation rather than `subject-path: 'dist/*'` glob.
- **`.planning/decisions/` directory convention** — does NOT exist yet; Phase 52 establishes it with `no-pypi-in-v0.6.md`. Files in this directory are short (≤2 pages), terminate with a one-line `**Decision (final, until revisited):**` block, and are referenced from PROJECT.md's key-decisions table. Phase 56 lands additional decision files using the same shape.

### Integration Points

- **`docs/RELEASE.md` STEP 6 → STEP 7 boundary** — exactly where step 6.5 inserts (Confirm `gitsign` configured). The existing step 6 ends with `gh run list --branch main --limit 1` confirmation; the existing step 7 begins with `git tag -a vN.M.P`. The new step 6.5 is the bridge.
- **`PROJECT.md` key-decisions table** — Phase 52 APPENDS one row at the table's end (no row reordering); the table is `decision | status | reference-file`-shaped per existing precedent.
- **`.github/workflows/release.yml` ↔ `scripts/release_gate.py`** — Phase 57's `release-workflow-signing-present` check (added in Phase 57, not Phase 52) will grep release.yml for the literal `sigstore/gh-action-sigstore-python`. Phase 52 ensures this literal appears verbatim in the workflow file's `uses:` line.
- **`tests/fixtures/sigstore/canonical/` ↔ `tests/fixtures/sigstore/wrong_identity/`** — Phase 52 creates `canonical/`; Phase 58 (TEST-24) creates the sibling `wrong_identity/`. The two directories share the same fixture-file naming convention (`wheel.sigstore + wheel.whl`) so the test harness can iterate over both with identical glob patterns.
- **`gitsign` ↔ git's standard `tag -s` flag** — `gitsign` registers itself as git's signer via `git config --global gpg.x509.program gitsign` + `git config --global tag.gpgsign true` (or per-repo). When `git tag -s` is invoked, git delegates to gitsign without ANY change to git's own `-s` semantics. This is what makes the STOP-BEFORE-TAG step 7 swap a one-character change (`-a` to `-s`) instead of a new command.

</code_context>

<specifics>
## Specific Ideas

- **release.yml MUST trigger on `on: release: types: [published]` ONLY.** Not `on: push: tags:`, not `on: workflow_dispatch:`. ARCHITECTURE.md §Q1 + ROADMAP success criterion #1 both fix this. The `release: published` trigger preserves the human-confirmation gate in STOP-BEFORE-TAG (`gh release create` is step 8 of the maintainer's checklist; workflow fires only when that step lands).
- **Step ordering inside `sign-and-attest` is load-bearing.** `python -m build` MUST precede `sigstore/gh-action-sigstore-python`. The sigstore action MUST precede `actions/attest-build-provenance` (attestations bind to the existing signed artifact). The 5-minute OIDC-to-sign budget (SIGN-01) is measured from sigstore-action invocation to bundle emission; build time is OUT of the budget but IN of the total job runtime budget.
- **`.sigstore` bundle format ONLY.** No `.sig` detached signatures (PITFALL 3: "Detached signatures require a separate round-trip to the transparency log to fetch the inclusion proof"). sigstore-python's `release-signing-artifacts: true` mode emits bundles by default; do not pass any flag that would switch to detached.
- **`EXPECTED_IDENTITY` `{version}` substitution is the ONLY mutation.** The string `https://github.com/Ridou/horus-os/.github/workflows/release.yml@refs/tags/{version}` is otherwise byte-identical. No URL encoding. No trailing slash. No `refs/heads/` ever (tags only). Verify_release.py asserts this shape at module-import time (assertion: `"refs/tags/{version}" in EXPECTED_IDENTITY_TEMPLATE`).
- **`docs/MAINTAINER-RUNBOOK.md` forward reference is acceptable.** Phase 56 lands the runbook; Phase 52's STOP-BEFORE-TAG step 6.5 references it by path. If Phase 56 has not landed at the time a maintainer reads RELEASE.md, the reference text is enough to find the file once it exists. The ROADMAP execution order (52 ∥ 53) → 54 → (55 ∥ 56) means Phase 56 lands BEFORE the first v0.6 release tag is pushed (which is Phase 59), so the runbook IS present at the moment the STOP-BEFORE-TAG sequence is followed for real.
- **Canonical fixture's `--version 0.6.0-rc1` is the recording-time version, not a substitution placeholder.** The fixture was recorded during a rehearsal release; the `EXPECTED_IDENTITY` it verifies against is literally `...@refs/tags/0.6.0-rc1`. Tests pin `--version 0.6.0-rc1` against this fixture. The Phase 58 wrong-identity fixture uses the SAME `0.6.0-rc1` version but a DIFFERENT workflow path (e.g., `someone-elses-repo/.github/workflows/release.yml@refs/tags/0.6.0-rc1`), which the verifier MUST reject.

</specifics>

<deferred>
## Deferred Ideas

- **SBOM generation step in release.yml** — Phase 53 (SBOM-01..03). Phase 52's release.yml has zero SBOM logic; Phase 53 inserts the `cyclonedx-py environment` step between `python -m build` and `sigstore/gh-action-sigstore-python`, then widens the sigstore `inputs:` glob to include `dist/*.sbom.json` (per D-10).
- **`actions/attest-sbom` invocation for SBOM attestations** — Phase 53 (SBOM-03). Mirrors Phase 52's `attest-build-provenance` per-artifact granularity (D-06); one `attest-sbom` per SBOM file.
- **`release-workflow-signing-present` release-gate check** — Phase 57 (REL-14). Phase 52 commits release.yml with the literal `sigstore/gh-action-sigstore-python`; Phase 57 grep-checks for that literal in the gate. Phase 52 does NOT touch release_gate.py.
- **`release-workflow-sbom-present` release-gate check** — Phase 57 (REL-15). Same pattern as above for the literal `cyclonedx_py`. Phase 52 does NOT seed this literal (Phase 53 owns).
- **`actions-pinned-by-sha` release-gate check (release.yml coverage)** — Phase 57. Will regex over `.github/workflows/release.yml` asserting every `uses:` is `@<40-hex>`. Phase 52's contribution is to ensure every `uses:` IS SHA-pinned in the file it writes.
- **Wrong-identity negative test fixture + assertion (TEST-24)** — Phase 58. Creates `tests/fixtures/sigstore/wrong_identity/` (sibling to Phase 52's `canonical/`) and the test that asserts verify_release.py REJECTS it.
- **PyPI Trusted Publishing (PEP 807) wiring** — DEFERRED to v0.7+ per D-09. Decision file landed in Phase 52 (`no-pypi-in-v0.6.md`); the wiring itself is out of scope until horus-os actually publishes to PyPI.
- **Sigstore Rekor private deployment** — out of scope for any v0.6 phase. Sigstore Public Good Instance is the lock; no operational alternative considered.
- **`zizmor` workflow-security audit on release.yml** — Phase 54 (DEPBOT-03). Will audit release.yml alongside ci.yml after Phase 52 lands it. Complements actionlint (Phase 51); both ship; both cheap; no contention.
- **`docs/MAINTAINER-RUNBOOK.md` content (gitsign one-time setup)** — Phase 56 (RUNBOOK-01). Phase 52's STOP-BEFORE-TAG step 6.5 forward-references this file; Phase 56 lands its content.
- **`docs/POSTFLIP-PLAYBOOK.md` rollback procedure** — Phase 59 (FLIP-01). Out of scope for Phase 52; relevant only after v0.6.0 ships.
- **Release rehearsal procedure documentation** — partial coverage: PITFALL 11 mandates a `v0.6.0-rc1` rehearsal on a fork; Phase 52 implicitly establishes this by sourcing its canonical fixture from such a rehearsal. The full rehearsal procedure prose lives in `docs/RELEASE.md` "Release rehearsal" subsection added in Phase 58 (TEST-22). Phase 52 ships the artifact (the fixture); Phase 58 ships the procedure.

</deferred>

---

*Phase: 52-signing-substrate-release-yml-new*
*Context gathered: 2026-05-29*
