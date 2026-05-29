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
| METRIC-01 | Every LLM call captures input_tokens, output_tokens, cache_read_input_tokens, cache_creation_input_tokens, latency_ms, model, provider, status | active | 33 |
| METRIC-02 | Every tool call captures duration_ms, status (success or error), retry_count (best-effort, may be NULL if SDK does not expose it), last_error_text on failure | active | 33 |
| METRIC-03 | Capture lands on the agent_runner path AND on the streaming SSE path (server/api.py:_event_stream); streamed runs never silently record $0 | active | 33 |
| METRIC-04 | Per-iteration LLM-call rows roll up to per-trace totals on RUN_END; fixes the v0.3 record_trace bug where only the final iteration's usage was recorded | active | 33 |
| METRIC-05 | Capture overhead stays within 50ms of the v0.3 baseline (BASELINE-01), asserted in a CI benchmark on the 3-OS matrix | active | 33 |

### Storage and migration (STORE)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| STORE-01 | New `llm_calls` child table keyed by `trace_id`, one row per LLM call | active | 32 |
| STORE-02 | New `tool_invocations` child table keyed by `trace_id`, one row per tool call | active | 32 |
| STORE-03 | Four nullable rollup columns on `traces`: total_input_tokens, total_output_tokens, total_cost_usd, total_duration_ms | active | 32 |
| STORE-04 | All schema changes additive (ADD COLUMN IF NOT EXISTS, CREATE TABLE IF NOT EXISTS); v0.3 databases load unchanged; old `traces.usage` JSON blob preserved forever | active | 32 |
| STORE-05 | SQLite pragmas set to `synchronous=NORMAL` + WAL; never `synchronous=FULL` | active | 32 |

### Pricing and cost (PRICE)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| PRICE-01 | Bundled `pricing.json` shipped as package data; schema mirrors LiteLLM's `model_prices_and_context_window.json` | active | 34 |
| PRICE-02 | Cost computed per LLM call from token counts times pricing-table rates, including separate cache_read and cache_creation rates (cache-aware) | active | 34 |
| PRICE-03 | Unknown models persist `pricing_missing=1` with `cost_usd=NULL`; NULL is honest, zero is a lie | active | 34 |
| PRICE-04 | User can override the pricing table via env `HORUS_OS_PRICING_PATH` or config field | active | 34 |
| PRICE-05 | Pricing table carries `version`, `updated_at`, `release_version` metadata; dashboard surfaces a stale-banner past 30 days | active | 34 |

### Observability dashboard (DASH-4)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| DASH-4-01 | New `/observability` tab with three panels: cost-by-agent, latency p50/p95, tool reliability | active | 36 |
| DASH-4-02 | Window selector (24h / 7d / 30d, default 7d) drives all panels | active | 36 |
| DASH-4-03 | Percentile cells with n < 10 samples render as "—", not as a number | active | 36 |
| DASH-4-04 | Existing `/agents` tab gains cost + latency columns from rollups | active | 35 |
| DASH-4-05 | Pre-v0.4 trace rows render "—" for new columns with hover "no cost data captured before v0.4" | active | 36 |

### Usage CLI (USAGE)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| USAGE-01 | `horus-os usage --since 7d` returns a usage report over a configurable window | active | 37 |
| USAGE-02 | `--format json|csv|table` controls output shape; JSON schema documented in `docs/CLI.md` and pinned by a test | active | 37 |
| USAGE-03 | `--by model|tool|agent` slices the report into per-model, per-tool, or per-agent views | active | 37 |
| USAGE-04 | Costs rounded to 6 decimal places, durations to integer ms, consistent units across all formats | active | 37 |

### OpenTelemetry exporter (OTEL)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| OTEL-01 | Opt-in OTel adapter ships behind `pip install horus-os[otel]`; bare install has zero `opentelemetry-*` deps | active | 38 |
| OTEL-02 | Adapter implements v0.3 LifecycleAdapter; `start(ctx)` configures OTLP HTTP exporter from env and subscribes to ObservationBus; `stop()` does `force_flush(2000)` then `shutdown()` | active | 38 |
| OTEL-03 | Default-deny content capture: prompt and completion bodies are NEVER attached to spans by default | active | 38 |
| OTEL-04 | Content capture opt-in via `HORUS_OS_OTEL_CAPTURE_CONTENT=true` AND a redactor allowlist (`AKIA[A-Z0-9]{16}`, `sk-...`, `ghp_*`, `xoxb-*`, emails, e164 phones, common API-key prefixes) | active | 38 |
| OTEL-05 | Span attribute names use OTel-canonical GenAI conventions sourced from internal `horus_os/_observability/semconv.py`; never the deprecated `gen_ai.prompt` / `gen_ai.completion` | active | 38 |
| OTEL-06 | `BatchSpanProcessor` always; `SimpleSpanProcessor` never used in production | active | 38 |
| OTEL-07 | Without the `[otel]` extra, importing the adapter module succeeds and `start(ctx)` raises a clean `RuntimeError` with a `pip install horus-os[otel]` hint (not `ModuleNotFoundError`) | active | 38 |

