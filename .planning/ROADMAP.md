# Roadmap: horus-os

## Milestones

- [x] **v0.1 Foundation** (Phases 01-11), shipped 2026-05-23 as v0.1.0. CLI + web chat, Anthropic + Gemini, one agent, six tools, full memory layer, 3-OS install gate, first public release.
- [x] **v0.2 Multi-Agent + Streaming** (Phases 12-21), shipped 2026-05-23 as v0.2.0. Named agent profiles, coordinator-to-sub-agent delegation, provider streaming on both CLI and dashboard, adapter plugin interface.
- [x] **v0.3 Adapter Ecosystem** (Phases 22-31), shipped 2026-05-24 as v0.3.0. Discord, Slack, email, and calendar adapters on top of the v0.2 plugin contract, plus adapter lifecycle hooks and dashboard adapter management.
- [x] **v0.4 Observability** (Phases 32-39), shipped 2026-05-26 as v0.4.0. Local-first cost, latency, and tool-reliability instrumentation. New `llm_calls` + `tool_invocations` child tables, bundled `pricing.json`, `/observability` dashboard tab, `horus-os usage` CLI subcommand, opt-in OpenTelemetry exporter behind a `[otel]` extra.
- [ ] **v0.5 Plugin System** (Phases 40-50), planning. Third-party plugin runtime: TOML manifest contract, entry-point + filesystem discovery, default-deny capability grants, two-phase `pip install` flow, in-process loader with bounded lifecycle and failure isolation, `/plugins` dashboard tab, per-plugin observability, reference plugin, additive v5→v6 schema migration.

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

<details>
<summary>v0.4 Observability (Phases 32-39) - SHIPPED 2026-05-26</summary>

- [x] **Phase 32: Schema migration, persistence skeleton, v0.3 baseline** (completed 2026-05-26)
- [x] **Phase 33: Capture at the runner + SSE branch** (completed 2026-05-26)
- [x] **Phase 34: Pricing table and cost annotation** (completed 2026-05-26)
- [x] **Phase 35: Query module and read APIs** (completed 2026-05-26)
- [x] **Phase 36: Observability dashboard tab** (completed 2026-05-26)
- [x] **Phase 37: `horus-os usage` CLI subcommand** (completed 2026-05-26)
- [x] **Phase 38: OpenTelemetry adapter** (completed 2026-05-26)
- [x] **Phase 39: Three-OS gate, release, migration doc** (completed 2026-05-26)

</details>

### v0.5 Plugin System (Phases 40-50)

**Milestone Goal:** Turn horus-os from "built-in tools and adapters only" into "anyone can ship a horus-os plugin." A TOML manifest contract, entry-point + filesystem discovery, default-deny capability grants persisted in SQLite, a `pip`-wrapped two-phase installer, an in-process loader with bounded lifecycle and failure isolation, a `/plugins` dashboard tab, per-plugin observability rolling up on the v0.4 ObservationBus, one reference plugin, and an additive v5→v6 schema migration. Anti-pattern explicitly rejected: OS sandboxing, hosted catalog, hot-reload, default-allow grants. Trust model: "you `pip install`-ed it; the manifest declares what it touches; you grant before it runs."

**Execution Order:** 40 → 41 → 42 → 43 → (44 ∥ 45) → 46 → 47 → 48 → 49 → 50. Mostly sequential because each phase consumes prior phase's substrate. The only legitimate parallel opportunity is Phase 44 (installer CLI) and Phase 45 (dashboard tab + observability extension): both consume the grant table + registry shipped in Phase 43 without depending on each other (mirrors v0.4's Phase 36 ∥ 37).

**Six constraints carried from research that ride across phases:**
1. **`plugins/api.py` is the SINGLE public API surface** (Pitfall 8). Defined in Phase 41, enforced by a ruff custom rule in Phase 48 against the reference plugin (`from horus_os` imports outside `horus_os.plugins.api` fail CI).
2. **Manifest hash drives re-prompt** (PERMISSION-02). `grant_hash = sha256(capabilities_set)`; manifest-hash diff on upgrade flips previously-granted `plugin_capabilities` rows to `state="pending"`. Lands in Phase 43.
3. **Bounded `asyncio.wait_for(start, timeout=2.0)`** matches v0.4 Phase 38 OtelAdapter shape (`force_flush(timeout_millis=2000)` precedent). Literal `timeout=2.0` appears in Phase 43's success criteria as a verifiable artifact.
4. **Two-phase install** for INSTALL-02: phase A `pip download --no-deps` → phase B validate manifest + capability prompt → phase C `pip install --no-deps --no-build-isolation <wheel>`. The literal three-step sequence is a Phase 44 success criterion.
5. **v5→v6 migration is additive only** (MIG-05). Three new tables (`plugins`, `plugin_capabilities`, `plugin_status`) + two NULLABLE columns (`llm_calls.plugin_name`, `tool_invocations.plugin_name`) + one index (`idx_tool_invocations_plugin`). Lands in Phase 41. v0.4 fixture round-trip is mandatory in Phase 41 and re-asserted in Phase 49's release gate.
6. **Two new direct deps** in `pyproject.toml` base `[project.dependencies]` (not an optional extra): `pydantic>=2.7,<3` and `packaging>=24.0`. Lands in Phase 41. v0.4 shipped with `dependencies = []`; this is the deliberate first runtime-dep addition called out in REL-10.

