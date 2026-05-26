# Migration from v0.3 to v0.4

## TL;DR

v0.4 is purely additive. Every v0.3 surface (`run_agent`,
`run_agent_async`, `run_agent_loop`, `run_agent_stream`,
`Database`, `ToolRegistry`, `Adapter`, `AdapterContext`,
`LifecycleAdapter`, `AdapterRegistry`, `discover_adapters`, the
JSON API, the CLI subcommands, the dashboard, all five v0.3
adapters) continues to work byte-identical. No removals. No
deprecations.

What lights up: a local-first cost / latency / tool-reliability
observability surface backed by SQLite as the source of truth, a
new `/observability` dashboard tab, a `horus-os usage` CLI
subcommand, an opt-in OpenTelemetry exporter behind a `[otel]`
extra, and two confirmed v0.3 cost-correctness bug fixes you
inherit for free.

## What is new

### Runtime types and modules

- `horus_os.observability`: new package. `get_observation_bus()` /
  `reset_observation_bus_for_tests()` (the `ObservationBus`
  singleton), `SQLitePersister` (one row per LLM call into
  `llm_calls`, one row per tool call into `tool_invocations`),
  `PricingTable` and `CostAnnotator` (the cost computation
  subscriber that runs BEFORE the persister), `queries.py` pure
  functions (`agent_totals`, `cost_by_agent`, `latency_p50_p95`,
  `tool_reliability`) shared by dashboard and CLI.
- `LLMCallEvent` and `ToolInvocationEvent`: the two event types the
  bus carries. The runner (Phase 33) publishes them at the LLM-call
  and tool-call boundaries; subscribers fan out to cost annotation,
  persistence, and the opt-in OTel exporter.
- `OtelAdapter`: opt-in adapter behind the `[otel]` extra. Lazy SDK
  import (no `ModuleNotFoundError` if the extra is missing; a clear
  `RuntimeError` instead). Default-deny on body content. See
  `docs/OTEL.md` for the threat model.

## Schema migration v4 to v5

v0.3 databases upgrade cleanly on first v0.4 startup. The migration
is additive only.

Added on `traces` (all nullable, NULL on pre-v0.4 rows):

- `total_input_tokens INTEGER NULL`
- `total_output_tokens INTEGER NULL`
- `total_cost_usd REAL NULL`
- `total_duration_ms INTEGER NULL`

Added as new child tables:

- `llm_calls`: one row per LLM call. Carries `trace_id`,
  `provider`, `model`, `input_tokens`, `output_tokens`,
  `cache_read_input_tokens`, `cache_creation_input_tokens`,
  `latency_ms`, `cost_usd` (NULL on unknown models),
  `pricing_missing` (1 when the model was not in pricing.json),
  `status`, `error_type`.
- `tool_invocations`: one row per tool call. Carries `trace_id`,
  `tool_name`, `duration_ms`, `status`, `retry_count` (NULL when
  the SDK does not expose it), `error_type`.

The old `traces.usage` JSON blob is preserved forever; v0.3 code
that reads it keeps working byte-identical.

SQLite pragmas are pinned to `synchronous=NORMAL` plus WAL on every
connection (never `FULL`). Pitfall 8 prevention.

Pre-v0.4 trace rows render with NULL on the four new rollup
columns. The dashboard shows a placeholder dash for cells with no
pre-v0.4 data; the `/agents` tab tile counts how many runs predate
v0.4 so the missing dollars are explained rather than hidden.

## Bug fixes you inherit for free

Two confirmed v0.3 cost-correctness bugs that v0.4 structurally
fixes. Both are documented as Pitfall 1 and Pitfall 2 in the
project research notes; both fixes land in Phase 33.

- **Per-iteration token undercount (Pitfall 1).** v0.3
  `record_trace` wrote only the FINAL loop iteration's `usage`
  dict, so a multi-turn run under-reported tokens by a factor of N.
  A 5-iteration agent run in v0.3 reported 1/5 of actual cost. v0.4
  publishes one `LLMCallEvent` per iteration via the
  `ObservationBus`; per-call `llm_calls` rows roll up to
  `traces.total_input_tokens = SUM(...)` on `RUN_END`. Streaming and
  non-streaming paths share the same capture, so multi-iteration
  agents report real cost regardless of the entrypoint.
- **SSE silent $0 (Pitfall 2).** v0.3 `/api/chat/stream` did not
  route through `run_agent_loop`, so every streamed run silently
  landed at $0.00 cost in the trace explorer. v0.4 instruments the
  SSE branch directly via `stream.get_final_message().usage` for
  Anthropic and `response.usage_metadata` for Gemini; streamed runs
  now persist real token counts and the same rollup math drives the
  trace `total_cost_usd`.

Pre-v0.4 cost reporting was DOUBLE-WRONG (undercounted tokens AND
$0 streaming). Anyone relying on v0.3 cost numbers should treat
them as ceilings, not actuals.

## New runtime surface

- `ObservationBus` singleton wired via `get_observation_bus()`. The
  bus is in-process pub/sub; subscribers (cost annotator, SQLite
  persister, OTel adapter when enabled) attach during `create_app`.
- `SQLitePersister` writes one `llm_calls` row per LLM call and one
  `tool_invocations` row per tool call. On `RUN_END` it computes
  the trace-level rollups via `SUM(...) FROM llm_calls WHERE
  trace_id = ?` and updates the `traces` row.
