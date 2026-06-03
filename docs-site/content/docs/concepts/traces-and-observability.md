---
title: "Traces and observability"
description: "How every agent action becomes a trace, how cost and latency are captured, and how to read them through the usage CLI and the dashboard."
---

## What a trace is

Every time an agent runs, horus-os records what happened. One agent run produces one trace, and a trace is the parent scope for everything that run did: each provider call and each tool invocation is attached to it by a shared `trace_id`.

A trace answers three questions about an agent run:

- What did it do (which provider, which model, which tools)?
- How long did it take (latency per call and per run)?
- What did it cost (US dollars, computed from token counts)?

All of this lives in a single local SQLite database. There is no separate metrics service, no telemetry endpoint, and nothing leaves your machine by default. The dashboard, the `horus-os usage` CLI, and the optional OpenTelemetry exporter all read the same rows, so they cannot disagree about what a number means.

> [!NOTE]
> The database is `horus.sqlite` inside your data directory. You can open it with any SQLite client. Nothing is hidden behind a binary protocol. See [The vault](/concepts/the-vault/) for the rest of the data directory layout.

## The observation bus

Capture runs through a small in-process publish/subscribe channel called the observation bus. The runtime publishes an event whenever something observable happens, and subscribers turn those events into rows, costs, and (optionally) exported metrics.

There is exactly one bus per process. The runtime, the dashboard, and any subscriber all reach it through a single accessor, so there is one place to wire in cost annotation, persistence, and export.

The bus is synchronous and fire-and-forget. A subscriber that raises an exception is swallowed, never propagated. A slow or broken exporter can never stall or crash the agent loop.

### The three events

The bus carries three event kinds:

| Event | Published when | Lands in table |
|-------|----------------|----------------|
| `LLMCallEvent` | One provider call completes | `llm_calls` |
| `ToolCallEvent` | One tool invocation completes | `tool_invocations` |
| `RunEndEvent` | An agent run finishes | rolls up into `traces` |

Subscribers fire in subscribe order, and that order matters:

1. The cost annotator runs first. It reads the token counts on an `LLMCallEvent` and fills in `cost_usd`.
2. The SQLite persister runs second. It writes the now-annotated event to the database.
3. The OpenTelemetry exporter, when installed and enabled, runs last. It exports numerical metadata only. See [OpenTelemetry](/operations/opentelemetry/).

## What gets captured

### Per LLM call

Each provider call writes one row to `llm_calls`:

- `input_tokens` and `output_tokens`.
- `cache_creation_input_tokens` and `cache_read_input_tokens`, when the provider reports them.
- `latency_ms`, the wall-clock time from call start to the result being available, including any SDK-level retries, backoff, and stream drain.
- `model`, `provider`, and `status`.
- `cost_usd` and `pricing_missing`.

### Per tool invocation

Each tool call writes one row to `tool_invocations`:

- `latency_ms`, the wall-clock duration of the call.
- `status`, either `success` or `error`.
- `retry_count`, best effort, and `NULL` when the underlying SDK does not expose a counter.
- `error_type`, captured as the exception class name only.

> [!IMPORTANT]
> Error fields store the exception class name, never the formatted message. User content, prompts, tool arguments, and tool output cannot leak through the error fields.

### Per run

When a run ends, the `RunEndEvent` rolls the per-call rows up onto the `traces` row:

- `total_input_tokens` and `total_output_tokens`.
- `total_cost_usd`.
- `total_duration_ms`.

## How cost is computed

Cost is computed locally from token counts and a bundled pricing table. For each LLM call:

```text
cost_usd = (
    input_tokens                 * input_per_million
    + output_tokens              * output_per_million
    + cache_creation_input_tokens * cache_write_per_million
    + cache_read_input_tokens     * cache_read_per_million
) / 1_000_000
```

The math is cache aware: each model carries four rates (input, output, cache write, cache read), so prompt caching is priced correctly rather than lumped into one number.

The per-run `total_cost_usd` is the sum of the per-call costs over that run.

### Honest nulls, never false zeros

When the pricing table has no entry for a model, horus-os sets `cost_usd` to `NULL` and flags `pricing_missing`, rather than pretending the call was free. The rule is all or nothing at the run level: if any contributing call has an unknown price, the run's `total_cost_usd` becomes `NULL` too, so a partial total never undercounts the real cost.

A call to a local provider is genuinely free and is recorded as `0.0`, which is distinct from the `NULL` used for an unknown price. The dashboard renders that as local and free rather than as a pricing gap.

> [!TIP]
> Rates ship in the package and refresh on each release. If you need newer or custom prices, you can point horus-os at your own pricing file. See [Configuration](/reference/configuration/) and [Observability](/operations/observability/) for the override.

## Reading traces from the CLI

List recent runs:

```bash
horus-os traces
```

By default this prints the most recent 20 traces as a table of timestamp, provider, model, status, and a prompt preview. Adjust the count, or emit JSON for scripting:

```bash
horus-os traces --limit 50
horus-os traces --json
```

## The usage report

`horus-os usage` aggregates cost, latency, and tool reliability over a time window. It reuses the same query layer as the dashboard, so the two cannot drift apart.

```bash
horus-os usage --since 7d
horus-os usage --since 24h --format json --by model
horus-os usage --since 30d --format csv --by tool > tools.csv
horus-os usage --since 7d --format table --by agent
```

The flags:

- `--since` takes a window: `24h`, `7d`, `30d`, or any `Nh` (hours) or `Nd` (days). Default `7d`.
- `--format` is `table`, `json`, or `csv`. Default `table`.
- `--by` slices the report by `agent`, `tool`, or `model`. Default `agent`.

Costs round to 6 decimal places and durations to integer milliseconds, which keeps the JSON output clean for `jq` pipelines. An uncosted value renders as `null` in JSON, an empty cell in CSV, and a single hyphen in table mode, so an unknown price never reads as a zero in any format.

> [!NOTE]
> The usage report and the dashboard read the local database. Run an agent first (see [Your first team run](/getting-started/first-team-run/)) so there are traces to aggregate.

## The dashboard views

Start the local dashboard:

```bash
horus-os serve
```

By default it binds to `http://127.0.0.1:8765` and requires the `dashboard` extra. Two tabs cover observability:

- The Traces tab lists recent runs. Delegated runs render as a tree, since each sub-agent run records its own trace pointing at the coordinator's.
- The Observability tab shows cost by agent, latency percentiles per model, and tool reliability over a selectable window. It also surfaces a banner when the bundled pricing data is stale.

See [The dashboard](/guides/dashboard/) for the full tour.

## Privacy

horus-os never sends prompts, completions, tool inputs, tool outputs, or formatted error messages out of the local database. That guarantee holds for the dashboard, the JSON API, and the CLI.

The OpenTelemetry exporter is opt-in. It is off unless you install the `otel` extra and configure an endpoint, and even then it exports numerical metadata only by default: token counts, cost, latency, model name, and exception class name. Body content export is a separate explicit opt-in. See [OpenTelemetry](/operations/opentelemetry/) for the full threat model.

## See also

- [Observability](/operations/observability/) for the operational detail: pricing overrides, staleness handling, and the SQLite schema.
- [OpenTelemetry](/operations/opentelemetry/) for exporting metrics to an external collector.
- [Architecture](/concepts/architecture/) for how the runtime and storage fit together.
- [CLI reference](/reference/cli-reference/) for every `traces` and `usage` flag.
