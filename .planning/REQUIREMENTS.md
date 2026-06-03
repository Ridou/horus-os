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
| DASH-4-03 | Percentile cells with n < 10 samples render as "-", not as a number | active | 36 |
| DASH-4-04 | Existing `/agents` tab gains cost + latency columns from rollups | active | 35 |
| DASH-4-05 | Pre-v0.4 trace rows render "-" for new columns with hover "no cost data captured before v0.4" | active | 36 |

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
| TEST-19 | Broken-plugin fixtures verify ISOLATE-01: synthetic plugins with invalid TOML, schema-failing manifest, import-raising module, `start()`-raising adapter, `start()`-hanging adapter - each must surface as `status="error"` without crashing the host | complete | 42, 43 |
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
| CIHARD-01 | `pull_request_target` is FORBIDDEN by default across every workflow; release-gate lint rejects any new occurrence unless guarded by a `# SECURITY:` comment AND a `safe-to-test` label gate; v0.6 ships ZERO `pull_request_target` triggers (v0.5 tests use recorded provider responses) | active | 51 |
| CIHARD-02 | Top-level `permissions: read-all` set on `.github/workflows/ci.yml`, `audit.yml`, `release.yml`; per-job opt-in for any write scope; lint asserts no workflow inherits the legacy GITHUB_TOKEN default scope | active | 51 |
| CIHARD-03 | Every `actions/checkout` step sets `persist-credentials: false` unless explicitly required for push; no `${{ github.event.pull_request.* }}` interpolation appears in any `run:` shell line | active | 51 |
| CIHARD-04 | Every third-party `uses:` is pinned to a 40-character commit SHA (`@<sha>` exact match); release-gate `actions-pinned-by-sha` check rejects any `@v<N>`, `@main`, `@master`, or short-SHA pin; `pinact` is documented as the local maintainer refresh tool | active | 51 |
| CIHARD-05 | `actionlint` runs on every PR via a new workflow lint job; failures block merge; covers untrusted-input interpolation, expired action references, missing `permissions:` | active | 51 |

### Signing substrate (SIGN)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| SIGN-01 | NEW `.github/workflows/release.yml` triggered on `release: types: [published]`; signs wheel + sdist + SBOM JSON via `sigstore/gh-action-sigstore-python@<sha>` (sigstore-python >=4.2,<5); produces `.sigstore` bundle (NOT detached `.sig`); sign step runs within 5 minutes of `id-token: write` OIDC mint | active | 52 |
| SIGN-02 | `actions/attest-build-provenance@<sha>` generates SLSA Build L2 provenance attestations bound to the GitHub workflow identity; verifiable via `gh attestation verify`; runs for every signed artifact | active | 52 |
| SIGN-03 | Tag signing via `gitsign` (Sigstore keyless, OIDC); no long-lived GPG keypair required; `docs/RELEASE.md` STOP-BEFORE-TAG block documents the gitsign-configured `git tag` invocation; tag verification uses workflow-scoped identity | active | 52 |
| SIGN-04 | `scripts/verify_release.py` (NEW) is a 5-check user-facing trust-chain verifier with workflow-scoped EXACT-match `EXPECTED_IDENTITY = "https://github.com/Ridou/horus-os/.github/workflows/release.yml@refs/tags/{version}"` (no wildcards, no regex); mandatory `--cert-oidc-issuer` flag; negative test rejects wrong-identity fixture | active | 52 |
| SIGN-05 | PyPI Trusted Publishing (PEP 807) is OUT OF SCOPE for v0.6 (horus-os does not currently publish to PyPI); deferral documented in `.planning/decisions/no-pypi-in-v0.6.md`; v0.7+ may revisit | active | 52 |

### Supply-chain SBOM (SBOM)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| SBOM-01 | Release-time SBOM generated via `cyclonedx-bom` (`cyclonedx-py environment`) against a FRESH `pip install <wheel>` venv (NOT `pip freeze` of the dev venv); CycloneDX 1.6 JSON format locked; signed via sigstore in the same `release.yml` job | active | 53 |
| SBOM-02 | Two SBOMs ship per release: clean install (`pip install <wheel>`) AND extras install (`pip install <wheel>[dev,otel]`); both attached to the GitHub Release alongside their `.sigstore` bundles; matches existing two-variant install-smoke convention | active | 53 |
| SBOM-03 | `actions/attest-sbom@<sha>` generates SBOM attestations bound to the artifact each SBOM describes; release-gate diffs SBOM contents against the published wheel's actual installed dependency tree | active | 53 |

### Supply-chain scanning (SUPPLY)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| SUPPLY-01 | NEW `.github/workflows/audit.yml` runs `pypa/gh-action-pip-audit@<sha>` (pip-audit >=2.10,<3) on every PR in dual-mode (`-s osv` AND `-s pypi`); failures block merge; `pip-audit` added to `[dev]` extras for local use | active | 53 |
| SUPPLY-02 | `actions/dependency-review-action@<sha>` runs on every PR with explicit license allowlist (Apache-2.0, MIT, BSD-2-Clause, BSD-3-Clause, ISC, PSF-2.0); rejects new deps under unlisted licenses | active | 53 |
| SUPPLY-03 | `.github/pip-audit-ignore.txt` is the ignore-list with mandatory dated-comment discipline (every entry includes `# YYYY-MM-DD: <reason>`); release-gate rejects undated entries; `.github/pip-audit-tracking/` directory carries fix-tracking docs for unfixable transitives | active | 53 |
| SUPPLY-04 | `pip-audit` runs on BOTH `[dev]` AND `[dev,otel]` install variants to match the existing two-variant install-smoke pattern; matches the Phase 39 OTel-variant precedent | active | 53 |

