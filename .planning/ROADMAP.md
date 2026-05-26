# Roadmap: horus-os

## Milestones

- [x] **v0.1 Foundation** (Phases 01-11), shipped 2026-05-23 as v0.1.0. CLI + web chat, Anthropic + Gemini, one agent, six tools, full memory layer, 3-OS install gate, first public release.
- [x] **v0.2 Multi-Agent + Streaming** (Phases 12-21), shipped 2026-05-23 as v0.2.0. Named agent profiles, coordinator-to-sub-agent delegation, provider streaming on both CLI and dashboard, adapter plugin interface.
- [x] **v0.3 Adapter Ecosystem** (Phases 22-31), shipped 2026-05-24 as v0.3.0. Discord, Slack, email, and calendar adapters on top of the v0.2 plugin contract, plus adapter lifecycle hooks and dashboard adapter management.
- [ ] **v0.4 Observability** (Phases 32-39), planning. Local-first cost, latency, and tool-reliability instrumentation. New `llm_calls` + `tool_invocations` child tables, bundled `pricing.json`, `/observability` dashboard tab, `horus-os usage` CLI subcommand, and an opt-in OpenTelemetry exporter behind a `[otel]` extra.

## Phases

<details>
<summary>v0.1 Foundation (Phases 01-11) - SHIPPED 2026-05-23</summary>

- [x] **Phase 01: Repo scaffold and CI** (completed 2026-05-23)
- [x] **Phase 02: Agent runtime core** (completed 2026-05-23)
- [x] **Phase 03: Persistence layer** (completed 2026-05-23)
- [x] **Phase 04: Tool registry** (completed 2026-05-23)
- [x] **Phase 05: Memory layer, read path** (completed 2026-05-23)
- [x] **Phase 06: Memory layer, write path** (completed 2026-05-23)
- [x] **Phase 07: CLI surface** (completed 2026-05-23)
- [x] **Phase 08: Web chat and dashboard** (completed 2026-05-23)
- [x] **Phase 09: Setup wizard with API key onboarding** (completed 2026-05-23)
- [x] **Phase 10: Three-OS install verification** (completed 2026-05-23)
- [x] **Phase 11: First public release** (completed 2026-05-23)

</details>

<details>
<summary>v0.2 Multi-Agent + Streaming (Phases 12-21) - SHIPPED 2026-05-23</summary>

- [x] **Phase 12: Agent profile model and schema migration** (completed 2026-05-23)
- [x] **Phase 13: Multi-agent orchestration runtime** (completed 2026-05-23)
- [x] **Phase 14: Streaming response support** (completed 2026-05-23)
- [x] **Phase 15: CLI multi-agent surface** (completed 2026-05-23)
- [x] **Phase 16: Dashboard multi-agent view and streaming chat** (completed 2026-05-23)
- [x] **Phase 17: Adapter plugin interface** (completed 2026-05-23)
- [x] **Phase 18: Documentation and examples refresh** (completed 2026-05-23)
- [x] **Phase 19: Test surface expansion** (completed 2026-05-23)
- [x] **Phase 20: Three-OS install verification (v0.2)** (completed 2026-05-23)
- [x] **Phase 21: v0.2.0 release** (completed 2026-05-23)

</details>

<details>
<summary>v0.3 Adapter Ecosystem (Phases 22-31) - SHIPPED 2026-05-24</summary>

- [x] **Phase 22: Adapter lifecycle hooks** (completed 2026-05-23)
- [x] **Phase 23: Discord adapter** (completed 2026-05-24)
- [x] **Phase 24: Slack adapter** (completed 2026-05-24)
- [x] **Phase 25: Email adapter** (completed 2026-05-24)
- [x] **Phase 26: Calendar adapter** (completed 2026-05-24)
- [x] **Phase 27: Dashboard adapter management** (completed 2026-05-24)
- [x] **Phase 28: Documentation and examples refresh** (completed 2026-05-24)
- [x] **Phase 29: Test surface expansion** (completed 2026-05-24)
- [x] **Phase 30: Three-OS install verification (v0.3)** (completed 2026-05-24)
- [x] **Phase 31: v0.3.0 release** (completed 2026-05-24)

</details>

### v0.4 Observability (Phases 32-39)

