# Project Research Summary

**Project:** horus-os v0.4 Observability
**Domain:** Local-first cost, latency, and tool-reliability instrumentation for a single-process agent runtime; opt-in OpenTelemetry exporter
**Researched:** 2026-05-25
**Confidence:** HIGH

## Executive Summary

v0.4 turns horus-os from "agents run" into "agents run and you know what they cost, what they took, and what broke." Research across STACK, FEATURES, ARCHITECTURE, and PITFALLS converges on a small, additive design: an in-process synchronous `ObservationBus`, two new SQLite child tables (`llm_calls`, `tool_invocations`), four nullable rollup columns on `traces`, a bundled `pricing.json` derived from the LiteLLM community dataset shape, a new `/observability` dashboard tab, a `horus-os usage` CLI subcommand, and a single opt-in `OtelAdapter` shipped behind a `[otel]` extra. No paid SaaS, no third-party services, no schema rewrites. The only meaningful new runtime deps are the three OpenTelemetry pure-Python packages, and only when the user explicitly opts in.

Two findings reshape the milestone scope beyond "instrumentation." First, ARCHITECTURE confirmed a live v0.3 correctness bug: `record_trace` writes the `usage` dict from only the FINAL loop iteration, so any multi-turn run currently under-reports tokens (and therefore cost) by a factor of N. The new `llm_calls` child table plus a `RUN_END` rollup is the structural fix. Second, the `/api/chat/stream` path does NOT go through `run_agent_loop` and so needs its own narrow capture site in `server/api.py:_event_stream`; without it, every streamed run silently lands at $0.00 in the dashboard. Both are framed in PITFALLS as Pitfalls 1 and 2 with the "never silently record $0" rule. Treat them as correctness work in the first two phases, not as polish later.

