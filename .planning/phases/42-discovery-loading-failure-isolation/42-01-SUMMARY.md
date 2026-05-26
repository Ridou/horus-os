---
phase: 42-discovery-loading-failure-isolation
plan: "01"
subsystem: plugin-runtime-substrate
tags: [plugin-system, discovery, loader, registry, failure-isolation, capability-guard, v0.5, DISCOVERY, ISOLATE, TEST]

# Dependency graph
requires:
  - phase: "41"  # PluginSpec, validate_manifest, plugins + plugin_status tables
provides:
  - "src/horus_os/plugins/discovery.py (discover_plugins() walking entry_points + filesystem with structured DiscoveryError side-channel)"
  - "src/horus_os/plugins/loader.py (PluginLoader with rollback-on-error + LOAD_PHASE_ORDER + PluginLoadResult)"
  - "src/horus_os/plugins/registry.py (PluginRegistry mirroring AdapterRegistry shape; persists to Phase 41 plugins + plugin_status tables)"
  - "src/horus_os/plugins/permissions.py (CapabilityGuard stub — Phase 43 swap site)"
  - "src/horus_os/plugins/__init__.py (internal-consumer re-exports)"
  - "FastAPI lifespan integration in src/horus_os/server/api.py (app.state.plugin_registry)"
  - "ruff banned-api rule for pkg_resources in pyproject.toml"
  - "tests/fixtures/broken_plugins/ (4 broken fixtures + 1 healthy control for TEST-19)"

requirements-completed:
  - DISCOVERY-01  # importlib.metadata.entry_points(group='horus_os.plugins') + pkg_resources lint-banned
  - DISCOVERY-02  # filesystem walk of ~/.horus-os/plugins/<name>/ via importlib resolution
  - ISOLATE-01    # broken plugin never crashes lifespan; status='error' with structured error_phase
  - ISOLATE-04    # per-plugin error rate via PluginRegistry; PluginLoadResult.error string hygiene
  - TEST-18       # cold-start benchmark <100ms median over 10 samples
  - TEST-19       # 4 broken-plugin fixtures (bad_toml, schema_fail, import_raises, tool_raises_registration) + healthy control

# Tech stack
tech-stack:
  added: []  # no new third-party deps; all stdlib + Phase 41's pydantic + packaging
  patterns:
    - "Two-list return tuple (specs, errors) from discover_plugins() — never raises; structured DiscoveryError side-channel routes containment to the lifespan caller (ISOLATE-01)"
    - "Module-level entry_points rebind (mirrors src/horus_os/adapters/base.py:22) so tests monkeypatch the discovery source without touching importlib internals"
    - "Module-level _read_entry_point_manifest_bytes helper as a test seam — fixture monkeypatches it for manifest-bytes injection without faking importlib.resources"
    - "Rollback-on-error pattern in PluginLoader.load(): tracked (registry, name) pairs walked in reverse on any exception; mirrors how database transactions roll back partial state"
    - "CapabilityGuard.wrap_tool_handler as the Phase 43 swap site — pass-through in v0.5 substrate, real default-deny enforcement lands without changing the wrap call signature"
    - "PluginRegistry persistence with INSERT...ON CONFLICT DO UPDATE — idempotent across restarts; mutators no-op on unknown names (matches AdapterRegistry semantics)"
    - "Two-layer pkg_resources ban: Layer 1 = ruff [tool.ruff.lint.flake8-tidy-imports.banned-api]; Layer 2 = source-tree grep test in tests/plugins/test_pkg_resources_banned.py"
    - "Cold-start benchmark via stdlib time.perf_counter + N=11 samples / discard-first; no pytest-benchmark dependency added"

