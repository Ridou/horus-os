# Requirements

## v0.1 Foundation

### Core runtime (CORE)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| CORE-01 | Run as a single Python process on macOS, Ubuntu, Windows 11 | active | 01, 10 |
| CORE-02 | Accept user prompts via a CLI command and return a structured result | active | 07 |
| CORE-03 | Accept user prompts via a local web chat and return a streaming result | active | 08 |
| CORE-04 | Configure via a single `.env` file | active | 09 |
| CORE-05 | Run with user-supplied API keys (Anthropic and Google Gemini both supported) | active | 02, 09 |

### Agent (AGENT)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| AGENT-01 | One named agent can invoke at least one registered tool | active | 02, 04 |
| AGENT-02 | Every agent run produces a structured trace stored in SQLite | active | 02, 03 |
| AGENT-03 | Agent runtime supports both Anthropic SDK and Google Gemini SDK | active | 02 |

### Tool registry (TOOL)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| TOOL-01 | Register a Python callable as a tool with a JSON schema | active | 04 |
| TOOL-02 | Every tool invocation is logged with input, output, and duration | active | 04 |
| TOOL-03 | At least one example tool ships: read a local file | active | 04 |

### Memory (MEM)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| MEM-01 | Agent can search a markdown notes folder and read individual files | active | 05 |
| MEM-02 | Agent can append to a markdown notes folder | active | 06 |
| MEM-03 | Every memory write is reviewable in the dashboard | active | 06, 08 |

### Dashboard (DASH)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| DASH-01 | Local Next.js dashboard lists recent agent runs and their traces | active | 08 |
| DASH-02 | Dashboard hosts a chat surface that sends prompts to the agent runtime | active | 08 |
| DASH-03 | Dashboard renders each trace with full input, output, and tool invocations | active | 08 |

### Setup wizard (WIZARD)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| WIZARD-01 | `horus-os init` walks a new user through configuration | active | 09 |
| WIZARD-02 | Wizard validates API keys with a live ping before saving | active | 09 |
| WIZARD-03 | Wizard provides direct hyperlinks to Anthropic console and Google AI Studio | active | 09 |
| WIZARD-04 | Wizard is idempotent and resumable (state in `.horus-init-state.json`) | active | 09 |

### Test and CI (TEST)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| TEST-01 | Lint passes (ruff) on Ubuntu, macOS, Windows in GitHub Actions | active | 01 |
| TEST-02 | Unit tests pass (pytest) on Ubuntu, macOS, Windows in GitHub Actions | active | 01 |
| TEST-03 | Fresh-VM install completes on Ubuntu 22.04, macOS, Windows 11 | active | 10 |

### Release (REL)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| REL-01 | Tag v0.1.0 and write release notes | active | 11 |
| REL-02 | Public GitHub repo published with README, LICENSE, CONTRIBUTING | active | 11 |

## v0.2 Multi-Agent + Streaming

### Multi-agent (MA)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| MA-01 | Named agent profiles persist in SQLite (name, system prompt, default model, allowed tools, memory scope) | active | 12 |
| MA-02 | A coordinator agent can delegate to one or more sub-agents via a registered tool | active | 13 |
| MA-03 | Every multi-agent run produces a trace with parent/child linkage | active | 13 |
| MA-04 | At least one default agent profile is auto-created on `horus-os init` | active | 12 |

### Streaming (STREAM)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| STREAM-01 | `run_agent_stream` yields incremental tokens from Anthropic and Gemini | active | 14 |
| STREAM-02 | CLI `run` shows streamed output by default; `--no-stream` falls back to v0.1 behavior | active | 15 |
| STREAM-03 | Dashboard chat surface renders streamed tokens live | active | 16 |

### Adapter (ADAPT)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| ADAPT-01 | Plugin contract defined via `horus_os.adapters` entry point | active | 17 |
| ADAPT-02 | One reference adapter ships: HTTP webhook receiver | active | 17 |
| ADAPT-03 | Third-party adapters register without forking horus-os | active | 17 |

