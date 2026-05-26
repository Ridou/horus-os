---
gsd_state_version: 1.0
milestone: v0.5
milestone_name: Plugin System
status: Phase 47 complete; proceeding to Phase 48
last_updated: "2026-05-26T22:00:00.000Z"
last_activity: 2026-05-26 — Phase 47 shipped (docs trio + manifest JSON-Schema mirror + 18 docs tests; Pitfall 12 docs-drift gate auto-activated; 977 total passing)
progress:
  total_phases: 33
  completed_phases: 30
  total_plans: 30
  completed_plans: 30
  percent: 91
---

# Project State

## Project Reference

See: .planning/PROJECT.md and .planning/README.md.

**Core value:** Run a personal team of AI agents on your laptop, with full transparency over every action.
**Current focus:** v0.5 Plugin System milestone — Phases 40, 41, 42, 43, 44, 45, 46, 47 shipped. Next phase: 48 (reference plugin — `horus-os-example-plugin`).

## Current Position

Phase: 48: Reference plugin (`horus-os-example-plugin`)
Plan: —
Status: Ready for `/gsd-plan-phase 48`
Last activity: 2026-05-26 — Phase 47 shipped (docs trio + manifest-v1.schema.json + 18 docs tests; Pitfall 12 docs-drift gate auto-activated without test-file edit; 977 total passing in 33s wall clock; REFERENCE-02 + REL-12 complete; zero deviations)

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

2026-05-26, Phase 47 shipped. The v0.5 documentation trio plus the release-gate substrate landed. `docs/PLUGINS.md` (138 lines) ships the 8-section plugin-author guide and embeds `tests/fixtures/manifests/manifest_v1_full.toml` verbatim. `docs/PLUGIN-SECURITY.md` (46 lines, under the 400-line one-sitting-read budget) contains the REL-12 literal sentence "plugins execute in the horus-os Python process" inside a `## Threat model` section, with three further sections (Trust contract, What v0.5 does NOT defend against, Recommended user practices). `docs/MIGRATION-v0.4-to-v0.5.md` (182 lines) mirrors the v0.3→v0.4 shape: TL;DR, What is new, Schema migration v5→v6, New base dependencies, How to roll back, Breaking change scan, Verification (PRAGMA user_version → 6). `docs/manifest-v1.schema.json` is the JSON-Schema mirror; `scripts/build_manifest_schema.py` is the idempotent regenerator (two runs produce no diff). The Phase 46 Pitfall 12 docs-drift test `test_docs_drift_against_committed_schema_file` auto-activated — its `pytest.skip` branch was gated on the docs file's absence, and shipping the file flipped it without any edit to the Phase 46 test file. README gained a "What is new in v0.5" section + three new Documents bullets; CHANGELOG gained a `[0.5.0] - YYYY-MM-DD` draft (date stamp lands in Phase 50). The installer's `render_grant_prompt` (lines 410-423) gained one literal-string write referencing `docs/PLUGIN-SECURITY.md` — existing prompt tests (7 tests) still pass byte-identical. Four new docs-test files land 18 new tests; full suite 977 passed (was 961; delta +16 = 18 new minus 2 pre-existing Pitfall 12 tests already counted). Ruff clean. Two requirements complete: REFERENCE-02 + REL-12. Zero deviations. Two commits: c3f399b (docs + manifest schema + installer link), 5afc54f (README/CHANGELOG + docs tests).

Prior: 2026-05-26, Phase 44 shipped. Two-phase installer + horus-os plugins CLI subcommand surface landed. `installer.py` exports a 5-phase pipeline (download → validate → grant → install → verify) with rollback and a single `subprocess.run` chokepoint (`grep -c` returns 1). Four refusal gates fire before Phase D ever runs: venv check, sdist refusal, `.pth`-in-RECORD refusal, runtime-dep downgrade refusal. The capability grant prompt enforces INSTALL-05's no-half-grant rule. `update_plugin` classifies upgrades as unchanged/reduced/expanded by set-equality on capability names and routes expansions through `PermissionService.pending_on_upgrade`. `plugins_cmd.py` dispatches 9 subcommands (install/uninstall/list/info/enable/disable/update/grant/revoke). Six requirements complete: INSTALL-01..06. 47 new tests across 10 files; suite total 888 passed (was 841). Installer subset runtime 0.13s (every test mocks `run_pip`; zero real pip invocations in CI per the "real install lands in Phase 49" deferral). Two commits: f31c627 (installer + 7 test files + fixture wheels) and 4cb186d (CLI dispatcher + 3 test files + argparse wiring).

Prior: 2026-05-26 Phase 43 shipped (PermissionGate + CapabilityGuard real enforcement + bounded asyncio.wait_for); 2026-05-26 Phase 42 shipped (discovery + loading + failure isolation); 2026-05-26 Phase 41 shipped (manifest schema + public API + persistence migration); 2026-05-26 v0.5 roadmap landed (11 phases 40-50, 100% requirement coverage).
