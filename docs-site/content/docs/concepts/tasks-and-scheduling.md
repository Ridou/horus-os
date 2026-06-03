---
title: "Tasks and scheduling"
description: "How horus-os represents tasks on the dashboard and how the in-process cron scheduler fires recurring agent runs with catch-up policies."
---

## Overview

horus-os has two related but distinct concepts for tracking and triggering work:

- A **task queue**, a record of units of work with a status, surfaced read-only on the dashboard at `/api/tasks`.
- A **cron scheduler**, an in-process loop that fires an agent profile with a prompt on a recurring schedule.

Tasks describe work that exists. Schedules cause work to happen on a clock. Both live in your local SQLite database alongside [traces](/concepts/traces-and-observability/), so nothing leaves your machine.

This page is conceptual. For the step-by-step commands, see [Scheduling agents](/guides/scheduling-agents/). To keep the scheduler running when you are not logged in, see [Running as a service](/guides/running-as-a-service/).

## Tasks

A task is a row in the `tasks` table. Each task carries a stable `task_id`, a `title`, an optional `description`, an optional assigned `agent_profile_name`, an optional `trace_id` linking it to the run that produced it, and a `status`.

A task status is always one of:

| Status      | Meaning                                          |
| ----------- | ------------------------------------------------ |
| `pending`   | Queued, not yet started.                         |
| `running`   | Currently being worked on.                        |
| `completed` | Finished successfully.                            |
| `error`     | Finished with a failure.                          |
| `cancelled` | Stopped before completion.                        |

The status set is enforced by a database `CHECK` constraint, so an invalid status cannot be written.

### Tasks on the dashboard

The dashboard exposes tasks through a read-only JSON endpoint:

```bash
# All tasks, newest first.
curl http://127.0.0.1:8765/api/tasks

# Filter by status.
curl "http://127.0.0.1:8765/api/tasks?status=running"
```

Passing a `status` value outside the allowed set returns HTTP 400. Omitting it returns every task. Tasks are always ordered newest first.

Deleting a task is the one mutating operation, and it is guarded:

```bash
# Cancel/delete one task. Only reachable from loopback.
curl -X DELETE http://127.0.0.1:8765/api/tasks/your-task-id
```

The delete endpoint carries a loopback guard: it rejects any request whose TCP peer is not `127.0.0.1`, so task rows cannot be mutated from a remote address even when the dashboard is reachable over the network. See [Remote access](/guides/remote-access/) for why that matters and how to reach the dashboard safely.

> [!NOTE]
> The dashboard surfaces tasks as a status view. In this release the primary way to drive recurring agent work is the cron scheduler described below, not a writable task board.

## The cron scheduler

The scheduler is a background adapter that runs inside the dashboard process. When you run `horus-os serve`, the scheduler starts on the server lifespan, reads the `schedules` table on a fixed tick (every 30 seconds), and fires any schedule whose next run time has passed.

Because it lives in the serve process, the scheduler only runs while the dashboard is running. To fire schedules around the clock, keep `horus-os serve` supervised as an always-on service. See [Running as a service](/guides/running-as-a-service/).

### What a schedule is

A schedule is a row in the `schedules` table. Each schedule pairs a cron expression with the agent work to run:

- `name`, a unique label you use to manage it.
- `cron_expression`, the canonical stored form of the schedule.
- `agent_profile_name`, the [agent](/concepts/agent-team/) profile that runs.
- `prompt`, the instruction sent on each run.
- `enabled`, whether the scheduler considers it.
- `catch_up_policy`, how missed runs are handled (see below).
- `last_run_at`, `next_run_at`, and `last_trace_id`, the bookkeeping the scheduler maintains.

Schedules are managed from the CLI only; there is no dashboard UI for creating or editing them. See [Scheduling agents](/guides/scheduling-agents/) for the full `horus-os schedule` command set.

### How a run fires

On each tick the scheduler:

1. Reads every **enabled** schedule.
2. Skips any schedule whose previous run is still in flight. A schedule never overlaps itself.
3. Skips any schedule whose `next_run_at` is still in the future.
4. For a due schedule, applies its catch-up policy to decide whether to fire and what the new `next_run_at` should be.
5. Persists `last_run_at` and `next_run_at` **before** dispatching the run, so a process restart mid-run never double-fires.
6. Dispatches the agent run on a worker thread so the tick loop is never blocked, then writes the resulting `trace_id` back onto the schedule row.

Each fired run records a normal trace, the same kind of trace an interactive run produces, so scheduled work shows up in your observability views. A failed run still records a trace with an error status rather than crashing the loop. One bad schedule never stops the others.

### Cron expressions and shorthand

Cron is the canonical form, but you can pass shorthand when creating a schedule. The CLI accepts:

- A standard 5-field cron expression, for example `0 9 * * 1` for 9 AM every Monday.
- An `@`-alias such as `@hourly` or `@daily`.
- A small set of human sugar: `every 1m`, `every 5m`, `every 30m`, `every 1h`.

Shorthand is desugared to cron before it is stored. Anything that is not recognized sugar, a valid `@`-alias, or a valid cron expression is rejected before anything is written, so a typo cannot create a broken schedule.

### Timezone

Cron is evaluated in the machine's local timezone, auto-detected from the OS. To pin a specific zone, set the `HORUS_TZ` environment variable to an IANA name such as `America/New_York`. There is no location-aware or network-based timezone resolution. See [Environment variables](/reference/environment-variables/).

## Catch-up and coalesce

A scheduler that lives in the serve process can miss windows whenever that process is down (a reboot, an upgrade, a laptop closed overnight). The `catch_up_policy` on each schedule decides what happens to those missed windows when the scheduler wakes up. Three policies are available:

| Policy     | Behavior on missed windows                                                                                   |
| ---------- | ------------------------------------------------------------------------------------------------------------ |
| `coalesce` | Default. Fire **exactly once** and collapse the entire backlog into the next future slot. One downtime, one run, never a flood. |
| `all`      | Backfill missed slots, one per tick, advancing one cron step at a time until the schedule catches up to now. |
| `skip`     | Never fire a genuinely late slot. Re-arm to the next future slot. An on-time slot still fires.               |

> [!TIP]
> Keep the default `coalesce` for most schedules. It means a machine that was off all weekend fires your "every morning" routine once on Monday, not once for every morning it missed.

> [!CAUTION]
> Use `all` deliberately. If a schedule runs frequently and the process was down for a long time, `all` will work through the entire backlog one slot per tick, which can produce many runs in a row.

## Disabling the scheduler

The scheduler is on by default whenever the dashboard runs. To turn it off, set `HORUS_OS_DISABLE_SCHEDULER=true` before starting `horus-os serve`. With that set, the scheduler does not start, the runtime comes up cleanly, and the health check still passes. This is useful when you want the dashboard for browsing traces and tasks but do not want any scheduled runs to fire from that process.

## See also

- [Scheduling agents](/guides/scheduling-agents/) walks through creating, editing, and managing schedules with the CLI.
- [Running as a service](/guides/running-as-a-service/) keeps `horus-os serve` (and therefore the scheduler) always on.
- [The agent team](/concepts/agent-team/) explains the profiles a schedule fires.
- [Traces and observability](/concepts/traces-and-observability/) shows where scheduled runs land once they fire.
