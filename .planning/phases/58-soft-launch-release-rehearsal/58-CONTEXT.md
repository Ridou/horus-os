# Phase 58: Soft launch + release rehearsal - Context

**Gathered:** 2026-05-30
**Status:** Ready for planning (autonomous portion + human UAT split)
**Mode:** Auto-generated (discuss skipped)

<domain>
## Phase Boundary

Last opportunity to identify friction BEFORE the public flip. Phase 58 is a hybrid phase:

- **Autonomous-completable now:** the pitfall regression suite (TEST-22), the wrong-identity sigstore negative-test fixture (TEST-24 negative case), and the install-smoke-matrix byte-identical assertion (TEST-25).
- **Human-only (rehearsal session):** 3-5 invited contributors landing sample PRs (TEST-26); the canonical wrong-identity recording from the rehearsal v0.6.0-rc1 release; first-time-contributor branch-protection setting (FLIP-02); `.planning/rollback/flip-gate-revert.md` git-apply test.

This CONTEXT.md scopes the autonomous portion; the human portion is enumerated in `.planning/v0.6-rehearsal-ready.md` (created in TASK 5).

</domain>

<canonical_refs>
## Canonical References

- `.planning/REQUIREMENTS.md` (TEST-22, TEST-24, TEST-25, TEST-26, FLIP-02)
- `.planning/ROADMAP.md` (Phase 58)
- `.planning/STATE.md`
- `.planning/research/PITFALLS.md` (the 12 pitfalls TEST-22 mirrors)
- `tests/test_plugin_pitfalls/test_pitfall_0X_*.py` (v0.5 precedent for filename + docstring shape)
- `tests/test_contribution_gate_pitfalls/test_pitfall_01_pull_request_target.py` (existing v0.6 example, pitfall 1)
- `tests/test_contribution_gate_pitfalls/test_pitfall_02_action_sha_pinning.py` (existing v0.6 example, pitfall 2)
- `scripts/verify_release.py` (the user-facing trust-chain verifier the wrong-identity fixture exercises)
- `tests/fixtures/sigstore/canonical/README.md` (positive-fixture canonical path; awaits rehearsal recording)

</canonical_refs>

<decisions>
## Implementation Decisions

### TEST-22 (pitfall regression suite)

10 new test files to land in `tests/test_contribution_gate_pitfalls/` (pitfalls 3 through 12). Pitfalls 1 + 2 already exist. Filename convention: `test_pitfall_<N>_<slug>.py` where N is zero-padded (matches v0.5 `tests/test_plugin_pitfalls/` precedent and existing 01/02 files). Each file:

- Cites the pitfall number + summary in the module docstring.
- Asserts the STRUCTURAL anti-pattern is absent from the relevant workflow/script/doc. If the anti-pattern is non-structural (e.g., Pitfall 6's "24h SLA promise"), assert the absence of the offending phrase in the documented file.
- Aims for ONE main assertion per pitfall plus optional non-vacuity tests for regex-based scans (mirrors `test_pitfall_02_action_sha_pinning.py` pattern with `tmp_path` fixtures).

### TEST-24 (wrong-identity sigstore negative fixture)

This is the AUTONOMOUS-ONLY portion: a hand-crafted negative fixture at `tests/fixtures/sigstore/wrong-identity/`. The fixture is documented as "this is a crafted stub for negative testing only; the canonical positive case requires the human UAT recording." Composition:

- `tests/fixtures/sigstore/wrong-identity/README.md` — purpose statement; explicit note that the bundle is hand-crafted (not gh-action-sigstore-python output).
- `tests/fixtures/sigstore/wrong-identity/wrong-identity-bundle.sigstore.json` — minimal stub with `verificationMaterial.certificate.subject` carrying a non-`Ridou/horus-os` repo identity (e.g., `https://github.com/Other/repo/.github/workflows/release.yml@refs/tags/v0.6.0`).
- `tests/test_verify_release_wrong_identity.py` — one test that invokes `scripts/verify_release.py --check identity ...` against the fixture and asserts exit code != 0. If the fixture stub is not realistic enough for the real verifier to round-trip, the test is `pytest.mark.skip(reason="awaits canonical fixture recording")` with a clear TODO.

### TEST-25 (install-smoke matrix byte-identical)

A regression test grepping `.github/workflows/ci.yml` for the existing job names. Asserts the literal strings `install-smoke-no-otel`, `install-smoke-with-otel`, `install-smoke-plugin` appear (no renames). This is a structural test; no CI invocation needed.

### Human-only UAT items (deferred to rehearsal session)

- TEST-26: 3-5 invited-contributor sample PRs (post-flip).
- TEST-24 canonical fixture: the positive-case `wheel.sigstore.json` recorded from the v0.6.0-rc1 release rehearsal.
- FLIP-02: branch-protection "Require approval for first-time contributors" setting (UI-only; no `gh api` mutation path documented at v0.6.0 time).
- RUNBOOK-02 consumer: `.planning/rollback/flip-gate-revert.md` `git apply --check` against a stale tree.

</decisions>

<specifics>
## Specific Constraints

1. CLAUDE.md HR3: no em-dashes anywhere in committed prose.
2. The wrong-identity fixture is HAND-CRAFTED; the README must say so explicitly so a future contributor does not try to verify the bundle with the real sigstore CLI and conclude the substrate is broken.
3. The verify_release.py `--check` enum is `{wheel, sdist, tag, sbom, changelog}` (no `identity` choice exists yet); the wrong-identity test must use `--check wheel` (which performs identity verification as part of the sigstore-verify shell-out).
4. The test must be RUN-AGNOSTIC: the verifier shells out to `python -m sigstore verify identity` which is NOT installed in the autonomous-run venv; the test should mark itself SKIP when sigstore is unavailable, matching the precedent in `tests/test_release_verification.py`.

</specifics>

<deferred>
## Deferred Ideas

A second wrong-identity fixture variant (wrong OIDC issuer rather than wrong identity URL) was considered but excluded; one negative case is sufficient for the v0.6 acceptance criterion. The variant can land in v0.7 if needed.

</deferred>
