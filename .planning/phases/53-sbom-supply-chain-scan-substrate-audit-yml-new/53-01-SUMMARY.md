---
phase: 53
plan: "01"
completed: 2026-05-30
status: complete
---

# Phase 53 Plan 01 Summary: Wave 0 RED-by-design SBOM + supply-chain test scaffolds

## Tasks Completed

| Task | File(s) | Status |
|------|---------|--------|
| Task 1 (audit.yml + release.yml + pip-audit-ignore + pyproject test scaffolds) | tests/test_audit_yml_structure.py, tests/test_release_yml_sbom_steps.py, tests/test_pip_audit_ignore_discipline.py, tests/test_pyproject_pip_audit_dev.py | complete |
| Task 2 (verify_release.py SBOM check active-mode test scaffold) | tests/test_verify_release_sbom.py | complete |

## Production Assertions: RED vs GREEN State

| File | Production Tests | RED | GREEN | SKIP |
|------|------------------|-----|-------|------|
| tests/test_audit_yml_structure.py | 14 | 13 | 1 (test_audit_yml_exists in pre-create FileNotFoundError flow) | 0 |
| tests/test_release_yml_sbom_steps.py | 12 | 11 | 1 (test_release_yml_exists; file exists from Phase 52) | 0 |
| tests/test_pip_audit_ignore_discipline.py | 6 | 3 | 3 (no-op-when-file-missing tests) | 0 |
| tests/test_verify_release_sbom.py | 5 | 3 | 0 | 2 (canonical fixture; diff function deferred) |
| tests/test_pyproject_pip_audit_dev.py | 5 | 2 | 3 (pyproject exists; base unchanged; no pip-audit in [all]) | 0 |
| **Total** | 42 | 32 | 8 | 2 |

