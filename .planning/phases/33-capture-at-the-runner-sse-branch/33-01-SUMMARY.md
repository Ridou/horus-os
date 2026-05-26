---
phase: 33-capture-at-the-runner-sse-branch
plan: "01"
subsystem: observability
tags: [capture-sites, runner, sse, pitfall-1, pitfall-2, pitfall-3, pitfall-4, pitfall-9, metric-05, test-12, v0.4]

# Dependency graph
requires:
  - phase: "32-01"  # ObservationBus + SQLitePersister + schema v5 + baseline JSON
provides:
  - "src/horus_os/observability/__init__.py: get_observation_bus() module-level singleton"
  - "src/horus_os/agent.py: run_agent_loop publishes LLMCallEvent per Conversation.send"
  - "src/horus_os/tools/loop.py: _execute_one publishes ObsToolCallEvent on each tool run"
  - "src/horus_os/server/api.py: chat (sync) + chat_stream (SSE) wire trace_id + RunEndEvent end-to-end"
  - "src/horus_os/_providers/_stream_types.py: _StreamUsage terminal sentinel"
  - "src/horus_os/_providers/{_anthropic,_gemini}.py: stream functions yield _StreamUsage"
  - "src/horus_os/storage.py: record_trace accepts optional trace_id kwarg"
  - "scripts/lint_no_wallclock.py: WATCHED_FILES now covers server/api.py"
  - "tests/perf/test_capture_overhead.py: 5-iteration / 3-tool-call benchmark vs v0_3_baseline.json"
  - ".github/workflows/ci.yml: new capture-overhead step on 3-OS x 2-python matrix"

requirements-completed:
  - METRIC-01  # token usage per LLM call (run_agent_loop publishes LLMCallEvent per send)
  - METRIC-02  # tool reliability per call (tools/loop publishes ObsToolCallEvent per _execute_one)
  - METRIC-03  # streaming token capture (SSE branch reads terminal _StreamUsage and persists non-zero tokens; Pitfall 2 fix)
  - METRIC-04  # per-iteration rollup into traces (Pitfall 1 fix via trace_id pre-generation + RunEndEvent after record_trace)
  - METRIC-05  # capture-overhead within 50ms of v0.3 baseline on the 3-OS x 2-python matrix
  - TEST-12    # CI step running the capture-overhead benchmark on every push and PR

# Tech stack
tech-stack:
  added: []
  patterns:
    - "Module-level singleton accessor with test-only reset helper (get_observation_bus / reset_observation_bus_for_tests)"
    - "Caller-owned RunEndEvent: runner publishes per-iteration LLMCallEvents only; caller publishes RunEndEvent AFTER db.record_trace so rollup UPDATE matches"
    - "Terminal _StreamUsage sentinel yielded by streaming generators; SSE handler consumes (never forwards)"
    - "Char-count fallback (max(1, len(text)//4)) so non-empty streams never persist 0 tokens (Pitfall 2)"
    - "Exception CLASS NAME only in error_message column (never str(exc) which leaks user content; Pitfall 9 + T-33-01)"
    - "Optional trace_id keyword on Database.record_trace, run_agent_loop, execute_tool_uses, _execute_one for back-compat"
    - "stdlib-only (no new pyproject.toml dependencies)"

# Key files
key-files:
  created:
    - src/horus_os/_providers/_stream_types.py
    - tests/observability/test_runner_capture.py
    - tests/observability/test_tool_loop_capture.py
    - tests/observability/test_run_end_rollup_integration.py
    - tests/observability/test_sse_capture.py
    - tests/observability/test_pitfall_3_negative_latency.py
    - tests/observability/test_pitfall_9_tool_status_columns.py
    - tests/perf/test_capture_overhead.py
    - .planning/phases/33-capture-at-the-runner-sse-branch/33-01-SUMMARY.md
  modified:
    - src/horus_os/observability/__init__.py
    - src/horus_os/observability/bus.py
    - src/horus_os/agent.py
    - src/horus_os/tools/loop.py
    - src/horus_os/server/api.py
    - src/horus_os/storage.py
    - src/horus_os/_providers/_anthropic.py
    - src/horus_os/_providers/_gemini.py
    - scripts/lint_no_wallclock.py
    - tests/observability/test_bus.py
    - tests/test_lint_no_wallclock.py
    - tests/test_provider_anthropic.py
    - tests/test_provider_gemini.py
    - tests/test_streaming_partial_failure.py
    - .github/workflows/ci.yml