The highest-stakes risk in the entire milestone is PII leakage through OTel span attributes (PITFALLS Pitfall 7). The OTel exporter MUST default-deny prompt and completion bodies, MUST gate any body capture behind an explicit `HORUS_OS_OTEL_CAPTURE_CONTENT=true` env var plus a redactor allowlist, and MUST be guarded by a CI test asserting that `AKIAI*`-class strings do not appear in the default output. Two other OTel failure modes are real and tracked upstream (issues #3309 and #4623): naive shutdown can block for 60 seconds, and there is no configurable timeout. Mitigation is a bounded 2s `force_flush` plus a `< 3s` shutdown test pointing at a closed port. Beyond OTel, write amplification under SQLite `synchronous=FULL` is a real perceptual-latency risk on slow disks (Raspberry-Pi-class deployments); `synchronous=NORMAL` plus WAL plus a capture-overhead benchmark in CI is the answer.

## Key Findings

### Recommended Stack

The additive runtime cost is small. Cost and latency capture need zero new deps because both SDKs already return usage in-band, stdlib `statistics.quantiles()` handles p50/p95, and stdlib `json` plus `csv` plus a hand-rolled column printer cover the `usage` subcommand. Aggregations live in SQLite via `NTILE(100) OVER (...)` window functions, which ship in stdlib SQLite on Python 3.11 + 3.12 across all three target OSes. The only meaningful additions are the three OpenTelemetry pure-Python packages, ALL gated behind a new `[otel]` extra, and ALL pure-Python (HTTP exporter, not gRPC, since `grpcio` has Windows wheel gaps on fresh Pythons that would break the 3-OS install matrix).

**Core technologies:**
- `opentelemetry-sdk >=1.42,<2.0`, opt-in OTLP trace export, pure-Python, transitively pulls `protobuf` (wheels ship for every supported combo).
- `opentelemetry-exporter-otlp-proto-http >=1.42,<2.0`, HTTP not gRPC, deliberately, to keep the 3-OS install matrix clean.
- Bundled `pricing.json` shaped like LiteLLM's `model_prices_and_context_window.json`, de-facto community dataset, no new license complications, user-overridable via `$HORUS_OS_HOME/pricing.json`.
- Reuse of v0.3 stack with no version bumps: FastAPI, SQLite WAL, aiosqlite, Anthropic SDK, google-genai SDK, AdapterRegistry + LifecycleAdapter Protocol, pytest + ruff, 3-OS CI.

**Critical stack constraint:** GenAI semantic conventions (`gen_ai.*`) are still in Development status per the official OTel spec page as of May 2026. Recommendation locked in STACK: emit OTel-canonical names from our OWN `horus_os/_observability/semconv.py` constants module, NOT from the `opentelemetry-semantic-conventions` Python package's experimental namespace. One-file change the day the spec stabilizes. Additionally, `gen_ai.prompt` and `gen_ai.completion` are deprecated as of OTel semconv 1.38 (FEATURES caught this), ship `gen_ai.input.messages` and `gen_ai.output.messages` from day one if/when content capture lands.

See STACK.md for full dependency footprint, install commands, version compatibility matrix, and the section on what NOT to use (no `opentelemetry-instrumentation-*` auto-patchers, no third-party SemConv flavors, no `prometheus-client`, no Langfuse/Phoenix/Helicone SDKs).

### Expected Features

The five reference OSS projects surveyed (Langfuse, Arize Phoenix, Helicone, Lunary, AgentOps) converge on the same baseline: token counts plus USD cost plus latency plus error rate, sliced by model and by agent and by tool, viewable in a dashboard, exportable. That convergence is what makes those features table stakes. Where they diverge is on evals, guardrails, prompt playgrounds, multi-tenant workspaces, and team features, and most of those are explicit anti-features for horus-os because they violate the local-first / single-user / no-paid-account anti-goals locked in PROJECT.md.

**Must have (table stakes, all P1, all locked by PROJECT.md):**
- Token-count capture per LLM call (input, output, plus Anthropic cache-read and cache-creation columns).
- USD cost computed from a bundled, user-overridable `pricing.json`.
- End-to-end agent-run latency and per-LLM-call latency.
- Per-tool-call latency, success/error status, and last-error preview.
- p50 / p95 percentile aggregates per model, per agent, per tool.
- Tool success / error rates with last-error preview.
- New `/observability` dashboard tab (cost-by-agent, latency p50/p95, tool error-rate) plus extended numbers on the existing `/agents` tab.
- Time-window filtering (`?since=24h|7d|30d`, default 7d).
- `horus-os usage --format json|csv|table --since 7d` CLI subcommand.
- Opt-in OTel exporter as a v0.3-style adapter behind a `[otel]` extra, emitting GenAI-semconv attribute names.
- Additive v4 to v5 SQLite migration; v0.3 databases continue to read.

**Should have (differentiators, P2, ship if scope allows):**
- Cache-aware cost math (separate counters and rates for Anthropic `cache_read_input_tokens` vs `cache_creation_input_tokens`). Open question: P1 or P2?
- Most-failing-tool callout on the dashboard (one SQL aggregate, threshold gate at `call_count >= 5`).
- Slow-trace drill-in reusing the existing trace-tree renderer from v0.2 multi-agent work.
- `horus-os usage --by model|tool|agent` for the three different "where's the money / where's the time / what's broken" questions.
- Cost diff vs. prior window ("week-over-week: +$2.13, +18%").
- Bundled `pricing.json` carries `last_updated` and `release_version`; dashboard surfaces a "stale" banner past 30 days.
- CLI JSON output schema pinned by a test and documented in `docs/CLI.md`.

**Defer (anti-features, explicit boundary):**
- Multi-user / multi-tenant cost attribution (violates "Multi-tenant patterns" Out of Scope).
- Cost budgets with alerts (needs an alerting subsystem; defer to v0.5 plugin manifest).
- Custom dashboards / saved queries / query builder (we have one dashboard for one operator).
- Trace evaluation / scoring / LLM-as-judge (separate concern; pulls in eval-model API costs).
- Replay / re-run a traced LLM call from the dashboard (network side-effects).
- PII redaction / guardrails / prompt-injection detection (out of scope for observability milestone).
- Forced OTel-only mode (violates "SQLite remains the source of truth").
- Auth on the `/observability` tab (we bind localhost; auth on one tab without auth on the rest is inconsistent).

See FEATURES.md for the full prioritization matrix, the dependency graph, and the competitor analysis table.

### Architecture Approach

The shape is an in-process synchronous observation bus with three subscribers fanning out from two narrow capture sites. Capture happens at the narrowest stable boundary: `agent.run_agent_loop` wraps each `Conversation.send` call (covers both providers, both sync and async, with iteration index in scope), and `tools/loop.py:_execute_one` adds a publish after the existing `time.perf_counter()` block (no new timing code). A third, smaller capture site lives in `server/api.py:_event_stream` for the SSE path that does NOT route through `run_agent_loop`. The bus dispatches synchronously so the SQLite row is committed before the runner moves on; the OTel exporter must do its own BatchSpanProcessor queueing on its side. SQL aggregations live in SQLite via `NTILE(100) OVER (...)`, not in Python, so percentiles survive restart and zero-memory-cost over unbounded run history.

**Major components:**
1. `horus_os/observability/bus.py` (NEW), `ObservationEvent` dataclasses plus `ObservationBus`; sync publish; per-subscriber exceptions swallowed like `_call_logger` already does.
2. `horus_os/observability/persist.py` (NEW), `SQLitePersister` subscribes to all events; one row per LLM call to `llm_calls`, one row per tool call to `tool_invocations`; updates `traces` rollup columns on `RUN_END`.
3. `horus_os/observability/cost.py` + `pricing.py` + `pricing.json` (NEW), `CostAnnotator` subscribes BEFORE the persister, mutates each `LLM_CALL` event with `cost_usd` from `PricingTable` lookup; bundled pricing as package data; user override via `cfg.pricing_path` (env: `HORUS_OS_PRICING_PATH`).
4. `horus_os/observability/queries.py` (NEW), pure functions over the new tables, consumed by BOTH the dashboard routes AND the CLI subcommand so they cannot drift. SQLite-side aggregation only, no Python percentile math.
5. `horus_os/adapters/otel_adapter.py` (NEW), `LifecycleAdapter`. On `start(context)`: lazy-import OTel SDK, configure OTLP exporter from env, subscribe to `context.observation_bus`. On `stop()`: bounded `force_flush(2000)` then `shutdown()`. New optional `observation_bus: ObservationBus | None` field on `AdapterContext` (additive, defaults to None, v0.3 third-party adapters keep working byte-identical).
6. `horus_os/cli/usage.py` (NEW), `horus-os usage --since 7d --format json|csv|table`; calls the same `queries.py` module the dashboard does.
7. `server/api.py` (MODIFIED), 4 new `/api/observability/*` GET routes; SSE branch instrumented; `/api/agents` extended with rollup fields.
8. `storage.py` (MODIFIED), additive v4 to v5 migration: 4 nullable `ALTER ADD COLUMN` on `traces`, two `CREATE TABLE IF NOT EXISTS` for the new child tables. No row rewrites. v0.3 databases load unchanged; `traces.usage` JSON blob stays forever.

See ARCHITECTURE.md for the full system diagram, the 8-phase build order, the 6 architectural patterns, the 6 anti-patterns, and the 11 explicit decisions with rejected alternatives.

### Critical Pitfalls

1. **Per-iteration token totals silently undercount cost (Pitfall 1).** The v0.3 `record_trace` writes only the final iteration's `usage`. A 5-iteration run reports 1/5 of actual cost. Prevention: per-call rows in `llm_calls`, `traces.total_input_tokens = SUM(...)` on `RUN_END`, integration test asserting a 3-iteration loop with stubbed `usage={input:100,output:50}` per turn yields `traces.total_input_tokens == 300`.
2. **Streaming path silently records $0.00 (Pitfall 2).** `/api/chat/stream` does not go through `run_agent_loop`. The fix is a second narrow capture site in `server/api.py:_event_stream` that reads `stream.get_final_message().usage` (Anthropic) or post-iteration `response.usage_metadata` (Gemini). NEVER persist `0` for a non-empty stream; fall back to a char-length estimate with `estimated=1` and a yellow dashboard badge.
3. **PII leaks through OTel span attributes (Pitfall 7), highest-stakes failure mode in the milestone.** Default-deny prompt and completion bodies. Numerical and structural attributes only. Body capture requires `HORUS_OS_OTEL_CAPTURE_CONTENT=true` plus the redactor allowlist (regex-redact `AKIA[A-Z0-9]{16}`, `sk-...`, `ghp_*`, `xoxb-*`, emails, e164 phones, common API key prefixes). CI test fires a synthetic event containing `AKIAIOSFODNN7EXAMPLE`, asserts the literal string never appears in the exported span via `InMemorySpanExporter`. Non-negotiable.
4. **OTel exporter blocks the hot path or hangs on shutdown (Pitfall 6).** Two OTel-Python issues are real and tracked upstream: #3309 (60-second shutdown block when collector unreachable) and #4623 (no configurable shutdown timeout). Always `BatchSpanProcessor`, never `SimpleSpanProcessor` in production. Implement `OtelAdapter.stop()` with `provider.force_flush(timeout_millis=2000)` then `provider.shutdown()`. CI test points the adapter at `http://127.0.0.1:1` (closed port), sends one event, asserts shutdown completes in `< 3s`. Non-negotiable.
5. **Migration breaks v0.3 readers (Pitfall 11).** Every new column is nullable, no exceptions. Never DROP, never RENAME. The `traces.usage` JSON blob stays forever. Check in a `tests/fixtures/v0_3_database.sqlite3` and assert v0.4 migration is additive: new columns exist, old `usage` blob still readable, pre-v0.4 rows have NULL on new columns. Rollback survival: `pip install horus-os==0.3.0` against a v5-written database must keep reading.

Other notable pitfalls (full list in PITFALLS.md): wall-clock vs monotonic latency (Pitfall 3, lint-guarded), latency excluding parts users actually feel (Pitfall 4, contract docstring + TTFT column), `pricing.json` rot (Pitfall 5, self-disclosure banner + 14-day release-time CI gate), SQLite write amplification (Pitfall 8, `synchronous=NORMAL` + capture-overhead benchmark), tool reliability counting retries as failures (Pitfall 9, `status` enum + `retry_count` column), percentile small-sample bias (Pitfall 10, `n >= 10` threshold + render "—" below it), and OTel adapter pulling in `opentelemetry-*` without the `[otel]` extra (Pitfall 12, lazy imports + two-variant install-smoke matrix).

## Implications for Roadmap

Based on research, suggested phase structure (8 phases, mapping to ARCHITECTURE.md §9):

### Phase 1: Schema migration + persistence skeleton (v0.4.1)
**Rationale:** Capture cannot fire without tables to write into. Foundational. Also lands the SQLite pragmas (`synchronous=NORMAL` + WAL) and the lint rule banning `time.time()` in the new package so they are guarding the right files from day one.
**Delivers:** `storage.py` v4 to v5 additive migration (4 nullable columns on `traces`, two `CREATE TABLE IF NOT EXISTS` for `llm_calls` and `tool_invocations`). `observability/bus.py` with `ObservationEvent` dataclasses and `ObservationBus`. `observability/persist.py` with `SQLitePersister` writing rows. Bus is NOT yet wired into the runner; unit tests publish directly to verify the persister.
**Addresses:** STORE requirement. Foundation for METRIC, PRICE, USAGE.
**Avoids:** Pitfall 11 (additive-only migration; v0.3 fixture test in CI). Pitfall 8 (pragmas + minimum index set). Pitfall 3 (lint rule).

### Phase 2: Capture at the runner + SSE branch (v0.4.2)
**Rationale:** Cost annotation needs events to annotate. Pricing without events is dead code. This is also where the two v0.3 correctness bugs get structurally fixed.
**Delivers:** `agent.run_agent_loop` wraps each `Conversation.send` with `time.perf_counter()` and publishes `LLM_CALL`. `tools/loop.py:_execute_one` publishes `TOOL_CALL` after the existing timing. `server/api.py:_event_stream` reads terminal `usage` and publishes `LLM_CALL` for the streaming path. Capture-overhead benchmark added to CI (asserts within 50ms of recorded v0.3 baseline). `cost_usd` is still NULL at this point.
**Addresses:** METRIC requirement (primary).
**Avoids:** Pitfall 1 (per-iteration sum via child table). Pitfall 2 (SSE branch instrumented, never silent $0). Pitfall 4 (`latency_ms` contract documented on `ObservationEvent`; TTFT column considered).

### Phase 3: Pricing + cost annotation (v0.4.3)
**Rationale:** Tokens-to-dollars math closes the cost loop. `CostAnnotator` subscribes BEFORE the persister so it can mutate the event in place. Without this, every dashboard tile shows zeros.
**Delivers:** `observability/pricing.py` + bundled `observability/pricing.json` (shape borrowed from LiteLLM's `model_prices_and_context_window.json`; current Anthropic + Gemini prices; carries `version`, `updated_at`, `release_version`). `observability/cost.py` with `CostAnnotator`. `config.py` adds `pricing_path` (env: `HORUS_OS_PRICING_PATH`). `traces.total_cost_usd` rollup updated on `RUN_END`. Unknown models persist with `pricing_missing=1, cost_usd=NULL` (NULL is honest, 0 is a lie).
**Addresses:** PRICE requirement.
**Avoids:** Pitfall 5 (NULL not zero for missing models; metadata in JSON for future banner; user override path).

### Phase 4: Query module + read APIs (v0.4.4)
**Rationale:** Dashboard and CLI both consume the same `queries.py`. Build the query layer once. Routes are thin wrappers, so the dashboard can land in Phase 5 and the CLI in Phase 6 without duplicating SQL.
**Delivers:** `observability/queries.py` with `agent_totals`, `cost_by_agent`, `latency_p50_p95`, `tool_reliability`. Four new GET routes (`/api/observability/cost`, `/latency`, `/tools`, `/llm-calls`). `/api/agents` extended with rollup fields. All percentiles via `NTILE(100) OVER (...)` in SQL, never aggregated-of-aggregates.
**Addresses:** Substrate for DASH-4 and USAGE requirements.
**Avoids:** Pitfall 10 (small-sample handling, no aggregate-of-aggregates). Pitfall 9 (reliability aggregation respects `status` enum).

### Phase 5: Dashboard `/observability` tab (v0.4.5)
**Rationale:** The user-visible surface. Same vanilla-JS pattern as the v0.3 Adapters tab. Also where Pitfall 5's "pricing is N days old" banner renders.
**Delivers:** `/observability` tab with three panels (cost-by-agent bar chart, latency p50/p95 table, tool reliability list). Existing `/agents` tab gets the new columns. Window selector (24h / 7d / 30d, default 7d). 5-second poll cadence. Pricing-staleness banner. Sample-count badges on percentile cells. Pre-v0.4 trace rows render "—" with hover "no cost data captured before v0.4."
**Addresses:** DASH-4 requirement.
**Avoids:** Pitfall 5 (staleness banner). Pitfall 9 (threshold gate `call_count >= 5` for "most failing tool" callout). Pitfall 10 (render "—" for `n < 10`). Pitfall 11 (graceful NULL handling for pre-v0.4 rows).

### Phase 6: `horus-os usage` CLI (v0.4.6)
**Rationale:** CLI is half the audience. Same query layer means dashboard and CLI cannot disagree.
**Delivers:** `cli/usage.py` registered as a subparser. `horus-os usage --since 7d --format json|csv|table`. Stdlib `json.dumps` and `csv.DictWriter`; table formatter from the existing `horus-os traces` pattern. JSON output schema documented in `docs/CLI.md` and pinned by a test. Costs rounded to 6 decimal places, durations to integer ms.
**Addresses:** USAGE requirement.
**Avoids:** UX pitfall around JSON float-precision noise breaking downstream `jq` pipelines.

### Phase 7: OTel adapter (v0.4.7), highest-risk phase
**Rationale:** OTel intentionally lands LAST. By this point the bus has had six commits of stability, all consumers are exercising the same event shapes, and adding the OTel subscriber is purely additive. Shipping OTel earlier would mean wiring `AdapterContext.observation_bus` before the bus is proven internally.
**Delivers:** `adapters/otel_adapter.py` as a `LifecycleAdapter`. Lazy imports inside `start()`. Bounded shutdown (`force_flush(2000)` then `shutdown()`). Subscribes to bus on `start`, unsubscribes on `stop`. `BatchSpanProcessor` always, never `SimpleSpanProcessor` in production. `pyproject.toml` `[otel]` extra. Entry-point registered. `AdapterContext` gains optional `observation_bus: ObservationBus | None` field. Attribute set per LLM-call span: `gen_ai.system`, `gen_ai.operation.name`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.usage.cached_tokens`, `horus_os.cost_usd`, `error.type`. NO `gen_ai.input.messages`, NO `gen_ai.output.messages`, NO `gen_ai.prompt`, NO `gen_ai.completion` in default output.
**Addresses:** OTEL requirement.
**Avoids:** Pitfall 6 (bounded shutdown, BSP not SSP, `< 3s` closed-port test). Pitfall 7 (default-deny content, opt-in env var + redactor allowlist, CI test for `AKIAI*` non-appearance). Pitfall 12 (lazy imports, clean `RuntimeError` with install hint when extra missing).

**Three non-negotiable tests for this phase belong in the Success Criteria block, not just the plan:**
- PII-not-leaked: `InMemorySpanExporter` fixture, prompt contains `AKIAIOSFODNN7EXAMPLE`, default-mode export does not contain that literal.
- Bounded-shutdown: adapter pointed at `http://127.0.0.1:1`, one event published, `stop()` completes in `< 3s` wall clock.
- Two-variant install-smoke: parallel CI jobs, one with `pip install -e ".[dev]"` (no otel) and one with `".[dev,otel]"`. The no-otel variant asserts the adapter module imports AND `start(ctx)` raises a clean `RuntimeError` with a `pip install horus-os[otel]` hint, NOT a `ModuleNotFoundError`.

### Phase 8: Three-OS gate, release, migration doc (v0.4.8)
**Rationale:** The release-quality gate. Where the `pricing.json` freshness check and the two-variant install-smoke matrix live as gates rather than as advisory.
**Delivers:** `docs/MIGRATION-v0.3-to-v0.4.md`, `docs/OBSERVABILITY.md`, `docs/OTEL.md` (with the explicit "Threat model" section on what the OTel collector receives), `docs/RELEASE.md` (manual pricing-refresh procedure), `CHANGELOG.md`, version bump to `0.4.0`. `scripts/release_gate.py` carrying two checks: `pricing.json.updated_at` within 14 days of the tag date, plus the two-variant install-smoke matrix. Three-OS CI matrix (macOS + Ubuntu + Windows × Python 3.11 + 3.12) green on the full test suite plus all v0.4 tests.
**Addresses:** REL and MIG continuation requirements.
**Avoids:** Pitfall 5 (CI fails release if pricing > 14 days stale). Pitfall 12 (install-smoke matrix enforces clean no-otel install).

### Phase Ordering Rationale

- **Schema before capture (1 before 2):** capture would fail if there were no tables to insert into.
- **Capture before cost (2 before 3):** cost annotation needs events to annotate.
- **Cost before query (3 before 4):** query rollups read `total_cost_usd`. Querying nulls is allowed but uninteresting.
- **Query before dashboard AND CLI (4 before 5, 6):** dashboard and CLI both consume `queries.py`. Module must exist; routes optional but parallel.
- **Dashboard and CLI in either order (5, 6):** they share the query layer and do not depend on each other.
- **OTel last (7):** opt-in surface; shipping earlier would wire `AdapterContext.observation_bus` before the bus is proven internally. By Phase 7 the bus has had six commits of stability.
- **Release gate last (8):** can only validate what already exists.

This order also delivers a usable slice after each phase: after Phase 2 you can SELECT row-level data from SQLite; after Phase 3 cost numbers exist; after Phase 4 you can curl the routes; after Phase 5 you see the dashboard; after Phase 6 you can pipe `horus-os usage` to `jq`; after Phase 7 OTel works; after Phase 8 you ship.

### Research Flags

Phases likely needing deeper research during planning:

- **Phase 2 (capture):** Validate whether `retry_count` is recoverable from the Anthropic SDK without monkey-patching the transport. PITFALLS explicitly recommends validating this at plan time. If not recoverable, Pitfall 4's `retry_count` column degrades to "best-effort or omitted." Also: measure the v0.3 capture-overhead baseline BEFORE v0.4 changes land, so the Phase-2 benchmark has something to assert against.
- **Phase 3 (pricing):** Open question on cache-aware cost math, is the separate accounting for `cache_read_input_tokens` vs `cache_creation_input_tokens` P1 or P2? Anthropic prompt caching is 90% cheaper to read and ~25% more to write; collapsing both into "input tokens" silently undercounts or overcounts. If users on Anthropic caching is a meaningful subset, this is P1; if not, P2.
- **Phase 4 (queries):** Open question on whether `total_cost_usd` and `total_duration_ms` live as columns on `traces` (current ARCHITECTURE choice) or in a separate `trace_aggregates` table. Tradeoff: write amplification on `traces` UPDATE vs. join cost on read. Validate at plan time with a benchmark.
- **Phase 7 (OTel):** Highest-risk phase. Already heavily researched in STACK, FEATURES, and PITFALLS, but the three non-negotiable tests need explicit test design before plan-time. Also: `OTEL_SEMCONV_STABILITY_OPT_IN` dual-emission is NOT in scope for v0.4 (we are not "existing instrumentation"), but plan-time should confirm we do not paint ourselves into a corner.

Phases with standard patterns (no research-phase needed during planning):

- **Phase 1 (schema):** Mirrors v3 to v4 pattern in `storage.py:125-152` exactly. Idempotent `ALTER ADD COLUMN` + `CREATE TABLE IF NOT EXISTS`.
- **Phase 5 (dashboard):** Same vanilla-JS pattern as the v0.3 Adapters tab. No new tech.
- **Phase 6 (CLI):** Same subparser pattern as existing `cli/init.py`, `cli/run.py`. Stdlib only.
- **Phase 8 (release gate):** Same release process as v0.1, v0.2, v0.3.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | OTel SDK, exporter, semconv status all verified directly against current PyPI plus the official spec page (2026-05-24). SDK shapes verified against Anthropic and Google Gen AI docs. Three-OS wheel availability confirmed. |
| Features | HIGH | Five reference OSS projects surveyed with cited docs. Anti-features ruled out against PROJECT.md "Out of Scope" verbatim. MEDIUM only on exact UX of cost-budget alerts and slow-trace drill-in where OSS implementations diverge (those are P2 anyway). |
| Architecture | HIGH | Grounded in direct source reads of `agent.py`, `tools/loop.py`, `tools/registry.py`, `storage.py`, `server/api.py`, `_providers/_anthropic.py`. The two v0.3 bugs (per-iteration token overwrite, missing tool latency persistence) were surfaced from source, not inferred. LOW only on OTel Python SDK lifecycle shutdown semantics, where the verification path is implementation-time testing in Phase 7. |
| Pitfalls | HIGH | Cross-referenced against OTel Python issue tracker (#3309, #4623), OneUptime + maketocreate + Last9 writeups, Langfuse + Helicone docs, Anthropic + Gemini SDK behaviour, and the v0.3 source-read findings in ARCHITECTURE. MEDIUM only on precise blast-radius numbers for a single-user desktop deployment shape. |

**Overall confidence:** HIGH

### Gaps to Address

- **Cache-aware cost math priority:** P1 or P2? Resolve during requirements definition. If P1, expand Phase 3 to carry the two extra columns and the per-rate pricing-JSON shape; if P2, document as a deferred enhancement.
- **`total_cost_usd` / `total_duration_ms` placement:** columns on `traces` vs. separate `trace_aggregates` table. Resolve during Phase 4 planning with a small benchmark on the existing dataset shape.
- **Anthropic SDK `retry_count` recoverability:** validate during Phase 2 planning. If not recoverable without monkey-patching, downgrade Pitfall 4's retry-count column to "best-effort or omitted" and document.
- **v0.3 capture-overhead baseline measurement:** must be recorded BEFORE Phase 2 capture lands so the Phase-2 CI benchmark has a pinned reference. One-shot measurement, take it during Phase 1.
- **OTel `OTEL_SEMCONV_STABILITY_OPT_IN` posture:** not in scope for v0.4, but Phase 7 planning should confirm the constants module (`horus_os/_observability/semconv.py`) is structured so adding dual-emission later is a one-file change.

## Sources

### Primary (HIGH confidence)
- Direct source reads of `/Users/santino/Projects/horus-os/src/horus_os/{agent.py, tools/loop.py, tools/registry.py, storage.py, server/api.py, _providers/_anthropic.py, types.py}` and `/Users/santino/Projects/horus-os/ARCHITECTURE.md`, v0.3 surface shape, the two confirmed v0.3 bugs.
- `/open-telemetry/opentelemetry-python` (Context7), OTLP exporter setup, `TracerProvider` config, `BatchSpanProcessor`, gRPC vs HTTP exporter constructors, span attribute setting.
- [OTel GenAI semconv index](https://opentelemetry.io/docs/specs/semconv/gen-ai/), [GenAI client spans spec](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/), [GenAI metrics spec](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-metrics/), [Python OTLP exporter guide](https://opentelemetry.io/docs/languages/python/exporters/), Development-status confirmation, attribute-stability map.
- [opentelemetry-sdk](https://pypi.org/project/opentelemetry-sdk/) + [opentelemetry-exporter-otlp-proto-http](https://pypi.org/project/opentelemetry-exporter-otlp-proto-http/) on PyPI, 1.42.1, pure-Python, three-OS wheel availability.
- [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python) + [Claude streaming docs](https://docs.anthropic.com/en/api/messages-streaming), `response.usage` and `stream.get_final_message().usage` access paths.
- [Google Gen AI SDK docs](https://googleapis.github.io/python-genai/) + [Gemini token docs](https://ai.google.dev/gemini-api/docs/tokens), `usage_metadata` shape.
- [opentelemetry-python #3309](https://github.com/open-telemetry/opentelemetry-python/issues/3309) and [#4623](https://github.com/open-telemetry/opentelemetry-python/issues/4623), the 60s-shutdown-block and configurability-gap bugs behind Pitfall 6.

### Secondary (MEDIUM confidence)
- OSS LLM-observability project docs surveyed: [Langfuse token & cost tracking](https://langfuse.com/docs/observability/features/token-and-cost-tracking), [Arize Phoenix](https://arize.com/docs/phoenix), [Helicone](https://github.com/Helicone/helicone), [Lunary in PostHog roundup](https://posthog.com/blog/best-open-source-llm-observability-tools), [AgentOps](https://github.com/agentops-ai/agentops).
- [LiteLLM `model_prices_and_context_window.json`](https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json), [tokencost](https://github.com/AgentOps-AI/tokencost), pricing dataset shape.
- [OpenLLMetry #3515](https://github.com/traceloop/openllmetry/issues/3515), `gen_ai.prompt` / `gen_ai.completion` deprecation.
- [maketocreate: OpenTelemetry GenAI without leaking PII](https://maketocreate.com/opentelemetry-genai-tracing-ai-agents-without-leaking-pii/), [OneUptime: Redact Sensitive Prompts](https://oneuptime.com/blog/post/2026-02-06-redact-sensitive-prompts-genai-opentelemetry-traces/view), [OneUptime: Prevent Data Loss in Seven OTel Scenarios](https://oneuptime.com/blog/post/2026-02-06-prevent-data-loss-opentelemetry-scenarios/view), Pitfall 7 grounding.
- [Last9: Latency Percentiles are Incorrect P99 of the Times](https://last9.io/blog/your-percentiles-are-incorrect-p99-of-the-times/), Pitfall 10 grounding.
- [phiresky: SQLite performance tuning](https://phiresky.github.io/blog/2020/sqlite-performance-tuning/), Pitfall 8 (`synchronous=NORMAL` rationale).
- [PEP 418](https://peps.python.org/pep-0418/) + [Ceph PR #22121](https://github.com/ceph/ceph/pull/22121), Pitfall 3 (monotonic vs wall clock).
- [Helicone retries docs](https://docs.helicone.ai/features/advanced-usage/retries), Pitfall 9 (retry-aware reliability counting).
- [implicator.ai: Anthropic Usage-Based Billing Is Exact](https://www.implicator.ai/anthropics-usage-based-billing-is-exact-its-plan-limits-are-vague-by-design/), Pitfall 1 cross-check rationale.

### Tertiary (LOW confidence)
- OTel Python SDK lifecycle shutdown semantics, verified via SDK docs convention, will need confirmation at Phase 7 implementation time.
- Precise blast-radius numbers on a single-user desktop deployment, single-user shape makes production-scale anecdotes hard to source; pitfall prevention is conservative as a result.

*Research completed: 2026-05-25*
*Ready for roadmap: yes*