**Milestone Goal:** Turn horus-os from "agents run" into "agents run and you know what they cost, what they took, and what broke." Ship cost-per-LLM-call (USD-denominated), latency p50/p95, and tool reliability rates against a local-first SQLite source of truth. Surface them in a new `/observability` dashboard tab and a `horus-os usage` CLI subcommand. Add an opt-in OpenTelemetry exporter as a v0.3-style adapter for users who already run their own observability stack. Fix two confirmed v0.3 correctness bugs along the way (multi-iteration token undercount; SSE streaming path silently recording $0.00).

**Execution Order:** 32 → 33 → 34 → 35 → (36 ∥ 37) → 38 → 39. Each phase consumes the prior phase's tables or events, so the milestone is mostly sequential. The only legitimate parallel opportunity is Phase 36 (dashboard `/observability` tab) and Phase 37 (`horus-os usage` CLI) because both consume the read-API and query module landed in Phase 35 without depending on each other.

**Three constraints carried from research that ride across phases:**
1. **BASELINE-01 must commit BEFORE Phase 33's METRIC capture lands.** The v0.3 capture-overhead baseline is a one-shot measurement; without it METRIC-05's "within 50ms of v0.3 baseline" assertion has nothing to compare against. The baseline artifact lands in Phase 32 alongside the schema migration.
2. **OTel (Phase 38) ships LAST among the feature phases.** The ObservationBus must have shipped (Phase 32) and been exercised by the SQLite persister plus the runner capture sites (Phases 32, 33) before the OTel subscriber is wired. Shipping earlier would wire `AdapterContext.observation_bus` before the bus is proven internally.
3. **TEST-13 (PII-not-leaked), TEST-14 (bounded-shutdown), and TEST-15 (two-variant install-smoke) appear in Phase 38's Success Criteria block as named observable tests, not as implied items in TEST traceability.** These are the highest-stakes guardrails in the milestone.

- [ ] **Phase 32: Schema migration, persistence skeleton, v0.3 baseline** - Schema v4→v5 additive migration, ObservationBus + SQLitePersister written but not yet wired into the runner, v0.3 capture-overhead baseline artifact committed.
- [ ] **Phase 33: Capture at the runner + SSE branch** - Wrap each `Conversation.send` and `_execute_one` with bus publishes; fix the SSE branch in `server/api.py:_event_stream` so streamed runs never silently record $0; capture-overhead CI benchmark.
- [ ] **Phase 34: Pricing table and cost annotation** - Bundle `pricing.json`, ship `PricingTable` + `CostAnnotator`; user override path; `pricing_missing=1, cost_usd=NULL` for unknown models.
- [ ] **Phase 35: Query module and read APIs** - `observability/queries.py` plus four `/api/observability/*` GET routes plus the `/api/agents` extension with rollup columns; SQLite-side `NTILE(100)` percentiles with sample-count guards.
- [ ] **Phase 36: Observability dashboard tab** - New `/observability` tab (cost-by-agent, latency p50/p95, tool reliability) with window selector, small-sample handling, pricing-staleness banner, and graceful pre-v0.4 trace rendering.
- [ ] **Phase 37: `horus-os usage` CLI subcommand** - `horus-os usage --since 7d --format json|csv|table --by model|tool|agent`; JSON schema pinned and documented.
- [ ] **Phase 38: OpenTelemetry adapter** - Opt-in `OtelAdapter` behind a `[otel]` extra; lifecycle adapter pattern; default-deny content capture; bounded shutdown; three non-negotiable tests (PII-not-leaked, bounded-shutdown, two-variant install-smoke).
- [ ] **Phase 39: Three-OS gate, release, migration doc** - `docs/MIGRATION-v0.3-to-v0.4.md`, `docs/OBSERVABILITY.md`, `docs/OTEL.md` (with explicit Threat model section), `scripts/release_gate.py` (pricing freshness + two-variant install-smoke), 3-OS CI green, v0.4.0 tag and GitHub Release.

## Phase Details

### Phase 22: Adapter lifecycle hooks
**Goal**: Give the Adapter Protocol optional lifecycle hooks (`start`, `stop`) so long-running adapters can manage their own connections, and expose adapter status via `/api/adapters`.
**Depends on**: Phase 17 (Adapter Protocol shipped in v0.2)
**Requirements**: ART-01, ART-02, ART-03
**Success Criteria** (what must be TRUE):
  1. `Adapter` Protocol gains optional `start(ctx) -> awaitable` and `stop() -> awaitable` methods that adapters can implement; existing webhook adapter continues to work without implementing them
  2. FastAPI app lifespan hooks call `start` on each discovered adapter at startup and `stop` at shutdown
  3. `GET /api/adapters` returns a list of adapters with `name`, `status` (running/stopped/error), `last_activity_at`, `error_count`
  4. `WebhookAdapter` (the v0.2 reference) registers as `status: running` (bound but no background task)
