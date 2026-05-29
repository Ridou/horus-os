# Canonical sigstore fixtures for verify_release.py

This directory holds the pre-recorded sigstore artifacts that
`tests/test_release_verification.py` consumes when exercising the
`scripts/verify_release.py` 5-check trust-chain verifier (SIGN-04).
The fixture is recorded ONCE per major release-substrate change
during the v0.6.0-rc1 release rehearsal on a maintainer fork, per
PITFALL 11 release-rehearsal discipline. The binary fixture files
are NOT committed by Phase 52 Plan 01; only this README.md
placeholder ships now. The binaries land at recording time per
VALIDATION.md Manual-Only Verifications row 1.

## Files in this directory

Once recorded, this directory will hold:

- `horus_os-0.6.0rc1-py3-none-any.whl` (or the equivalent
  wheel name produced by `python -m build` against the
  `v0.6.0-rc1` tag).
- `horus_os-0.6.0rc1-py3-none-any.whl.sigstore` OR
  `horus_os-0.6.0rc1-py3-none-any.whl.sigstore.json`. The bundle
  suffix depends on the sigstore-python action version at recording
  time. Sigstore-python 3.x ships the `.sigstore.json` form by
  default; 2.x shipped `.sigstore`. The maintainer pins the observed
  suffix in the `## Observed bundle filename suffix` section below
  after the rehearsal completes.

The wrong-identity negative-test sibling lives at
`tests/fixtures/sigstore/wrong_identity/` and is owned by Phase 58
(TEST-24); that directory follows the same filename convention.

## Recording procedure (v0.6.0-rc1 rehearsal)

These seven steps are transcribed verbatim from VALIDATION.md
"Manual-Only Verifications" row 1. They double as the PITFALL 11
release-rehearsal procedure (the artifact this directory holds IS
the rehearsal output).

1. On a fork (e.g. `your-fork-name/horus-os`), configure `gitsign`.
   Run the four `git config` commands from
   `docs/MAINTAINER-RUNBOOK.md` (Phase 56 lands the runbook
   content; pre-Phase-56 reference is the upstream gitsign README).
2. Push the `v0.6.0-rc1` tag.
3. Run `gh release create v0.6.0-rc1 --prerelease` on the fork.
4. Wait for `release.yml` to complete. Verify the GitHub Release
   page shows the wheel artifact plus its `.sigstore` (or
   `.sigstore.json`) bundle attached automatically by
   `release-signing-artifacts: true`.
5. Download the artifacts into this directory:
   `gh release download v0.6.0-rc1 -D tests/fixtures/sigstore/canonical/`.
6. Update this README's `## Observed bundle filename suffix`
   section with the recording date plus whichever of the two
   suffixes the bundle file uses.
7. Commit the binary fixtures plus the README update with a
   message like
   `test(58): record canonical sigstore fixture from v0.6.0-rc1 rehearsal`.

## Why committed instead of generated

The fixture is checked in rather than re-recorded at test time
because:

- Live signing in CI test setup would require `id-token: write`
  in the test runner. That permission expands the contribution-gate
  attack surface and is forbidden by CIHARD-02 per-job permission
  discipline. The only job in this repository that holds
  `id-token: write` is the `sign-and-attest` job inside
  `.github/workflows/release.yml`; the test matrix never holds it.
- Pre-recorded bundles are the canonical sigstore-python testing
  pattern; the upstream sigstore-python test suite uses the same
  approach.
- The committed fixture also serves as the durable artifact of the
  PITFALL 11 release-rehearsal discipline. Each major substrate
  change re-runs the rehearsal and re-commits this fixture.
- Mirrors the pattern set by
  `tests/fixtures/v0_4_database.sqlite3` and
  `tests/fixtures/manifests/manifest_v1_full.toml` (both committed
  fixtures consumed by hermetic tests; both produced by a one-time
  build script and pinned for deterministic test runs).

## Observed bundle filename suffix

**Status:** PENDING (filled in at v0.6.0-rc1 rehearsal recording
time).

Two possible values depending on the recording-time
sigstore-python action version:

- `.sigstore.json` (sigstore-python 3.x default; documented as
  Sigstore Bundle Format v0.3).
- `.sigstore` (sigstore-python 2.x default; legacy form).

The maintainer records the observed suffix on step 6 of the
recording procedure above. `tests/test_release_verification.py`
already probes for both suffixes via
`_canonical_fixture_paths()`; whichever is present is loaded.

## Phase 58 sibling: tests/fixtures/sigstore/wrong_identity/

Phase 58 (TEST-24) creates a sibling directory at
`tests/fixtures/sigstore/wrong_identity/` containing a recorded
sigstore bundle whose embedded identity does NOT match
`EXPECTED_IDENTITY_TEMPLATE` (for example, a bundle from
`your-fork-name/horus-os/.github/workflows/release.yml@refs/tags/0.6.0-rc1`
rather than `Ridou/horus-os/...`). The sibling fixture uses the
same filename convention as this directory so the test harness can
iterate over both with identical glob patterns. The wrong-identity
fixture proves the verifier REJECTS a signature attributable to
the wrong workflow path, even when issuer and tag match.