### Dependabot + zizmor (DEPBOT)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| DEPBOT-01 | `.github/dependabot.yml` v2 with `package-ecosystem: pip` (groups: `ai-sdks` for anthropic + google-genai, `otel`, `web-stack`, `dev-tools`; cooldown 3 days default, 14 days majors; `applies-to: version-updates`) AND `package-ecosystem: github-actions` (SHA-pin refresh, weekly cadence) | active | 54 |
| DEPBOT-02 | Security updates are explicitly UN-grouped (no `applies-to: security-updates` matcher); one PR per CVE; PRs gain a distinct `security-update` label; CVE PRs never hide inside a weekly grouped bump | active | 54 |
| DEPBOT-03 | `zizmor` workflow runs on every PR + on `.github/workflows/**` edits; static-analysis findings block merge; complements actionlint by covering known-bad expression interpolation patterns | active | 54 |

### Contributor docs + templates (CONTRIB)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| CONTRIB-01 | `CONTRIBUTING.md` rewritten: claim flow ("comment to claim, maintainer assigns"), branch policy, commit format (conventional commits, present tense, no em-dashes per CLAUDE.md), test/doc/changelog expectations; honest solo-maintainer language ("aim to acknowledge within 7 days"); NO 24-hour SLA, NO CLA, Discord optional | active | 55 |
| CONTRIB-02 | `.github/PULL_REQUEST_TEMPLATE.md` NOTICE block removed at gate-flip; gains a checklist (tests added/updated, docs updated if user-visible, CHANGELOG `[Unreleased]` entry added if user-visible, license header on new files), and a reference to CONTRIBUTING.md + CODE_OF_CONDUCT.md | active | 55 |
| CONTRIB-03 | `.github/ISSUE_TEMPLATE/` carries three forms: `bug.yml`, `feature.yml`, `security.yml` (security form redirects to GHSA private-vulnerability-reporting); banners flipped at gate-flip to drop "not accepting contributions" | active | 55 |
| CONTRIB-04 | `.github/CODEOWNERS` NEW with PATH-SCOPED ownership (workflows, scripts/release_gate.py, scripts/verify_release.py, SECURITY.md, .planning/), NOT `* @Ridou` blanket assignment; reviewers auto-assigned by directory | active | 55 |
| CONTRIB-05 | `docs/TRIAGE.md` NEW: label taxonomy with ≤15 hard cap (type:bug, type:feature, area:adapters, area:dashboard, area:cli, good-first-issue, help-wanted, security-update, breaking, blocked, needs-info, waiting-for-author, accepted, claimed, wontfix); `good-first-issue` rubric; weekly Sunday triage cadence; "may go silent up to 2 weeks" disclaimer; NO `actions/stale` auto-close | active | 55 |
| CONTRIB-06 | `docs/LABEL-TAXONOMY.md` documents the label set + when each applies + saved-reply text for common scenarios (claim accepted, claim conflict, missing repro, stale-but-real bug) | active | 55 |
| CONTRIB-07 | `.planning/decisions/` directory carries one-page rationale files: `no-cla.md`, `no-stale-bot.md`, `sigstore-keyless.md`, `sbom-cyclonedx.md`, `no-pypi-in-v0.6.md`; referenced from CONTRIBUTING.md and PROJECT.md key-decisions table | active | 55 |

### SECURITY disclosure refresh (SECDISC)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| SECDISC-01 | `SECURITY.md` "(not active yet)" / staged-pipeline section deleted at gate-flip; replaced with active vulnerability-disclosure flow pointing at GitHub Security Advisories private reporting | active | 56 |
| SECDISC-02 | Severity-tier SLOs replace any blanket SLO: "aim to acknowledge within 7 days"; fix targets critical 14d / high 30d / medium 90d / low no commitment; coordinated disclosure 90-day default; over-capacity acknowledgement language explicit ("if we go silent, file a public issue tagged `security-update-followup`") | active | 56 |
| SECDISC-03 | Supported-versions table refreshed to cover v0.5.x and v0.6.x; clear retirement policy (only the most recent minor receives security fixes); test-advisory ritual ("we publish at least one rehearsal GHSA before any real CVE") documented | active | 56 |
| SECDISC-04 | One-time GitHub repo settings checklist appended to `docs/RELEASE.md`: enable private vulnerability reporting, enable Dependabot alerts + security updates, enable secret scanning + push protection; checklist items each include a verification command (`gh api`) the maintainer runs once | active | 56 |

### Runbook (RUNBOOK)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| RUNBOOK-01 | NEW single `docs/MAINTAINER-RUNBOOK.md` covers BOTH the v0.6.0 release procedure (mirror of v0.5's STOP-BEFORE-TAG block) AND the post-flip operational playbook (freeze triggers, throttle triggers, burnout triggers, decision matrix for "is this PR worth my time?"); supersedes the candidate `docs/POSTFLIP-PLAYBOOK.md` name (one doc, not two) | active | 56 |
| RUNBOOK-02 | `.planning/rollback/flip-gate-revert.md` carries the one-commit revert template that restores the pre-flip prose; tested by running `git apply` against a stale working tree in a Phase 59 rehearsal | active | 56 |

### Discussions + status channel (DISCGH)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| DISCGH-01 | GitHub Discussions enabled with categories (General, Q&A, Show and Tell, Ideas); enabling is a one-time repo settings step documented in `docs/MAINTAINER-RUNBOOK.md` repo-settings checklist | active | 56 |
| DISCGH-02 | Pinned "Project Status" Discussion post created at v0.6.0 ship; text mirrors STATUS.md `## TL;DR` plus a "follow this post" CTA; updated at each release | active | 59 |

### Gate flip (FLIP)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| FLIP-01 | All gate-flip prose changes land in ONE atomic commit at v0.6.0 ship: STATUS.md TL;DR rewritten to "contributions OPEN" + milestone row marked SHIPPED; README "Project status" section + CTAs updated + badge bumped to v0.6.0; CONTRIBUTING.md NOTICE blocks deleted; PR template NOTICE block deleted; SECURITY.md "(not active yet)" section deleted; `.github/workflows/issue-claim-watcher.yml` deleted; saved replies updated; CHANGELOG `[0.6.0]` promoted | active | 59 |
| FLIP-02 | First-time-contributor approval gate enabled in branch protection settings: every fork-PR from a user without prior merged PRs requires explicit "Approve and run" before CI runs; documented in `docs/MAINTAINER-RUNBOOK.md` | active | 58 |
| FLIP-03 | `accepted-for-review` throttle active for first 30 days post-flip: PRs without that label do not block the queue; documented in `docs/MAINTAINER-RUNBOOK.md` as the burnout-prevention valve; removed after first 30 days unless retained based on volume | active | 59 |

