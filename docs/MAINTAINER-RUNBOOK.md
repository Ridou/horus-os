# Maintainer runbook

Single doc covering BOTH the release procedure AND the operational playbook for `horus-os`. Lives here instead of in `docs/RELEASE.md` because the operational content is broader than a single release.

For the v0.5 era step-by-step release sequence (pricing refresh, release gate, version bumps, CHANGELOG promotion, tag, GitHub Release), see `docs/RELEASE.md`. This runbook extends that doc with the Phase 52 + 53 substrate (release.yml runs, signed-tag procedure, SBOM attestations).

## Part 1: release procedure (v0.6+ substrate, used for v0.7.0 and v0.8.0)

The base procedure in `docs/RELEASE.md` Section "Release procedure" stays as-is for steps 1 through 6. The v0.6 hardening work inserted step 6.5, modified step 7, and added post-tag verification.

### Step 6.5: confirm gitsign is configured

Before tagging, verify gitsign has an active OIDC connector configured. Run:

```
git config --get gitsign.connectorID
```

Expect a non-empty value. If empty, follow the gitsign setup procedure:

1. `gitsign config --global` and walk through the OAuth flow once.
2. Re-run the `git config --get` check.

This step is single-time per workstation; the configuration persists.

### Step 7: signed tag (replaces `git tag -a`)

Where the v0.5 procedure said:

```
git tag -a vN.M.P -m "vN.M.P - <milestone-name>"
```

The v0.6 procedure says:

```
git tag -s vN.M.P -m "vN.M.P - <milestone-name>"
```

The `-s` flag invokes gitsign and produces a tag signed by the keyless OIDC certificate. Browser will open for OAuth on first use of the day; subsequent tags reuse the cached identity within the 10-minute certificate window.

Verify locally with:

```
git verify-tag vN.M.P
```

Exit 0 means the tag verifies cleanly.

### Step 8: push the tag, then push to origin

```
git push origin vN.M.P
git push origin main
```

### Step 9: publish the GitHub Release

```
gh release create vN.M.P --title "vN.M.P - <milestone-name>" --notes-file CHANGELOG-vN.M.P.md
```

Publishing the release fires the `release.yml` workflow (`on: release: types: [published]`). The workflow:

1. Builds the wheel + sdist via `python -m build`.
2. Generates two SBOMs (`dist/horus_os-clean.cdx.json` + `dist/horus_os-dev-otel.cdx.json`) against FRESH `pip install <wheel>` venvs.
3. Signs the wheel, sdist, and both SBOMs via `sigstore/gh-action-sigstore-python`.
4. Emits SLSA Build L2 provenance via two `actions/attest-build-provenance` invocations (wheel + sdist).
5. Emits SBOM attestations via two `actions/attest-sbom` invocations (clean + dev-otel).
6. The signing-artifacts are attached to the GitHub Release automatically.

### Step 10: verify the release end-to-end

After the workflow completes:

```
gh release view vN.M.P
```

Confirm the release page shows:

- `horus_os-X.Y.Z-py3-none-any.whl` + `.sigstore.json`
- `horus_os-X.Y.Z.tar.gz` + `.sigstore.json`
- `horus_os-clean.cdx.json` + `.sigstore.json`
- `horus_os-dev-otel.cdx.json` + `.sigstore.json`

Run the user-facing verifier locally:

```
python scripts/verify_release.py \
  --version X.Y.Z \
  --cert-oidc-issuer https://token.actions.githubusercontent.com \
  --check tag
```

Expect exit 0. Repeat with `--check wheel` and `--check sbom` after `gh release download` to verify the binary fixtures.

Run `gh attestation verify`:

```
gh attestation verify dist/horus_os-X.Y.Z-py3-none-any.whl --repo Ridou/horus-os
```

Expect exit 0 and the identity line matches `https://github.com/Ridou/horus-os/.github/workflows/release.yml@refs/tags/vX.Y.Z`.

