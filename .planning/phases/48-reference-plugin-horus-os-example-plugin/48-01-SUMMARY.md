---
phase: 48-reference-plugin-horus-os-example-plugin
plan: 01
subsystem: plugins-reference
tags: [v0.5, REFERENCE-01, TEST-21, Pitfall-8, plugins]
requires:
  - Phase 41 (horus_os.plugins.api single public surface + MANIFEST_V1_SCHEMA)
  - Phase 42 (filesystem-walk discovery; two-layer banned-api precedent)
  - Phase 43 (PermissionGate + CapabilityGuard + asyncio.wait_for(timeout=2.0))
  - Phase 45 (/api/plugins route surfaces granted/pending capability sets)
  - Phase 46 (installer_e2e marker + clean_venv session-scoped fixture)
  - Phase 47 (docs/PLUGINS.md forward-reference contract)
provides:
  - examples/horus-os-example-plugin/ (PEP 621 + setuptools, self-contained installable)
  - examples/horus-os-example-plugin/horus-plugin.toml (v1 manifest; 2 tools + 1 adapter; 2 capabilities)
  - examples/horus-os-example-plugin/src/horus_os_example_plugin/ (3 modules; only public-API imports)
  - examples/horus-os-example-plugin/tests/test_example_plugin.py (5 tier-1 scenario tests)
  - examples/horus-os-example-plugin/tests/conftest.py (sys.path injection; avoids host venv pollution)
  - examples/horus-os-example-plugin/README.md (one-page authoring starter)
  - tests/plugins/test_reference_plugin_public_api_only.py (TEST-21 layer 2; 4 tests)
  - tests/plugins/test_reference_plugin_install_local.py (REFERENCE-01 installer-e2e smoke; 1 gated test)
  - pyproject.toml extension (TEST-21 layer 1 ruff banned-api scoped to reference plugin src/; testpaths add)
  - CHANGELOG.md [0.5.0] -> Added: forward-reference bullet replaced with concrete reference-plugin entry
affects:
  - pyproject.toml (banned-api + per-file-ignores + testpaths)
  - CHANGELOG.md (forward-reference bullet replaced)
tech-stack:
  added: []
  patterns:
    - "setuptools editable install of a sibling package alongside the host (PEP 621)"
    - "ruff flake8-tidy-imports.banned-api scoped via per-file-ignores inversion (allow everywhere except reference plugin src/)"
    - "two-layer surface lock (ruff lint + pytest source-tree grep; same pattern as Phase 42's pkg_resources guard)"
    - "filesystem-walk discovery for installer-e2e in-process app (avoids cross-interpreter sys.path mutation)"
    - "tier-1 plugin-local tests via sys.path-injection conftest (avoids polluting host venv's importlib.metadata)"
key-files:
  created:
    - examples/horus-os-example-plugin/pyproject.toml
    - examples/horus-os-example-plugin/horus-plugin.toml
    - examples/horus-os-example-plugin/README.md
    - examples/horus-os-example-plugin/src/horus_os_example_plugin/__init__.py
    - examples/horus-os-example-plugin/src/horus_os_example_plugin/tools.py
    - examples/horus-os-example-plugin/src/horus_os_example_plugin/adapter.py
    - examples/horus-os-example-plugin/tests/conftest.py
    - examples/horus-os-example-plugin/tests/test_example_plugin.py
    - tests/plugins/test_reference_plugin_public_api_only.py
    - tests/plugins/test_reference_plugin_install_local.py
  modified:
    - pyproject.toml
    - CHANGELOG.md
