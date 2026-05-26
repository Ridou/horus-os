---
phase: 34-pricing-table-and-cost-annotation
plan: "01"
subsystem: observability
tags: [pricing, cost-annotation, observability, pitfall-5, v0.4]

# Dependency graph
requires:
  - phase: "33-01"  # ObservationBus singleton + SQLitePersister capture sites
provides:
  - "src/horus_os/observability/pricing.json: bundled per-million USD rates for 5 seeded models"
  - "src/horus_os/observability/pricing.py: PricingTable + ModelPricing frozen dataclass"
  - "src/horus_os/observability/cost.py: CostAnnotator subscriber for the ObservationBus"
  - "src/horus_os/observability/__init__.py: PricingTable, ModelPricing, CostAnnotator re-exports"
  - "src/horus_os/config.py: Config.pricing_path field with HORUS_OS_PRICING_PATH + [pricing] TOML override"
  - "src/horus_os/server/api.py: CostAnnotator subscribes BEFORE SQLitePersister in create_app"
  - "pyproject.toml: [tool.setuptools.package-data] ships pricing.json with the wheel"

requirements-completed:
  - PRICE-01  # bundled pricing.json with metadata, ships in the wheel
  - PRICE-02  # cache-aware cost computation via the four-rate Anthropic / Gemini shape
  - PRICE-03  # unknown model lands cost_usd NULL + pricing_missing=1 (Pitfall 5; NULL is honest)
  - PRICE-04  # HORUS_OS_PRICING_PATH env + cfg.pricing_path override the bundled file
  - PRICE-05  # pricing.json carries version + updated_at + release_version; is_stale boundary pinned

# Tech stack
tech-stack:
  added: []
  patterns:
    - "Subscriber chain mutation: CostAnnotator mutates LLMCallEvent in place before SQLitePersister sees it (subscribe order is dispatch order)"
    - "Package-data delivery via [tool.setuptools.package-data] + importlib.resources.files (no string-path file IO at runtime)"
    - "Override precedence: HORUS_OS_PRICING_PATH env beats [pricing] TOML beats None (use bundled)"
    - "Pitfall 5 NULL-is-honest: unknown model writes cost_usd = None (never 0 or 0.0), pricing_missing = 1"
    - "Boundary contract pinned by tests: is_stale at 29 = False, 30 = False (strict past), 31 = True"
    - "stdlib only (json, datetime, pathlib, importlib.resources, dataclasses); no new pyproject.toml dependencies"

# Key files
key-files:
  created:
    - src/horus_os/observability/pricing.json
    - src/horus_os/observability/pricing.py
    - src/horus_os/observability/cost.py
    - tests/observability/test_pricing_table.py
    - tests/observability/test_cost_annotator.py
    - tests/observability/test_cost_annotator_e2e.py
    - tests/observability/test_pricing_override.py
    - tests/observability/test_pricing_staleness.py
    - .planning/phases/34-pricing-table-and-cost-annotation/34-01-SUMMARY.md
  modified:
    - src/horus_os/observability/__init__.py
    - src/horus_os/config.py
    - src/horus_os/server/api.py
    - pyproject.toml
    - tests/test_config.py
    - tests/observability/test_sse_capture.py  # single Rule 1 assertion update (Phase 33 -> 34 handoff)

# Metrics
duration: 45m
completed: 2026-05-26
total-tests: 520 passed
commits: 9
---

# Phase 34 Plan 01 Summary: pricing table and cost annotation

## What shipped

Nine atomic commits ship the bridge between Phase 33's token capture and dollar-denominated cost. Real chat runs now write `cost_usd` to every known-model `llm_calls` row through the cache-aware four-rate formula (input + output + cache_write + cache_read at per-million USD). Unknown models persist with `cost_usd = NULL, pricing_missing = 1` so the dashboard surfaces the gap honestly instead of misreporting a zero. The bundled `pricing.json` ships as wheel package-data; users override via `HORUS_OS_PRICING_PATH` or the `[pricing] path` TOML key. `pricing.json` self-discloses its `updated_at`, `version`, and `release_version` so Phase 36 can render a staleness banner and Phase 39 release CI can refuse stale releases.