# Metrics
duration: 35m
completed: 2026-05-26
total-tests: 488 passed
commits: 9
---

# Phase 33 Plan 01 Summary: capture at the runner + SSE branch

## What shipped

Nine atomic commits wire the Phase 32 ObservationBus into the live runner. Real agent runs now populate `llm_calls` and `tool_invocations` on every chat call (sync, async, and streaming). `traces.total_input_tokens / total_output_tokens / total_duration_ms` reflect summed totals across all iterations (Pitfall 1 fix). The SSE branch reads terminal usage from a `_StreamUsage` sentinel both providers yield and persists real token counts on streamed runs (Pitfall 2 fix). `cost_usd` stays NULL until Phase 34's CostAnnotator subscribes BEFORE the persister.

| Commit | Type | Title |
|--------|------|-------|
| `c94d2f6` | feat(33) | Task 1: wire ObservationBus singleton + SQLitePersister into create_app |
| `5889ad1` | feat(33) | Task 2: capture LLMCallEvent per iteration in run_agent_loop (Pitfall 1) |
| `44317cd` | feat(33) | Task 3: capture ObsToolCallEvent in tools/loop.py (Pitfall 9 substrate) |
| `1c8caae` | feat(33) | Task 4: wire RunEndEvent into api.py:chat after record_trace (Pitfall 1 fix) |
| `567d2f2` | feat(33) | Task 5: SSE capture via terminal _StreamUsage sentinel (Pitfall 2) |
| `9f969d7` | chore(33) | Task 6: extend lint_no_wallclock to cover server/api.py (Pitfall 3 scope) |
| `7660630` | test(33) | Task 7: Pitfall 3 negative-latency + Pitfall 9 tool column regressions |
| `270cec9` | test(33) | Task 8: capture-overhead benchmark (METRIC-05 / TEST-12) |
| `fcea01c` | chore(33) | Task 9: add capture-overhead benchmark step to CI (TEST-12) |

## Capture-site map

| Capture site | Event type | Source file | Owns trace_id? |
|--------------|-----------|-------------|----------------|
| `run_agent_loop` per-iteration | `LLMCallEvent` | `agent.py` | accepts caller-supplied or auto-generates |
| `_execute_one` per-tool | `observability.bus.ToolCallEvent` (aliased `ObsToolCallEvent`) | `tools/loop.py` | gated on caller-supplied trace_id |
| `api.py:chat` (sync) post-record | `RunEndEvent` | `server/api.py` | pre-generates and threads through |
| `api.py:chat_stream` (SSE) post-stream | `LLMCallEvent` + `RunEndEvent` | `server/api.py` | pre-generates; consumes terminal `_StreamUsage` sentinel |
| `stream_anthropic_async` / `stream_gemini_async` | `_StreamUsage` (private sentinel) | `_providers/_*.py` | n/a (passes through) |

## Requirements satisfied

- **METRIC-01** (token usage per LLM call): Task 2. `run_agent_loop` publishes one `LLMCallEvent` per `Conversation.send` with `input_tokens / output_tokens / cache_creation_input_tokens / cache_read_input_tokens` extracted via `_extract_usage` (Anthropic and Gemini key shapes normalized). Verified by `tests/observability/test_runner_capture.py` (5 tests).
- **METRIC-02** (tool reliability per call): Tasks 3 + 7. `_execute_one` publishes `ObsToolCallEvent` with `status='success'|'error'`, `error_type=ExceptionClass.__name__`, `retry_count=NULL` (SDK does not expose), `output_size=len(str(output).encode('utf-8'))`. Verified by `tests/observability/test_tool_loop_capture.py` (4 tests) + `tests/observability/test_pitfall_9_tool_status_columns.py` (3 tests).
- **METRIC-03** (streaming token capture, Pitfall 2 fix): Task 5. SSE branch consumes `_StreamUsage` sentinel from both providers, normalizes provider keys, and falls back to char-count estimate when terminal usage is empty AND the stream produced text (never persist 0 for a non-empty stream). Verified by `tests/observability/test_sse_capture.py` (5 tests).
- **METRIC-04** (per-iteration rollup into traces, Pitfall 1 fix): Task 4. `api.py:chat` pre-generates trace_id, passes into `run_agent_loop` AND `db.record_trace`, then publishes `RunEndEvent` AFTER `record_trace` so the persister's `_rollup_trace UPDATE` matches the just-inserted row. Verified by `tests/observability/test_run_end_rollup_integration.py::test_three_iteration_rollup` (canonical 3-iteration regression: `traces.total_input_tokens == 300`).
- **METRIC-05** (capture-overhead within 50ms of v0.3 baseline): Tasks 8 + 9. New benchmark exercises full Phase 33 wiring across N=20 samples, compares the median to `tests/perf/v0_3_baseline.json`. On darwin py3.12 the captured median was 1.146ms vs baseline 0.005ms (delta +1.141ms, well within 50ms tolerance). Verified by `tests/perf/test_capture_overhead.py` (2 tests).
- **TEST-12** (CI step for the benchmark): Task 9. New step `capture-overhead benchmark (METRIC-05 / TEST-12)` runs on the 3-OS x 2-python matrix inside `lint-and-test`. Skips when no matching `(os, python)` baseline entry exists so unseeded combos do not block the build.

