# Roadmap: horus-os

## Milestones

- [x] **v0.1 Foundation** (Phases 01-11), shipped 2026-05-23 as v0.1.0. CLI + web chat, Anthropic + Gemini, one agent, six tools, full memory layer, 3-OS install gate, first public release.
- [ ] **v0.2 Multi-Agent + Streaming** (Phases 12-21), active. Named agent profiles, coordinator-to-sub-agent delegation, provider streaming on both CLI and dashboard, adapter plugin interface.

## Phases

<details>
<summary>v0.1 Foundation (Phases 01-11) - SHIPPED 2026-05-23</summary>

- [x] **Phase 01: Repo scaffold and CI**, pyproject.toml, src layout, ruff + pytest, GitHub Actions running lint and test on Ubuntu, macOS, Windows. (completed 2026-05-23)
- [x] **Phase 02: Agent runtime core**, Python module that takes a prompt, invokes Anthropic or Gemini with one tool, returns a structured result. Sync and async paths both supported. (completed 2026-05-23)
- [x] **Phase 03: Persistence layer**, SQLite schema for tasks, traces, agent state. Migrations are idempotent. WAL mode. (completed 2026-05-23)
- [x] **Phase 04: Tool registry**, Register a callable as a tool, expose it to the agent, log every invocation. First example tool: read a local file. (completed 2026-05-23)
- [x] **Phase 05: Memory layer, read path**, Agent searches a markdown notes folder and reads files. (completed 2026-05-23)
- [x] **Phase 06: Memory layer, write path**, Agent appends to the notes folder with a structured trail. Every write is reviewable. (completed 2026-05-23)
- [x] **Phase 07: CLI surface**, `horus-os run "<prompt>"` runs an agent against the local stack. Output is structured. Also: `init`, `serve` (stub), `traces`. Multi-turn tool-execution loop shipped. (completed 2026-05-23)
- [x] **Phase 08: Web chat and dashboard**, single-page HTML dashboard served locally by FastAPI. Hosts a chat surface, traces explorer, and writes audit view. (completed 2026-05-23)
- [x] **Phase 09: Setup wizard with API key onboarding**, `horus-os init --interactive` walks a new user through configuration. Direct links to Anthropic console and Google AI Studio. Validates keys with a live ping before saving. Idempotent and resumable. (completed 2026-05-23)
- [x] **Phase 10: Three-OS install verification**, Fresh-VM install on macOS, Ubuntu, Windows via the install-smoke CI job. (completed 2026-05-23)
- [x] **Phase 11: First public release**, Tagged v0.1.0 on origin, CHANGELOG written, version bumped. (completed 2026-05-23)

</details>

### v0.2 Multi-Agent + Streaming (Phases 12-21)

**Milestone Goal:** Move from "one agent answers questions" to "a personal team of agents that can hand off to each other, with live streaming responses in the CLI and dashboard." Named agent profiles persist in SQLite. A coordinator delegates to sub-agents. Both providers stream incremental tokens. The adapter plugin interface opens the door to external surfaces (Discord, Slack, webhook receivers) which arrive in v0.3.

**Parallelization:** 12 → 13 → (14 ∥ 15 ∥ 16 ∥ 17) → 18 → 19 → 20 → 21. Phase 12 (agent profile schema + migration) gates everything because it changes the storage layer. After 13 (runtime support for delegation) lands, surfaces and adapters can ship in parallel.

- [x] **Phase 12: Agent profile model and schema migration**, `agent_profiles` table with name, system prompt, default model, allowed tools, memory scope. Idempotent forward migration from v0.1 schema. CRUD API. At least one default agent auto-created on `init`. (completed 2026-05-23)
- [ ] **Phase 13: Multi-agent orchestration runtime**, `delegate_to_agent` tool. Parent and child trace linkage. A coordinator can invoke one or more sub-agents synchronously or in parallel. Iteration bound applies to the whole tree.
- [ ] **Phase 14: Streaming response support**, `run_agent_stream` async generator. Anthropic and Gemini streaming SDK paths. `run_agent` and `run_agent_loop` continue to work unchanged for non-streaming callers.
- [ ] **Phase 15: CLI multi-agent surface**, `horus-os agents` subcommand (list, show, create, edit, delete). `horus-os run --agent <name>`. Streaming output to terminal by default; `--no-stream` falls back to the v0.1 behavior.
- [ ] **Phase 16: Dashboard multi-agent view and streaming chat**, agents list, per-agent activity, delegate-tree visualization per run, live token streaming in the chat surface.
- [ ] **Phase 17: Adapter plugin interface**, Plugin contract via `importlib.metadata.entry_points("horus_os.adapters")`. One reference adapter ships: HTTP webhook receiver. Third-party adapters can register without forking horus-os.
- [ ] **Phase 18: Documentation and examples refresh**, Update ARCHITECTURE.md for the multi-agent shape. Add `examples/multi_agent.py`, `examples/streaming.py`, `examples/custom_adapter.py`. Document the migration path for v0.1 users.
- [ ] **Phase 19: Test surface expansion**, End-to-end multi-agent flows, streaming partial-failure modes, adapter contract tests. Cross-OS coverage maintained.
- [ ] **Phase 20: Three-OS install verification (v0.2)**, Same hard gate as Phase 10, re-targeted at the v0.2 feature set. Fresh-VM install on macOS, Ubuntu, Windows passes through `install-smoke`.
- [ ] **Phase 21: v0.2.0 release**, Tag v0.2.0 on origin, CHANGELOG updated, version bumped, GitHub Release published with migration notes.

