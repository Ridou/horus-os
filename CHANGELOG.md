# Changelog

All notable changes to horus-os are documented here. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **MCP client (opt-in).** A new optional `[mcp]` extra (`mcp>=1.27`, the
  official Anthropic Model Context Protocol SDK) lets horus-os connect to
  explicitly-allowlisted MCP servers over stdio, SSE, and streamable-http
  transports. Each discovered tool registers into the shared `ToolRegistry`
  under a `mcp:{server}:{tool}` namespace and is traced through the existing
  `tool_invocations` path exactly like a builtin, with no schema change.
  - **Opt-in trust gate.** Servers activate ONLY through `<data_dir>/mcp.toml`;
    an absent or empty file registers zero MCP tools and triggers no network
    probe. Adding a `[[mcp.servers]]` block is the single activation surface.
  - **Namespacing with builtin collision refusal.** The registry refuses any
    MCP tool name that would shadow a builtin (raising `CollisionError`, never
    swallowing it) and surfaces the refusal without aborting other servers.
  - **Tool description sanitization.** Unicode tag characters
    (U+E0000-U+E007F) and zero-width / format control characters are stripped
    and descriptions are length-capped before reaching the model, defending
    against tool poisoning.
  - **Clean cross-OS subprocess teardown.** stdio servers get an explicit,
    idempotent `terminate` / `wait` / `kill` teardown independent of the SDK
    lifespan, proven to leave no zombie process on macOS, Ubuntu, and Windows.
  - **Registered as a first-party LifecycleAdapter** in the FastAPI lifespan
    (alongside the Discord and Email adapters) and reported by
    `horus-os doctor --mcp`. See `docs/MCP.md` for the schema, the three
    transports, and the Threat model.

## [0.7.0] - 2026-06-02

The Command Center milestone. v0.7.0 turns horus-os from a single-page
vanilla-JS dashboard into a polished Next.js command center with a
design system, a Setup-and-Verify integrations surface, an opt-in
Discord control bot, an opt-in Supabase sync loop, a cron scheduler
with an always-on service, and an opt-in Vercel deploy path. v0.6
(Contribution Gate) was never tagged, so 0.7.0 follows 0.5.0 directly
in the tag history.

This release adds no removals and no deprecations. Every v0.5 surface
keeps working byte-identical, `pip install horus-os` (no extras) still
starts and runs the local runtime fully, and the SQLite schema upgrade
is additive and idempotent.

See `docs/MIGRATION-v0.5-to-v0.7.md` for upgrade notes from v0.5.

### Added

- **Design system and layout shell (Phase 60).** Tailwind v4 token
  source in `globals.css`, Radix-backed `Modal` and `Stepper`
  primitives, a four-state pulsing `StatusDot`, and an `AppShell`
  with a locked ten-item sidebar (Home, Team, Memory, Tasks, Activity,
  Traces, Costs, Integrations, Settings, About). The CI em-dash and
  reserved-private-name guards land here, scoped to the changed-file
  diff.
- **Integrations surface and read-only API (Phase 61).** A ten-card
  Integrations page with per-integration walkthroughs (Modal plus
  Stepper, read-only in demo mode), a readiness summary, and a
  read-only `GET /api/integrations` route sourced from an
  `INTEGRATION_REGISTRY` that never echoes secret values. The
  get-started flow gains a step that links straight to the surface.
- **Key-write endpoint and verification engine (Phase 62).** A
  loopback-guarded `POST /api/integrations/{name}/keys` plus a
  `POST /verify` probe that never echoes the key value, refuses in
  demo mode (403), writes `.env` with `chmod 600`, and invalidates a
  saved verification when the key hash changes. The credential
  management UI lands on `/settings` with masked display and a
  restart banner.
- **Tier-1 dashboard pages, starter team, and seed content
  (Phase 63).** A `/tasks` page and a full-page `/team/[slug]` agent
  detail route, `GET /api/tasks` plus task and trace delete routes, a
  case-insensitive team lookup, an example-data banner and a guided
  tour, and idempotent seed content (a starter team and demo tasks).
- **Discord control bot (Phase 64).** The `[discord]` adapter becomes
  a control bot: create-only, non-destructive channel bootstrap,
  deny-by-default admin gating, slash commands, and a `#horus`
  thread-dispatch flow. Three required env vars
  (`HORUS_OS_DISCORD_TOKEN`, `HORUS_OS_DISCORD_GUILD_ID`,
  `HORUS_OS_DISCORD_ADMIN_ROLE_ID`) and a minimal-permission invite.
