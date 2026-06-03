---
status: partial
phase: 53-sbom-supply-chain-scan-substrate-audit-yml-new
source: [53-VERIFICATION.md]
started: 2026-05-30
updated: 2026-05-30
---

## Current Test

[awaiting human testing]

## Tests

### 1. Canonical SBOM bundle binary fixture recording (v0.6.0-rc1 rehearsal)
expected: tests/fixtures/sigstore/canonical/horus_os-clean.cdx.json + .sigstore.json AND horus_os-dev-otel.cdx.json + .sigstore.json committed; the currently-SKIPPED test_check_sbom_signature_two_bundles_verified flips GREEN.
result: [pending]
why_human: Requires a live release.yml run on a fork via gh release create. Same recording session as Phase 52 canonical wheel + sigstore fixture; one extra gh release download fetches the .cdx.json + .sigstore files alongside the wheel + bundle.

### 2. gh attestation verify against a published SBOM
expected: After v0.6.0-rc1 rehearsal, `gh attestation verify dist/horus_os-clean.cdx.json --repo Ridou/horus-os --predicate-type <CycloneDX or SPDX URI>` exits 0 + the attestation binds the SBOM to the wheel.
result: [pending]
why_human: Requires a published GitHub Release with attached SBOM attestations; cannot run pre-release. Resolve the exact predicate-type URI at rehearsal time (CycloneDX 1.6 maps to https://cyclonedx.org/bom/1.6 per the CycloneDX spec).

## Summary

Two new UAT items added by Phase 53 (both gated on v0.6.0-rc1 rehearsal). They compose cleanly with the three Phase 52 carry-forward items (canonical wheel + sigstore bundle recording; gitsign tag-signing workstation flow; gh attestation verify against the published wheel). All five UAT items should be exercised in a single rehearsal session and recorded together into the canonical fixture directory + Phase 58 verification log.
