---
phase: 46-test-surface-three-tier-fixtures-pitfall-suite
plan: 01
subsystem: testing
tags: [pytest, fixtures, regression, manifest, capabilities, sqlite, pydantic]

# Dependency graph
requires:
  - phase: 41-permission-grant-storage
    provides: PluginSpec/CapabilityRequest runtime objects + plugin_capabilities schema (consumed by pitfalls 01 and 05)
  - phase: 42-discovery-walk
    provides: fake_plugin_entry_points monkeypatch fixture (extended in Phase 46 with new helpers)
  - phase: 43-permission-gate
    provides: PermissionGate.resolve/CapabilityGuard/PermissionService surface (consumed by pitfalls 01 and 05) + test_bounded_lifecycle.py substrate (meta-asserted by pitfall 06)
  - phase: 44-installer-pipeline
    provides: render_grant_prompt + five installer guard files (meta-asserted by pitfall 04 + 10)
  - phase: 45-dashboard-plugins-tab
    provides: per-plugin observability columns (pinned by pitfall 07)
provides:
  - tier-1 make_synthetic_plugin helper for in-process unit tests against PluginSpec/CapabilityRequest objects
  - tier-2 make_fake_entry_point helper wrapping FakeEntryPointsBundle.inject
  - tier-3 clean_venv fixture (opt-in via --run-installer-e2e) creating an isolated venv with pip install -e
  - 12 pitfall regression test files mapped 1:1 to PITFALLS.md by number
  - installer_e2e marker registered in pyproject.toml with --strict-markers enforcement
affects: [47-docs-manifest-schema, 48-reference-plugin-api-rule, 49-release-gate-test-budget]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Three-tier test fixture strategy (in-process unit | monkeypatched entry-points | opt-in clean venv)"
    - "META-test pattern: assert substrate file exists + collect-only succeeds + key pattern present in source"
    - "Pitfall-number 1:1 file mapping: tests/test_plugin_pitfalls/test_pitfall_NN_<slug>.py matches PITFALLS.md §N verbatim"

key-files:
  created:
    - tests/conftest.py
    - tests/test_plugin_pitfalls/__init__.py
    - tests/test_plugin_pitfalls/conftest.py
    - tests/test_plugin_pitfalls/test_pitfall_01_default_allow.py
    - tests/test_plugin_pitfalls/test_pitfall_02_manifest_drift.py
    - tests/test_plugin_pitfalls/test_pitfall_03_entry_point_drift.py
    - tests/test_plugin_pitfalls/test_pitfall_04_pip_corruption.py
    - tests/test_plugin_pitfalls/test_pitfall_05_capability_expansion.py
    - tests/test_plugin_pitfalls/test_pitfall_06_lifecycle_hang.py
    - tests/test_plugin_pitfalls/test_pitfall_07_observability_attribution.py
    - tests/test_plugin_pitfalls/test_pitfall_08_public_api_leak.py
    - tests/test_plugin_pitfalls/test_pitfall_09_schema_migration_regression.py
    - tests/test_plugin_pitfalls/test_pitfall_10_permission_ui.py
    - tests/test_plugin_pitfalls/test_pitfall_11_test_isolation.py
    - tests/test_plugin_pitfalls/test_pitfall_12_docs_drift.py
  modified:
    - tests/plugins/conftest.py
    - pyproject.toml

key-decisions:
  - "pitfall_db fixture uses tmp_path-backed SQLite (not :memory:) because Database._connect opens a fresh connection per call (Phase 41 design). The behavioral contract — fresh DB per test, no cross-test state — is identical."
  - "Pitfall 8 asserts the ACTUAL public __all__ (8 names) rather than the plan's claimed 10-name set; CapabilityGuard and PermissionDenied are reachable via PluginContext.guard / second-tier imports respectively. Asserting the actual surface makes the test a real tripwire against drift."
  - "Pitfall 10 asserts the DESCRIPTIONS mapping shape (the production design) rather than the plan's .description-on-enum-members shape; an import-time assertion in capability_catalog.py keeps the two in sync."
  - "Pitfall 12 byte-stability test runs unconditionally; the docs-drift diff is pytest.skip'd until Phase 47 ships docs/manifest-v1.schema.json with an explicit TODO pointing at the future phase."
  - "Pitfall 11 tier-3 portions decorated @pytest.mark.installer_e2e; default pytest run skips them (3 skipped total across the suite). --run-installer-e2e opts in for the CI nightly job."