## Phase Details

### Phase 12: Agent profile model and schema migration
**Goal**: Persist named agent profiles in SQLite with idempotent forward migration from v0.1, and auto-create a default agent on init.
**Depends on**: Phase 11 (v0.1.0 release)
**Requirements**: MA-01, MA-04, MIG-01, MIG-02
**Success Criteria** (what must be TRUE):
  1. `agent_profiles` table exists in SQLite with columns for name, system_prompt, default_model, allowed_tools, memory_scope, and timestamps
  2. A v0.1 database upgrades to v0.2 schema on first boot, idempotently, and existing v0.1 traces remain readable
  3. `horus-os init` creates a default agent profile if none exist; subsequent runs do not duplicate it
  4. A CRUD API (`load_profile`, `save_profile`, `list_profiles`, `delete_profile`) exists with full test coverage
**Plans**: 1 plan

Plans:
- [x] 12-01-PLAN.md -- AgentProfile type, agent_profiles DDL, CRUD API, default agent bootstrap

### Phase 13: Multi-agent orchestration runtime
**Goal**: Coordinator can delegate to sub-agents through a registered tool; parent/child trace links capture the call tree.
**Depends on**: Phase 12
**Requirements**: MA-02, MA-03
**Success Criteria** (what must be TRUE):
  1. A `delegate_to_agent` tool is registered and invocable from any agent profile that has it allowed
  2. Every sub-agent trace carries a `parent_id` linking it to the coordinator's run
  3. The 10-iteration cap applies across the entire delegation tree, not per-agent
  4. Parallel delegation to multiple sub-agents completes without deadlock and merges results back to the coordinator
**Plans**: 2 plans

Plans:
- [ ] 13-01-PLAN.md -- Schema v4 migration, TraceRecord extension, IterationBudget, _filter_registry
- [ ] 13-02-PLAN.md -- make_delegate_tool factory, run_agent_loop budget+system_prompt, parallel delegation, integration tests

### Phase 14: Streaming response support
**Goal**: `run_agent_stream` async generator yields incremental tokens from both providers without breaking the existing `run_agent` surface.
**Depends on**: Phase 12
**Requirements**: STREAM-01
**Success Criteria** (what must be TRUE):
  1. `run_agent_stream` yields tokens incrementally from both Anthropic and Gemini provider streams
  2. The non-streaming `run_agent` and `run_agent_loop` continue to pass v0.1 tests unchanged
  3. Streaming handles a mid-flight tool call by emitting a synthetic event the consumer can observe
  4. Trace recording captures the final assembled response, not the partial chunks
**Plans**: TBD

Plans:
- [ ] 14-01: Streaming generator, provider stream paths, trace assembly

### Phase 15: CLI multi-agent surface
**Goal**: New `horus-os agents` subcommand plus `--agent <name>` and streaming output on `run`.
**Depends on**: Phase 12, Phase 13, Phase 14
**Requirements**: MA-01, STREAM-02
**Success Criteria** (what must be TRUE):
  1. `horus-os agents list` shows configured profiles in a stable, machine-parseable format
  2. `horus-os agents create`, `agents show`, `agents edit`, `agents delete` work and round-trip through SQLite
  3. `horus-os run --agent <name>` runs against the named profile (falls back to default if omitted)
  4. CLI streams tokens to stdout by default; `--no-stream` falls back to the v0.1 buffered output
**Plans**: TBD

Plans:
- [ ] 15-01: Agents subcommand + run --agent + streaming output

### Phase 16: Dashboard multi-agent view and streaming chat
**Goal**: Dashboard lists configured agents, shows the delegate tree for each run, and renders streamed tokens in chat.
**Depends on**: Phase 12, Phase 13, Phase 14
**Requirements**: STREAM-03, MIG-02
**Success Criteria** (what must be TRUE):
  1. The dashboard exposes an `/agents` view that lists configured agent profiles with last-activity timestamps
  2. The trace explorer renders the parent/child delegate tree for any multi-agent run
  3. The chat surface streams tokens live (no buffer-and-flush at the end)
  4. v0.1 single-agent traces still render correctly in the v0.2 dashboard
**Plans**: TBD

Plans:
- [ ] 16-01: Agents view, delegate tree, streaming chat, v0.1 trace compatibility