decisions:
  - "Plan's blanket 'horus_os.plugins' banned-api entry dropped: ruff matches by prefix, banning horus_os.plugins would also ban the sanctioned horus_os.plugins.api surface. Layer-2 regex (not-equal-to-api) covers any future submodule slip."
  - "Plan's 'src/**/*.py' per-file-ignore replaced with 'src/horus_os/**/*.py' to keep the rule active on the reference plugin's nested src/ tree (the blanket pattern would silence TID251 on the very files we want locked down)."
  - "Plan's 'examples/*.py' per-file-ignore replaced with explicit filenames for the seven sibling adapter examples; the wildcard would have matched the reference plugin's deeper paths under ruff's glob semantics."
  - "Reference plugin NOT pip-installed into the host .venv for tier-1 tests; instead a local conftest.py prepends src/ to sys.path. Installing it would pollute the host's plugin-discovery tests with a real entry point — pre-fixed in this commit."
  - "Plugin-local tests/__init__.py removed: clashed with host tests/conftest.py under ImportPathMismatchError (both being 'tests' packages)."
  - "Installer-e2e smoke uses filesystem-walk discovery (HORUS_OS_PLUGIN_DIR) for the in-process app instead of consuming the clean venv's site-packages. Cross-interpreter sys.path mutation would leak across the session; this path is cleaner and exercises the same validate -> gate -> grant pipeline."
  - "Installer-e2e test explicitly cleans up the *.egg-info directory pip-install -e leaves behind in the plugin's source tree; without cleanup, subsequent default pytest runs in the same checkout see the plugin discovered via importlib.metadata and break tests/server/test_plugins_api.py::test_list_plugins_empty."
metrics:
  duration: "~50 min"
  completed: 2026-05-26T14:47:00Z
---

# Phase 48 Plan 01: Reference Plugin (`horus-os-example-plugin`) Summary

Shipped the canonical reference plugin for v0.5 plugin authors plus a
two-layer surface lock that pins the plugin's public API surface to
`horus_os.plugins.api`. Closes REFERENCE-01 and TEST-21.

## One-liner

`examples/horus-os-example-plugin/` is now a self-contained installable
package that demonstrates all four v0.5 plugin scenarios (capability-gated
filesystem tool, capability-gated secret tool, bounded-lifecycle adapter,
combined tool + adapter package) and the public-API surface is byte-locked
via ruff `flake8-tidy-imports.banned-api` (layer 1) + a pytest
source-tree-grep backstop (layer 2).

## What landed

**Reference plugin package** (`examples/horus-os-example-plugin/`)

- `pyproject.toml` — PEP 621 + `setuptools.build_meta`. Declares
  `[project.entry-points."horus_os.plugins"]` with one entry
  (`horus-os-example-plugin = "horus_os_example_plugin"`). Depends on
  `horus-os>=0.5,<0.6`. Setuptools `packages.find` rooted at `src/`.
- `horus-plugin.toml` — v1 manifest. Eleven top-level fields populated.
  `capabilities = ["filesystem.read", "secrets.read"]`. Two
  `[[contributions.tools]]` entries + one `[[contributions.adapters]]`
  entry. Validates against `MANIFEST_V1_SCHEMA` with zero errors;
  yields a `PluginSpec` with manifest_hash `00daac3b65485d7a...`.
- `src/horus_os_example_plugin/tools.py` — `echo_text_tool` (filesystem
  read, gated on `Capability.FILESYSTEM_READ`) and `lookup_secret_tool`
  (env-var read, gated on `Capability.SECRETS_READ`, returns `None` on
  missing key). Single import line:
  `from horus_os.plugins.api import Capability, PluginContext, require_capability`.
- `src/horus_os_example_plugin/adapter.py` — `ExampleAdapter` with
  `start(ctx)` (schedules `asyncio.create_task(asyncio.sleep(0))`) and
  `stop()` (cancels + awaits under `except asyncio.CancelledError`).
  Both methods return in microseconds; the Phase 43
  `asyncio.wait_for(timeout=2.0)` ceiling is never approached.
- `src/horus_os_example_plugin/__init__.py` — marker module with
  empty `__all__` (the public surface is the entry-point group, not
  bare attribute imports).