### Test and CI (continued from v0.5)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| TEST-22 | `tests/test_contribution_gate_pitfalls/` directory contains one regression test per documented pitfall in `.planning/research/PITFALLS.md` (minimum 12 tests); test names map 1:1 to pitfall numbers (mirrors v0.5 TEST-17 pattern) | active | 58 |
| TEST-23 | Workflow-lint regression test enforces CIHARD-01..05: scans every `.github/workflows/*.yml` for forbidden patterns (`pull_request_target` unguarded, missing top-level `permissions:`, non-SHA action pin, `${{ github.event.* }}` in shell, missing `persist-credentials: false`) | active | 51 |
| TEST-24 | Sigstore identity negative-test: fixture signature signed by a different workflow identity MUST fail `scripts/verify_release.py`; positive fixture signed by the canonical identity passes; both fixtures committed under `tests/fixtures/sigstore/` | active | 58 |
| TEST-25 | Three-OS install-smoke matrix (macOS + Ubuntu + Windows × Python 3.11 + 3.12) remains green; new `verify_release.py` test runs on every OS to catch platform-specific sigstore-python regressions; existing install-smoke + install-smoke-plugin jobs byte-identical (no rename) | active | 58 |
| TEST-26 | Pre-flip soft-launch rehearsal (Phase 59): 3-5 invited contributors land sample PRs end-to-end through the new audit + sign + verify pipeline; friction findings tracked in `.planning/phases/59-*/REHEARSAL.md`; rehearsal PRs credited in CHANGELOG | active | 58 |

### Release (continued from v0.5)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| REL-13 | Tag v0.6.0 with CHANGELOG and GitHub Release; gitsign-signed tag; `docs/MIGRATION-v0.5-to-v0.6.md` documents: no schema migration, no new base dependencies (signing/SBOM/audit are CI-time), one new `[dev]` addition (`pip-audit`), the gate flip's external-facing changes | active | 59 |
| REL-14 | `scripts/release_gate.py` extended from 8 to 13 checks (5 new): `release-workflow-signing-present` (grep for sigstore-python + attest-build-provenance literals), `release-workflow-sbom-present` (grep for cyclonedx-py + attest-sbom), `audit-workflow-present` (grep for pip-audit + dependency-review-action), `local-pip-audit-clean` (`pip-audit -s osv` exits 0), `actions-pinned-by-sha` (regex asserts every `uses:` is `@<40-hex>`); `--check` enum APPENDED, existing 8 values byte-identical | active | 57 |
| REL-15 | Two-tier release-gate execution: tier 1 (pre-merge, local, <10s) covers the grep-only checks + lint; tier 2 (pre-release, network, ~60s) adds `pip-audit` network call + sigstore-verify on the built wheel; tier choice via `--tier {local,release}` CLI flag (default `release`); offline mode short-circuits tier-2 with explicit `--allow-offline` flag plus warning | active | 57 |

## v0.7 Command Center

Polished local-first dashboard plus a full OPTIONAL integration suite (Discord, Supabase, Vercel, Tailscale, GitHub, AI providers, existing adapters) connectable through guided in-dashboard walkthroughs with green-light verification and in-app key management. Every integration is optional; horus-os runs fully locally with only an LLM key. Phase column is TBD until the roadmap maps each requirement.

### Design system and layout shell (DESIGN)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| DESIGN-01 | Dashboard renders against a single Tailwind v4 design-token theme (background, text, accent, border, and semantic tokens) defined in one place | active | 60 |
| DESIGN-02 | A reusable Modal primitive (portal-mounted, backdrop, Escape to close, focus trap) is available to every page | active | 60 |
| DESIGN-03 | A reusable multi-step Stepper primitive (numbered progress, back/continue/done, per-step validation) is available | active | 60 |
| DESIGN-04 | The dashboard uses a persistent sidebar navigation shell listing all pages, with a dark default theme | active | 60 |
| DESIGN-05 | A shared UI kit (empty state, loading skeleton, status dot/badge, metric card, markdown renderer) is used consistently across pages | active | 60 |

### Tier-1 dashboard pages (PAGES)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| PAGES-01 | User can view the agent roster at /team with status filter tabs, live counts, and a list vs org-chart view toggle | active | 63 |
| PAGES-02 | User can open a single agent at /team/[agent] and see its persona, color, domain, model, and recent session activity | active | 63 |
| PAGES-03 | User can browse the markdown vault at /memory with a folder tree, content viewer, debounced search, and time-ago timestamps | active | 63 |
| PAGES-04 | User can view the task queue at /tasks (pending, running, completed) and retry or cancel a task | active | 63 |
| PAGES-05 | User can watch a live timeline of agent actions at /activity | active | 63 |
| PAGES-06 | The existing /traces view is redesigned against the new design system | active | 63 |
| PAGES-07 | The existing observability view is redesigned as /costs with Recharts-based charts | active | 63 |
| PAGES-08 | User can read /about explaining what horus-os is, the running version, and where to get help | active | 63 |

### Starter agent team (TEAM)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| TEAM-01 | `horus-os init` auto-creates five generic starter agents (Coordinator, Engineer, Researcher, Writer, Operator), each with a name, color, domain, and default model | active | 63 |
| TEAM-02 | Each starter agent ships a SOUL.md persona (YAML frontmatter plus Identity, Principles, Voice, Boundaries, Workflow sections) with a user-name template placeholder | active | 63 |
| TEAM-03 | The Coordinator can delegate work to the other starter agents via the existing delegate_to_agent tool | active | 63 |