### Migration (MIG)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| MIG-01 | v0.1 SQLite database upgrades to v0.2 schema idempotently | active | 12 |
| MIG-02 | v0.1 single-agent traces remain readable in the v0.2 dashboard | active | 12, 16 |
| MIG-03 | Migration is one-way; downgrade is not supported and is documented | active | 18 |

### Test and CI (continued from v0.1)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| TEST-04 | Multi-agent end-to-end tests pass on three-OS matrix | active | 19, 20 |
| TEST-05 | Streaming tests pass on three-OS matrix | active | 19, 20 |
| TEST-06 | Adapter contract tests pass on three-OS matrix | active | 19, 20 |

### Release (continued from v0.1)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| REL-03 | Tag v0.2.0 with CHANGELOG and GitHub Release | active | 21 |
| REL-04 | Migration notes documented for v0.1 users | active | 18, 21 |

## v0.3 Adapter Ecosystem

### Adapter Runtime (ART)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| ART-01 | Adapter Protocol gains optional `start(ctx)` and `stop()` lifecycle hooks; v0.2 adapters work unchanged | active | 22 |
| ART-02 | FastAPI lifespan invokes `start` on each discovered adapter at startup and `stop` at shutdown | active | 22 |
| ART-03 | `GET /api/adapters` returns name, status, last_activity_at, error_count per adapter | active | 22, 27 |

### Discord (DISC)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| DISC-01 | Discord bot connects, listens for mentions and DMs, replies via configured agent | active | 23 |
| DISC-02 | Setup guide documents bot creation, intents, and token env var | active | 23, 28 |
| DISC-03 | Disconnects trigger exponential-backoff reconnect with configurable cap | active | 23 |

### Slack (SLAK)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| SLAK-01 | Slack Events API endpoint handles `app_mention` and DM events | active | 24 |
| SLAK-02 | Signature verification via signing-secret HMAC-SHA256 over body and timestamp | active | 24 |
| SLAK-03 | Slash command support routing to an agent profile | active | 24 |

### Email (MAIL)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| MAIL-01 | Email adapter polls IMAP inbox, runs agent on new messages | active | 25 |
| MAIL-02 | Replies sent via SMTP preserve `In-Reply-To` and `References` headers | active | 25 |
| MAIL-03 | Configurable poll interval; sleeps cleanly when no messages | active | 25 |

### Calendar (CAL)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| CAL-01 | Calendar adapter exposes `list_calendar_events_today` tool returning structured events | active | 26 |
| CAL-02 | Optional event creation tool, gated behind `HORUS_OS_CALENDAR_WRITE_ALLOWED=true` | active | 26 |

### Dashboard v0.3 (DASH-3)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| DASH-3-01 | `/adapters` dashboard view lists adapters with status, last activity, error count | active | 27 |
| DASH-3-02 | Enable/disable toggle from dashboard via `POST /api/adapters/{name}/{enable,disable}` | active | 27 |

### Test and CI (continued)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| TEST-07 | Discord adapter mocked-SDK tests pass on three-OS matrix | active | 29, 30 |
| TEST-08 | Slack adapter mocked-SDK tests pass on three-OS matrix | active | 29, 30 |
| TEST-09 | Email adapter mocked tests pass on three-OS matrix | active | 29, 30 |
| TEST-10 | Calendar adapter mocked tests pass on three-OS matrix | active | 29, 30 |

### Release (continued)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| REL-05 | Tag v0.3.0 with CHANGELOG and GitHub Release | validated | 31 |
| REL-06 | Migration notes documented for v0.2 users (additive Protocol change) | validated | 28, 31 |

## v0.4 Observability

### Capture instrumentation (METRIC)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| METRIC-01 | Every LLM call captures input_tokens, output_tokens, cache_read_input_tokens, cache_creation_input_tokens, latency_ms, model, provider, status | active | TBD |
| METRIC-02 | Every tool call captures duration_ms, status (success or error), retry_count (best-effort, may be NULL if SDK does not expose it), last_error_text on failure | active | TBD |
| METRIC-03 | Capture lands on the agent_runner path AND on the streaming SSE path (server/api.py:_event_stream); streamed runs never silently record $0 | active | TBD |
| METRIC-04 | Per-iteration LLM-call rows roll up to per-trace totals on RUN_END; fixes the v0.3 record_trace bug where only the final iteration's usage was recorded | active | TBD |
| METRIC-05 | Capture overhead stays within 50ms of the v0.3 baseline (BASELINE-01), asserted in a CI benchmark on the 3-OS matrix | active | TBD |

