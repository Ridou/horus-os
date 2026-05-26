---
phase: 41-manifest-schema-public-api-persistence-migration
plan: "01"
subsystem: plugin-system-foundation
tags: [plugin-system, manifest, pydantic, packaging, schema-migration, v0.5, MANIFEST, OBSERVE, MIG]

# Dependency graph
requires:
  - phase: "40"  # v0.4 baseline artifact pinned (BASELINE-02)
provides:
  - "src/horus_os/plugins/ (importable package with 5 modules: __init__, spec, capability_catalog, manifest, api)"
  - "src/horus_os/plugins/spec.py (frozen PluginSpec + CapabilityRequest dataclasses)"
  - "src/horus_os/plugins/capability_catalog.py (closed Capability StrEnum + DESCRIPTIONS mapping)"
  - "src/horus_os/plugins/manifest.py (MANIFEST_V1_SCHEMA pydantic v2 + validate_manifest + format_validation_error + compute_manifest_hash)"
  - "src/horus_os/plugins/api.py (single public API surface; 8 names via __all__)"
  - "src/horus_os/storage.py SCHEMA_VERSION = 6 (3 new tables + 2 NULLABLE plugin_name columns + 1 index)"
  - "tests/fixtures/v0_4_database.sqlite3 (v5-pinned fixture for MIG-05 round-trip + Phase 49 release gate)"
  - "scripts/build_v0_4_fixture.py (stdlib-only deterministic fixture regenerator)"
  - "5 horus-plugin.toml fixtures under tests/fixtures/manifests/ (minimum, full, missing_version, unknown_capability, invalid_compat)"

requirements-completed:
  - MANIFEST-01  # required identity fields (manifest_version, name, version, description, author, license, homepage, issue_tracker) + tomllib parser
  - MANIFEST-02  # horus_os_compat as PEP 440 SpecifierSet via packaging
  - MANIFEST-03  # [contributions] declares tools + adapters by dotted-path entry_point
  - MANIFEST-04  # [capabilities] validated against closed Capability StrEnum catalog
  - MANIFEST-05  # pydantic v2 validation + format_validation_error plain-English line shape
  - OBSERVE-01   # plugin_name TEXT NULLABLE on llm_calls + tool_invocations; idx_tool_invocations_plugin
  - MIG-05       # v0.4 -> v0.5 SQLite migration is additive (3 new tables + 2 NULLABLE columns + 1 index); idempotent; v0.4 fixture upgrades byte-identically

# Tech stack
tech-stack:
  added:
    - "pydantic>=2.7,<3 (BaseModel, ConfigDict, Field, HttpUrl, ValidationError, field_validator)"
    - "packaging>=24.0 (packaging.specifiers.SpecifierSet, packaging.version.Version)"
  patterns:
    - "single public API surface via plugins/api.py with sorted __all__ tuple (Pitfall 8)"
    - "closed StrEnum capability catalog with import-time DESCRIPTIONS coverage assertion (Pitfall 1)"
    - "additive-only SQLite migration: ALTER TABLE ADD COLUMN (NULLABLE) wrapped in sqlite3.OperationalError try/except + CREATE INDEX IF NOT EXISTS (Pitfall 9)"
    - "tomllib (stdlib) for manifest parsing — Pitfall: NEVER tomli, NEVER tomlkit"
    - "Pydantic v2 model_config = ConfigDict(extra='ignore') + UserWarning pre-scan for unknown top-level fields (Pitfall 2 forward-compat)"
    - "sha256 over sorted+dedup'd capability set for manifest_hash (capability-order-independent)"
    - "Inlined V5_SCHEMA_SQL constant in scripts/build_v0_4_fixture.py mirrors scripts/build_v0_3_fixture.py shape so the fixture regenerator stays independent of future storage.py refactors"