**Plans**: TBD

Plans:
- [ ] 22-01: Lifecycle Protocol additions, FastAPI lifespan integration, status API

### Phase 23: Discord adapter
**Goal**: Ship a Discord adapter that listens for mentions and direct messages, routes them to a configured agent profile, and replies in-channel.
**Depends on**: Phase 22
**Requirements**: DISC-01, DISC-02, DISC-03
**Success Criteria** (what must be TRUE):
  1. `DiscordAdapter` connects on `start`, listens for `app_mention` and DMs, runs the configured agent profile, posts the response back to the source channel/DM
  2. Disconnects trigger an exponential-backoff reconnect (configurable cap)
  3. Setup guide documents bot creation, required intents, and `HORUS_OS_DISCORD_TOKEN` env var
  4. Tests mock the Discord SDK and cover: message routing, reconnect, intent validation
**Plans**: TBD

Plans:
- [ ] 23-01: Discord adapter implementation with mocked-SDK tests

### Phase 24: Slack adapter
**Goal**: Ship a Slack adapter that handles `app_mention`, DMs, and slash commands via the Events API, with HMAC signature verification.
**Depends on**: Phase 22
**Requirements**: SLAK-01, SLAK-02, SLAK-03
**Success Criteria** (what must be TRUE):
  1. `SlackAdapter` binds an Events API webhook endpoint that handles `app_mention` and DM events
  2. Signature verification uses Slack's signing secret (HMAC-SHA256 over body + timestamp)
  3. Slash commands route to an agent profile and respond inline
  4. Tests mock the Slack SDK and cover: signature pass/fail, event routing, slash command handling
**Plans**: TBD

Plans:
- [ ] 24-01: Slack adapter implementation with mocked-SDK tests

### Phase 25: Email adapter
**Goal**: Ship an email adapter that polls IMAP for new messages, runs an agent, and replies via SMTP. No new heavy dependencies.
**Depends on**: Phase 22
**Requirements**: MAIL-01, MAIL-02, MAIL-03
**Success Criteria** (what must be TRUE):
  1. `EmailAdapter` connects to IMAP, marks messages seen as it processes them, runs the configured agent on the message body
  2. Replies sent via SMTP preserve `In-Reply-To` and `References` headers so they thread correctly
  3. Configurable poll interval; sleeps cleanly when no messages
  4. Tests use stdlib `imaplib` + `smtplib` mocks and cover: poll, send, thread headers, idle sleep
**Plans**: TBD

Plans:
- [ ] 25-01: Email adapter implementation with mocked tests

### Phase 26: Calendar adapter
**Goal**: Google Calendar adapter exposes a "list today's events" tool agents can call; optional event creation gated behind a permission flag.
**Depends on**: Phase 22
**Requirements**: CAL-01, CAL-02
**Success Criteria** (what must be TRUE):
  1. `CalendarAdapter` exposes a `list_calendar_events_today` tool that agents can invoke; returns events in a structured format
  2. Optional `create_calendar_event` tool, gated behind `HORUS_OS_CALENDAR_WRITE_ALLOWED=true`
  3. OAuth flow documented (Google Cloud project setup, OAuth client, token storage in the data dir)
  4. Tests mock `google-api-python-client` calls and cover: list events, create event (allowed/denied), token refresh path
**Plans**: TBD

Plans:
- [ ] 26-01: Calendar adapter implementation with mocked SDK tests

### Phase 27: Dashboard adapter management
**Goal**: Dashboard `/adapters` view shows configured adapters with health, allows enable/disable, and surfaces per-adapter activity.
**Depends on**: Phase 22, Phase 23, Phase 24, Phase 25, Phase 26
**Requirements**: DASH-3-01, DASH-3-02
**Success Criteria** (what must be TRUE):
  1. `/adapters` page lists configured adapters with status, last activity timestamp, and error count
  2. Each adapter has an enable/disable toggle that calls `POST /api/adapters/{name}/disable` and `/enable`
  3. Health indicator reflects status (running, stopped, error)
  4. v0.2 dashboard surfaces (agents view, trace explorer, SSE chat) continue to work unchanged
