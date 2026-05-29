---
status: partial
phase: 52-signing-substrate-release-yml-new
source: [52-VERIFICATION.md]
started: 2026-05-29
updated: 2026-05-29
---

## Current Test

[awaiting human testing]

## Tests

### 1. Canonical fixture recording (v0.6.0-rc1 rehearsal)
expected: tests/fixtures/sigstore/canonical/<wheel>.whl + <wheel>.whl.sigstore[.json] committed; the 2 currently-SKIPPED tests (test_canonical_fixture_passes_wheel_check, test_wheel_check_with_canonical_fixture) flip GREEN; README.md `Observed bundle filename suffix` section filled in with the actual recorded suffix (.sigstore vs .sigstore.json)
result: [pending]
why_human: Requires a live `gh release create` on a fork with OIDC; cannot run in CI. Recording happens ONCE per major release substrate change. See tests/fixtures/sigstore/canonical/README.md + VALIDATION.md Manual-Only Verifications row 1.

### 2. End-to-end gitsign tag signing on maintainer workstation
expected: `git config --get gitsign.connectorID` returns non-empty; `git tag -s vX.Y.Z-test -m "test"` opens browser for OAuth and creates a signed tag; `git verify-tag vX.Y.Z-test` exits 0
result: [pending]
why_human: Requires interactive OAuth flow in browser; cannot be unit-tested. See VALIDATION.md Manual-Only Verifications row 2.

### 3. `gh attestation verify` against a published release
expected: After v0.6.0-rc1 rehearsal, `gh attestation verify dist/horus_os-0.6.0rc1-py3-none-any.whl --repo Ridou/horus-os` exits 0 + identity line matches EXPECTED_IDENTITY (`https://github.com/Ridou/horus-os/.github/workflows/release.yml@refs/tags/v0.6.0-rc1`)
result: [pending]
why_human: Requires a published GitHub Release with attached attestations; cannot run pre-release. See VALIDATION.md Manual-Only Verifications row 3.

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