### Seed content and first-run (SEED)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| SEED-01 | First run seeds an example vault of generic sample notes so /memory is not empty, clearly labeled as example data | active | 63 |
| SEED-02 | A demo trace is seeded on init so /traces and /activity are not empty, with an example-data banner and a way to clear it | active | 63 |
| SEED-03 | A first-run onboarding tour overlay highlights the core pages in turn and can be dismissed and replayed | active | 63 |

### Integrations surface and guided setup (SETUP)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| SETUP-01 | An Integrations page lists every connector (Anthropic, Gemini, Discord, Slack, Email, Calendar, GitHub, Supabase, Vercel, Tailscale) as a card with a status indicator | active | 61 |
| SETUP-02 | GET /api/integrations returns each integration's metadata and live configured/verified status without returning any secret value | active | 61 |
| SETUP-03 | Each integration card opens a guided multi-step popup walkthrough explaining what it unlocks, where to get the credential (with a portal deep-link), and the exact env var or command | active | 61 |
| SETUP-04 | Walkthrough steps can display an optional screenshot or image asset bundled with the dashboard | active | 61 |
| SETUP-05 | The get-started page launches the same guided setup, replacing the reserved placeholder | active | 61 |
| SETUP-06 | In demo mode the walkthroughs degrade to instructional-only with no writes | active | 61 |

### Verification and green-light readiness (VERIFY)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| VERIFY-01 | Each integration exposes a server-side verification probe that tests the configured credential and returns pass or fail without echoing the secret | active | 62 |
| VERIFY-02 | The Integrations surface shows a per-integration readiness state (verified, configured-but-unverified, missing, error) as a green-light indicator | active | 61 |
| VERIFY-03 | Changing or rotating a credential invalidates a previously verified state via key-hash change detection | active | 62 |
| VERIFY-04 | A readiness summary tells the user which integrations are ready, and never blocks local-only operation on any optional integration | active | 61 |

### In-app key management (KEYS)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| KEYS-01 | A real /settings page lets the user see which credentials are set (masked) and adjust or replace them per integration | active | 62 |
| KEYS-02 | A secret-aware key-write endpoint persists an allowlisted credential to the local data_dir .env at chmod 600 and to the running process, and never echoes the value back | active | 62 |
| KEYS-03 | The key-write endpoint refuses non-loopback clients and returns an error in demo mode | active | 62 |
| KEYS-04 | After a credential change the UI tells the user whether a restart is needed and surfaces the new verification state | active | 62 |

### Discord control bot (DISC, continued from v0.3)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| DISC-05 | An opt-in setup creates the bot's channel and category layout idempotently and never deletes channels it does not own | active | 64 |
| DISC-06 | Typing in the control channel opens a thread, submits the message to the orchestrator, and posts the result back in that thread | active | 64 |
| DISC-07 | Guild-scoped slash commands are registered for the core actions, with stale global-command cleanup | active | 64 |
| DISC-08 | Task progress is posted as status cards and reactions provide approve and feedback signals | active | 64 |
| DISC-09 | Privileged-command authorization uses a configurable admin role rather than a hardcoded name, and the Message Content privileged-intent requirement is documented | active | 64 |
| DISC-10 | The Discord setup guide and the in-dashboard walkthrough cover full-admin bot creation, intents, and the invite URL | active | 64 |

### Always-live mission control: Supabase (SUPA)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| SUPA-01 | An opt-in background loop incrementally syncs local SQLite rows to Supabase using an updated-at cursor and push-only upserts | active | 65 |
| SUPA-02 | Supabase writes use a server-side service key only; the service key never reaches the browser or the static bundle | active | 65 |
| SUPA-03 | Versioned Supabase schema migrations create the mirrored tables with row-level security enabled | active | 65 |
| SUPA-04 | When configured, the dashboard can read from Supabase directly with the anon key so a deployed dashboard stays current without redeploys | active | 65 |
| SUPA-05 | The runtime starts and runs fully with zero Supabase configuration; Supabase lives behind an optional [supabase] extra | active | 65 |

### Deploy your own dashboard: Vercel (VERCEL)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| VERCEL-01 | The dashboard build honors a configurable API base URL so a Vercel-hosted copy can target a reachable backend, defaulting to same-origin locally | active | 67 |
| VERCEL-02 | A walkthrough documents deploying your own dashboard to Vercel (root directory, environment variables, build) | active | 67 |
| VERCEL-03 | An observe-only Vercel client reports deploy status using a user-supplied token, behind an optional [vercel] extra | active | 67 |
| VERCEL-04 | Any guidance that exposes the dashboard beyond localhost carries a prominent warning that /api has no authentication layer | active | 67 |

### Remote access and 24/7 operation (REMOTE)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| REMOTE-01 | Mutating endpoints (including the key-write endpoint) are guarded to loopback by default, and starlette is pinned to a version without the host-header bypass | active | 62 |
| REMOTE-02 | `horus-os serve --host` is documented alongside the localhost default and its security implications | active | 66 |
| REMOTE-03 | A remote-access guide covers reaching the dashboard over Tailscale (serve or Funnel), gated on adding an authentication layer first | active | 66 |
| REMOTE-04 | `horus-os service install` registers an always-on service cross-platform (systemd, launchd, Windows) with restart-on-failure | active | 66 |
| REMOTE-05 | An in-process cron scheduler runs recurring agent routines from a schedules table so routines fire 24/7, with a catch-up policy for missed runs | active | 66 |

### GitHub integration (GH)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| GH-01 | GitHub appears in the Integrations surface with a token-based connect walkthrough and a verification probe | active | 61 |
| GH-02 | An optional GitHub tool lets an agent read repository data (issues, pull requests, files) using the configured token, behind an opt-in extra | active | 67 |

### Migration (continued from v0.6)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| MIG-06 | The SQLite schema migration that adds v0.7 tables (schedules, integration verification state, sync cursors) is additive and idempotent | active | 62 |

