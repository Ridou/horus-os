<!--
Maintainer-facing file. Not rendered on GitHub for visitors except
those who navigate here directly. Holds canned responses for the
maintainer to paste into comments without having to retype the
same thing.

Each reply is wrapped in a fenced code block so it copies cleanly
without the surrounding context.

Tone target: dev-to-dev, direct, honest, no corporate fluff. Each
reply links to the doc that holds the relevant policy so the
recipient has one URL to internalize.

The first four replies are also documented in
docs/LABEL-TAXONOMY.md; keep the text in sync when editing.
-->

# Saved replies

## Reply 1: claim accepted

Paste in response to "I'd like to take this" when assigning the
issue.

```
Thanks for offering. Adding the `claimed` label and assigning to you. Open
a draft PR within 7 days so I can see the shape; if the PR does not appear
by then I will reopen for re-claim. Holler in the issue if you hit a wall.
```

## Reply 2: claim conflict (two contributors want the same issue)

```
Thanks. This was already claimed by @<other-contributor>. Holding the
claim there for the standard 7-day window. If they do not open a draft PR
in that window I will reopen this comment and assign to you. In the
meantime, the `good-first-issue` label on other open items is a good
place to look.
```

## Reply 3: missing repro (bug report lacks reproduction steps)

```
Thanks for the report. I cannot reproduce from the current description;
adding `needs-info`. To make this actionable, please add:

1. The exact `horus-os` version you are running (`pip show horus-os | grep Version`).
2. The exact command(s) you ran, including the working directory and any
   relevant env vars.
3. The full traceback or error output.

When you reply with those, I will remove `needs-info` and triage.
```

## Reply 4: stale-but-real bug

```
This is still a real bug. We do not use stale-close automation
(.planning/decisions/no-stale-bot.md), so the age of this issue is not a
verdict on its importance. Adding `accepted` and marking for a future
phase. If you (or anyone reading this) want to take a shot, the file to
start with is `<path/to/relevant/file.py>`.
```

## Reply 5: PR arrived without an assigned issue

Paste on a fork PR that did not go through the claim flow. Not an
auto-close; a routing nudge.

```
Thanks for the PR. The flow here starts from an issue: substantial
changes should have an issue first, and claims are assigned before
the PR lands (see
https://github.com/Ridou/horus-os/blob/main/CONTRIBUTING.md).

If an open issue covers this change, link it and I will treat this
PR as the claim. If no issue exists, open one (or a Discussion if
the scope is fuzzy) so the decision survives outside the PR. Small,
obvious fixes (typos, doc corrections) are fine without an issue;
for those, ignore this nudge and I will review as-is.
```

## Reply 6: scope-expansion proposal as a PR

Paste when a PR proposes new direction rather than fitting a
tracked phase.

```
The change is interesting but it expands the project's scope past
what's in PROJECT.md and ROADMAP.md. Scope changes go through a
Discussion first, then a roadmap update, then code. Reversing the
order doesn't fit the workflow described in CONTRIBUTING.md.

Closing this for now. Please open a Discussion describing the
problem you're trying to solve and what shape you have in mind;
that's the right entry point.
```

## Reply 7: low-effort or AI-generated PR

Paste when the PR looks generated and the author hasn't engaged
with the codebase.

```
This PR looks generated without a real engagement with the
codebase. Closing without a full review.

If I'm wrong about how this PR was produced, I apologize for the
canned reply. The signal I'm looking for before re-opening a
review: claim an issue first (see CONTRIBUTING.md), and describe in
the issue what files you plan to touch and why. That conversation
is the intro path.
```

## Reply 8: polite ping when an issue is going stale

Paste when an issue has open follow-ups from the reporter and the
maintainer wants to bump it without forcing a status check.

```
Bumping this one. horus-os is solo-maintained and triage runs on a
weekly cadence (see docs/TRIAGE.md). If the bug still reproduces on
the latest release, a fresh log paste helps; if it doesn't, feel
free to close.
```