## ROADMAP Success Criteria

- [x] A real POST /api/chat run with a 3-iteration agent loop writes three rows to `llm_calls` AND `traces.total_input_tokens` equals the sum across iterations (Pitfall 1 fixed). [Task 4 test_three_iteration_rollup + test_api_chat_endpoint_e2e_rollup]
- [x] A real POST /api/chat/stream run extracts terminal `usage` from `MessageStream.get_final_message()` (Anthropic) or `response.usage_metadata` (Gemini) and persists non-zero token counts (Pitfall 2 fixed). When terminal usage is unavailable, the char-count fallback is used; ZERO is never persisted for a non-empty stream. [Task 5 test_sse_anthropic_usage_persisted + test_sse_never_persists_zero_for_nonempty_stream]
- [x] Every `llm_calls` and `tool_invocations` row uses `time.perf_counter()` for `latency_ms`; lint guard watches all four scope paths (observability/, agent.py, tools/loop.py, server/api.py); SQLitePersister still asserts `latency_ms >= 0` and refuses negative inserts. [Tasks 2/3/4/5/6/7; verified by lint_no_wallclock + test_pitfall_3_negative_latency]
- [x] Tool invocation rows persist `status ∈ {success, error}`, `retry_count` NULL with a code comment explaining the SDK limitation, `error_message` carries CLASS NAME ONLY (never `str(exc)` per T-33-01). [Tasks 3 + 7; verified by test_pitfall_9_tool_status_columns]
- [x] CI step `capture-overhead benchmark (METRIC-05 / TEST-12)` runs on the 3-OS x 2-python matrix and asserts within 50ms; skips on unseeded combos. [Tasks 8 + 9]

## Pitfalls guarded

- **Pitfall 1** (per-iteration overwrite undercounting tokens): Fixed structurally by publishing one `LLMCallEvent` per `Conversation.send` (Task 2) AND pre-generating trace_id in the caller so all iterations rollup under one trace (Task 4). Canonical regression test: stubbed 3-iteration run with `usage={input:100, output:50}` per call lands `traces.total_input_tokens == 300` (not 100). The v0.3 bug had landed only the last iteration's value.
- **Pitfall 2** (silent $0 on streamed runs): Fixed by yielding `_StreamUsage` sentinel from both provider streaming generators (Task 5) and reading it in the SSE handler. When terminal usage is unavailable but the stream produced text, fallback to `max(1, len(text)//4)` so non-empty streams never persist `input_tokens=0 AND output_tokens=0`. Canonical regression test: `test_sse_never_persists_zero_for_nonempty_stream`.
- **Pitfall 3** (wall-clock vs perf_counter): Extended `scripts/lint_no_wallclock.py` WATCHED_FILES to cover `server/api.py` (Task 6). All four watched paths (observability/, agent.py, tools/loop.py, server/api.py) use perf_counter. SQLitePersister's `assert event.latency_ms >= 0` from Phase 32 stays live; regression test in `test_pitfall_3_negative_latency.py` proves negative-latency publishes land zero rows.
- **Pitfall 4** (latency_ms contract): Added a NOTE paragraph to `LLMCallEvent` docstring stating latency_ms is wall-clock end to end including SDK retries / backoff / queueing / stream drain, but does NOT include TTFT. A `ttft_ms` column is a future v0.5 consideration and is intentionally NOT a Phase 33 deliverable. Lint guard's triple-quoted exemption keeps this docstring from self-tripping.
- **Pitfall 9** (tool error column shape): `_execute_one` persists `status ∈ {success, error}`, `error_type=ExceptionClass.__name__`, `error_message=ExceptionClass.__name__` (CLASS NAME ONLY, NEVER `str(exc)` which leaks user-supplied paths or content per T-33-01), `retry_count=NULL`. Belt-and-braces guard in `test_pitfall_9_tool_status_columns::test_tool_failure_records_class_name_only` asserts the leaked user path does NOT appear in any column of the persisted row.

