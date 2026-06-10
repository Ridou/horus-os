<!--
This file is a draft for the maintainer to paste into a pinned
GitHub Discussion (category: Announcements). It is NOT auto-posted.

To use:
  1. Go to https://github.com/Ridou/horus-os/discussions/new?category=announcements
  2. Title: "Project Status (pinned)"
  3. Paste the body below.
  4. After posting, click the "..." menu on the Discussion and pick "Pin".
  5. Update the body or post a reply when STATUS.md changes.
-->

# Project Status (pinned)

> **TL;DR:** horus-os is **open for outside contributions** as of
> 2026-06-10. The latest release is **v0.8.0** (Local-first and
> Autonomous Research). See
> [STATUS.md](https://github.com/Ridou/horus-os/blob/main/STATUS.md)
> for the dated, canonical version of everything below.

This Discussion is the rolling public-facing update for the
project. The full timeline and dates live in
[STATUS.md](https://github.com/Ridou/horus-os/blob/main/STATUS.md).
Bookmark that file. The rest of this post is a snapshot.

## Where the project is right now

- **Latest release:** v0.8.0 (Local-first and Autonomous Research)
  on 2026-06-03: local LLM provider, on-device vector memory, MCP
  client, web access, vision and PDF, the Deep Research workflow, a
  skills system, and gated shell execution.
- **On `main`, unreleased:** a streaming dashboard chat, an agent
  store with a custom-agent builder, an opt-in Twilio voice adapter,
  a 10-step onboarding tour, and an agent Standup view. They ship in
  the next tagged cut.
- **Next milestone:** v0.9, Autonomy and Control (planned).
- **Open for outside PRs:** yes, through the claim flow in
  [CONTRIBUTING.md](https://github.com/Ridou/horus-os/blob/main/CONTRIBUTING.md).

## How to contribute

1. Pick an issue labeled `good-first-issue` or `help-wanted`, or
   file the bug or proposal you actually hit.
2. Comment to claim it. The maintainer reviews and assigns; the
   `claimed` label means it is yours.
3. Open a draft PR within 7 days. CI runs the full three-OS matrix
   plus supply-chain scans before human review.

Design questions and scope ideas go to Discussions first. Questions
and help live in the
[community Discord](https://discord.gg/vwX9WvwQhp).

## Honest expectations

horus-os is solo-maintained. Triage targets a weekly Sunday pass and
may go quiet for up to two weeks; see
[docs/TRIAGE.md](https://github.com/Ridou/horus-os/blob/main/docs/TRIAGE.md).
There is no 24-hour SLA, no stale-bot, and no CLA.

Real-use feedback is still the highest-value input: run horus-os
against a real workload and write up what worked and what did not,
right here in Discussions.