- **Supabase sync loop and schema migrations (Phase 65).** An opt-in
  `[supabase]` `SupabaseAdapter` that pushes traces, agent profiles,
  and tasks through a background sync loop, with cursors stored
  locally so the runtime survives Supabase downtime. The service key
  never reaches a browser-accessible route or a `NEXT_PUBLIC_*` value,
  every synced table ships Row Level Security, and a
  `horus-os doctor --supabase` command reports per-table RLS state
  without printing the key. An anon-key read path lets the dashboard
  read from Supabase when configured and fall back to the local API
  otherwise.
- **Cron scheduler and always-on service (Phase 66).** A
  `SchedulerAdapter` (core-on-by-default, opt-out via
  `HORUS_OS_DISABLE_SCHEDULER`) that fires agent profiles on cron
  schedules with a double-fire guard and an overlap guard, a
  `horus-os schedule` subcommand family, a cross-platform
  `horus-os service` install path (systemd, launchd, NSSM) with
  `horus-os doctor --service`, and a `docs/REMOTE.md` remote-access
  guide.
- **Vercel deploy path, GitHub tool, and configurable API base
  (Phase 67).** A `NEXT_PUBLIC_API_BASE` abstraction so the static
  export can point at a remote API origin, an opt-in `[vercel]` deploy
  path, and an opt-in read-only `github_read` agent tool behind the
  `[github]` extra that never echoes `GITHUB_TOKEN`.
- **New optional extras.** Four opt-in integration extras join the
  package: `[discord]`, `[supabase]`, `[vercel]`, and `[github]`. Each
  is installed explicitly (for example
  `pip install 'horus-os[supabase]'`) and all four are EXCLUDED from
  `[all]`, so neither `pip install horus-os` nor
  `pip install 'horus-os[all]'` pulls any of them. An install-smoke
  test pins this exclusion invariant.

### Changed

- **SQLite schema bump (v6 to v12, additive and idempotent).** v0.5
  ships schema version 6, so a v0.5 database advances to v12 on first
  v0.7 startup. The v0.7 phases add five tables across the milestone:
  `integration_verification_state` (Phase 62), `tasks` (Phase 63),
  `discord_feedback` (Phase 64), `sync_cursors` (Phase 65), and
  `schedules` (Phase 66), plus three nullable `agent_profiles` columns
  for the starter team. Every migration is additive and idempotent,
  runs automatically on first startup, and leaves pre-v0.7 rows
  byte-identical. The schema advanced to v12; query the
  `schema_version` table to confirm, as the migration note documents.
