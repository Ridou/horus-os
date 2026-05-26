---
gsd_state_version: 1.0
milestone: v0.4
milestone_name: observability
status: milestone_complete
last_updated: "2026-05-26T07:23:00.619Z"
last_activity: 2026-05-26, v0.4 Observability milestone shipped (8 of 8 phases). Awaiting maintainer tag + GitHub Release per STOP-BEFORE-TAG.
progress:
  total_phases: 8
  completed_phases: 8
  total_plans: 8
  completed_plans: 8
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md and .planning/README.md.

**Core value:** Run a personal team of AI agents on your laptop, with full transparency over every action.
**Current focus:** v0.4 Observability milestone SHIPPED 2026-05-26. All 8 phases complete (32-39). Release gate green on all 4 checks. Version bumped to 0.4.0 in pyproject.toml + __init__.py. CHANGELOG [0.4.0] section finalized. **Awaiting maintainer to run STOP-BEFORE-TAG block** (`git tag -a v0.4.0` + `git push origin v0.4.0` + `gh release create v0.4.0`) to publish the v0.4.0 tag and GitHub Release.

## Current Position

v0.4 Observability: ALL PHASES COMPLETE
- Phase 32 (schema + persistence + baseline)
- Phase 33 (capture at runner + SSE)
- Phase 34 (pricing + CostAnnotator)
- Phase 35 (queries.py + read APIs)
- Phase 36 (/observability dashboard tab)
- Phase 37 (horus-os usage CLI)
- Phase 38 (OTel adapter)
- Phase 39 (release gate + docs trio + version bump)

Status: Ready for maintainer to ship v0.4.0 (see .planning/phases/39-three-os-gate-release-migration-doc/39-01-SUMMARY.md ## STOP-BEFORE-TAG section).
Last activity: 2026-05-26, release gate ran live with all 4 checks green; wheel built as horus_os-0.4.0-py3-none-any.whl shipping bundled pricing.json; 718 tests passing.

## Prior Milestones

- **v0.1 Foundation** (Phases 01-11): SHIPPED 2026-05-23 as v0.1.0. 175 tests, 3-OS install-smoke green.
- **v0.2 Multi-Agent + Streaming** (Phases 12-21): SHIPPED 2026-05-23 as v0.2.0. 319 tests, 3-OS install-smoke green. Multi-agent runtime, streaming, adapter contract, HMAC webhook reference adapter, dashboard SSE + agents view.
- **v0.3 Adapter Ecosystem** (Phases 22-31): SHIPPED 2026-05-24 as v0.3.0. 447 tests, 3-OS install-smoke green. Adapter lifecycle hooks, Discord + Slack + Email + Calendar adapters, AdapterRegistry, Dashboard Adapters tab, four per-adapter setup guides, four runnable examples, v0.2-to-v0.3 migration guide.

## Last Activity

2026-05-26, Phase 34 (Pricing table and cost annotation) shipped. Verifier passed all 5 ROADMAP success criteria with live evidence (no SUMMARY claims taken on faith); all 5 phase requirements covered (PRICE-01..05). Anti-scope held: zero touches to `bus.py`, `persist.py`, `agent.py`, `tools/loop.py`, `storage.py`, or `opentelemetry`. `pyproject.toml` touch scoped to ONE `[tool.setuptools.package-data]` line. `server/api.py` touch scoped to two-line CostAnnotator subscribe insertion. `tests/observability/test_sse_capture.py` touch scoped to ONE assertion swap (legitimate Phase 33→34 handoff: `rollup[1] is None` → `pytest.approx(0.002596, abs=1e-9)` with hand-computed math).

10 atomic commits (TDD RED/GREEN pairs): `139fcec`+`b4c7f79` Config.pricing_path with env+TOML override; `ca2fe45`+`b54927e` PricingTable + bundled pricing.json + package-data wiring; `6251cab`+`930af42` CostAnnotator cache-aware math; `4567fa7`+`6d1fa7b` wire CostAnnotator BEFORE SQLitePersister in create_app (+ Phase 33 SSE handoff fix); `9902d20` pricing override + staleness banner substrate tests; `15ee714` SUMMARY. Plus `a5e8d29` merge commit and the verifier wrote `34-01-VERIFICATION.md` directly into the phase dir.

Cache-aware math: 4 rates per model (input/output/cache_read/cache_write). Canonical test: `claude-sonnet-4-6` with 1000 input + 200 output + 500 cache_read → `cost_usd == 0.006150` (hand-computed: `(1000*3 + 200*15 + 500*0.30) / 1_000_000`). Pitfall 5 defence-in-depth: NULL-on-unknown asserted at 4 layers (PricingTable.get returns None, CostAnnotator writes None, e2e DB readback is None, all-or-nothing rollup forces traces.total_cost_usd NULL when any contributing row is NULL). Bundled `pricing.json` (1132 bytes) ships in the wheel — proof via `python -m build --wheel` + unzip-grep. Subscriber order pinned programmatically (`test_e2e_subscriber_order_annotator_before_persister` introspects `_bus._subscribers` so future refactor failures are loud). pytest 520 passed (+32 new), ruff clean, lint_no_wallclock clean. Next phase: 35 (query module + read APIs).

Prior: Phase 33 shipped 2026-05-26 (commits `c94d2f6` through `c4b0b6b`); Phase 32 shipped 2026-05-26 (commits `c0d7c6e` through `1cbaf0a`). Note: pre-existing Phase 33 commit SHAs in this STATE were rebased during a separate user commit; current SHAs are `0ddcd13` (Phase 33 state) and `4c6df60` (Phase 33 merge).

10 atomic commits: `c94d2f6` bus singleton + persister wired into create_app; `5889ad1` LLMCallEvent per iteration in run_agent_loop (Pitfall 1); `44317cd` ObsToolCallEvent in tools/loop.py (Pitfall 9 substrate); `1c8caae` RunEndEvent wired into api.py:chat AFTER record_trace (Pitfall 1 caller-side fix); `567d2f2` SSE capture via terminal _StreamUsage sentinel (Pitfall 2); `9f969d7` extend lint_no_wallclock scope to server/api.py; `7660630` Pitfall 3 negative-latency + Pitfall 9 tool column regressions; `270cec9` capture-overhead benchmark (METRIC-05); `fcea01c` capture-overhead CI step on 3-OS matrix (TEST-12); `c4b0b6b` SUMMARY.

ToolCallEvent name-collision handled cleanly (existing `horus_os.types.ToolCallEvent` preserved, observability one imported as `ObsToolCallEvent`). RunEndEvent ownership: caller in api.py publishes AFTER db.record_trace so the rollup UPDATE matches an existing row. Phase 32's correctness-bug fixes (per-iteration token undercount + SSE silent zero) now backed by concrete regression tests. pytest 488 passed (+29 new), ruff clean, lint_no_wallclock clean across 4 watched paths. Next phase: 34 (pricing table and cost annotation).

Prior: 2026-05-26 Phase 32 shipped (commits `c0d7c6e` through `1cbaf0a`).