- `PricingTable` loads `src/horus_os/observability/pricing.json`
  (cache-aware: four rates per model) and exposes a `lookup(model)`
  helper. The `CostAnnotator` subscriber runs BEFORE the persister
  so cost lands on the event before it is written.
- `observability/queries.py` exports pure helpers (`agent_totals`,
  `cost_by_agent`, `latency_p50_p95`, `tool_reliability`) that both
  the dashboard JSON routes and the CLI subcommand reuse.

## New env vars and config

Pricing override:

- `HORUS_OS_PRICING_PATH=/path/to/your/pricing.json` (env)
- `[pricing] path = "/path/to/your/pricing.json"` in `config.toml`

Both override the bundled `src/horus_os/observability/pricing.json`.
Useful when a model is unknown or a published rate moved between
bundled-pricing refreshes. Schema mirrors LiteLLM's
`model_prices_and_context_window.json`. Unknown models persist
`pricing_missing=1, cost_usd=NULL`; NULL is honest, zero is a lie
(Pitfall 5).

OpenTelemetry opt-in:

- `HORUS_OS_OTEL_CAPTURE_CONTENT=true` (EXACT lowercase only; any
  other value, including `1`, `yes`, `TRUE`, `True`, stays
  default-deny). When set, the OTel adapter MAY attach a redacted
  body attribute carrying the LLM error message. The redactor
  allowlist is defence-in-depth; see `docs/OTEL.md` `## Threat
  model` for the trust statement.
- `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS`,
  `OTEL_SERVICE_NAME`: OTel SDK env vars, passed through verbatim
  when the `[otel]` extra is installed.

## New CLI surface

```
horus-os usage --since 7d
horus-os usage --since 24h --format json --by model
horus-os usage --since 30d --format csv --by tool > tools.csv
horus-os usage --since 7d --format table --by agent
```

- `--since` accepts `Nh` (hours) or `Nd` (days).
- `--format json|csv|table` controls output shape. JSON output
  schema is pinned in `docs/CLI.md` and tested against a fixture
  so the CLI cannot drift.
- `--by model|tool|agent` slices the report.
- Costs are rounded to 6 decimal places, durations to integer ms.
  Safe for `jq` pipelines (no float-precision noise like
  `0.04200000000000001`).

Stdlib only. Reuses `observability/queries.py` so the CLI and the
dashboard cannot drift.

## New dashboard surface

A new `/observability` tab joins Chat / Traces / Writes / Agents /
Adapters. Three panels:

- Cost by agent (bar chart, sorted high to low).
- Latency p50 and p95 (table per model).
- Tool reliability (list per tool: success rate plus a preview of
  the last error).

Window selector drives all three: 24h / 7d / 30d, default 7d.

A pricing-staleness banner at the top of the tab turns yellow past
30 days and red past 90 days; the copy explains the
`HORUS_OS_PRICING_PATH` override.

A small-sample guard renders a placeholder dash for cells with
fewer than 10 samples. Pre-v0.4 trace rows render the same
placeholder dash with a hover note "no cost data captured before
v0.4".

The existing `/agents` tab gains three new columns sourced from
the same rollups: `total_cost_usd`, `latency_p50`, `latency_p95`.

## New optional extra and install

```
pip install "horus-os[otel]"
```

The `[otel]` extra adds two pure-Python packages
(`opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-http`).
The HTTP exporter is the deliberate choice; gRPC was rejected
because the Windows wheel gap on `grpcio` would break the 3-OS CI
install matrix.

A bare `pip install horus-os` does NOT pull `opentelemetry-*`
(verified by the `install-smoke-no-otel` CI job). If you forget
the extra and try to start the adapter, you get a clean
`RuntimeError: OTel adapter requires 'pip install horus-os[otel]'`,
NEVER a `ModuleNotFoundError` (Pitfall 12).

See `docs/OTEL.md` for the full configuration, attribute schema,
threat model, and bounded-shutdown story.

## No breaking changes

Every v0.3 API works byte-identical under v0.4. No removals. No
deprecations. The `Adapter`, `LifecycleAdapter`, `AdapterContext`,
`AdapterRegistry`, `AdapterEntry`, and `discover_adapters` shapes
are unchanged. All five v0.3 adapters (webhook, discord, slack,
email, calendar) keep working without modification. The dashboard
Chat, Traces, Writes, Agents, and Adapters tabs render the same as
in v0.3 with cost columns appearing only on Agents.

## Upgrade checklist

1. `pip install --upgrade horus-os`
2. Optionally add `[otel]`: `pip install --upgrade "horus-os[otel]"`
3. Restart the server (`horus-os serve`)
4. Verify the schema migrated to v5 (the server logs the migration
   on first v0.4 startup; `SELECT version FROM schema_version`
   returns 5)
5. Open `http://localhost:8000/observability` and confirm the new
   tab renders. New traces will populate cost / latency / tool
   reliability as agents run.

## See also

- `docs/OBSERVABILITY.md`: user-facing observability guide (what
  gets captured, dashboard tour, CLI usage, cost math, pricing
  staleness, privacy note).
- `docs/OTEL.md`: opt-in OpenTelemetry adapter guide, including
  the `## Threat model` section that covers default vs
  content-capture modes.
- `docs/CLI.md`: full CLI reference with the new `horus-os usage`
  subcommand and JSON output schema.
- `CHANGELOG.md` `[0.4.0]` section: complete changelog of the
  Observability milestone.