### Test and CI (continued from v0.6)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| TEST-27 | Regression tests cover the new endpoints (integrations list, verification probe, key-write) including the loopback guard and demo-mode refusal | active | 62 |
| TEST-28 | A test asserts the Discord channel bootstrap is idempotent and never deletes channels outside its managed set | active | 64 |
| TEST-29 | A test asserts the Supabase service key never appears in any browser-exposed value or the static bundle | active | 65 |
| TEST-30 | Cross-OS tests cover the always-on service install path on macOS, Ubuntu, and Windows | active | 66 |
| TEST-31 | Three-OS install-smoke remains green with the new optional extras | active | 67 |

### Release (continued from v0.6)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| REL-16 | v0.7.0 ships behind the three-OS hard gate (macOS, Ubuntu, Windows; Python 3.11 and 3.12) | active | 68 |
| REL-17 | The new optional extras ([supabase], [vercel]) are excluded from [all] and documented | active | 68 |

### Deferred to a later milestone (v0.7 context)

These are intentionally out of v0.7 scope: Tier-2 dashboard pages (/inbox, /approvals, /goals, /schedules UI, /health, /terminal), the memory intelligence pipeline (fact extraction, consolidation, vault drift, working vs long-term split, likely a v0.8 milestone), voice features via a paid SDK, OAuth-based connect flows (token or API key is sufficient for v0.7), and any personal-data domains.

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

## Traceability - v0.5 Plugin System

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

## Traceability - v0.6 Contribution Gate

Single-phase mapping for every v0.6 requirement (Phases 51-59). Source-of-truth: the Phase column in each category table above. Mirrors v0.5 traceability shape.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CIHARD-01 | 51 | Pending |
| CIHARD-02 | 51 | Pending |
| CIHARD-03 | 51 | Pending |
| CIHARD-04 | 51 | Pending |
| CIHARD-05 | 51 | Pending |
| TEST-23 | 51 | Pending |
| SIGN-01 | 52 | Complete |
| SIGN-02 | 52 | Complete |
| SIGN-03 | 52 | Complete |
| SIGN-04 | 52 | Complete |
| SIGN-05 | 52 | Complete |
| SBOM-01 | 53 | Pending |
| SBOM-02 | 53 | Pending |
| SBOM-03 | 53 | Pending |
| SUPPLY-01 | 53 | Pending |
| SUPPLY-02 | 53 | Pending |
| SUPPLY-03 | 53 | Pending |
| SUPPLY-04 | 53 | Pending |
| DEPBOT-01 | 54 | Pending |
| DEPBOT-02 | 54 | Pending |
| DEPBOT-03 | 54 | Pending |
| CONTRIB-01 | 55 | Pending |
| CONTRIB-02 | 55 | Pending |
| CONTRIB-03 | 55 | Pending |
| CONTRIB-04 | 55 | Pending |
| CONTRIB-05 | 55 | Pending |
| CONTRIB-06 | 55 | Pending |
| CONTRIB-07 | 55 | Pending |
| SECDISC-01 | 56 | Pending |
| SECDISC-02 | 56 | Pending |
| SECDISC-03 | 56 | Pending |
| SECDISC-04 | 56 | Pending |
| RUNBOOK-01 | 56 | Pending |
| RUNBOOK-02 | 56 | Pending |
| DISCGH-01 | 56 | Pending |
| REL-14 | 57 | Pending |
| REL-15 | 57 | Pending |
| TEST-22 | 58 | Pending |
| TEST-24 | 58 | Pending |
| TEST-25 | 58 | Pending |
| TEST-26 | 58 | Pending |
| FLIP-02 | 58 | Pending |
| FLIP-01 | 59 | Pending |
| FLIP-03 | 59 | Pending |
| DISCGH-02 | 59 | Pending |
| REL-13 | 59 | Pending |

**Coverage:** 46 v0.6 requirements, 46 mapped, 0 orphans, 0 duplicates. Phase 52 (fork-PR CI split) consolidated into Phase 51 per research SUMMARY recommendation (v0.5 tests use recorded provider responses; no live-secret fork-CI path needed in v0.6). Result: 9-phase shape (51-59) instead of 10.

## Traceability - v0.7 Command Center

Single-phase mapping for every v0.7 requirement (Phases 60-68). Source-of-truth: the Phase column in each category table above.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DESIGN-01 | 60 | Complete |
| DESIGN-02 | 60 | Complete |
| DESIGN-03 | 60 | Complete |
| DESIGN-04 | 60 | Complete |
| DESIGN-05 | 60 | Complete |
| SETUP-01 | 61 | Complete |
| SETUP-02 | 61 | Complete |
| SETUP-03 | 61 | Complete |
| SETUP-04 | 61 | Complete |
| SETUP-05 | 61 | Complete |
| SETUP-06 | 61 | Complete |
| VERIFY-02 | 61 | Complete |
| VERIFY-04 | 61 | Complete |
| GH-01 | 61 | Complete |
| KEYS-01 | 62 | Complete |
| KEYS-02 | 62 | Complete |
| KEYS-03 | 62 | Complete |
| KEYS-04 | 62 | Complete |
| VERIFY-01 | 62 | Complete |
| VERIFY-03 | 62 | Complete |
| REMOTE-01 | 62 | Complete |
| MIG-06 | 62 | Complete |
| TEST-27 | 62 | Complete |
| PAGES-01 | 63 | Complete |
| PAGES-02 | 63 | Complete |
| PAGES-03 | 63 | Complete |
| PAGES-04 | 63 | Complete |
| PAGES-05 | 63 | Complete |
| PAGES-06 | 63 | Complete |
| PAGES-07 | 63 | Complete |
| PAGES-08 | 63 | Complete |
| TEAM-01 | 63 | Complete |
| TEAM-02 | 63 | Complete |
| TEAM-03 | 63 | Complete |
| SEED-01 | 63 | Complete |
| SEED-02 | 63 | Complete |
| SEED-03 | 63 | Complete |
| DISC-05 | 64 | Complete |
| DISC-06 | 64 | Complete |
| DISC-07 | 64 | Complete |
| DISC-08 | 64 | Complete |
| DISC-09 | 64 | Complete |
| DISC-10 | 64 | Complete |
| TEST-28 | 64 | Complete |
| SUPA-01 | 65 | Complete |
| SUPA-02 | 65 | Complete |
| SUPA-03 | 65 | Complete |
| SUPA-04 | 65 | Complete |
| SUPA-05 | 65 | Complete |
| TEST-29 | 65 | Complete |
| REMOTE-02 | 66 | Complete |
| REMOTE-03 | 66 | Complete |
| REMOTE-04 | 66 | Complete |
| REMOTE-05 | 66 | Complete |
| TEST-30 | 66 | Complete |
| VERCEL-01 | 67 | Complete |
| VERCEL-02 | 67 | Complete |
| VERCEL-03 | 67 | Complete |
| VERCEL-04 | 67 | Complete |
| GH-02 | 67 | Complete |
| TEST-31 | 67 | Complete |
| REL-16 | 68 | Complete |
| REL-17 | 68 | Complete |