- `README.md` — one-page authoring starter (84 lines): what it
  demonstrates, how to install, anatomy by source file, rename-as-
  starting-template instructions, links to docs/PLUGINS.md and
  docs/PLUGIN-SECURITY.md.
- `tests/test_example_plugin.py` + `tests/conftest.py` — 5 tier-1
  scenario tests run under the host pytest invocation. The conftest
  prepends `src/` to `sys.path` so the package imports without being
  pip-installed in the host venv.

**TEST-21 layer 1 — ruff banned-api** (`pyproject.toml`)

Added 10 banned-api entries scoped to the reference plugin's `src/`
tree via the per-file-ignores inversion pattern:

- `horus_os.adapters`, `horus_os.types`
- `horus_os.plugins.spec`, `horus_os.plugins.manifest`,
  `horus_os.plugins.permissions`, `horus_os.plugins.capability_catalog`,
  `horus_os.plugins.discovery`, `horus_os.plugins.loader`,
  `horus_os.plugins.registry`, `horus_os.plugins.installer`

Each entry's `.msg` names Pitfall 8 and points at `docs/PLUGINS.md`
"Public API surface." The bare `horus_os.plugins` ban from the plan is
intentionally NOT included — ruff's prefix matching would extend the
ban to `horus_os.plugins.api`, the sanctioned public surface. Layer 2
catches future submodule slips.

