---
phase: 34-pricing-table-and-cost-annotation
verified: 2026-05-26T04:02:06Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
---

# Phase 34: Pricing Table and Cost Annotation - Verification Report

**Phase Goal:** Ship `pricing.json` as package data plus `PricingTable` and `CostAnnotator` that turn token counts into USD costs. Cost annotation subscribes BEFORE the persister so each `LLM_CALL` event is mutated in place. Unknown models persist with `pricing_missing=1, cost_usd=NULL`.

**Verified:** 2026-05-26T04:02:06Z
**Status:** PASSED
**Re-verification:** No (initial verification)

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Bundled pricing.json ships current Anthropic + Gemini rates with the four cache-aware per-million fields | VERIFIED | `src/horus_os/observability/pricing.json` has 5 models (claude-sonnet-4-6, claude-opus-4-7, claude-haiku-4-5, gemini-2.5-flash, gemini-2.5-pro) each with provider + 4 rate fields. Verified via `test_pricing_table.py::test_bundled_pricing_loads`. Wheel proof: `unzip -l /tmp/horus-os-verify/*.whl \| grep pricing.json` returned 1 hit at 1132 bytes. |
| 2 | Known-model LLM call (input=1000, output=200, cache_read=500) writes cost_usd=0.006150 (hand-computed) | VERIFIED | Live python execution returned `0.00615` (float-equivalent). `test_known_model_computes_cache_aware_cost` PASSED with `pytest.approx(0.006150, abs=1e-9)`. E2E test `test_e2e_known_model_writes_cost_usd` PASSED — DB row has cost_usd == 0.006150, pricing_missing == 0. |
| 3 | Unknown-model LLM call writes pricing_missing=1, cost_usd IS NULL; never 0 | VERIFIED | `test_unknown_model_sets_null_cost` + `test_unknown_model_explicitly_not_zero` (belt-and-braces `!= 0` + `!= 0.0` + `is None`) PASSED. E2E `test_e2e_unknown_model_writes_null_cost` confirms DB row has cost_usd IS NULL and pricing_missing == 1. ZERO occurrences of `cost_usd == 0` or `cost_usd == 0.0` in any test file. |
| 4 | HORUS_OS_PRICING_PATH env + cfg.pricing_path override the bundled file; override takes precedence | VERIFIED | `Config.pricing_path: Path \| None = None` field present in config.py (line 44). Env wins over TOML wins over None (lines 88-90, 129-130). E2E test `test_e2e_pricing_override_via_env` PASSED — fixture rate (99.99/M) produced cost 0.09999 instead of bundled 3.00/M. Unit-level proof: 3 tests in `test_pricing_override.py` including a no-leak guard. |
| 5 | pricing.json carries version, updated_at, release_version; is_stale boundary pinned at 30 days | VERIFIED | `pricing.json` has `version=1`, `updated_at=2026-05-26`, `release_version=0.4.0`. `test_pricing_staleness.py` PASSED all four tests: 29 days=False, 30 days=False (strict boundary), 31 days=True, 60/90 days correctly returned by updated_at_age_days. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/horus_os/observability/pricing.json` | Bundled per-million USD rates + version/updated_at/release_version | VERIFIED | Exists; valid JSON; 5 seeded models with 4 rate fields each; metadata top-level fields all present |
| `src/horus_os/observability/pricing.py` | PricingTable (load via importlib.resources, get, is_stale, updated_at_age_days) + frozen ModelPricing | VERIFIED | 119 lines; `@dataclass(frozen=True) class ModelPricing` with 5 fields; PricingTable supports `__init__(path=None)` for bundled+override; uses `importlib.resources.files("horus_os.observability").joinpath("pricing.json")` |
| `src/horus_os/observability/cost.py` | CostAnnotator subscribing to ObservationBus, mutating LLMCallEvent in place | VERIFIED | 63 lines; `class CostAnnotator(pricing_table)` with `on_event(event)`. Early-return on non-LLMCallEvent; cache-aware 4-rate formula; sets `cost_usd=None, pricing_missing=True` on unknown |
| `src/horus_os/observability/__init__.py` | Re-exports CostAnnotator, PricingTable, ModelPricing | VERIFIED | All 3 symbols imported and in `__all__` |
| `src/horus_os/config.py` | Config.pricing_path field + HORUS_OS_PRICING_PATH env + [pricing] TOML | VERIFIED | Field added line 44; env override lines 88-90; TOML parse lines 117, 129-130; round-trip in _dump_toml lines 150-151 |
| `src/horus_os/server/api.py` | create_app subscribes CostAnnotator BEFORE SQLitePersister | VERIFIED | Line 128: `_bus.subscribe(CostAnnotator(_pricing_table).on_event)`. Line 129: `_bus.subscribe(SQLitePersister(...).on_event)`. Order correct. |
| `pyproject.toml` | [tool.setuptools.package-data] ships pricing.json | VERIFIED | Line 74: `"horus_os.observability" = ["pricing.json"]`. Diff is exactly +1 line, scoped correctly. |
| 5 test files + tests/test_config.py extension | 32 new tests covering all PRICE-01..05 | VERIFIED | All test files created (test_pricing_table.py 8 tests, test_cost_annotator.py 7, test_cost_annotator_e2e.py 4, test_pricing_override.py 3, test_pricing_staleness.py 4); 6 new pricing tests in test_config.py; 1 assertion update in test_sse_capture.py |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| api.py:create_app | cost.py:CostAnnotator | `_bus.subscribe(CostAnnotator(...).on_event)` BEFORE SQLitePersister | WIRED | api.py lines 128-129; subscribe order pinned by `test_e2e_subscriber_order_annotator_before_persister` which inspects `bus._subscribers` |
| cost.py:CostAnnotator.on_event | pricing.py:PricingTable.get | `self._table.get(event.model)` | WIRED | cost.py line 48 |
| pricing.py:PricingTable.__init__ | pricing.json | `importlib.resources.files("horus_os.observability").joinpath("pricing.json")` | WIRED | pricing.py lines 68-72 |
| config.py:Config.load | Config.pricing_path | `HORUS_OS_PRICING_PATH` env / `[pricing] path` TOML | WIRED | config.py lines 88-90 (env override beats TOML beats None per test_pricing_path_env_beats_toml) |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| CostAnnotator | event.cost_usd | Computed from event token counts × PricingTable rates (real bundled JSON) | YES | FLOWING |
| PricingTable._models | dict[str, ModelPricing] | json.loads(pricing.json) loaded via importlib.resources | YES | FLOWING |
| api.py CostAnnotator subscription | LLMCallEvent mutation | Real bus dispatch chain; ordering before persister proven by e2e test that reads back from sqlite | YES | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Canonical Sonnet cache-aware math returns 0.006150 | python -c (CostAnnotator + LLMCallEvent) | `0.00615` (== 0.006150) | PASS |
| Unknown model returns None | python -c (model='unknown-xyz') | `None`, pricing_missing=True | PASS |
| SSE handoff math returns 0.002596 | python -c (250 in, 120 out, 30 cache_r, 10 cache_w) | `0.002596` | PASS |
| Wheel ships pricing.json | `python -m build --wheel` + `unzip -l \| grep pricing.json` | 1 hit | PASS |
| PricingTable loads bundled 5 models | python -c (from horus_os.observability import PricingTable; sorted keys) | All 5 seeded model names returned | PASS |
| Full pytest suite | `.venv/bin/pytest -q` | 520 passed in 4.31s, 0 failed | PASS |
| ruff check . | `.venv/bin/ruff check .` | All checks passed! | PASS |
| ruff format --check . | `.venv/bin/ruff format --check .` | 116 files already formatted | PASS |
| lint_no_wallclock | `.venv/bin/python scripts/lint_no_wallclock.py` | OK (0 violations) | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| PRICE-01 | 34-01 | Bundled pricing.json shipped as package data; schema mirrors LiteLLM shape | SATISFIED | pricing.json exists with 5 seeded models; wheel-build proof shows it ships at horus_os/observability/pricing.json |
| PRICE-02 | 34-01 | Cost computed per LLM call from token counts × rates (cache_read + cache_creation separate) | SATISFIED | cost.py implements 4-rate formula at lines 53-58; canonical Sonnet test PASSES with hand-computed 0.006150 |
| PRICE-03 | 34-01 | Unknown models persist pricing_missing=1, cost_usd=NULL; NULL is honest | SATISFIED | cost.py lines 49-52; e2e DB-read test confirms NULL in cost_usd column, 1 in pricing_missing column; zero `cost_usd == 0` assertions anywhere |
| PRICE-04 | 34-01 | User can override via env HORUS_OS_PRICING_PATH or config field | SATISFIED | Config.pricing_path field + env-wins-over-TOML precedence; e2e proof env override resolves to fixture rate (0.09999 instead of bundled 0.00615) |
| PRICE-05 | 34-01 | pricing.json carries version, updated_at, release_version; dashboard stale-banner past 30 days | SATISFIED | Top-level fields present; is_stale boundary pinned at 30 days (29=F, 30=F strict, 31=T); updated_at_age_days verified at 60 and 90 |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | - | - | - | No TODO/FIXME/XXX/TBD/PLACEHOLDER markers in any of the 4 new source files |

### Anti-Scope Verification

- `git diff 92175c1..HEAD --name-only` returned 15 files; ALL within allowed scope.
- Anti-scope check: NO matches for `bus.py`, `persist.py`, `agent.py`, `tools/loop.py`, `storage.py`, or `opentelemetry*` in the diff.
- pyproject.toml diff: exactly +1 line (`"horus_os.observability" = ["pricing.json"]`); no new runtime dependencies added.
- api.py diff: exactly the documented 2-line subscribe insertion + 1 import block extension + 1 comment refresh. No other changes.
- test_sse_capture.py diff: exactly 1 assertion swapped (`rollup[1] is None` → `pytest.approx(0.002596, abs=1e-9)`) + 1 import for pytest. Hand-computed value matches the formula for 250 input + 120 output + 30 cache_read + 10 cache_write on claude-sonnet-4-6: (250×3 + 120×15 + 30×0.30 + 10×3.75)/1e6 = 2596.5/1e6 = 0.0025965 → banker's-round 6dp → 0.002596. CORRECT.

### Mutability Proof

- `bus.py` `LLMCallEvent` uses `@dataclass(kw_only=True)` (line 53); NOT frozen. Direct attribute mutation supported. Confirmed by reading bus.py.
- `test_known_model_computes_cache_aware_cost` mutates `event.cost_usd` and `event.pricing_missing` and downstream e2e test reads the mutation back from SQLite — proving the mutation IS visible to SQLitePersister via the bus subscriber chain.

### Subscription Order (Load-Bearing)

- api.py line 128: CostAnnotator subscribe
- api.py line 129: SQLitePersister subscribe
- Order correct (CostAnnotator FIRST).
- `test_e2e_subscriber_order_annotator_before_persister` introspects `bus._subscribers` programmatically and asserts `annotator_idx < persister_idx`. Test PASSED.

### Test Counts

- Before Phase 34: 488 (per Phase 33 SUMMARY claim).
- After Phase 34: **520 passed, 0 failed** — confirmed by live pytest run.
- New tests added: 32 (8 + 7 + 4 + 3 + 4 + 6).
- Matches SUMMARY claim of "520 passed".

### Gaps Summary

None. All 5 success criteria verified by live test execution. All anti-scope constraints respected. Wheel actually ships pricing.json (binary proof). Subscription order is correct (line 128 before line 129) and pinned by a programmatic test. Pitfall 5 NULL-is-honest contract enforced at every layer with belt-and-braces `!= 0` + `!= 0.0` assertions. No `cost_usd == 0` wrong-answer assertions anywhere in the test suite. Hand-computed math values match for both the canonical case (0.006150) and the Phase 33→34 SSE handoff (0.002596 with Python's banker's rounding).

---

## VERIFICATION PASSED

**Score:** 5/5 must-haves verified

**Dimension confirmations:**

- **SC1 (PRICE-01 bundled pricing.json ships in wheel):** PASS. JSON has version=1, updated_at=2026-05-26, release_version=0.4.0, models object with 5 entries (3 Anthropic, 2 Gemini), each with all 4 cache-aware rate fields. Wheel-build proof: 1 hit at `horus_os/observability/pricing.json`.
- **SC2 (PRICE-02 cache-aware math hand-computed):** PASS. `test_known_model_computes_cache_aware_cost` asserts `pytest.approx(0.006150, abs=1e-9)`. Live python execution returns 0.00615 (== 0.006150). Formula in cost.py covers ALL 4 rate fields (input, output, cache_creation×cache_write_per_million, cache_read×cache_read_per_million).
- **SC3 (PRICE-03 unknown model returns NULL, never 0):** PASS. 6 assertions across 2 files (`cost_usd is None` 3×, `pricing_missing is True/== 1` 3×). ZERO `cost_usd == 0` or `cost_usd == 0.0` assertions in the entire tests/ tree.
- **SC4 (PRICE-04 env + config override):** PASS. `Config.pricing_path: Path | None` field exists. Env beats TOML beats None precedence verified. E2E test confirms override path resolves the fixture's 99.99/M rate instead of bundled 3.00/M.
- **SC5 (PRICE-05 staleness substrate):** PASS. Boundary pinned at 29=False, 30=False (strict past), 31=True. `updated_at_age_days` returns correct integer at 60 and 90.

**Test count:** 520 passed, 0 failed (pytest -q completed in 4.31s).

**Lints:** ruff check (clean), ruff format --check (116 files clean), lint_no_wallclock (0 violations).

**Anti-scope:** Clean. No touches to bus.py, persist.py, agent.py, tools/loop.py, storage.py, or opentelemetry files. pyproject.toml diff is +1 line. api.py diff is exactly the documented subscribe-insertion + import + comment refresh. test_sse_capture.py diff is exactly 1 assertion swap with hand-computed expected value.

**Wheel delivery:** `python -m build --wheel` succeeded; `unzip -l *.whl | grep pricing.json` returned 1 hit (`horus_os/observability/pricing.json`, 1132 bytes).

**Subscription order (load-bearing):** CostAnnotator at api.py:128 BEFORE SQLitePersister at api.py:129. Pinned by `test_e2e_subscriber_order_annotator_before_persister` which programmatically inspects `bus._subscribers`.

---

_Verified: 2026-05-26T04:02:06Z_
_Verifier: Claude (gsd-verifier)_
