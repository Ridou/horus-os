# Phase 18 Plan 01 Summary

**Status:** Shipped
**Date:** 2026-05-23
**Requirements:** MIG-03, REL-04

## What shipped

The v0.2 documentation pass. ARCHITECTURE.md refreshed for the
multi-agent, streaming, and adapter surfaces. Three runnable example
scripts plus an index README under `examples/`. A migration guide
under `docs/`. README and CHANGELOG updated to link the new material
and reflect every phase 12 through 17 deliverable.

### ARCHITECTURE.md refresh

Three new top-level sections: "Multi-agent shape" (AgentProfile,
make_delegate_tool, parent/child traces, shared IterationBudget,
parallel delegation), "Streaming surface" (run_agent_stream,
ToolCallEvent, CLI and dashboard consumption), and "Adapter
interface" (Adapter Protocol, AdapterContext, discover_adapters,
entry-point group, reference WebhookAdapter). Module layout table
gains `tools/delegation.py`, `adapters/base.py`, and
`adapters/webhook.py`. "What is not in v0.1" renamed to "What is not
in v0.2" with a refreshed deferred list (vector search, dashboard
auth, observability, in-stream tool dispatch, Discord/Slack adapters,
webhook replay protection, dashboard profile editing,
provider-per-profile). v0.1 sections (single-agent data flow,
storage shape now at v4, configuration, design principles) preserved.

### Examples

- **`examples/multi_agent.py`**: coordinator delegating to a
  `summarizer` profile via `make_delegate_tool`. Stubs
  `agent.run_agent_loop` for offline runs; prints the resulting
  parent/child trace linkage.
- **`examples/streaming.py`**: `run_agent_stream` consumption.
  Stubs `_anthropic.stream_anthropic_async` to yield text deltas plus
  a `ToolCallEvent`; prints tokens to stdout and tool requests to
  stderr.
- **`examples/custom_adapter.py`**: implementing the `Adapter`
  Protocol. Stubs `adapters_base.entry_points` so the inline
  `HelloAdapter` mounts on `create_app` without a separate package
  install. Walks `app.router.routes` to confirm.
- **`examples/README.md`**: indexes the three scripts, documents the
  run command for each, and notes the stub-to-live-call swap.

All three scripts run cleanly via `python examples/<name>.py` from
the repo root.

### Migration guide

`docs/MIGRATION-v0.1-to-v0.2.md` enumerates the new public API
surface (run_agent_stream, ToolCallEvent, AgentProfile, Adapter,
AdapterContext, IterationBudget, the new Database CRUD methods, the
two new TraceRecord fields, the agents CLI group, the new server
routes, the adapter contract). Documents the v2 -> v3 -> v4 schema
migration as automatic and idempotent. Calls out the single
user-visible behavior change (run streams by default; --no-stream
restores v0.1). Includes code samples for switching `run_agent` to
`run_agent_stream` and for declaring a custom adapter entry point.
States downgrade is one-way and recommends backing up the SQLite
file before upgrading.

### README and CHANGELOG

README Quickstart gained an `agents list` line and a `run --agent
default` line; a new "What is new in v0.2" section between What's
included and Documents links the migration guide, examples, and
roadmap; the Documents block now links the migration guide and
examples.

CHANGELOG `[Unreleased]` rewritten with `### Added`, `### Changed`,
and `### Documentation` subheadings covering every phase 12 through
17 deliverable. Phase 21 owns the `[0.2.0]` heading and the release
tag; that is intentionally not done here.

## Files touched

- `ARCHITECTURE.md` (refresh)
- `examples/multi_agent.py` (new)
- `examples/streaming.py` (new)
- `examples/custom_adapter.py` (new)
- `examples/README.md` (new)
- `docs/MIGRATION-v0.1-to-v0.2.md` (new)
- `README.md` (update)
- `CHANGELOG.md` (update)

## Verification

- `python examples/multi_agent.py` exits 0 and prints the
  coordinator-to-sub-agent response plus the child trace.
- `python examples/streaming.py` exits 0; tokens print to stdout,
  ToolCallEvent prints to stderr.
- `python examples/custom_adapter.py` exits 0 and prints the mounted
  `/api/adapters/hello/ping` route.
- `ruff check .` clean across 64 files.
- `ruff format --check .` clean.
- `python -m pytest -q` reports 302 passed.
- `grep -rn '—\|–' ARCHITECTURE.md README.md CHANGELOG.md docs/ examples/`
  returns nothing.

## Commits

1. `docs(18): create phase 18 plan and context`
2. `docs(18): refresh ARCHITECTURE.md for v0.2`
3. `docs(18): add examples directory with three runnable scripts`
4. `docs(18): add v0.1 to v0.2 migration guide`
5. `docs(18): update README and CHANGELOG for v0.2`
6. `docs(18): summary for plan 18-01`

## Notable / deferred

- The example scripts use the documented monkey-patching pattern
  inline rather than reaching for `pytest.monkeypatch`. This is
  honest: the docstring shows how to revert the stub for a live call,
  and the script does not depend on pytest at runtime.
- The migration guide does not link CHANGELOG entries by line; the
  CHANGELOG `[Unreleased]` block is the canonical list of what
  shipped. Phase 21 will collapse that into a `[0.2.0]` heading.
- `pip install -e .` is required for the reference webhook adapter's
  entry-point test to pass (importlib needs the dist-info metadata).
  This is documented behavior from Phase 17 and not a Phase 18
  concern.
- Out of scope by design: a docsite build, CONTRIBUTING refresh
  beyond what the public surface required, and any new tests. Phase
  19 owns the test surface expansion.