### Phase 17: Adapter plugin interface
**Goal**: Plugin contract via entry points, with one reference adapter (HTTP webhook receiver) and tests for third-party registration.
**Depends on**: Phase 12, Phase 13
**Requirements**: ADAPT-01, ADAPT-02, ADAPT-03
**Success Criteria** (what must be TRUE):
  1. Adapters register via `importlib.metadata.entry_points("horus_os.adapters")` and are discovered on import
  2. The reference HTTP webhook adapter handles inbound payloads and routes to a configured agent
  3. A third-party adapter installed from a separate package is discovered without modifying horus-os
  4. Adapter contract is documented with a stable Python type signature
**Plans**: TBD

Plans:
- [ ] 17-01: Adapter contract, entry-point discovery, webhook reference adapter

### Phase 18: Documentation and examples refresh
**Goal**: Refresh ARCHITECTURE.md for multi-agent + streaming, add three new examples, write the v0.1 to v0.2 migration guide.
**Depends on**: Phase 12, Phase 13, Phase 14, Phase 15, Phase 16, Phase 17
**Requirements**: MIG-03, REL-04
**Success Criteria** (what must be TRUE):
  1. ARCHITECTURE.md documents the multi-agent data flow, streaming surface, and adapter interface
  2. `examples/multi_agent.py`, `examples/streaming.py`, `examples/custom_adapter.py` exist and run end-to-end
  3. A migration guide (`docs/MIGRATION-v0.1-to-v0.2.md` or similar) explains the schema upgrade and any user-visible behavior changes
  4. README links to the migration guide and the examples directory
**Plans**: TBD

Plans:
- [ ] 18-01: Architecture refresh, three examples, migration guide

### Phase 19: Test surface expansion
**Goal**: End-to-end multi-agent flows, streaming partial-failure modes, and adapter contract tests are all covered.
**Depends on**: Phase 12, Phase 13, Phase 14, Phase 15, Phase 16, Phase 17
**Requirements**: TEST-04, TEST-05, TEST-06
**Success Criteria** (what must be TRUE):
  1. Multi-agent end-to-end tests pass (coordinator delegates, sub-agent runs, parent receives result)
  2. Streaming tests cover normal flow, mid-flight tool calls, and provider error during stream
  3. Adapter contract tests verify entry-point discovery, dispatch, and third-party adapter registration
  4. Overall test count is at least the v0.1 baseline (175) plus the new tests; nothing regresses
**Plans**: TBD

Plans:
- [ ] 19-01: Multi-agent E2E + streaming + adapter contract test expansion

### Phase 20: Three-OS install verification (v0.2)
**Goal**: `install-smoke` job re-runs against the v0.2 feature set and stays green on Ubuntu, macOS, Windows.
**Depends on**: Phase 12, Phase 13, Phase 14, Phase 15, Phase 16, Phase 17, Phase 18, Phase 19
**Requirements**: TEST-04, TEST-05, TEST-06
**Success Criteria** (what must be TRUE):
  1. The `install-smoke` CI job passes on Ubuntu, macOS, and Windows for Python 3.11 and 3.12
  2. `horus-os agents list` succeeds on a fresh install on each OS
  3. `horus-os run --agent default "hello"` returns a result on each OS when keys are available
  4. Streaming output renders correctly in each OS default terminal
**Plans**: TBD

Plans:
- [ ] 20-01: Update install-smoke for v0.2 surface, verify three-OS green

### Phase 21: v0.2.0 release
**Goal**: Tag v0.2.0, update CHANGELOG with the milestone diff, publish GitHub Release with migration notes.
**Depends on**: Phase 20
**Requirements**: REL-03, REL-04
**Success Criteria** (what must be TRUE):
  1. The `v0.2.0` tag exists on origin
  2. CHANGELOG.md has a complete `[0.2.0]` section describing all multi-agent, streaming, and adapter additions
  3. A GitHub Release at the v0.2.0 tag is published with the CHANGELOG body and a link to the migration guide
  4. Version bumped to `0.2.0` in `pyproject.toml` and `src/horus_os/__init__.py`
**Plans**: TBD

Plans:
- [ ] 21-01: Version bump, CHANGELOG, tag, GitHub Release

## Progress

**Execution Order:** 12 → 13 → (14 ∥ 15 ∥ 16 ∥ 17) → 18 → 19 → 20 → 21

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 01-11 | v0.1 | 13/13 | Complete | 2026-05-23 |
| 12. Agent profile model and schema migration | v0.2 | 1/1 | Complete    | 2026-05-23 |
| 13. Multi-agent orchestration runtime | v0.2 | 0/1 | Not started | - |
| 14. Streaming response support | v0.2 | 0/1 | Not started | - |
| 15. CLI multi-agent surface | v0.2 | 0/1 | Not started | - |
| 16. Dashboard multi-agent view and streaming chat | v0.2 | 0/1 | Not started | - |
| 17. Adapter plugin interface | v0.2 | 0/1 | Not started | - |
| 18. Documentation and examples refresh | v0.2 | 0/1 | Not started | - |
| 19. Test surface expansion | v0.2 | 0/1 | Not started | - |
| 20. Three-OS install verification (v0.2) | v0.2 | 0/1 | Not started | - |
| 21. v0.2.0 release | v0.2 | 0/1 | Not started | - |