# Key files
key-files:
  created:
    - src/horus_os/plugins/__init__.py
    - src/horus_os/plugins/spec.py
    - src/horus_os/plugins/capability_catalog.py
    - src/horus_os/plugins/manifest.py
    - src/horus_os/plugins/api.py
    - tests/plugins/__init__.py
    - tests/plugins/test_manifest_schema.py
    - tests/plugins/test_capability_catalog.py
    - tests/plugins/test_api_surface.py
    - tests/plugins/test_manifest_hash.py
    - tests/plugins/test_v5_to_v6_migration.py
    - tests/fixtures/manifests/manifest_v1_minimum.toml
    - tests/fixtures/manifests/manifest_v1_full.toml
    - tests/fixtures/manifests/manifest_v1_missing_version.toml
    - tests/fixtures/manifests/manifest_v1_unknown_capability.toml
    - tests/fixtures/manifests/manifest_v1_invalid_compat.toml
    - tests/fixtures/v0_4_database.sqlite3
    - scripts/build_v0_4_fixture.py
    - .planning/phases/41-manifest-schema-public-api-persistence-migration/41-01-SUMMARY.md
  modified:
    - pyproject.toml             # +pydantic>=2.7,<3 +packaging>=24.0 in [project.dependencies]
    - src/horus_os/storage.py    # SCHEMA_VERSION 5->6; +3 tables; +2 nullable plugin_name cols; +1 index; v5->v6 migration block
    - tests/test_storage.py      # 6 assertions bumped from v5 to v6 (cascade from SCHEMA_VERSION bump)
    - tests/test_e2e_dashboard_composition.py  # v6 assertion (cascade)
    - tests/test_install_smoke.py              # schema_version==6 string match (cascade)
    - scripts/install_smoke.py                 # SCHEMA_VERSION_EXPECTED 5->6 (cascade)

decisions:
  - "plugin_name column lives in SCHEMA_SQL CREATE TABLE for fresh-DB-correctness; ALTER TABLE in v5->v6 block covers the upgrade path (deviation from plan's strict 'ALTER-only' wording; documented below)"
  - "idx_tool_invocations_plugin CREATE INDEX runs unconditionally after the migration block (mirrors how idx_traces_parent_trace_id was wired in v4->v5)"
  - "TOML manifest fixtures place top-level fields (including `capabilities`) BEFORE the `[[contributions.tools]]` array-of-tables to avoid TOML's table-scoping rule that would otherwise put `capabilities` inside the last [[contributions.tools]] table"

# Metrics
duration: ~30m
completed: 2026-05-26
total-tests: 760 passed (39 new: 26 manifest + 13 migration)
commits: 2
---

# Phase 41 Plan 01 Summary: Manifest schema, public API, persistence migration

## One-line description

Lands the foundation substrate for v0.5 plugin system: `PluginSpec` + `MANIFEST_V1_SCHEMA` (pydantic v2) + `plugins/api.py` single public API surface + closed `Capability` StrEnum + additive v5→v6 SQLite migration (3 new tables + 2 NULLABLE `plugin_name` columns + 1 index). Adds `pydantic>=2.7,<3` and `packaging>=24.0` as the first runtime deps horus-os has ever shipped.

## Two atomic commits

1. **`c2ad590`** — `feat(41): plugin manifest schema + public API + capability catalog`
   - pyproject.toml: +pydantic>=2.7,<3 +packaging>=24.0
   - 5 new plugin modules (spec, capability_catalog, manifest, api, __init__)
   - 5 horus-plugin.toml fixtures
   - 4 test files, 26 tests covering MANIFEST-01..05

2. **`5ec57ad`** — `feat(41): v5->v6 plugin schema migration + v0.4 fixture`
   - storage.py: SCHEMA_VERSION = 6; +3 tables; +2 nullable columns; +1 index; v5->v6 migration block
   - scripts/build_v0_4_fixture.py + tests/fixtures/v0_4_database.sqlite3
   - tests/plugins/test_v5_to_v6_migration.py — 13 tests covering MIG-05
   - 4 cascade updates (storage tests + install_smoke + dashboard composition test) bumping SCHEMA_VERSION expectations from 5 to 6

## storage.py v5→v6 line ranges

Mirroring how Phase 32's summary called out the v4→v5 range, here are the v5→v6 landings:

| Change | Lines | Pattern |
|---|---|---|
| `SCHEMA_VERSION = 6` | storage.py:28 | constant bump |
| `plugins` CREATE TABLE | storage.py:135-142 | inside SCHEMA_SQL |
| `plugin_capabilities` CREATE TABLE | storage.py:144-153 | inside SCHEMA_SQL |
| `plugin_status` CREATE TABLE | storage.py:155-162 | inside SCHEMA_SQL |
| `plugin_name TEXT` on llm_calls | storage.py:106 | inside SCHEMA_SQL CREATE TABLE |
| `plugin_name TEXT` on tool_invocations | storage.py:125 | inside SCHEMA_SQL CREATE TABLE |
| v5→v6 ALTER TABLE block | storage.py:245-260 | mirrors v4→v5 block at 226-242 |
| `idx_tool_invocations_plugin` CREATE INDEX | storage.py:269-272 | unconditional, after migration block |