- [x] **Phase 40: v0.5 baseline artifact** - Mirror of v0.4 Phase 32. Commit `tests/perf/v0_4_baseline.json` snapshotting v0.4 cold-start + zero-plugin discovery overhead on the 3-OS matrix so Phase 42's <100ms cold-start benchmark has a pinned reference. Pure infrastructure; no behavior change for users. (completed 2026-05-26)
- [x] **Phase 41: Manifest schema, public API, persistence migration** - Define `PluginSpec`, `MANIFEST_V1_SCHEMA` (pydantic v2), `plugins/api.py` single-public-surface module, `capability_catalog.py` closed enum. Land v5→v6 additive SQLite migration (three new tables + two NULLABLE plugin_name columns + one index). Add `pydantic>=2.7,<3` and `packaging>=24.0` to base `[project.dependencies]`. v0.4 fixture round-trip green. (completed 2026-05-26)
- [ ] **Phase 42: Discovery + loading + failure isolation** - `plugins/discovery.py` (entry-points + filesystem walk), `plugins/loader.py` (guard stubbed pass-through; CapabilityGuard wraps land in Phase 43), `plugins/registry.py`. Ban `pkg_resources` via ruff custom rule. Cold-start <100ms benchmark vs Phase 40 baseline. Broken-plugin fixtures (invalid TOML, schema-failing manifest, import-raising module) surface as `status="error"` without crashing host.
- [ ] **Phase 43: Permission model + bounded lifecycle** - `plugins/permissions.py` with `PermissionGate` + `CapabilityGuard`; helper shims (`ctx.filesystem`, `ctx.secrets`, `ctx.net`); per-version grants keyed on `(plugin_name, plugin_version, capability)` AND tied to `manifest_hash`; `DEFAULT_GRANT_POLICY = "deny"` constant; bounded `asyncio.wait_for(start, timeout=2.0)` / `asyncio.wait_for(stop, timeout=2.0)` lifecycle wrappers. `--disable-all-plugins` CLI escape hatch.
- [ ] **Phase 44: Installer flow (two-phase install + upgrade diff)** - `cli/plugins_cmd.py` with `install/uninstall/list/info/enable/disable/update/grant/revoke`. Two-phase install via `subprocess.check_call([sys.executable, "-m", "pip", ...])`. Refuse install outside venv (`--allow-system-python` escape hatch), refuse sdists by default (`--allow-sdist`), refuse wheels with `.pth` in RECORD, refuse runtime-dep downgrade. First-install grant prompt with plain-English capability descriptions.
- [ ] **Phase 45: REST API + `/plugins` dashboard tab + per-plugin observability** - Six `/api/plugins` routes (list/get/enable/disable/grant/revoke). `/plugins` dashboard tab (vanilla JS, mirrors v0.3 `/adapters` and v0.4 `/observability` patterns) with capability chips, grant modal, enable/disable toggle. `/api/observability/plugins` route + dashboard rollup tile ("by plugin" alongside existing "by agent" and "by tool"). OBSERVE-02 LLM-cost-attribution-by-plugin if the column-add is cheap.
- [ ] **Phase 46: Test surface (three-tier fixtures + pitfall regression suite)** - Tier 1: in-process unit tests against `PluginSpec` objects. Tier 2: `fake_plugin_entry_points` monkeypatch fixture. Tier 3: `clean_venv` fixture opt-in via `@pytest.mark.installer_e2e`. `tests/test_plugin_pitfalls/` with one regression test per pitfall in `.planning/research/PITFALLS.md` (minimum 12 tests, names map 1:1 to pitfall numbers).
- [ ] **Phase 47: Documentation refresh (docs trio)** - `docs/PLUGINS.md` (plugin-author guide: manifest + capabilities + lifecycle + testing + walkthrough of the four reference-plugin scenarios). `docs/PLUGIN-SECURITY.md` with explicit "Threat model" section containing the literal sentence "plugins execute in the horus-os Python process" and enumerating the capability-grant trust contract. `docs/MIGRATION-v0.4-to-v0.5.md` covering v5→v6 schema + the two new direct deps.
- [ ] **Phase 48: Reference plugin (`horus-os-example-plugin`)** - `examples/horus-os-example-plugin/` shipped as a separate package with its own `pyproject.toml` and `horus-plugin.toml`. Demonstrates four scenarios: simple tool + capability check, config-reading tool, lifecycle adapter with start/stop, plugin registering both tool + adapter. CI lint rejects any `from horus_os` import that doesn't come from `horus_os.plugins.api` (TEST-21, ruff custom rule).
- [ ] **Phase 49: Three-OS install gate + release-gate extension** - 3-OS install-smoke job (macOS + Ubuntu + Windows × Python 3.11 + 3.12) installs the reference plugin via `pip install -e ./examples/horus-os-example-plugin` and asserts `status="running"` in `/api/plugins`. `scripts/release_gate.py` gains: (a) docs-drift check between `MANIFEST_V1_SCHEMA` runtime constant and `docs/manifest-v1.schema.json`; (b) plugin install-smoke on each OS from TEST-20; (c) reference plugin manifest validates against the runtime schema; (d) v0.4 fixture round-trip survives the v5→v6 migration.
- [ ] **Phase 50: v0.5.0 release** - Tag `v0.5.0`, finalize CHANGELOG `[0.5.0]` section, GitHub Release with migration-notes link. Version bumped to `0.5.0` in `pyproject.toml` and `src/horus_os/__init__.py`. Release-gate green on all 4 v0.5 checks plus the four v0.4 checks carried forward.

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
- [x] 32-01-PLAN.md: v4-to-v5 migration, ObservationBus + SQLitePersister, v0.3 baseline artifact, lint guard

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
**Plans**: 1 plan

Plans:
- [x] 33-01-PLAN.md: Runner + SSE capture sites with trace_id threading, Pitfall 1/2/3/9 regression tests, lint guard extension, 3-OS capture-overhead benchmark

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
**Plans**: 1 plan

Plans:
- [x] 34-01-PLAN.md: PricingTable, bundled pricing.json + package-data wiring, CostAnnotator subscriber with cache-aware math, user override, Pitfall 5 defence-in-depth

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
**Plans**: 1 plan

Plans:
- [x] 35-01-PLAN.md: queries.py (parse_window + agent_totals + cost_by_agent + latency_p50_p95 + tool_reliability), four new /api/observability routes, /api/agents extension with rollup columns (DASH-4-04 backend half)

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
**Plans**: 1 plan
**UI hint**: yes

Plans:
- [x] 36-01-PLAN.md: /observability tab + /agents extension + pricing-staleness banner + small-sample + NULL render contracts

### Phase 37: `horus-os usage` CLI subcommand
**Goal**: Ship `horus-os usage --since 7d --format json|csv|table --by model|tool|agent` as an argparse subparser. Reuses `observability/queries.py` from Phase 35 so the CLI and dashboard cannot disagree. Stdlib `json` and `csv`; no new dependencies.
**Depends on**: Phase 35
**Requirements**: USAGE-01, USAGE-02, USAGE-03, USAGE-04
**Success Criteria** (what must be TRUE):
  1. `horus-os usage --since 7d` returns a usage report over a configurable window; `--since` accepts `24h`, `7d`, `30d`, or any `Nh`/`Nd` form (USAGE-01)
  2. `--format json|csv|table` controls output shape; the JSON output schema is documented in `docs/CLI.md` and pinned by a test that diffs the output against a fixture (USAGE-02)
  3. `--by model|tool|agent` slices the report into per-model, per-tool, or per-agent views; output for each shape matches the corresponding `/api/observability/*` route byte-for-byte where the data overlaps (USAGE-03)
  4. Costs render rounded to 6 decimal places, durations to integer ms, consistent units across all three formats; a `jq` pipe on the JSON output never trips on float-precision noise like `0.04200000000000001` (USAGE-04, Pitfall float-precision UX trap)
**Plans**: 1 plan

Plans:
- [x] 37-01-PLAN.md: usage subparser, three formatters (JSON/CSV/table) with float-precision rounding, additive cost_by_model query + matching /api/observability/cost-by-model route for --by model byte-for-byte parity, JSON schema pin, docs/CLI.md entry

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
**Plans**: 1 plan