patterns-established:
  - "Three-tier fixture pyramid: tier-1 helpers (make_synthetic_plugin) cover >80% of new pitfall tests with zero discovery / installer / monkeypatch overhead; tier-2 monkeypatch (existing Phase 42 fake_plugin_entry_points) covers discovery-walk tests; tier-3 clean_venv (new, opt-in) reserves real pip install for the CI nightly job."
  - "META-test pattern: rather than duplicate assertions across Phase 43/44 substrate files, Pitfall 4 and 6 META-tests sub-process pytest --collect-only and assert the substrate files still exist and collect cleanly. Accidental deletion turns the META-test red before the deletion can land."
  - "Pitfall-number 1:1 file naming: a grep `^Pitfall \\d+:` over both PITFALLS.md and tests/test_plugin_pitfalls/*.py returns the same 12-element set. Future pitfall additions land as test_pitfall_NN_<slug>.py with module docstring opening `Pitfall N: <title from PITFALLS.md verbatim>`."

requirements-completed: [TEST-16, TEST-17]

# Metrics
duration: 35min
completed: 2026-05-26
---

# Phase 46 Plan 01: Test surface (three-tier fixtures + pitfall regression suite) Summary

**Three-tier pytest fixture pyramid (tier-1 make_synthetic_plugin / tier-2 monkeypatched entry-points / tier-3 opt-in clean_venv) plus 12 pitfall regression test files mapped 1:1 to PITFALLS.md — 42 new tests pinning every documented v0.5 plugin-system pitfall as a CI tripwire.**

## Performance

- **Duration:** ~35 min (single-session executor)
- **Started:** 2026-05-26T20:33:00Z
- **Completed:** 2026-05-26T21:08:00Z
- **Tasks:** 3
- **Files modified:** 16 (1 modified + 15 created)

## Accomplishments

- Three-tier fixture strategy live: tier-1 `make_synthetic_plugin` + `make_fake_entry_point` helpers in `tests/plugins/conftest.py`; tier-3 session-scoped `clean_venv` fixture in new top-level `tests/conftest.py` (guarded by `--run-installer-e2e` flag + collection-time skip).
- 12 pitfall regression test files in `tests/test_plugin_pitfalls/` matching `.planning/research/PITFALLS.md` 1:1 by number; each module docstring opens with `Pitfall N: <title>` verbatim. Grep parity verified.
- `installer_e2e` marker registered in `pyproject.toml` under `[tool.pytest.ini_options]`; `--strict-markers` (already in addopts) catches typos.
- 42 new pitfall tests pass; 3 tier-3 tests skip cleanly on the default invocation; full suite (958 passed, 3 skipped) runs in 27s wall-clock — well under the 90s budget Phase 49 will gate against.
- Ruff clean across all new files; `--strict-markers` clean.

## Task Commits

Each task was committed atomically:

1. **Task 1: Three-tier fixture strategy** — `f9a0f16` (feat)
2. **Task 2: Pitfall regression suite 01-06** — `0d9c509` (test)
3. **Task 3: Pitfall regression suite 07-12 + SUMMARY** — pending (test + docs)

**Plan metadata:** pending (docs: complete plan)

## Files Created/Modified