# Key files
key-files:
  created:
    - src/horus_os/plugins/discovery.py
    - src/horus_os/plugins/loader.py
    - src/horus_os/plugins/registry.py
    - src/horus_os/plugins/permissions.py
    - tests/plugins/conftest.py
    - tests/plugins/_loader_partial_fixture.py
    - tests/plugins/test_discovery.py
    - tests/plugins/test_loader.py
    - tests/plugins/test_loader_isolation.py
    - tests/plugins/test_cold_start_benchmark.py
    - tests/plugins/test_lifespan_integration.py
    - tests/plugins/test_pkg_resources_banned.py
    - tests/fixtures/broken_plugins/__init__.py
    - tests/fixtures/broken_plugins/bad_toml/horus-plugin.toml
    - tests/fixtures/broken_plugins/schema_fail/horus-plugin.toml
    - tests/fixtures/broken_plugins/import_raises/__init__.py
    - tests/fixtures/broken_plugins/import_raises/horus-plugin.toml
    - tests/fixtures/broken_plugins/tool_raises_registration/__init__.py
    - tests/fixtures/broken_plugins/tool_raises_registration/horus-plugin.toml
    - tests/fixtures/broken_plugins/healthy/__init__.py
    - tests/fixtures/broken_plugins/healthy/horus-plugin.toml
    - tests/perf/v0_5_phase42_cold_start.json
    - .planning/phases/42-discovery-loading-failure-isolation/42-01-SUMMARY.md
  modified:
    - src/horus_os/plugins/__init__.py       # internal-consumer re-exports for discover/loader/registry/guard
    - src/horus_os/server/api.py             # plugin pipeline + app.state.plugin_registry
    - pyproject.toml                          # TID select + flake8-tidy-imports.banned-api for pkg_resources

decisions:
  - "PluginLoader uses importlib.import_module for BOTH entry_point AND filesystem sources (tests/ is already on sys.path via pytest's rootdir). The future hook for spec_from_file_location is kept as a comment in _resolve_target_for_source so Phase 43+ can pivot without re-architecting"
  - "PluginRegistry.register_discovery_error() is a separate method from register(spec) — keeps the contract clean (DiscoveryError rows have no PluginSpec; register(spec) refuses None to keep the success path strict)"
  - "The loader's full implementation landed in Task 1's commit (not Task 2 as originally scoped) because horus_os.plugins.__init__ re-exports LOAD_PHASE_ORDER + PluginLoader, and Task 1's verify step imports those names. Splitting the loader file across commits would have created an import-time NameError. Documented as deviation Rule 3 below."
  - "Synthetic spec rows for DiscoveryError entries persist with version='0.0.0' + manifest_hash='' so the plugins.source CHECK constraint stays satisfied. Phase 45's /api/plugins route filters these placeholders out of the public surface"

# Metrics
duration: ~45m
completed: 2026-05-26
total-tests: 793 passed (33 new in tests/plugins/test_*.py); 0 failed; 0 skipped
commits: 2
---

# Phase 42 Plan 01 Summary: Discovery + loading + failure isolation

## One-line description

Wires the Phase 41 manifest substrate into a working discovery + loading pipeline with full failure isolation: ``discover_plugins()`` walks ``entry_points(group='horus_os.plugins')`` + ``~/.horus-os/plugins/`` with structured error side-channel; ``PluginLoader.load()`` registers tools + adapters with rollback-on-error and CapabilityGuard-wrapped handlers (pass-through Phase 42; Phase 43 swap site); ``PluginRegistry`` mirrors ``AdapterRegistry`` shape and persists to the Phase 41 ``plugins`` + ``plugin_status`` tables; FastAPI lifespan integrates the pipeline so broken plugins surface as ``status='error'`` rows without crashing the host. ``pkg_resources`` is now lint-banned across the source tree (Pitfall 3).

## Two atomic commits

1. **`a481b0b`** — `feat(42): plugin discovery + registry + permissions stub + pkg_resources ban`
   - 4 new plugin modules (discovery, registry, permissions, loader)
   - __init__.py rewritten with internal-consumer re-exports
   - pyproject.toml: enable TID ruff family + banned-api table

2. **`a444045`** — `feat(42): plugin loader + lifespan integration + broken-plugin fixtures`
   - FastAPI lifespan integration in server/api.py (app.state.plugin_registry)
   - 5 broken-plugin fixtures under tests/fixtures/broken_plugins/

## Requirements satisfied — one-line per ID

