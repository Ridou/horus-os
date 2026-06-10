---
title: "Maintainer runbook"
description: "How horus-os maintainers triage issues and pull requests, apply the label taxonomy, and cut a release."
---

## Overview

This page is for maintainers. It summarizes how the project handles the inbound queue (issues and pull requests), the label set used to route work, and the high-level release procedure. horus-os is a solo-maintained, open-source project that welcomes outside contributions, so the workflow is deliberately lightweight and honest about timelines.

The canonical, full-length versions of these procedures live in the repository:

- [docs/TRIAGE.md](https://github.com/Ridou/horus-os/blob/main/docs/TRIAGE.md)
- [docs/LABEL-TAXONOMY.md](https://github.com/Ridou/horus-os/blob/main/docs/LABEL-TAXONOMY.md)
- [docs/RELEASE.md](https://github.com/Ridou/horus-os/blob/main/docs/RELEASE.md)
- [docs/MAINTAINER-RUNBOOK.md](https://github.com/Ridou/horus-os/blob/main/docs/MAINTAINER-RUNBOOK.md)

If you are a contributor rather than a maintainer, start with [Contributing](/project/contributing/) instead.

## Triage

### Cadence

- **Weekly target.** The maintainer aims for one triage pass per week: review new issues, new pull requests, and updates on existing items.
- **May go quiet for up to two weeks.** During travel or deep work on an in-flight phase, a weekly pass can be skipped for up to two consecutive weeks. After that, a polite reminder comment on an item resurfaces it.
- **No 24-hour SLA.** The service-level objective is "aim to acknowledge within 7 days," not "respond within 24 hours."

### No auto-close

horus-os does not run any stale bot and does not auto-close issues after silence. An open issue means the maintainer has not closed it, and an aging issue is a real signal rather than a bot artifact.

> [!NOTE]
> Because there is no stale automation, the age of an issue is never a verdict on its importance. Old-but-real bugs stay open until they are fixed or explicitly closed.

### good-first-issue rubric

An issue qualifies for `good-first-issue` only when all of the following hold:

1. **Self-contained.** Fits in a single file or a small handful of files, with no cross-subsystem changes.
2. **Well-defined.** The acceptance criteria are unambiguous, so a contributor can know when they are done.
3. **Low-risk.** Worst-case revert is one commit. No release-pipeline impact, no security implications, no schema migrations.
4. **Has tests.** Either failing tests already exist, or the contributor is expected to add a test as part of the fix.
5. **Has a hint.** The issue body points to the relevant file or function.

Good examples: a docstring typo fix, a missing test for an existing feature, a small CLI usage-string improvement. Out of scope: anything in the agent runtime, anything requiring deep knowledge of the adapter contract, and anything that touches the CI workflows.

### Claim flow

With contributions open, the claim flow is:

1. A contributor comments that they would like to take an issue.
2. The maintainer reviews recent contribution history, applies the `claimed` label, and assigns the issue. Until assigned, the issue is not claimed.
3. The contributor opens a draft pull request within 7 days. If no draft appears, the `claimed` label is removed and the issue returns to the queue.

## Label taxonomy

The label set has a **hard cap of 15 labels**. Adding a 16th requires deprecating an existing label first. This intentional friction keeps the list grep-able for someone reading the project for the first time. The full per-label "when to apply" guidance and the saved-reply text live in [docs/LABEL-TAXONOMY.md](https://github.com/Ridou/horus-os/blob/main/docs/LABEL-TAXONOMY.md).

### Type labels

| Label | Meaning |
|-------|---------|
| `type:bug` | A defect in shipped code or shipped docs. |
| `type:feature` | A concrete proposal for new capability, scoped to the roadmap. |

### Area labels

| Label | Subsystem |
|-------|-----------|
| `area:adapters` | The adapter framework and built-in adapters (Discord, Slack, Email, Calendar, webhook, OTel). |
| `area:dashboard` | The FastAPI dashboard, its frontend, and the event stream. |
| `area:cli` | The `horus-os` CLI surface. |

### Workflow labels

| Label | Meaning |
|-------|---------|
| `accepted` | Triaged and confirmed in-scope. The maintainer intends to land it. |
| `claimed` | Assigned to a specific contributor. |
| `blocked` | Cannot proceed until an upstream dependency, related issue, or external decision lands. Always paired with an explanatory comment. |
| `needs-info` | Cannot reproduce or evaluate without more information. Always paired with a specific question. |
| `waiting-for-author` | The question has been asked and progress waits on the author's reply. |

### Outcome and special-purpose labels

| Label | Meaning |
|-------|---------|
| `wontfix` | Out of scope or intentional. Closed without a fix. |
| `good-first-issue` | Self-contained, well-defined, low-risk, with hints (see rubric above). |
| `help-wanted` | The maintainer can review but does not have hands free to implement. |
| `security-update` | Security-related, typically a CVE-bumping dependency PR. The routing signal for one PR per advisory. |
| `breaking` | A backwards-incompatible change. Requires a CHANGELOG entry, a migration note in the PR, and possibly a major version bump. |

### Adding a new label

Because of the hard cap, adding a label is a small process: open a `type:feature` issue against the taxonomy itself, argue which label retires and why the new one is sharper, and (if accepted) update `docs/LABEL-TAXONOMY.md`, `docs/TRIAGE.md`, and any issue or PR templates that name labels.

## Operational triggers

The maintainer pauses or slows the queue under defined conditions, communicated in the pinned project-status discussion.

- **Freeze (stop merging).** An active security incident, a red CI matrix on `main`, a release-gate failure that is not a known-and-tracked issue, or an extended period with no laptop access.
- **Throttle (slow intake).** When pull requests accumulate faster than they can be reviewed, new PRs are scope-checked first and only then labeled for review.
- **Break.** Sustained signs of maintainer burnout take precedence over external commitments; a multi-week break is announced, with no exceptions during the break except security incidents.

When deciding whether to invest review time in a borderline PR, the maintainer scores it on scope-fit (alignment with the current roadmap phase), contributor quality history, and review cost, and documents close decisions rather than carrying them as guilt.

## Release process

Every release follows the same sequence. The high-level shape is below; the full step-by-step procedure, including exact commands, lives in [docs/RELEASE.md](https://github.com/Ridou/horus-os/blob/main/docs/RELEASE.md). The released version notes are summarized in the [Changelog](/reference/changelog/).

### Pre-release checklist

1. Confirm CI is green on `main` for the latest commit across the full three-OS by two-Python matrix (Ubuntu, macOS, Windows on Python 3.11 and 3.12), including the install-smoke jobs.
2. Confirm there are no open pull requests that should merge before the tag.
3. Confirm all phase summaries for the milestone are committed.
4. Run the local release gate.

### Release gate

`scripts/release_gate.py` is a local pre-tag quality gate. It runs a set of checks and exits `0` only when all of them pass. It is a local check the maintainer runs before tagging; it does not run in CI. The checks include:

- **Pricing freshness.** The bundled `pricing.json` `updated_at` must be within 14 days of today.
- **Two-variant install smoke.** The CI workflow must still contain both the no-OTel and with-OTel install-smoke jobs, proving the `otel` extra is the only path into the OpenTelemetry SDK.
- **Wheel pricing bundle.** A wheel build must succeed and the wheel must contain the bundled `pricing.json`.
- **Tests.** `python -m pytest -q` from the repo root must exit `0`.
- **Docs drift, plugin install smoke, reference manifest validity, and a fixture round-trip** covering the plugin manifest schema and database migrations.

The runner prints one diagnostic per failing check rather than stopping at the first failure, so you see everything in one pass.

```bash
python scripts/release_gate.py
```

> [!TIP]
> If the pricing-freshness check fails, refresh `pricing.json` before re-running the gate. The refresh is a short mechanical task that compares the bundled Anthropic and Gemini rate cards against the upstream source and bumps the `updated_at` date.

### Release sequence

After the gate passes:

1. Refresh `pricing.json` if its `updated_at` is older than 14 days, and regenerate the bundled manifest JSON schema if it has drifted.
2. Run the release gate and confirm a full pass.
3. Bump the version in both `pyproject.toml` and `src/horus_os/__init__.py`.
4. Promote the `[Unreleased]` section in `CHANGELOG.md` to `[N.M.P] - YYYY-MM-DD` (Keep a Changelog format), and leave a fresh empty `[Unreleased]` stub on top.
5. Commit the version bump and CHANGELOG promotion with a `chore(release):` message.
6. Push to `main` and wait for CI green on the full matrix.
7. Create a signed annotated tag and push it.
8. Publish the GitHub Release with the new CHANGELOG section as the release notes, linking the migration note when one exists.
9. Confirm the release is visible on the repository releases page.

> [!IMPORTANT]
> Never push to a remote, tag, or publish a release without explicit owner confirmation. The push, tag, and release-publish steps are gated on a human go-ahead.

### Post-release

- Update the planning state to point at the next milestone and reflect the just-shipped progress.
- Open a tracking note for the next milestone's planning.

## See also

- [Contributing](/project/contributing/)
- [Security policy](/project/security-policy/)
- [Changelog](/reference/changelog/)
- [Roadmap](/project/roadmap/)