### Baseline measurement (BASELINE)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| BASELINE-01 | A `tests/perf/v0_3_baseline.json` artifact captures v0.3 latency overhead for 3-iteration agent loops with no observability; committed before Phase 2 instrumentation lands; METRIC-05 asserts against it | active | 32 |

### Test and CI (continued from v0.3)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| TEST-11 | v0.3 SQLite fixture (`tests/fixtures/v0_3_database.sqlite3`) loads cleanly under v0.4 migration; new columns NULL on old rows; old `usage` JSON preserved | active | 32 |
| TEST-12 | Capture-overhead benchmark on 3-OS matrix (asserts METRIC-05) | active | 33 |
| TEST-13 | PII-not-leaked test: `InMemorySpanExporter` fixture, prompt contains `AKIAIOSFODNN7EXAMPLE`, default-mode OTel export does not contain the literal (asserts OTEL-03 and OTEL-04) | active | 38 |
| TEST-14 | Bounded-shutdown test: OTel adapter pointed at closed port (`http://127.0.0.1:1`), one event published, `stop()` completes in < 3s wall clock (asserts OTEL-02) | active | 38 |
| TEST-15 | Two-variant install-smoke matrix: parallel CI jobs for `[dev]` and `[dev,otel]`; the no-otel variant asserts the adapter module imports AND `start(ctx)` raises the `RuntimeError` hint (asserts OTEL-07) | active | 38 |

### Migration (continued from v0.2)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| MIG-04 | v0.3 SQLite databases upgrade to v0.4 (v5) schema idempotently; multiple runs of the migration are a no-op after the first; downgrade not supported and documented | active | 32 |

### Release (continued from v0.3)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| REL-07 | Tag v0.4.0 with CHANGELOG and GitHub Release; migration notes for v0.3 users documented | active | 39 |
| REL-08 | `scripts/release_gate.py` enforces (a) `pricing.json.updated_at` within 14 days of tag date AND (b) a green two-variant install-smoke matrix | active | 39 |
| REL-09 | `docs/OTEL.md` includes a "Threat model" section covering what an OTel collector receives in default and content-capture-enabled modes | active | 39 |

## v0.5 Plugin System

### Manifest schema (MANIFEST)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| MANIFEST-01 | `horus-plugin.toml` declares `manifest_version: int` (required from day one), `name`, `version`, `description`, `author`, `license`, `homepage`, `issue_tracker` | complete | 41 |
| MANIFEST-02 | `horus_os_compat` declares supported horus-os range as a PEP 440 specifier string (e.g. `">=0.5,<0.6"`) parsed via `packaging.SpecifierSet`; mismatch yields validation error before load | complete | 41 |
| MANIFEST-03 | `[contributions]` table declares plugin's tool entry points and adapter entry points by reference (dotted path); duplicates against built-ins refused by loader | complete | 41 |
| MANIFEST-04 | `[capabilities]` array lists requested capabilities by string; every entry must be a member of `capability_catalog.py` closed enum or validation fails | complete | 41 |
| MANIFEST-05 | Pydantic v2 schema validation runs at install time and at every server boot; errors surface line-numbered, plain-English messages via `format_validation_error()` | complete | 41 |

### Discovery (DISCOVERY)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| DISCOVERY-01 | Server discovers plugins via `importlib.metadata.entry_points(group="horus_os.plugins")` (canonical path for pip-installed plugins); `pkg_resources` is lint-banned | complete | 42 |
| DISCOVERY-02 | Server discovers dev plugins via filesystem walk of `~/.horus-os/plugins/<name>/` (each contains a `horus-plugin.toml` + Python package); loaded via `importlib.util.spec_from_file_location` | complete | 42 |