**Plans**: TBD
**UI hint**: yes

Plans:
- [ ] 27-01: Adapter management UI, enable/disable endpoints, health indicator

### Phase 28: Documentation and examples refresh
**Goal**: Refresh ARCHITECTURE.md for v0.3, add four adapter example scripts, write the v0.2 to v0.3 migration guide.
**Depends on**: Phase 22, Phase 23, Phase 24, Phase 25, Phase 26, Phase 27
**Requirements**: REL-06
**Success Criteria** (what must be TRUE):
  1. ARCHITECTURE.md documents the lifecycle hooks, adapter status, and dashboard adapter management
  2. `examples/discord_adapter.py`, `slack_adapter.py`, `email_adapter.py`, `calendar_adapter.py` exist and run offline (stub SDKs)
  3. `docs/MIGRATION-v0.2-to-v0.3.md` covers the additive Protocol changes and any user-visible behavior
  4. README links to the new examples and migration guide
**Plans**: TBD

Plans:
- [ ] 28-01: ARCHITECTURE refresh, four examples, migration guide

### Phase 29: Test surface expansion
**Goal**: Cross-adapter E2E flows, lifecycle tests, and shared mocked-SDK fixtures.
**Depends on**: Phase 22, Phase 23, Phase 24, Phase 25, Phase 26, Phase 27
**Requirements**: TEST-07, TEST-08, TEST-09, TEST-10
**Success Criteria** (what must be TRUE):
  1. Lifecycle tests cover start/stop/error transitions for an adapter with all three states
  2. Each of the four new adapters has E2E mocked-SDK tests
  3. Cross-adapter routing test: one trigger reaches multiple adapter channels without race conditions
  4. Overall test count maintains or exceeds the v0.2 baseline (319) plus the new tests
**Plans**: TBD

Plans:
- [ ] 29-01: Lifecycle E2E + cross-adapter routing + mock fixture consolidation

### Phase 30: Three-OS install verification (v0.3)
**Goal**: `install-smoke` job re-runs against the v0.3 feature set and stays green on Ubuntu, macOS, Windows.
**Depends on**: Phase 22, Phase 23, Phase 24, Phase 25, Phase 26, Phase 27, Phase 28, Phase 29
**Requirements**: TEST-07, TEST-08, TEST-09, TEST-10
**Success Criteria** (what must be TRUE):
  1. The `install-smoke` CI job passes on Ubuntu, macOS, and Windows for Python 3.11 and 3.12
  2. Each of the four new adapter modules imports cleanly on each OS
  3. Adapter discovery via entry points works on each OS
  4. Streaming and multi-agent surfaces from v0.2 continue to pass install-smoke
**Plans**: TBD

Plans:
- [ ] 30-01: Update install-smoke for v0.3 surface, verify three-OS green

### Phase 31: v0.3.0 release
**Goal**: Tag v0.3.0, update CHANGELOG with the milestone diff, publish GitHub Release with migration notes.
**Depends on**: Phase 30
**Requirements**: REL-05, REL-06
**Success Criteria** (what must be TRUE):
  1. The `v0.3.0` tag exists on origin
  2. CHANGELOG.md has a complete `[0.3.0]` section describing the four new adapters, lifecycle hooks, and dashboard updates
  3. A GitHub Release at the v0.3.0 tag is published with the CHANGELOG body and a link to the migration guide
  4. Version bumped to `0.3.0` in `pyproject.toml` and `src/horus_os/__init__.py`
**Plans**: TBD

Plans:
- [ ] 31-01: Version bump, CHANGELOG, tag, GitHub Release

