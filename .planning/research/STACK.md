# Stack Research

**Domain:** v0.4 Observability — cost tracking, latency, tool reliability, opt-in OTel exporter
**Researched:** 2026-05-24
**Confidence:** HIGH (OTel SDK, exporter, semconv status all verified against current PyPI + official spec; SDK shapes verified against Anthropic and Google Gen AI docs)

## Scope of This Research

v0.4 builds on the validated v0.3 stack (Python 3.11+, FastAPI, SQLite WAL, aiosqlite, Anthropic SDK, google-genai SDK, Next.js dashboard, Adapter Protocol with lifecycle hooks, pytest+ruff, 3-OS CI). This file lists **only the additive dependencies** v0.4 needs. Everything in v0.3's `pyproject.toml` stays as-is.

The headline finding: the additive cost is small. Cost+latency capture needs zero new runtime deps (SDKs already return what we need, stdlib `statistics.quantiles()` computes p50/p95, `csv`+`json`+a hand-rolled column printer handle the `usage` subcommand). The only meaningful new deps are the OTel SDK trio behind a new `[otel]` extra, opt-in by design.

## Recommended Stack

### Core Additions

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| (none) | — | Cost + latency capture in the hot path | The Anthropic SDK exposes `response.usage.input_tokens` / `output_tokens` and Gemini exposes `response.usage_metadata.{prompt,candidates,cached_content,total}_token_count`. Both numbers are returned in-band on every call. Pricing math is a dict lookup against `pricing.json`. Latency is `time.perf_counter()` deltas. Adding a runtime dep here would be all cost and no value. |
| (none) | — | Percentile computation (p50, p95) | `statistics.quantiles(data, n=100)` from the Python stdlib (3.8+) returns 99 cut points, p50 = index 49, p95 = index 94. We persist raw latency samples in SQLite and compute percentiles in-process on the dashboard request. No numpy/scipy/pandas — those would be ~30 MB of native deps for one math op the stdlib already covers. |
| (none) | — | CLI `horus-os usage` output (JSON / CSV / table) | `json.dumps` and `csv.DictWriter` are stdlib. The table renderer is a 30-line column-width function (already the established pattern in v0.2's `horus-os traces` and v0.3's `horus-os agents`; adding Rich here would inconsistent-up the CLI surface). |

### Optional `[otel]` Extra (NEW)

These are the ONLY new dependencies the milestone needs, and they ship behind `pip install horus-os[otel]`. Core install stays slim.

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `opentelemetry-api` | `>=1.42,<2.0` | OTel API surface — `Tracer`, `Span`, `context` propagation | Required by the SDK. Pinned via the SDK transitively. |
| `opentelemetry-sdk` | `>=1.42,<2.0` | OTel SDK — `TracerProvider`, `BatchSpanProcessor`, `Resource` | Builds the in-process trace pipeline. The 1.42.x line shipped 2026-05-21 and is the current stable API. |
| `opentelemetry-exporter-otlp-proto-http` | `>=1.42,<2.0` | OTLP exporter over HTTP/protobuf | **HTTP not gRPC** — gRPC variant pulls `grpcio`, which lacks pre-built wheels on some Windows / Python combos and triggers a C-toolchain build. HTTP variant pulls only `requests` + `protobuf` and installs clean on all three OSes. Endpoint is the user's existing OTel collector (`OTEL_EXPORTER_OTLP_ENDPOINT`). |
| `opentelemetry-semantic-conventions` | (transitive, `>=0.63b0`) | Constants for HTTP/server/error attribute names | Pulled in by the SDK. We do NOT need it directly for GenAI attributes (see "What NOT to Use" below — GenAI semconv is still Development). |

That's the full new dependency footprint for v0.4.

### Reused From v0.3 (no version bumps required)

