---
gsd_state_version: 1.0
milestone: v0.5
milestone_name: Plugin System
status: planning
last_updated: "2026-05-26T10:20:30.401Z"
last_activity: 2026-05-26
progress:
  total_phases: 11
  completed_phases: 0
  total_plans:
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md and .planning/README.md.

**Core value:** Run a personal team of AI agents on your laptop, with full transparency over every action.
**Current focus:** v0.5 Plugin System milestone — roadmap landed 2026-05-26 with 11 phases (40-50) covering all 39 v0.5 requirements at 100% coverage. Next step: `/gsd-plan-phase 40` to expand the v0.5 baseline artifact phase into a plan.

## Current Position

Phase: 40: v0.5 baseline
Plan: —
Status: Defining plan
Last activity: 2026-05-26 — Roadmap for v0.5 Plugin System landed (Phases 40-50)

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

2026-05-26, v0.5 roadmap landed. 11 phases (40-50) defined with 5 success criteria each, 100% requirement coverage (39/39 v0.5 requirements mapped, zero orphans, zero duplicates). All six load-bearing constraints embedded in the success criteria as verifiable artifacts: literal `timeout=2.0` in Phase 43, literal three-step `pip download → validate → pip install` sequence in Phase 44, literal sentence "plugins execute in the horus-os Python process" in Phase 47's threat model, literal `manifest_version: int` requirement in Phase 41. Phase 44 ∥ Phase 45 is the only legitimate parallelism (mirrors v0.4's 36 ∥ 37). REQUIREMENTS.md traceability section added with 39-row v0.5 mapping table.

Prior: 2026-05-26 Phase 34 shipped (pricing table); 2026-05-26 Phase 38 shipped (OtelAdapter); 2026-05-26 Phase 39 shipped (release gate + docs trio + v0.4.0 tag).