### Installer flow (INSTALL)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| INSTALL-01 | `horus-os plugins install <pip-spec>` wraps `pip install --require-virtualenv` via `subprocess.run([sys.executable, "-m", "pip", ...])` (single chokepoint in `run_pip`); refuses outside a venv (`sys.prefix == sys.base_prefix` check) with `--allow-system-python` escape hatch | complete | 44 |
| INSTALL-02 | Two-phase install: phase A `pip download --no-deps` → phase B validate manifest + show requested capabilities + grant prompt → phase C `pip install --no-deps --no-build-isolation <wheel>`; aborts cleanly on phase B refusal | complete | 44 |
| INSTALL-03 | Sdist (`*.tar.gz`) refused by default; `--allow-sdist` flag required to bypass; wheels containing `.pth` files in RECORD also refused | complete | 44 |
| INSTALL-04 | Installer refuses any spec that would downgrade horus-os runtime deps (pydantic, packaging); `pip freeze` sha256 captured pre/post install for rollback verification (silent_rollback + runtime_dep_changed branches) | complete | 44 |
| INSTALL-05 | First-install grant prompt lists each requested capability with plain-English `capability_catalog.py` description; user types `y` to grant all or per-capability tokens; refusing any capability aborts install (no half-grant state) | complete | 44 |
| INSTALL-06 | `horus-os plugins {uninstall,list,info,enable,disable,update,grant,revoke}` subcommands; `update` runs the upgrade-diff (PERMISSION-02) | complete | 44 |

### Permission model (PERMISSION)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| PERMISSION-01 | Default-deny posture enforced by `DEFAULT_GRANT_POLICY = "deny"` constant; helper shims (`ctx.filesystem`, `ctx.secrets`, `ctx.net`, `ctx.process`, `ctx.env`) raise `PermissionDenied` if grant row missing | complete | 43 |
| PERMISSION-02 | Grants persisted in `plugin_capabilities` table keyed on `(plugin_name, plugin_version, capability)` AND tied to `manifest_hash = sha256(capabilities_set)`; manifest-hash diff on upgrade flips previously-granted rows to `pending` and triggers re-prompt | complete | 43 |
| PERMISSION-03 | Grants revocable from `/plugins` dashboard tab and via `horus-os plugins revoke <name> <capability>`; revocation takes effect on next plugin run (no in-flight cancellation needed) | complete | 43 |
| PERMISSION-04 | `capability_catalog.py` is the single source of truth for the closed enum of capability strings; v0.5 ships at minimum `filesystem.read`, `filesystem.write`, `net.outbound`, `secrets.read`; each entry carries a plain-English description surfaced at the prompt | complete | 43 |

### Failure isolation (ISOLATE)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| ISOLATE-01 | Plugin import failure, manifest validation failure, or `start()` exception NEVER crashes horus-os; failed plugin appears in `/api/plugins` with `status="error"` and structured `error_phase` (discover/validate/permission/load/start), lifespan continues | complete | 42, 43 |
| ISOLATE-02 | Plugin `start()` and `stop()` wrapped in `asyncio.wait_for(..., timeout=2.0)` matching v0.4 Phase 38 OtelAdapter shape; timeout or exception → `status="error", error_phase="start"`, lifespan continues | complete | 43 |
| ISOLATE-03 | Per-plugin enable/disable persisted in `plugins.enabled` column; disabled plugins skip discovery (no half-loaded state); `--disable-all-plugins` CLI flag as escape hatch | complete | 43 |
| ISOLATE-04 | Plugin runtime exceptions inside tool invocations absorbed by existing `ObservationBus.publish` exception-swallow at `observability/bus.py:174-181`; per-plugin error rate surfaced in `/api/plugins/{name}.health` and `/observability` | complete | 42 |

### Plugins dashboard tab (DASH-5)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| DASH-5-01 | `/plugins` dashboard tab lists installed plugins with version, declared contributions (tools + adapters), granted capabilities (chips), lifecycle status, last error preview, and error rate over selected window | complete | 45 |
| DASH-5-02 | Enable/disable toggle per plugin from dashboard; grant modal lists per-capability state with revoke buttons | complete | 45 |
| DASH-5-03 | Plugin tile renders hyperlinks from manifest `author`, `homepage`, `issue_tracker` fields (no inline rendering of arbitrary URLs from plugin code, only from validated manifest fields) | complete | 45 |

### Observability extension (OBSERVE)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| OBSERVE-01 | `plugin_name TEXT NULL` column added to `llm_calls` and `tool_invocations`; NULL = "horus-os core" (pre-v0.5 rows roll up under that); index `idx_tool_invocations_plugin(plugin_name, created_at)` for rollup query speed | complete | 41 |
| OBSERVE-02 | `/api/observability/plugins` route returns per-plugin error rate (last 7d, 30d window) + p50/p95 latency; `/observability` dashboard tab gains a "by plugin" rollup tile alongside existing "by agent" and "by tool" tiles | complete | 45 |

