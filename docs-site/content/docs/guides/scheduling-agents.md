---
title: "Scheduling agents"
description: "Run agents on a recurring cron schedule with horus-os schedule, including time zones, catch-up policy, and how to disable the scheduler."
---

## Overview

A schedule fires an agent on a cron timetable. Each schedule pairs an [agent profile](/concepts/agent-team/) with a fixed prompt, and on every due tick horus-os runs that profile against that prompt and records a [trace](/concepts/traces-and-observability/) just like an interactive run.

Schedules are created and managed entirely from the command line with `horus-os schedule`. There is no dashboard UI for managing schedules in this release.

The schedule definitions are stored in your database, but the scheduler that actually fires them runs inside `horus-os serve`. Creating a schedule does not start a background process by itself. For schedules to fire, `horus-os serve` must be running, ideally as an always-on service.

> [!IMPORTANT]
> A schedule only fires while `horus-os serve` is running. If you run `serve` only when you are at your machine, schedules fire only during those windows. To fire schedules reliably, run `serve` as a platform service. See [Running as a service](/guides/running-as-a-service/).

## Create a schedule

Use `horus-os schedule create`. A name, `--cron`, `--profile`, and `--prompt` are required:

```bash
horus-os schedule create morning-brief \
  --cron @daily \
  --profile operator \
  --prompt "Summarize anything new in my vault since yesterday."
```

The arguments are:

| Argument | Required | Purpose |
| --- | --- | --- |
| `name` | yes | Unique name for the schedule. Used to edit, enable, disable, or delete it later. |
| `--cron` | yes | When to fire: a cron expression, an `@`-alias, or shorthand sugar (see below). |
| `--profile` | yes | The agent profile to run on each fire. |
| `--prompt` | yes | The prompt sent to the agent on every run. |
| `--catch-up` | no | How to handle runs missed while `serve` was down. One of `coalesce` (default), `skip`, `all`. |

Names must be unique. Creating a schedule with a name that already exists fails and tells you to use `schedule edit` instead.

## Cron expressions and shorthand

`--cron` accepts three forms. All of them are validated before anything is stored, so an invalid expression is rejected at create time rather than failing silently later.

### Standard cron

A standard five-field cron expression (`minute hour day-of-month month day-of-week`):

```bash
# Every weekday at 9:00 in your local time zone.
horus-os schedule create standup \
  --cron "0 9 * * 1-5" \
  --profile operator \
  --prompt "Draft my standup notes from yesterday's vault changes."
```

### @-aliases

The standard cron aliases pass through directly:

```text
@hourly   @daily   @weekly   @monthly   @yearly   @annually   @midnight
```

```bash
horus-os schedule create weekly-review \
  --cron @weekly \
  --profile operator \
  --prompt "Write a weekly review of my open tasks."
```

### Shorthand sugar

A small set of human shorthand values map to cron for the common short intervals:

| Shorthand | Cron equivalent | Meaning |
| --- | --- | --- |
| `every 1m` | `* * * * *` | Every minute |
| `every 5m` | `*/5 * * * *` | Every 5 minutes |
| `every 30m` | `*/30 * * * *` | Every 30 minutes |
| `every 1h` | `0 * * * *` | Every hour, on the hour |

```bash
horus-os schedule create inbox-sweep \
  --cron "every 30m" \
  --profile operator \
  --prompt "Check for anything that needs my attention and note it."
```

> [!NOTE]
> Whatever form you pass, the schedule is stored as canonical cron. `schedule list` shows the resolved cron expression, not the shorthand you typed.

## Time zones

Cron expressions are evaluated in your machine's local time zone by default. horus-os auto-detects the local zone from the operating system; no network or location lookup is used.

To pin the schedule clock to a specific time zone, set `HORUS_TZ` to an IANA time zone name:

```bash
export HORUS_TZ="America/New_York"
```

