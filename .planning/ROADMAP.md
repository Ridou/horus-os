# Roadmap: horus-os

## Milestones

- [x] **v0.1 Foundation** (Phases 01-11), shipped 2026-05-23 as v0.1.0. CLI + web chat, Anthropic + Gemini, one agent, six tools, full memory layer, 3-OS install gate, first public release.
- [x] **v0.2 Multi-Agent + Streaming** (Phases 12-21), shipped 2026-05-23 as v0.2.0. Named agent profiles, coordinator-to-sub-agent delegation, provider streaming on both CLI and dashboard, adapter plugin interface.
- [ ] **v0.3 Adapter Ecosystem** (Phases 22-31), active. Discord, Slack, email, and calendar adapters on top of the v0.2 plugin contract, plus adapter lifecycle hooks and dashboard adapter management.

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

### v0.3 Adapter Ecosystem (Phases 22-31)

**Milestone Goal:** Take the v0.2 adapter plugin interface from "one reference webhook" to a real ecosystem. Ship four first-class adapters (Discord, Slack, email, calendar) that turn horus-os into a personal command center reachable from the user's existing channels. Add adapter lifecycle hooks for long-running connections, surface adapter health in the dashboard, and document the setup path for each integration.

**Parallelization:** 22 → (23 ∥ 24 ∥ 25 ∥ 26) → 27 → 28 → 29 → 30 → 31. Phase 22 (lifecycle hooks) gates the four adapter implementations because Discord/Slack need persistent connections that the current bind-only Protocol does not support. After 22 lands, the four adapters can ship in parallel.

- [ ] **Phase 22: Adapter lifecycle hooks**, optional `start(ctx)` and `stop()` methods on the Adapter Protocol; FastAPI lifespan integration so long-running adapters get a background task slot; adapter status (running, stopped, error) queryable via `/api/adapters`.
- [ ] **Phase 23: Discord adapter**, Discord bot listens for mentions and direct messages, routes to a configured agent profile, replies in-channel; setup guide for bot creation and token; backoff reconnect on disconnect.
- [ ] **Phase 24: Slack adapter**, Slack Events API endpoint handles `app_mention` and DMs, signature verification via signing secret, slash command support, routes to an agent profile.
- [ ] **Phase 25: Email adapter**, IMAP poll + SMTP send. Polls inbox on a configurable interval, runs an agent on new messages, replies via SMTP. No new heavy deps (stdlib `imaplib` + `smtplib`).
- [ ] **Phase 26: Calendar adapter**, Google Calendar adapter exposes "list today's events" as a tool agents can call; optional event creation gated behind a permission flag; documented OAuth flow with `google-api-python-client`.
- [ ] **Phase 27: Dashboard adapter management**, `/adapters` dashboard view shows configured adapters with status (running, stopped, last activity, error count); enable and disable from dashboard; per-adapter health indicator.
- [ ] **Phase 28: Documentation and examples refresh**, Update ARCHITECTURE.md for v0.3, add `examples/discord_adapter.py`, `examples/slack_adapter.py`, `examples/email_adapter.py`, `examples/calendar_adapter.py`, write the v0.2 to v0.3 migration guide.
- [ ] **Phase 29: Test surface expansion**, Adapter lifecycle tests, mocked-SDK tests for each of the four adapters, cross-adapter routing test, error-path coverage.
- [ ] **Phase 30: Three-OS install verification (v0.3)**, Same hard gate as Phase 10 and Phase 20, re-targeted at the v0.3 feature set.
- [ ] **Phase 31: v0.3.0 release**, Tag v0.3.0 on origin, CHANGELOG updated, version bumped, GitHub Release published with migration notes.

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

## Progress

**Execution Order:** 22 → (23 ∥ 24 ∥ 25 ∥ 26) → 27 → 28 → 29 → 30 → 31

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 01-11 | v0.1 | 13/13 | Complete | 2026-05-23 |
| 12-21 | v0.2 | 11/11 | Complete | 2026-05-23 |
| 22. Adapter lifecycle hooks | v0.3 | 0/1 | Not started | - |
| 23. Discord adapter | v0.3 | 0/1 | Not started | - |
| 24. Slack adapter | v0.3 | 0/1 | Not started | - |
| 25. Email adapter | v0.3 | 0/1 | Not started | - |
| 26. Calendar adapter | v0.3 | 0/1 | Not started | - |
| 27. Dashboard adapter management | v0.3 | 0/1 | Not started | - |
| 28. Documentation and examples refresh | v0.3 | 0/1 | Not started | - |
| 29. Test surface expansion | v0.3 | 0/1 | Not started | - |
| 30. Three-OS install verification (v0.3) | v0.3 | 0/1 | Not started | - |
| 31. v0.3.0 release | v0.3 | 0/1 | Not started | - |
