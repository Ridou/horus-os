---
phase: 43-permission-model-bounded-lifecycle
plan: 01
subsystem: plugins
tags: [permissions, default-deny, capabilities, lifecycle, asyncio, sqlite, audit-log]

# Dependency graph
requires:
  - phase: 41
    provides: PluginSpec, MANIFEST_V1_SCHEMA, v6 plugin_capabilities table, capability_catalog closed enum
  - phase: 42
    provides: discover_plugins, PluginLoader (pass-through CapabilityGuard stub), PluginRegistry, FastAPI lifespan plugin pipeline
provides:
  - "DEFAULT_GRANT_POLICY = 'deny' module constant; default-deny invariant locked in"
  - "PermissionDenied exception with plugin_name + capability public fields (Pitfall 6 message hygiene)"
  - "PermissionGate.resolve(spec) — granted/pending partition reading plugin_capabilities; manifest_hash mismatch flips granted → pending (PERMISSION-02 / Pitfall 5 upgrade re-prompt)"
  - "CapabilityGuard real enforcement at the wrap site preserved from Phase 42 (loader signature unchanged)"
  - "PermissionService.grant/revoke/pending_on_upgrade with audit log appended per action"
  - "plugin_capability_grants_log SQLite table (additive within v6; no SCHEMA_VERSION bump)"
  - "PluginContext.filesystem/.secrets/.net helper shim namespaces backed by per-plugin CapabilityGuard"
  - "Path.resolve() runs BEFORE the filesystem cap check (Pitfall 1 path-escape defense)"
  - "ctx.net.outbound raises clean RuntimeError on missing httpx, not ModuleNotFoundError (Pitfall 12 mirror of OtelAdapter)"
  - "asyncio.wait_for(..., timeout=PLUGIN_LIFECYCLE_TIMEOUT_S=2.0) wraps plugin adapter start/stop (ISOLATE-02; mirrors Phase 38 FORCE_FLUSH_TIMEOUT_MS=2000)"
  - "HORUS_OS_DISABLE_PLUGINS env var + --disable-all-plugins CLI flag — ISOLATE-03 escape hatch"
  - "PluginRegistry.enable/disable/is_enabled methods; per-plugin disable gate at discovery time (ISOLATE-03)"
  - "PluginLoadResult.materialized_adapters field (additive; defaults to empty tuple)"
affects: [44 (installer two-phase + grant prompt consumes PermissionService), 45 (dashboard /plugins tab + revoke buttons consume audit log + enable/disable), 46 (Pitfall regression tests extend SlowAdapter fixture)]

# Tech tracking
tech-stack:
  added: [asyncio.wait_for bounded-lifecycle pattern for plugin adapters]
  patterns:
    - "Default-deny invariant codified as module constant + referenced in every allow/deny path"
    - "Audit-log table append in same DB connection as state mutation (atomic per action)"
    - "Lazy import of optional deps (httpx in NetShim) with clean RuntimeError hint on missing — same shape as OtelAdapter's OTEL_EXTRA_HINT"
    - "Bounded asyncio.wait_for at lifespan hooks (literal 2.0s mirrors v0.4 Phase 38 OtelAdapter precedent)"