### Reference plugin (REFERENCE)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| REFERENCE-01 | `examples/horus-os-example-plugin/` shipped as a separate package with its own `pyproject.toml` and `horus-plugin.toml`; demonstrates four scenarios (simple tool + capability check, config-reading tool, lifecycle adapter with start/stop, plugin registering both tool + adapter) | complete | 48 |
| REFERENCE-02 | `docs/PLUGINS.md` is the plugin-author guide; covers manifest, capabilities catalog, lifecycle hooks, testing, walkthrough of each reference plugin scenario in order; embedded `horus-plugin.toml` snippet diffs against the example plugin in CI | complete | 47 |

### Migration (continued from v0.4)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| MIG-05 | v0.4 SQLite databases upgrade to v0.5 (v6) schema idempotently; additive only (three new tables + two NULLABLE columns + one index); v0.4 fixture (`tests/fixtures/v0_4_database.sqlite3`) loads cleanly; multiple runs of the migration are a no-op after the first | complete | 41 |

### Baseline measurement (continued from v0.4)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| BASELINE-02 | A `tests/perf/v0_4_baseline.json` artifact captures v0.4 cold-start time + discovery overhead with zero plugins; committed before Phase 42 discovery lands; cold-start regression test asserts against it | complete | 40 |

### Test and CI (continued from v0.4)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| TEST-16 | Three-tier test fixtures shipped: tier 1 in-process unit tests against `PluginSpec` objects; tier 2 `fake_plugin_entry_points` monkeypatch fixture; tier 3 `clean_venv` fixture (opt-in via `@pytest.mark.installer_e2e`) for real `pip install` E2E | complete | 46 |
| TEST-17 | `tests/test_plugin_pitfalls/` directory contains one regression test per documented pitfall in `.planning/research/PITFALLS.md` (minimum 12 tests); test names map 1:1 to pitfall numbers | complete | 46 |
| TEST-18 | Cold-start benchmark: full discovery + validation + load pass with zero installed plugins completes in <100ms wall clock on Ubuntu CI runner; regression fails CI | complete | 42 |
| TEST-19 | Broken-plugin fixtures verify ISOLATE-01: synthetic plugins with invalid TOML, schema-failing manifest, import-raising module, `start()`-raising adapter, `start()`-hanging adapter — each must surface as `status="error"` without crashing the host | complete | 42, 43 |
| TEST-20 | Three-OS install-smoke job (macOS + Ubuntu + Windows × Python 3.11 + 3.12) installs `examples/horus-os-example-plugin` via `pip install -e ./examples/horus-os-example-plugin` and asserts plugin appears in `/api/plugins` with `status="running"` | complete | 49 |
| TEST-21 | Reference plugin CI lint rejects any `from horus_os` import that doesn't come from `horus_os.plugins.api` (the single public API surface); enforced by ruff `flake8-tidy-imports.banned-api` (layer 1) + pytest source-tree backstop at `tests/plugins/test_reference_plugin_public_api_only.py` (layer 2) | complete | 48 |

### Release (continued from v0.4)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| REL-10 | Tag v0.5.0 with CHANGELOG and GitHub Release; `docs/MIGRATION-v0.4-to-v0.5.md` documents v5→v6 schema migration + the two new direct deps (`pydantic>=2.7,<3`, `packaging>=24.0`) | complete | 50 |
| REL-11 | `scripts/release_gate.py` extended with: (a) docs-drift check between `MANIFEST_V1_SCHEMA` runtime constant and `docs/manifest-v1.schema.json`; (b) plugin install-smoke on each OS from TEST-20; (c) reference plugin manifest validates against the runtime schema; (d) v0.4 fixture round-trip survives the v5→v6 migration | complete | 49 |
| REL-12 | `docs/PLUGIN-SECURITY.md` includes a "Threat model" section with the literal sentence "plugins execute in the horus-os Python process" and enumerates the capability-grant trust contract; linked from the install-prompt screen | complete | 47 |

## v0.6 Contribution Gate

### CI hardening (CIHARD)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| CIHARD-01 | `pull_request_target` is FORBIDDEN by default across every workflow; release-gate lint rejects any new occurrence unless guarded by a `# SECURITY:` comment AND a `safe-to-test` label gate; v0.6 ships ZERO `pull_request_target` triggers (v0.5 tests use recorded provider responses) | active | TBD |
| CIHARD-02 | Top-level `permissions: read-all` set on `.github/workflows/ci.yml`, `audit.yml`, `release.yml`; per-job opt-in for any write scope; lint asserts no workflow inherits the legacy GITHUB_TOKEN default scope | active | TBD |
| CIHARD-03 | Every `actions/checkout` step sets `persist-credentials: false` unless explicitly required for push; no `${{ github.event.pull_request.* }}` interpolation appears in any `run:` shell line | active | TBD |
| CIHARD-04 | Every third-party `uses:` is pinned to a 40-character commit SHA (`@<sha>` exact match); release-gate `actions-pinned-by-sha` check rejects any `@v<N>`, `@main`, `@master`, or short-SHA pin; `pinact` is documented as the local maintainer refresh tool | active | TBD |
| CIHARD-05 | `actionlint` runs on every PR via a new workflow lint job; failures block merge; covers untrusted-input interpolation, expired action references, missing `permissions:` | active | TBD |

