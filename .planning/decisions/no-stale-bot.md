# Decision: no `actions/stale` auto-close bot

**Status:** OUT for v0.6 and beyond unless triage-load forces a revisit.

## Context

`actions/stale` (and its derivatives) auto-labels and auto-closes issues / PRs that go a configurable number of days without activity. Many open-source projects use it to keep the issue tracker visually tidy and to signal "we are responsive" to outside observers.

The downside is that auto-close creates a false signal: the bot's activity does not reflect maintainer engagement. An issue that gets auto-closed after 60 days of silence may be a real bug the maintainer simply has not had time to triage; the auto-close hides that backlog from the public view and frustrates the original reporter.

A solo-maintained project amplifies this problem. If the maintainer is offline for 4 weeks, the stale bot keeps marching, and contributors return to find their issues closed without explanation.

## Decision (final, until revisited)

horus-os does NOT use `actions/stale` or any equivalent auto-close mechanism. Issues stay open until they are explicitly resolved, duplicated, or marked `wontfix` by the maintainer.

To set honest expectations, `docs/TRIAGE.md` documents:
- Weekly Sunday triage cadence as the target.
- Explicit "may go silent up to 2 weeks" disclaimer.
- A `waiting-for-author` label for issues that legitimately need the reporter to respond; no auto-close on that label either, but a saved reply asks the reporter to ping again if the question is still relevant.

## Trade-offs

- Pro: backlog visibility is honest; an old issue means an old issue.
- Pro: contributors are not annoyed by a bot closing their report.
- Con: the issue list grows. Mitigated by the label taxonomy and the weekly triage cadence.
- Con: looks less "responsive" by standard GitHub-bot-driven metrics. Acceptable; we optimize for actual responsiveness, not bot-driven activity.

## When to revisit

- If issue volume exceeds the maintainer's weekly triage capacity by 3x for a sustained 8 weeks.
- If the project moves from solo to multi-maintainer and a triage rotation makes auto-close less misleading.

Neither trigger is on the roadmap. Revisit on signal, not on schedule.
