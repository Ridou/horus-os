---
phase: 28-documentation-and-examples-refresh
plan: "01"
subsystem: docs
tags: [docs, examples, migration, adapters]

requires:
  - phase: "22-01"
  - phase: "23-01"
  - phase: "24-01"
  - phase: "25-01"
  - phase: "26-01"
  - phase: "27-01"
provides:
  - "ARCHITECTURE.md Adapter ecosystem section for v0.3"
  - "examples/discord_adapter.py, slack_adapter.py, email_adapter.py, calendar_adapter.py"
  - "docs/MIGRATION-v0.2-to-v0.3.md"
  - "README.md What is new in v0.3 section + Documents links"
  - "CHANGELOG.md [Unreleased] populated for v0.3"

requirements-completed:
  - REL-06

duration: ~30m (across two execution windows)
completed: 2026-05-24
total-tests: 437
delta-tests: 0
v0.3-progress: Phase 28 of 31 complete (REL-06 done)
---

# Phase 28 Plan 01 Summary: Documentation and examples refresh

## What shipped

The v0.3 documentation pass. REL-06 from `.planning/REQUIREMENTS.md`
lands here: a refreshed `ARCHITECTURE.md`, four runnable adapter
examples, a v0.2-to-v0.3 migration guide, and a README plus
CHANGELOG that link and enumerate everything Phases 22 through 27
shipped.

No `src/` changes. The 437-test surface is byte-identical.

## Files touched

| File | Change |
|------|--------|
| `ARCHITECTURE.md` | Added a new "Adapter ecosystem" section covering `LifecycleAdapter`, `AdapterRegistry`, FastAPI lifespan, `tool_registry`, four shipped adapters, toggle routes, Dashboard tab. Module layout table extended with the four new adapter modules. "What is not in v0.2" renamed to "What is not in v0.3"; shipped items dropped; new v0.3-era deferrals (Socket Mode, OAuth CLI, write-tool merge, soft-disable middleware) added. Test count bumped to 437. |
| `examples/discord_adapter.py` | New. Fakes `discord` module via `sys.modules`, starts the adapter, dispatches a fabricated guild mention through the captured `on_message`. |
| `examples/slack_adapter.py` | New. Fakes `slack_sdk`, binds to a FastAPI app, builds a valid HMAC-SHA256 signature, POSTs through `TestClient`. |
| `examples/email_adapter.py` | New. Fakes `IMAP4_SSL` + `SMTP_SSL`, seeds one unseen RFC 822 message, drives `_poll_once()` directly, shows full RFC 5322 threading headers on the reply. |
| `examples/calendar_adapter.py` | New. Fakes `google.*` and `googleapiclient.*` modules, registers tools onto a real `ToolRegistry`, invokes `list_calendar_events_today`. |
| `examples/README.md` | Four new entries; intro line spans v0.2 and v0.3. |
| `docs/MIGRATION-v0.2-to-v0.3.md` | New. Same shape as `MIGRATION-v0.1-to-v0.2.md`: TL;DR, what is new (Protocol additions, four adapters, optional extras, env vars, server routes, dashboard tab), no schema migration, no deprecations, downgrade, upgrade code samples (LifecycleAdapter sketch, `/api/adapters` query, per-adapter env-var setup). |
| `README.md` | New "What is new in v0.3" section between the v0.2 section and the Documents block. Documents block gains the migration guide and `docs/adapters/`. |
| `CHANGELOG.md` | `[Unreleased]` populated with Added, Changed, Documentation subheadings reflecting every Phase 22 to 27 deliverable. No `[0.3.0]` heading; Phase 31 owns that rotation. |

## Verification

- All four examples exit 0 offline with no SDK installs and no
  network. Each prints the dispatch path plus the registry entry
  state.
- `ruff check .` and `ruff format --check .` clean across the
  whole tree.
- `pytest -q` reports 437 passed, no regressions.
- A repo-wide grep for em-dashes and en-dashes across every
  committed file in this phase returns nothing.
- `CHANGELOG.md` has no `[0.3.0]` heading; `[Unreleased]` is
  non-empty and reflects the full v0.3 surface.

## Commits

1. `docs(28): refresh ARCHITECTURE.md for v0.3`
2. `docs(28): add four adapter example scripts`
3. `docs(28): add v0.2 to v0.3 migration guide`
4. `docs(28): update README and CHANGELOG for v0.3`
5. `docs(28): summary for plan 28-01` (this file)

## Notes

The prior agent had already committed the plan and context as
`8bddb2a` and timed out before the rest. This run finished the
remaining four atomic commits and the summary.

The example scripts deliberately set placeholder env vars in
process so they exercise the same `start` / `bind` code paths a
live operator would hit. Each docstring documents the live-run
env vars and points at the corresponding `docs/adapters/*.md`
setup guide.