When `HORUS_TZ` is set, all cron expressions are evaluated in that zone. This matters when `serve` runs as a service: a service may run under a different locale or zone than your interactive shell, so setting `HORUS_TZ` explicitly removes ambiguity.

> [!TIP]
> Set `HORUS_TZ` in the same place you set your provider keys for the service. A supervised service does not inherit your interactive shell environment, so the zone (and your keys) must be forwarded into the service definition. See [Running as a service](/guides/running-as-a-service/).

## Catch-up policy

A schedule can miss firing windows while `serve` is stopped (a reboot, a laptop asleep overnight, a crashed service). The `--catch-up` policy decides what happens to those missed windows when `serve` comes back up.

| Policy | Behavior on wake-up |
| --- | --- |
| `coalesce` (default) | Fire exactly once, then advance to the next future slot. A long downtime collapses into a single run, never a flood of catch-up runs. |
| `all` | Backfill missed slots, firing one per tick until the schedule catches up to the present. |
| `skip` | Do not fire genuinely missed slots at all. Re-arm to the next future slot. A slot that is due on time still fires. |

For most schedules `coalesce` is what you want: if your machine was off all night, a `@daily` job runs once on wake-up rather than once for every missed day.

```bash
# Backfill every missed window after downtime.
horus-os schedule create hourly-log \
  --cron @hourly \
  --profile operator \
  --prompt "Append an hourly status line to my log note." \
  --catch-up all
```

The scheduler also guards against overlap and double-firing on its own, independent of the catch-up policy:

- If a schedule's previous run is still in flight when its next slot comes due, the new run is skipped until the prior one finishes.
- Run state is persisted before each run dispatches, so a process restart in the middle of a run does not cause that schedule to fire twice.

## List, edit, enable, disable, and delete

### List

```bash
horus-os schedule list
```

This prints a table of every schedule with its name, resolved cron expression, profile, whether it is enabled, and the next run time. With no schedules yet, it prints `(no schedules yet)`.

### Edit

`schedule edit` updates one or more fields of an existing schedule. Pass only the fields you want to change:

```bash
# Change just the timetable.
horus-os schedule edit standup --cron "0 8 * * 1-5"

# Change the prompt and catch-up policy at once.
horus-os schedule edit standup \
  --prompt "Draft standup notes and flag any blockers." \
  --catch-up skip
```

You can change `--cron`, `--profile`, `--prompt`, and `--catch-up`. Editing with no fields is an error, since there is nothing to update.

### Enable and disable

Disabling a schedule stops it from firing without deleting it. Re-enable it to resume:

```bash
horus-os schedule disable standup
horus-os schedule enable standup
```

### Delete

```bash
horus-os schedule delete standup
```

Deleting removes the schedule permanently. Traces from its past runs are not removed.

## Disabling the scheduler

The scheduler is on by default whenever `serve` runs. To stop `serve` from starting the scheduler at all, set `HORUS_OS_DISABLE_SCHEDULER` to `true`:

```bash
export HORUS_OS_DISABLE_SCHEDULER=true
horus-os serve
```

With this set, `serve` starts cleanly and the dashboard works normally, but no schedules fire. This is useful when you want the dashboard without background runs, or when you run multiple `serve` instances against the same data directory and want only one of them to own scheduling.

> [!WARNING]
> Disabling the scheduler does not delete or disable your individual schedules. They remain in the database and will fire again as soon as a `serve` process without `HORUS_OS_DISABLE_SCHEDULER` starts.

## See also

- [Running as a service](/guides/running-as-a-service/) keeps `serve` alive so schedules fire reliably.
- [Tasks and scheduling](/concepts/tasks-and-scheduling/) explains the scheduling model and how runs become traces.
- [The agent team](/concepts/agent-team/) covers the profiles a schedule fires.
- [Environment variables](/reference/environment-variables/) lists `HORUS_TZ`, `HORUS_OS_DISABLE_SCHEDULER`, and related settings.