### Phase 32: Schema migration, persistence skeleton, v0.3 baseline
**Goal**: Land the v4-to-v5 additive SQLite migration, the `ObservationBus` plus `SQLitePersister` infrastructure (not yet wired into the runner), and commit a `tests/perf/v0_3_baseline.json` artifact so the Phase 33 capture-overhead benchmark has a pinned reference. Pure infrastructure phase, no behavior change for users.
**Depends on**: Phase 31 (v0.3.0 shipped; v0.3 schema and lifecycle hooks in place)
**Requirements**: STORE-01, STORE-02, STORE-03, STORE-04, STORE-05, BASELINE-01, TEST-11, MIG-04
**Success Criteria** (what must be TRUE):
  1. `Database.init()` against a fresh database creates `llm_calls` and `tool_invocations` tables plus the four nullable rollup columns on `traces`; running it twice on a v5 schema is a no-op (idempotent)
  2. `Database.init()` against the checked-in `tests/fixtures/v0_3_database.sqlite3` upgrades cleanly: new columns and tables exist, old `traces.usage` JSON blob still reads, pre-v0.4 rows have NULL on new columns (Pitfall 11 guard)
  3. SQLite pragmas read back as `journal_mode=wal` and `synchronous=NORMAL` after init; never `synchronous=FULL` (Pitfall 8 guard)
  4. `tests/perf/v0_3_baseline.json` artifact committed before Phase 33 starts; captures wall-clock latency for the same fixture 3-iteration agent loop on Ubuntu, macOS, Windows under Python 3.11 + 3.12
  5. Unit tests publish synthetic `ObservationEvent`s directly to `ObservationBus`; `SQLitePersister` inserts one row per event into the right table; no runner code touched yet
**Plans**: 1 plan

Plans:
- [ ] 32-01-PLAN.md: v4-to-v5 migration, ObservationBus + SQLitePersister, v0.3 baseline artifact, lint guard

### Phase 33: Capture at the runner + SSE branch
**Goal**: Wire the bus into the runner so real agent runs publish `LLM_CALL` and `TOOL_CALL` events that the SQLitePersister writes. Fix two confirmed v0.3 correctness bugs: per-iteration token undercount (Pitfall 1) and the streaming path silently recording $0 (Pitfall 2). Cost still NULL at this point; pricing lands in Phase 34.
**Depends on**: Phase 32
**Requirements**: METRIC-01, METRIC-02, METRIC-03, METRIC-04, METRIC-05, TEST-12
**Success Criteria** (what must be TRUE):
  1. A 3-iteration agent run with stubbed `usage={input:100,output:50}` per turn results in `traces.total_input_tokens == 300` and three rows in `llm_calls`; the v0.3 "last iteration overwrites" bug is structurally fixed (Pitfall 1)
  2. A streaming run via `/api/chat/stream` produces an `llm_calls` row with non-zero `input_tokens` and `output_tokens` read from `stream.get_final_message().usage` (Anthropic) or `response.usage_metadata` (Gemini); the SSE path never silently lands at $0 (Pitfall 2)
  3. Every `llm_calls` and `tool_invocations` row uses `time.perf_counter()` for `latency_ms`; a ruff/grep CI rule fails the build if `time.time()` appears inside `horus_os/observability/`, `agent.py`, or `tools/loop.py`; `SQLitePersister` asserts `latency_ms >= 0` and refuses to insert negatives (Pitfall 3)
  4. Tool invocations persist `status` (success / error), `retry_count` (best-effort, NULL allowed if SDK does not surface it), and `last_error_text` (exception class name only, never user-supplied content) (Pitfall 9 substrate)
  5. Capture-overhead benchmark in CI runs the fixture 5-iteration / 3-tool-call loop on the 3-OS matrix and asserts total wall-clock is within 50ms of the Phase 32 baseline (METRIC-05, Pitfall 8 guard)
**Plans**: TBD

Plans:
- [ ] 33-01: Runner + SSE capture sites, lint rule, capture-overhead benchmark

### Phase 34: Pricing table and cost annotation
**Goal**: Ship `pricing.json` as package data plus the `PricingTable` and `CostAnnotator` that turn token counts into USD costs. Cost annotation subscribes BEFORE the persister so each `LLM_CALL` event is mutated in place. Unknown models persist with `pricing_missing=1, cost_usd=NULL` (NULL is honest, zero is a lie).
**Depends on**: Phase 33
**Requirements**: PRICE-01, PRICE-02, PRICE-03, PRICE-04, PRICE-05
**Success Criteria** (what must be TRUE):
  1. Bundled `src/horus_os/observability/pricing.json` ships current Anthropic + Gemini rates including separate `input_per_million`, `output_per_million`, `cache_write_per_million`, `cache_read_per_million` columns; schema mirrors LiteLLM's `model_prices_and_context_window.json` shape (PRICE-01, PRICE-02)
  2. A known-model `LLM_CALL` event with `input_tokens=1000, output_tokens=200, cache_read_input_tokens=500` lands in `llm_calls` with `cost_usd` equal to the hand-computed cache-aware sum, rounded to 6 decimal places (PRICE-02)
  3. An unknown-model event lands with `pricing_missing=1` and `cost_usd=NULL`; never `cost_usd=0` for an uncovered model (PRICE-03, Pitfall 5)
  4. `HORUS_OS_PRICING_PATH` env var (and `cfg.pricing_path` config field) override the bundled file; a fixture test confirms the override path takes precedence (PRICE-04)
  5. `pricing.json` carries `version`, `updated_at`, and `release_version` top-level fields; `PricingTable.is_stale(now, threshold_days=30)` returns True past 30 days for the dashboard banner Phase 36 will render (PRICE-05)
