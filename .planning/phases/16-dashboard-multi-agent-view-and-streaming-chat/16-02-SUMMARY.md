# Phase 16 Plan 02 Summary

**Status:** Shipped
**Commit:** feat(16): dashboard agents tab, SSE chat, delegate-tree expander
**Date:** 2026-05-23

## What shipped

The single-page vanilla-JS dashboard now exposes the v0.2 multi-agent
view and live token streaming. The contract from Plan 01 is consumed
without a build step, framework, or new dependency.

### New tab: Agents

A fourth top-level tab between Traces and Writes. `loadAgents()` calls
`/api/agents` and renders a table of:

- `name`
- `default_model` (with `(default)` fallback when null)
- `allowed_tools` (`(all)` when null, `(none)` when explicit empty,
  comma-joined when populated)
- `last_activity_at` (with `(never)` fallback)
- `system_prompt` preview (truncated at 60 chars)

Empty and error states reuse the existing `.empty` styling. The
refresh button on the tab head is wired identically to Traces.

### Chat: SSE consumption

The Send button no longer waits for a JSON response. It opens
`POST /api/chat/stream`, reads the body as a `ReadableStream`, and
dispatches every `data: <json>\n\n` frame on the JSON `type` field.

- `token` -> `pre.appendChild(document.createTextNode(text))` so the
  user sees the response paint in real time. No innerHTML on streamed
  content; the XSS boundary stays intact.
- `tool_call` -> a muted `[tool-request] name(input)` aside inserted
  above the trailing status line. Tool count is reflected in the meta.
- `done` -> finalizes the meta line with `[streamed, Nms, trace
  abcd1234, K tool calls]`.
- `error` -> tints the `<pre>` with `--error`, appends the message,
  and rewrites the meta line as `[error after Nms, trace abcd1234]`.

HTTP 4xx and 503 responses are surfaced before any frame is read and
rendered as a single error block, matching the JSON `detail` shape.

### Traces: delegate-tree expander

Trace rows that carry `agent_profile_name` get an `expand` button.
Clicking the button calls `/api/traces/{id}/children` and renders the
result inline as a nested `tree-row` containing a child table with the
same columns plus an `agent` column. Clicking again removes the
sibling row and resets the button label.

v0.1 traces (where `agent_profile_name` is null) render exactly as
before with no expand affordance. MIG-02 is satisfied at the
frontend boundary, not just in the JSON shape.

### Style

All new CSS reuses the existing `:root` variable block. No new color
tokens. New classes (`tree-toggle`, `tree-row`, `stream-tool`,
`stream-error`) reference `--border`, `--text-muted`, `--text`, and
`--error` only. Dark theme preserved.

## Files touched

- `src/horus_os/server/static/index.html`: nav button for Agents tab,
  new `#agents` section, restructured chat send handler for SSE,
  `loadAgents` and `toggleChildren` functions, expanded
  `loadTraces` columns (+ agent + expand cell), new CSS rules.
- `tests/test_server_static.py`: four additional substring assertions
  on the dashboard body covering `/api/chat/stream`, `/api/agents`,
  `data-tab="agents"`, and the `/children` URL fragment. These lock
  in the new surface at the markup level without needing a JS runtime.

## Test count delta

No new test files in this plan. Static test gains four assertions in
its single test case. Full suite stays at 275 passing.

## Lint status

`ruff check .` clean. `ruff format --check .` clean. HTML and JS are
unlinted by intent.

## Notable / deferred

- Delegate tree depth: v0.2 ships two levels (parent + one expansion
  of children). Children themselves do not get expand buttons. The
  CONTEXT records the v0.3 follow-up. In practice the delegation
  trees observed during Phase 13 are flat.
- Profile editing in the dashboard: the Agents tab is read-only. CRUD
  stays on the CLI from Plan 15, keeping the dashboard's threat
  surface minimal. The JSON routes exist for future use.
- Provider/model echo in the `done` frame: deliberately not added.
  The client knows the request side already.
- Manual sanity verification beyond the assert: open the dashboard,
  click Agents (the default profile renders), send a prompt (tokens
  paint live when an API key is configured), click a trace with an
  agent (the children load inline). Each step matched the test
  assertions during local exploration.