- **New environment variables.** The integration suite introduces
  `HORUS_OS_DISCORD_TOKEN`, `HORUS_OS_DISCORD_GUILD_ID`,
  `HORUS_OS_DISCORD_ADMIN_ROLE_ID`, `SUPABASE_URL`,
  `SUPABASE_SERVICE_KEY`, `NEXT_PUBLIC_SUPABASE_URL`,
  `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `HORUS_OS_VERCEL_TOKEN`,
  `GITHUB_TOKEN`, `HORUS_OS_DISABLE_SCHEDULER`, `HORUS_TZ`, and
  `NEXT_PUBLIC_API_BASE`. All are optional; the local runtime starts
  with none of them set.

## [0.5.0] - 2026-05-27

Fifth alpha. Adds a third-party plugin system on top of the v0.4
observability substrate. Plugins are Python packages that ship a
`horus-plugin.toml` manifest, contribute tools and/or adapters, and
run with default-deny capability grants. A new `/plugins` dashboard
tab visualizes the state; a `horus-os plugins` CLI subcommand family
manages installs; per-plugin observability attribution lands on
every LLM call and every tool invocation.

See `docs/MIGRATION-v0.4-to-v0.5.md` for upgrade notes from v0.4.

### Added

- **Plugin manifest contract.** `MANIFEST_V1_SCHEMA` in
  `horus_os.plugins.manifest` (pydantic v2). Required fields:
  `manifest_version`, `name`, `version`, `description`, `author`,
  `license`, `horus_os_compat`. Optional: `contributions.tools`,
  `contributions.adapters`, `capabilities`, `homepage`,
  `issue_tracker`. Unknown top-level keys emit `UserWarning`
  (forward-compat: a v2-authored manifest still loads under v0.5
  with warnings). `validate_manifest(toml_bytes)` is the single
  entry point; `format_validation_error(exc)` turns pydantic
  failures into plain-English multi-line error strings.
- **Two-phase installer.** `horus-os plugins install <spec>` runs
  `pip download --no-deps` into a tmpdir, refuses sdists by default
  (`--allow-sdist` to override), refuses any wheel that ships a
  `.pth` file in RECORD (Checkmarx command-jacking defense), refuses
  any wheel whose `Requires-Dist` would downgrade `pydantic` or
  `packaging`, prompts for capability grants, then runs
  `pip install --no-deps --no-build-isolation` against the wheel.
  Any failure post-Phase-D rolls back via `pip uninstall -y` plus
  a `DELETE FROM plugins`. The single `subprocess.run` chokepoint
  inside `run_pip` is the only audit point - a grep for the literal
  invocation token returns 1.
- **Default-deny capability grants.** Four-capability v1 catalog:
  `filesystem.read`, `filesystem.write`, `net.outbound`,
  `secrets.read`. The `Capability` StrEnum and `DESCRIPTIONS`
  mapping live in `horus_os.plugins.capability_catalog`. Grants
  pinned to `(plugin_name, plugin_version, manifest_hash)` where
  `manifest_hash = sha256(sorted(set(capabilities)))`. Every grant
  transition (issue, revoke, expire, re-grant under a new version)
  appends one row to `plugin_capability_grants_log`. The audit log
  survives plugin uninstall. The `PermissionService` is the only
  writer; `CapabilityGuard` shims (`ctx.filesystem`, `ctx.secrets`,
  `ctx.net`) enforce at every call site.
- **Bounded lifecycle.** `asyncio.wait_for(start, timeout=2.0)`
  wraps every plugin adapter's `start(ctx)` hook (ISOLATE-02). A
  hung `start` becomes a load-time `PluginLoadError`. Same bound
  on `stop()` at shutdown. Mirrors the v0.4 OtelAdapter shape.
- **`/plugins` dashboard tab.** Sixth nav tab. One row per
  discovered plugin: manifest metadata, granted-capability pills,
  status (pending / running / error / disabled), error message,
  per-plugin Enable / Disable / Revoke buttons. Polls
  `GET /api/plugins` every five seconds.
- **Per-plugin observability.** Two new NULLABLE columns
  (`tool_invocations.plugin_name`, `llm_calls.plugin_name`). The
  runner publishes these on every event. Pre-v0.5 rows stay NULL;
  the dashboard renders these as "horus-os core" attribution.
- **`horus-os plugins` CLI surface.** Nine subcommands:
  `install`, `uninstall`, `list`, `info`, `enable`, `disable`,
  `update`, `grant`, `revoke`. `update` runs the upgrade-diff
  classifier (unchanged / reduced / expanded) and re-prompts only
  for new caps on the expanded path.
- **`--disable-all-plugins` boot flag.** Escape hatch wired in
  `src/horus_os/__main__.py` and consumed in
  `src/horus_os/cli/serve_cmd.py`. Skips entry-point and
  local-directory discovery entirely; the server starts with only
  v0.4 first-party adapters. Settable via `HORUS_OS_DISABLE_ALL_PLUGINS=1`.
- **Three-tier test fixtures.** Tier 1 `make_synthetic_plugin`
  (in-process unit tests, no pip), tier 2
  `fake_plugin_entry_points` (discovery-walk monkeypatch), tier 3
  `clean_venv` (throwaway venv real-pip tests, gated by
  `--run-installer-e2e`). The Phase 49 install-smoke matrix is the
  primary tier-3 consumer.
- **12-pitfall regression suite.** `tests/test_plugin_pitfalls/`
  maps 1:1 to `PITFALLS.md`. Each pitfall has one or more tests
  that pin the prevention pattern.
- **Reference plugin (`examples/horus-os-example-plugin/`).**
  Self-contained installable Python package demonstrating the v0.5
  plugin contract across four scenarios in one distribution:
  capability-gated filesystem tool (`echo_text_tool` via
  `@require_capability(FILESYSTEM_READ)`), capability-gated secret
  tool (`lookup_secret_tool` via `@require_capability(SECRETS_READ)`,
  returns `None` on missing key), bounded-lifecycle adapter
  (`ExampleAdapter` with `asyncio.create_task(asyncio.sleep(0))` +
  cancel/await - well inside Phase 43's
  `asyncio.wait_for(timeout=2.0)` ceiling), and a single
  `horus-plugin.toml` registering both tools AND the adapter through
  `[[contributions.*]]` arrays. Shipped as the canonical starting
  template for third-party plugin authors. The TEST-21 two-layer
  guard (ruff `flake8-tidy-imports.banned-api` + pytest source-tree
  scan at `tests/plugins/test_reference_plugin_public_api_only.py`)
  pins the plugin's public API surface to `horus_os.plugins.api` and
  fires on any non-public `horus_os.*` import inside the reference
  plugin's `src/` tree.
- **Three new docs files.** `docs/PLUGINS.md` (plugin author
  guide), `docs/PLUGIN-SECURITY.md` (threat model + trust contract
  + out-of-scope defenses + recommended user practices), and
  `docs/MIGRATION-v0.4-to-v0.5.md` (mirrors the v0.3→v0.4 shape).
- **`docs/manifest-v1.schema.json`.** JSON-Schema mirror of
  `MANIFEST_V1_SCHEMA.model_json_schema()`. Phase 49 release-gate
  diff target. Regenerated via
  `python scripts/build_manifest_schema.py`.

### Changed

- **Base `[project.dependencies]` gained two new direct deps.**
  `pydantic>=2.7,<3` powers manifest validation and the JSON-Schema
  export. `packaging>=24.0` powers PEP 440 `horus_os_compat` parsing
  via `SpecifierSet` and `Requires-Dist` parsing via
  `Requirement`. Both are pure-Python wheels with universal install
  surface - no 3-OS install-smoke impact.

### Migration

- **v5 → v6 schema migration.** Additive only: three new tables
  (`plugins`, `plugin_capabilities`, `plugin_status`) + two new
  NULLABLE columns (`tool_invocations.plugin_name`,
  `llm_calls.plugin_name`) + one new index on `(plugin_name,
  plugin_version)`. v0.4 databases continue to read byte-identical.
  Pre-v0.5 rows have `plugin_name = NULL`, surfaced as
  "horus-os core" attribution. Roll back via the
  `--disable-all-plugins` boot flag; no downgrade path. See
  `docs/MIGRATION-v0.4-to-v0.5.md`.

## [0.4.0] - 2026-05-26

Fourth alpha. Turns horus-os from "agents run" into "agents run and
you know what they cost, what they took, and what broke."
Local-first cost, latency, and tool-reliability instrumentation
against a SQLite source of truth. New `/observability` dashboard
tab, `horus-os usage` CLI subcommand, opt-in OpenTelemetry exporter
behind a `[otel]` extra. Fixes two confirmed v0.3 cost-correctness
bugs along the way.

See `docs/MIGRATION-v0.3-to-v0.4.md` for upgrade notes from v0.3.

### Added

- **Observability capture pipeline.** New `horus_os.observability`
  package: `ObservationBus` singleton (`get_observation_bus`,
  `reset_observation_bus_for_tests`), `SQLitePersister` (one row
  per LLM call into `llm_calls`, one row per tool call into
  `tool_invocations`), `LLMCallEvent` and `ToolInvocationEvent`
  payloads. SQLite pragmas pinned to `synchronous=NORMAL` plus
  WAL on every connection (Pitfall 8 prevention).
- **Runner and SSE-branch capture sites.** Phase 33 wired
  `agent.run_agent_loop`, `tools/loop.py:_execute_one`, and
  `server/api.py:_event_stream` to publish events through the bus
  at every LLM call and every tool call. Latency measured via
  `time.perf_counter` (Pitfall 3 prevention). Capture overhead
  benchmark in TEST-12 / METRIC-05.
- **Pricing table + cost annotation.** Bundled
  `src/horus_os/observability/pricing.json` (cache-aware: four
  rates per model: input, output, cache write, cache read).
  `PricingTable` exposes `lookup(model)`. `CostAnnotator`
  subscribes to the bus BEFORE the persister so cost lands on
  the event before it is written. NULL not zero on unknown
  models (Pitfall 5: honesty over false precision). Override
  via `HORUS_OS_PRICING_PATH` env or `[pricing] path = "..."`
  in `config.toml`.
- **`observability/queries.py`** pure functions (`agent_totals`,
  `cost_by_agent`, `latency_p50_p95`, `tool_reliability`) shared
  by the dashboard JSON routes and the CLI subcommand.
- **Four new `/api/observability/*` GET routes** sourced from
  `queries.py`. The existing `/api/agents` route gained
  `total_cost_usd`, `latency_p50`, `latency_p95` rollup columns.
- **New `/observability` dashboard tab.** Three panels: cost by
  agent (bar chart, sorted high to low), latency p50 and p95
  (table per model), tool reliability (list per tool: success
  rate + last error preview). Window selector (24h / 7d / 30d,
  default 7d) drives all three. Pricing-staleness banner
  (yellow past 30 days, red past 90 days) with copy explaining
  the `HORUS_OS_PRICING_PATH` override. Small-sample guard
  renders a placeholder dash for cells with fewer than 10
  samples. Pre-v0.4 NULL render explains missing dollars rather
  than hiding them. The existing `/agents` tab shows the three
  new rollup columns.
- **`horus-os usage` CLI subcommand.** `horus-os usage --since
  Nh|Nd --format json|csv|table --by model|tool|agent`. Stdlib
  only. Reuses `observability/queries.py` so CLI and dashboard
  cannot drift. JSON output schema pinned in `docs/CLI.md` and
  tested against a fixture. Costs rounded to 6 decimal places,
  durations to integer ms (safe for `jq` pipelines).
- **`OtelAdapter`** behind the new `[otel]` extra. Opt-in OTLP
  HTTP exporter (gRPC was rejected for the Windows wheel-gap
  issue documented in STACK.md). Default-deny on body content;
  emits the eight canonical attributes from
  `src/horus_os/_observability/semconv.py`
  (`gen_ai.system`, `gen_ai.operation.name`,
  `gen_ai.request.model`, `gen_ai.usage.input_tokens`,
  `gen_ai.usage.output_tokens`, `gen_ai.usage.cached_tokens`,
  `horus_os.cost_usd`, `error.type`). Body capture opt-in via
  `HORUS_OS_OTEL_CAPTURE_CONTENT=true` (EXACT lowercase only)
  with the seven-pattern redactor allowlist from
  `src/horus_os/observability/redact.py` as defence-in-depth.
  Lazy SDK import so `pip install horus-os` without the extra
  raises a clean `RuntimeError`, never `ModuleNotFoundError`
  (Pitfall 12). Bounded shutdown: `force_flush(2000ms)` +
  `shutdown()` with a 1s per-export timeout so the app exits in
  under 3 seconds when the collector is unreachable.
- **Three non-negotiable OTel tests.** TEST-13 (PII redaction:
  `AKIAIOSFODNN7EXAMPLE` never appears in exported spans in
  either default or opt-in mode), TEST-14 (bounded shutdown
  against a closed-port endpoint completes in less than 3
  seconds), TEST-15 (two-variant install-smoke CI matrix:
  `install-smoke-no-otel` AND `install-smoke-with-otel` on the
  3-OS x 2-Python matrix).
- **`scripts/release_gate.py`** local pre-tag quality gate. Four
  checks: pricing freshness (within 14 days, env-overridable via
  `HORUS_OS_PRICING_MAX_AGE_DAYS`), CI two-variant install-smoke
  presence (greps both job literals), wheel pricing.json
  packaging (`python -m build` + zipfile membership), pytest
  pass. CLI flags `--check {pricing,wheel,ci,tests}` and
  `--skip-build`. See `docs/RELEASE.md` for the maintainer's
  release procedure.

### Changed

- **SQLite schema v4 to v5 (additive).** Four nullable rollup
  columns on `traces` (`total_input_tokens`,
  `total_output_tokens`, `total_cost_usd`, `total_duration_ms`).
  Two new child tables (`llm_calls`, `tool_invocations`). v0.3
  databases upgrade cleanly on first v0.4 startup; old
  `traces.usage` JSON blob preserved forever; pre-v0.4 trace
  rows render NULL on the new columns and the dashboard shows a
  placeholder dash with explanatory hover text.
- **Multi-iteration token capture now correct (Pitfall 1).** v0.3
  `record_trace` wrote only the FINAL iteration's `usage` dict.
  v0.4 publishes one `LLMCallEvent` per iteration through the
  observation bus; per-call `llm_calls` rows roll up to
  `traces.total_input_tokens = SUM(...)` on `RUN_END`. Streaming
  and non-streaming paths share the same capture.
- **SSE streaming runs now persist real cost (Pitfall 2).** v0.3
  `/api/chat/stream` did not route through `run_agent_loop`, so
  every streamed run silently landed at $0.00. v0.4 instruments
  the SSE branch directly via `stream.get_final_message().usage`
  (Anthropic) or `response.usage_metadata` (Gemini).
- **SQLite pragmas pinned to `synchronous=NORMAL` plus WAL** on
  every connection. Never `FULL`. Pitfall 8 prevention.

### Fixed

- **Per-iteration token undercount (Pitfall 1, Phase 33).** A
  5-iteration agent run in v0.3 reported 1/5 of actual cost.
  v0.4 reports the truth via per-call `llm_calls` rows that roll
  up to `traces.total_input_tokens`. Pre-v0.4 cost numbers
  should be treated as ceilings, not actuals.
- **SSE silent $0 (Pitfall 2, Phase 33).** v0.4 instruments the
  SSE branch directly; streamed runs now persist real token
  counts and the same rollup math drives the trace
  `total_cost_usd`.

### Documentation

- `docs/MIGRATION-v0.3-to-v0.4.md` (new): upgrade guide with
  `## Schema migration v4 to v5`, `## Bug fixes you inherit for
  free`, env vars, new CLI / dashboard surface, no breaking
  changes, upgrade checklist.
- `docs/OBSERVABILITY.md` (new): user-facing observability guide
  (what gets captured, dashboard tour, CLI usage, cost math,
  pricing staleness, privacy note).
- `docs/OTEL.md` (new): OTel adapter guide with installation,
  configuration, attribute schema, threat model (Default mode /
  Opt-in mode / Trust statement subsections), bounded shutdown,
  regression coverage.
- `docs/RELEASE.md` (new): maintainer release procedure with the
  release gate, pricing refresh procedure, full release
  sequence, and the rationale for the gate (Pitfall 5 and
  Pitfall 12).
- `docs/CLI.md`: extended with the `horus-os usage` subcommand
  and JSON output schema.

## [0.3.0] - 2026-05-24

Third alpha. Takes the v0.2 adapter plugin interface from "one
reference webhook" to a real ecosystem: four first-class adapters
(Discord, Slack, Email, Calendar) on top of new lifecycle hooks
(`start`/`stop`) and an adapter registry surfaced through both a JSON
API and a Dashboard Adapters tab. Calendar is the first
tool-providing adapter, registering `list_calendar_events_today` and
the write-gated `create_calendar_event` onto a master
`ToolRegistry` that adapters now share via `AdapterContext`.

See `docs/MIGRATION-v0.2-to-v0.3.md` for upgrade notes from v0.2.

### Added

- **LifecycleAdapter Protocol** (`horus_os.LifecycleAdapter`).
  Optional `runtime_checkable` sibling Protocol with async
  `start(context)` and `stop()` hooks. Long-running adapters
  implement it alongside `Adapter` and get tied into the
  FastAPI app lifespan automatically.
- **AdapterRegistry + AdapterEntry** (`horus_os.AdapterEntry`,
  `horus_os.AdapterRegistry`). Per-app status tracker attached
  to `app.state.adapter_registry`. Tracks `name`, `status`,
  `last_activity_at`, `error_count`, `error_message`. Adapters
  mutate via `mark_running`, `mark_stopped`, `mark_error`,
  `touch`. Three status constants exported:
  `ADAPTER_STATUS_RUNNING`, `ADAPTER_STATUS_STOPPED`,
  `ADAPTER_STATUS_ERROR`.
- **AdapterContext additions** (`AdapterContext.registry`,
  `AdapterContext.tool_registry`). Both additive with safe
  defaults (default factory `AdapterRegistry` and `None`
  respectively), so v0.2 `AdapterContext(config=, data_dir=)`
  calls keep working.
- **`GET /api/adapters`** route. Returns one JSON object per
  discovered adapter with `name`, `status`, `last_activity_at`,
  `error_count`, `error_message`, and `supports_toggle`.
- **FastAPI lifespan integration.** `create_app` registers a
  lifespan that calls `await adapter.start(context)` at startup
  and `await adapter.stop()` at shutdown for every adapter with
  the matching hook. Errors are captured into the registry and
  isolated from sibling adapters.
- **DiscordAdapter** + new `[discord]` optional extra
  (`discord.py>=2.3`) + new `horus_os.adapters:discord` entry
  point. Connects to the Discord gateway, handles app mentions
  in guild channels and DMs, chunked replies to honor Discord's
  2000-char limit.
- **SlackAdapter** + new `[slack]` optional extra
  (`slack-sdk>=3.27`) + new `horus_os.adapters:slack` entry
  point. Mounts `POST /api/adapters/slack/events` and
  `POST /api/adapters/slack/commands`, verifies HMAC-SHA256
  signatures over `v0:{timestamp}:{body}` with a 300s replay
  window, routes `app_mention` and DM `message` events through
  `run_agent`.
- **EmailAdapter** (stdlib only) + new
  `horus_os.adapters:email` entry point. IMAP poll loop, SMTP
  reply with full RFC 5322 threading (`In-Reply-To`,
  `References`, `Message-ID`, `Date`). Poison-message safety:
  `\Seen` is set even on agent failure so a crashing message
  cannot loop forever.
- **CalendarAdapter** + new `[calendar]` optional extra
  (`google-api-python-client>=2.110`,
  `google-auth-oauthlib>=1.2`) + new `horus_os.adapters:calendar`
  entry point. First tool-providing adapter: registers
  `list_calendar_events_today` (always) and
  `create_calendar_event` (gated on
  `HORUS_OS_CALENDAR_WRITE_ALLOWED=true`) onto
  `AdapterContext.tool_registry`.
- **POST /api/adapters/{name}/enable** and
  **POST /api/adapters/{name}/disable** toggle routes. Drive
  `await adapter.start(context)` / `await adapter.stop()` on
  lifecycle adapters. 404 unknown, 400 missing hook, 500 on
  hook exception with the registry capturing the error.
- **`supports_toggle` field on `/api/adapters` entries.** Derived
  from `hasattr(adapter, "start") and hasattr(adapter, "stop")`.
- **Dashboard Adapters tab.** Fifth nav tab in the local
  dashboard. Renders one row per adapter with a color-coded
  status pill (green running, gray stopped, red error),
  `last_activity_at`, `error_count`, truncated `error_message`,
  and a per-adapter Enable / Disable / n/a button driven by
  `supports_toggle`. Polls `GET /api/adapters` every five
  seconds.

### Changed

- `AdapterContext` gained two additive fields (`registry`,
  `tool_registry`) with safe defaults. v0.2 callers and v0.2
  third-party adapters remain byte-identical.
- `WebhookAdapter` now calls `context.registry.touch(name)`
  after each successful request so it shows up in the new
  Dashboard Adapters tab with a live `last_activity_at`.
- `create_app` now constructs a master `ToolRegistry`, passes it
  through `AdapterContext.tool_registry`, and exposes both
  `app.state.tool_registry` and `app.state.adapters` for
  downstream code to introspect.

### Documentation

- `ARCHITECTURE.md` refreshed for v0.3: new Adapter ecosystem
  section covering LifecycleAdapter, AdapterRegistry, the
  lifespan integration, `tool_registry`, the four shipped
  adapters, toggle routes, and the Dashboard Adapters tab.
  Module layout updated; the deferred list renamed to "What is
  not in v0.3" with the shipped items removed and the new v0.3-era
  items (Socket Mode, OAuth CLI, write-tool merge into chat,
  soft-disable middleware) added.
- Four runnable, offline adapter examples added under
  `examples/`: `discord_adapter.py`, `slack_adapter.py`,
  `email_adapter.py`, `calendar_adapter.py`. Each uses the
  same `sys.modules` injection pattern the adapter tests use,
  runs without the optional SDK installed, and prints the
  dispatch and registry state.
- `docs/MIGRATION-v0.2-to-v0.3.md` added: additive Protocol
  changes, full env-var list, new optional dependency groups,
  no-schema-migration note, upgrade code samples.
- Four per-adapter setup guides under `docs/adapters/`:
  `DISCORD.md`, `SLACK.md`, `EMAIL.md`, `CALENDAR.md`.
- README updated with a "What is new in v0.3" section and
  Documents entries for the migration guide and the adapter
  setup guides.

## [0.1.0] - 2026-05-23

First alpha release. A working v0.1 foundation: install the package,
run an agent through CLI or local web chat, and read or write a
markdown notes folder with a full SQLite audit trail.

### Added

- **Agent runtime** (`run_agent`, `run_agent_async`, `run_agent_loop`)
  with sync and async paths. Multi-turn tool-execution loop.
- **Anthropic provider** with sync and async call functions and a
  `Conversation` class for stateful multi-turn use.
- **Google Gemini provider** with the same surface as Anthropic.
- **Tool registry** (`ToolRegistry`, `execute_tool_uses`) plus a
  built-in `read_file_tool` factory with optional path sandboxing.
- **Memory layer** for markdown notes folders: `NotesStore`,
  `list_notes` / `search_notes` / `read_note` / `create_note` /
  `append_note` tool factories.
- **SQLite persistence** (`Database`, `TraceRecord`, `NoteWrite`)
  with WAL mode, schema v2, idempotent migrations, and a
  reviewable audit trail for every note write.
- **CLI surface**: `horus-os init`, `init --interactive` (setup
  wizard with API key onboarding and 1-token live validation),
  `traces`, `run "<prompt>"`, `serve`.
- **Local web dashboard** served by FastAPI: chat surface, traces
  explorer, writes audit view. Single-file HTML + vanilla JS, no
  build step required.
- **JSON API** under `/api`: health, traces, trace-by-id, writes,
  chat.
- **Three-OS install verification** via GitHub Actions
  `install-smoke` job on (Ubuntu, macOS, Windows) by (Python 3.11,
  3.12).
- 175 automated tests covering every public API surface.
- Optional dependency groups: `[anthropic]`, `[gemini]`,
  `[dashboard]`, `[all]`, `[dev]`.

### Documentation

- `README.md`, `PROJECT.md`, `ARCHITECTURE.md`, `ROADMAP.md`,
  `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `CLAUDE.md`.
- Apache 2.0 license.

### Known limitations

- No streaming responses. The dashboard waits for the full loop to
  finish before rendering.
- No retry, no rate-limit handling, no cost tracking. Defer to
  v0.5 Observability.
- The dashboard is a single-page vanilla-JS surface. A Next.js
  evolution is anticipated when the UX requirements grow.
- Tool execution loop bails out at 10 iterations by default; users
  can override with `--max-iterations`.

## [0.2.0] - 2026-05-23

Second alpha. Moves from "one agent answers questions" to "a personal
team of agents that can hand off to each other, with live streaming
responses in the CLI and dashboard." Named agent profiles persist in
SQLite. A coordinator delegates to sub-agents. Both providers stream
incremental tokens. An adapter plugin interface opens the door to
external surfaces.

See `docs/MIGRATION-v0.1-to-v0.2.md` for upgrade notes from v0.1.

### Added

- **Agent profiles.** `AgentProfile` dataclass plus a new
  `agent_profiles` table with `Database.load_profile`,
  `save_profile`, `list_profiles`, and `delete_profile`. A `default`
  profile is bootstrapped on every `init()` so a fresh database
  always has at least one row.
- **Multi-agent runtime.** `delegate_to_agent` tool produced by
  `make_delegate_tool(db, master_registry, parent_trace_id, budget,
  provider)`. Sub-agent runs inherit a shared `IterationBudget` so
  the iteration cap applies across the whole delegation tree.
  Parallel `delegate_to_agent` calls in a single coordinator turn
  execute concurrently and merge results back by `tool_use_id`.
- **Parent and child traces.** `TraceRecord` carries
  `parent_trace_id` and `agent_profile_name`; `Database.record_trace`
  accepts them as optional kwargs; `Database.list_child_traces`
  returns the children of a coordinator trace.
- **Streaming runtime.** `run_agent_stream(prompt, *, provider,
  model, max_tokens, system)` async generator that yields token
  strings and `ToolCallEvent` values. Both Anthropic and Gemini
  provider streaming paths land via `stream_anthropic_async` and
  `stream_gemini_async`.
- **CLI multi-agent surface.** `horus-os agents` group with `list`,
  `show`, `create`, `edit`, `delete`. `horus-os run --agent <name>`
  loads a profile and threads its `system_prompt` and
  `default_model` through the run.
- **Dashboard v0.2.** A new Agents tab, live SSE token streaming in
  the chat surface, and a delegate-tree expander on traces that
  carry an `agent_profile_name`. New server routes: `/api/agents`
  (list/show/create/edit/delete with `last_activity_at`),
  `/api/traces/{id}/children`, and `POST /api/chat/stream` with a
  `type`-discriminated SSE frame shape (`token`, `tool_call`,
  `done`, `error`).
- **Adapter contract.** `horus_os.adapters` package exposes the
  `Adapter` Protocol, `AdapterContext`, `discover_adapters`, and the
  `ADAPTER_ENTRY_POINT_GROUP` constant. Adapters are discovered via
  `entry_points(group="horus_os.adapters")` and bound onto FastAPI
  at `create_app` startup. Per-entry failures are isolated.
- **Reference adapter.** `WebhookAdapter` mounts
  `POST /api/adapters/webhook` with HMAC-SHA256 signature
  validation. Refuses to run when `HORUS_OS_WEBHOOK_SECRET` is
  unset.

### Changed

- `horus-os run "<prompt>"` now streams tokens to stdout by default.
  Pass `--no-stream` to restore the v0.1 buffered output.
  `ToolCallEvent` values surface on stderr as
  `[tool-request] {name}({input})`.
- SQLite schema upgraded automatically to version 4 on first
  startup. The migration is idempotent: v0.1 databases pick up the
  `agent_profiles` table (v3) and the `parent_trace_id` plus
  `agent_profile_name` columns on `traces` (v4) without manual
  intervention. v0.1 trace rows remain readable.

### Documentation

- `CONTRIBUTING.md` rewritten with dev setup, branch and commit
  conventions, code style, and contributor onboarding guidance now
  that v0.1 has shipped.
- `SECURITY.md` added with a private-disclosure process via GitHub
  Security Advisories.
- `ARCHITECTURE.md` refreshed for v0.2: multi-agent shape, streaming
  surface, adapter interface, schema v4, refreshed deferred list.
- `docs/MIGRATION-v0.1-to-v0.2.md` added with API additions, schema
  migration, behavior changes, and upgrade code samples.
- `examples/` added: `multi_agent.py`, `streaming.py`,
  `custom_adapter.py` plus an index README. All three run offline.
- GitHub issue templates (bug report, feature request) and pull
  request template added under `.github/`.

