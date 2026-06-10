# Observability

horus-os captures cost, latency, and tool-reliability data for
every agent run into a local SQLite database. This is the doc to
read when you want to answer "what did my agents actually do, how
long did it take, and what did it cost?".

SQLite is the source of truth. The dashboard, the `horus-os usage`
CLI, and the opt-in OpenTelemetry exporter all read from the same
rows. There is no separate metrics store.

## What gets captured

Per LLM call (one row per provider call in `llm_calls`):

- `input_tokens`, `output_tokens`
- `cache_read_input_tokens`, `cache_creation_input_tokens` (when
  the provider exposes them; Anthropic does, Gemini exposes
  `cached_content_token_count`)
- `latency_ms` (measured with `time.perf_counter`)
- `model`, `provider`, `status`
- `cost_usd` and `pricing_missing`. NULL on unknown models; honest
  rather than false-zero.

Per tool call (one row per tool execution in `tool_invocations`):

- `duration_ms` (`time.perf_counter`)
- `status` (success or error)
- `retry_count` (best-effort; NULL when the SDK does not expose it)
- `last_error_text` is captured as the exception CLASS NAME ONLY,
  never the formatted message; user content cannot leak through
  this field.

Per trace (rolled up onto `traces` on `RUN_END`):

- `total_input_tokens`, `total_output_tokens`
- `total_cost_usd`, `total_duration_ms`

Everything lives in `<data_dir>/horus.sqlite`, where the data
directory is the platform default or the `HORUS_OS_DATA_DIR`
override. Open it with any SQLite client; nothing is hidden behind
a binary protocol.

## How to read the Costs dashboard

Run `horus-os serve` and open `http://127.0.0.1:8765`, then the
Costs page. Three panels:

- **Cost by agent** (bar chart, sorted high to low).
- **Latency p50 and p95** (table per model).
- **Tool reliability** (list per tool: success rate plus a preview
  of the last error).

A window selector at the top drives all three panels: 24h / 7d /
30d, default 7d.

A pricing-staleness banner appears past 30 days (yellow) and past
90 days (red). The banner copy explains the two paths to fresh
rates (upgrade to a newer horus-os release, or set
`HORUS_OS_PRICING_PATH` to point at your own pricing file).

A small-sample guard renders a placeholder dash for cells with
fewer than 10 samples; statistics with too little data are not
shown so they cannot mislead.

The Team page surfaces the same rollups per agent
(`total_cost_usd`, `latency_p50`, `latency_p95`) on each agent's
detail view.

## How to use the horus-os usage CLI

```
horus-os usage --since 7d
horus-os usage --since 24h --format json --by model
horus-os usage --since 30d --format csv --by tool > tools.csv
horus-os usage --since 7d --format table --by agent
```

- `--since` accepts `Nh` (hours) or `Nd` (days).
- `--format json|csv|table` controls output shape; the JSON schema
  is pinned in `docs/CLI.md` and tested against a fixture so the
  CLI cannot drift from what scripts depend on.
- `--by model|tool|agent` slices the report.

Costs are rounded to 6 decimal places, durations to integer ms.
That keeps the JSON output safe for `jq` pipelines (no
`0.04200000000000001` float-precision noise).

The CLI reuses `observability/queries.py` so the dashboard and the
CLI cannot disagree.

## How costs are computed

Per-LLM-call cost:

```
cost_usd = (
    input_tokens * input_per_million
    + output_tokens * output_per_million
    + cache_read_input_tokens * cache_read_per_million
    + cache_creation_input_tokens * cache_write_per_million
) / 1_000_000
```

Rates come from `src/horus_os/observability/pricing.json`.
Cache-aware: four rates per model (input, output, cache write,
cache read).

Per-trace `total_cost_usd` is the SUM of per-call `cost_usd` over
the trace's `llm_calls` rows. All-or-nothing semantics: if ANY
contributing row has `cost_usd IS NULL` (unknown model), the
trace rollup is NULL too. Honesty over false precision.

## Pricing staleness

The bundled `pricing.json` carries three fields at the top level:
`version`, `updated_at` (ISO-8601 date), `release_version`.

The dashboard surfaces a staleness banner when `updated_at` is
more than 30 days old.

Two paths to fresh rates:

1. Upgrade to a newer horus-os release. The bundled pricing.json
   refreshes on every minor release; the release gate
   (`scripts/release_gate.py`) blocks any release where pricing
   is older than 14 days (see `docs/RELEASE.md`).
2. Override locally with `HORUS_OS_PRICING_PATH=/path/to/your/pricing.json`
   (env) or `[pricing] path = "/path/to/your/pricing.json"` in
   `config.toml`. Schema mirrors LiteLLM's
   `model_prices_and_context_window.json`.

Unknown models persist `pricing_missing=1, cost_usd=NULL`.
NULL is honest; zero is a lie (Pitfall 5). Trace and CLI rollups
that include an unknown-model row become NULL too rather than
silently undercounting.

## Privacy note

horus-os NEVER sends prompts, completions, user content, tool
input arguments, tool output content, or formatted error messages
outside the local SQLite file. That guarantee holds for the
dashboard, the JSON API, and the CLI.

The opt-in OpenTelemetry adapter (installed via `[otel]` extra AND
gated on `OTEL_EXPORTER_OTLP_ENDPOINT` being set) exports
NUMERICAL metadata only by default: token counts, cost, latency,
model name, exception class name. Body content is opt-in via
`HORUS_OS_OTEL_CAPTURE_CONTENT=true` (exact lowercase) and goes
through a redactor allowlist before attribute attachment. See
`docs/OTEL.md` `## Threat model` for the full inventory and the
operator trust statement.

## Pre-v0.4 trace rendering

Trace rows created before v0.4 have NULL on the four new rollup
columns. The dashboard renders a placeholder dash for those
cells with hover text "no cost data captured before v0.4". The
`/agents` tab also shows a separate tile counting "N runs from
before v0.4 with no cost data" so the missing dollars are
explained rather than hidden.

New traces created on v0.4 populate the columns as agents run.

## See also

- `docs/MIGRATION-v0.3-to-v0.4.md`: upgrade notes from v0.3,
  including the schema migration and the inherited bug fixes.
- `docs/CLI.md`: CLI overview and the `horus-os usage` JSON output
  schema.
- `docs/OTEL.md`: opt-in OpenTelemetry adapter setup and threat
  model.
- `docs/RELEASE.md`: maintainer release procedure, including the
  pricing-freshness gate.
