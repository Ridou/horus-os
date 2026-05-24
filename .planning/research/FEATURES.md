# Feature Research

**Domain:** LLM-application observability (cost, latency, tool-reliability, OTel export) for an existing local-first, single-machine OSS agent runtime (horus-os v0.4)
**Researched:** 2026-05-24
**Confidence:** HIGH for prior-art shapes (multiple official sources). HIGH for what's table-stakes vs. anti given v0.4's locked anti-goals (PROJECT.md "Out of Scope"). MEDIUM on the exact UX of a few differentiators (cost-budget alerts, slow-trace drill-in) where OSS implementations diverge.

## Prior-Art Grounding (cited inline below)

Five reference OSS LLM-observability projects and the GenAI specs that define "what an LLM observability feature looks like" in 2026:

| Project | License | What they ship for cost / latency / tool-reliability / OTel |
|---------|---------|-------------------------------------------------------------|
| [Langfuse](https://langfuse.com/docs/observability/features/token-and-cost-tracking) | OSS (self-hostable, all core features free) | Cost & latency broken down by user, session, model, prompt version. Tracks usage/cost on `generation` and `embedding` observations. Aggregate metrics (latency, cost, tokens) on dashboard. Gantt-chart trace timeline. |
| [Arize Phoenix](https://arize.com/docs/phoenix) | OSS (Apache 2.0) | Span-level tracing built on OpenTelemetry + OpenInference. Traces every step including tool calls. "Traces stay in your environment" (self-hostable). Playground for replaying traced LLM calls. |
| [Helicone](https://github.com/Helicone/helicone) | OSS (self-hostable, single Docker command) | Cost tracking, latency, error rates per request. Self-host containerized down to 4 services. Export to PostHog for custom dashboards. |
| [Lunary](https://posthog.com/blog/best-open-source-llm-observability-tools) | OSS (self-hostable) | Cost & token tracking per user, per session, per model. Detailed traces, user-session grouping, prompt playground. |
| [AgentOps](https://github.com/AgentOps-AI/agentops) | OSS (MIT) | Cost monitoring, failure detection ("multi-agent interaction issues"), session replay, time-travel debugging. Maintainer of [tokencost](https://github.com/AgentOps-AI/tokencost) (`model_prices.json` for 400+ models). |
| [OpenLLMetry / OTel GenAI semconv](https://opentelemetry.io/docs/specs/semconv/gen-ai/) | OSS standard | Defines the wire shape: `gen_ai.client.token.usage` (histogram), `gen_ai.client.operation.duration` (histogram), `gen_ai.request.model`, `gen_ai.provider.name`, plus `gen_ai.input.messages` / `gen_ai.output.messages` (the deprecation of `gen_ai.prompt` / `gen_ai.completion` matters for our schema choices — see PITFALLS). |
| [LiteLLM `model_prices_and_context_window.json`](https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json) | OSS pricing dataset | The de-facto community-maintained pricing JSON. Auto-synced from GitHub by LiteLLM itself. Single source for input/output/cache token rates per 400+ models. |

All five OSS projects converge on the same baseline: **token counts + USD cost + latency + error rate, sliced by model and by agent/run/session, viewable in a dashboard, exportable.** That convergence is what makes those features "table stakes." Where the projects diverge is on evals, guardrails, prompt playgrounds, multi-tenant workspaces, and team features — most of which are explicit anti-features for us.

## Feature Landscape

### Table Stakes (Users Expect These)

Every v0.4 user already running an agent on horus-os will assume these exist. Missing any of them makes the milestone feel like a half-shipped observability story.

| Feature | Why Expected | Complexity | Notes (incl. dependencies on existing v0.1-v0.3 surfaces) |
|---------|--------------|------------|-----------|
| **Token counts captured per LLM call** (input/output, plus cache-read / cache-write when the provider returns them) | Every OSS LLM-obs tool (Langfuse, Helicone, Lunary, AgentOps) captures this. Without it, no cost math is possible. | LOW | Anthropic SDK returns `usage.input_tokens` / `usage.output_tokens` / cache fields directly. Gemini SDK returns `usage_metadata.prompt_token_count` / `candidates_token_count`. We already buffer the provider response in `_providers/_anthropic.py` and `_providers/_gemini.py`. **Depends on:** existing provider helpers. Schema change: add columns to `traces` (v4 → v5 migration). |
| **USD cost computed from token counts + bundled `pricing.json`** | Decision is locked (PROJECT.md). Token counts alone are useful but everyone wants $ figures — this is the headline of [Langfuse cost tracking](https://langfuse.com/docs/observability/features/token-and-cost-tracking) and [Helicone](https://github.com/Helicone/helicone). | LOW | Bundled JSON shaped like [LiteLLM's `model_prices_and_context_window.json`](https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json) (per-1M-token input/output rates, optional cache rates). Cost = `(input_tokens × input_rate + output_tokens × output_rate) / 1_000_000`. **Depends on:** token-capture above. **Dependency on:** nothing else; pure derived column. |
| **User-overridable `pricing.json`** | Bundled file ages between releases; new models ship weekly. PROJECT.md locks this in. [LiteLLM](https://docs.litellm.ai/docs/proxy/sync_models_github) and [tokencost-dev](https://github.com/atriumn/tokencost-dev) both treat overrideability as required because pricing changes weekly. | LOW | Load order: bundled → `${HORUS_OS_HOME}/pricing.json` → env override. **Depends on:** existing `config.py` (`HORUS_OS_HOME` already wired in). |
| **End-to-end agent-run latency** (wall clock from `run_agent` entry to final result) | This is the single most-asked-about LLM-observability number. Every tool surveyed surfaces it as the primary chart on the dashboard. | LOW | Measure in `run_agent` / `run_agent_async` / `run_agent_loop`. Store on the top-level trace row. **Depends on:** existing `traces` table (add `total_duration_ms` column). |
| **Per-LLM-call latency** | OTel GenAI semconv defines [`gen_ai.client.operation.duration`](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-metrics/) as a core histogram. Without per-call latency, "slow run" investigations dead-end at "the run was slow." | LOW | Measure inside `_providers/_anthropic.py` and `_providers/_gemini.py` around the SDK call. Already exists implicitly (we have a `latency` column in v4 `traces`); we need to make sure it's populated consistently and split from total agent latency. **Depends on:** existing `traces.latency` column. |
| **Per-tool-call latency + success/error status** | The [OTel GenAI agent spans spec](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/) treats tool calls as first-class spans. Phoenix and AgentOps both surface tool-call success/failure as a top-level signal. | LOW-MEDIUM | We already have `ToolCallEvent` in `types.py` and `execute_tool_uses` in `tools/registry.py` — wrap the dispatch in try/except + timing. Store as JSON in trace row OR new `tool_calls` child table. The child-table version is cleaner for the reliability dashboard query. **Depends on:** `tools/registry.py`, `types.py`, `traces` schema. |
| **p50 / p95 percentile aggregates per model + per agent + per tool** | OTel GenAI metrics spec [explicitly recommends p95 by `(provider, model)`](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-metrics/). Langfuse, Helicone, Lunary all surface percentile bands (mean alone hides tail-latency, which is what users actually feel). | LOW | Computed on-demand in SQL (`ORDER BY duration_ms LIMIT 1 OFFSET <pct * N>`) over a time window. No need for a streaming percentile estimator at v0.4 scale (single user, single machine, thousands of rows). **Depends on:** per-call latency capture. |
| **Tool success/error rates** (rolling success ratio per tool name) | Decision is locked. AgentOps and Phoenix both show this as a per-tool tile. Without it, broken tools rot silently. | LOW | `SELECT tool_name, AVG(success), COUNT(*) FROM tool_calls WHERE ts > ?`. **Depends on:** per-tool capture above. |
| **Last-error preview per tool** (most recent error message, truncated) | Decision is locked. Listed in user-facing copy across [Helicone error dashboards](https://github.com/Helicone/helicone) and Phoenix's [tool-span view](https://arize.com/docs/phoenix). The dashboard tells you a tool is failing; the preview tells you *why* without a full trace dive. | LOW | Store `last_error_message`, `last_error_at` either on a rolled-up `tool_stats` view OR computed from the latest failing row per tool. View is cheaper, no extra writes. **Depends on:** per-tool error capture. |
| **`/observability` dashboard tab** with three core panels: cost-by-agent, latency p50/p95, tool error-rate | PROJECT.md locks this in. The shape mirrors [Helicone's main dashboard](https://www.helicone.ai/blog/self-hosting-launch) and [Langfuse aggregate views](https://langfuse.com/docs/metrics/overview). | MEDIUM | Three vanilla-JS panels added to the existing single-page dashboard (no React build — see ARCHITECTURE.md "single-page vanilla JS"). New `/api/observability/*` endpoints in `server/api.py`. **Depends on:** existing dashboard scaffolding, existing API patterns (`/api/traces`, `/api/agents`). |
| **Extended numbers on existing `/agents` tab** (cost / median latency / error rate per profile) | Same expectation users already have for the `/agents` listing — they'll glance there first. PROJECT.md mentions this explicitly. | LOW | Augment the existing `GET /api/agents` payload with aggregate fields. **Depends on:** existing `/api/agents` route. |
| **Time-window filtering** (last 24h / 7d / 30d, with default of 7d) | Every OSS tool defaults to a window. Without it, the cost panel either lies (lifetime totals) or overwhelms (every row). | LOW | URL query param `?since=24h|7d|30d`. Wire through `/api/observability/*` and the new CLI. |
| **`horus-os usage` CLI subcommand** with `--format json|csv|table` and `--since 7d` | PROJECT.md locks this in. The CLI is the v0.1 audience — they need parity with the dashboard. Pattern mirrors [`aws ce get-cost-and-usage`](https://docs.aws.amazon.com/cli/latest/reference/ce/get-cost-and-usage.html) (JSON/CSV/text output) and the existing `horus-os traces` subcommand we already ship. | LOW-MEDIUM | New file `cli/usage.py`. Shares query layer with `/api/observability/*` — extract a `horus_os.metrics` module that both call so we don't duplicate SQL. **Depends on:** existing `cli/` scaffolding, new `metrics` module. |
| **Opt-in OTel exporter as a v0.3-style adapter** (behind `[otel]` extra) | PROJECT.md locks the *shape* (adapter, opt-in extra). The *feature* is table-stakes for any OSS observability tool in 2026 because half the audience already runs Grafana/Tempo/Jaeger/Honeycomb. [OpenLLMetry](https://www.traceloop.com/docs/openllmetry/contributing/semantic-conventions) demonstrates OSS LLM apps emitting OTel directly. [Python OTLP exporter](https://opentelemetry.io/docs/languages/python/exporters/) is the standard install (`pip install opentelemetry-exporter-otlp`). | MEDIUM | New `adapters/otel_adapter.py` implementing `Adapter` + `LifecycleAdapter` (start = init `TracerProvider` + `OTLPSpanExporter`, stop = shutdown provider). Emit one span per trace row, child spans for tool calls. Use the GenAI semantic-convention attribute names (`gen_ai.request.model`, `gen_ai.client.token.usage`, `gen_ai.provider.name`). **Depends on:** existing `adapters/base.py` (LifecycleAdapter, AdapterRegistry, FastAPI lifespan integration — all already in place). |
| **Additive v4 → v5 SQLite migration** (v0.3 databases continue to read) | PROJECT.md locks this in. v0.1 → v0.2 (v2 → v3) and v0.2 → v0.3 (v3 → v4) both already shipped under the "additive, idempotent" rule. Breaking that contract on the first observability release would be the worst-possible user surprise. | LOW | `ALTER TABLE traces ADD COLUMN ...` for the new cost/latency fields, `CREATE TABLE IF NOT EXISTS tool_calls ...`. Idempotent in the existing `storage.py` boot path. **Depends on:** existing `storage.py` migration scaffold (already handles v2 → v3 → v4 cleanly). |

### Differentiators (Competitive Advantage)

These are not strictly required for v0.4 to feel complete, but each one is a genuine local-first / single-user UX win over the SaaS-flavored OSS tools surveyed. Pick from this list if scope allows.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Cache-aware cost math** (separate counters for cache-read vs. cache-write tokens with their own rates) | Anthropic prompt caching is 90% cheaper to read, 25% more to write. Most OSS tools collapse both into "input tokens" and silently undercount or overcount cost. Getting this right is a small honesty win that matters to people who actually use prompt caching. | LOW-MEDIUM | Anthropic SDK already exposes `cache_creation_input_tokens` and `cache_read_input_tokens`. LiteLLM's [pricing JSON](https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json) already carries `cache_read_input_token_cost` and `cache_creation_input_token_cost` per model. Just persist + use those columns. |
| **Cost diff vs. prior window** ("week-over-week: +$2.13, +18%") on dashboard + CLI | Single-line summary that turns raw numbers into a decision signal. Lunary's per-user/session cost cards do something similar. Cheap to compute over a single SQLite table. | LOW | One extra SQL aggregate; one extra dashboard tile; one CLI flag (`--compare 7d`). |
| **Slow-trace drill-in** ("top 5 slowest agent runs in window, click → full trace tree") | The existing `/traces` view shows everything chronologically; users want "show me what's painful." Phoenix and Langfuse both highlight slow traces. We already have `parent_trace_id` + `list_child_traces` from v0.2 multi-agent work — the tree rendering already exists. | LOW-MEDIUM | New panel on `/observability` querying `ORDER BY total_duration_ms DESC LIMIT 5`, deep-linking to existing `/traces/{id}` page. |
| **Most-failing-tool callout** (single biggest red number on the dashboard) | One-glance answer to "what's broken right now?" Inverts the success-rate panel into an action signal. AgentOps and Helicone both surface this. | LOW | One SQL aggregate (`ORDER BY error_rate DESC LIMIT 1 WHERE call_count >= 5`). |
| **CLI JSON output is stable enough to pipe through `jq`** (documented schema, semver-tagged) | Local-first users compose. `horus-os usage --format json --since 7d \| jq '...'` should not break between point releases. Treats the CLI like a public API. The existing `horus-os traces` JSON output already sets this precedent. | LOW (mostly discipline + docs) | Document the JSON schema in `docs/CLI.md`. Add a test that pins the top-level shape. |
| **OTel adapter emits both spans and metrics** (not just spans) | OTel GenAI spec defines [`gen_ai.client.token.usage`](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-metrics/) as a histogram metric. Users who already run a metrics backend (Prometheus, Grafana, Honeycomb) want native histograms, not derived-from-spans. | MEDIUM | Adds `MeterProvider` + `OTLPMetricExporter` alongside the trace exporter. Bucket boundaries per spec. |
| **`horus-os usage --by model` / `--by tool` / `--by agent`** | Three different "where's the money / where's the time / where's the broken thing" questions. Mirrors `aws ce get-cost-and-usage --group-by`. | LOW | Same query layer, different `GROUP BY` column. |
| **Bundled `pricing.json` includes a `last_updated` and `release_version` field** | Honesty about freshness. tokencost and LiteLLM both ship with version metadata. Lets the dashboard show a "pricing data is N days old, override at $HORUS_OS_HOME/pricing.json" hint when stale. | LOW | Trivial header fields in the JSON; consumed by a single dashboard banner. |

### Anti-Features (Commonly Requested, Often Problematic)

These are features the surveyed OSS LLM-observability projects all ship — and that v0.4 must explicitly NOT ship, because they violate horus-os's locked anti-goals (PROJECT.md "Out of Scope": no SaaS, no multi-tenant, no third-party paid accounts, single-machine).

| Feature | Why Requested | Why Problematic Here | Alternative |
|---------|---------------|----------------------|-------------|
| **Multi-user / multi-tenant cost attribution** ("cost per `user_id`", "cost per `session_id`") — central to Langfuse, Lunary, Helicone | Required for SaaS-style chargeback dashboards. Users coming from Langfuse will ask. | Violates PROJECT.md "Multi-tenant patterns" Out of Scope. There's one user — the operator. Cost-per-agent / per-model / per-tool already gives them every slice they need. | The agent-profile dimension *is* our per-user proxy. Document this. |
| **Cost budgets with alerts** ("notify me when this month > $50") | Almost every OSS tool has this. Tempting because "alert me" feels universal. | Requires an alerting subsystem (channels, delivery, dedup) we deliberately don't have. Closest existing surface is the Discord/Slack adapter, but wiring observability into adapter-emitted alerts is a v0.5 plugin-manifest concern. | v0.5+. Users who need this today can query the SQLite directly with cron. |
| **Custom dashboards / saved queries** | Helicone exports to PostHog for custom dashboards. Langfuse has its own query builder. | We have one dashboard for one operator. A query builder UI is a 10x feature for a 1x audience. | The CLI `usage` subcommand + JSON output covers ad-hoc analysis. SQLite is a file on disk; advanced users can use any SQL tool. |
| **Trace evaluation / scoring / LLM-as-judge** — Phoenix and Langfuse both ship this | Big in 2026 LLM-obs marketing. Users coming from those tools will ask. | Out of scope for the *observability* milestone. Evals are a separate concern (v0.6+ candidate). Mixing them in dilutes v0.4 and pulls in eval-model API costs (anti-goal). | Defer entirely. Note in PROJECT.md if it becomes a recurring ask. |
| **Replay / re-run a traced LLM call from the dashboard** — Phoenix Playground | Genuinely useful for debugging. | Requires either re-issuing the call (network + cost side-effects, breaks "no silent network calls" principle) or a mock-replay mode (significant complexity). | The existing `horus-os run` CLI already takes a prompt; `traces` already shows the prompt. Copy-paste suffices at v0.4. |
| **PII redaction / guardrails / prompt-injection detection** — Lunary ships this | Increasingly expected from LLM-obs tools. | Out of scope for an observability milestone. Conflates two concerns. | Defer. Could land as an opt-in v0.5 adapter (the v0.3 adapter pattern fits this well). |
| **Required external service for storage** (ClickHouse, Postgres, S3) — Langfuse v3 needs all three | Performant at scale. | Violates PROJECT.md "SQLite remains the source of truth" + "no paid third-party account" + "single-machine." | SQLite scales fine to millions of rows for a single user. WAL mode handles concurrent dashboard reads + agent writes. |
| **A built-in alerting / webhook hub** | Helicone has rate-limit hooks, Langfuse has alerts. | We have adapters that already own the "outbound notification" lane (Discord, Slack, Email). Building a parallel alerting subsystem inside observability fragments the codebase. | When alerting eventually ships, it should be an adapter consuming observability data, not a feature *of* observability. v0.5 plugin manifest era. |
| **Multi-project / workspace separation** | Standard in SaaS-flavored OSS (Lunary "3 projects", Langfuse "organizations"). | Out of scope. One operator, one machine, one project. Adding workspaces is a complexity tax with zero local-first benefit. | The `agent_profile_name` axis already gives logical grouping. |
| **Auth on the `/observability` tab** | Reasonable for a hosted dashboard. | We bind to `127.0.0.1` (already documented in ARCHITECTURE.md "What is not in v0.3"). Adding auth on a single endpoint without auth on the rest of the dashboard is inconsistent and misleading. | Stays bound to localhost. Document. |
| **Forced OTel-only mode** (no SQLite, push everything to user's collector) | Pure-OTel purists will ask. | Violates "SQLite remains the source of truth" (PROJECT.md). Also breaks the CLI `usage` subcommand, the dashboard, and the existing `traces` table contract. | OTel is opt-in *additive* export. SQLite is always-on. |

## Feature Dependencies

```
[SQLite v4 → v5 migration]                  (TABLE STAKES, foundational)
        |
        +--> [Token-count capture per LLM call]
        |        |
        |        +--> [USD cost computation]
        |        |        |
        |        |        +--> [User-overridable pricing.json]
        |        |        |
        |        |        +--> [/observability cost panel]
        |        |        |
        |        |        +--> [/agents tab cost augmentation]
        |        |        |
        |        |        +--> [horus-os usage CLI]
        |        |        |
        |        |        +--> [Cost diff vs. prior window]   (DIFF)
        |        |        |
        |        |        +--> [Cache-aware cost math]        (DIFF)
        |        |
        |        +--> [OTel exporter — token usage metric]    (TABLE STAKES; opt-in)
        |
        +--> [Per-LLM-call latency]
        |        |
        |        +--> [p50/p95 aggregates]
        |        |        |
        |        |        +--> [/observability latency panel]
        |        |        +--> [horus-os usage CLI]
        |        |        +--> [Slow-trace drill-in]          (DIFF)
        |        |
        |        +--> [OTel exporter — operation.duration]    (TABLE STAKES; opt-in)
        |
        +--> [Per-tool-call latency + status]
                 |
                 +--> [Tool success/error rates]
                 |        |
                 |        +--> [/observability tool-reliability panel]
                 |        +--> [Most-failing-tool callout]    (DIFF)
                 |
                 +--> [Last-error preview]
                 |
                 +--> [OTel exporter — tool spans]            (TABLE STAKES; opt-in)

[Time-window filtering] ──enhances──> every dashboard panel + the CLI

[OTel adapter] ──depends on──> existing v0.3 [Adapter + LifecycleAdapter protocols],
                               existing [AdapterRegistry], existing [FastAPI lifespan integration]
```

### Dependency Notes

- **SQLite v4 → v5 migration is the only hard ordering constraint.** Everything else can ship in any order once the schema is in place. The migration adds: `traces.input_tokens`, `traces.output_tokens`, `traces.cache_read_input_tokens`, `traces.cache_creation_input_tokens`, `traces.cost_usd`, `traces.total_duration_ms`, plus a new `tool_calls` child table keyed by `trace_id`.
- **Token-count capture must precede cost computation.** No tokens, no math. Both Anthropic and Gemini SDKs already return the data — we just have to persist it.
- **Per-call latency must precede percentile aggregates.** SQLite can compute `PERCENTILE_CONT` only if we have the per-call rows. We do not need a streaming sketch (HdrHistogram, T-Digest) at v0.4 scale.
- **Per-tool capture must precede both the reliability panel and the last-error preview.** Same row, different SELECTs.
- **`horus-os usage` CLI shares its query layer with `/api/observability/*`.** Extract a `horus_os.metrics` module and have both consumers call it. Avoids two SQL implementations drifting apart.
- **OTel adapter depends on the entire v0.3 adapter system.** This is by design — PROJECT.md locks it. The lifecycle protocol's `start`/`stop` hooks map cleanly to `TracerProvider` init/shutdown. The AdapterRegistry's error isolation means a missing OTLP collector cannot brick the core dashboard.
- **OTel adapter does NOT depend on `horus-os usage` or the dashboard panels.** It can ship in parallel with them. They share the same underlying capture path (token counts, durations) but consume it differently.
- **The bundled `pricing.json` must ship in the package data,** like the dashboard JS file already does. Reuse the same package-data plumbing — there's a known-good path in `pyproject.toml` for shipping non-Python files.

## MVP Definition

### v0.4 Launch (Table Stakes Only)

Minimum viable v0.4 — every item is from the Table Stakes table above. Without all of these, the milestone is incomplete.

- [ ] SQLite v4 → v5 additive migration (foundational)
- [ ] Token-count capture per LLM call (both providers, all token types Anthropic returns)
- [ ] USD cost computation from bundled `pricing.json`
- [ ] User-overridable `pricing.json` via `$HORUS_OS_HOME/pricing.json`
- [ ] End-to-end agent-run latency on top-level trace row
- [ ] Per-LLM-call latency (already partially present; normalize)
- [ ] Per-tool-call latency + success/error status (new `tool_calls` table)
- [ ] p50 / p95 aggregates per model / per agent / per tool
- [ ] Tool success/error rates + last-error preview
- [ ] `/observability` dashboard tab (cost-by-agent, latency p50/p95, tool error-rate)
- [ ] Cost / median latency / error rate added to `/agents` tab
- [ ] Time-window filtering (`?since=24h|7d|30d`, default 7d)
- [ ] `horus-os usage --format json|csv|table --since 7d` CLI subcommand
- [ ] Opt-in OTel exporter as a v0.3-style adapter (`[otel]` extra), emitting GenAI-semconv-compliant spans

### Add If Scope Allows (Differentiators)

In rough order of "biggest UX win for least extra work."

- [ ] Cache-aware cost math (LOW, free correctness win; user-visible only if they use Anthropic caching)
- [ ] Most-failing-tool callout on dashboard (LOW, one SQL aggregate)
- [ ] Slow-trace drill-in (LOW-MEDIUM, reuses existing trace-tree renderer)
- [ ] `horus-os usage --by model|tool|agent` (LOW, same query layer)
- [ ] Cost diff vs. prior window (LOW, one extra aggregate)
- [ ] OTel metrics (in addition to spans) — `gen_ai.client.token.usage` histogram (MEDIUM)
- [ ] `pricing.json` carries `last_updated` + `release_version`; dashboard surfaces a "stale" banner (LOW)
- [ ] CLI JSON output schema documented + pinned by a test (LOW; mostly process)

### Out (Explicit, Don't Drift Into)

Everything in the Anti-Features table. Document the boundary in v0.4 release notes so people coming from Langfuse / Phoenix / Helicone aren't surprised.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| SQLite v4 → v5 migration | HIGH (blocks everything) | LOW | P1 |
| Token-count capture per LLM call | HIGH | LOW | P1 |
| USD cost computation | HIGH | LOW | P1 |
| User-overridable `pricing.json` | MEDIUM (becomes HIGH the day a model is missing) | LOW | P1 |
| End-to-end agent-run latency | HIGH | LOW | P1 |
| Per-LLM-call latency | HIGH | LOW | P1 |
| Per-tool-call latency + status | HIGH | LOW-MEDIUM | P1 |
| p50 / p95 aggregates | HIGH | LOW | P1 |
| Tool success/error rates | HIGH | LOW | P1 |
| Last-error preview | HIGH | LOW | P1 |
| `/observability` dashboard tab | HIGH | MEDIUM | P1 |
| `/agents` tab augmentation | MEDIUM | LOW | P1 |
| Time-window filtering | HIGH (default 7d is the actual UX) | LOW | P1 |
| `horus-os usage` CLI | HIGH (CLI is half our audience) | LOW-MEDIUM | P1 |
| Opt-in OTel exporter | MEDIUM (huge for the subset who run their own collector; zero for everyone else) | MEDIUM | P1 (PROJECT.md locks it) |
| Cache-aware cost math | MEDIUM | LOW-MEDIUM | P2 |
| Most-failing-tool callout | MEDIUM | LOW | P2 |
| Slow-trace drill-in | MEDIUM | LOW-MEDIUM | P2 |
| Cost diff vs. prior window | MEDIUM | LOW | P2 |
| `usage --by model\|tool\|agent` | MEDIUM | LOW | P2 |
| OTel metrics (alongside spans) | LOW-MEDIUM | MEDIUM | P3 |
| `pricing.json` freshness banner | LOW | LOW | P3 |

**Priority key:**
- P1 — required for v0.4 launch (table stakes; PROJECT.md locked items).
- P2 — ship if scope allows after P1 lands; clear differentiators with cheap implementations.
- P3 — defer to a v0.4.x patch or v0.5 if the cost-benefit moves.

## Competitor Feature Analysis

How each of the five reference OSS projects implements the v0.4 surface area, and what we do differently because of our anti-goals.

| Feature | Langfuse | Phoenix (Arize) | Helicone | Lunary | AgentOps | horus-os v0.4 |
|---------|----------|-----------------|----------|--------|----------|----------------|
| **Cost tracking source** | Auto-attaches usage based on model name; supports custom pricing per project | Inherits from instrumented framework | Built-in price registry, per-request cost | Per-user / per-session / per-model | Uses [tokencost](https://github.com/AgentOps-AI/tokencost) JSON | Bundled `pricing.json` (shape borrowed from [LiteLLM's](https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json)), user-overridable |
| **Storage backend** | Postgres + ClickHouse + Redis + S3 (v3) | OpenTelemetry-native, multiple backends | Postgres (self-host: 4 containers) | Postgres | Cloud-hosted, OSS SDK | SQLite (single file, WAL mode) — and that's it |
| **Tracing primitive** | Trace / observation hierarchy | OTel spans + OpenInference | Per-request | Trace / session | Sessions + events | Top-level trace + child traces (delegation) + new tool_calls child table |
| **Latency view** | Gantt + aggregates | Span tree + waterfall | Request list + percentiles | Trace list + aggregates | Session replay timeline | Per-trace tree (existing) + p50/p95 panel (new) |
| **Tool reliability UI** | Generic span/event filtering | Tool-call spans (OpenInference convention) | Generic error tracking | Generic error tracking | Failure detection callout | Dedicated `/observability` tile + last-error preview |
| **OTel export** | Ingests OTLP (it's a *receiver*) | OTel-native end-to-end | Has OTel integrations | Has OTel exporter (custom) | Multi-framework SDK | Opt-in *outbound* OTLP adapter (`[otel]` extra) — we never *receive* OTLP, we only emit it |
| **CLI for usage data** | None (web-first) | None (web-first) | None (web-first) | None (web-first) | None (SDK-first) | `horus-os usage` — none of the surveyed tools ship a CLI usage report; this is a genuine gap we fill |
| **Auth model** | Multi-tenant, project keys | Configurable | Multi-tenant, project keys | Multi-tenant, project keys | Multi-tenant, project keys | Single-user, localhost-bound, no auth |
| **Evals / playgrounds / guardrails** | Yes (all three) | Yes (evals + playground) | Experimentation | Prompt playground + guardrails | Failure analysis | None — explicit anti-feature for v0.4 |

The differentiation pattern is consistent: **we trade away every "team / SaaS / multi-tenant / hosted" feature, and in return we get a single-binary install, zero external dependencies, the CLI, and the file the user can grep with `sqlite3`.**

## Sources

OSS LLM observability projects surveyed (the prior art the v0.4 feature set is calibrated against):

- [Langfuse — Token & Cost Tracking](https://langfuse.com/docs/observability/features/token-and-cost-tracking)
- [Langfuse — Observability Overview](https://langfuse.com/docs/observability/overview)
- [Langfuse v3 Self-Hosting Guide (ClickHouse architecture rationale)](https://jangwook.net/en/blog/en/langfuse-self-hosted-llm-tracing-setup-guide-2026/)
- [Arize Phoenix — What it is (OSS)](https://arize.com/docs/phoenix)
- [Arize Phoenix — GitHub](https://github.com/arize-ai/phoenix)
- [Helicone — GitHub](https://github.com/Helicone/helicone)
- [Helicone — Self-Hosting launch announcement](https://www.helicone.ai/blog/self-hosting-launch)
- [Lunary — feature overview (PostHog OSS tools roundup)](https://posthog.com/blog/best-open-source-llm-observability-tools)
- [AgentOps — GitHub](https://github.com/agentops-ai/agentops)

Pricing data sources (for the bundled `pricing.json` shape):

- [tokencost — AgentOps-AI/tokencost (Python package + `model_prices.json` for 400+ models)](https://github.com/AgentOps-AI/tokencost)
- [LiteLLM `model_prices_and_context_window.json` (the de-facto community pricing dataset, auto-synced from GitHub)](https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json)
- [LiteLLM — Auto Sync New Models from GitHub (Day-0 Launches)](https://docs.litellm.ai/docs/proxy/sync_models_github)
- [tokencost-dev — MCP server backed by LiteLLM registry](https://github.com/atriumn/tokencost-dev)

OpenTelemetry GenAI semantic conventions (defines the wire shape the OTel adapter must produce):

- [OTel — Semantic conventions for generative AI systems (index)](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- [OTel — Semantic conventions for generative client AI spans](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/)
- [OTel — Semantic conventions for GenAI agent and framework spans](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/)
- [OTel — Semantic conventions for generative AI metrics](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-metrics/)
- [OTel — Python OTLP exporter docs](https://opentelemetry.io/docs/languages/python/exporters/)
- [OpenLLMetry — GenAI semantic conventions contribution guide](https://www.traceloop.com/docs/openllmetry/contributing/semantic-conventions)
- [traceloop/openllmetry#3515 — deprecation of `gen_ai.prompt` / `gen_ai.completion`, replaced by `gen_ai.input.messages` / `gen_ai.output.messages`](https://github.com/traceloop/openllmetry/issues/3515) (informs our schema attribute naming)

CLI usage-report design references:

- [AWS CLI `ce get-cost-and-usage` reference (JSON/text output shape)](https://docs.aws.amazon.com/cli/latest/reference/ce/get-cost-and-usage.html)
- [AWS Cost Management — CSV download format](https://docs.aws.amazon.com/cost-management/latest/userguide/ce-download-csv.html)

---
*Feature research for: LLM-observability features for horus-os v0.4 (cost, latency, tool reliability, OTel export, CLI usage)*
*Researched: 2026-05-24*