(One additional Wave 0 helper test that always RED'd because test_check_sbom_signature_no_longer_returns_skipped uses tmp_path dummy bundles brings the count to 33 RED.)

## Non-Vacuity Coverage

| Scanner / Parser | Synthetic Violation | Status |
|------------------|---------------------|--------|
| audit.yml: missing `permissions: read-all` | tmp_path YAML omits the line | GREEN |
| audit.yml: contains `id-token: write` | tmp_path YAML includes the literal | GREEN |
| audit.yml: mutable tag (`pypa/gh-action-pip-audit@v1`) | tmp_path YAML with v1 tag | GREEN |
| audit.yml: missing dual-mode (only `-s osv`, no `-s pypi`) | tmp_path YAML with one source | GREEN |
| release.yml: `pip freeze` substitution (no cyclonedx-py environment, no .venv-sbom-clean) | tmp_path YAML | GREEN |
| release.yml: single attest-sbom (count != 2) | tmp_path YAML with one invocation | GREEN |
| release.yml: missing `--schema-version 1.6` | tmp_path YAML omits the flag | GREEN |
| pip-audit-ignore: undated comment | tmp_path with bad preceding comment | GREEN |
| pip-audit-ignore: orphan entry (no preceding comment) | tmp_path with bare ID line | GREEN |
| pip-audit-ignore: accepts well-formed dated comment | tmp_path with valid entry | GREEN |
| pyproject: missing pip-audit in dev | tmp_path TOML | GREEN |
| pyproject: unpinned pip-audit | tmp_path TOML with bare `pip-audit` | GREEN |
| verify_release.py: today's stub returns SKIPPED with ok=None | live module | GREEN |
| verify_release.py: module loads cleanly today | importlib spec | GREEN |
| verify_release.py: subprocess import smoke | `python -c '...'` | GREEN |

15 non-vacuity tests proving each scanner / parser fires on a known violation.

## Test Collection Counts

| File | Collected |
|------|-----------|
| tests/test_audit_yml_structure.py | 18 |
| tests/test_release_yml_sbom_steps.py | 15 |
| tests/test_pip_audit_ignore_discipline.py | 9 |
| tests/test_verify_release_sbom.py | 8 |
| tests/test_pyproject_pip_audit_dev.py | 7 |
| **Total** | 57 |

End state: 33 failed (RED-by-design production), 22 passed (non-vacuity + today-state), 2 skipped (canonical fixture + diff function deferred). All RED diagnostics name the missing file or function and cite the SBOM-NN / SUPPLY-NN requirement.

## Self-Check

- [x] All 5 test files exist at tests/ top-level
- [x] Each file contains `REPO_ROOT = Path(__file__).resolve().parents[1]`
- [x] All required literals present (audit.yml: 17; release.yml SBOM: 13; pip-audit: 3; pyproject: 1)
- [x] 57 tests collected, 22 GREEN, 33 RED-by-design, 2 SKIP
- [x] `ruff check` exits 0 on all 5 files
- [x] `ruff format --check` exits 0 on all 5 files
- [x] No em-dashes / en-dashes (grep -P returns empty)

## Requirements Coverage

| Requirement | Test File | Test(s) |
|-------------|-----------|---------|
| SBOM-01 | test_release_yml_sbom_steps.py | test_fresh_venv_sbom_generation, test_cyclonedx_environment_called, test_schema_version_1_6_locked, test_output_format_json, test_cyclonedx_bom_version_pinned, test_sigstore_inputs_include_cdx_json |
| SBOM-02 | test_release_yml_sbom_steps.py | test_two_sbom_variants, test_pip_install_wheel_for_extras |
| SBOM-03 | test_release_yml_sbom_steps.py + test_verify_release_sbom.py | test_two_attest_sbom_invocations, test_attest_sbom_sha_pinned, test_attest_sbom_sbom_path_paired, test_check_sbom_signature_no_longer_returns_skipped, test_check_sbom_signature_signature_supports_bundle_artifact_args, test_check_sbom_signature_two_bundles_verified, test_main_sbom_check_runs_active |
| SUPPLY-01 | test_audit_yml_structure.py + test_pyproject_pip_audit_dev.py | test_pip_audit_action_present, test_pip_audit_action_sha_pinned, test_pip_audit_dual_mode, test_dev_extras_includes_pip_audit, test_dev_extras_pip_audit_version_pinned, test_base_deps_unchanged, test_no_other_optional_extras_have_pip_audit |
| SUPPLY-02 | test_audit_yml_structure.py | test_dependency_review_action_present, test_dependency_review_action_sha_pinned, test_dependency_review_license_allowlist, test_dependency_review_comment_on_failure |
| SUPPLY-03 | test_pip_audit_ignore_discipline.py | test_ignore_file_exists, test_tracking_dir_exists, test_tracking_readme_exists, test_every_entry_has_dated_comment, test_tracking_readme_documents_convention, test_at_launch_ignore_file_may_be_empty_but_format_documented |
| SUPPLY-04 | test_audit_yml_structure.py | test_two_variant_matrix |

All 7 v0.6 requirements addressed by RED scaffolds.

## Hand-off Notes (Plan 02)

Plan 02 (Wave 1 GREEN flip) must:

1. **Create `.github/workflows/audit.yml`** with all literals enumerated in tests/test_audit_yml_structure.py acceptance criteria. SHA-pin every uses: line. NO `id-token: write` anywhere. Mirror Phase 52 release.yml structure conventions.
2. **Extend `.github/workflows/release.yml`** with two `python -m venv .venv-sbom-*` + `cyclonedx-py environment` steps, modify sigstore inputs glob to append `./dist/*.cdx.json`, add two `actions/attest-sbom@<SHA>` invocations.
3. **Create `.github/pip-audit-ignore.txt`** with format-documenting header comment block, empty CVE list at launch.
4. **Create `.github/pip-audit-tracking/README.md`** documenting the per-CVE convention.
5. **Flip `scripts/verify_release.py check_sbom_signature`** from Phase 52 D-08 stub (`ok=None, "SKIPPED - Phase 53 lands ..."`) to active 2-bundle verification per D-05 signature. Add 4 CLI args (`--clean-bundle`, `--clean-artifact`, `--extras-bundle`, `--extras-artifact`).
6. **Add `pip-audit>=2.10,<3` to pyproject.toml `[project.optional-dependencies].dev`** (alphabetical insert between `httpx` and `pytest`). NO change to base `[project.dependencies]` or `[all]`.
7. **Update tests/test_verify_release_sbom.py D-09 inverse-flip**: `test_phase_52_stub_currently_returns_skipped` already auto-skips when the new signature is detected. Optionally rename to `test_check_sbom_signature_returns_skipped_only_with_no_bundles` with the new assertion.

After Plan 02 lands, all 33 RED tests flip GREEN. 2 SKIP tests stay SKIP (canonical binary not yet recorded; diff function deferred to Phase 57). Phase 52's existing tests (test_release_yml_structure.py, test_release_verification.py) MUST continue passing (no regression).