## Threat register outcomes

- **T-33-01** (info disclosure via tool_invocations.error_message) — **mitigated**. Tasks 3 + 7. `_execute_one` populates `error_type` and `error_message` with `type(exc).__name__` only. Verified by `test_pitfall_9_tool_status_columns::test_tool_failure_records_class_name_only` which asserts the literal user-supplied path `/Users/santino/secret/path` does NOT appear in any column.
- **T-33-02** (negative latency tampering) — **mitigated**. Tasks 5 + 7. All capture sites wrap `latency_ms` in `max(0, ...)` before publishing; the Phase 32 persister assertion is the final gate. Regression test in `test_pitfall_3_negative_latency.py`.
- **T-33-03** (slow subscriber DoS) — **accepted** per the threat register. Phase 32 already wraps each subscriber call in `try/except BaseException`. Phase 33 only adds publishers; no new subscriber surface.
- **T-33-04** (SSE stream text accumulation) — **accepted** per the threat register. `text_parts` is built locally and persisted into `traces.response_text` (existing column, unchanged). Phase 33 observability events carry token COUNTS only, not content.

## Deviations from plan

1. **[Rule 1 - Bug] Auto-fixed three pre-existing provider tests that pinned the legacy generator shape** (`tests/test_provider_anthropic.py`, `tests/test_provider_gemini.py`, `tests/test_streaming_partial_failure.py`). The Phase 33 `_StreamUsage` terminal sentinel is appended to every provider streaming generator's yield list; tests that asserted `assert items == [...]` against the bare str/event surface now use a `_strip_sentinel` helper. The legacy semantics are preserved; only the helper threads through. Committed inside Task 5 (`567d2f2`).
2. **[Rule 1 - Bug] Fixed a bug in my initial Task 5 test stub** where `_stub_stream_anthropic(raise_after=N)` checked the raise condition BEFORE the yield in the loop, causing `raise_after=1` with `texts=["partial"]` to silently complete without raising. Reordered to raise AFTER the matching yield. Committed inside Task 5.
3. **[Rule 1 - Bug] Fixed a test crash where `PRAGMA table_info` row indices were wrong**. SQLite's `PRAGMA table_info(tool_invocations)` returns rows shaped `(cid, name, type, notnull, dflt_value, pk)`; the column name is at index 1, not 0. Fixed in `test_pitfall_9_tool_status_columns.py` and the test now passes. Committed inside Task 7 (`7660630`).
4. **[Rule 1 - Bug] Adjusted the lint-guard sanity test to write its scratch file UNDER the repo root** so `scripts/lint_no_wallclock.py:main()`'s `relative_to(REPO_ROOT)` does not raise ValueError on a `tmp_path` lying outside the repo. The test cleans up the scratch file in a try/finally. Committed inside Task 6 (`9f969d7`).

No architectural Rule 4 deviations. No new dependencies. No touches to anti-scope files (`observability/persist.py`, `pricing.py`, `pricing.json`, opentelemetry, `pyproject.toml`).

## Authentication gates

None encountered. Tests use stub Conversations and fake API keys.

## Test counts

- Before Phase 33: 459 (per Phase 32 SUMMARY).
- After Phase 33: **488 passed, 0 failed, 0 skipped** (29 new tests across 7 new test files; 3 prior provider tests updated for the `_StreamUsage` sentinel; 1 prior lint test file extended).