**Plans**: TBD

Plans:
- [ ] 34-01: PricingTable, pricing.json bundle, CostAnnotator subscriber, user override path

### Phase 35: Query module and read APIs
**Goal**: Build `observability/queries.py` once so the dashboard (Phase 36) and CLI (Phase 37) cannot drift. All percentiles via SQLite-side `NTILE(100) OVER (...)`, never aggregate-of-aggregates. Ship the four new `/api/observability/*` GET routes and the `/api/agents` extension that adds rollup columns to the existing v0.3 surface.
**Depends on**: Phase 34
**Requirements**: DASH-4-04
**Success Criteria** (what must be TRUE):
  1. `observability/queries.py` exposes `agent_totals(window)`, `cost_by_agent(window)`, `latency_p50_p95(window)`, `tool_reliability(window)` as pure functions returning JSON-serializable dicts; all aggregation in SQL, no Python percentile math (Pitfall 10 anti-pattern guard)
  2. Four new GET routes (`/api/observability/cost`, `/latency`, `/tools`, `/llm-calls`) accept `?since=24h|7d|30d` and return the query-module output as JSON; default window is `7d`
  3. Existing `/api/agents` route gains `total_runs`, `total_cost_usd`, `latency_p50`, `latency_p95` fields per agent, sourced from the v0.4 rollup columns; pre-v0.4 rows contribute NULL and are excluded from cost sums via `COALESCE` (DASH-4-04 backend half, Pitfall 11 NULL handling)
  4. Percentile queries return NULL (not 0) for windows with no data; queries return raw `sample_count` alongside `p50`/`p95` so callers can apply the n-threshold rule (Pitfall 10)
  5. Reliability query honors the `status` enum so `retry_then_success` rows do not count toward `error_count`; query never reads `error_message` content (Pitfall 9)
**Plans**: TBD

Plans:
- [ ] 35-01: queries.py module, four new /api/observability routes, /api/agents extension

### Phase 36: Observability dashboard tab
**Goal**: New `/observability` tab with three panels (cost-by-agent, latency p50/p95, tool reliability) plus the small UI tweak that extends the existing `/agents` tab with the cost and latency columns sourced from Phase 35's `/api/agents` extension. Same vanilla-JS pattern as the v0.3 Adapters tab. Render NULLs honestly so pre-v0.4 runs never look like $0.
**Depends on**: Phase 35
**Requirements**: DASH-4-01, DASH-4-02, DASH-4-03, DASH-4-05
**Success Criteria** (what must be TRUE):
  1. `/observability` tab renders three panels (cost-by-agent bar chart, latency p50/p95 table, tool reliability list) with a window selector (24h / 7d / 30d, default 7d) that drives all three (DASH-4-01, DASH-4-02)
  2. Percentile cells with `sample_count < 10` render as "—" with hover text "need at least 10 runs for percentile"; never as a number, never as `0ms` (DASH-4-03, Pitfall 10)
  3. Pre-v0.4 trace rows in the agents table render "—" for new cost and latency columns with hover text "no cost data captured before v0.4"; a separate small tile shows "N runs from before v0.4 with no cost data" so the missing dollars are explained, not hidden (DASH-4-05, Pitfall 11)
  4. Pricing-staleness banner renders when `pricing.json.updated_at` is more than 30 days old; yellow at 30-60 days, red at 90+; copy includes the user override path (Pitfall 5)
  5. Existing `/agents` tab shows the new `total_cost_usd`, `latency_p50`, `latency_p95` columns sourced from the Phase 35 `/api/agents` extension; v0.3 surfaces (trace explorer, SSE chat, Adapters tab) keep working unchanged
**Plans**: TBD
**UI hint**: yes

Plans:
- [ ] 36-01: /observability tab, /agents tab extension, staleness banner, small-sample render

