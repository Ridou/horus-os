# Wrong-identity sigstore fixture (Phase 58 TEST-24 negative case)

This directory holds a HAND-CRAFTED sigstore bundle stub used to
exercise the negative-test branch of `scripts/verify_release.py`. The
bundle is NOT produced by `sigstore/gh-action-sigstore-python`; it
is a synthetic JSON file whose certificate metadata names a different
repository (`Other/repo`) than the workflow-scoped identity pinned in
`scripts/verify_release.py::EXPECTED_IDENTITY_TEMPLATE`
(`Ridou/horus-os`).

## Why hand-crafted?

The autonomous build environment cannot exchange a GitHub OIDC token
for a Fulcio certificate (no `id-token: write`, no browser OAuth).
Producing a real-but-wrong sigstore bundle from a different fork
requires a live rehearsal session on that fork. The HAND-CRAFTED stub
is sufficient for the test class that asserts "the verifier rejects
identity mismatch BEFORE attempting cryptographic verification"
because the identity check is the EARLIEST failure mode and triggers
on certificate metadata, not on a valid signature.

The CANONICAL positive-case fixture (recorded from a real release.yml
run on a fork) is documented in `tests/fixtures/sigstore/canonical/`
and lands at v0.6.0-rc1 release-rehearsal time (Phase 58 human UAT).
The full positive-AND-negative end-to-end round-trip through the real
`python -m sigstore verify identity` CLI requires BOTH fixtures.

## Files in this directory

- `README.md` (this file).
- `wrong-identity-bundle.sigstore.json`: minimal stub with
  `verificationMaterial.certificate.subject` carrying a non-Ridou
  identity URL. The bundle is internally valid JSON but is NOT
  cryptographically valid (the signature bytes are placeholder).
  Sufficient for parsing-level identity-mismatch assertions; will
  FAIL `python -m sigstore verify identity` for the trivial reason
  that the signature does not actually verify, but that is the
  correct behavior the test asserts.

## What this fixture proves

When `scripts/verify_release.py --check wheel` (which performs
identity verification as part of its sigstore-verify shell-out) is
invoked against this fixture:

1. The verifier's expected identity is the byte-exact
   `https://github.com/Ridou/horus-os/.github/workflows/release.yml@refs/tags/v<version>`.
2. The bundle's certificate subject is
   `https://github.com/Other/repo/.github/workflows/release.yml@refs/tags/v0.6.0`.
3. The sigstore-python CLI exits non-zero with an identity-mismatch
   diagnostic (or a signature-invalid diagnostic when the signature
   bytes are placeholder; either failure mode is acceptable).

The test asserts exit code != 0. The structural assertion is "the
verifier did not green-light the wrong identity."

## Lifecycle

This stub is sufficient for v0.6 launch. At the v0.6.0-rc1
release-rehearsal session, the maintainer SHOULD replace the stub
with a real bundle recorded from a different fork (e.g., the
maintainer's personal `your-fork-name/horus-os` repo signing under
its own workflow path). The replacement gives the negative test
genuine cryptographic teeth, not just parser teeth.

Until that replacement happens, the test against this fixture is
marked `pytest.mark.skipif(not sigstore_cli_available)` so the test
suite stays green on machines without sigstore-python installed.