### Signing substrate (SIGN)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| SIGN-01 | NEW `.github/workflows/release.yml` triggered on `release: types: [published]`; signs wheel + sdist + SBOM JSON via `sigstore/gh-action-sigstore-python@<sha>` (sigstore-python >=4.2,<5); produces `.sigstore` bundle (NOT detached `.sig`); sign step runs within 5 minutes of `id-token: write` OIDC mint | active | TBD |
| SIGN-02 | `actions/attest-build-provenance@<sha>` generates SLSA Build L2 provenance attestations bound to the GitHub workflow identity; verifiable via `gh attestation verify`; runs for every signed artifact | active | TBD |
| SIGN-03 | Tag signing via `gitsign` (Sigstore keyless, OIDC); no long-lived GPG keypair required; `docs/RELEASE.md` STOP-BEFORE-TAG block documents the gitsign-configured `git tag` invocation; tag verification uses workflow-scoped identity | active | TBD |
| SIGN-04 | `scripts/verify_release.py` (NEW) is a 5-check user-facing trust-chain verifier with workflow-scoped EXACT-match `EXPECTED_IDENTITY = "https://github.com/Ridou/horus-os/.github/workflows/release.yml@refs/tags/{version}"` (no wildcards, no regex); mandatory `--cert-oidc-issuer` flag; negative test rejects wrong-identity fixture | active | TBD |
| SIGN-05 | PyPI Trusted Publishing (PEP 807) is OUT OF SCOPE for v0.6 (horus-os does not currently publish to PyPI); deferral documented in `.planning/decisions/no-pypi-in-v0.6.md`; v0.7+ may revisit | active | TBD |

### Supply-chain SBOM (SBOM)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| SBOM-01 | Release-time SBOM generated via `cyclonedx-bom` (`cyclonedx-py environment`) against a FRESH `pip install <wheel>` venv (NOT `pip freeze` of the dev venv); CycloneDX 1.6 JSON format locked; signed via sigstore in the same `release.yml` job | active | TBD |
| SBOM-02 | Two SBOMs ship per release: clean install (`pip install <wheel>`) AND extras install (`pip install <wheel>[dev,otel]`); both attached to the GitHub Release alongside their `.sigstore` bundles; matches existing two-variant install-smoke convention | active | TBD |
| SBOM-03 | `actions/attest-sbom@<sha>` generates SBOM attestations bound to the artifact each SBOM describes; release-gate diffs SBOM contents against the published wheel's actual installed dependency tree | active | TBD |

### Supply-chain scanning (SUPPLY)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| SUPPLY-01 | NEW `.github/workflows/audit.yml` runs `pypa/gh-action-pip-audit@<sha>` (pip-audit >=2.10,<3) on every PR in dual-mode (`-s osv` AND `-s pypi`); failures block merge; `pip-audit` added to `[dev]` extras for local use | active | TBD |
| SUPPLY-02 | `actions/dependency-review-action@<sha>` runs on every PR with explicit license allowlist (Apache-2.0, MIT, BSD-2-Clause, BSD-3-Clause, ISC, PSF-2.0); rejects new deps under unlisted licenses | active | TBD |
| SUPPLY-03 | `.github/pip-audit-ignore.txt` is the ignore-list with mandatory dated-comment discipline (every entry includes `# YYYY-MM-DD: <reason>`); release-gate rejects undated entries; `.github/pip-audit-tracking/` directory carries fix-tracking docs for unfixable transitives | active | TBD |
| SUPPLY-04 | `pip-audit` runs on BOTH `[dev]` AND `[dev,otel]` install variants to match the existing two-variant install-smoke pattern; matches the Phase 39 OTel-variant precedent | active | TBD |

### Dependabot + zizmor (DEPBOT)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| DEPBOT-01 | `.github/dependabot.yml` v2 with `package-ecosystem: pip` (groups: `ai-sdks` for anthropic + google-genai, `otel`, `web-stack`, `dev-tools`; cooldown 3 days default, 14 days majors; `applies-to: version-updates`) AND `package-ecosystem: github-actions` (SHA-pin refresh, weekly cadence) | active | TBD |
| DEPBOT-02 | Security updates are explicitly UN-grouped (no `applies-to: security-updates` matcher); one PR per CVE; PRs gain a distinct `security-update` label; CVE PRs never hide inside a weekly grouped bump | active | TBD |
| DEPBOT-03 | `zizmor` workflow runs on every PR + on `.github/workflows/**` edits; static-analysis findings block merge; complements actionlint by covering known-bad expression interpolation patterns | active | TBD |