- **DISCOVERY-01** — Plugin discovery uses ``importlib.metadata.entry_points(group="horus_os.plugins")``; ``pkg_resources`` is lint-banned via ``[tool.ruff.lint.flake8-tidy-imports.banned-api]`` + source-tree grep test. Evidence: ``src/horus_os/plugins/discovery.py:41`` imports ``entry_points`` from ``importlib.metadata``; ``pyproject.toml`` ruff config + ``tests/plugins/test_pkg_resources_banned.py``.
- **DISCOVERY-02** — Dev plugins discovered via filesystem walk of ``$HOME/.horus-os/plugins/<name>/`` (overridable via ``HORUS_OS_PLUGIN_DIR`` env var or ``extra_paths`` arg). Each subdir is one plugin with ``horus-plugin.toml`` at the root. Evidence: ``src/horus_os/plugins/discovery.py:_discover_filesystem``; ``tests/plugins/test_discovery.py::test_one_filesystem_plugin_discovers``.
- **ISOLATE-01** — Plugin import failure, manifest validation failure, or factory exception NEVER crashes lifespan; failed plugin appears in ``app.state.plugin_registry.error()`` with structured ``error_phase``. Evidence: 5 tests in ``tests/plugins/test_loader_isolation.py`` + ``test_lifespan_integration.py::test_lifespan_continues_on_broken_plugin``.
- **ISOLATE-04** — Per-plugin error surfacing via ``PluginRegistry`` + ``PluginLoadResult.error`` hygiene (``f"{type(exc).__name__}: {exc}"`` shape; never the full traceback). Evidence: ``src/horus_os/plugins/loader.py:PluginLoader.load`` exception handler; ``tests/plugins/test_loader.py::test_load_failure_on_unimportable_module``.
- **TEST-18** — Cold-start benchmark <100ms median over 10 samples with zero installed plugins. Evidence: ``tests/plugins/test_cold_start_benchmark.py`` (local darwin/3.12 median: **0.056 ms**, three orders of magnitude under the 100ms threshold; full pipeline includes ``discover_plugins()`` + ``PluginLoader.__init__()`` constructor cost).
- **TEST-19** — Four broken-plugin fixtures + one healthy control: ``bad_toml`` (error_phase='discover'), ``schema_fail`` (error_phase='validate'), ``import_raises`` (error_phase='load'), ``tool_raises_registration`` (error_phase='load' with rollback), ``healthy`` (loads cleanly alongside). Evidence: ``tests/fixtures/broken_plugins/`` + ``tests/plugins/test_loader_isolation.py``.

## Six new test files + one helper

| File | Test count | What it covers |
|---|---|---|
| ``tests/plugins/conftest.py`` | (4 fixtures) | ``fake_plugin_entry_points``, ``tmp_plugin_dir``, ``install_broken_fixture``, ``clean_plugin_registry`` |
| ``tests/plugins/test_discovery.py`` | 12 | DISCOVERY-01 + DISCOVERY-02 — entry_points + filesystem dedup, TOML parse failure containment, schema validation failure containment, extra_paths override |
| ``tests/plugins/test_loader.py`` | 8 | PluginLoader success-path + partial-registration rollback + name-collision + factory error paths |
| ``tests/plugins/test_loader_isolation.py`` | 6 | TEST-19 — one test per broken fixture + isolation guarantee + discover-never-raises smoke |
| ``tests/plugins/test_cold_start_benchmark.py`` | 1 | TEST-18 — median <100ms with zero plugins; optional trend capture via ``HORUS_OS_CAPTURE_PERF=1`` |
| ``tests/plugins/test_lifespan_integration.py`` | 4 | FastAPI startup with broken plugin / healthy plugin / both / zero plugins; ``app.state.plugin_registry`` shape |
| ``tests/plugins/test_pkg_resources_banned.py`` | 2 | Layer-2 source-tree guard against ``import pkg_resources`` / ``from pkg_resources`` |

Total new tests: **33** (12 + 8 + 6 + 1 + 4 + 2). Suite total: **793 passed**, 0 failed, 0 skipped (up from 760 after Phase 41).

## Five broken-plugin fixtures

| Fixture | Manifest | Module | Surfaces as |
|---|---|---|---|
| ``bad_toml`` | unterminated string literal | (no module) | ``error_phase='discover'`` |
| ``schema_fail`` | valid TOML; ``capabilities=["gpu.cuda_access"]`` | (no module) | ``error_phase='validate'`` |
| ``import_raises`` | valid manifest; one tool | top-level ``raise RuntimeError`` | ``error_phase='load'`` |
| ``tool_raises_registration`` | valid manifest; one tool | ``make_tool`` raises ``ValueError`` | ``error_phase='load'`` (with rollback) |
| ``healthy`` | valid manifest; one tool named ``hello_tool`` | ``make_tool()`` returns echo Tool | ``status='loaded'`` (control) |