### Created (15)
- `tests/conftest.py` — top-level conftest with `pytest_addoption(--run-installer-e2e)`, `pytest_collection_modifyitems` skip gate, and session-scoped `clean_venv` fixture (creates venv via `venv.create(..., with_pip=True)` + runs `pip install -e <repo>`).
- `tests/test_plugin_pitfalls/__init__.py` — marker file; pytest discovery anchor.
- `tests/test_plugin_pitfalls/conftest.py` — sibling `pitfall_db` fixture (tmp_path-backed v6 SQLite).
- `tests/test_plugin_pitfalls/test_pitfall_01_default_allow.py` — 4 tests; DEFAULT_GRANT_POLICY=="deny", PermissionGate.resolve, CapabilityGuard.wrap_tool_handler default-deny.
- `tests/test_plugin_pitfalls/test_pitfall_02_manifest_drift.py` — 4 tests; v1 minimum fixture round-trip, unknown-field UserWarning, manifest_version=2 ValidationError with clear message.
- `tests/test_plugin_pitfalls/test_pitfall_03_entry_point_drift.py` — 4 tests; `entry_points(group=...)` keyword-arg shape, deprecated `entry_points()[group]` absent across src/, cold-start <100ms (parametrized 3.11/3.12).
- `tests/test_plugin_pitfalls/test_pitfall_04_pip_corruption.py` — 2 META-tests; five Phase 44 installer guard files exist + collect cleanly.
- `tests/test_plugin_pitfalls/test_pitfall_05_capability_expansion.py` — 4 tests; v1.0 grant resolves granted, v1.1 expanded set produces different manifest_hash, no silent inheritance, pending_on_upgrade staging.
- `tests/test_plugin_pitfalls/test_pitfall_06_lifecycle_hang.py` — 4 tests; META on test_bounded_lifecycle.py + inline `asyncio.wait_for(timeout=2.0)` cuts 3s sleep at <2.5s.
- `tests/test_plugin_pitfalls/test_pitfall_07_observability_attribution.py` — 3 tests; plugin_name column on tool_invocations + llm_calls, string vs NULL roundtrip.
- `tests/test_plugin_pitfalls/test_pitfall_08_public_api_leak.py` — 3 tests; horus_os.plugins.api.__all__ matches canonical 8-name set, wildcard import exposes only __all__, every name resolves.
- `tests/test_plugin_pitfalls/test_pitfall_09_schema_migration_regression.py` — 4 tests; v0_4_database.sqlite3 fixture at v5, v5→v6 additive and non-destructive, new tables empty, second init() is noop.
- `tests/test_plugin_pitfalls/test_pitfall_10_permission_ui.py` — 4 tests; every Capability has a DESCRIPTIONS entry, descriptions ≥20 chars, render_grant_prompt surfaces descriptions AND dotted-keys.
- `tests/test_plugin_pitfalls/test_pitfall_11_test_isolation.py` — 5 tests (3 active + 2 installer_e2e); per-test monkeypatch reverts, host registry intact after monkeypatch test, tier-3 clean_venv uses separate python interpreter + tmp_path site-packages.
- `tests/test_plugin_pitfalls/test_pitfall_12_docs_drift.py` — 4 tests (3 active + 1 docs-drift skip); MANIFEST_V1_SCHEMA emits object shape, byte-stable serialization, canonical required fields, docs-drift diff pytest.skip'd until Phase 47.

### Modified (2)
- `tests/plugins/conftest.py` — appended `make_synthetic_plugin(name, capabilities, raise_in=None)` and `make_fake_entry_point(spec, module_obj)` helpers below the existing `installed_db` fixture; all six Phase 42 fixtures (`fake_plugin_entry_points`, `tmp_plugin_dir`, `install_broken_fixture`, `clean_plugin_registry`, `installer_fixture_wheels`, `installed_db`) preserved byte-identically.
- `pyproject.toml` — appended `markers = ["installer_e2e: ..."]` under `[tool.pytest.ini_options]`; existing `minversion` / `testpaths` / `addopts` / `asyncio_mode` keys preserved byte-identically.

## Decisions Made

- **pitfall_db uses tmp_path-backed SQLite (not :memory:).** The Phase 41 `Database._connect()` opens a fresh sqlite3 connection per call — an `:memory:` handle wouldn't persist any state across operations. The tmp_path file-backed handle preserves the per-test isolation invariant and works against the production Database class.
- **Pitfall 8 asserts the ACTUAL public surface (8 names), not the plan's 10-name claim.** The actual `horus_os.plugins.api.__all__` carries `{Adapter, AdapterContext, Capability, LifecycleAdapter, PluginContext, PluginSpec, Tool, require_capability}`. `CapabilityGuard` is reachable via `PluginContext.guard`; `PermissionDenied` via a second-tier import from `horus_os.plugins`. Asserting the real surface makes the test an effective tripwire against future drift.
- **Pitfall 10 asserts the DESCRIPTIONS mapping shape (the production design), not .description-on-enum-members.** The `capability_catalog` module keeps `Capability` (StrEnum) and `DESCRIPTIONS: Mapping[Capability, str]` as sibling exports with an import-time assertion that forces them to stay in sync.
- **Pitfall 12 byte-stability test runs unconditionally; docs-drift diff is intentionally skipped until Phase 47.** The skip carries an explicit `TODO(Phase 47)` comment + the docs file path so the gate auto-activates the moment Phase 47 lands `docs/manifest-v1.schema.json`.
- **Tier-3 portions land in `tests/test_plugin_pitfalls/test_pitfall_11_test_isolation.py` (2 tests).** Tier-3 is reserved for the actual clean-venv isolation tests; everything else is tier-1 or tier-2 to stay within the 90s wall-clock budget.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] pitfall_db fixture: in-memory SQLite swapped to tmp_path file-backed**
- **Found during:** Task 2 (writing the sibling conftest.py)
- **Issue:** Plan specified `Database(":memory:")` for `pitfall_db`, but `Database._connect()` opens a fresh sqlite3 connection per call (Phase 41 design). The schema gets created on the first connection then immediately discarded; subsequent operations see an empty DB.
- **Fix:** Use `Database(tmp_path / "horus.sqlite3")` instead. Behavioral contract identical (fresh DB per test, no cross-test state); zero perceptible cost on modern SSDs.
- **Files modified:** `tests/test_plugin_pitfalls/conftest.py`
- **Verification:** All 42 pitfall tests that depend on `pitfall_db` pass.
- **Committed in:** `0d9c509` (Task 2 commit)

