---
title: "Observability"
description: "How horus-os captures cost, latency, and tool-reliability data for every agent run into local SQLite, and how to read it with the dashboard and CLI."
---

## Overview

horus-os records cost, latency, and tool-reliability data for every agent run
into a local SQLite database. This is the page to read when you want to answer
"what did my agents actually do, how long did it take, and what did it cost?".

SQLite is the source of truth. The dashboard, the `horus-os usage` CLI, and the
opt-in OpenTelemetry exporter all read from the same rows. There is no separate
metrics store. The database lives inside your data directory at `horus.sqlite`
(see [Configuration](/getting-started/configuration/) for where that directory
resolves on each platform). Open it with any SQLite client. Nothing is hidden
behind a binary protocol.

> [!NOTE]
> For the conceptual model behind traces, spans, and rollups, read
> [Traces and observability](/concepts/traces-and-observability/). This page is
> the operational guide: what gets stored, how to query it, and how costs are
> computed.

## The observation bus

Instrumentation flows through an in-process observation bus. As an agent runs,
the runtime publishes three kinds of events to the bus:

- `LLM_CALL` for one provider call. Persists as one row in `llm_calls`.
- `TOOL_CALL` for one tool invocation. Persists as one row in `tool_invocations`.
- `RUN_END` at the end of an agent run. Triggers a rollup of `llm_calls` totals
  onto the matching `traces` row.

Subscribers receive every event in the order they subscribed. The cost annotator
subscribes first so it can populate `cost_usd` before the SQLite persister writes
the row. Each subscriber call is isolated: a subscriber that raises does not
block the others, so a broken or absent exporter never starves persistence.

The SQLite persister is the subscriber that writes the data described below. It
maps `LLM_CALL` to an insert into `llm_calls`, `TOOL_CALL` to an insert into
`tool_invocations`, and `RUN_END` to an update of the `traces` row.

## What gets captured

### Per LLM call (`llm_calls`)

One row per provider call:

- `input_tokens`, `output_tokens`
- `cache_read_input_tokens`, `cache_creation_input_tokens` when the provider
  exposes them. Anthropic reports both. Gemini exposes a cached-content token
  count.
- `latency_ms`, measured with `time.perf_counter`
- `model`, `provider`, `status`
- `cost_usd` and `pricing_missing`. `cost_usd` is NULL on unknown models. The
  goal is honesty rather than a false zero.

### Per tool call (`tool_invocations`)

One row per tool execution:

- `duration_ms`, measured with `time.perf_counter`
- `status`, either success or error
- `retry_count`, best effort. NULL when the SDK does not expose it.
- `last_error_text`, captured as the exception class name only, never the
  formatted message. User content cannot leak through this field.

### Per trace (`traces`)

Rolled up on `RUN_END`:

- `total_input_tokens`, `total_output_tokens`
- `total_cost_usd`, `total_duration_ms`

The trace rollup uses all-or-nothing cost semantics. If any contributing
`llm_calls` row has `cost_usd IS NULL` (an unknown model), the trace's
`total_cost_usd` is NULL too. The rollup never silently undercounts.

## How costs are computed

The cost annotator computes per-call cost from token counts and the pricing
table before the row is persisted:

```text
cost_usd = (
    input_tokens * input_per_million
    + output_tokens * output_per_million
    + cache_read_input_tokens * cache_read_per_million
    + cache_creation_input_tokens * cache_write_per_million
) / 1_000_000
```

Rates come from the bundled pricing table, which carries four rates per model:
input, output, cache write, and cache read. The result is rounded to 6 decimal
places.

Per-trace `total_cost_usd` is the sum of per-call `cost_usd` over the trace's
`llm_calls` rows, with the all-or-nothing rule described above.

> [!IMPORTANT]
> Unknown models persist `pricing_missing = 1` and `cost_usd = NULL`. NULL is
> honest. Zero would be a lie. A local model whose name is not in the pricing
> table is treated as genuinely free and annotated with `cost_usd = 0.0` rather
> than NULL.

## Pricing staleness

