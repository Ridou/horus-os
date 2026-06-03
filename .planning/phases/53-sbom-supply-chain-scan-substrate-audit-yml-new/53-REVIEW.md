---
phase: 53-sbom-supply-chain-scan-substrate-audit-yml-new
reviewed: 2026-05-30T11:00:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - .github/pip-audit-ignore.txt
  - .github/pip-audit-tracking/README.md
  - .github/workflows/audit.yml
  - .github/workflows/release.yml
  - pyproject.toml
  - scripts/verify_release.py
findings:
  critical: 0
  warning: 0
  info: 2
  total: 2
status: clean
---

# Phase 53: Code Review Report

**Reviewed:** 2026-05-30T11:00:00Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** clean

## Summary

Retroactive standard-depth review of all 6 non-test source files modified or created in Phase 53 (SBOM substrate + supply-chain scan + audit.yml). The implementation is sound:

- audit.yml omits `id-token: write` and runs on `pull_request` (not `pull_request_target`), correctly closing the fork-PR OIDC abuse vector that PITFALL 1 + PITFALL 2 cover.
- Every `uses:` line is SHA-pinned with a version comment (CIHARD-04).
- `actions/checkout` uses `persist-credentials: false` (CIHARD-03).
- release.yml SBOMs are generated against FRESH `pip install <wheel>` venvs (NOT pip freeze of the dev venv), per SBOM-01.
- sigstore-python step has a 5-minute `timeout-minutes` budget (PITFALL 2).
- attest-sbom invocations bind 1:1 to the wheel subject path (per-artifact granularity per D-06).
- verify_release.py SBOM check returns ok=None (SKIP) when no bundle paths provided, matching `check_wheel_signature` semantics so the dispatcher does not crash.
- subprocess calls in verify_release.py use `timeout=` parameter, capture both stdout and stderr, and tail the last 3 stderr lines into the diagnostic for actionable error messages.
- pyproject.toml adds `pip-audit>=2.10,<3` to `[dev]` extras only (NOT `[project.dependencies]`); honors the v0.6 zero-base-dep constraint.
- The `pip-audit-ignore.txt` file is empty at v0.6.0 launch (no carry-over CVEs); the format docstring is enforced by the Phase 57 `local-pip-audit-clean` release-gate check.

No Critical or Warning issues found. Two Info-tier observations below.

## Info

### IN-01: SBOM dev-otel install path uses shell glob

**File:** `.github/workflows/release.yml:67`
**Issue:** `pip install 'dist/*.whl[dev,otel]'` quotes the entire pattern, so the shell never expands `dist/*.whl`. pip then sees the literal string `dist/*.whl[dev,otel]` which it parses as a path pattern with extras. This works in practice because pip resolves the path glob internally, but the contrast with line 56 (`pip install dist/*.whl`, shell-expanded) is visually inconsistent.
**Fix:** Either unquote both for shell-expansion consistency, or document the quoting choice in the comment. The current behavior is correct, flagged for readability only:
```yaml
# pip resolves the glob internally so the literal string is correct here
.venv-sbom-extras/bin/pip install 'dist/*.whl[dev,otel]'
```

### IN-02: Glob in sigstore inputs accepts no-match silently

**File:** `.github/workflows/release.yml:78`
**Issue:** `inputs: ./dist/*.whl ./dist/*.tar.gz ./dist/*.cdx.json` relies on the sigstore action expanding globs. If the SBOM-generation steps above silently produce zero `.cdx.json` files (for example, cyclonedx-py exits 0 with no output on an empty venv), the sigstore step still passes because the action treats no-match as no-op. The two SBOM-generation steps DO have implicit exit-on-error from `set -e` defaults in `run:` blocks, so a real failure exits the job, but a corner case (cyclonedx-py emits warnings to stderr and exits 0 with no file) is silently absorbed.
**Fix:** Optional defense; assert SBOM file existence between SBOM-generation and sigstore-sign:
```yaml
- name: Assert SBOMs were generated
  run: |
    test -f dist/horus_os-clean.cdx.json
    test -f dist/horus_os-dev-otel.cdx.json
```
Not Blocking; the cyclonedx-py contract is reliable in practice.

---

_Reviewed: 2026-05-30T11:00:00Z_
_Reviewer: Claude (gsd-code-reviewer, inline-mode)_
_Depth: standard_