| Existing dep | How v0.4 uses it |
|--------------|------------------|
| `fastapi>=0.110` | New `/api/observability/*` routes mounted on the existing app. No new web framework. |
| SQLite via stdlib `sqlite3` + `aiosqlite` | Two additive tables (`llm_calls`, `tool_calls`) and one schema-version bump v4→v5. Same WAL+busy-timeout pragmas. |
| `anthropic>=0.40` | Read `response.usage.input_tokens` / `output_tokens`. Streaming path reads `final_message.usage` once the stream drains. |
| `google-genai>=0.3` | Read `response.usage_metadata.prompt_token_count` / `candidates_token_count` / `cached_content_token_count` / `total_token_count`. |
| Adapter Protocol with `start`/`stop` hooks (v0.3 / Phase 22) | The OTel exporter ships as a `LifecycleAdapter`: `start(ctx)` builds the `TracerProvider`, adds a `BatchSpanProcessor(OTLPSpanExporter(...))`, registers it as the global tracer; `stop()` calls `provider.shutdown()` to flush. Same lifecycle slot the Discord adapter uses today. |
| `pytest>=8.0` + `pytest-asyncio` | All new tests follow existing pattern. |

## Installation

```bash
# Core install — unchanged, observability is built in
pip install horus-os

# Opt-in OTel export — NEW extra
pip install "horus-os[otel]"

# Combined install (everything)
pip install "horus-os[all,otel]"
```

`pyproject.toml` diff is small:

```toml
[project.optional-dependencies]
# ... existing extras unchanged ...
otel = [
    "opentelemetry-sdk>=1.42,<2.0",
    "opentelemetry-exporter-otlp-proto-http>=1.42,<2.0",
]
all = [
    # ... existing entries ...
    "opentelemetry-sdk>=1.42,<2.0",
    "opentelemetry-exporter-otlp-proto-http>=1.42,<2.0",
]

[project.entry-points."horus_os.adapters"]
# ... existing entries ...
otel = "horus_os.adapters.otel_adapter:OtelAdapter"
```

## Integration Points

### 1. Capturing cost + latency in the v0.3 runtime

The hooks land in two narrowly-scoped places, no v0.3 API breakage:

- **Per LLM call** — `_providers/_anthropic.py` and `_providers/_gemini.py` already wrap the SDK call. Wrap that call in `time.perf_counter()` and, after it returns, extract `usage.input_tokens` / `usage.output_tokens` (Anthropic) or `usage_metadata.prompt_token_count` / `candidates_token_count` (Gemini), look up unit price from the in-memory `pricing.json`, and write one row to `llm_calls` (provider, model, input_tokens, output_tokens, cost_usd, latency_ms, trace_id). Existing `ProviderResponse` shape unchanged — observability data is persisted, not returned.
- **Per tool call** — `tools/registry.execute_tool_uses` is the single dispatcher for every tool the agent invokes. Wrap each handler call with `time.perf_counter()` + try/except, and write one row to `tool_calls` (tool_name, success, latency_ms, error_kind, trace_id). The v0.3 `delegate_to_agent` parallel path already runs through a `ThreadPoolExecutor`; the wrapper goes inside the per-future code path so concurrent tool calls each get their own timing.
- **Per agent run** — `agent.run_agent_loop` and `run_agent_stream` are the two top-level entry points. The existing `TraceRecord` already records per-iteration latency; v0.4 adds `total_duration_ms` and `total_cost_usd` aggregates to the `traces` row at loop exit. Schema migration is additive (new columns, NULL on v0.3 rows).

All three hooks add ~5 lines each. No refactor required.

### 2. OTel exporter as an Adapter

This is the elegant part — the v0.3 lifecycle hooks (`start`/`stop` from Phase 22) are exactly what OTel needs. `OtelAdapter` is a ~60-line file:

```python
# horus_os/adapters/otel_adapter.py
class OtelAdapter:
    name = "otel"
    def bind(self, app, context): pass  # bind-time work is none
    async def start(self, context):
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        self._provider = TracerProvider(resource=Resource.create({
            "service.name": "horus-os",
            "service.version": _version(),
        }))
        self._provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        trace.set_tracer_provider(self._provider)
    async def stop(self):
        self._provider.shutdown()
```

