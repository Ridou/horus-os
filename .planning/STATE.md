---
gsd_state_version: 1.0
milestone: v0.5
milestone_name: Plugin System
status: Phase 42 complete; proceeding to Phase 43
last_updated: "2026-05-26T12:30:00.000Z"
last_activity: 2026-05-26 — Phase 42 shipped (discovery + loading + failure isolation, 33 new tests, 793 total passing)
progress:
  total_phases: 32
  completed_phases: 24
  total_plans: 24
  completed_plans: 24
  percent: 75
---

# Project State

## Project Reference

See: .planning/PROJECT.md and .planning/README.md.

**Core value:** Run a personal team of AI agents on your laptop, with full transparency over every action.
**Current focus:** v0.5 Plugin System milestone — Phases 40, 41, 42 shipped. Next phase: 43 (PermissionGate + CapabilityGuard real enforcement; bounded asyncio.wait_for(start, timeout=2.0); plugin disable short-circuit).

## Current Position

Phase: 43: PermissionGate + CapabilityGuard enforcement
Plan: —
Status: Ready for `/gsd-plan-phase 43`
Last activity: 2026-05-26 — Phase 42 shipped (discovery + loading + failure isolation)

## Prior Milestones

- **v0.1 Foundation** (Phases 01-11): SHIPPED 2026-05-23 as v0.1.0. 175 tests, 3-OS install-smoke green.
- **v0.2 Multi-Agent + Streaming** (Phases 12-21): SHIPPED 2026-05-23 as v0.2.0. 319 tests, 3-OS install-smoke green. Multi-agent runtime, streaming, adapter contract, HMAC webhook reference adapter, dashboard SSE + agents view.
- **v0.3 Adapter Ecosystem** (Phases 22-31): SHIPPED 2026-05-24 as v0.3.0. 447 tests, 3-OS install-smoke green. Adapter lifecycle hooks, Discord + Slack + Email + Calendar adapters, AdapterRegistry, Dashboard Adapters tab, four per-adapter setup guides, four runnable examples, v0.2-to-v0.3 migration guide.
- **v0.4 Observability** (Phases 32-39): SHIPPED 2026-05-26 as v0.4.0. ObservationBus + SQLitePersister, llm_calls + tool_invocations child tables, bundled pricing.json with cache-aware cost annotation, /observability dashboard tab + horus-os usage CLI, opt-in OtelAdapter behind [otel] extra with default-deny content capture + bounded shutdown, scripts/release_gate.py with pricing freshness + two-variant install-smoke matrix.

## v0.5 Plugin System — Milestone Plan

**11 phases (40-50)**, all 39 v0.5 requirements covered at 100%. Execution order:

  40 → 41 → 42 → 43 → (44 ∥ 45) → 46 → 47 → 48 → 49 → 50

**Six load-bearing constraints carried across phases:**

1. `plugins/api.py` is the SINGLE public API surface (Phase 41 defines, Phase 48 lints)
2. Manifest hash drives re-prompt (`grant_hash = sha256(capabilities_set)`, Phase 43)
3. Bounded `asyncio.wait_for(start, timeout=2.0)` matching v0.4 Phase 38 OtelAdapter shape (Phase 43)
4. Two-phase install: `pip download --no-deps` → validate → `pip install --no-deps --no-build-isolation` (Phase 44)
5. v5→v6 additive only: 3 new tables + 2 NULLABLE columns + 1 index (Phase 41, gated again Phase 49)
6. Two new direct deps in base `[project.dependencies]`: `pydantic>=2.7,<3`, `packaging>=24.0` (Phase 41, called out in REL-10)

## Last Activity

2026-05-26, Phase 42 shipped. Discovery + loading + failure isolation substrate landed: `discover_plugins()` (entry_points + filesystem walk with structured DiscoveryError side-channel), `PluginLoader` with rollback-on-error, `PluginRegistry` mirroring AdapterRegistry shape and persisting to Phase 41 plugins + plugin_status tables, `CapabilityGuard` stub (Phase 43 swap site), FastAPI lifespan integration (`app.state.plugin_registry`), and ruff banned-api lint rule for `pkg_resources`. Six requirements complete: DISCOVERY-01, DISCOVERY-02, ISOLATE-01, ISOLATE-04, TEST-18, TEST-19. 33 new tests; suite total 793 passed (760 baseline + 33). Cold-start median 0.056ms vs 100ms threshold. Two commits: a481b0b (modules + ruff ban) and a444045 (lifespan + broken-plugin fixtures).

Prior: 2026-05-26 Phase 41 shipped (manifest schema + public API + persistence migration; 39 new tests, 760 total); 2026-05-26 v0.5 roadmap landed (11 phases 40-50, 100% requirement coverage).
