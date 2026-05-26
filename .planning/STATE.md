---
gsd_state_version: 1.0
milestone: v0.5
milestone_name: Plugin System
status: Phase 46 complete; proceeding to Phase 47
last_updated: "2026-05-26T21:08:00.000Z"
last_activity: 2026-05-26 — Phase 46 shipped (three-tier fixture strategy + 12 pitfall regression test files mapping 1:1 to PITFALLS.md; 42 new tests, 958 total passing in 27s wall clock)
progress:
  total_phases: 32
  completed_phases: 29
  total_plans: 29
  completed_plans: 29
  percent: 91
---

# Project State

## Project Reference

See: .planning/PROJECT.md and .planning/README.md.

**Core value:** Run a personal team of AI agents on your laptop, with full transparency over every action.
**Current focus:** v0.5 Plugin System milestone — Phases 40, 41, 42, 43, 44, 45, 46 shipped. Next phase: 47 (documentation refresh — docs trio).

## Current Position

Phase: 47: Documentation refresh (docs trio)
Plan: —
Status: Ready for `/gsd-plan-phase 47`
Last activity: 2026-05-26 — Phase 46 shipped (three-tier fixture strategy + 12 pitfall regression test files mapping 1:1 to PITFALLS.md; 42 new tests, 958 total passing in 27s wall clock; 8 deviations auto-fixed against plan/production drift)

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

2026-05-26, Phase 44 shipped. Two-phase installer + horus-os plugins CLI subcommand surface landed. `installer.py` exports a 5-phase pipeline (download → validate → grant → install → verify) with rollback and a single `subprocess.run` chokepoint (`grep -c` returns 1). Four refusal gates fire before Phase D ever runs: venv check, sdist refusal, `.pth`-in-RECORD refusal, runtime-dep downgrade refusal. The capability grant prompt enforces INSTALL-05's no-half-grant rule. `update_plugin` classifies upgrades as unchanged/reduced/expanded by set-equality on capability names and routes expansions through `PermissionService.pending_on_upgrade`. `plugins_cmd.py` dispatches 9 subcommands (install/uninstall/list/info/enable/disable/update/grant/revoke). Six requirements complete: INSTALL-01..06. 47 new tests across 10 files; suite total 888 passed (was 841). Installer subset runtime 0.13s (every test mocks `run_pip`; zero real pip invocations in CI per the "real install lands in Phase 49" deferral). Two commits: f31c627 (installer + 7 test files + fixture wheels) and 4cb186d (CLI dispatcher + 3 test files + argparse wiring).

Prior: 2026-05-26 Phase 43 shipped (PermissionGate + CapabilityGuard real enforcement + bounded asyncio.wait_for); 2026-05-26 Phase 42 shipped (discovery + loading + failure isolation); 2026-05-26 Phase 41 shipped (manifest schema + public API + persistence migration); 2026-05-26 v0.5 roadmap landed (11 phases 40-50, 100% requirement coverage).
