# Phase 59 publish guide: apply the flip, sign the tag, ship v0.6.0

This document is the rehearsal-day command sequence for landing the v0.6.0
release on `Ridou/horus-os`. The single atomic flip commit lives as a patch
file at `.planning/phase-59-flip.patch` (drafted by the autonomous run; NOT
applied yet). This guide walks the maintainer through applying the patch,
signing the tag, publishing the release, creating the pinned discussion, and
the rollback path if anything goes wrong.

**ALL of these steps require live human OAuth (gitsign) and a live GitHub
repo configuration. Run only when you are ready to actually flip the gate.**

---

## Pre-flight check

Before doing anything irreversible, verify the patch applies cleanly and the
working tree is on a known-good commit:

```bash
git checkout main
git status --short                            # must be empty
git apply --check .planning/phase-59-flip.patch   # must exit 0
```

If `--check` fails, the working tree has diverged from the snapshot the
patch was generated against. Resolve before continuing.

Also run the full test suite and the release-gate locally:

```bash
pytest tests/ -x                              # all tests green
python scripts/release_gate.py --tier release # all 14 checks green
```

Confirm the v0.6.0-rc1 rehearsal session completed successfully and the
canonical sigstore fixtures landed under `tests/fixtures/sigstore/canonical/`.

---

## Step 1: Apply the flip patch

```bash
git apply .planning/phase-59-flip.patch
git add -A
git status --short                            # confirm expected diff
```

Expected diff: 10 files changed (8 modified + 1 added section in CHANGELOG +
1 deleted workflow).

Now manually update the CHANGELOG date placeholder. The patch promotes
`[Unreleased]` to `[0.6.0] - 2026-05-30` (the date this patch was drafted).
Replace `2026-05-30` with today's actual flip date in CHANGELOG.md.

```bash
# Manual edit: find/replace `[0.6.0] - 2026-05-30` to `[0.6.0] - $(date +%Y-%m-%d)`
# Or, on macOS / Linux:
TODAY=$(date +%Y-%m-%d)
sed -i.bak "s/\[0.6.0\] - 2026-05-30/[0.6.0] - ${TODAY}/" CHANGELOG.md
rm CHANGELOG.md.bak
```

Same edit on STATUS.md's "Last updated:" line and on the milestone-table date
column if today is not 2026-05-30.

---

## Step 2: Commit the atomic flip

The commit message subject is under 70 chars; the body references every
requirement satisfied (FLIP-01, FLIP-03, REL-13, DISCGH-02).

```bash
git commit -m "feat(59): flip gate, open horus-os to outside contributions (v0.6.0)" \
  -m "$(cat <<'EOF'
The contribution gate flips OPEN. STATUS.md, README.md, CONTRIBUTING.md,
SECURITY.md, the PR template, and the bug + feature + security issue
templates all updated to the post-flip state. The issue-claim-watcher.yml
workflow is removed (no longer needed; claims are honored per the
documented flow in docs/TRIAGE.md). CHANGELOG promotes [Unreleased] to
[0.6.0].

Closes FLIP-01 (single atomic flip commit, no half-flip state).
Closes FLIP-03 (accepted-for-review 30-day throttle documented in
MAINTAINER-RUNBOOK).
Closes REL-13 (CHANGELOG promoted on the same commit as the flip).
Closes DISCGH-02 (pinned Project Status discussion documented as
post-tag procedure; see .planning/discussion-status-v0.6.md).

The 14-check release-gate is green; the pitfall regression suite at
tests/test_contribution_gate_pitfalls/ has 49 tests covering the 12
PITFALLS.md regressions; sigstore-signed release artifacts (wheel +
sdist + 2 SBOMs) and SLSA Build L2 provenance ship via release.yml on
the v0.6.0 tag push.
EOF
)"
```

---

## Step 3: Sign the tag (gitsign + browser OAuth)

```bash
# Confirm gitsign is configured (see MAINTAINER-RUNBOOK Step 6.5)
git config --get gitsign.connectorID         # must be non-empty

# Sign the tag (opens browser for OAuth on first use of the day)
git tag -s v0.6.0 -m "v0.6.0, Contribution Gate"

# Verify the signature locally
git verify-tag v0.6.0                        # must exit 0
```

If `git verify-tag` exits non-zero, do NOT push. Rerun the gitsign config
procedure in `docs/MAINTAINER-RUNBOOK.md` Step 6.5.

---

## Step 4: Push (the irreversible step)

```bash
git push origin main
git push origin v0.6.0
```

After the push, the `release.yml` workflow fires automatically on the
`release: published` event (after Step 5 creates the Release). It builds
the wheel + sdist, generates two SBOMs against fresh venvs, signs all four
artifacts via sigstore-python, emits SLSA Build L2 provenance, and uploads
everything to the Release page.

---

## Step 5: Publish the GitHub Release

```bash
gh release create v0.6.0 \
  --title "v0.6.0, Contribution Gate" \
  --notes-file <(awk '/^## \[0.6.0\]/{flag=1; next} /^## \[/{flag=0} flag' CHANGELOG.md)
```