### Contributor docs + templates (CONTRIB)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| CONTRIB-01 | `CONTRIBUTING.md` rewritten: claim flow ("comment to claim, maintainer assigns"), branch policy, commit format (conventional commits, present tense, no em-dashes per CLAUDE.md), test/doc/changelog expectations; honest solo-maintainer language ("aim to acknowledge within 7 days"); NO 24-hour SLA, NO CLA, Discord optional | active | TBD |
| CONTRIB-02 | `.github/PULL_REQUEST_TEMPLATE.md` NOTICE block removed at gate-flip; gains a checklist (tests added/updated, docs updated if user-visible, CHANGELOG `[Unreleased]` entry added if user-visible, license header on new files), and a reference to CONTRIBUTING.md + CODE_OF_CONDUCT.md | active | TBD |
| CONTRIB-03 | `.github/ISSUE_TEMPLATE/` carries three forms: `bug.yml`, `feature.yml`, `security.yml` (security form redirects to GHSA private-vulnerability-reporting); banners flipped at gate-flip to drop "not accepting contributions" | active | TBD |
| CONTRIB-04 | `.github/CODEOWNERS` NEW with PATH-SCOPED ownership (workflows, scripts/release_gate.py, scripts/verify_release.py, SECURITY.md, .planning/), NOT `* @Ridou` blanket assignment; reviewers auto-assigned by directory | active | TBD |
| CONTRIB-05 | `docs/TRIAGE.md` NEW: label taxonomy with ≤15 hard cap (type:bug, type:feature, area:adapters, area:dashboard, area:cli, good-first-issue, help-wanted, security-update, breaking, blocked, needs-info, waiting-for-author, accepted, claimed, wontfix); `good-first-issue` rubric; weekly Sunday triage cadence; "may go silent up to 2 weeks" disclaimer; NO `actions/stale` auto-close | active | TBD |
| CONTRIB-06 | `docs/LABEL-TAXONOMY.md` documents the label set + when each applies + saved-reply text for common scenarios (claim accepted, claim conflict, missing repro, stale-but-real bug) | active | TBD |
| CONTRIB-07 | `.planning/decisions/` directory carries one-page rationale files: `no-cla.md`, `no-stale-bot.md`, `sigstore-keyless.md`, `sbom-cyclonedx.md`, `no-pypi-in-v0.6.md`; referenced from CONTRIBUTING.md and PROJECT.md key-decisions table | active | TBD |

### SECURITY disclosure refresh (SECDISC)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| SECDISC-01 | `SECURITY.md` "(not active yet)" / staged-pipeline section deleted at gate-flip; replaced with active vulnerability-disclosure flow pointing at GitHub Security Advisories private reporting | active | TBD |
| SECDISC-02 | Severity-tier SLOs replace any blanket SLO: "aim to acknowledge within 7 days"; fix targets critical 14d / high 30d / medium 90d / low no commitment; coordinated disclosure 90-day default; over-capacity acknowledgement language explicit ("if we go silent, file a public issue tagged `security-update-followup`") | active | TBD |
| SECDISC-03 | Supported-versions table refreshed to cover v0.5.x and v0.6.x; clear retirement policy (only the most recent minor receives security fixes); test-advisory ritual ("we publish at least one rehearsal GHSA before any real CVE") documented | active | TBD |
| SECDISC-04 | One-time GitHub repo settings checklist appended to `docs/RELEASE.md`: enable private vulnerability reporting, enable Dependabot alerts + security updates, enable secret scanning + push protection; checklist items each include a verification command (`gh api`) the maintainer runs once | active | TBD |

### Runbook (RUNBOOK)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| RUNBOOK-01 | NEW single `docs/MAINTAINER-RUNBOOK.md` covers BOTH the v0.6.0 release procedure (mirror of v0.5's STOP-BEFORE-TAG block) AND the post-flip operational playbook (freeze triggers, throttle triggers, burnout triggers, decision matrix for "is this PR worth my time?"); supersedes the candidate `docs/POSTFLIP-PLAYBOOK.md` name (one doc, not two) | active | TBD |
| RUNBOOK-02 | `.planning/rollback/flip-gate-revert.md` carries the one-commit revert template that restores the pre-flip prose; tested by running `git apply` against a stale working tree in a Phase 59 rehearsal | active | TBD |