### Phase 37: `horus-os usage` CLI subcommand
**Goal**: Ship `horus-os usage --since 7d --format json|csv|table --by model|tool|agent` as an argparse subparser. Reuses `observability/queries.py` from Phase 35 so the CLI and dashboard cannot disagree. Stdlib `json` and `csv`; no new dependencies.
**Depends on**: Phase 35
**Requirements**: USAGE-01, USAGE-02, USAGE-03, USAGE-04
**Success Criteria** (what must be TRUE):
  1. `horus-os usage --since 7d` returns a usage report over a configurable window; `--since` accepts `24h`, `7d`, `30d`, or any `Nh`/`Nd` form (USAGE-01)
  2. `--format json|csv|table` controls output shape; the JSON output schema is documented in `docs/CLI.md` and pinned by a test that diffs the output against a fixture (USAGE-02)
  3. `--by model|tool|agent` slices the report into per-model, per-tool, or per-agent views; output for each shape matches the corresponding `/api/observability/*` route byte-for-byte where the data overlaps (USAGE-03)
  4. Costs render rounded to 6 decimal places, durations to integer ms, consistent units across all three formats; a `jq` pipe on the JSON output never trips on float-precision noise like `0.04200000000000001` (USAGE-04, Pitfall float-precision UX trap)
**Plans**: TBD

Plans:
- [ ] 37-01: usage subparser, three formatters, JSON schema pin, docs/CLI.md entry

