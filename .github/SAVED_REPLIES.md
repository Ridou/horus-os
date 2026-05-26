<!--
Maintainer-facing file. Not rendered on GitHub for visitors except
those who navigate here directly. Holds canned responses for the
maintainer to paste into comments without having to retype the
same thing.

Each reply is wrapped in a fenced code block so it copies cleanly
without the surrounding context.

Tone target: dev-to-dev, direct, honest, no corporate fluff. Each
reply links to STATUS.md so the recipient has one URL to
internalize.
-->

# Saved replies

## Reply 1: someone claimed an issue

Paste in response to comments like "I'll take this", "on it",
"claim this", "assign to me", "working on this".

```
Thanks for the offer, but the repo isn't accepting issue claims
right now. horus-os is in solo development mode and the
maintainer holds the queue. See
https://github.com/Ridou/horus-os/blob/main/STATUS.md for the
timeline and the gate for when that changes (private PR-review
pipeline; earliest v0.6, not promised).

If you want to make a real dent today, run horus-os against a
real workload and write up what worked and what didn't in
Discussions. That feedback shapes the roadmap.
```

## Reply 2: a PR from a fork arrived

Paste before closing a fork PR that wasn't pre-coordinated.

```
Thanks for the contribution, but this repo isn't currently
accepting outside PRs. The reasons and the gate condition are
in https://github.com/Ridou/horus-os/blob/main/STATUS.md.

Closing the PR. The branch on your fork still has your work;
nothing is lost. If the underlying issue is one I haven't
tracked yet, please open it as an issue or a Discussion so the
idea survives outside of a closed PR.
```

## Reply 3: scope-expansion proposal as a PR

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

For the current project status and the gate for outside
contributions, see
https://github.com/Ridou/horus-os/blob/main/STATUS.md.
```

## Reply 4: low-effort or AI-generated PR

Paste when the PR looks generated and the author hasn't engaged
with the codebase.

```
This PR looks generated without a real engagement with the
codebase, and it doesn't have the contributor-vetting context
this repo requires (see STATUS.md). Closing without review.

If I'm wrong about how this PR was produced, I apologize for the
canned reply. The signal I'm looking for before re-opening a
review is a Discussion thread where you describe the problem and
your understanding of the relevant files in horus-os. That's the
intro path.

Project status and the gate for the contribution model:
https://github.com/Ridou/horus-os/blob/main/STATUS.md
```

## Reply 5: polite ping when an issue is going stale

Paste when an issue has open follow-ups from the reporter and the
maintainer wants to bump it without forcing a status check.

```
Bumping this one. The repo's in solo dev mode and triage cadence
depends on what's on the active milestone (see
https://github.com/Ridou/horus-os/blob/main/STATUS.md). If the
bug still reproduces on the latest release, a fresh log paste
helps; if it doesn't, feel free to close.
```
