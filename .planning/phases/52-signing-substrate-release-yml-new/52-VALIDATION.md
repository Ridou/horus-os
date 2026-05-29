---
phase: 52
slug: signing-substrate-release-yml-new
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-29
---

# Phase 52 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `52-RESEARCH.md` §Validation Architecture; planner extends per-task rows in §Per-Task Verification Map at plan-time.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing project framework; not new for this phase) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (existing) |
| **Quick run command** | `pytest tests/test_release_verification.py tests/test_release_yml_structure.py tests/test_release_md_stop_before_tag.py tests/test_decision_no_pypi.py -v` |
| **Full suite command** | `pytest -v` (from repo root) |
| **Estimated runtime** | ~30 s quick / ~2 min full (Ubuntu CI) |

---

## Sampling Rate

- **After every task commit:** Run the quick run command above (subset of Phase 52 + non-Phase-52 tests adjacent to the changed file).
- **After every plan wave:** Run `pytest -v` (full suite; ~2 min Ubuntu CI).
- **Before `/gsd-verify-work`:** Full suite must be green on Ubuntu, macOS, Windows (CI matrix per `ci.yml`).
- **Max feedback latency:** 30 seconds for the quick command.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD-by-planner | 52-NN | TBD | SIGN-01 | PITFALL 3 (OIDC TTL) | release.yml exists; sigstore step has `timeout-minutes: 5`; per-job `id-token: write` ONLY on sign-and-attest | structural (workflow YAML lint) | `pytest tests/test_release_yml_structure.py -v` | Wave 0 | pending |
| TBD-by-planner | 52-NN | TBD | SIGN-02 | PITFALL 3 (provenance) | release.yml contains TWO per-artifact `actions/attest-build-provenance@<sha>` invocations; both SHA-pinned; per-job `attestations: write` | structural | `pytest tests/test_release_yml_structure.py::test_per_artifact_attest -v` | Wave 0 | pending |
| TBD-by-planner | 52-NN | TBD | SIGN-03 | PITFALL 11 (signed-tag) | docs/RELEASE.md step 6.5 inserted (mentions `gitsign.connectorID`); step 7 uses `git tag -s`; steps 1-6 and 8-9 prose byte-identical to pre-edit baseline | structural (docs lint) | `pytest tests/test_release_md_stop_before_tag.py -v` | Wave 0 | pending |
| TBD-by-planner | 52-NN | TBD | SIGN-04 | PITFALL 3 (wildcard identity) | verify_release.py `EXPECTED_IDENTITY_TEMPLATE` and `EXPECTED_ISSUER` hardcoded constants present byte-identical to spec; argparse refuses without `--cert-oidc-issuer` AND without `--version`; refuses on mismatched issuer; canonical fixture passes; SBOM check returns SKIPPED | unit + integration | `pytest tests/test_release_verification.py -v` | Wave 0 | pending |
| TBD-by-planner | 52-NN | TBD | SIGN-05 | PITFALL 9 (PyPI deferral) | `.planning/decisions/no-pypi-in-v0.6.md` exists with `**Decision (final, until revisited):**` terminator; PROJECT.md key-decisions table contains a row referencing the decision file path | structural | `pytest tests/test_decision_no_pypi.py -v` | Wave 0 | pending |

*Status: pending / green / red / flaky*

*The planner populates concrete `Task ID`, `Plan`, and `Wave` columns during plan-phase. Each task MUST cite at least one row from this table in its `<acceptance_criteria>`.*

---

## Wave 0 Requirements

- [ ] `tests/test_release_verification.py` — SIGN-04 (5 tests: canonical-fixture pass, missing-issuer refuse, wrong-issuer refuse, SBOM-stub returns SKIPPED, full-run all-checks)
- [ ] `tests/test_release_yml_structure.py` — SIGN-01 + SIGN-02 (9 assertions: file-exists, on-release-published trigger, top-level `permissions: read-all`, per-job `id-token: write`, both `attest-build-provenance` present, sigstore literal present, sigstore SHA-pinned, `timeout-minutes: 5` on sign step, every `uses:` SHA-pinned)
- [ ] `tests/test_release_md_stop_before_tag.py` — SIGN-03 (3 tests: step 6.5 inserted with gitsign connector-id phrase; step 7 uses `tag -s` not `tag -a`; steps 1-6 + 8-9 byte-identical to pre-edit baseline string)
- [ ] `tests/test_decision_no_pypi.py` — SIGN-05 (3 tests: decision file exists; decision file has terminating `**Decision (final, until revisited):**` line; PROJECT.md key-decisions table contains a row referencing the decision file path)
- [ ] `tests/fixtures/sigstore/canonical/README.md` — documents the rehearsal recording procedure + observed bundle filename suffix
- [ ] `tests/fixtures/sigstore/canonical/<wheel>.whl` + `tests/fixtures/sigstore/canonical/<wheel>.whl.sigstore[.json]` — committed wheel + bundle from a v0.6.0-rc1 rehearsal release recorded on a fork

*No framework install — pytest already in `[dev]` extras per project conventions.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Canonical fixture recording (v0.6.0-rc1 rehearsal) | SIGN-04 (D-07) | Requires a live `gh release create` on a fork with OIDC; cannot run in CI. Recording happens ONCE per major release substrate change. | (1) On a fork, configure `gitsign`. (2) Push `v0.6.0-rc1` tag. (3) Run `gh release create v0.6.0-rc1 --prerelease`. (4) Wait for `release.yml` to complete; verify GitHub Release page shows wheel + `.sigstore` bundle. (5) `gh release download v0.6.0-rc1 -D tests/fixtures/sigstore/canonical/`. (6) Update README.md with recording date + observed bundle suffix. (7) Commit. |
| End-to-end gitsign tag signing on maintainer workstation | SIGN-03 | Requires interactive OAuth flow in browser; cannot be unit-tested. | (1) Run the four `git config` commands from `docs/MAINTAINER-RUNBOOK.md` (Phase 56 lands the content; pre-Phase-56 reference is the gitsign README). (2) Run `git config --get gitsign.connectorID`; assert non-empty. (3) Run `git tag -s vX.Y.Z-test -m "test"`; assert browser opens for OAuth; assert tag created. (4) Run `git verify-tag vX.Y.Z-test`; assert exit 0. (5) Delete the test tag. |
| `gh attestation verify` against a published release | SIGN-02 | Requires a published GitHub Release with attached attestations; cannot run pre-release. | After v0.6.0-rc1 rehearsal: `gh attestation verify dist/horus_os-0.6.0rc1-py3-none-any.whl --repo Ridou/horus-os`. Assert exit 0 + identity line matches `EXPECTED_IDENTITY`. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies (planner populates at plan-time)
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (5 Wave-0 gaps enumerated above)
- [ ] No watch-mode flags
- [ ] Feedback latency < 30 s
- [ ] `nyquist_compliant: true` set in frontmatter (after planner completes)

**Approval:** pending