This fires `release.yml`. Monitor the run:

```bash
gh run watch                                 # interactive; pick the release.yml run
```

The workflow takes about 3-5 minutes. When it completes, verify the
release page has all 7 expected assets:

```bash
gh release view v0.6.0 --json assets --jq '.assets[].name'
```

Expected output (the four sigstore bundles use `.sigstore.json` per
sigstore-python 3.x):

```
horus_os-0.6.0-py3-none-any.whl
horus_os-0.6.0-py3-none-any.whl.sigstore.json
horus_os-0.6.0.tar.gz
horus_os-0.6.0.tar.gz.sigstore.json
horus_os-clean.cdx.json
horus_os-clean.cdx.json.sigstore.json
horus_os-dev-otel.cdx.json
horus_os-dev-otel.cdx.json.sigstore.json
```

That is 8 assets (4 artifacts + 4 sigstore bundles).

---

## Step 6: Verify the trust chain end-to-end

```bash
# Sigstore identity check (downloads the wheel + bundle, runs the verifier)
mkdir -p /tmp/v0.6.0-verify
gh release download v0.6.0 -D /tmp/v0.6.0-verify
python scripts/verify_release.py \
  --version 0.6.0 \
  --cert-oidc-issuer https://token.actions.githubusercontent.com \
  --check wheel \
  --bundle /tmp/v0.6.0-verify/horus_os-0.6.0-py3-none-any.whl.sigstore.json \
  --artifact /tmp/v0.6.0-verify/horus_os-0.6.0-py3-none-any.whl
# Expect: OK wheel-signature ...

python scripts/verify_release.py \
  --version 0.6.0 \
  --cert-oidc-issuer https://token.actions.githubusercontent.com \
  --check tag
# Expect: OK tag-signature ...

# SLSA attestation verification (PEP 740 path)
gh attestation verify /tmp/v0.6.0-verify/horus_os-0.6.0-py3-none-any.whl --repo Ridou/horus-os
gh attestation verify /tmp/v0.6.0-verify/horus_os-clean.cdx.json --repo Ridou/horus-os
```

All three must exit 0.

---

## Step 7: Create the pinned Project Status Discussion (DISCGH-02)

```bash
gh discussion create \
  --repo Ridou/horus-os \
  --category General \
  --title "Project Status, v0.6.0 (Contribution Gate)" \
  --body-file .planning/discussion-status-v0.6.md
```

Note the discussion number from the output, then pin it:

```bash
DISCUSSION_NUMBER=<from above>
gh api -X POST /repos/Ridou/horus-os/discussions/${DISCUSSION_NUMBER}/pin
```

(The pin API may not exist in `gh` 2.x; if not, pin via the Discussions UI.)

---

## Step 8: Announce + celebrate

The gate is open. Tweet, blog, post to relevant communities. The pinned
discussion is the canonical "where to follow along" link.

---

## Rollback path

If anything goes wrong post-flip, the rollback template at
`.planning/rollback/flip-gate-revert.md` documents three methods:

### Method 1: git revert (preferred, history-preserving)

```bash
FLIP_SHA=$(git log --oneline --grep="^feat(59):" -1 --format=%H)
git revert --no-edit "${FLIP_SHA}"
git push origin main
```

### Method 2: tag deletion (irreversible side-effect of force-push)

```bash
# Delete the remote tag
git push origin :refs/tags/v0.6.0
# Delete the local tag
git tag -d v0.6.0
# Delete the GitHub Release (this also removes the published assets)
gh release delete v0.6.0 --yes
```

### Method 3: hard reset (DESTRUCTIVE, coordinate first)

Only if the flip commit was pushed less than 30 minutes ago AND no
downstream contributors have pulled yet. See the rollback template for
full details and warnings.

Post-rollback steps (announce on the pinned discussion, open a tracking
issue, update STATE.md) are documented in
`.planning/rollback/flip-gate-revert.md` lines 75-100.

---

## What the maintainer must verify before pushing v0.6.0

A checklist before Step 3 (signing the tag):

- [ ] `git apply --check .planning/phase-59-flip.patch` exits 0.
- [ ] `pytest tests/ -x` is green.
- [ ] `python scripts/release_gate.py --tier release` is green (all 14 checks).
- [ ] The v0.6.0-rc1 rehearsal has been completed and the canonical
      sigstore fixtures landed.
- [ ] One-time GitHub repo settings done (see MAINTAINER-RUNBOOK):
  - [ ] private vulnerability reporting enabled
  - [ ] Dependabot alerts + security updates enabled
  - [ ] secret scanning + push protection enabled
  - [ ] Discussions enabled with 4 categories (General, Q&A, Show and Tell, Ideas)
  - [ ] branch protection: "Require approval for first-time contributors" set
- [ ] gitsign configured on the workstation (`git config --get gitsign.connectorID` non-empty).
- [ ] CHANGELOG.md date placeholder substituted with today's date.
- [ ] STATUS.md "Last updated" date substituted with today's date.

When all checks pass, proceed to Step 3.