NULL is honest. Zero is a lie. Pitfall 5 is now structurally guarded at four layers (PricingTable.get returns None, CostAnnotator writes None, the persister writes NULL through the existing column, and the all-or-nothing rollup from Phase 32 keeps `traces.total_cost_usd` NULL whenever any contributing row is NULL).

| Commit | Type | Title |
|--------|------|-------|
| `139fcec` | test(34-01) | Task 1 RED: failing tests for Config.pricing_path |
| `b4c7f79` | feat(34-01) | Task 1 GREEN: Config.pricing_path field with env + TOML override |
| `ca2fe45` | test(34-01) | Task 2 RED: failing tests for PricingTable + bundled pricing.json |
| `b54927e` | feat(34-01) | Task 2 GREEN: bundle pricing.json + PricingTable + package-data wiring |
| `6251cab` | test(34-01) | Task 3 RED: failing tests for CostAnnotator cache-aware math |
| `930af42` | feat(34-01) | Task 3 GREEN: CostAnnotator subscriber with cache-aware math |
| `4567fa7` | test(34-01) | Task 4 RED: failing e2e tests for CostAnnotator wiring in create_app |
| `6d1fa7b` | feat(34-01) | Task 4 GREEN: wire CostAnnotator BEFORE SQLitePersister in create_app |
| `9902d20` | test(34-01) | Task 5: pricing override + staleness banner substrate tests |

## Requirements satisfied

