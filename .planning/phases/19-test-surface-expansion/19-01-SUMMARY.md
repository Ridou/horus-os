# Phase 19 Plan 01 Summary

**Status:** Shipped
**Date:** 2026-05-23
**Requirements:** TEST-04, TEST-05, TEST-06

## What shipped

Five new test files, 16 net new tests, closing the cross-phase seams
no single phase 12-17 plan owned. No production code changed. Suite
went from 302 to 318 passing.

## Files added

| File | Tests | Gap closed |
|------|-------|------------|
| `tests/test_e2e_multi_agent.py` | 3 | A: coordinator -> delegate -> sub-agent -> parent through real run_agent_loop, plus shared budget cap and unknown-sub-agent error continuation |
| `tests/test_streaming_partial_failure.py` | 4 | B: Anthropic stream raising mid-iteration, empty final-message content list, malformed tool_use block with missing name/input, SSE endpoint persisting partial text on error |
| `tests/test_e2e_adapter_round_trip.py` | 3 | C: fake third-party adapter via stubbed entry point + HMAC signed POST + run_agent stub + Database trace through create_app; signature rejection path; live webhook entry-point reachable through create_app |
| `tests/test_e2e_cli_agent_scoping.py` | 2 | D: buffered horus-os run --agent X system_prompt and model forwarding plus the contract that the CLI does not pre-filter the registry by profile allowed_tools |
| `tests/test_e2e_dashboard_composition.py` | 4 | E: SSE chat with agent=X then /api/agents last_activity_at composition. F: v0.1 sqlite on disk + Database.init() migration + /api/traces and /api/agents and /children all work transparently |

## Test count delta

| Surface | Before | After |
|---------|--------|-------|
| e2e_multi_agent | 0 | 3 |
| streaming_partial_failure | 0 | 4 |
| e2e_adapter_round_trip | 0 | 3 |
| e2e_cli_agent_scoping | 0 | 2 |
| e2e_dashboard_composition | 0 | 4 |
| **full suite** | **302** | **318** |

16 net new tests. `python -m pytest -q` reports 318 passed in
~1.55s, still well under the 2s budget.

## Verification

- `python -m pytest -q` -> 318 passed
- `ruff check .` -> clean (one import-sort fix applied via `--fix` to
  two new files, then format pass on three new files)
- `ruff format --check .` -> 69 files already formatted
- grep for unicode dash characters across new tests and the phase
  folder -> no em-dashes or en-dashes
- No production code touched. `git diff main src/` shows zero changes.

## Commits

1. `docs(19): create phase 19 plan and context`
2. `test(19): multi-agent end-to-end coverage through run_agent_loop`
3. `test(19): streaming partial-failure cases`
4. `test(19): adapter contract round-trip through create_app`
5. `test(19): CLI --agent buffered path and registry scoping contract`
6. `test(19): dashboard composition and v0.1 database on disk`
7. `docs(19): summary for plan 19-01`

## Notable design choices

- The multi-agent end-to-end tests monkeypatch
  `horus_os.agent._new_conversation` rather than the per-provider SDK
  modules. This intercepts both the coordinator Conversation and the
  sub-agent Conversation produced inside the delegate handler with one
  patch, and a `_scripted_factory` doles out canned `AgentResult`
  values in the order `run_agent_loop` requests them. The pattern is
  reusable for any future test that needs to script multi-turn
  multi-agent flows without touching real SDKs.
- The fake third-party adapter in `test_e2e_adapter_round_trip.py`
  uses HMAC-SHA256 with a distinct env var (`FAKE_THIRD_PARTY_SECRET`)
  rather than reusing `HORUS_OS_WEBHOOK_SECRET`, so the test is
  isolated from any env that happens to be set when running locally.
- The v0.1-database-on-disk tests call `Database(db_path).init()`
  explicitly before instantiating `create_app`. That mirrors the
  realistic upgrade flow where the user runs `horus-os init` against
  an existing data_dir before opening the dashboard. The dashboard
  routes do not run migrations on their own (deliberate; init is the
  migration surface), so a test that just instantiated `create_app`
  against a raw v1 file would fail with `KeyError: parent_trace_id`
  on the first row read, and that failure mode is documented in the
  init UX.

## Notable / deferred

- Gemini streaming partial-failure was not exercised at the provider
  level. The Anthropic provider has more event surface (text_stream
  context manager + final message inspection) and is the higher-risk
  side. The SSE endpoint test exercises any provider through the
  dispatcher boundary already.
- A v0.2 sub-agent provider override (sub-agent runs on Gemini while
  coordinator runs on Anthropic) is not in scope; Phase 13 deferred
  provider-per-profile to v0.3 by design. The multi-agent tests use
  a single provider end-to-end.
- No new test for the dashboard delegate-tree HTML rendering beyond
  the substring assertions Phase 16 Plan 02 already added. The
  composition test confirms the API contract; the HTML rendering is
  visually verified per Phase 16 Plan 02's notes.