All five live under ``tests/fixtures/broken_plugins/``. The fixtures are addressable by Python entry-point path (``tests.fixtures.broken_plugins.import_raises:make_tool``) because pytest puts ``tests/`` on ``sys.path`` automatically.

## Deviations from plan

### 1. Loader full implementation in Task 1 (Rule 3 — auto-fix blocking issue)

**Plan said:** Task 1 commits discovery + registry + permissions + ``__init__.py`` + ``pyproject.toml``; Task 2 introduces ``loader.py``.

**Actual:** ``src/horus_os/plugins/loader.py`` was created in Task 1's commit alongside the other plugin modules.

**Reason:** Task 1's ``__init__.py`` re-exports ``LOAD_PHASE_ORDER``, ``PluginLoader``, and ``PluginLoadResult`` from ``loader.py``. Task 1's verify step (``python -c "from horus_os.plugins import LOAD_PHASE_ORDER, ..."``) requires the loader to exist at Task 1 commit time. Splitting the loader file across commits would leave the package un-importable between commit 1 and commit 2.

**Resolution:** Loader file committed with Task 1; Task 2 commit covers the FastAPI lifespan integration + broken-plugin fixtures (the lifespan is the consumer of the loader; the fixtures exercise its rollback path).

### 2. Synthetic placeholder rows for DiscoveryError persistence (Rule 2 — auto-add missing critical functionality)

**Issue:** ``PluginRegistry.register_discovery_error()`` writes a row into the SQLite ``plugins`` table for failed-discovery plugins so the ``plugin_status`` FK survives. The ``plugins.source`` CHECK constraint requires ``IN ('entry_point', 'filesystem')`` — but DiscoveryError already carries the source attribution, so we pass it straight through. Side effect: a DiscoveryError-only row has ``version='0.0.0'`` and ``manifest_hash=''`` placeholders.

**Resolution:** Documented in the registry's docstring; Phase 45's ``/api/plugins`` route should filter these placeholders out of the public surface (added as a forward-looking note in the "Open questions for Phase 43+" section below).

### 3. Ruff `noqa` cleanup (Rule 1 — auto-fix bugs)

**Issue:** Initial test files had ``# noqa: ARG001`` on unused-argument fixtures; the ruff config does not enable the ARG rule family, so every directive was flagged as ``RUF100``.