Plans:
- [x] 38-01-PLAN.md: OtelAdapter (lazy import + RuntimeError contract), BatchSpanProcessor + bounded shutdown, 8 canonical GenAI attrs from semconv module, redactor allowlist + default-deny content capture, three non-negotiable tests (TEST-13 PII / TEST-14 bounded-shutdown / TEST-15 two-variant install-smoke), docs/OTEL.md with Threat model section

### Phase 39: Three-OS gate, release, migration doc
**Goal**: The release-quality gate. Document the v0.3-to-v0.4 migration, the observability surface, and the OTel threat model. Ship `scripts/release_gate.py` carrying both the pricing freshness check and the two-variant install-smoke matrix as a release-blocking gate. Three-OS CI green on the full test suite plus all v0.4 tests. Tag v0.4.0 and publish the GitHub Release.
**Depends on**: Phase 38
**Requirements**: REL-07, REL-08, REL-09
**Success Criteria** (what must be TRUE):
  1. `docs/MIGRATION-v0.3-to-v0.4.md`, `docs/OBSERVABILITY.md`, and `docs/OTEL.md` exist; `docs/OTEL.md` contains an explicit "Threat model" section covering what an OTel collector receives in default mode versus content-capture-enabled mode (REL-09, Pitfall 7)
  2. `scripts/release_gate.py` enforces both (a) `pricing.json.updated_at` within 14 days of the tag date and (b) the two-variant install-smoke matrix from Phase 38 is green; release workflow refuses to tag when either fails (REL-08, Pitfalls 5 and 12)
  3. Three-OS CI matrix (macOS + Ubuntu + Windows × Python 3.11 + 3.12) green on the full test suite plus the new v0.4 tests including the capture-overhead benchmark from Phase 33 and the three non-negotiable OTel tests from Phase 38
  4. `v0.4.0` tag exists on origin; CHANGELOG has a complete `[0.4.0]` section describing the new cost / latency / reliability surface, the OTel opt-in adapter, the two v0.3 correctness fixes, and the v0.3-to-v0.4 migration; GitHub Release at the tag is published with the CHANGELOG body and a link to the migration guide; version bumped to `0.4.0` in `pyproject.toml` and `src/horus_os/__init__.py` (REL-07)
**Plans**: 1 plan

Plans:
- [x] 39-01-PLAN.md: Docs trio (MIGRATION + OBSERVABILITY + OTEL polish + RELEASE), scripts/release_gate.py + tests, version bump to 0.4.0, CHANGELOG promotion (STOP-BEFORE-TAG; maintainer runs git tag + gh release after approval)

### Phase 40: v0.5 baseline artifact
**Goal**: Mirror of v0.4 Phase 32's structure. Commit a `tests/perf/v0_4_baseline.json` artifact that snapshots v0.4 cold-start time and discovery overhead with zero installed plugins on the 3-OS matrix, so Phase 42's cold-start <100ms benchmark has a pinned reference. Pure infrastructure phase; no behavior change for users, no v0.5 runtime code yet.
**Depends on**: Phase 39 (v0.4.0 shipped; v0.4 schema and observability surface in place)
**Requirements**: BASELINE-02
**Success Criteria** (what must be TRUE):
  1. `tests/perf/v0_4_baseline.json` artifact committed before any Phase 42 discovery work lands; captures wall-clock cold-start time for `from horus_os.server.api import create_app; create_app()` on Ubuntu, macOS, Windows under Python 3.11 + 3.12 (BASELINE-02)
  2. Baseline artifact captures discovery overhead with zero installed plugins (no entry points in `horus_os.plugins` group; empty `~/.horus-os/plugins/` directory); v4 baseline carries `version`, `captured_at`, `platform`, `python_version`, `cold_start_ms`, `discovery_ms` fields per OS/Python combination
  3. A 3-OS CI workflow step captures the baseline numbers in a reproducible manner (same fixture as v0.3 baseline pattern); committed values match the workflow output within float tolerance so a future re-capture diffs cleanly
  4. No runtime code touched in this phase; pure `tests/perf/` artifact + the `scripts/capture_v0_4_baseline.py` capture script if one is needed for reproducibility; `pip install -e .` continues to work unchanged
**Plans**: 1 plan

Plans:
- [x] 40-01-PLAN.md — Capture script + seeded v0_4_baseline.json (maintainer row + linux/win32 placeholders) + schema-shape pytest

### Phase 41: Manifest schema, public API, persistence migration
**Goal**: Pure infrastructure phase landing the entire schema substrate that every later v0.5 phase consumes. Ship `PluginSpec` (frozen dataclass), `MANIFEST_V1_SCHEMA` (pydantic v2 model with `manifest_version: int` required from day one), `plugins/api.py` as the single public re-export surface, `capability_catalog.py` closed enum with plain-English descriptions. Land the v5→v6 additive SQLite migration: three new tables (`plugins`, `plugin_capabilities`, `plugin_status`) + two NULLABLE columns (`llm_calls.plugin_name`, `tool_invocations.plugin_name`) + one index (`idx_tool_invocations_plugin`). Add the two new base direct deps (`pydantic>=2.7,<3` and `packaging>=24.0`) to `[project.dependencies]`. No discovery, no loader, no behavior change yet.
**Depends on**: Phase 40 (baseline artifact pinned)
**Requirements**: MANIFEST-01, MANIFEST-02, MANIFEST-03, MANIFEST-04, MANIFEST-05, OBSERVE-01, MIG-05
**Success Criteria** (what must be TRUE):
  1. `Database.init()` against a fresh database creates `plugins`, `plugin_capabilities`, `plugin_status` tables and adds `plugin_name TEXT` NULLABLE columns to `llm_calls` and `tool_invocations` plus `idx_tool_invocations_plugin(plugin_name, created_at)`; running `init()` twice on a v6 schema is a no-op (idempotent); `Database.init()` against the checked-in `tests/fixtures/v0_4_database.sqlite3` upgrades cleanly and pre-v0.5 rows have NULL `plugin_name` (MIG-05, OBSERVE-01, Pitfall 9)
  2. `MANIFEST_V1_SCHEMA` (pydantic v2 `BaseModel`) accepts a valid `horus-plugin.toml` parsed via `tomllib.loads`; requires `manifest_version: int` and rejects manifests without it; declares `name`, `version`, `description`, `author`, `license`, `homepage`, `issue_tracker`, `horus_os_compat`, `[contributions]` tool + adapter dotted-path entries, `[capabilities]` list (MANIFEST-01, MANIFEST-02, MANIFEST-03, MANIFEST-04)
  3. `validate_manifest()` parses `horus_os_compat` as a `packaging.SpecifierSet` and rejects mismatches against `horus_os.__version__` before load; `format_validation_error()` turns pydantic `ValidationError.errors()` into a plain-English line-numbered string the installer (Phase 44) renders verbatim; one fixture test asserts a bad manifest yields a human-readable error mentioning the offending key (MANIFEST-02, MANIFEST-05)
  4. `capability_catalog.py` exports a closed enum (`Capability` or equivalent typed-string set) containing at minimum `filesystem.read`, `filesystem.write`, `net.outbound`, `secrets.read`; every entry carries a plain-English `description` attribute; `MANIFEST_V1_SCHEMA` validation refuses any `[capabilities]` entry whose `name` is not a member of the catalog (MANIFEST-04, PERMISSION-04 substrate, Pitfall 1 closed-enum guard)
  5. `src/horus_os/plugins/api.py` re-exports the entire v0.5 public surface (`PluginSpec`, `Capability`, `validate_manifest`, `format_validation_error`, the future `PluginContext`/`AdapterContext` shims); `pyproject.toml` `[project.dependencies]` lists exactly `pydantic>=2.7,<3` and `packaging>=24.0` as new base deps (no optional extra); pytest 525+ green, ruff clean (Pitfall 8, REL-10 substrate)