**Coverage:** 63 v0.7 requirements, 63 mapped, 0 orphans, 0 duplicates. VERIFY-01 and VERIFY-03 (server-side probes, key-hash detection) land in Phase 62 with the key-write security substrate; VERIFY-02 and VERIFY-04 (UI status indicators, readiness summary) land in Phase 61 with the read-only integrations surface. REMOTE-01 (starlette pin + loopback guard) lands in Phase 62 as a BLOCKING security prerequisite; REMOTE-02..05 (docs, service install, cron) land in Phase 66. GH-01 (integrations card + verify probe) lands in Phase 61; GH-02 (GitHub tool behind extra) lands in Phase 67. TEST-27..31 each land in the phase that owns the code they exercise.

## v0.8 Local-first & Autonomous Research

Make horus-os fully usable on local hardware with zero cloud key, then prove it with an autonomous Deep Research capability built on the existing delegation runtime. Derived from the eight v0.8 seeds and `.planning/research/` (STACK, FEATURES, ARCHITECTURE, PITFALLS, SUMMARY). Three blocking security constraints: MCP-03, WEB-03, SHELL-01. Phase column is TBD until the roadmap maps each requirement.

### Local LLM provider (LLM)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| LLM-01 | User configures a local OpenAI-compatible endpoint (base URL plus model) and runs a full agent turn with zero cloud API key | active | 69 |
| LLM-02 | User can discover and select available local models during setup (probe GET /v1/models, one-token smoke test) | active | 69 |
| LLM-03 | Local provider handles tool-calling and streaming correctly, using Ollama native /api/chat where the OpenAI-compat streaming-plus-tools path is broken | active | 69 |
| LLM-04 | Local provider runs are traced and cost-annotated with local zero-cost pricing, not cloud pricing | active | 69 |

### Local-embedding vector memory (MEM, continued from v0.1)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| MEM-04 | User enables hybrid vector-plus-keyword search over the notes folder, results merged by reciprocal rank fusion | active | 70 |
| MEM-05 | Embeddings are computed on-device (ONNX); no network call occurs on a memory write | active | 70 |
| MEM-06 | User explicitly downloads the embedding model via a CLI pre-step (horus-os memory download-model); no silent download; the system still starts offline without it | active | 70 |
| MEM-07 | The reviewable note_writes audit trail is preserved; the vector index is a rebuildable cache in a separate store, needing no SCHEMA_VERSION bump | active | 70 |

### MCP client (MCP)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| MCP-01 | User configures MCP servers (stdio, SSE, HTTP); horus-os registers their tools into the agent tool registry, traced like any builtin tool | active | 71 |
| MCP-02 | MCP-discovered tools are namespaced (mcp:server:tool) to prevent collisions with builtin tools | active | 71 |
| MCP-03 | MCP servers are opt-in only (explicit config, no auto-discovery); an untrusted server cannot gain tool access unless the user adds it. BLOCKING security constraint | active | 71 |
| MCP-04 | MCP server subprocesses terminate cleanly on shutdown across macOS, Ubuntu, and Windows (no Windows zombies) | active | 71 |

### Agent web access (WEB)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| WEB-01 | User gives the agent a web search tool backed by a BYO or self-hosted provider (SearXNG default; Brave or Tavily optional); the tool is absent unless configured | active | 72 |
| WEB-02 | User gives the agent web browsing and screenshots via the Playwright MCP server, consumed through MCP | active | 72 |
| WEB-03 | Web fetch and browse enforce an SSRF blocklist (private IP ranges, localhost, cloud metadata 169.254.169.254) before any request. BLOCKING security constraint | active | 72 |

### Vision and PDF analysis (VIS)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| VIS-01 | User attaches an image and the agent analyzes it via the provider native vision, no new heavy deps | active | 72 |
| VIS-02 | User attaches a PDF and the agent reads it (native provider PDF where available, else pypdf text extraction), with a pre-flight size check | active | 72 |
| VIS-03 | The dashboard chat input exposes a file-upload affordance for images and PDFs | active | 72 |

### Deep Research flagship (RESEARCH)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| RESEARCH-01 | User starts a Deep Research run from a single question; the agent plans, searches, fetches, reads, and synthesizes a structured report | active | 73 |
| RESEARCH-02 | The plan is shown before execution and the user can cancel; a live progress panel shows the run | active | 73 |
| RESEARCH-03 | The report includes inline numeric citations and a reference list; sources are de-duplicated | active | 73 |
| RESEARCH-04 | The run is bounded by a hard source and iteration budget enforced by the coordinator, with no runaway cost or recursion | active | 73 |
| RESEARCH-05 | The report is stored as a reviewable note (audited) and its trace is inspectable | active | 73 |