(Exact line numbers may shift slightly with whitespace.)

## Requirements satisfied — one-line per ID

- **MANIFEST-01** — `horus-plugin.toml` declares required identity fields (`manifest_version: int`, `name`, `version`, `description`, `author`, `license`, optional `homepage`, `issue_tracker`). Evidence: `src/horus_os/plugins/manifest.py:MANIFEST_V1_SCHEMA` lists all eight; `tests/plugins/test_manifest_schema.py` exercises minimum + full + missing_version fixtures.
- **MANIFEST-02** — `horus_os_compat` parses via `packaging.specifiers.SpecifierSet`; mismatch yields ValidationError. Evidence: `MANIFEST_V1_SCHEMA._check_compat` field_validator + `manifest_v1_invalid_compat.toml` fixture proves the failure path.
- **MANIFEST-03** — `[contributions]` declares tool + adapter entry points by dotted path. Evidence: `ContributionEntry` BaseModel with `entry_point` regex `^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*(:[A-Za-z_][A-Za-z0-9_]*)?$`; `manifest_v1_full.toml` exercises two tools + two adapters.
- **MANIFEST-04** — `[capabilities]` array entries must be members of the closed `Capability` catalog. Evidence: `_check_capabilities` field_validator + `capability_catalog.py` closed StrEnum + `manifest_v1_unknown_capability.toml` fixture + `test_unknown_capability_in_manifest_payload_is_refused`.
- **MANIFEST-05** — Pydantic v2 validation runs at install + boot; `format_validation_error()` returns line-numbered plain-English errors. Evidence: `format_validation_error()` in manifest.py with `_HUMANIZED_TYPE_MESSAGES` dict; tests assert substring presence for each malformed fixture.
- **OBSERVE-01** — `plugin_name TEXT NULL` on `llm_calls` + `tool_invocations`; index `idx_tool_invocations_plugin(plugin_name, created_at)`. Evidence: storage.py SCHEMA_SQL lists `plugin_name TEXT` on both tables; init() emits the index; `test_new_columns_exist_on_*` asserts shape; `test_new_index_exists` asserts existence.
- **MIG-05** — v0.4 SQLite DBs upgrade to v6 idempotently; additive only; v0.4 fixture loads cleanly; multiple migration runs are a no-op. Evidence: `tests/fixtures/v0_4_database.sqlite3` (schema_version=5); `tests/plugins/test_v5_to_v6_migration.py` covers fixture upgrade + 3 new tables + 2 new columns + new index + Pitfall 9 byte-identical preservation + plugin_name NULL on old rows + idempotent replay + fresh-DB-at-v6 + fresh-equals-upgraded shape + no-DROP/RENAME static check.

## Five new horus-plugin.toml fixtures

| File | Purpose |
|---|---|
| `tests/fixtures/manifests/manifest_v1_minimum.toml` | Minimum-valid shape (Pitfall 2 forward-compat "always loadable" reference) |
| `tests/fixtures/manifests/manifest_v1_full.toml` | Every field exercised — both contributions tables populated, multi-clause `horus_os_compat`, all 4 capabilities, homepage + issue_tracker URLs |
| `tests/fixtures/manifests/manifest_v1_missing_version.toml` | `manifest_version` commented out — must raise ValidationError with "field is required" |
| `tests/fixtures/manifests/manifest_v1_unknown_capability.toml` | `[capabilities]` contains `gpu.cuda_access` — must raise with catalog allowed-values reference |
| `tests/fixtures/manifests/manifest_v1_invalid_compat.toml` | `horus_os_compat = "not-a-spec-set"` — must raise referencing `packaging.SpecifierSet` |

## Five new test files

| File | Test count | What it covers |
|---|---|---|
| `tests/plugins/test_manifest_schema.py` | 11 | MANIFEST-01..05 — passing fixtures, malformed fixtures (parametrized), Pitfall 2 forward-compat UserWarning, manifest_version=2 canonical upgrade message, MANIFEST_VERSION sanity |
| `tests/plugins/test_capability_catalog.py` | 5 | Closed StrEnum guard, DESCRIPTIONS coverage, minimum members present, unknown capability refused at schema-validate time |
| `tests/plugins/test_api_surface.py` | 4 | `__all__` matches the 8 canonical names, every name resolves to non-None, no leading-underscore leak, tuple shape |
| `tests/plugins/test_manifest_hash.py` | 6 | Determinism, order-independence, set-sensitivity, duplicate-tolerance, empty-set, lowercase-hex |
| `tests/plugins/test_v5_to_v6_migration.py` | 13 | MIG-05 — fixture upgrade, new tables + columns + index, Pitfall 9 byte-identical row preservation, plugin_name NULL on old rows, idempotent replay, fresh-DB-at-v6, fresh-equals-upgraded shape, no-DROP/RENAME static check |