The bundled pricing table carries three top-level fields: `version`,
`updated_at` (an ISO-8601 date), and `release_version`.

The dashboard surfaces a staleness banner when `updated_at` is more than 30 days
old (yellow), and a stronger warning past 90 days (red). There are two paths to
fresh rates:

1. Upgrade to a newer horus-os release. The bundled pricing refreshes on every
   minor release.
2. Override locally. Point at your own pricing file with the
   `HORUS_OS_PRICING_PATH` environment variable, or set the `[pricing] path` key
   in `config.toml`:

   ```toml
   [pricing]
   path = "/Users/you/.config/horus-os/pricing.json"
   ```

The override schema mirrors LiteLLM's `model_prices_and_context_window.json`.

## The usage CLI

`horus-os usage` aggregates cost, latency, and tool-reliability data over a time
window and emits it as a table, JSON, or CSV:

```bash
horus-os usage --since 7d
horus-os usage --since 24h --format json --by model
horus-os usage --since 30d --format csv --by tool > tools.csv
horus-os usage --since 7d --format table --by agent
```

Flags:

- `--since` accepts a window like `24h`, `7d`, `30d`, or any `Nh` (hours) or
  `Nd` (days). Default `7d`.
- `--format` is one of `json`, `csv`, or `table`. Default `table`.
- `--by` slices the report by `agent`, `tool`, or `model`. Default `agent`.
- `--data-dir` overrides the platform default data directory for this command.

The CLI reuses the same query functions as the dashboard, so the two cannot
disagree about what a number means. If there is no database yet, the command
tells you to run `horus-os init` first.

### Output guarantees

Costs are rounded to 6 decimal places and durations to integer milliseconds.
That keeps the JSON output safe for `jq` pipelines, with no
`0.04200000000000001` float-precision noise.

The honesty contract survives serialization in every format. An uncosted value
renders as `null` in JSON, an empty cell in CSV, and a single hyphen (`-`) in
the table. It never reads as `0`. An empty window renders
`(no usage data in window)` in table mode and an empty string in CSV, so you can
tell "no data" apart from "command failed".

JSON output is wrapped in a stable envelope so `jq '.rows[]'` works uniformly
across all three `--by` modes:

```json
{
  "by": "model",
  "since": "24h",
  "rows": [
    {
      "model": "claude-sonnet-4-6",
      "total_cost_usd": 0.042,
      "total_input_tokens": 12000,
      "total_output_tokens": 800
    }
  ]
}
```

The full JSON schema is in the [CLI reference](/reference/cli-reference/).

## The observability dashboard

Start the dashboard and open the observability view:

```bash
horus-os serve
```

By default this serves on `http://127.0.0.1:8765`. Open `/observability` for
three panels:

- Cost by agent, a bar chart sorted high to low.
- Latency p50 and p95, a table per model.
- Tool reliability, a list per tool showing the success rate plus a preview of
  the last error.

A window selector at the top drives all three panels: 24h, 7d, or 30d, with 7d
as the default. The same pricing-staleness banner described above appears here
when rates are old.

A small-sample guard renders a placeholder dash for cells with fewer than 10
samples. Statistics with too little data are not shown, so they cannot mislead.

The `/agents` view gains three columns sourced from the same rollups:
`total_cost_usd`, `latency_p50`, and `latency_p95`.

See the [Dashboard guide](/guides/dashboard/) for the rest of the interface.

## Privacy

horus-os never sends prompts, completions, user content, tool input arguments,
tool output content, or formatted error messages outside the local SQLite file.
That guarantee holds for the dashboard, the JSON API, and the CLI alike.

The opt-in OpenTelemetry adapter exports numerical metadata only by default:
token counts, cost, latency, model name, and exception class name. Body content
is opt-in and passes through a redactor allowlist before it is attached. See
[OpenTelemetry](/operations/opentelemetry/) for the full threat model and the
operator trust statement.

## See also

- [Traces and observability](/concepts/traces-and-observability/)
- [OpenTelemetry](/operations/opentelemetry/)
- [CLI reference](/reference/cli-reference/)
- [Dashboard guide](/guides/dashboard/)