### Skills system (SKILL)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| SKILL-01 | User defines a skill as a file (name, description, tags, body); skills are discovered from a skills folder | active | 74 |
| SKILL-02 | Skill names and descriptions are injected at turn start (progressive disclosure); the full body loads on use_skill(name) | active | 74 |
| SKILL-03 | Prompt-template skills are distinguished from code-bearing skills, which require an explicit plugin-style capability grant | active | 74 |
| SKILL-04 | The skills table migration (v11 to v12) updates every SCHEMA_VERSION expectation file in the tripwire set | active | 74 |

### Gated shell and code execution (SHELL)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| SHELL-01 | Shell and code execution are OFF by default; the tool only registers when both a config flag and a capability grant are present (default-deny double gate). BLOCKING security constraint | active | 75 |
| SHELL-02 | Every command is traced (command, exit code, truncated stdout, working directory) | active | 75 |
| SHELL-03 | Execution is pinned to a safe working directory with escape blocked; an optional human-confirm mode is available | active | 75 |

### Migration (continued from v0.7)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| MIG-07 | The v11 to v12 SQLite migration adding the skills table is additive and idempotent; the vector index lives in a separate store needing no schema bump | active | 74 |

### Test and CI (continued from v0.7)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| TEST-32 | A test proves a full agent turn completes against a mocked local OpenAI-compatible endpoint with no cloud key set | active | 69 |
| TEST-33 | A test proves no network call occurs on a memory write and the system starts offline without the embedding model | active | 70 |
| TEST-34 | Tests cover MCP tool namespacing, opt-in trust, and clean subprocess termination on all three OSes | active | 71 |
| TEST-35 | A test proves the web SSRF blocklist refuses localhost, private ranges, and cloud-metadata addresses | active | 72 |
| TEST-36 | A test proves the shell tool is absent from the registry unless both gates are set | active | 75 |
| TEST-37 | A test proves Deep Research enforces its source and iteration budget and de-duplicates sources | active | 73 |
| TEST-38 | Three-OS install-smoke stays green with the new optional extras and the onnxruntime Intel-macOS pin | active | 76 |

### Release (continued from v0.7)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| REL-18 | v0.8.0 ships behind the three-OS hard gate (macOS, Ubuntu, Windows; Python 3.11 and 3.12), all new deps with cross-OS wheels | active | 76 |
| REL-19 | v0.8.0 is tagged with CHANGELOG and migration notes; every integration is optional and horus-os still starts with zero cloud config | active | 76 |

### Out of scope (v0.8 context)

Explicitly rejected as off-thesis or PROJECT.md anti-goals: image editor, documents editor (markdown, HTML, CSV authoring), blind model comparison UI, mobile clients or PWA, multi-tenant or hosted SaaS, and email AI triage as a core feature (build it as a skill or example on the existing EmailAdapter). Deferred riders: agent-initiated skill evolution, OS-level syscall sandboxing and container or microVM execution for shell, research-session vector GC policy, CalDAV broadening, Cookbook-lite model picker, and notification fan-out.

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

## Traceability - v0.5 Plugin System

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

## Traceability - v0.6 Contribution Gate

Single-phase mapping for every v0.6 requirement (Phases 51-59). Source-of-truth: the Phase column in each category table above. Mirrors v0.5 traceability shape.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CIHARD-01 | 51 | Pending |
| CIHARD-02 | 51 | Pending |
| CIHARD-03 | 51 | Pending |
| CIHARD-04 | 51 | Pending |
| CIHARD-05 | 51 | Pending |
| TEST-23 | 51 | Pending |
| SIGN-01 | 52 | Complete |
| SIGN-02 | 52 | Complete |
| SIGN-03 | 52 | Complete |
| SIGN-04 | 52 | Complete |
| SIGN-05 | 52 | Complete |
| SBOM-01 | 53 | Pending |
| SBOM-02 | 53 | Pending |
| SBOM-03 | 53 | Pending |
| SUPPLY-01 | 53 | Pending |
| SUPPLY-02 | 53 | Pending |
| SUPPLY-03 | 53 | Pending |
| SUPPLY-04 | 53 | Pending |
| DEPBOT-01 | 54 | Pending |
| DEPBOT-02 | 54 | Pending |
| DEPBOT-03 | 54 | Pending |
| CONTRIB-01 | 55 | Pending |
| CONTRIB-02 | 55 | Pending |
| CONTRIB-03 | 55 | Pending |
| CONTRIB-04 | 55 | Pending |
| CONTRIB-05 | 55 | Pending |
| CONTRIB-06 | 55 | Pending |
| CONTRIB-07 | 55 | Pending |
| SECDISC-01 | 56 | Pending |
| SECDISC-02 | 56 | Pending |
| SECDISC-03 | 56 | Pending |
| SECDISC-04 | 56 | Pending |
| RUNBOOK-01 | 56 | Pending |
| RUNBOOK-02 | 56 | Pending |
| DISCGH-01 | 56 | Pending |
| REL-14 | 57 | Pending |
| REL-15 | 57 | Pending |
| TEST-22 | 58 | Pending |
| TEST-24 | 58 | Pending |
| TEST-25 | 58 | Pending |
| TEST-26 | 58 | Pending |
| FLIP-02 | 58 | Pending |
| FLIP-01 | 59 | Pending |
| FLIP-03 | 59 | Pending |
| DISCGH-02 | 59 | Pending |
| REL-13 | 59 | Pending |

**Coverage:** 46 v0.6 requirements, 46 mapped, 0 orphans, 0 duplicates. Phase 52 (fork-PR CI split) consolidated into Phase 51 per research SUMMARY recommendation (v0.5 tests use recorded provider responses; no live-secret fork-CI path needed in v0.6). Result: 9-phase shape (51-59) instead of 10.

## Traceability - v0.7 Command Center