**Plans**: 1 plan

Plans:
- [ ] 41-01-PLAN.md — Plugin manifest schema (PluginSpec + MANIFEST_V1_SCHEMA + capability_catalog), single-public-surface plugins/api.py, v5→v6 additive SQLite migration (3 tables + 2 NULLABLE columns + 1 index) + v0.4 fixture, pyproject.toml base deps (pydantic + packaging)

### Phase 42: Discovery + loading + failure isolation
**Goal**: Wire the schema substrate from Phase 41 into a real `discover_plugins()` pass that walks `importlib.metadata.entry_points(group="horus_os.plugins")` AND the filesystem walk of `~/.horus-os/plugins/`. Ship `plugins/registry.py` (mirror of v0.3 `AdapterRegistry`), `plugins/loader.py` with the CapabilityGuard hook stubbed as pass-through (real enforcement lands Phase 43). Wire the six-phase pipeline into FastAPI lifespan, but with permission gate (Phase C) stubbed to "always grant" and `start()` lifecycle wrapper unbounded — Phase 43 tightens both. Ban `pkg_resources` via ruff custom rule. Land the <100ms cold-start benchmark vs Phase 40 baseline. Surface plugin import failures, manifest validation failures as `status="error"` with structured `error_phase` (discover/validate/load) without crashing host.
**Depends on**: Phase 41 (PluginSpec, MANIFEST_V1_SCHEMA, schema migration)
**Requirements**: DISCOVERY-01, DISCOVERY-02, ISOLATE-04, TEST-18, TEST-19
**Success Criteria** (what must be TRUE):
  1. `discover_plugins(extra_paths=[...])` returns a `list[PluginSpec]` from `importlib.metadata.entry_points(group="horus_os.plugins")` plus a filesystem walk of `~/.horus-os/plugins/<name>/horus-plugin.toml`; filesystem-discovered plugins load via `importlib.util.spec_from_file_location` (no `sys.path` mutation); ruff custom rule fails CI if `pkg_resources` appears anywhere under `src/horus_os/` (DISCOVERY-01, DISCOVERY-02, Pitfall 3)
  2. **TEST-18 cold-start benchmark:** full `discover_plugins()` + validate + load pass with zero installed plugins completes in <100ms wall clock on the Ubuntu CI runner under Python 3.11 + 3.12; CI fails the build on regression vs Phase 40's `v0_4_baseline.json` cold-start number (TEST-18, Pitfall 3)
  3. **TEST-19 broken-plugin fixtures:** synthetic plugins with (a) invalid TOML (parse failure), (b) schema-failing manifest (missing `manifest_version`), (c) import-raising module (`raise RuntimeError` at module top-level), (d) duplicate tool name colliding with a built-in — each appears in `/api/plugins` with `status="error"` and structured `error_phase` (`discover`/`validate`/`load`); FastAPI lifespan completes; built-in tools and adapters keep working byte-identically (TEST-19, ISOLATE-04, Pitfall 6 discover+load half)
  4. Per-plugin error surfacing rides on `ObservationBus.publish` exception-swallow (`observability/bus.py:174-181`); a plugin tool that raises mid-invocation lands in `tool_invocations` with `status="error"`, `plugin_name="<plugin>"`, but does not crash the agent loop or other tools; `PluginHealthSubscriber` increments per-plugin `error_count` and surfaces it via `/api/plugins/{name}.health.error_rate_1h` (ISOLATE-04)
  5. `app.state.plugin_registry` exists after lifespan startup; `PluginRegistry.register(name, spec=spec)` is idempotent; pre-v0.5 surfaces (`/api/adapters`, `/api/observability/*`, `/api/agents`, SSE chat, trace explorer) keep working byte-identically; v0.4 fixture upgrades through Phase 41's migration still pass (carried-forward regression guard)
**Plans**: TBD

Plans:
- [ ] 42-01: discovery + loader (guard stubbed) + registry + cold-start benchmark + broken-plugin fixtures + pkg_resources lint ban

