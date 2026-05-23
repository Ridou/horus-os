# Phase 16 Context: Dashboard multi-agent view and streaming chat

**Date:** 2026-05-23
**Phase:** 16
**Status:** Context captured (headless auto-mode)

## Domain

Phase 16 ships the dashboard surface for the v0.2 multi-agent and
streaming features. The work spans two layers:

1. Backend: a streaming SSE chat endpoint that drives `run_agent_stream`,
   plus `/api/agents` CRUD routes that mirror the Phase 15 CLI, and an
   enrichment of `/api/traces/{id}` so the frontend can render a
   delegate tree (parent + child link metadata is already in storage).
2. Frontend: extend the single-page vanilla-JS dashboard with an
   "Agents" tab, swap the chat surface from `fetch + JSON` to an SSE
   reader that paints tokens live, and add a nested-list delegate-tree
   visual to the existing trace table.

Phase 13 wrote `parent_trace_id` and `agent_profile_name` columns plus
the `list_child_traces` SQLite helper. Phase 14 shipped
`run_agent_stream`. Phase 15 added `Database.{list,load,save,delete}_profile`
CRUD. All primitives are in place. This phase is composition only.

## Canonical refs

- `.planning/ROADMAP.md` Phase 16 success criteria
- `.planning/REQUIREMENTS.md` STREAM-03, MIG-02
- `src/horus_os/server/api.py` current FastAPI surface
- `src/horus_os/server/static/index.html` single-page dashboard
- `src/horus_os/agent.py` `run_agent_stream` (Phase 14)
- `src/horus_os/storage.py` profile CRUD and `list_child_traces`
- `tests/test_server_api.py` FastAPI TestClient patterns
- `tests/test_server_static.py` dashboard content assertions

## Decisions

### 1. Stream over SSE, not WebSockets

Use `text/event-stream` with FastAPI's `StreamingResponse`. SSE composes
cleanly with `TestClient.stream(...)` in tests, is one-way (server to
client), and matches the existing JSON-only surface stylistically.
WebSockets would force a separate test runtime and a bidirectional
protocol the chat does not need.

### 2. Single-page dashboard, no build step

Extend `static/index.html` in place. Add an Agents tab, an SSE-driven
chat path, and a delegate-tree nested list. No bundler, no framework,
no npm. The dashboard ships as Python package data, and stays
inspectable in a browser source view.

### 3. SSE event shape

The stream emits two event types:

- `data: {"type":"token","text":"..."}` for each text delta
- `data: {"type":"tool_call","name":"...","input":{...}}` when the
  model surfaces a `ToolCallEvent`
- `data: {"type":"done","trace_id":"...","latency_ms":...}` once at the
  end, after the trace row is recorded
- `data: {"type":"error","message":"..."}` on failure, with an error
  trace recorded server-side

Each frame is `data: <json>\n\n`. No custom `event:` field; the client
dispatches on `type`. Keeping it JSON-typed (vs. raw token strings)
avoids ambiguity when a token literally contains the separator and
makes tool-call events fit into the same channel.

### 4. v0.1 compatibility

`parent_trace_id` and `agent_profile_name` are read with `getattr` style
defaults on the frontend. A v0.1 trace has both as null, renders as a
flat row with no tree indicator, and the existing trace explorer keeps
working byte-identically.

### 5. Delegate tree rendering

The frontend asks `/api/traces/{id}` for the focused trace and, if it
has children (any trace whose `parent_trace_id` matches), `/api/traces/{id}/children`
for the immediate child list. Render as a nested `<ul>` with an
indented prefix character. Backend does no recursion; the frontend
lazy-loads children only when the user expands a node. Two levels is
enough for v0.2 (delegate tree depth in practice is shallow).

### 6. Profile CRUD route shape

Five HTTP verbs across two paths, intentionally tracking the CLI:

- `GET  /api/agents`            list profiles
- `GET  /api/agents/{name}`     show one profile
- `POST /api/agents`            create (409 on duplicate)
- `PATCH /api/agents/{name}`    edit (404 on missing)
- `DELETE /api/agents/{name}`   delete (404 on missing)

`last_activity_at` is computed via a JOIN-free per-row query that picks
the newest `traces.created_at WHERE agent_profile_name = name`. v0.1
profiles with no traces report null.

### 7. Backend factoring

Move the existing handlers into a dedicated `_register_routes` function
inside `create_app` so the new routes do not blow up the file. No new
module, no new package layer. `_event_stream` lives next to `chat`
as a private async generator.

### 8. Test surface

One new test file: `tests/test_server_agents.py` for the agents CRUD
routes. One new test file: `tests/test_server_stream.py` for the SSE
endpoint, using `TestClient(...).stream(...)` and a monkeypatched
`run_agent_stream`. Extend `tests/test_server_api.py` for the
`parent_trace_id`/`agent_profile_name` fields on `/api/traces/{id}`
and for the new `/api/traces/{id}/children` route. Extend
`tests/test_server_static.py` to assert the new tab markers appear in
the HTML (no JS evaluation; just DOM-marker presence).

## Execution split

- **Plan 01:** Backend. SSE chat stream, agents CRUD routes, trace
  enrichment, children route. Tests for every new route. No frontend
  changes; the JSON shape is the contract.
- **Plan 02:** Frontend. Extend `static/index.html` with the Agents
  tab, swap chat to SSE consumption, render the delegate tree. Static
  test additions only.

Atomic commits: docs(16) for plan+context, feat(16) for backend,
feat(16) for frontend, docs(16) for summaries.

## Deferred / not in scope

- Recursive delegate tree expansion beyond two levels (lazy-load
  children stays flat per click; deeper trees just keep clicking).
- Token-level usage counters in SSE (Phase 14 stream does not yield
  usage; the done event reports latency only).
- Profile JSON write/edit forms in the dashboard (read-only Agents
  view for v0.2; editing stays on the CLI to keep the threat surface
  minimal).
- Auth or rate limiting on the SSE route (local-only server in v0.2).