### Phase 38: OpenTelemetry adapter
**Goal**: Highest-risk phase, lands LAST among the feature phases. Ship `OtelAdapter` as a v0.3-style `LifecycleAdapter` behind a `[otel]` extra. Lazy imports so a bare `pip install horus-os` never sees `opentelemetry-*`. Default-deny content capture: prompt and completion bodies are NEVER attached to spans by default; opt-in via `HORUS_OS_OTEL_CAPTURE_CONTENT=true` plus a redactor allowlist. `BatchSpanProcessor` always, never `SimpleSpanProcessor` in production. Bounded `force_flush(2000)` then `shutdown()` so Ctrl-C never blocks for 60 seconds (Pitfalls 6, 7, 12).
**Depends on**: Phase 37 (and the ObservationBus has now had five commits of stability across Phases 32-37)
**Requirements**: OTEL-01, OTEL-02, OTEL-03, OTEL-04, OTEL-05, OTEL-06, OTEL-07, TEST-13, TEST-14, TEST-15
**Success Criteria** (what must be TRUE):
  1. `pip install horus-os` (no extra) installs zero `opentelemetry-*` packages; `from horus_os.adapters.otel_adapter import OtelAdapter` succeeds; `OtelAdapter().start(ctx)` raises a clean `RuntimeError("OTel adapter requires 'pip install horus-os[otel]'")`, never `ModuleNotFoundError` (OTEL-01, OTEL-07, Pitfall 12)
  2. **TEST-13 PII-not-leaked:** an `InMemorySpanExporter` fixture receives an `LLM_CALL` event whose prompt contains the literal `AKIAIOSFODNN7EXAMPLE`; the exported span contains `gen_ai.usage.input_tokens` and `horus_os.cost_usd` but DOES NOT contain the literal string `AKIAIOSFODNN7EXAMPLE` anywhere in its attributes (OTEL-03, OTEL-04, Pitfall 7)
  3. **TEST-14 bounded-shutdown:** `OtelAdapter` pointed at `http://127.0.0.1:1` (closed port), one event published, `await adapter.stop()` completes in less than 3 seconds wall clock; `BatchSpanProcessor` (never `SimpleSpanProcessor`) is used; `force_flush(timeout_millis=2000)` precedes `shutdown()` (OTEL-02, OTEL-06, Pitfall 6)
  4. **TEST-15 two-variant install-smoke:** parallel CI jobs run on the 3-OS matrix; the `[dev]` job (no otel) asserts the import-plus-clean-RuntimeError contract from criterion 1; the `[dev,otel]` job asserts `start(ctx)` succeeds when `OTEL_EXPORTER_OTLP_ENDPOINT` is set and spans appear in a local `InMemorySpanExporter` (OTEL-07, Pitfall 12)
  5. Span attribute names come from `horus_os/_observability/semconv.py` constants; emitted attributes are exactly `gen_ai.system`, `gen_ai.operation.name`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.usage.cached_tokens`, `horus_os.cost_usd`, `error.type`; never the deprecated `gen_ai.prompt` / `gen_ai.completion`; never `gen_ai.input.messages` / `gen_ai.output.messages` in default mode (OTEL-05)
**Plans**: TBD

Plans:
- [ ] 38-01: OtelAdapter, lazy imports, default-deny content, redactor allowlist, three non-negotiable tests

### Phase 39: Three-OS gate, release, migration doc
**Goal**: The release-quality gate. Document the v0.3-to-v0.4 migration, the observability surface, and the OTel threat model. Ship `scripts/release_gate.py` carrying both the pricing freshness check and the two-variant install-smoke matrix as a release-blocking gate. Three-OS CI green on the full test suite plus all v0.4 tests. Tag v0.4.0 and publish the GitHub Release.
**Depends on**: Phase 38
**Requirements**: REL-07, REL-08, REL-09
**Success Criteria** (what must be TRUE):
  1. `docs/MIGRATION-v0.3-to-v0.4.md`, `docs/OBSERVABILITY.md`, and `docs/OTEL.md` exist; `docs/OTEL.md` contains an explicit "Threat model" section covering what an OTel collector receives in default mode versus content-capture-enabled mode (REL-09, Pitfall 7)
  2. `scripts/release_gate.py` enforces both (a) `pricing.json.updated_at` within 14 days of the tag date and (b) the two-variant install-smoke matrix from Phase 38 is green; release workflow refuses to tag when either fails (REL-08, Pitfalls 5 and 12)
  3. Three-OS CI matrix (macOS + Ubuntu + Windows × Python 3.11 + 3.12) green on the full test suite plus the new v0.4 tests including the capture-overhead benchmark from Phase 33 and the three non-negotiable OTel tests from Phase 38
  4. `v0.4.0` tag exists on origin; CHANGELOG has a complete `[0.4.0]` section describing the new cost / latency / reliability surface, the OTel opt-in adapter, the two v0.3 correctness fixes, and the v0.3-to-v0.4 migration; GitHub Release at the tag is published with the CHANGELOG body and a link to the migration guide; version bumped to `0.4.0` in `pyproject.toml` and `src/horus_os/__init__.py` (REL-07)
**Plans**: TBD

Plans:
- [ ] 39-01: Docs trio, release_gate.py, version bump, CHANGELOG, tag, GitHub Release

## Progress

**Execution Order (v0.3):** 22 → (23 ∥ 24 ∥ 25 ∥ 26) → 27 → 28 → 29 → 30 → 31
**Execution Order (v0.4):** 32 → 33 → 34 → 35 → (36 ∥ 37) → 38 → 39

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 01-11 | v0.1 | 13/13 | Complete | 2026-05-23 |
| 12-21 | v0.2 | 11/11 | Complete | 2026-05-23 |
| 22. Adapter lifecycle hooks | v0.3 | 1/1 | Complete | 2026-05-23 |
| 23. Discord adapter | v0.3 | 1/1 | Complete | 2026-05-24 |
| 24. Slack adapter | v0.3 | 1/1 | Complete | 2026-05-24 |
| 25. Email adapter | v0.3 | 1/1 | Complete | 2026-05-24 |
| 26. Calendar adapter | v0.3 | 1/1 | Complete | 2026-05-24 |
| 27. Dashboard adapter management | v0.3 | 1/1 | Complete | 2026-05-24 |
| 28. Documentation and examples refresh | v0.3 | 1/1 | Complete | 2026-05-24 |
| 29. Test surface expansion | v0.3 | 1/1 | Complete | 2026-05-24 |
| 30. Three-OS install verification (v0.3) | v0.3 | 1/1 | Complete | 2026-05-24 |
| 31. v0.3.0 release | v0.3 | 1/1 | Complete | 2026-05-24 |
| 32. Schema migration, persistence skeleton, v0.3 baseline | v0.4 | 0/1 | Not started | - |
| 33. Capture at the runner + SSE branch | v0.4 | 0/1 | Not started | - |
| 34. Pricing table and cost annotation | v0.4 | 0/1 | Not started | - |
| 35. Query module and read APIs | v0.4 | 0/1 | Not started | - |
| 36. Observability dashboard tab | v0.4 | 0/1 | Not started | - |
| 37. `horus-os usage` CLI subcommand | v0.4 | 0/1 | Not started | - |
| 38. OpenTelemetry adapter | v0.4 | 0/1 | Not started | - |
| 39. Three-OS gate, release, migration doc | v0.4 | 0/1 | Not started | - |