### Discussions + status channel (DISCGH)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| DISCGH-01 | GitHub Discussions enabled with categories (General, Q&A, Show and Tell, Ideas); enabling is a one-time repo settings step documented in `docs/MAINTAINER-RUNBOOK.md` repo-settings checklist | active | TBD |
| DISCGH-02 | Pinned "Project Status" Discussion post created at v0.6.0 ship; text mirrors STATUS.md `## TL;DR` plus a "follow this post" CTA; updated at each release | active | TBD |

### Gate flip (FLIP)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| FLIP-01 | All gate-flip prose changes land in ONE atomic commit at v0.6.0 ship: STATUS.md TL;DR rewritten to "contributions OPEN" + milestone row marked SHIPPED; README "Project status" section + CTAs updated + badge bumped to v0.6.0; CONTRIBUTING.md NOTICE blocks deleted; PR template NOTICE block deleted; SECURITY.md "(not active yet)" section deleted; `.github/workflows/issue-claim-watcher.yml` deleted; saved replies updated; CHANGELOG `[0.6.0]` promoted | active | TBD |
| FLIP-02 | First-time-contributor approval gate enabled in branch protection settings: every fork-PR from a user without prior merged PRs requires explicit "Approve and run" before CI runs; documented in `docs/MAINTAINER-RUNBOOK.md` | active | TBD |
| FLIP-03 | `accepted-for-review` throttle active for first 30 days post-flip: PRs without that label do not block the queue; documented in `docs/MAINTAINER-RUNBOOK.md` as the burnout-prevention valve; removed after first 30 days unless retained based on volume | active | TBD |

### Test and CI (continued from v0.5)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| TEST-22 | `tests/test_contribution_gate_pitfalls/` directory contains one regression test per documented pitfall in `.planning/research/PITFALLS.md` (minimum 12 tests); test names map 1:1 to pitfall numbers (mirrors v0.5 TEST-17 pattern) | active | TBD |
| TEST-23 | Workflow-lint regression test enforces CIHARD-01..05: scans every `.github/workflows/*.yml` for forbidden patterns (`pull_request_target` unguarded, missing top-level `permissions:`, non-SHA action pin, `${{ github.event.* }}` in shell, missing `persist-credentials: false`) | active | TBD |
| TEST-24 | Sigstore identity negative-test: fixture signature signed by a different workflow identity MUST fail `scripts/verify_release.py`; positive fixture signed by the canonical identity passes; both fixtures committed under `tests/fixtures/sigstore/` | active | TBD |
| TEST-25 | Three-OS install-smoke matrix (macOS + Ubuntu + Windows × Python 3.11 + 3.12) remains green; new `verify_release.py` test runs on every OS to catch platform-specific sigstore-python regressions; existing install-smoke + install-smoke-plugin jobs byte-identical (no rename) | active | TBD |
| TEST-26 | Pre-flip soft-launch rehearsal (Phase 59): 3-5 invited contributors land sample PRs end-to-end through the new audit + sign + verify pipeline; friction findings tracked in `.planning/phases/59-*/REHEARSAL.md`; rehearsal PRs credited in CHANGELOG | active | TBD |

### Release (continued from v0.5)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| REL-13 | Tag v0.6.0 with CHANGELOG and GitHub Release; gitsign-signed tag; `docs/MIGRATION-v0.5-to-v0.6.md` documents: no schema migration, no new base dependencies (signing/SBOM/audit are CI-time), one new `[dev]` addition (`pip-audit`), the gate flip's external-facing changes | active | TBD |
| REL-14 | `scripts/release_gate.py` extended from 8 to 13 checks (5 new): `release-workflow-signing-present` (grep for sigstore-python + attest-build-provenance literals), `release-workflow-sbom-present` (grep for cyclonedx-py + attest-sbom), `audit-workflow-present` (grep for pip-audit + dependency-review-action), `local-pip-audit-clean` (`pip-audit -s osv` exits 0), `actions-pinned-by-sha` (regex asserts every `uses:` is `@<40-hex>`); `--check` enum APPENDED, existing 8 values byte-identical | active | TBD |
| REL-15 | Two-tier release-gate execution: tier 1 (pre-merge, local, <10s) covers the grep-only checks + lint; tier 2 (pre-release, network, ~60s) adds `pip-audit` network call + sigstore-verify on the built wheel; tier choice via `--tier {local,release}` CLI flag (default `release`); offline mode short-circuits tier-2 with explicit `--allow-offline` flag plus warning | active | TBD |

## Coverage summary