| New test file | Test count | Covers |
|---------------|-----------|--------|
| tests/observability/test_runner_capture.py | 5 | Task 2: LLMCallEvent per iteration + provider usage normalization |
| tests/observability/test_tool_loop_capture.py | 4 | Task 3: ObsToolCallEvent per tool + class-name-only contract |
| tests/observability/test_run_end_rollup_integration.py | 3 | Task 4: 3-iteration rollup (Pitfall 1) + e2e /api/chat |
| tests/observability/test_sse_capture.py | 5 | Task 5: SSE terminal usage + Pitfall 2 fallback |
| tests/observability/test_pitfall_3_negative_latency.py | 2 | Task 7: persister still rejects negative latency |
| tests/observability/test_pitfall_9_tool_status_columns.py | 3 | Task 7: tool column shape + class-name-only leak guard |
| tests/perf/test_capture_overhead.py | 2 | Task 8: METRIC-05 baseline compare + schema guard |
| tests/observability/test_bus.py (appended) | +3 | Task 1: singleton + reset + create_app wiring |
| tests/test_lint_no_wallclock.py (appended) | +2 | Task 6: WATCHED_FILES includes api.py + scanner mechanics |

## Out of scope (deliberate)

- **`src/horus_os/observability/persist.py`**: untouched. Phase 32 owns it; Phase 33 only consumes via the bus.
- **`src/horus_os/observability/bus.py` code**: only the LLMCallEvent docstring was extended with the Pitfall 4 NOTE. No class behavior changes.
- **`src/horus_os/storage.py` schema**: only the additive `trace_id` keyword on `record_trace`. SCHEMA_VERSION stays at 5; no migrations.
- **CostAnnotator subscriber + `pricing.json`**: Phase 34's job. `cost_usd` stays NULL on every llm_calls row; the persister's all-or-nothing aggregate keeps `total_cost_usd` NULL on traces (Pitfall 5).
- **`observability/queries.py` + new `/api/observability/*` routes**: Phase 35's job.
- **OpenTelemetry adapter**: Phase 38's job.
- **`pyproject.toml`**: untouched. No new deps.
- **Per-OS baseline entries for linux/win32 and Python 3.11**: capture-overhead benchmark will SKIP on those combos until `scripts/capture_v0_3_baseline.py` is run on each target.

## Process notes

- Full suite green at 488 passed.
- Ruff is clean across the repo (109 files formatted).
- `lint_no_wallclock` is clean across the four watched paths.
- `time.time()` literal does not appear in any watched file. The Pitfall 4 docstring NOTE in `bus.py` names the forbidden literal as `time.time()`; the triple-quoted exemption in the scanner keeps it from self-tripping.
- Anti-scope respected: no touches to `persist.py`, no new dependencies, no schema changes beyond the additive `trace_id` keyword.

## Forward dependencies for Phase 34

- The bus singleton accessor `get_observation_bus()` is the wire Phase 34's CostAnnotator subscribes to. CostAnnotator MUST subscribe BEFORE SQLitePersister (subscribe order is dispatch order per `ObservationBus.publish`).
- `LLMCallEvent.cost_usd` is None on every event Phase 33 publishes; CostAnnotator mutates the event (or publishes an enriched copy) before SQLitePersister sees it.
- `LLMCallEvent.pricing_missing` flips True when CostAnnotator's bundled pricing table has no row for `(provider, model)`.
- All `provider` / `model` fields on LLMCallEvent are populated by Phase 33's `_extract_usage` and `conversation.model`, so CostAnnotator can look up the right pricing row.

## Self-Check

Verified after writing this SUMMARY:

- All nine plan commits exist with the required `feat(33) / test(33) / chore(33)` prefixes.
- All files in the `key-files.created` list above exist on disk under the repo root.
- All files in the `key-files.modified` list above exist on disk under the repo root.
- `pytest -q` exits 0 with 488 passed.
- `ruff check .` exits 0.
- `ruff format --check .` exits 0.
- `python scripts/lint_no_wallclock.py` exits 0.
- No modifications to `.planning/STATE.md` or `.planning/ROADMAP.md` (worktree mode; orchestrator owns those writes after merge-back).
- No touches to anti-scope files (`observability/persist.py`, `pricing.py`, `pricing.json`, opentelemetry, `pyproject.toml`).

## Self-Check: PASSED