Total new tests: **39**.

## Deviations from plan

### 1. plugin_name column lives in SCHEMA_SQL CREATE TABLE for llm_calls + tool_invocations

**Rule 2 deviation (auto-add missing critical functionality).** The plan's `<schema_v6_canonical>` block specifies plugin_name should be added via `ALTER TABLE ADD COLUMN` only, inside the `stored_version < 6` migration block. The plan's mid-task comment "this table predates plugin_name" implied SCHEMA_SQL's CREATE TABLE for llm_calls and tool_invocations should NOT include plugin_name.

Following that wording literally creates a correctness bug: on a fresh database (`stored_version is None`), the migration block is skipped (existing v3→v4 and v4→v5 blocks all gate on `stored_version is not None`), so the column would never be added. The plan's `must_haves.truths` line explicitly contradicts this:

> "Database.init() on a fresh database creates plugins, plugin_capabilities, plugin_status tables AND adds plugin_name nullable column to llm_calls AND tool_invocations AND creates idx_tool_invocations_plugin index"

Resolution: `plugin_name TEXT` lives in SCHEMA_SQL's CREATE TABLE for both tables. The `ALTER TABLE ADD COLUMN` in the migration block handles the v5→v6 upgrade path for existing databases (and is no-op idempotent thanks to the sqlite3.OperationalError swallow). This matches how `traces.parent_trace_id` was wired in v3→v4: present in SCHEMA_SQL AND added via ALTER TABLE on upgrade.

The `idx_tool_invocations_plugin` CREATE INDEX similarly moved outside the version-guarded block to mirror the existing `idx_traces_parent_trace_id` pattern (unconditional, after the migration). Same root cause: a fresh DB needs the index too.

`test_fresh_database_initializes_at_v6` + `test_fresh_database_path_matches_upgraded_database_path` lock in the fix.

### 2. Cascade SCHEMA_VERSION expectations updated in 4 places

**Rule 1 deviation (auto-fix bugs).** Bumping `SCHEMA_VERSION` 5→6 caused 8 test assertions to fail (`assert version == 5`) across 3 test files, plus 2 string-match checks in install_smoke.py and its wrapper test. All updated to expect v6. Not in the plan's stated files-modified list but unavoidable from the SCHEMA_VERSION bump.

### 3. TOML fixture field ordering

Discovered during initial test run: TOML's table-scoping rule means writing

```toml
[[contributions.tools]]
name = "echo"
entry_point = "fixture.mod:echo_tool"

capabilities = ["filesystem.read"]
```

puts `capabilities` inside the last `[[contributions.tools]]` table, NOT at the top level. The fix: all top-level scalars (including `capabilities`) live BEFORE the first `[[contributions.tools]]` or `[[contributions.adapters]]` block. Updated all 5 manifest fixtures + 2 inline TOML payloads in `test_manifest_schema.py`. No semantic change to what the fixtures test; only the layout shifted to satisfy TOML's grammar.

## Authentication gates

None. Pure local infrastructure phase.

## Test counts

- Before Phase 41: 721 passed (per Phase 40 summary).
- After Phase 41: **760 passed, 0 failed, 0 skipped** (39 new tests in `tests/plugins/`).
- `.venv/bin/python -m ruff check src/horus_os/plugins/ tests/plugins/` — All checks passed.
- `.venv/bin/python -m pip install -e .` — clean install with new deps.

## What is NOT yet wired

Phase 41 ships substrate only. The MANIFEST_V1_SCHEMA, PluginSpec, plugins/api.py, and the v6 schema tables are present in the runtime but no code populates them yet. No `/api/plugins` route; no `discover_plugins()`; no `PermissionGate`; the `plugins`, `plugin_capabilities`, `plugin_status` tables stay empty on a fresh install.

