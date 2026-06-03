# Project Status, v0.6.0 (Contribution Gate, OPEN)

Pinned discussion for the v0.6.0 release. This is the canonical
"what's the state of horus-os today" post; subscribe (or click the
bell at the top of this thread) to get forward-looking updates
without a commit.

## TL;DR

- **v0.6.0 shipped** (`v0.6.0` tag, GitHub Release published).
- **Outside contributions are OPEN** as of today. PRs from forks
  are reviewed per the documented flow in `CONTRIBUTING.md`.
- First-time contributors require explicit "Approve and run"
  before CI runs (branch-protection setting).
- Released artifacts are sigstore-signed and SBOM-attested. See
  `scripts/verify_release.py --help` for the verification script
  shipped in this release.

## What v0.6 ships

The "Contribution Gate" milestone is the 9-phase contribution-
readiness effort that ran from Phase 51 through Phase 59. Headlines:

- **Sigstore-signed release artifacts.** Wheel + sdist + two
  CycloneDX 1.6 JSON SBOMs (clean + dev-otel) all signed by
  `sigstore/gh-action-sigstore-python` under the workflow-scoped
  exact-match identity `https://github.com/Ridou/horus-os/.github/workflows/release.yml@refs/tags/v0.6.0`.
  Bundles upload to the GitHub Release page automatically.
- **SLSA Build L2 provenance.** Two `actions/attest-build-provenance`
  invocations bind 1:1 to the wheel + sdist.
- **SBOM attestations.** Two `actions/attest-sbom` invocations
  bind the two SBOMs to the wheel.
- **User-facing trust-chain verifier.** `scripts/verify_release.py`
  runs five checks: wheel-signature, sdist-signature, tag-signature,
  sbom-signature, changelog-cross-ref. Pure stdlib; no base-dep
  changes.
- **PR-time supply-chain scan.** `audit.yml` runs pip-audit
  (osv + pypi) and `dependency-review-action` license enforcement
  on every PR.
- **Dependabot v2.** Weekly cadence, four version-update groups,
  ungrouped security updates (every CVE gets its own PR).
- **Contributor docs + templates.** Updated CONTRIBUTING flow,
  TRIAGE guide, LABEL-TAXONOMY (15-label hard cap), path-scoped
  CODEOWNERS, three issue templates, five decision files.
- **SECURITY refresh.** Severity-tier SLOs (Critical 14d, High
  30d, Medium 90d, Low none). Over-capacity escalation path.
- **Maintainer runbook.** `docs/MAINTAINER-RUNBOOK.md` extends
  `docs/RELEASE.md` with the signed-tag procedure, one-time repo
  settings, and the `accepted-for-review` 30-day throttle for
  post-flip PR queue management.
- **Release-gate extended to 14 checks.** Two-tier execution model:
  `--tier local` (under 10s, grep-only) vs `--tier release` (full
  network + scan). `--allow-offline` short-circuits network checks
  to SKIP.

Full release notes: see [CHANGELOG.md](https://github.com/Ridou/horus-os/blob/main/CHANGELOG.md) `[0.6.0]` section.

## How to follow along

- **Watch the repo** on GitHub. Releases and Discussions surface
  in your notifications.
- **Subscribe to this thread** for forward-looking project-status
  updates without a commit.
- **Read STATUS.md** for the live "what's shipped, what's active"
  view.

## How to contribute

`CONTRIBUTING.md` documents the flow. Highlights:

1. Pick a `good-first-issue` or `help-wanted` issue and comment to
   claim. Maintainer assigns. Open a draft PR within 7 days.
2. CI (Ubuntu, macOS, Windows on Python 3.11 and 3.12) plus the
   install-smoke matrix and supply-chain scan must pass.
3. Path-scoped reviewers per `.github/CODEOWNERS`. Workflow and
   release-script changes require the maintainer.
4. No auto-merge. Maintainer hits the button after review-pass
   and CI-green.

For triage cadence and label rubric, read `docs/TRIAGE.md`.

## SLOs and honest expectations

- Aim to acknowledge issues within 7 days. No 24-hour SLA.
- Weekly Sunday triage is the target cadence. The queue may go
  silent up to 2 weeks (travel or deep work); after 2 weeks, a
  polite ping resurfaces the item.
- Severity-tier disclosure SLOs are documented in `SECURITY.md`.

## What is next

The roadmap for v0.7 and beyond lives in `.planning/ROADMAP.md`.
The forward direction will be discussed in this thread as it solidifies.