The provider+tool+agent hook layer above checks `trace.get_tracer_provider()` and, if a real provider is present, emits a span alongside writing the SQLite row. If the OTel extra isn't installed, the tracer is the no-op default and the cost is one attribute set per span. Honors standard `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS`, `OTEL_SERVICE_NAME` env vars — users with an existing collector configure nothing.

This pattern means the v0.4 observability hooks live in core (always on, writing to SQLite); OTel export is purely additive (lifecycle adapter, opt-in). v0.5's plugin manifest is unaffected.

### 3. Pricing table sourcing strategy

`pricing.json` is bundled as package data (same as the v0.3 dashboard static assets) at `src/horus_os/data/pricing.json`:

```json
{
  "anthropic": {
    "claude-opus-4-7": {"input_per_mtok_usd": 15.00, "output_per_mtok_usd": 75.00},
    "claude-sonnet-4-5": {"input_per_mtok_usd": 3.00, "output_per_mtok_usd": 15.00}
  },
  "gemini": {
    "gemini-2.5-pro": {"input_per_mtok_usd": 1.25, "output_per_mtok_usd": 10.00}
  }
}
```

**Sourcing process at release time (manual, ~5 min per release):**
1. Pull current prices from https://www.anthropic.com/pricing#api and https://ai.google.dev/pricing
2. Diff against `pricing.json` on `main`
3. Update + commit + tag

A scrape script is tempting but both vendors block scrapers and change page structure quarterly — manual curation is faster and more reliable for a release cadence of weeks-to-months. Document the process in `docs/RELEASE.md` so any contributor can cut a release.

**User override:** `config.pricing_path` env / config key. If set, the file is loaded at startup with the bundled file as fallback per (provider, model) key. Users tracking custom pricing (private endpoints, negotiated rates) override only the rows they care about.

### 4. SQLite schema migration (additive, v4 → v5)

```sql
-- v5: observability tables
CREATE TABLE IF NOT EXISTS llm_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cached_tokens INTEGER,
    cost_usd REAL NOT NULL,
    latency_ms INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    error_kind TEXT
);
CREATE INDEX IF NOT EXISTS idx_llm_calls_created_at ON llm_calls(created_at);
CREATE INDEX IF NOT EXISTS idx_llm_calls_trace_id ON llm_calls(trace_id);

CREATE TABLE IF NOT EXISTS tool_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    success INTEGER NOT NULL,
    latency_ms INTEGER NOT NULL,
    error_kind TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tool_calls_created_at ON tool_calls(created_at);
CREATE INDEX IF NOT EXISTS idx_tool_calls_tool_name ON tool_calls(tool_name);

-- Additive columns on existing traces table
ALTER TABLE traces ADD COLUMN total_duration_ms INTEGER;
ALTER TABLE traces ADD COLUMN total_cost_usd REAL;
```

