# Phase 15 Plan 02 Summary

**Status:** Shipped
**Commit:** feat(15): run streams by default, --agent and --no-stream flags
**Date:** 2026-05-23

## What shipped

`horus-os run <prompt>` now streams tokens to stdout by default by
consuming the Phase 14 `run_agent_stream` async generator. The
`--no-stream` flag falls back to the v0.1 buffered output unchanged.
`--agent <name>` loads a profile via `Database.load_profile` and threads
its `system_prompt` and `default_model` through whichever path the user
picks. STREAM-02 closes and the MA-01 run-side edge ("run against the
named profile") lands together with Plan 01's agents CRUD.

### Streaming output contract

- `stdout.write(chunk)` + `stdout.flush()` per `str` token. `StringIO`
  treats `flush()` as a no-op, so tests use the same harness as the
  buffered path with no special handling.
- Trailing summary line on the streaming path:
  `\n\n[{provider}/{model}, {latency_ms}ms, streamed]\n`.
- `ToolCallEvent` items surface on stderr as
  `[tool-request] {name}({input})` and do not pollute the response body
  on stdout. Tool dispatch remains the responsibility of
  `run_agent_loop`, matching the Phase 14 contract.

### Profile precedence

```
model = args.model
        or (profile.default_model if profile else None)
        or _model_for(config, provider)
```

User-supplied `--model` always wins. Profile default wins over config
default. Pitfall 4 from the research file (silent profile clobber) is
mitigated.

### Trace recording

Both paths call `Database.record_trace` unless `--no-record` is set.
The streaming path:

- On success, records `AgentResult(text="".join(text_parts), ...)`
  with `latency_ms`, `agent_profile_name=agent_name` (NULL when
  `--agent` was not used).
- On exception, records the same shape with `status="error"`,
  `error_message=...`, and the partial text accumulated so far. Pitfall
  3 from the research file is mitigated.

### Error paths

- `--agent ghost` returns 1 with `No agent profile named 'ghost'.` to
  stderr before any provider call.
- Streaming exception returns 1 with `Agent run failed: ...` to stderr,
  partial text preserved on the error trace.

## Files touched

- `src/horus_os/cli/run_cmd.py`: refactored `run_run` into a thin
  router plus `_run_buffered` and `_run_streaming` branches; added
  `_consume_stream` async helper; imports `asyncio`,
  `run_agent_stream`, and `ToolCallEvent`.
- `src/horus_os/__main__.py`: added `--agent` and `--no-stream` flags
  to the existing `run` subparser. No flag removed; all v0.1 flags
  preserved.
- `tests/test_cli_run.py`:
  - Existing buffered tests opt into `--no-stream` so the new default
    does not flip their semantics. Buffered fakes also accept
    `system_prompt=` now that `run_agent_loop` receives it.
  - Eight new tests cover streaming default, `--no-stream` fallback,
    `--agent` profile load (system_prompt + default model), `--model`
    precedence over profile, unknown-agent error, streaming error
    trace, streaming `--no-record`, and `ToolCallEvent` stderr
    surfacing.

## Test count delta

| Surface | Before | After |
|---------|--------|-------|
| cli_run | 7 | 16 (existing tests updated, plus 8 new + 1 surfaces ToolCallEvent) |
| **full suite (post-15-01 baseline)** | **238** | **246** |

All green: `python -m pytest -q` reports 246 passed in 0.89s.

## Lint status

`ruff check .` clean. `ruff format --check .` clean across 53 files
after a single `ruff format` pass on the modified test file.

## Notable / deferred

- The `--no-stream` flag is required, not implicit. The plan considered
  auto-detecting whether stdout is a TTY but decided against it: tests
  pass `StringIO` (not a TTY) and would silently switch paths,
  obscuring which branch is actually being verified. Explicit flag
  keeps the surface predictable.
- `ToolCallEvent` flows to stderr as a notification only. Tool
  execution inside the streaming path is intentionally deferred (and
  per Phase 14 contract, may never land here; that is what
  `run_agent_loop` exists for). Callers who need tool execution use
  `--no-stream`.
- `--agent` accepts profile names with no shell quoting magic.
  Validation is "name resolves via `load_profile`"; no regex gate, no
  reserved-name list. The Phase 12 upsert semantics protect against
  silent corruption.
- The buffered path now passes `system_prompt=` to `run_agent_loop`.
  `run_agent_loop` already accepted this kwarg (Phase 13), so this is
  wiring not new surface.
- `--no-record` continues to suppress trace recording on both paths.