key-files:
  created:
    - tests/plugins/test_permission_gate.py
    - tests/plugins/test_capability_guard.py
    - tests/plugins/test_permission_service.py
    - tests/plugins/test_helper_shims.py
    - tests/plugins/test_bounded_lifecycle.py
    - tests/plugins/test_disable_all_plugins.py
    - tests/plugins/test_plugin_enable_disable.py
  modified:
    - src/horus_os/plugins/permissions.py (replace Phase 42 pass-through stub with real default-deny enforcement)
    - src/horus_os/plugins/api.py (add filesystem/secrets/net shim namespaces)
    - src/horus_os/plugins/__init__.py (re-export PermissionDenied/PermissionGate/PermissionService/PluginContext/require_capability)
    - src/horus_os/plugins/registry.py (add enable/disable/is_enabled methods)
    - src/horus_os/plugins/loader.py (add PluginLoadResult.materialized_adapters)
    - src/horus_os/storage.py (add plugin_capability_grants_log table; additive within v6)
    - src/horus_os/server/api.py (PermissionGate wiring + bounded lifecycle + HORUS_OS_DISABLE_PLUGINS short-circuit)
    - src/horus_os/__main__.py (--disable-all-plugins on serve subparser)
    - src/horus_os/cli/serve_cmd.py (CLI flag → env var before create_app)
    - tests/plugins/test_lifespan_integration.py (pre-grant the healthy + import-raises + tool-raises-registration fixtures' caps so the Phase 42 assertions still hold under default-deny)

key-decisions:
  - "DEFAULT_GRANT_POLICY exposed as a module-level constant, not a config field. The default-deny posture is a code-level invariant; a future contributor who wants to flip it must edit the constant in plugins/permissions.py and read the surrounding contract."
  - "PermissionGate.resolve uses Capability(name) for early ValueError on unknown caps; the loader catches and routes to error_phase='permission'. This keeps the closed-catalog (Pitfall 1) contract from MANIFEST_V1_SCHEMA all the way to the runtime gate."
  - "CapabilityGuard constructor accepts BOTH the Phase 42 positional `capabilities` tuple (legacy informational) AND the new `granted_capabilities` keyword arg. Phase 42 callsites compile unchanged; Phase 43 callers use the keyword. The legacy property stays as a deprecated alias to avoid a churn cascade through the loader."
  - "PluginContext switched from frozen dataclass to a regular class with __slots__. A frozen dataclass cannot hold the closure-bound shim references at __post_init__ time without dataclass-private trickery; plain class + __slots__ matches the CapabilityGuard pattern and is the simpler shape."
  - "_NetShim cap check fires BEFORE the lazy httpx import. A denied outbound never even loads the network stack — defense in depth against a denied plugin side-effecting the import system."
  - "PluginLoadResult.materialized_adapters is additive (defaults to empty tuple). Phase 42's PluginLoadResult-using tests continue to pass without modification; the field is opt-in for callers that need adapter instance references."
  - "The audit log table is additive within v6 (no SCHEMA_VERSION bump). CREATE TABLE IF NOT EXISTS is idempotent on both fresh and upgraded databases; v0.4 → v0.5 migration callers do not need a new ALTER TABLE block."
  - "First-party adapters (Discord, Slack, OtelAdapter etc.) stay on the unbounded v0.3 wait path. Bounded wait_for(2.0) applies ONLY to plugin adapters because untrusted plugin code is the threat model; first-party adapters are trusted code shipped with the package."
  - "test_lifespan_integration.py: fixture-setup change (_pre_grant_healthy + _pre_grant_filesystem_read helpers) preserves Phase 42 assertions. This mirrors the Phase 44 installer's grant-then-load order; the test no longer asserts pass-through behavior but the success-path assertions stay byte-identical."

patterns-established:
  - "Default-deny module constant + every gate references it (PERMISSION-01)"
  - "Manifest-hash diff drives re-prompt on upgrade (PERMISSION-02 / Pitfall 5)"
  - "Per-action audit log append in same connection as state mutation"
  - "Bounded asyncio.wait_for(2.0) for plugin lifecycle hooks (mirrors OtelAdapter force_flush(2000))"
  - "CLI escape hatch via env var + flag — env var is the authoritative gate so any caller (uvicorn worker, docker entrypoint, direct create_app) can opt out without going through the serve CLI"
  - "Fixture pre-grants in regression tests to preserve original assertions under default-deny — same code path the installer will run"

requirements-completed:
  - PERMISSION-01
  - PERMISSION-02
  - PERMISSION-03
  - PERMISSION-04
  - ISOLATE-01
  - ISOLATE-02
  - ISOLATE-03

# Metrics
duration: 1h05min
completed: 2026-05-26
---

# Phase 43 Plan 01: Permission model + bounded lifecycle Summary

**Default-deny capability enforcement, manifest-hash-pinned grants with append-only audit log, bounded asyncio.wait_for(2.0) plugin lifecycle hooks, and an `--disable-all-plugins` escape hatch — Phase 42's pass-through CapabilityGuard stub is now real default-deny without changing the loader's wrap-site signature.**

## Performance

- **Duration:** ~1h 05min
- **Started:** 2026-05-26T19:22 (Task 1 first commit)
- **Completed:** 2026-05-26 (Task 3 + Summary)
- **Tasks:** 3 of 3 complete
- **Files modified:** 10 source + 7 new test files

## Accomplishments
- **Default-deny posture codified as a module constant** (`DEFAULT_GRANT_POLICY = "deny"`) — PERMISSION-01 success criteria locked in at the code level so a future refactor cannot silently flip the default.
- **Hash-pinned grants on upgrade** (PERMISSION-02 / Pitfall 5): `PermissionGate.resolve` flips previously-granted rows to pending when `manifest_hash != spec.manifest_hash`. `PermissionService.pending_on_upgrade` logs the transition for the Phase 44 installer's update flow.
- **2.0s bounded lifecycle precedent** (ISOLATE-02): plugin adapter `start()` / `stop()` wrapped in `asyncio.wait_for(timeout=PLUGIN_LIFECYCLE_TIMEOUT_S=2.0)`. Mirrors the v0.4 Phase 38 OtelAdapter `force_flush(timeout_millis=2000)` shape literally. A 5-second sleep in a synthetic `_SlowStartAdapter.start()` is cut inside 2.5s wall clock (verified by `test_bounded_lifecycle.py::test_start_timeout_marks_error`: 2.21s duration in the slowest-test report).
- **Non-pip recovery path** (ISOLATE-03): `HORUS_OS_DISABLE_PLUGINS=true` env var short-circuits `discover_plugins()` entirely. The `--disable-all-plugins` flag on `horus-os serve` sets the env var before `create_app()` runs. `PluginRegistry.enable/disable/is_enabled` give the per-plugin level; disabled plugins skip the load step at the next `create_app` pass.
- **Append-only audit log**: `plugin_capability_grants_log` table indexed by `(plugin_name, timestamp DESC)`; every grant / revoke / pending_on_upgrade transition writes one row with actor + timestamp + manifest_hash. CHECK constraint refuses any actor outside `{cli, dashboard, system}`.
- **Helper shims**: `ctx.filesystem.read/.write`, `ctx.secrets.read`, `ctx.net.outbound` each close over a per-plugin `CapabilityGuard` and consult `granted_capabilities` before the privileged action. `Path(input).resolve()` runs BEFORE the filesystem cap check (Pitfall 1 path-escape defense). `_NetShim` lazy-imports httpx and raises a clean `RuntimeError("httpx is required for ctx.net.outbound; install horus-os[plugins-net] or pin httpx in your venv")` on missing — same shape as `OtelAdapter.OTEL_EXTRA_HINT` (Pitfall 12).

## Task Commits

Each task was committed atomically:

1. **Task 1: real CapabilityGuard + PermissionGate + PermissionService + audit table** — `42e3d5d` (feat)
2. **Task 2: PluginContext helper shims (filesystem/secrets/net) with path-escape defense** — `edb9522` (feat)
3. **Task 3: bounded lifecycle + --disable-all-plugins + enable/disable + permission gate wiring** — `4728048` (feat)

_Note: No TDD multi-commit cycle this plan — the executor wrote tests after the implementation (verifying contract from the plan's `<behavior>` block) and committed both per task._

## Files Created/Modified

### Source
- `src/horus_os/plugins/permissions.py` — Replace Phase 42 pass-through stub with `DEFAULT_GRANT_POLICY` constant, `PermissionDenied` exception, `PermissionGate.resolve`, real `CapabilityGuard.wrap_tool_handler` enforcement, `PermissionService.grant/revoke/pending_on_upgrade`.
- `src/horus_os/plugins/api.py` — Extend `PluginContext` with `.filesystem`, `.secrets`, `.net` shim namespaces backed by `CapabilityGuard`. `_FilesystemShim.read` runs `Path.resolve()` BEFORE the cap check (Pitfall 1). `_NetShim.outbound` cap-checks then lazy-imports httpx with a clean `RuntimeError` on miss.
- `src/horus_os/plugins/__init__.py` — Re-export `DEFAULT_GRANT_POLICY`, `PermissionDenied`, `PermissionGate`, `PermissionService`, `PluginContext`, `require_capability` for internal consumers.
- `src/horus_os/plugins/registry.py` — Add `enable(name)`, `disable(name)`, `is_enabled(name)` methods. `disable` flips both the SQL `plugins.enabled` column and the in-memory entry's `status` to `'disabled'`. `enable` flips status back to `'pending'` so the next discover pass re-resolves.
- `src/horus_os/plugins/loader.py` — Add `PluginLoadResult.materialized_adapters: tuple[tuple[str, object], ...]` field (additive; default empty tuple). The loader populates `(name, instance)` pairs so the FastAPI lifespan has the adapter object handle without a parallel `_plugin_adapter_instances` dict on `create_app`.
- `src/horus_os/storage.py` — Add `plugin_capability_grants_log` table inside `SCHEMA_SQL` block + `idx_plugin_capability_grants_log_plugin` index. `SCHEMA_VERSION` stays at 6 (additive within v6; `CREATE TABLE IF NOT EXISTS` is idempotent on fresh + upgraded databases).
- `src/horus_os/server/api.py` — `PLUGIN_LIFECYCLE_TIMEOUT_S = 2.0` module constant. `create_app` reads `HORUS_OS_DISABLE_PLUGINS` env var at top and short-circuits the plugin pipeline. Per-spec `is_enabled` gate + `PermissionGate.resolve` between `register` and `load`; pending caps flip status to `error_phase='permission'`. Lifespan body extends with bounded `asyncio.wait_for(start_fn(ctx), timeout=PLUGIN_LIFECYCLE_TIMEOUT_S)` on plugin adapters; symmetric stop in the `finally` block. First-party adapters stay on the v0.3 unbounded path.
- `src/horus_os/__main__.py` — Add `--disable-all-plugins` arg to the `serve` subparser.
- `src/horus_os/cli/serve_cmd.py` — `run_serve` sets `os.environ["HORUS_OS_DISABLE_PLUGINS"] = "true"` BEFORE `create_app()` runs when the flag is present.

### Tests
- `tests/plugins/test_permission_gate.py` — 6 cases: all_granted, first_install, hash_mismatch, revoked_acts_as_deny, partial grant, unknown-cap raises ValueError.
- `tests/plugins/test_capability_guard.py` — 8 cases: no-grant raises, with-grant passes, no-required-caps pass-through, explicit `required_cap` kwarg, message format contains both fields, wrapper preserves `__horus_required_caps__`, `granted_capabilities` property is frozenset, Phase 42 signature still works.
- `tests/plugins/test_permission_service.py` — 5 cases: grant appends log, revoke appends log, pending_on_upgrade appends log, actor CHECK constraint refuses unknown, re-grant is idempotent + appends second log row.
- `tests/plugins/test_helper_shims.py` — 12 cases covering all three shim namespaces' grant/no-grant matrix, path-escape defense (`Path.resolve` called BEFORE cap check), missing-env-var returns None, `net.outbound` cap check fires before `httpx.request` (mock asserts not called when denied), method kwarg forwarding, identity-field preservation.
- `tests/plugins/test_bounded_lifecycle.py` — 5 cases with synthetic `_SlowStartAdapter` / `_SlowStopAdapter` / `_RaisingStartAdapter` / `_RaisingStopAdapter` / `_FastAdapter` hand-wired via monkeypatched `PluginLoader.load`. The 5s sleep is cut by `wait_for(2.0)` in 2.21s wall clock (verified by `--durations`). Phase 46's pitfall regression tests can extend the synthetic-adapter fixture without reinventing it.
- `tests/plugins/test_disable_all_plugins.py` — 6 cases: env var skips discover, env var false does discover, env var unset does discover, CLI flag sets env var via run_serve, no flag leaves env untouched, parser recognises the flag.
- `tests/plugins/test_plugin_enable_disable.py` — 6 cases: is_enabled defaults true, disable persists to SQL + flips in-memory status, enable restores + flips status to pending, round-trip multiple times, unknown name defaults true, disable() at create_app time skips loader.load (assert via monkeypatched load that records invocation names).
- `tests/plugins/test_lifespan_integration.py` — Phase 42 regression file; fixture-setup additions (`_pre_grant_filesystem_read`, `_pre_grant_healthy` helpers) preserve original assertions under Phase 43 default-deny. Assertions unchanged.

## Test Counts

| Suite | Count | Status |
|-------|-------|--------|
| Phase 42 baseline (untouched) | 72 | green |
| Phase 43 Task 1 (permissions) | 19 | green |
| Phase 43 Task 2 (helper shims) | 12 | green |
| Phase 43 Task 3 (bounded lifecycle + disable + enable) | 17 | green |
| **Plugins total** | **120** | **green** |
| **Full repo test suite** | **841** | **green** |

`ruff check .` clean. `pytest tests/plugins/test_bounded_lifecycle.py -q -v --durations=5` confirms 2.21s wall for the 5s-sleep timeout test (budget 2.5s).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing functionality] Pre-grant fixtures in test_lifespan_integration.py**
- **Found during:** Task 3 full-suite verification.
- **Issue:** Phase 42's `test_lifespan_integration.py` healthy / import-raises / tool-raises-registration fixtures all request `filesystem.read` in their manifests. Under Phase 43 default-deny, those plugins now land in `error_phase='permission'` instead of the load-phase outcome the tests pin.
- **Fix:** Added `_pre_grant_filesystem_read(data_dir, plugin_name)` and `_pre_grant_healthy(data_dir)` helpers in the same test file. The helpers run the same `PermissionService.grant` code path the Phase 44 installer will run at install time. Original assertions unchanged.
- **Files modified:** `tests/plugins/test_lifespan_integration.py`
- **Commit:** `4728048`

**2. [Rule 1 - Bug] CLI flag test leaks env var into subsequent tests**
- **Found during:** Task 3 full-suite verification.
- **Issue:** `test_cli_flag_sets_env_var` calls `run_serve` which sets `os.environ["HORUS_OS_DISABLE_PLUGINS"] = "true"` directly — bypassing pytest's `monkeypatch`. The env var leaked into subsequent tests, breaking `test_lifespan_integration.py` runs.
- **Fix:** Wrap the CLI assertion in a try/finally that explicitly `os.environ.pop("HORUS_OS_DISABLE_PLUGINS", None)` after the run.
- **Files modified:** `tests/plugins/test_disable_all_plugins.py`
- **Commit:** `4728048`

### Auto-fixed Lint Issues

Ruff auto-fixed 7 mechanical issues (slot sort, asyncio.TimeoutError → TimeoutError alias, unused noqa). 5 remaining manually fixed: `zip(..., strict=True)`, removed dead `with patch.object(...) as mock_resolve` leftover from earlier test-iteration scratch, `db, registry` → `_db, registry` in three fixture-using tests.

## Self-Check

All claimed artifacts verified present:

```
$ ls src/horus_os/plugins/permissions.py src/horus_os/plugins/api.py src/horus_os/storage.py
src/horus_os/plugins/permissions.py
src/horus_os/plugins/api.py
src/horus_os/storage.py

$ ls tests/plugins/test_{permission_gate,capability_guard,permission_service,helper_shims,bounded_lifecycle,disable_all_plugins,plugin_enable_disable}.py
[all 7 present]

$ git log --oneline | head -3
4728048 feat(43): bounded lifecycle + --disable-all-plugins + enable/disable + permission gate wiring
edb9522 feat(43): PluginContext helper shims (filesystem/secrets/net) with path-escape defense
42e3d5d feat(43): real CapabilityGuard + PermissionGate + PermissionService + audit log

$ pytest -q | tail -1
841 passed in 21.82s

$ ruff check .
All checks passed!
```

## Self-Check: PASSED