`[tool.ruff.lint.per-file-ignores]` silences `TID251` everywhere except
`examples/horus-os-example-plugin/src/`:
- `src/horus_os/**/*.py` (anchored at the first-party package name so
  the rule does NOT silence on the reference plugin's nested `src/`)
- `tests/**/*.py`, `scripts/**/*.py`, `docs/**/*.py`
- `examples/horus-os-example-plugin/tests/**/*.py` (the plugin's own
  tests import internal surface freely)
- The seven sibling adapter examples enumerated by full filename
  (`examples/discord_adapter.py`, etc.) rather than a wildcard glob
  (the wildcard would also match the reference plugin's deeper paths
  under ruff's matcher).

**TEST-21 layer 2 — pytest source-tree backstop**
(`tests/plugins/test_reference_plugin_public_api_only.py`)

Four tests in the default pytest invocation:

1. `test_reference_plugin_source_dir_exists` — guards against vacuous
   pass on a refactor that moves or renames the example.
2. `test_reference_plugin_uses_only_public_api` — walks every `*.py`
   under the plugin's `src/`, regex-matches `from horus_os.*` or
   `import horus_os.*`, fails on any line that is not exactly
   `from horus_os.plugins.api import ...`. File:line context on
   failure.
3. `test_scanner_catches_synthetic_bad_import` — synthesizes a fake
   plugin source tree containing a known violation under `tmp_path`;
   asserts the scanner returns exactly one offender string. Proves the
   scanner is non-vacuous (matches Phase 42 pattern).
4. `test_scanner_also_catches_bare_import_horus_os` — covers
   `import horus_os.types` style (not just `from`).

**REFERENCE-01 installer-e2e smoke**
(`tests/plugins/test_reference_plugin_install_local.py`)

One test marked `pytestmark = pytest.mark.installer_e2e` (skipped under
default invocation; runs under `--run-installer-e2e`). Pip-installs the
reference plugin into the Phase 46 `clean_venv` session fixture,
filesystem-discovers it via `HORUS_OS_PLUGIN_DIR`, asserts the gate
transitions `pending_capabilities = {filesystem.read, secrets.read}`
-> `granted_capabilities = {...}` after `PermissionService.grant`
calls. Single-host shape-correctness gate; the 3-OS matrix is Phase 49
TEST-20.

The test cleans up `*.egg-info` after running so the source tree
returns to pre-test shape — without this, subsequent default pytest
runs see the plugin discovered via `importlib.metadata` and the host's
`tests/server/test_plugins_api.py::test_list_plugins_empty` fails.

**CHANGELOG**

`[0.5.0]` -> `Added` forward-reference bullet replaced with a concrete
reference-plugin entry naming all four scenarios and the TEST-21 guard.
`grep -c "horus-os-example-plugin" CHANGELOG.md` returns 1.

## Verification

| Check | Command | Result |
|-------|---------|--------|
| Manifest validates | `validate_manifest(horus-plugin.toml).manifest_hash` | OK; capabilities = {filesystem.read, secrets.read}; 2 tools, 1 adapter |
| Public-API-only (AST) | `ast.walk` over `src/**/*.py` | only `from horus_os.plugins.api` imports |
| Layer 1 (ruff) on shipped source | `ruff check examples/horus-os-example-plugin/` | All checks passed |
| Layer 1 (ruff) on synthetic violation | inject `from horus_os.adapters import Adapter`, re-run | TID251 fires; revert |
| Layer 2 (pytest scan) | `pytest tests/plugins/test_reference_plugin_public_api_only.py` | 4 passed |
| Plugin-local tier-1 tests | `pytest examples/horus-os-example-plugin/tests/` | 5 passed |
| Installer-e2e (default invocation) | `pytest tests/plugins/test_reference_plugin_install_local.py` | 1 skipped (installer_e2e gate) |
| Installer-e2e (with flag) | `pytest --run-installer-e2e tests/plugins/test_reference_plugin_install_local.py` | 1 passed in ~9s after the ~30s clean_venv warm-up |
| Phase 42 pkg_resources guard | `pytest tests/plugins/test_pkg_resources_banned.py` | 2 passed |
| Phase 47 docs-anatomy | `pytest tests/docs/test_plugins_md_anatomy.py` | 4 passed |
| Full suite | `pytest -q` | 986 passed, 3 skipped (was 977; +9 = 5 plugin-local + 4 layer-2) |

## Deviations from Plan

All deviations were Rule 3 (fix blocking issues) — the plan's suggested
ruff config did not work as written and the plugin's tests collided with
host conftest. No architectural changes; all are config-shape adjustments.

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Plan's ruff `horus_os.plugins` bare-name ban silenced the sanctioned surface**

- **Found during:** Task 2 layer-1 verification.
- **Issue:** ruff's `flake8-tidy-imports.banned-api` matches by prefix.
  Banning `horus_os.plugins` (per the plan) also bans
  `horus_os.plugins.api`, which the reference plugin must import from.
  Ran into immediate TID251 failures on the shipped source.
- **Fix:** Dropped the `horus_os.plugins` bare-name entry; kept the
  10 specific submodule entries. Layer 2's regex
  (`from horus_os.<anything but plugins.api>`) catches any future
  submodule slip.
- **Files modified:** `pyproject.toml`.
- **Commit:** fc96184.

**2. [Rule 3 — Blocking] Plan's `src/**/*.py` per-file-ignore silenced TID251 on the very tree it should lock down**

- **Found during:** Task 2 layer-1 verification (ruff did not flag a
  synthetic `from horus_os.adapters import Adapter` in
  `examples/horus-os-example-plugin/src/`).
- **Issue:** ruff's glob matcher matches any path containing the
  glob pattern, so `src/**/*.py` matches both
  `src/horus_os/...` AND `examples/horus-os-example-plugin/src/...`.
- **Fix:** Anchored the per-file-ignore to `src/horus_os/**/*.py`.
  Same correction for `examples/*.py` → enumerated the seven sibling
  adapter examples by full filename.
- **Files modified:** `pyproject.toml`.
- **Commit:** fc96184.

**3. [Rule 3 — Blocking] Plan's tests `__init__.py` clashed with host conftest under ImportPathMismatchError**

- **Found during:** Task 1 verification (full pytest suite).
- **Issue:** `examples/horus-os-example-plugin/tests/__init__.py`
  made it a `tests` package; the host's `tests/conftest.py` also
  declares a `tests` package; pytest's path resolution refused to
  load both ("ImportPathMismatchError: tests.conftest").
- **Fix:** Dropped the plugin tests' `__init__.py`. Tests still get
  collected via the host's `[tool.pytest.ini_options].testpaths`
  glob (`examples/horus-os-example-plugin/tests`); the plugin's
  `tests/conftest.py` injects `src/` onto `sys.path` so imports
  resolve without an `__init__.py`.
- **Files modified:** Deleted
  `examples/horus-os-example-plugin/tests/__init__.py`.
- **Commit:** fc96184.

**4. [Rule 3 — Blocking] Pip-installing the reference plugin into the host .venv pollutes plugin-discovery tests**

- **Found during:** Task 1 initial validation (full pytest suite
  after a manual `pip install -e ./examples/horus-os-example-plugin`).
- **Issue:** The host's `tests/server/test_plugins_api.py::test_list_plugins_empty`
  expects `/api/plugins` to return `[]`; if the reference plugin is
  installed into the host .venv it discovers as a real entry point
  and breaks the test.
- **Fix:** Do NOT install the plugin into the host venv. Local
  `examples/horus-os-example-plugin/tests/conftest.py` prepends
  `src/` to `sys.path` so tier-1 tests import the package without
  it appearing in `importlib.metadata`. The installer-e2e smoke
  (Task 3) DOES exercise the pip-install path but uses the isolated
  `clean_venv` fixture.
- **Files modified:** Added
  `examples/horus-os-example-plugin/tests/conftest.py`.
- **Commit:** 30b7e95.

**5. [Rule 1 — Bug] Installer-e2e left `*.egg-info` behind, breaking subsequent default pytest runs**

- **Found during:** Task 3 verification (re-ran `pytest -q` after
  `pytest --run-installer-e2e ...`).
- **Issue:** `pip install -e <ref_plugin>` writes
  `examples/horus-os-example-plugin/src/horus_os_example_plugin.egg-info`
  into the SOURCE tree. Even after `pip uninstall`, that directory
  stays. The host pytest interpreter's `importlib.metadata` then
  discovers the plugin via the source `.egg-info` and pollutes the
  same tests that originally motivated deviation #4.
- **Fix:** Explicit cleanup at the end of
  `test_reference_plugin_installs_and_loads_after_grant` removes
  `*.egg-info`, any `*.dist-info`, and any stale `build/` or `dist/`
  directories. Asserts the egg-info is gone after cleanup.
- **Files modified:**
  `tests/plugins/test_reference_plugin_install_local.py`.
- **Commit:** (in Task 3, separate commit below).

## Forward Dependency Cleared

Phase 49 (3-OS install-smoke matrix, TEST-20) can now consume
`examples/horus-os-example-plugin/` as the package the matrix builds
and installs. The matrix runs against (Ubuntu, macOS, Windows) by
(Python 3.11, 3.12) and exercises the entry-point seam via the host
interpreter's `importlib.metadata` — which Phase 48's tier-3 smoke
does not (it uses the filesystem-walk discovery path instead). The
Phase 49 release gate REL-11 also consumes the manifest as a
validate-during-build check.

## Stub Tracking

No stubs. Every line of the reference plugin's source compiles, runs,
and is exercised by at least one test (tier-1 in-process for tools +
adapter, tier-3 installer-e2e for the manifest + entry-point shape).

## Self-Check: PASSED

All 11 claimed files exist on disk. All 3 commits (30b7e95, fc96184,
b1dce5b) exist in the git log. Full pytest suite green (986 passed, 3
skipped). Host-wide ruff clean. Phase 47's docs-anatomy test still
green (4 passed); Phase 42's pkg_resources guard still green (2
passed). `grep -c "horus-os-example-plugin" CHANGELOG.md` returns 1.