| Category | Total | Active | Validated |
|----------|-------|--------|-----------|
| CORE | 5 | 5 | 5 |
| AGENT | 3 | 3 | 3 |
| TOOL | 3 | 3 | 3 |
| MEM | 3 | 3 | 3 |
| DASH | 3 | 3 | 3 |
| WIZARD | 4 | 4 | 4 |
| TEST | 21 | 21 | 15 |
| REL | 12 | 12 | 9 |
| MA | 4 | 4 | 4 |
| STREAM | 3 | 3 | 3 |
| ADAPT | 3 | 3 | 3 |
| MIG | 5 | 5 | 4 |
| ART | 3 | 3 | 3 |
| DISC | 3 | 3 | 3 |
| SLAK | 3 | 3 | 3 |
| MAIL | 3 | 3 | 3 |
| CAL | 2 | 2 | 2 |
| DASH-3 | 2 | 2 | 2 |
| METRIC | 5 | 5 | 5 |
| STORE | 5 | 5 | 5 |
| PRICE | 5 | 5 | 5 |
| DASH-4 | 5 | 5 | 5 |
| USAGE | 4 | 4 | 4 |
| OTEL | 7 | 7 | 7 |
| BASELINE | 2 | 2 | 1 |
| MANIFEST | 5 | 5 | 0 |
| DISCOVERY | 2 | 2 | 0 |
| INSTALL | 6 | 6 | 0 |
| PERMISSION | 4 | 4 | 4 |
| ISOLATE | 4 | 4 | 4 |
| DASH-5 | 3 | 3 | 0 |
| OBSERVE | 2 | 2 | 0 |
| REFERENCE | 2 | 2 | 0 |
| **Total** | **141** | **141** | **114** |

"Validated" means the requirement is covered by a shipped phase. v0.1 and v0.2 shipped 2026-05-23 (tags `v0.1.0`, `v0.2.0`); v0.3 shipped 2026-05-24 (tag `v0.3.0`); v0.4 shipped 2026-05-26 (tag `v0.4.0`). v0.5 requirements stay unvalidated until their phases ship.

## Traceability — v0.5 Plugin System

Single-phase mapping for every v0.5 requirement (Phases 40-50). Source-of-truth: the Phase column in each category table above. Where a requirement's Phase column lists two numbers (ISOLATE-01 "42, 43" and TEST-19 "42, 43"), the owning phase is the one carrying the bulk of the work; the other phase consumes its substrate.

| Requirement | Phase | Status |
|-------------|-------|--------|
| BASELINE-02 | 40 | Complete |
| MANIFEST-01 | 41 | Complete |
| MANIFEST-02 | 41 | Complete |
| MANIFEST-03 | 41 | Complete |
| MANIFEST-04 | 41 | Complete |
| MANIFEST-05 | 41 | Complete |
| OBSERVE-01 | 41 | Complete |
| MIG-05 | 41 | Complete |
| DISCOVERY-01 | 42 | Complete |
| DISCOVERY-02 | 42 | Complete |
| ISOLATE-04 | 42 | Complete |
| TEST-18 | 42 | Complete |
| TEST-19 | 42 | Complete |
| PERMISSION-01 | 43 | Complete |
| PERMISSION-02 | 43 | Complete |
| PERMISSION-03 | 43 | Complete |
| PERMISSION-04 | 43 | Complete |
| ISOLATE-01 | 43 | Complete |
| ISOLATE-02 | 43 | Complete |
| ISOLATE-03 | 43 | Complete |
| INSTALL-01 | 44 | Complete (2026-05-26) |
| INSTALL-02 | 44 | Complete (2026-05-26) |
| INSTALL-03 | 44 | Complete (2026-05-26) |
| INSTALL-04 | 44 | Complete (2026-05-26) |
| INSTALL-05 | 44 | Complete (2026-05-26) |
| INSTALL-06 | 44 | Complete (2026-05-26) |
| DASH-5-01 | 45 | Complete (2026-05-26) |
| DASH-5-02 | 45 | Complete (2026-05-26) |
| DASH-5-03 | 45 | Complete (2026-05-26) |
| OBSERVE-02 | 45 | Complete (2026-05-26) |
| TEST-16 | 46 | Complete (2026-05-26) |
| TEST-17 | 46 | Complete (2026-05-26) |
| REFERENCE-02 | 47 | Complete (2026-05-26) |
| REL-12 | 47 | Complete (2026-05-26) |
| REFERENCE-01 | 48 | Complete (2026-05-26) |
| TEST-21 | 48 | Complete (2026-05-26) |
| TEST-20 | 49 | Complete (2026-05-26) |
| REL-11 | 49 | Complete (2026-05-26) |
| REL-10 | 50 | Complete (2026-05-26) |

**Coverage:** 39 v0.5 requirements, 39 mapped, 0 orphans, 0 duplicates. Multi-phase entries (ISOLATE-01: 42, 43 and TEST-19: 42, 43) resolved to owning phase per "bulk of the work" rule; consumer phase relationship preserved via the Depends-on notes in ROADMAP.md.