## Part 2: post-flip operational playbook

Contributions are open (the v0.6 gate flipped on 2026-06-10). This section is the operational playbook for handling the queue.

### Freeze triggers

Pause merging incoming PRs entirely when ANY of:

- Active security incident in flight (vulnerability under embargo, fix in progress).
- CI matrix is red on `main` (any of Ubuntu, macOS, Windows on Python 3.11 or 3.12).
- Release-gate fails locally for any reason that is not a known-and-tracked issue.
- The maintainer is on the road for more than 5 consecutive days with no laptop access.

Resume only when the trigger is gone. Communicate the freeze in the pinned "Project Status" Discussion post.

### Throttle triggers

Below freeze, but enough load that PRs accumulate faster than they can be reviewed:

- More than 5 open external PRs awaiting first review for >7 days.
- More than 2 weeks of accumulated "weekly Sunday triage" backlog (see `docs/TRIAGE.md`).

Throttle by labeling new PRs `accepted` only after a first-pass scope check. Unlabelled PRs sit in a "received but not yet promised" pool. Communicate the throttle in the Discussion post.

### Burnout triggers

Self-care criteria that take precedence over external commitments:

- Two weeks of consecutive Sundays where triage was skipped because the maintainer was too drained to look at GitHub.
- The thought "I do not want to open this PR" for any specific PR three days in a row.
- Sustained drop in shipping cadence over a 6-week window without an external trigger (no vacation, no day job spike).

Action: announce a 4-week break in the Discussion post. No exceptions during the break except security incidents.

### "Is this PR worth my time?" decision matrix

For each PR, score along three axes (1-low, 3-high):

| Axis | Question | Score |
|------|----------|-------|
| Scope-fit | Does this align with the current `ROADMAP.md` phase? | 1-3 |
| Quality | Does the contributor's history show care (tests, focused PRs, responsive to review)? | 1-3 |
| Cost | Will this take more than 1 hour of my time to review and merge? | 1 high cost, 3 low cost |

Sum: 7-9 = take it. 4-6 = ask for changes first; if the contributor lands the changes, take it. 3 or lower = close with a polite explanation and a pointer to the closest accepted-shape issue.

The matrix exists so close decisions are documented in the maintainer's notes, not lived as guilt. Iterate the matrix as data accumulates.

## Part 3: one-time repo settings checklist

See `docs/RELEASE.md` "One-time repo settings checklist (contribution-gate setup)" for the canonical list with `gh api` verification commands.

This runbook references the checklist by pointer because the release procedure is the canonical place the maintainer reads when shipping; repeating the checklist here would create drift.

## Part 4: GitHub Discussions

Enable via:

```
gh api -X PATCH /repos/Ridou/horus-os --field has_discussions=true
```

Configure these categories via the Discussions UI:

- **General**: catch-all conversation. Default for anyone unsure where their post fits.
- **Q&A**: question-with-marked-answer format. Best for "how do I X" with concrete answers.
- **Show and Tell**: user-built things on top of horus-os. Show-don't-tell shape.
- **Ideas**: future-direction proposals that are not yet concrete enough for an issue. Issues belong in the issue tracker; ideas live here while the shape is still negotiable.

The pinned "Project Status" Discussion post lives in Announcements with the title "Project Status (pinned)"; the body mirrors `.github/DISCUSSION_STATUS_POST.md` and gets a reply whenever `STATUS.md` changes.

## Part 5: rollback procedure

If the v0.6.0 atomic gate flip ever needs to be backed out (CI regression, contributor-facing copy bug, anything the maintainer wants to walk back inside 24 hours of the flip), apply the template at `.planning/rollback/flip-gate-revert.md`.

That template restores the pre-flip prose: NOTICE block in PR template, "Status: not currently accepting" in CONTRIBUTING.md, "(not active yet)" in SECURITY.md, etc. It is a single commit revert designed to be `git apply`-tested against a stale working tree.
