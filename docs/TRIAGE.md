# Triage guide

This document defines how the maintainer triages issues and pull requests for `horus-os`. It exists so contributors and users see honest expectations: when the maintainer looks at the queue, how long things may sit, and what labels mean.

## Cadence

- **Weekly target:** Sunday triage pass. The maintainer reviews new issues, new PRs, and updates on existing items at least once per week.
- **May go silent up to 2 weeks.** If the maintainer is offline (travel, deep work on an in-flight phase), the Sunday triage may be skipped for up to two consecutive weeks. After two weeks of silence, ping the issue with a polite reminder; that ping resurfaces the item.
- **No 24-hour SLA.** horus-os is a solo-maintained project. The SLO is "aim to acknowledge within 7 days," not "respond within 24 hours."

## No auto-close

horus-os does NOT use `actions/stale` or any bot that auto-closes issues after silence. An issue staying open means the maintainer has not closed it; an aging issue is a real signal, not a bot artifact.

Rationale: `.planning/decisions/no-stale-bot.md`.

## Label taxonomy

We keep the label set to a hard cap of 15 labels. Adding a 16th requires deprecating an existing label first. See `docs/LABEL-TAXONOMY.md` for the saved-reply text per label and the "when to apply" rubric.

### Type labels (what kind of thing this is)

- `type:bug`: a defect in shipped code or docs.
- `type:feature`: a proposal for new capability.

### Area labels (which subsystem this touches)

- `area:adapters`: adapter framework, built-in adapters (Discord, Slack, Email, Calendar, webhook, OTel).
- `area:dashboard`: the FastAPI dashboard and its frontend.
- `area:cli`: the `horus-os` CLI surface.

### Workflow labels (where this is in the maintainer queue)

- `accepted`: triaged and confirmed in-scope; the maintainer intends to land a fix or feature.
- `claimed`: assigned to a specific contributor (post-gate-flip; pre-gate the maintainer assigns to self).
- `blocked`: cannot proceed until an upstream dep, a related issue, or an external decision lands.
- `needs-info`: cannot reproduce or evaluate without more information from the reporter.
- `waiting-for-author`: reporter or PR author needs to respond before progress.

### Outcome labels (terminal states)

- `wontfix`: out of scope or intentional. Closed without a fix.

### Special-purpose labels

- `good-first-issue`: small, well-defined, low-risk. See rubric below.
- `help-wanted`: maintainer has capacity to review but not to implement.
- `security-update`: a security-related issue or PR (typically Dependabot-driven; one PR per CVE).
- `breaking`: change is backwards-incompatible. Requires a CHANGELOG entry and may require a major version bump.

## good-first-issue rubric

An issue qualifies for `good-first-issue` if ALL of the following hold:

1. **Self-contained.** Fits in a single file or a small handful of files. No cross-subsystem changes.
2. **Well-defined.** The acceptance criteria are unambiguous; a contributor can know they are done.
3. **Low-risk.** Worst-case revert is one commit. No release-pipeline impact, no security implications, no schema migrations.
4. **Has tests.** Either tests already exist that fail because of the bug, or the contributor is expected to add a test as part of the fix.
5. **Has a hint.** The issue body includes a pointer to the relevant file or function so the contributor knows where to look.

Bad examples: anything in `src/horus_os/agent/` (runtime); anything that requires understanding the adapter contract; anything touching `.github/workflows/`.

Good examples: typo fix in a docstring; adding a missing test for an existing feature; small CLI usage-string improvement.

## Claim flow

Contributions opened on 2026-06-10 (the v0.6 gate flip). The claim flow is:

1. Comment on the issue: "I'd like to take this." The maintainer reviews recent contribution history and, for first-time contributors, may suggest a smaller intro task first.
2. Maintainer adds the `claimed` label and assigns the issue. Until assigned, the issue is not claimed.
3. The contributor opens a draft PR within 7 days. If the PR does not appear, the `claimed` label is removed and the issue returns to the queue.

An automation (`.github/workflows/issue-claim-watcher.yml`) acknowledges claim-style comments immediately so claimers learn the flow without waiting for the next triage pass.

## Saved replies

`docs/LABEL-TAXONOMY.md` lists the saved-reply text for the four most common scenarios: claim accepted, claim conflict, missing repro, stale-but-real bug.