**Resolution:** ``ruff check --fix`` removed all 32 unused directives. The fixtures still work (they're passed for monkey-patch side effects, not for their return values); the comments stay informational via the fixture docstrings.

## What is NOT yet wired (forward-looking)

Phase 42 ships the runtime substrate; the consumer surfaces land in subsequent phases:

- **Phase 43** (PermissionGate + CapabilityGuard real enforcement)
  - Swaps ``CapabilityGuard.wrap_tool_handler`` from pass-through to default-deny; the wrap site marker comment is pinned at ``src/horus_os/plugins/permissions.py:74``.
  - Adds the Start lifecycle phase (bounded ``asyncio.wait_for(start, timeout=2.0)`` in the FastAPI lifespan).
  - Introduces ``mark_started`` / ``mark_stopped`` on ``PluginRegistry``.
  - May add a true ``unregister`` on ``AdapterRegistry`` so adapter rollback symmetrically matches tool rollback (currently the loader uses ``mark_error("rolled back: ...")`` because ``AdapterRegistry`` has no unregister).
  - Wires ISOLATE-01 from "tested-only-for-discover/validate/load" to "covers start-raising + start-hanging" via TEST-19's remaining variants.
  - Adds the ``plugins.enabled=0`` short-circuit: disabled plugins skip discovery (no half-loaded state). Phase 43 reads the ``enabled`` column at discovery time and routes disabled plugins to ``status='disabled'`` without invoking the loader.

- **Phase 44** (Installer CLI)
  - Consumes the discovery + registry surface to list, enable, disable plugins via ``horus-os plugins`` subcommands.
  - Uses ``Capability.DESCRIPTIONS`` (Phase 41) to render install-time grant prompts.
  - Uses ``format_validation_error()`` to surface manifest validation failures verbatim.

- **Phase 45** (Dashboard ``/api/plugins`` + ``/plugins`` tab)
  - Serializes ``PluginEntry`` shape from ``app.state.plugin_registry`` directly.
  - **Open question:** the DiscoveryError placeholder rows (version='0.0.0', manifest_hash='') need a serialization rule — surface them with a "failed at discovery" badge AND clear that placeholder data, OR filter them out of the API and show only at-rest plugins. Phase 45's planner should pick.

## Cold-start benchmark numbers (TEST-18)

| Env | Median (ms) | Threshold (ms) | Headroom |
|---|---|---|---|
| darwin / 3.12 / horus-os 0.4.0 | **0.056** | 100 | 1786x |

Trend baseline reference: Phase 40's ``v0_4_baseline.json`` recorded entry_points discovery at 1.909ms on darwin/3.12. Phase 42's pipeline (with zero plugins) is 30x faster than that baseline because the rebound ``entry_points`` returns an empty list immediately — no importlib walk required.

Trend capture: ``HORUS_OS_CAPTURE_PERF=1 pytest tests/plugins/test_cold_start_benchmark.py`` writes ``tests/perf/v0_5_phase42_cold_start.json``. CI does not set the env var by default; the JSON file is intended for ad-hoc trend tracking on dev machines.

## Authentication gates

None. Pure local infrastructure phase.

## Test counts + verification commands

```
$ .venv/bin/python -m pytest -q
793 passed in 18.53s

$ .venv/bin/python -m ruff check src/ tests/
All checks passed!

$ .venv/bin/python -c "from horus_os.plugins import discover_plugins, PluginLoader, PluginRegistry, LOAD_PHASE_ORDER; print('ok')"
ok

$ grep -rE "import pkg_resources|from pkg_resources" src/horus_os/ ; echo exit=$?
exit=1   # no matches; ban is intact
```

## Atomic commit ledger

1. `feat(42): plugin discovery + registry + permissions stub + pkg_resources ban`. **`a481b0b`**
2. `feat(42): plugin loader + lifespan integration + broken-plugin fixtures`. **`a444045`**

## Self-Check

Verified after writing this SUMMARY:

- Both Phase 42 commits exist on local main with the required ``feat(42)`` prefixes.
- ``src/horus_os/plugins/discovery.py`` exposes ``discover_plugins`` + ``DiscoveryError`` + ``PLUGIN_ENTRY_POINT_GROUP`` + ``DEFAULT_FILESYSTEM_PLUGIN_DIR``.
- ``src/horus_os/plugins/loader.py`` exposes ``PluginLoader`` + ``PluginLoadResult`` + ``LOAD_PHASE_ORDER == ('discover', 'validate', 'permission', 'load', 'start', 'stop')``.
- ``src/horus_os/plugins/registry.py`` exposes ``PluginRegistry`` + ``PluginEntry`` + four ``PLUGIN_STATUS_*`` constants.
- ``src/horus_os/plugins/permissions.py`` exposes ``CapabilityGuard`` with the ``# Phase 43 wires real enforcement`` comment marker present.
- ``src/horus_os/plugins/__init__.py`` re-exports all of the above + ``DiscoveryError`` in the ``__all__`` tuple.
- ``src/horus_os/server/api.py`` imports from ``horus_os.plugins`` and sets ``app.state.plugin_registry``.
- ``pyproject.toml`` has ``[tool.ruff.lint.flake8-tidy-imports.banned-api]`` table with the ``pkg_resources`` entry.
- ``tests/fixtures/broken_plugins/`` has 5 subdirectories (bad_toml, schema_fail, import_raises, tool_raises_registration, healthy) each with ``horus-plugin.toml``; the three with importable Python modules also have ``__init__.py``.
- ``.venv/bin/python -m pytest -q`` → 793 passed.
- ``.venv/bin/python -m ruff check src/ tests/`` → All checks passed.
- ``grep -rE 'import pkg_resources|from pkg_resources' src/horus_os/`` returns no matches.
- Cold-start benchmark median (darwin/3.12): **0.056 ms** vs 100 ms threshold.