### Phase 43: Permission model + bounded lifecycle
**Goal**: Turn Phase 42's stubbed pass-through guards into real default-deny enforcement. Ship `plugins/permissions.py` with `PermissionGate` + `CapabilityGuard`; the four helper shims (`ctx.filesystem`, `ctx.secrets`, `ctx.net`, `ctx.process`) that raise `PermissionDenied` when the grant row is missing; per-version grants keyed on `(plugin_name, plugin_version, capability)` AND tied to `manifest_hash = sha256(capabilities_set)`. Manifest-hash diff on upgrade flips previously-granted rows to `state="pending"` and triggers re-prompt. Wrap plugin `start()` and `stop()` in `asyncio.wait_for(..., timeout=2.0)` matching the v0.4 Phase 38 OtelAdapter `force_flush(timeout_millis=2000)` precedent. Add `--disable-all-plugins` CLI escape hatch + per-plugin `plugins.enabled` column gate at discovery time. ISOLATE-01's lifespan-continues guarantee fully cemented here (status surfacing + bounded lifecycle).
**Depends on**: Phase 42 (loader + registry shipped with stubbed guards)
**Requirements**: PERMISSION-01, PERMISSION-02, PERMISSION-03, PERMISSION-04, ISOLATE-01, ISOLATE-02, ISOLATE-03
**Success Criteria** (what must be TRUE):
  1. `DEFAULT_GRANT_POLICY = "deny"` is a module-level constant in `plugins/permissions.py`; helper shims (`ctx.filesystem.read`, `ctx.filesystem.write`, `ctx.secrets.read`, `ctx.net.outbound`) raise `PermissionDenied` if the corresponding grant row is missing OR in `state="pending"` OR `state="revoked"`; a fixture plugin with no granted capabilities cannot read a file via `ctx.filesystem` (PERMISSION-01, PERMISSION-04, Pitfall 1)
  2. Grants persist in `plugin_capabilities` keyed on `(plugin_name, plugin_version, capability)` UNIQUE; `manifest_hash` column stored alongside; on plugin upgrade where `sha256(new_capabilities_set) != old.manifest_hash`, the loader flips previously-granted rows to `state="pending"` and the dashboard re-prompts before next run; upgrade-with-shrunk-capabilities path auto-grants the subset (PERMISSION-02, Pitfall 5)
  3. Grants revocable via `horus-os plugins revoke <name> <capability>` AND via `DELETE /api/plugins/{name}/grant/{capability}`; revocation flips `state="revoked"` + `revoked_at=<ts>`; takes effect on next plugin run; no in-flight cancellation required for v0.5 (PERMISSION-03)
  4. **Bounded lifecycle:** plugin `start(ctx)` and `stop()` wrapped in `asyncio.wait_for(start(ctx), timeout=2.0)` and `asyncio.wait_for(stop(), timeout=2.0)` respectively (literal `timeout=2.0`, matching v0.4 Phase 38 `force_flush(timeout_millis=2000)` shape); timeout or exception → `plugin_status.status="error"`, `error_phase="start"` or `"stop"`, host lifespan continues; a fixture plugin whose `start()` sleeps 30s flips to error within 3 seconds wall clock (ISOLATE-02, Pitfall 6)
  5. ISOLATE-01 cemented: import failure, manifest validation failure, permission denied, `start()` exception/timeout NEVER crash horus-os; `plugin_status` table carries `status` in `{"loaded", "pending", "error", "disabled"}` and structured `error_phase` in `{"discover", "validate", "permission", "load", "start", "stop", NULL}`; `plugins.enabled=0` skips discovery cleanly (no half-loaded state); `horus-os --disable-all-plugins` boot flag loads with empty plugin list (ISOLATE-01, ISOLATE-03)
**Plans**: TBD

Plans:
- [ ] 43-01: PermissionGate + CapabilityGuard + helper shims + per-version+hash grants + bounded asyncio.wait_for(timeout=2.0) + --disable-all-plugins flag + ISOLATE-01 status surfacing