- **Phase 42** (`/gsd-plan-phase 42`) wires `plugins/discovery.py` + `plugins/loader.py` + `plugins/registry.py` against the substrate this phase shipped. Consumes `PluginSpec` and `validate_manifest()`; populates the `plugins` table at lifespan startup; surfaces broken plugins as `plugin_status.status='error'` without crashing the host.
- **Phase 43** wires `PermissionGate` + `CapabilityGuard`; the `require_capability` stub in `plugins/api.py` becomes real enforcement. Consumes the `plugin_capabilities` table.
- **Phase 44** wires the install-time grant prompt; consumes `Capability.DESCRIPTIONS` for the user-visible capability text and `format_validation_error()` for surfacing manifest validation failures verbatim.
- **Phase 45** wires `/api/plugins` REST routes + `/plugins` dashboard tab; serializes `PluginSpec` directly. OBSERVE-02 per-plugin cost rollup becomes trivial because `llm_calls.plugin_name` now exists.
- **Phase 48** ships the ruff custom rule enforcing that the reference plugin imports ONLY from `horus_os.plugins.api` (Pitfall 8). The api.py `__all__` tuple is the contract the lint locks in.
- **Phase 49** release gate re-asserts the v0.4 fixture round-trip via `scripts/release_gate.py` (REL-11 part d).

## Forward-looking notes

### Phase 42 (Discovery + loading + failure isolation)

Consumes from this phase:

- **`PluginSpec`** — returned by `discover_plugins()` as `list[PluginSpec]`.
- **`validate_manifest(toml_bytes) -> PluginSpec`** — called on each `horus-plugin.toml` found via entry-points walk or filesystem walk.
- **`plugins` / `plugin_capabilities` / `plugin_status` SQLite tables** — `discover_plugins()` writes plugin discovery results to `plugins`; lifespan startup writes status to `plugin_status` (loaded/error/disabled).
- **`Capability` enum + `DESCRIPTIONS` mapping** — exists but Phase 42 only uses the enum at validate-time; install-prompt rendering lands in Phase 44.

### Phase 43 (PermissionGate + CapabilityGuard)

Consumes:

- **`compute_manifest_hash(capabilities)`** — re-computed on every plugin load and compared against `plugin_capabilities.manifest_hash` to detect capability-set drift (Pitfall 5).
- **`Capability` StrEnum** — `CapabilityGuard` switches on enum members.
- **`require_capability` decorator** — Phase 41 ships the no-op stub; Phase 43 replaces with actual `CapabilityGuard.check_and_raise()` body.

### Phase 49 (Release gate)

Consumes:

- **`tests/fixtures/v0_4_database.sqlite3`** — REL-11 part (d) runs the v0.4 fixture through `Database.init()` and asserts the v6 surface after upgrade. The committed fixture is the input.
- **`scripts/build_v0_4_fixture.py`** — re-runnable for any future schema re-pin scenario (should not happen for v0.4 itself).

## Atomic commit ledger

1. `feat(41): plugin manifest schema + public API + capability catalog`. **`c2ad590`**
2. `feat(41): v5->v6 plugin schema migration + v0.4 fixture`. **`5ec57ad`**

## Self-Check

Verified after writing this SUMMARY:

- All two plan commits exist on local main with the required `feat(41)` prefixes.
- `pyproject.toml` lists `pydantic>=2.7,<3` and `packaging>=24.0` in `[project.dependencies]`.
- `src/horus_os/plugins/` package importable; `horus_os.plugins.api` exposes exactly 8 names.
- `src/horus_os/storage.py` has `SCHEMA_VERSION = 6`; `stored_version < 6` block lives between v4→v5 and the parent_trace_id index; `idx_tool_invocations_plugin` CREATE INDEX lives outside the version guard.
- `tests/fixtures/v0_4_database.sqlite3` exists and is schema_version=5 (`sqlite3 tests/fixtures/v0_4_database.sqlite3 'SELECT version FROM schema_version'` returns `5`).
- `.venv/bin/python -m pytest tests/plugins/ -q` → 39 passed.
- `.venv/bin/python -m pytest -q` → 760 passed, 0 failed.
- `.venv/bin/python -m ruff check src/horus_os/plugins/ tests/plugins/ scripts/build_v0_4_fixture.py` → All checks passed.
- `.venv/bin/python -c "from horus_os.plugins.api import PluginSpec, Capability, Tool, Adapter, LifecycleAdapter, AdapterContext, PluginContext, require_capability; print('ok')"` → `ok`.
- No `DROP` / `RENAME` / `ADD COLUMN NOT NULL` in the v5→v6 block (Pitfall 9).
