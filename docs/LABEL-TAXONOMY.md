# Label taxonomy

The complete `horus-os` label set with definitions, "when to apply" guidance, and saved-reply text. The hard cap is 15 labels; the list below is the full set.

See `docs/TRIAGE.md` for the broader triage cadence and the `good-first-issue` rubric.

## Labels

### `type:bug`
A defect in shipped code or shipped docs. Use when the project is doing something other than what it documented. Do NOT use for "this design is wrong" complaints (that is `type:feature` with a discussion-first hint).

### `type:feature`
Proposal for new capability or behavior. Includes "this feature exists but should also do X." Open-ended design discussion belongs in GitHub Discussions; this label is for concrete proposals scoped to the roadmap.

### `area:adapters`
The adapter framework or any built-in adapter (Discord, Slack, Email, Calendar, webhook, OTel). Applies whether the change is to the adapter API or to a single adapter implementation.

### `area:dashboard`
The FastAPI dashboard server, its static frontend, the SSE event stream, or the dashboard test surface.

### `area:cli`
The `horus-os` CLI surface (subcommands, argparse, init wizard, usage output).

### `accepted`
Triaged and confirmed in-scope. The maintainer intends to land a fix or feature for this. Adding `accepted` is the maintainer's commitment; do not add this label until that commitment is honest.

### `claimed`
Assigned to a specific contributor. The maintainer adds this label when accepting a claim; until it lands, the issue is not reserved. Removed if no draft PR appears within 7 days.

### `blocked`
Cannot proceed until something else lands. Always paired with a comment explaining the block (an upstream issue link, a related horus-os issue number, or a date / external event the block resolves on).

### `needs-info`
The maintainer or a contributor cannot reproduce or evaluate without more information from the reporter. Always paired with a specific question.

### `waiting-for-author`
The reporter or PR author needs to respond before progress. Different from `needs-info` in that the question has been asked and we are waiting; `needs-info` is the moment the question goes out.

### `wontfix`
Out of scope or intentional. Closed without a fix. The closing comment must explain why and link the relevant decision file in `.planning/decisions/` when one exists.

### `good-first-issue`
Self-contained, well-defined, low-risk, with hints. See the rubric in `docs/TRIAGE.md`.

### `help-wanted`
The maintainer has capacity to review but not to implement. Typically a `type:feature` or a non-trivial `type:bug` where the maintainer agrees with the proposed approach but does not have hands free.

### `security-update`
Security-related. Typically applied automatically by Dependabot for CVE-bumping PRs (Phase 54 DEPBOT-02 ensures one PR per CVE; this label is the routing signal). Manual application for security-related bug reports is also fine; coordinate with `SECURITY.md` private disclosure flow if the issue is not yet public.

### `breaking`
Backwards-incompatible change. Requires a CHANGELOG `[Unreleased]` entry and may require a major version bump. Always paired with a migration note in the PR description.

## Saved replies

The maintainer keeps these as GitHub saved replies. The text is documented here so the prose stays consistent.

### Claim accepted (post-flip)

```
Thanks for offering. Adding the `claimed` label and assigning to you. Open
a draft PR within 7 days so I can see the shape; if the PR does not appear
by then I will reopen for re-claim. Holler in the issue if you hit a wall.
```

### Claim conflict (post-flip; two contributors want the same issue)

```
Thanks. This was already claimed by @<other-contributor>. Holding the
claim there for the standard 7-day window. If they do not open a draft PR
in that window I will reopen this comment and assign to you. In the
meantime, the `good-first-issue` label on other open items is a good
place to look.
```

### Missing repro (bug report lacks reproduction steps)

```
Thanks for the report. I cannot reproduce from the current description;
adding `needs-info`. To make this actionable, please add:

1. The exact `horus-os` version you are running (`pip show horus-os | grep Version`).
2. The exact command(s) you ran, including the working directory and any
   relevant env vars.
3. The full traceback or error output.

When you reply with those, I will remove `needs-info` and triage.
```

### Stale-but-real bug (issue is old but the maintainer agrees it is still a bug)

```
This is still a real bug. We do not use stale-close automation
(.planning/decisions/no-stale-bot.md), so the age of this issue is not a
verdict on its importance. Adding `accepted` and marking for a future
phase. If you (or anyone reading this) want to take a shot, the file to
start with is `<path/to/relevant/file.py>`.
```

## Adding a new label

Hard cap: 15. Adding a 16th requires deprecating an existing label first. Process:

1. Open an issue tagged `type:feature` (yes, applied to the taxonomy itself).
2. Argue the case: what label gets retired, why the new one is sharper, and what saved-reply text accompanies it.
3. If accepted, update this file AND `docs/TRIAGE.md` AND any issue/PR templates that name labels by hard-coded name.
4. Re-label existing issues that carry the retired label.

This intentional friction keeps the label list grep-able by a contributor reading the project for the first time.
