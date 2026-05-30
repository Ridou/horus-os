---
phase: 53
slug: sbom-supply-chain-scan-substrate-audit-yml-new
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-30
---

# Phase 53 Validation Strategy

> Per-phase validation contract. Derived from `53-RESEARCH.md` §Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) |
| **Quick run command** | `pytest tests/test_audit_yml_structure.py tests/test_release_yml_sbom_steps.py tests/test_pip_audit_ignore_discipline.py tests/test_verify_release_sbom.py tests/test_pyproject_pip_audit_dev.py -v` |
| **Full suite command** | `pytest -v` |
| **Estimated runtime** | ~30 s quick / ~2 min full |

---

## Sampling Rate

- **After every task commit:** quick run command above.
- **After every plan wave:** `pytest -v` (full suite).
- **Before `/gsd-verify-work`:** Full suite green on 3-OS CI matrix.
- **Max feedback latency:** 30 seconds for the quick command.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | 53-NN | TBD | SBOM-01 | PITFALL (pip-freeze SBOM) | release.yml SBOM step uses `python -m venv .venv-sbom-clean` + `pip install dist/*.whl` + `cyclonedx-py environment` (NOT `pip freeze`); schema-version 1.6 locked | structural | `pytest tests/test_release_yml_sbom_steps.py::test_fresh_venv_sbom_generation -v` | Wave 0 | pending |
| TBD | 53-NN | TBD | SBOM-02 | (none) | release.yml contains TWO SBOM generation steps (clean + dev,otel); both `.cdx.json` artifacts appended to the sigstore inputs glob | structural | `pytest tests/test_release_yml_sbom_steps.py::test_two_sbom_variants -v` | Wave 0 | pending |
| TBD | 53-NN | TBD | SBOM-03 | (none) | release.yml contains TWO `actions/attest-sbom@<sha>` invocations; verify_release.py `check_sbom_signature` is no longer a stub and asserts both bundles + diff matches | structural + unit | `pytest tests/test_verify_release_sbom.py -v` | Wave 0 | pending |
| TBD | 53-NN | TBD | SUPPLY-01 | PITFALL (id-token in audit.yml) | audit.yml exists; trigger is `pull_request`; top-level `permissions: read-all`; per-job `contents: read` only; NO `id-token: write` anywhere; runs `pypa/gh-action-pip-audit@<sha>` dual-mode `-s osv` AND `-s pypi` | structural | `pytest tests/test_audit_yml_structure.py -v` | Wave 0 | pending |
| TBD | 53-NN | TBD | SUPPLY-01 | (none) | pyproject.toml `[project.optional-dependencies] dev` adds `pip-audit>=2.10,<3` | structural | `pytest tests/test_pyproject_pip_audit_dev.py -v` | Wave 0 | pending |
| TBD | 53-NN | TBD | SUPPLY-02 | (none) | audit.yml `dependency-review` job uses `actions/dependency-review-action@<sha>` with `allow-licenses: Apache-2.0, MIT, BSD-2-Clause, BSD-3-Clause, ISC, PSF-2.0` and `comment-summary-in-pr: on-failure` | structural | `pytest tests/test_audit_yml_structure.py::test_dependency_review_license_allowlist -v` | Wave 0 | pending |
| TBD | 53-NN | TBD | SUPPLY-03 | (none) | `.github/pip-audit-ignore.txt` exists; every non-comment entry preceded by a `# YYYY-MM-DD: <reason>` line; `.github/pip-audit-tracking/` directory exists with `README.md` documenting the convention | structural + lint | `pytest tests/test_pip_audit_ignore_discipline.py -v` | Wave 0 | pending |
| TBD | 53-NN | TBD | SUPPLY-04 | (none) | audit.yml pip-audit job uses `strategy.matrix.extras` over `[dev]` AND `[dev,otel]`; both literals present in workflow text | structural | `pytest tests/test_audit_yml_structure.py::test_two_variant_matrix -v` | Wave 0 | pending |

---

## Wave 0 Requirements

- [ ] `tests/test_audit_yml_structure.py` (SUPPLY-01, SUPPLY-02, SUPPLY-04; multiple assertions per the table above)
- [ ] `tests/test_release_yml_sbom_steps.py` (SBOM-01, SBOM-02)
- [ ] `tests/test_pip_audit_ignore_discipline.py` (SUPPLY-03)
- [ ] `tests/test_verify_release_sbom.py` (SBOM-03; flips Phase 52 D-08 SKIP stub)
- [ ] `tests/test_pyproject_pip_audit_dev.py` (SUPPLY-01 pyproject row)

All Wave 0 tests RED-by-design until Wave 1 lands the production code. Non-vacuity synthetic-fixture tests pass NOW (proving the scanners fire on known violations written to `tmp_path`).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Canonical SBOM bundle binary fixture (`*.cdx.json.sigstore`) | SBOM-03 | Same procedure as Phase 52 Plan 01 canonical fixture; binary lands at v0.6.0-rc1 rehearsal time | After Phase 52 rehearsal procedure completes, also `gh release download v0.6.0-rc1 -D tests/fixtures/sigstore/canonical/` will fetch the two `.cdx.json` + `.cdx.json.sigstore` files; commit alongside the wheel + bundle |
| `gh attestation verify` against a published SBOM | SBOM-03 | Requires a published GitHub Release with attached SBOM attestations | After rehearsal: `gh attestation verify dist/horus_os-clean.cdx.json --repo Ridou/horus-os --predicate-type https://spdx.dev/Document` (or the CycloneDX predicate URI; verify at execute time which URI attest-sbom uses) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30 s
- [ ] `nyquist_compliant: true` set after planner completes

**Approval:** pending