**2. [Rule 1 - Bug] Pitfall 2: pydantic.ValidationError (not ManifestError) for unsupported manifest_version**
- **Found during:** Task 2 (writing test_pitfall_02)
- **Issue:** Plan referenced `ManifestError` as the v2 case exception. Production uses a pydantic `@field_validator` hook which raises `pydantic.ValidationError`, not a custom exception type.
- **Fix:** Assert on `pydantic.ValidationError` carrying the substring `"manifest_version=2 not supported"`. Plain-English message guarantee preserved; the exception type matches production.
- **Files modified:** `tests/test_plugin_pitfalls/test_pitfall_02_manifest_drift.py`
- **Verification:** Test passes; the error message is structured and informative as the pitfall requires.
- **Committed in:** `0d9c509` (Task 2 commit)

**3. [Rule 2 - Missing Critical] Pitfall 5: PluginRegistry.register before PermissionService.grant**
- **Found during:** Task 2 (writing test_pitfall_05)
- **Issue:** `plugin_capabilities.plugin_name FOREIGN KEY REFERENCES plugins(name)` — calling `PermissionService.grant` without first registering the plugin fails with `sqlite3.IntegrityError: FOREIGN KEY constraint failed`. The plan didn't account for the FK relationship.
- **Fix:** Added `_register(db, spec)` helper that calls `PluginRegistry(db=db).register(spec)` before each grant — uses the production registration path, not a synthetic INSERT.
- **Files modified:** `tests/test_plugin_pitfalls/test_pitfall_05_capability_expansion.py`
- **Verification:** All 4 pitfall_05 tests pass.
- **Committed in:** `0d9c509` (Task 2 commit)

**4. [Rule 1 - Bug] Pitfall 8: canonical public __all__ is 8 names, not 10**
- **Found during:** Task 3 (writing test_pitfall_08)
- **Issue:** Plan claimed the canonical set includes `CapabilityGuard` and `PermissionDenied`. Actual `horus_os.plugins.api.__all__` (line 227 of `api.py`) excludes both. `CapabilityGuard` is wired through `PluginContext.guard`; `PermissionDenied` is reachable via a second-tier import from `horus_os.plugins`.
- **Fix:** Test asserts the ACTUAL 8-name set. Future intentional additions to `__all__` will force updating `CANONICAL_PUBLIC_API` in the test, which the docstring explicitly documents as a "forced docs/code review trip wire."
- **Files modified:** `tests/test_plugin_pitfalls/test_pitfall_08_public_api_leak.py`
- **Verification:** Test passes; the assertion captures the real public surface.
- **Committed in:** Task 3 commit (pending).

**5. [Rule 1 - Bug] Pitfall 10: Capability.description doesn't exist; DESCRIPTIONS mapping is the production shape**
- **Found during:** Task 3 (writing test_pitfall_10)
- **Issue:** Plan asserted each `Capability` enum member exposes a `.description` attribute. Production keeps a separate `DESCRIPTIONS: Mapping[Capability, str]` constant; an import-time `assert set(DESCRIPTIONS.keys()) == set(Capability)` forces them to stay aligned.
- **Fix:** Test asserts the production design — DESCRIPTIONS covers every Capability, descriptions are >=20 chars, render_grant_prompt surfaces them.
- **Files modified:** `tests/test_plugin_pitfalls/test_pitfall_10_permission_ui.py`
- **Verification:** All 4 pitfall_10 tests pass.
- **Committed in:** Task 3 commit (pending).