Idempotent — same `ADD COLUMN IF NOT EXISTS` pattern as v3/v4. v0.3 databases load unchanged; the new columns are NULL on old rows, dashboard treats NULL as "not measured" so historical traces stay visible.

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `opentelemetry-exporter-otlp-proto-http` | `opentelemetry-exporter-otlp-proto-grpc` | Only if the user has a gRPC-only collector AND grpcio installs cleanly on their box. HTTP works against every backend that speaks OTLP (Honeycomb, Grafana Tempo, Datadog, Jaeger, the OTel Collector itself), so the gRPC path is unjustified default complexity. |
| Bundled `pricing.json` + manual release-time refresh | Live scrape on startup; pull from a vendor "/v1/pricing" API | Both vendors lack stable pricing endpoints; scraping their pricing pages is brittle and against ToS. A bundled file users can override is the local-first answer. |
| Stdlib `statistics.quantiles` | `numpy.percentile` or `pandas.quantile` | A user already running numpy in their venv can compute their own. We don't pull a 30 MB binary dep for one math op. |
| Hand-rolled column printer for `horus-os usage --format=table` | `rich`, `tabulate` | The existing CLI (`horus-os traces`, `horus-os agents`) renders tables with a stdlib helper. Adding `rich` for one new subcommand fragments the CLI look; adding it as a project-wide dep forces it onto users who only want `init` + `run`. |
| `OTelAdapter` as a `LifecycleAdapter` (entry point) | Hard-wire OTel into `server/api.py` lifespan | The v0.3 adapter contract is the right abstraction. Hard-wiring would force `opentelemetry-*` imports at app-create time (breaks `pip install horus-os` without the `[otel]` extra). |
| `OTEL_SEMCONV_STABILITY_OPT_IN` dual-emission for GenAI attribute names | Adopt unstable GenAI names as primary today | The GenAI semantic conventions are in **Development** as of May 2026 (verified against opentelemetry.io spec page). Emitting only the unstable names risks breaking when they go stable. Dual-emit when we eventually feel pressure from users; for v0.4, ship our own clear attribute names (see "GenAI semconv adoption" below). |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `opentelemetry-instrumentation-*` (auto-instrumentation packages) | They monkey-patch SDKs at import time. Our `_providers/_anthropic.py` and `_providers/_gemini.py` are thin wrappers — manual instrumentation in 3 known places beats opaque auto-patching of two vendor SDKs whose major versions move quarterly. | Manual spans in the provider wrappers. |
| `opentelemetry-instrumentation-google-genai` (specific package, exists) | Same reason. Adds an extra dep, owns the import chain, surprises debug sessions. Premature for a system with two providers and one in-house tool registry. | Manual `tracer.start_as_current_span()` calls in the wrappers. |
| `opentelemetry-semantic-conventions-ai` (third-party, Traceloop) | Reasonable library, but it's a third-party SemConv flavor that competes with the official OTel GenAI spec. Adopting it now means a future migration when official SemConv goes stable. | Hand-roll attribute names that match the current OTel GenAI spec where reasonable, switch when stable. |
| `langfuse-python`, `arize-phoenix`, `helicone-python`, vendor SDKs | Each pulls a service dependency. Anti-goal: no paid third-party account. Local-first SQLite is the source of truth; OTel is the bridge to whatever the user already runs. | SQLite + opt-in OTel. |
| `prometheus-client` | Prometheus is a pull model — needs an exposed `/metrics` endpoint, requires Prometheus on the other side, doesn't carry traces. We need traces + metrics together, OTel does both. | OTel metrics export (later milestone if users ask). |
| `pandas`, `numpy` | Heavy native deps for one percentile call. Three-OS install matrix gets fragile. | `statistics.quantiles`. |
| `grpcio` (via the gRPC OTLP exporter) | Native compile dep, occasional Windows wheel gaps; doubles install time on the OTel extra. | `opentelemetry-exporter-otlp-proto-http` (pure-Python + protobuf). |
| `python-json-logger` / `structlog` for telemetry | We're not emitting structured logs — we're persisting structured rows in SQLite. Different problem. | Direct SQLite writes. |
| `aiocache` / `cachetools` for pricing lookup | A dict in module-level state with a 5-minute reload on mtime change is six lines. A cache library is two layers of abstraction over a dict. | In-memory dict + mtime check. |

## GenAI semconv adoption: ship now, semconv later