- **PRICE-01** (bundled pricing.json ships in the wheel): Task 2. Five seeded models (`claude-sonnet-4-6`, `claude-opus-4-7`, `claude-haiku-4-5`, `gemini-2.5-flash`, `gemini-2.5-pro`) each with four per-million USD rates (input, output, cache_write, cache_read) plus a `provider` field; top-level `version=1`, `updated_at=2026-05-26`, `release_version=0.4.0`. Wheel-delivery proof: `python -m build --wheel` then `unzip -l *.whl | grep -c horus_os/observability/pricing.json` returns 1. Verified by `tests/observability/test_pricing_table.py::test_bundled_pricing_loads` + `::test_metadata_fields_present` + `::test_package_data_grep`.
- **PRICE-02** (cache-aware cost computation): Task 3. The canonical Anthropic Sonnet example with `input_tokens=1000, output_tokens=200, cache_read_input_tokens=500, cache_creation_input_tokens=0` produces `cost_usd = (1000*3.00 + 200*15.00 + 500*0.30 + 0*3.75) / 1_000_000 = 0.006150` rounded to 6 decimals. Cache-write tokens are billed at the distinct cache_write rate (Pitfall 5 cache-handling note: cache_creation and cache_read are independent counters; treating them as one undercounts cost). Verified by `tests/observability/test_cost_annotator.py::test_known_model_computes_cache_aware_cost` + `::test_cache_creation_tokens_included` + `::test_rounding_to_6_decimals` and end to end by `tests/observability/test_cost_annotator_e2e.py::test_e2e_known_model_writes_cost_usd`.
- **PRICE-03** (unknown model writes NULL, never 0): Task 3 + Task 5. `PricingTable.get(unknown)` returns `None`. `CostAnnotator.on_event` then sets `event.cost_usd = None` (literal None) and `event.pricing_missing = True`. The persister writes NULL to the cost_usd column; the existing all-or-nothing aggregate in `_rollup_trace` keeps `traces.total_cost_usd` NULL. NULL is honest. Zero is a lie. Pitfall 5. Verified by `tests/observability/test_cost_annotator.py::test_unknown_model_sets_null_cost` + `::test_unknown_model_explicitly_not_zero` (belt-and-braces non-zero guard) and end to end by `tests/observability/test_cost_annotator_e2e.py::test_e2e_unknown_model_writes_null_cost`.
- **PRICE-04** (override-takes-precedence at every layer): Tasks 1 + 4 + 5. `Config.pricing_path` reads `HORUS_OS_PRICING_PATH` env first, then `[pricing] path` from TOML, then None. `create_app` constructs `PricingTable(Config.load(...).pricing_path)` so the override flows into the live bus. Unit-level proof in `tests/observability/test_pricing_override.py` (three tests including a no-leak guard between override and bundled instances). E2E proof in `tests/observability/test_cost_annotator_e2e.py::test_e2e_pricing_override_via_env` (monkeypatched env var resolves to the fixture's 99.99 rate, not the bundled 3.00).
- **PRICE-05** (staleness banner substrate): Task 2 + Task 5. `pricing.json` carries `version`, `updated_at`, `release_version` at the top level. `PricingTable.is_stale(now, threshold_days=30)` boundary contract pinned: 29 days = False, 30 days = False (strictly past), 31 days = True. `updated_at_age_days(now)` returns the exact integer at 60 and 90 days so the Phase 36 dashboard can switch yellow / red on a stable contract. Verified by `tests/observability/test_pricing_table.py::test_is_stale_*` (3 tests) + `tests/observability/test_pricing_staleness.py` (4 tests pinning 29/30/31/60/90).

## ROADMAP Success Criteria

- [x] Bundled `pricing.json` ships with five seeded models (claude-sonnet-4-6, claude-opus-4-7, claude-haiku-4-5, gemini-2.5-flash, gemini-2.5-pro), four-rate cache-aware shape, plus `version` / `updated_at` / `release_version` metadata. Wheel-delivery proof: `unzip -l *.whl | grep horus_os/observability/pricing.json` returns 1. [Task 2]
- [x] A known-model LLM_CALL with `input_tokens=1000, output_tokens=200, cache_read_input_tokens=500` lands `llm_calls.cost_usd == 0.006150` (hand-computed cache-aware sum, 6-decimal rounded). [Task 4 test_e2e_known_model_writes_cost_usd]
- [x] An unknown-model LLM_CALL lands `pricing_missing=1` and `cost_usd IS NULL` (literal Python None, never 0 or 0.0). [Task 4 test_e2e_unknown_model_writes_null_cost; belt-and-braces guard in test_unknown_model_explicitly_not_zero]
- [x] `HORUS_OS_PRICING_PATH` env var and `cfg.pricing_path` config field override the bundled file; e2e test confirms override precedence at the integration layer. [Task 1 + Task 4 test_e2e_pricing_override_via_env]
- [x] `pricing.json` carries `version`, `updated_at`, `release_version`; `PricingTable.is_stale(now, 30)` returns True past 30 days; `updated_at_age_days(now)` returns the exact integer at boundary points (60, 90). [Task 5 test_pricing_staleness.py]

## Pitfalls guarded

- **Pitfall 5** (pricing.json rot, silent zero on unknown): Structurally guarded at four layers. (a) `PricingTable.get(unknown)` returns None, never raises, never falls back to a zero-price block. (b) `CostAnnotator.on_event` writes `event.cost_usd = None` and `event.pricing_missing = True` on unknown models; NULL is honest, zero is a lie. (c) `SQLitePersister._insert_llm_call` writes NULL to the cost_usd column unchanged from Phase 32. (d) The all-or-nothing aggregate in `_rollup_trace` (Phase 32) forces `traces.total_cost_usd` to NULL whenever any contributing `llm_calls.cost_usd` is NULL, so a partial total is never reported. The staleness substrate (`is_stale`, `updated_at_age_days`, `version`, `updated_at`, `release_version`) ships now so Phase 36 can render the dashboard banner and Phase 39 release CI can refuse stale releases without further pricing-layer work.

## Threat register outcomes

- **T-34-01** (user-supplied pricing.json tampering): **accepted** per the register. The override is explicitly user-controlled per PRICE-04; bad JSON raises on `PricingTable.__init__` at boot; the operator owns the override file. No PII, no network surface.
- **T-34-02** (cost-computation info disclosure): **mitigated**. CostAnnotator touches only `event.cost_usd` and `event.pricing_missing`. No prompt or completion content is read; no logging; no exception messages carry token counts.
- **T-34-03** (slow PricingTable lookup DoS): **accepted**. `PricingTable._models` is a dict; `.get(model)` is O(1). Per-event overhead is one dict lookup plus a 4-multiply-add float computation, well under the METRIC-05 budget Phase 33 proved on the 3-OS matrix.
- **T-34-04** (wrong cost from stale pricing.json): **mitigated**. PRICE-05 staleness substrate shipped; the Phase 36 banner and Phase 39 release CI gate will read it.
- **T-34-05** (importlib.resources path traversal): **accepted**. `resources.files("horus_os.observability").joinpath("pricing.json")` takes literal package and filename strings; neither flows from user input. The override path is a typed `Path` on Config, expanded once at boot, used read-only.
- **T-34-06** (cost spoofing on wrong model): **mitigated**. `event.model` is set at the Phase 33 capture site from `conversation.model`; CostAnnotator never invents a model name. Unknown-model fallback writes NULL, never picks a near-match.

## Deviations from plan

1. **[Rule 1 - Bug auto-fix] Updated one assertion in the Phase 33 SSE test** at `tests/observability/test_sse_capture.py::test_sse_anthropic_usage_persisted`. The original assertion was `assert rollup[1] is None  # cost stays NULL until Phase 34`. With CostAnnotator now wired the SSE chat (provider=anthropic, default model=claude-sonnet-4-6) populates cost via the bundled rates: 250 input + 120 output + 30 cache_read + 10 cache_write = `(250*3.00 + 120*15.00 + 30*0.30 + 10*3.75) / 1_000_000 = 0.0025965`, rounded to 6 decimals using Python's banker's rounding = `0.002596`. The plan explicitly anticipated this update at Task 4 acceptance line 359 ("a documented Rule 1 Bug auto-fix"). Committed inside Task 4 (`6d1fa7b`).

No architectural Rule 4 deviations. No new dependencies. No touches to anti-scope files (`observability/persist.py`, `observability/bus.py`, `agent.py`, `tools/loop.py`, `storage.py`, opentelemetry). Only `pyproject.toml` edit is the one-line `[tool.setuptools.package-data]` entry for `horus_os.observability/pricing.json`.

## Authentication gates

None encountered. The e2e chat tests use a fake `ANTHROPIC_API_KEY` plus stubbed Conversation factory; no real API calls leave the test process.

## Test counts

- Before Phase 34: 488 (per Phase 33 SUMMARY).
- After Phase 34: **520 passed, 0 failed, 0 skipped** (32 new tests across 5 new test files; 1 prior assertion in `tests/observability/test_sse_capture.py` updated for the Phase 33 -> Phase 34 cost-handoff; 6 new tests appended to `tests/test_config.py`).

| New test file | Test count | Covers |
|---------------|-----------|--------|
| tests/observability/test_pricing_table.py | 8 | Task 2: bundled load + metadata + is_stale + updated_at_age_days + ModelPricing frozen + package-data grep |
| tests/observability/test_cost_annotator.py | 7 | Task 3: cache-aware math, NULL on unknown (Pitfall 5 belt-and-braces), 6dp rounding, clear-flag-on-known |
| tests/observability/test_cost_annotator_e2e.py | 4 | Task 4: known cost populated, unknown NULL, subscriber order pinned, HORUS_OS_PRICING_PATH override e2e |
| tests/observability/test_pricing_override.py | 3 | Task 5: PRICE-04 unit-level (override + no-leak + annotator-honors-override) |
| tests/observability/test_pricing_staleness.py | 4 | Task 5: PRICE-05 boundary pin (29/30/31 days + 60/90 day arithmetic) |
| tests/test_config.py (appended) | +6 | Task 1: pricing_path default + env + TOML + env-beats-TOML + save-omits + round-trip |

## Out of scope (deliberate)

- **`src/horus_os/observability/persist.py`**: untouched. Phase 32 owns it; Phase 34 only consumes the existing write path (cost_usd column + all-or-nothing aggregate).
- **`src/horus_os/observability/bus.py`**: untouched. `LLMCallEvent` is `kw_only=True` not frozen, so direct attribute mutation works as Phase 32 designed for this exact subscriber pattern.
- **`src/horus_os/agent.py` and `src/horus_os/tools/loop.py`**: untouched. The runner publishes events; Phase 34's annotator subscribes between the publisher and the persister, but the runner does not know the annotator exists (loose coupling through the bus).
- **`src/horus_os/storage.py`**: untouched. Schema v5 already added `llm_calls.cost_usd` (REAL nullable) and `llm_calls.pricing_missing` (INTEGER NOT NULL DEFAULT 0) in Phase 32. No new migrations.
- **`observability/queries.py` + new `/api/observability/*` routes**: Phase 35's job. Phase 34 lands the cost data; Phase 35 ships the SQL that aggregates it.
- **Phase 36 dashboard banner**: PRICE-05 substrate is shipped here (`is_stale`, `updated_at_age_days`, `version`, `updated_at`, `release_version`); the banner UI lands in Phase 36.
- **CLI `horus-os usage`**: Phase 37's job.
- **OpenTelemetry adapter**: Phase 38's job.
- **Phase 39 release CI gate** that fails on `is_stale > 14 days`: the substrate is here; the CI gate is Phase 39.
- **New runtime deps**: none. stdlib only.

## Forward dependencies for Phase 35

- `llm_calls.cost_usd` is now populated for every known-model row. Phase 35's `observability/queries.py` can `SELECT SUM(cost_usd) FROM llm_calls WHERE created_at >= ?` and trust the result for the non-NULL fraction. Use `COALESCE(cost_usd, 0)` only when joining for display; never overwrite NULL to zero before storage.
- `llm_calls.pricing_missing` is now a reliable signal for the "runs with unknown pricing" yellow-badge query Phase 36 will render.
- `traces.total_cost_usd` is honest: populated when every contributing row has a cost, NULL when any row is missing. Phase 35's per-trace cost endpoint can return the field verbatim with the right docstring.
- `PricingTable.is_stale(now, threshold_days)` is the boolean Phase 36's banner reads at threshold 30. `updated_at_age_days(now)` is the integer Phase 36 switches color on at 60 and 90.
- `HORUS_OS_PRICING_PATH` env var and `[pricing]` TOML key are the override surface documented for Phase 37's CLI help text and Phase 36's dashboard footer.

## Self-Check

Verified after writing this SUMMARY:

- All nine plan commits exist with the required `test(34-01)` / `feat(34-01)` prefixes.
- All files in `key-files.created` exist under the repo root.
- All files in `key-files.modified` exist under the repo root.
- `pytest -q` exits 0 with 520 passed.
- `ruff check .` exits 0 (116 files clean).
- `ruff format --check .` exits 0 (116 files formatted).
- `python scripts/lint_no_wallclock.py` exits 0.
- Wheel-delivery proof: `python -m build --wheel --outdir /tmp/horus-os-w34` then `unzip -l /tmp/horus-os-w34/*.whl | grep -c "horus_os/observability/pricing.json"` returns 1.
- Subscriber order in `src/horus_os/server/api.py`: CostAnnotator subscribe at line 128, SQLitePersister subscribe at line 129 (annotator first).
- No modifications to `.planning/STATE.md` or `.planning/ROADMAP.md` (worktree mode; orchestrator owns those writes after merge-back).
- No touches to anti-scope files: `git diff --name-only main..HEAD | grep -E "(bus\.py|persist\.py|^src/horus_os/agent\.py|tools/loop\.py|storage\.py|opentelemetry)" | wc -l` returns 0.

## Self-Check: PASSED