Single-phase mapping for every v0.7 requirement (Phases 60-68). Source-of-truth: the Phase column in each category table above.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DESIGN-01 | 60 | Complete |
| DESIGN-02 | 60 | Complete |
| DESIGN-03 | 60 | Complete |
| DESIGN-04 | 60 | Complete |
| DESIGN-05 | 60 | Complete |
| SETUP-01 | 61 | Complete |
| SETUP-02 | 61 | Complete |
| SETUP-03 | 61 | Complete |
| SETUP-04 | 61 | Complete |
| SETUP-05 | 61 | Complete |
| SETUP-06 | 61 | Complete |
| VERIFY-02 | 61 | Complete |
| VERIFY-04 | 61 | Complete |
| GH-01 | 61 | Complete |
| KEYS-01 | 62 | Complete |
| KEYS-02 | 62 | Complete |
| KEYS-03 | 62 | Complete |
| KEYS-04 | 62 | Complete |
| VERIFY-01 | 62 | Complete |
| VERIFY-03 | 62 | Complete |
| REMOTE-01 | 62 | Complete |
| MIG-06 | 62 | Complete |
| TEST-27 | 62 | Complete |
| PAGES-01 | 63 | Complete |
| PAGES-02 | 63 | Complete |
| PAGES-03 | 63 | Complete |
| PAGES-04 | 63 | Complete |
| PAGES-05 | 63 | Complete |
| PAGES-06 | 63 | Complete |
| PAGES-07 | 63 | Complete |
| PAGES-08 | 63 | Complete |
| TEAM-01 | 63 | Complete |
| TEAM-02 | 63 | Complete |
| TEAM-03 | 63 | Complete |
| SEED-01 | 63 | Complete |
| SEED-02 | 63 | Complete |
| SEED-03 | 63 | Complete |
| DISC-05 | 64 | Complete |
| DISC-06 | 64 | Complete |
| DISC-07 | 64 | Complete |
| DISC-08 | 64 | Complete |
| DISC-09 | 64 | Complete |
| DISC-10 | 64 | Complete |
| TEST-28 | 64 | Complete |
| SUPA-01 | 65 | Complete |
| SUPA-02 | 65 | Complete |
| SUPA-03 | 65 | Complete |
| SUPA-04 | 65 | Complete |
| SUPA-05 | 65 | Complete |
| TEST-29 | 65 | Complete |
| REMOTE-02 | 66 | Pending |
| REMOTE-03 | 66 | Pending |
| REMOTE-04 | 66 | Pending |
| REMOTE-05 | 66 | Pending |
| TEST-30 | 66 | Pending |
| VERCEL-01 | 67 | Pending |
| VERCEL-02 | 67 | Pending |
| VERCEL-03 | 67 | Pending |
| VERCEL-04 | 67 | Pending |
| GH-02 | 67 | Pending |
| TEST-31 | 67 | Pending |
| REL-16 | 68 | Pending |
| REL-17 | 68 | Pending |

**Coverage:** 63 v0.7 requirements, 63 mapped, 0 orphans, 0 duplicates. VERIFY-01 and VERIFY-03 (server-side probes, key-hash detection) land in Phase 62 with the key-write security substrate; VERIFY-02 and VERIFY-04 (UI status indicators, readiness summary) land in Phase 61 with the read-only integrations surface. REMOTE-01 (starlette pin + loopback guard) lands in Phase 62 as a BLOCKING security prerequisite; REMOTE-02..05 (docs, service install, cron) land in Phase 66. GH-01 (integrations card + verify probe) lands in Phase 61; GH-02 (GitHub tool behind extra) lands in Phase 67. TEST-27..31 each land in the phase that owns the code they exercise.

## Traceability - v0.8 Local-first & Autonomous Research

Single-phase mapping for every v0.8 requirement (Phases 69-76). Source-of-truth: the Phase column in each category table above.

| Requirement | Phase | Status |
|-------------|-------|--------|
| LLM-01 | 69 | Pending |
| LLM-02 | 69 | Pending |
| LLM-03 | 69 | Pending |
| LLM-04 | 69 | Pending |
| TEST-32 | 69 | Pending |
| MEM-04 | 70 | Pending |
| MEM-05 | 70 | Pending |
| MEM-06 | 70 | Pending |
| MEM-07 | 70 | Pending |
| TEST-33 | 70 | Pending |
| MCP-01 | 71 | Pending |
| MCP-02 | 71 | Pending |
| MCP-03 | 71 | Pending |
| MCP-04 | 71 | Pending |
| TEST-34 | 71 | Pending |
| WEB-01 | 72 | Pending |
| WEB-02 | 72 | Pending |
| WEB-03 | 72 | Pending |
| VIS-01 | 72 | Pending |
| VIS-02 | 72 | Pending |
| VIS-03 | 72 | Pending |
| TEST-35 | 72 | Pending |
| RESEARCH-01 | 73 | Pending |
| RESEARCH-02 | 73 | Pending |
| RESEARCH-03 | 73 | Pending |
| RESEARCH-04 | 73 | Pending |
| RESEARCH-05 | 73 | Pending |
| TEST-37 | 73 | Pending |
| SKILL-01 | 74 | Pending |
| SKILL-02 | 74 | Pending |
| SKILL-03 | 74 | Pending |
| SKILL-04 | 74 | Pending |
| MIG-07 | 74 | Pending |
| SHELL-01 | 75 | Pending |
| SHELL-02 | 75 | Pending |
| SHELL-03 | 75 | Pending |
| TEST-36 | 75 | Pending |
| TEST-38 | 76 | Pending |
| REL-18 | 76 | Pending |
| REL-19 | 76 | Pending |

**Coverage:** 40 v0.8 requirements, 40 mapped, 0 orphans, 0 duplicates. WEB-02 (Playwright browsing) lands in Phase 72 with the other web/vision work because Playwright is consumed through MCP (Phase 71 is its prerequisite), not as a separate tool implementation. MIG-07 (v11->v12 migration) lands in Phase 74 with SKILL-01..04 because the skills table is the sole cause of the schema bump; the vector index (MEM-04..07) uses a separate vectors.sqlite file requiring no SCHEMA_VERSION change. TEST-36 (shell-tool-absent proof) lands in Phase 75 with SHELL-01..03 as the security gate test for that phase.