### Phase 44: Installer flow (two-phase install + upgrade diff)
**Goal**: Ship `horus-os plugins {install, uninstall, list, info, enable, disable, update, grant, revoke}` as a new argparse subparser. The `install` subcommand is the highest-stakes path: wraps `pip` via `subprocess.check_call([sys.executable, "-m", "pip", ...])` with `--require-virtualenv`; refuses outside a venv (`sys.prefix == sys.base_prefix` check) with `--allow-system-python` escape hatch. Implements the literal three-phase install sequence (phase A `pip download --no-deps` → phase B validate manifest + show capability prompt → phase C `pip install --no-deps --no-build-isolation <wheel>`). Refuses sdists by default (`*.tar.gz`) with `--allow-sdist` escape hatch. Refuses wheels containing `.pth` files in RECORD. Captures `pip freeze` hash pre/post install and refuses any spec that downgrades horus-os runtime deps. `update` runs the upgrade-with-diff that consumes Phase 43's manifest-hash logic. Can run in parallel with Phase 45.
**Depends on**: Phase 43 (PermissionGate + grant table)
**Requirements**: INSTALL-01, INSTALL-02, INSTALL-03, INSTALL-04, INSTALL-05, INSTALL-06
**Success Criteria** (what must be TRUE):
  1. `horus-os plugins install <pip-spec>` wraps `subprocess.check_call([sys.executable, "-m", "pip", "install", "--require-virtualenv", "--no-deps", "--no-build-isolation", "<wheel>"])`; refuses to run when `sys.prefix == sys.base_prefix` with a clean error message and `--allow-system-python` escape hatch; a fixture test outside a venv asserts the refusal (INSTALL-01, Pitfall 4)
  2. **Two-phase install (the literal three-step sequence):** phase A runs `pip download --no-deps <spec>` into a temp directory; phase B parses the downloaded wheel's embedded `horus-plugin.toml`, validates via `MANIFEST_V1_SCHEMA`, and prints the requested capabilities with plain-English descriptions from `capability_catalog.py`, then prompts `Grant all (y) / per-capability (a/b/c/...) / refuse (n)?`; phase C runs `pip install --no-deps --no-build-isolation <local-wheel-path>` ONLY if the user grants; refusal aborts cleanly with no venv mutation (INSTALL-02, INSTALL-05, Pitfalls 4 and 1)
  3. Sdists (`*.tar.gz`) refused by default; `--allow-sdist` flag required to bypass; wheels containing `.pth` files in RECORD also refused (parsed by reading `<wheel>.dist-info/RECORD` and grepping `\.pth\b`); a fixture sdist and a fixture `.pth`-wheel both rejected with structured error messages (INSTALL-03, Pitfall 4)
  4. Pre-install `pip freeze` hash captured; post-install `pip freeze` hash captured; installer refuses any spec that would downgrade `pydantic`, `packaging`, `fastapi`, or any other horus-os runtime dep (check against the resolver's planned changes via `pip install --dry-run --report -` JSON output); on downgrade-attempt detected, install aborts BEFORE phase C runs (INSTALL-04, Pitfall 4)
  5. Subcommand suite complete: `uninstall <name>` runs `pip uninstall -y <pkg>` then `discover_plugins()` refresh; `list` prints discovered plugins with status; `info <name>` prints manifest + grants + health; `enable <name>` / `disable <name>` flip `plugins.enabled`; `update <name>` runs Phase 43's upgrade-with-diff (unchanged auto / reduced auto / expanded re-prompt); `grant <name> --capability <cap>` flips `state="granted"`; `revoke <name> --capability <cap>` flips `state="revoked"` (INSTALL-06, PERMISSION-02 consumer)
**Plans**: TBD

Plans:
- [ ] 44-01: cli/plugins_cmd.py with all subcommands + two-phase install + venv/sdist/.pth/downgrade refusals + upgrade-with-diff

### Phase 45: REST API + `/plugins` dashboard tab + per-plugin observability
**Goal**: Land the read/write API and dashboard surface. Six `/api/plugins` routes (list/get/enable/disable/grant/revoke). `/plugins` dashboard tab (vanilla JS, mirrors v0.3 `/adapters` tab and v0.4 `/observability` tab patterns) with plugin tiles showing version, declared contributions (tools + adapters), capability chips (granted/pending/revoked with revoke buttons), lifecycle status, last error preview, error rate over selected window. Author / homepage / issue_tracker hyperlinks rendered from validated manifest fields only (no inline rendering of arbitrary URLs from plugin code). `/api/observability/plugins` route + dashboard rollup tile on `/observability` ("by plugin" alongside existing "by agent" and "by tool"). OBSERVE-02 per-plugin LLM cost attribution if the column-add is cheap (already in place via Phase 41's `llm_calls.plugin_name` column). Can run in parallel with Phase 44.
**Depends on**: Phase 43 (grant table + status; both run in parallel after Phase 43)
**Requirements**: DASH-5-01, DASH-5-02, DASH-5-03, OBSERVE-02
**Success Criteria** (what must be TRUE):
  1. Six `/api/plugins` routes wired and tested: `GET /api/plugins` (list all with health), `GET /api/plugins/{name}` (full detail), `POST /api/plugins/{name}/enable`, `POST /api/plugins/{name}/disable`, `POST /api/plugins/{name}/grant` (body `{"capability": "filesystem.read"}`), `DELETE /api/plugins/{name}/grant/{capability}`; all return the `PluginRow` shape; enable/disable/grant return `needs_restart=true` (DASH-5-02 consumer)
  2. `/plugins` dashboard tab renders one tile per discovered plugin showing: `name` + `version` + status badge (`loaded`/`pending`/`error`/`disabled`); declared tools and adapters as labeled chips; capability chips (granted=green, pending=yellow, revoked=gray) with revoke buttons; last error preview (first 200 chars) on hover for `status="error"`; error rate + p50/p95 latency over selected window from `PluginHealthSubscriber` rollup (DASH-5-01)
  3. Plugin tile renders hyperlinks from manifest `author`, `homepage`, `issue_tracker` fields ONLY (rendered via `<a href="{validated_url}" rel="noopener noreferrer">` after URL validation); no inline rendering of arbitrary URLs from plugin code, no markdown rendering of plugin-provided text (XSS guard) (DASH-5-03)
  4. `/api/observability/plugins?since=7d|30d` returns per-plugin `error_rate`, `latency_p50_ms`, `latency_p95_ms`, `total_invocations`, `total_cost_usd` from a SQL query joining `tool_invocations` + `llm_calls` on `plugin_name`; pre-v0.5 rows (NULL `plugin_name`) roll up under `"horus-os core"`; `/observability` dashboard gains a "by plugin" tile alongside "by agent" and "by tool" (OBSERVE-02, Pitfall 7)
  5. OBSERVE-02 LLM cost attribution: a plugin tool that triggers an LLM call lands in `llm_calls` with `plugin_name="<plugin>"` set; cost rolls up correctly per plugin; an integration test asserts a fixture plugin call increments only its own row, never another plugin's; v0.4 `/api/observability/*` routes keep working byte-identically (OBSERVE-02, Pitfall 7)
**Plans**: TBD
**UI hint**: yes

Plans:
- [ ] 45-01: /api/plugins routes + /plugins dashboard tab + /api/observability/plugins + dashboard rollup tile

### Phase 46: Test surface (three-tier fixtures + pitfall regression suite)
**Goal**: Land the three-tier test fixture strategy that makes plugin testing tractable without polluting the test-runner venv. Tier 1: in-process unit tests against synthetic `PluginSpec` objects (no entry points, no filesystem). Tier 2: `fake_plugin_entry_points` pytest fixture that monkeypatches `importlib.metadata.entry_points` for a single test. Tier 3: `clean_venv` pytest fixture opt-in via `@pytest.mark.installer_e2e` that spawns a real `venv` and runs `pip install` against the test plugin (slow, real E2E, marked off-by-default). Ship `tests/test_plugin_pitfalls/` with one regression test per pitfall in `.planning/research/PITFALLS.md` — minimum 12 tests, names map 1:1 to pitfall numbers (e.g. `test_pitfall_1_default_allow_normalizes_compromise.py`).
**Depends on**: Phase 45 (full v0.5 runtime surface available for tier 3 e2e)
**Requirements**: TEST-16, TEST-17
**Success Criteria** (what must be TRUE):
  1. Tier 1 fixture: synthetic `PluginSpec` objects constructable via a `make_plugin_spec(**overrides)` factory; one example unit test in `tests/plugins/test_registry.py` uses ONLY this tier and runs in <50ms; ruff clean, pytest clean (TEST-16 tier 1)
  2. Tier 2 fixture: `fake_plugin_entry_points` pytest fixture that monkeypatches `importlib.metadata.entry_points(group="horus_os.plugins")` to return a configurable list; one example test in `tests/plugins/test_discovery.py` uses ONLY this tier, no real entry points touched in the runner venv; tier 2 tests run in <500ms total (TEST-16 tier 2)
  3. Tier 3 fixture: `clean_venv` pytest fixture opt-in via `@pytest.mark.installer_e2e`; creates a fresh `venv` via `python -m venv`, runs `pip install -e .` for horus-os plus the test plugin path, asserts plugin appears in `/api/plugins`; marked off in the default `pytest` invocation; the default `pytest -m "not installer_e2e"` invocation never installs anything into the runner venv (TEST-16 tier 3, Pitfall 11)
  4. `tests/test_plugin_pitfalls/` directory contains at minimum 12 regression test files, one per pitfall in `.planning/research/PITFALLS.md`; filenames match `test_pitfall_<N>_<slug>.py` 1:1 to pitfall numbers (`test_pitfall_1_default_allow.py`, `test_pitfall_2_manifest_schema_drift.py`, ... `test_pitfall_12_docs_drift.py`); each test cites the pitfall number in its docstring (TEST-17)
  5. Default pytest run (excluding tier 3) maintains or exceeds the v0.4 baseline test count (520+) and stays under 90s wall clock on the Ubuntu CI runner; ruff clean across the new `tests/test_plugin_pitfalls/` directory
**Plans**: TBD

Plans:
- [ ] 46-01: three-tier fixtures + 12+ pitfall regression tests + @pytest.mark.installer_e2e isolation

### Phase 47: Documentation refresh (docs trio)
**Goal**: Ship the three documentation files that v0.5 needs for plugin authors and existing v0.4 users. `docs/PLUGINS.md` is the plugin-author guide: manifest schema, capability catalog, lifecycle hooks, testing harness, walkthrough of each reference-plugin scenario in order. `docs/PLUGIN-SECURITY.md` carries an explicit "Threat model" section with the literal sentence `plugins execute in the horus-os Python process` and enumerates the capability-grant trust contract; linked from the install-prompt screen. `docs/MIGRATION-v0.4-to-v0.5.md` documents the v5→v6 schema migration plus the two new direct deps (`pydantic>=2.7,<3`, `packaging>=24.0`). Embedded `horus-plugin.toml` snippet in `docs/PLUGINS.md` diffs against the reference plugin in CI (docs-drift trip wire for Phase 49's gate).
**Depends on**: Phase 46 (full test surface available so docs examples can reference real test patterns)
**Requirements**: REFERENCE-02, REL-12
**Success Criteria** (what must be TRUE):
  1. `docs/PLUGINS.md` exists and covers in order: `horus-plugin.toml` schema with annotated example, capability catalog (`filesystem.read`, `filesystem.write`, `net.outbound`, `secrets.read`) with plain-English descriptions, lifecycle hooks (`start(ctx)` / `stop()` contract + bounded `asyncio.wait_for(timeout=2.0)`), testing harness using the three-tier fixtures from Phase 46, walkthrough of each of the four reference-plugin scenarios from Phase 48 (REFERENCE-02)
  2. The `horus-plugin.toml` snippet embedded in `docs/PLUGINS.md` is byte-identical to `examples/horus-os-example-plugin/horus-plugin.toml`; a CI docs-drift check (extended in Phase 49's release gate) fails the build on divergence (REFERENCE-02, Pitfall 12)
  3. `docs/PLUGIN-SECURITY.md` exists with a section titled "Threat model" containing the literal sentence `plugins execute in the horus-os Python process` and enumerating the capability-grant trust contract; the install-prompt screen (from Phase 44) links to this doc by URL; the doc is short enough (<400 lines) to read in one sitting (REL-12, Pitfall 1)
  4. `docs/MIGRATION-v0.4-to-v0.5.md` documents: the v5→v6 schema migration (three new tables + two NULLABLE columns + one index, all additive); the two new base direct deps (`pydantic>=2.7,<3`, `packaging>=24.0`) and why they were added; how to roll back (`horus-os --disable-all-plugins` boot flag); the breaking-change-free upgrade path for existing v0.4 users (REL-12 consumer, MIG-05 consumer)
  5. README.md updated with v0.5 capability call-outs and a link to `docs/PLUGINS.md`; CHANGELOG `[0.5.0]` section drafted (final tag lands in Phase 50)
**Plans**: TBD

Plans:
- [ ] 47-01: docs/PLUGINS.md + docs/PLUGIN-SECURITY.md (Threat model) + docs/MIGRATION-v0.4-to-v0.5.md + README + CHANGELOG draft

### Phase 48: Reference plugin (`horus-os-example-plugin`)
**Goal**: Ship `examples/horus-os-example-plugin/` as a separate installable package living in the same monorepo with its own `pyproject.toml`, `horus-plugin.toml`, and `src/` tree. Demonstrates four scenarios in `src/horus_os_example_plugin/`: (a) simple tool that requires a capability and uses `ctx.filesystem`, (b) config-reading tool that respects `secrets.read`, (c) lifecycle adapter with `start()` + `stop()` that respects the bounded `asyncio.wait_for(timeout=2.0)` contract, (d) plugin registering both a tool AND an adapter in the same package. Enforces the public-API contract via a ruff custom rule that fails CI on any `from horus_os` import outside `horus_os.plugins.api` — this is the byte-level enforcement of Pitfall 8.
**Depends on**: Phase 47 (docs reference this plugin in the walkthrough)
**Requirements**: REFERENCE-01, TEST-21
**Success Criteria** (what must be TRUE):
  1. `examples/horus-os-example-plugin/` exists as a self-contained package: `pyproject.toml` declaring `[project.entry-points."horus_os.plugins"]`, `horus-plugin.toml` with `manifest_version=1` plus all required fields, `README.md`, `src/horus_os_example_plugin/{__init__,tools,adapter}.py`; `pip install -e ./examples/horus-os-example-plugin` from the host repo succeeds in a clean venv (REFERENCE-01)
  2. Four reference scenarios demonstrated: (a) `tools.py::echo_text_tool` requires `filesystem.read` and reads a file via `ctx.filesystem.read(path)`; (b) `tools.py::lookup_secret_tool` requires `secrets.read` and reads via `ctx.secrets.read(key)`; (c) `adapter.py::ExampleAdapter` implements `start(ctx)` + `stop()` and respects the bounded lifecycle (sleeps no more than 1 second in `start`); (d) the single package registers BOTH `tools.py` tools AND `adapter.py::ExampleAdapter` via its manifest (REFERENCE-01)
  3. **TEST-21 single-public-API-surface lint:** a ruff custom rule fails CI on any `from horus_os ...` or `import horus_os...` line in the reference plugin source EXCEPT `from horus_os.plugins.api import ...`; the rule is documented in `docs/PLUGINS.md` and tested with a synthetic bad-import fixture that MUST fail CI (TEST-21, Pitfall 8)
  4. CI runs `pip install -e ./examples/horus-os-example-plugin` in a clean venv, boots horus-os, calls `GET /api/plugins`, asserts the example plugin appears with `status="pending"` (no grants yet); after `horus-os plugins grant horus-os-example-plugin --all`, restart asserts `status="loaded"`; tools and adapter both registered (REFERENCE-01)
  5. CHANGELOG `[0.5.0]` section updated with a link to the example plugin and a callout that the reference is the contract for third-party authors
**Plans**: TBD

Plans:
- [ ] 48-01: examples/horus-os-example-plugin/ package + four scenarios + ruff single-API-surface custom rule (TEST-21) + CI install-smoke

### Phase 49: Three-OS install gate + release-gate extension
**Goal**: The v0.5 release-quality gate. Three-OS install-smoke job (macOS + Ubuntu + Windows × Python 3.11 + 3.12) installs the reference plugin via `pip install -e ./examples/horus-os-example-plugin` and asserts the plugin appears in `/api/plugins` with `status="running"` after grant. Extends `scripts/release_gate.py` (shipped in v0.4 Phase 39) with four new v0.5 checks: (a) docs-drift check between `MANIFEST_V1_SCHEMA` runtime constant and `docs/manifest-v1.schema.json`; (b) plugin install-smoke on each OS from TEST-20; (c) reference plugin manifest validates against the runtime schema; (d) v0.4 fixture round-trips the v5→v6 migration. Three-OS CI green on the full test suite plus the new v0.5 tests including TEST-18 cold-start benchmark + TEST-19 broken-plugin fixtures + TEST-20 install-smoke.
**Depends on**: Phase 48 (reference plugin installable for the smoke test)
**Requirements**: TEST-20, REL-11
**Success Criteria** (what must be TRUE):
  1. **TEST-20 three-OS plugin install-smoke:** parallel CI jobs on macOS + Ubuntu + Windows × Python 3.11 + 3.12 (six total combinations) each: (a) run `pip install -e ./examples/horus-os-example-plugin` in the host venv, (b) boot horus-os via `horus-os serve` in the background, (c) `curl -s http://localhost:8000/api/plugins | jq` asserts `horus-os-example-plugin` appears with `status="pending"`, (d) `horus-os plugins grant horus-os-example-plugin --all && horus-os serve restart`, then re-curl asserts `status="running"`; all six combinations green (TEST-20)
  2. `scripts/release_gate.py` carries the four new v0.5 checks alongside the existing v0.4 pricing-freshness + two-variant install-smoke checks: (a) `MANIFEST_V1_SCHEMA.model_json_schema()` diffs against committed `docs/manifest-v1.schema.json`; (b) the TEST-20 install-smoke matrix is green; (c) parsing `examples/horus-os-example-plugin/horus-plugin.toml` via the runtime `validate_manifest()` succeeds with zero errors; (d) `tests/fixtures/v0_4_database.sqlite3` upgrades cleanly through Phase 41's v5→v6 migration with all three new tables and both new columns present (REL-11)
  3. Release workflow refuses to allow the v0.5.0 tag when ANY of the eight gate checks fails (four new + four carried from v0.4); a fixture test asserts each of the four new checks individually fails the gate when its precondition is broken (e.g. mutating the docs schema file diverges from the runtime constant) (REL-11)
  4. Three-OS CI matrix (macOS + Ubuntu + Windows × Python 3.11 + 3.12) green on the full test suite including: v0.4 capture-overhead benchmark, v0.4 OTel three non-negotiable tests (PII-not-leaked, bounded-shutdown, two-variant install-smoke), v0.5 cold-start <100ms benchmark (TEST-18), v0.5 broken-plugin fixtures (TEST-19), v0.5 plugin install-smoke (TEST-20), the 12+ pitfall regression tests from Phase 46
  5. `docs/manifest-v1.schema.json` committed alongside `MANIFEST_V1_SCHEMA` runtime constant; both stay in sync via the docs-drift gate; any future schema change must update both atomically or the gate refuses the tag
**Plans**: TBD

Plans:
- [ ] 49-01: TEST-20 three-OS plugin install-smoke + scripts/release_gate.py extension (4 new checks) + docs/manifest-v1.schema.json + v0.4-fixture v5→v6 round-trip test

### Phase 50: v0.5.0 release
**Goal**: Tag `v0.5.0`, finalize CHANGELOG `[0.5.0]` section, publish GitHub Release with migration-notes link. Version bumped to `0.5.0` in `pyproject.toml` and `src/horus_os/__init__.py`. Release-gate green on all 8 checks (4 new v0.5 + 4 carried from v0.4). STOP-BEFORE-TAG block: maintainer runs `git tag` + `gh release create` after final approval, mirroring v0.4 Phase 39's release pattern.
**Depends on**: Phase 49 (release gate green)
**Requirements**: REL-10
**Success Criteria** (what must be TRUE):
  1. `v0.5.0` tag exists on origin; CHANGELOG has a complete `[0.5.0]` section describing the plugin manifest contract, two-phase installer, default-deny capability grants with manifest-hash re-prompt, bounded lifecycle, `/plugins` dashboard tab, per-plugin observability, reference plugin, v5→v6 migration, and the two new direct deps (`pydantic>=2.7,<3`, `packaging>=24.0`) (REL-10)
  2. GitHub Release at the `v0.5.0` tag is published with the CHANGELOG body and a link to `docs/MIGRATION-v0.4-to-v0.5.md`; release notes call out the deliberate addition of two new base runtime deps and the trust model summary (`plugins execute in the horus-os Python process`, default-deny grants, manifest-hash drives re-prompt) (REL-10)
  3. Version bumped to `0.5.0` in `pyproject.toml` and `src/horus_os/__init__.py`; `horus-os --version` returns `0.5.0`; `pip show horus-os` returns version `0.5.0` after install
  4. All 8 release-gate checks green at tag time: (v0.4 carried) pricing freshness within 14 days, two-variant `[dev]`/`[dev,otel]` install-smoke, full 3-OS test suite green, pricing.json metadata schema; (v0.5 new) docs-drift check, plugin install-smoke 3-OS matrix, reference plugin manifest validates, v0.4 fixture v5→v6 round-trip
**Plans**: TBD

Plans:
- [ ] 50-01: Version bump to 0.5.0 + CHANGELOG promotion + STOP-BEFORE-TAG block (maintainer runs git tag + gh release after approval)

## Progress

**Execution Order (v0.3):** 22 → (23 ∥ 24 ∥ 25 ∥ 26) → 27 → 28 → 29 → 30 → 31
**Execution Order (v0.4):** 32 → 33 → 34 → 35 → (36 ∥ 37) → 38 → 39
**Execution Order (v0.5):** 40 → 41 → 42 → 43 → (44 ∥ 45) → 46 → 47 → 48 → 49 → 50

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
| 32. Schema migration, persistence skeleton, v0.3 baseline | v0.4 | 1/1 | Complete   | 2026-05-26 |
| 33. Capture at the runner + SSE branch | v0.4 | 1/1 | Complete   | 2026-05-26 |
| 34. Pricing table and cost annotation | v0.4 | 1/1 | Complete   | 2026-05-26 |
| 35. Query module and read APIs | v0.4 | 1/1 | Complete   | 2026-05-26 |
| 36. Observability dashboard tab | v0.4 | 1/1 | Complete   | 2026-05-26 |
| 37. `horus-os usage` CLI subcommand | v0.4 | 1/1 | Complete   | 2026-05-26 |
| 38. OpenTelemetry adapter | v0.4 | 1/1 | Complete   | 2026-05-26 |
| 39. Three-OS gate, release, migration doc | v0.4 | 1/1 | Complete   | 2026-05-26 |
| 40. v0.5 baseline artifact | v0.5 | 1/1 | Complete   | 2026-05-26 |
| 41. Manifest schema, public API, persistence migration | v0.5 | 0/1 | Pending | — |
| 42. Discovery + loading + failure isolation | v0.5 | 0/1 | Pending | — |
| 43. Permission model + bounded lifecycle | v0.5 | 0/1 | Pending | — |
| 44. Installer flow (two-phase install + upgrade diff) | v0.5 | 0/1 | Pending | — |
| 45. REST API + `/plugins` dashboard tab + per-plugin observability | v0.5 | 0/1 | Pending | — |
| 46. Test surface (three-tier fixtures + pitfall regression suite) | v0.5 | 0/1 | Pending | — |
| 47. Documentation refresh (docs trio) | v0.5 | 0/1 | Pending | — |
| 48. Reference plugin (`horus-os-example-plugin`) | v0.5 | 0/1 | Pending | — |
| 49. Three-OS install gate + release-gate extension | v0.5 | 0/1 | Pending | — |
| 50. v0.5.0 release | v0.5 | 0/1 | Pending | — |