**Verified 2026-05-24 against https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/** — the entire GenAI client-span spec is marked **"Status: Development"** at the top of the page. Only `error.type`, `server.address`, and `server.port` are stable across GenAI spans. `gen_ai.system`, `gen_ai.operation.name`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.client.token.usage` (metric) are all in Development.

**Our position for v0.4:**

1. **Emit OTel-canonical attribute names where they exist today, even if Development.** They're widely adopted by Datadog, Honeycomb, Grafana, OpenObserve, New Relic, Dynatrace — every consumer of OTLP that cares about LLM data already keys off these names. Risk of name churn is real but bounded; the spec change cadence on GenAI is months, not weeks.
2. **Don't depend on the SemConv Python package's GenAI constants** — the official `opentelemetry-semantic-conventions` Python package (0.63b0) does include some GenAI constants but they're under the `.experimental` namespace and may rename. Use string literals in one constants module of our own (`horus_os/_observability/semconv.py`) so when the spec stabilizes, one file changes.
3. **Be ready for `OTEL_SEMCONV_STABILITY_OPT_IN`** — the spec mandates that any instrumentation supporting the eventual stable names support this env var for dual-emission. We don't need to implement it in v0.4 (we're not "existing instrumentation"), but the constants module pattern makes it a one-evening add when needed.

**Attribute set we emit per LLM-call span (Development today, stable target):**

| Attribute | Source | Notes |
|-----------|--------|-------|
| `gen_ai.system` | "anthropic" or "google_genai" | matches spec value list |
| `gen_ai.operation.name` | "chat" | only operation we make today |
| `gen_ai.request.model` | model name string | exact model id as sent to SDK |
| `gen_ai.usage.input_tokens` | from SDK response | Anthropic `usage.input_tokens`, Gemini `usage_metadata.prompt_token_count` |
| `gen_ai.usage.output_tokens` | from SDK response | Anthropic `usage.output_tokens`, Gemini `usage_metadata.candidates_token_count` |
| `gen_ai.usage.cached_tokens` | Gemini `usage_metadata.cached_content_token_count` | NULL for Anthropic |
| `horus_os.cost_usd` | computed | our extension — no spec value for this |
| `error.type` | exception class name on failure | this one IS stable |

Per-tool spans use OTel-canonical naming where possible: span name is the tool name, `code.function` is the handler, `horus_os.tool.success` is a bool. No GenAI spec covers tools yet — agent + framework spans are still Development.

## Three-OS CI Compatibility

| Dep | Ubuntu wheel | macOS wheel | Windows wheel | Native compile risk |
|-----|--------------|-------------|---------------|---------------------|
| `opentelemetry-api` 1.42.1 | pure Python | pure Python | pure Python | none |
| `opentelemetry-sdk` 1.42.1 | pure Python | pure Python | pure Python | none |
| `opentelemetry-exporter-otlp-proto-http` 1.42.1 | pure Python (pulls `requests`, `protobuf`) | pure Python | pure Python | none — `protobuf` ships wheels for every CPython 3.11/3.12 combo on all three OSes |
| `opentelemetry-semantic-conventions` (transitive) | pure Python | pure Python | pure Python | none |

The HTTP exporter choice (not gRPC) is the key one — `grpcio` has historically had Windows wheel gaps on fresh Python releases. HTTP path keeps the OTel extra `pip install` clean on the existing 3-OS Python-3.11+3.12 matrix.

**Install-smoke job update needed:** add `[otel]` extra to the smoke matrix as a separate variant (don't bloat the default-install variant). One job: `pip install -e ".[otel,dev]"` + import-check `from opentelemetry import trace` + adapter discovery confirms `otel` is registered.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `opentelemetry-sdk 1.42.x` | `opentelemetry-api 1.42.x` | They must move together; the SDK pins API to the same minor. |
| `opentelemetry-exporter-otlp-proto-http 1.42.x` | `opentelemetry-sdk 1.42.x` | Same — pinned via setup. |
| `opentelemetry-sdk >=1.42,<2.0` | `protobuf >=5.0` (transitive) | Pre-built wheels exist for CPython 3.11+3.12 on all 3 OSes. Verified May 2026. |
| `anthropic>=0.40` (existing) | Returns `response.usage.input_tokens` / `output_tokens` | Stable shape since 0.20. No bump needed for v0.4. |
| `google-genai>=0.3` (existing) | Returns `response.usage_metadata.prompt_token_count` / `candidates_token_count` / `cached_content_token_count` / `total_token_count` | Confirmed stable as of May 2026; `cached_content_token_count` is None when no cache hit. |

## Stack Patterns by Variant

**If the user runs no observability backend:**
- Install `horus-os` (no extra)
- Cost + latency + tool reliability still captured in SQLite
- View at `/observability` in the local dashboard
- Export with `horus-os usage --since 7d --format csv`

**If the user runs an OTel collector / Grafana Tempo / Honeycomb / SigNoz / Datadog:**
- Install `horus-os[otel]`
- Set `OTEL_EXPORTER_OTLP_ENDPOINT` env var (HTTP, e.g. `http://localhost:4318`)
- Optionally set `OTEL_EXPORTER_OTLP_HEADERS` (auth) and `OTEL_SERVICE_NAME` (defaults to "horus-os")
- Spans flow to their backend; SQLite stays as local source of truth
- Same adapter on/off toggle as Discord/Slack via `/api/adapters/otel/disable`

**If the user wants custom pricing (private endpoint, negotiated rate, future provider):**
- Drop a `pricing.json` at `config.pricing_path` (env: `HORUS_OS_PRICING_PATH`)
- File is merged over bundled one per (provider, model)
- Reloaded on file mtime change (no restart needed)

## Sources

**Context7 (HIGH confidence):**
- `/open-telemetry/opentelemetry-python` — OTLP exporter setup, `TracerProvider` config, `BatchSpanProcessor`, gRPC vs HTTP exporter constructors, span attribute setting

**Official spec pages (HIGH confidence):**
- [GenAI semantic conventions (overview)](https://opentelemetry.io/docs/specs/semconv/gen-ai/) — confirms Development status, mandates `OTEL_SEMCONV_STABILITY_OPT_IN` dual-emission for migration
- [GenAI client spans spec](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/) — verified attribute-level stability: only `error.type`, `server.address`, `server.port` are Stable; all `gen_ai.*` attributes are Development
- [GenAI metrics spec](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-metrics/) — `gen_ai.client.token.usage` histogram still Development as of May 2026
- [OpenTelemetry Python Exporters guide](https://opentelemetry.io/docs/languages/python/exporters/) — current exporter packages and config patterns

**Official PyPI (HIGH confidence):**
- [opentelemetry-sdk on PyPI](https://pypi.org/project/opentelemetry-sdk/) — 1.42.1 released 2026-05-21, supports Python 3.10+
- [opentelemetry-exporter-otlp-proto-http on PyPI](https://pypi.org/project/opentelemetry-exporter-otlp-proto-http/) — 1.42.1, pure-Python deps
- [opentelemetry-exporter-otlp-proto-grpc on PyPI](https://pypi.org/project/opentelemetry-exporter-otlp-proto-grpc/) — 1.42.1, pulls `grpcio` (the reason we don't pick this one)
- [opentelemetry-semantic-conventions on PyPI](https://pypi.org/project/opentelemetry-semantic-conventions/) — 0.63b0 as of 2026-05-19

**SDK shape verification (HIGH confidence):**
- [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python) + [Claude API token-counting docs](https://docs.anthropic.com/en/api/messages-count-tokens) — confirms `response.usage.input_tokens` / `output_tokens` are the documented access path on every call (including the `final_message` of a stream)
- [Google Gen AI SDK docs](https://googleapis.github.io/python-genai/) + [Gemini token docs](https://ai.google.dev/gemini-api/docs/tokens) — confirms `response.usage_metadata.{prompt,candidates,cached_content,total}_token_count` shape

**stdlib reference (HIGH confidence):**
- [Python statistics module — quantiles()](https://docs.python.org/3/library/statistics.html) — confirms `quantiles(data, n=100)` returns 99 cut points sufficient for p50/p95 without any external dep

**Cross-checks (MEDIUM confidence — independent commentary corroborates the official spec status):**
- [OpenTelemetry GenAI Observability blog (otel.io)](https://opentelemetry.io/blog/2026/genai-observability/) — vendor-agreed attribute names even while spec is Development
- [Greptime: How OTel Traces LLM Calls (May 2026)](https://www.greptime.com/blogs/2026-05-09-opentelemetry-genai-semantic-conventions) — independent confirmation that production usage of Development-status GenAI attributes is standard practice in mid-2026

---
*Stack research for: v0.4 Observability on horus-os*
*Researched: 2026-05-24*