### Storage and migration (STORE)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| STORE-01 | New `llm_calls` child table keyed by `trace_id`, one row per LLM call | active | TBD |
| STORE-02 | New `tool_invocations` child table keyed by `trace_id`, one row per tool call | active | TBD |
| STORE-03 | Four nullable rollup columns on `traces`: total_input_tokens, total_output_tokens, total_cost_usd, total_duration_ms | active | TBD |
| STORE-04 | All schema changes additive (ADD COLUMN IF NOT EXISTS, CREATE TABLE IF NOT EXISTS); v0.3 databases load unchanged; old `traces.usage` JSON blob preserved forever | active | TBD |
| STORE-05 | SQLite pragmas set to `synchronous=NORMAL` + WAL; never `synchronous=FULL` | active | TBD |

### Pricing and cost (PRICE)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| PRICE-01 | Bundled `pricing.json` shipped as package data; schema mirrors LiteLLM's `model_prices_and_context_window.json` | active | TBD |
| PRICE-02 | Cost computed per LLM call from token counts times pricing-table rates, including separate cache_read and cache_creation rates (cache-aware) | active | TBD |
| PRICE-03 | Unknown models persist `pricing_missing=1` with `cost_usd=NULL`; NULL is honest, zero is a lie | active | TBD |
| PRICE-04 | User can override the pricing table via env `HORUS_OS_PRICING_PATH` or config field | active | TBD |
| PRICE-05 | Pricing table carries `version`, `updated_at`, `release_version` metadata; dashboard surfaces a stale-banner past 30 days | active | TBD |

### Observability dashboard (DASH-4)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| DASH-4-01 | New `/observability` tab with three panels: cost-by-agent, latency p50/p95, tool reliability | active | TBD |
| DASH-4-02 | Window selector (24h / 7d / 30d, default 7d) drives all panels | active | TBD |
| DASH-4-03 | Percentile cells with n < 10 samples render as "—", not as a number | active | TBD |
| DASH-4-04 | Existing `/agents` tab gains cost + latency columns from rollups | active | TBD |
| DASH-4-05 | Pre-v0.4 trace rows render "—" for new columns with hover "no cost data captured before v0.4" | active | TBD |

### Usage CLI (USAGE)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| USAGE-01 | `horus-os usage --since 7d` returns a usage report over a configurable window | active | TBD |
| USAGE-02 | `--format json|csv|table` controls output shape; JSON schema documented in `docs/CLI.md` and pinned by a test | active | TBD |
| USAGE-03 | `--by model|tool|agent` slices the report into per-model, per-tool, or per-agent views | active | TBD |
| USAGE-04 | Costs rounded to 6 decimal places, durations to integer ms, consistent units across all formats | active | TBD |

### OpenTelemetry exporter (OTEL)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| OTEL-01 | Opt-in OTel adapter ships behind `pip install horus-os[otel]`; bare install has zero `opentelemetry-*` deps | active | TBD |
| OTEL-02 | Adapter implements v0.3 LifecycleAdapter; `start(ctx)` configures OTLP HTTP exporter from env and subscribes to ObservationBus; `stop()` does `force_flush(2000)` then `shutdown()` | active | TBD |
| OTEL-03 | Default-deny content capture: prompt and completion bodies are NEVER attached to spans by default | active | TBD |
| OTEL-04 | Content capture opt-in via `HORUS_OS_OTEL_CAPTURE_CONTENT=true` AND a redactor allowlist (`AKIA[A-Z0-9]{16}`, `sk-...`, `ghp_*`, `xoxb-*`, emails, e164 phones, common API-key prefixes) | active | TBD |
| OTEL-05 | Span attribute names use OTel-canonical GenAI conventions sourced from internal `horus_os/_observability/semconv.py`; never the deprecated `gen_ai.prompt` / `gen_ai.completion` | active | TBD |
| OTEL-06 | `BatchSpanProcessor` always; `SimpleSpanProcessor` never used in production | active | TBD |
| OTEL-07 | Without the `[otel]` extra, importing the adapter module succeeds and `start(ctx)` raises a clean `RuntimeError` with a `pip install horus-os[otel]` hint (not `ModuleNotFoundError`) | active | TBD |

