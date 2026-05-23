# Phase 16 Plan 01 Summary

**Status:** Shipped
**Commit:** feat(16): SSE chat stream, agents CRUD, trace children routes
**Date:** 2026-05-23

## What shipped

The full backend contract for the v0.2 multi-agent dashboard, all
behind the existing `create_app(data_dir)` factory. The frontend
(Plan 02) consumes this surface without any further server changes.

### New endpoints

| Method | Path | Behavior |
|--------|------|----------|
| GET    | /api/agents | List all profiles with `last_activity_at` |
| GET    | /api/agents/{name} | Show one profile or 404 |
| POST   | /api/agents | Create, 409 on duplicate, 400 on missing fields |
| PATCH  | /api/agents/{name} | Update only supplied fields, 404 on missing |
| DELETE | /api/agents/{name} | 204 on success, 404 on missing |
| GET    | /api/traces/{id}/children | Child traces oldest first |
| POST   | /api/chat/stream | SSE stream of token / tool_call / done / error frames |

### Behavior locked in

- The SSE event shape is JSON-typed, not raw token text. Each frame is
  `data: <json>\n\n` with a `type` discriminator. Token frames carry
  `text`; tool_call frames carry `name` and `input`; done frames carry
  `trace_id` and `latency_ms`; error frames carry `message` and the
  partial-text trace_id. This avoids ambiguity when a token contains
  the delimiter and lets the frontend dispatch on a single channel.
- Provider failures inside the async generator emit exactly one error
  frame and no done frame. A status=error trace lands server-side with
  the partial text already streamed. The HTTP status stays 200 because
  the response body was already in flight; the type=error frame is the
  client's failure signal.
- 4xx and 503 errors are returned BEFORE the stream opens (missing
  prompt, missing API key, unknown provider, unknown agent profile).
- `last_activity_at` on the agents list is a per-row scalar
  `MAX(created_at) FROM traces WHERE agent_profile_name = ?`. Profiles
  with no matching trace report null. v0.1 profiles match nothing
  because no v0.1 trace carries an `agent_profile_name`.
- PATCH semantics mirror the CLI: only fields present in the JSON body
  are touched. `allowed_tools: null` clears restrictions; omitted
  means unchanged.
- `_trace_to_dict` already calls `dataclasses.asdict` on TraceRecord,
  so `parent_trace_id` and `agent_profile_name` flow through every
  trace endpoint automatically. v0.1 rows surface both as null.

## Files touched

- `src/horus_os/server/api.py`: added imports for json,
  StreamingResponse, Response, AsyncGenerator, AgentProfile, and
  ToolCallEvent. Registered five agents routes, the trace children
  route, and `/api/chat/stream`. Added `_profile_to_dict`,
  `_last_activity_for`, and `_sse` module-level helpers.
- `tests/test_server_agents.py` (new): 15 tests covering list, show,
  create, edit, delete, last_activity_at, duplicate-create,
  unknown-name 404s, and 400 on malformed bodies.
- `tests/test_server_stream.py` (new): 9 tests covering happy-path
  token frames, tool_call emission, error-mid-stream, missing-prompt
  400, missing-db 503, missing-key 503, unknown-provider 400,
  unknown-agent 404, and agent profile forwarding plus user-model
  precedence.
- `tests/test_server_api.py`: 5 added cases covering the enriched
  `/api/traces/{id}` payload (parent_trace_id and agent_profile_name
  null vs. populated) and the new `/children` route (oldest-first
  ordering, empty list, 503 when DB missing). Existing 12 cases
  unchanged.

## Test count delta

| Surface | Before | After |
|---------|--------|-------|
| server_agents | 0 | 15 |
| server_stream | 0 | 9 |
| server_api | 12 | 17 |
| **full suite** | **246** | **275** |

29 net new tests. `python -m pytest -q` reports 275 passed in 1.16s.

## Lint status

`ruff check .` clean. `ruff format --check .` clean across 55 files
after one auto-format pass on the new test files.

## Notable / deferred

- The SSE `done` frame intentionally does not echo provider/model. The
  client computes the meta line from the request side; pushing the
  echo into the protocol would make the contract noisier without
  meaningful gain.
- `_last_activity_for` reaches into `Database._connect()` directly
  rather than adding a new public method. A future
  `Database.last_trace_for_profile` is fair game if a second consumer
  appears.
- FastAPI requires `response_class=Response` on the 204 DELETE route
  to suppress automatic body generation. The pattern is documented in
  the route definition for the next person.
- The agents routes accept and emit JSON payloads only. No web form
  shape (multipart, urlencoded). The CLI from Plan 15 remains the
  canonical write surface for users; the JSON API is for the
  dashboard and any future programmatic clients.
