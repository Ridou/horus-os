# Phase 19 Context: Test surface expansion

**Date:** 2026-05-23
**Phase:** 19
**Status:** Audit complete; gap list below

## Domain

Each prior v0.2 phase (12 through 17) added tests for its own surface in
isolation. Phase 19 audits the cross-phase seams and closes the gaps no
single phase owned. Phase 18 added zero tests; the test suite stands at
302 passing.

## Audit findings

The unit shape of every public symbol is already covered. The seams
between surfaces are where coverage thins out.

### Gap A: multi-agent end-to-end through `run_agent_loop`

`make_delegate_tool` has unit tests that stub `run_agent_loop` and
verify the closure shape (`tests/test_delegation.py`). No test wires
`make_delegate_tool` into a registry and calls `run_agent_loop`
end-to-end with a stubbed provider Conversation so a coordinator turn
emits a delegate tool_use, the loop dispatches it, the sub-agent runs
inside the same `run_agent_loop` call, the parent receives the
sub-agent text on the next turn, and the trace tree is readable via
`Database.list_child_traces`. The shared `IterationBudget` only has
counter-level thread-safety tests; running through a real
`run_agent_loop` that drains the shared pool across coordinator and
sub-agent turns is uncovered.

Will close: add `tests/test_e2e_multi_agent.py` with 3 tests.

### Gap B: streaming partial failure and malformed payload

Provider-level streaming tests cover the happy path and the
`ToolCallEvent` emission. None cover the provider raising mid-stream
(network drop, SDK error after the first delta) or the final message
containing a malformed `tool_use` block. The SSE server test covers
error propagation but only when `run_agent_stream` raises before
yielding; the partial-yield-then-raise case (text already streamed,
then an exception) is implicit at the dispatcher level only.

Will close: add `tests/test_streaming_partial_failure.py` with 4
tests covering the Anthropic provider raising mid-stream, an empty
final-message content list, missing `name`/`input` fields on a tool_use
block (defensive defaults), and the SSE endpoint yielding partial text
then surfacing an error frame with the partial text persisted on the
error trace.

### Gap C: adapter contract round-trip through entry-point + webhook

`tests/test_adapters_discovery.py` covers entry-point discovery in
isolation; `tests/test_adapters_webhook.py` covers the reference
webhook adapter mounted directly. No test simulates a third-party
adapter declaring itself via a fake entry point, getting discovered by
`create_app`, accepting an HMAC-signed POST, invoking `run_agent`, and
recording the trace through the full `create_app` pipeline.

Will close: add `tests/test_e2e_adapter_round_trip.py` with 2 tests
(third-party adapter via fake entry point with HMAC route, and the
reference webhook adapter binding through `discover_adapters` rather
than direct `WebhookAdapter().bind(...)`).

### Gap D: CLI `--agent` with `allowed_tools` restriction

`test_run_with_agent_loads_system_prompt` confirms the `system_prompt`
and `default_model` reach the run path. Neither the buffered nor the
streaming run path is tested with a profile that carries a non-None
`allowed_tools` list, even though the buffered path threads the
profile through `run_agent_loop`. Streaming does not take a registry,
so the gap is in the buffered branch only.

Will close: add `tests/test_e2e_cli_agent_scoping.py` with 2 tests
covering the buffered run path receiving the system_prompt + model
plus a registry-side check confirming the profile is forwarded.

### Gap E: SSE + delegate tree composition

Phase 16 tests cover the chat stream and the children route
independently. A test that runs the SSE chat to completion with an
`agent` profile, then queries `/api/agents` and verifies
`last_activity_at` matches the stream's `done.trace_id`, would close a
cross-feature seam.

Will close: add 1 test in `tests/test_e2e_dashboard_composition.py`.

### Gap F: v0.1 database on disk through dashboard

`tests/test_storage.py::test_schema_v1_database_upgrades_to_current`
covers the migration at the SQLite level. No test takes a v0.1-shaped
database, opens it via `create_app`, calls `/api/traces` and
`/api/agents`, and confirms v0.1 traces surface with null
`parent_trace_id`/`agent_profile_name` plus the default profile seeds
on first init.

Will close: add 2 tests in `tests/test_e2e_dashboard_composition.py`
(v0.1 db on disk + dashboard list, v0.1 db on disk + agents seeded).

## Out of scope for Phase 19

- Re-testing surfaces already covered by 12-18.
- Refactoring existing tests for style.
- Live network or real provider/API calls.
- New production code; Phase 19 only adds tests. If a real bug
  surfaces, surface it in the report rather than patching silently.

## Expected delta

12 new tests minimum across 4 new test files. Suite target: 302 + at
least 12 = 314 or more. Lint clean. Full suite must run under 2s.