### Baseline measurement (BASELINE)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| BASELINE-01 | A `tests/perf/v0_3_baseline.json` artifact captures v0.3 latency overhead for 3-iteration agent loops with no observability; committed before Phase 2 instrumentation lands; METRIC-05 asserts against it | active | TBD |

### Test and CI (continued from v0.3)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| TEST-11 | v0.3 SQLite fixture (`tests/fixtures/v0_3_database.sqlite3`) loads cleanly under v0.4 migration; new columns NULL on old rows; old `usage` JSON preserved | active | TBD |
| TEST-12 | Capture-overhead benchmark on 3-OS matrix (asserts METRIC-05) | active | TBD |
| TEST-13 | PII-not-leaked test: `InMemorySpanExporter` fixture, prompt contains `AKIAIOSFODNN7EXAMPLE`, default-mode OTel export does not contain the literal (asserts OTEL-03 and OTEL-04) | active | TBD |
| TEST-14 | Bounded-shutdown test: OTel adapter pointed at closed port (`http://127.0.0.1:1`), one event published, `stop()` completes in < 3s wall clock (asserts OTEL-02) | active | TBD |
| TEST-15 | Two-variant install-smoke matrix: parallel CI jobs for `[dev]` and `[dev,otel]`; the no-otel variant asserts the adapter module imports AND `start(ctx)` raises the `RuntimeError` hint (asserts OTEL-07) | active | TBD |

### Migration (continued from v0.2)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| MIG-04 | v0.3 SQLite databases upgrade to v0.4 (v5) schema idempotently; multiple runs of the migration are a no-op after the first; downgrade not supported and documented | active | TBD |

### Release (continued from v0.3)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| REL-07 | Tag v0.4.0 with CHANGELOG and GitHub Release; migration notes for v0.3 users documented | active | TBD |
| REL-08 | `scripts/release_gate.py` enforces (a) `pricing.json.updated_at` within 14 days of tag date AND (b) a green two-variant install-smoke matrix | active | TBD |
| REL-09 | `docs/OTEL.md` includes a "Threat model" section covering what an OTel collector receives in default and content-capture-enabled modes | active | TBD |

## Coverage summary

| Category | Total | Active | Validated |
|----------|-------|--------|-----------|
| CORE | 5 | 5 | 5 |
| AGENT | 3 | 3 | 3 |
| TOOL | 3 | 3 | 3 |
| MEM | 3 | 3 | 3 |
| DASH | 3 | 3 | 3 |
| WIZARD | 4 | 4 | 4 |
| TEST | 15 | 15 | 10 |
| REL | 9 | 9 | 6 |
| MA | 4 | 4 | 4 |
| STREAM | 3 | 3 | 3 |
| ADAPT | 3 | 3 | 3 |
| MIG | 4 | 4 | 3 |
| ART | 3 | 3 | 3 |
| DISC | 3 | 3 | 3 |
| SLAK | 3 | 3 | 3 |
| MAIL | 3 | 3 | 3 |
| CAL | 2 | 2 | 2 |
| DASH-3 | 2 | 2 | 2 |
| METRIC | 5 | 5 | 0 |
| STORE | 5 | 5 | 0 |
| PRICE | 5 | 5 | 0 |
| DASH-4 | 5 | 5 | 0 |
| USAGE | 4 | 4 | 0 |
| OTEL | 7 | 7 | 0 |
| BASELINE | 1 | 1 | 0 |
| **Total** | **107** | **107** | **66** |

"Validated" means the requirement is covered by a shipped phase. v0.1 and v0.2 shipped 2026-05-23 (tags `v0.1.0`, `v0.2.0`); v0.3 shipped 2026-05-24 (tag `v0.3.0`). v0.4 requirements stay unvalidated until their phases ship.