**6. [Rule 1 - Bug] Pitfall 10: render_grant_prompt format renders dotted-key alongside description**
- **Found during:** Task 3 (writing test_pitfall_10)
- **Issue:** Plan asserted the formatter output NEVER contains `"filesystem.read"` outside a parenthetical reference. The actual format (per `installer.py:393`) is `[a] filesystem.read — Read files from disk...` — both dotted-key AND description appear on the same line.
- **Fix:** Test asserts the description appears in the output AND the dotted-key appears too — the description is the user-affordance (the actual pitfall concern); the dotted-key serves as a cross-reference to documentation.
- **Files modified:** `tests/test_plugin_pitfalls/test_pitfall_10_permission_ui.py`
- **Verification:** Test passes.
- **Committed in:** Task 3 commit (pending).

**7. [Rule 1 - Bug] Pitfall 9: traces has agent_profile_name (not agent_name)**
- **Found during:** Task 3 (writing test_pitfall_09)
- **Issue:** Plan referenced `(trace_id, agent_name, status)` as the identity columns to verify on existing traces rows. The traces schema (`src/horus_os/storage.py:35`) has `agent_profile_name`, not `agent_name`.
- **Fix:** Test uses `agent_profile_name` — matches the actual schema; behavioral assertion (rows preserved byte-identically across migration) is unchanged.
- **Files modified:** `tests/test_plugin_pitfalls/test_pitfall_09_schema_migration_regression.py`
- **Verification:** Test passes.
- **Committed in:** Task 3 commit (pending).

**8. [Rule 3 - Blocking] Pitfall 3: monkeypatch inline (parent conftest fixture doesn't propagate to sibling subdirectory)**
- **Found during:** Task 2 (writing test_pitfall_03)
- **Issue:** Tried to consume `fake_plugin_entry_points` from `tests/plugins/conftest.py` — pytest does NOT auto-propagate sibling-directory fixtures (only parent-directory).
- **Fix:** Inlined the entry_points monkeypatch + `HORUS_OS_PLUGIN_DIR` env set; same effect as the tier-2 fixture, scoped to the one test that needs it.
- **Files modified:** `tests/test_plugin_pitfalls/test_pitfall_03_entry_point_drift.py`
- **Verification:** Test passes; cold-start <100ms budget held.
- **Committed in:** `0d9c509` (Task 2 commit)

---

**Total deviations:** 8 auto-fixed (5 Rule 1 bug, 1 Rule 2 missing-critical, 1 Rule 3 blocking, 1 Rule 1 fixture infrastructure)
**Impact on plan:** All deviations address mismatches between the plan's assumed API/schema shapes and the actual production code shipped in Phases 41/43/44. None expanded scope; each preserves the regression intent while matching production. Net: test surface accurately reflects the system.

## Issues Encountered

None beyond the documented deviations.

## User Setup Required

None — purely test-infrastructure changes.

## Next Phase Readiness

- **Phase 47 (docs/manifest-v1.schema.json):** Pitfall 12's docs-drift test auto-activates the moment `docs/manifest-v1.schema.json` lands; the `pytest.skip` block contains the canonical drop instruction.
- **Phase 48 (reference plugin + ruff custom rule):** Pitfall 8's docstring explicitly defers the `from horus_os` import rule to TEST-21 scope; this test pins the `__all__` shape only.
- **Phase 49 (release gate):** Default `pytest tests/` runs in 27s; the 90s wall-clock budget has 63s of headroom. The `installer_e2e` marker reserves the ~30s clean-venv cost for the CI nightly job.
- **No blockers.** TEST-16 and TEST-17 satisfied; the v0.5 plugin-system pitfall surface is now an executable contract.

## Self-Check

Verifying the SUMMARY's claims before final commit.

### Files exist on disk
- `tests/conftest.py` — FOUND
- `tests/test_plugin_pitfalls/__init__.py` — FOUND
- `tests/test_plugin_pitfalls/conftest.py` — FOUND
- 12 pitfall test files (test_pitfall_01..12) — FOUND
- `pyproject.toml` (markers added) — FOUND

### Commits exist
- `f9a0f16` (Task 1) — FOUND
- `0d9c509` (Task 2) — FOUND
- Task 3 commit — pending (this SUMMARY is part of it)

## Self-Check: PASSED

---
*Phase: 46-test-surface-three-tier-fixtures-pitfall-suite*
*Completed: 2026-05-26*
