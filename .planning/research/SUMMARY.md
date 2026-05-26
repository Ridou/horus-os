# Project Research Summary

**Project:** horus-os v0.5 Plugin System
**Domain:** Third-party Python plugin runtime on a local-first single-process AI command center
**Researched:** 2026-05-26
**Confidence:** HIGH

## Executive Summary

v0.5 turns horus-os from "built-in adapters and tools only" into "anyone can ship a horus-os plugin," and the four research files converge on the same shape: a TOML manifest, entry-point + filesystem discovery, a default-deny capability grant model, a `pip`-wrapped installer, an in-process loader that registers plugin-contributed tools and adapters into the existing `ToolRegistry` / `AdapterRegistry` (no new hook framework), and a `/plugins` dashboard tab that reuses v0.4's `ObservationBus` for per-plugin error-rate attribution. The closest analog is Datasette's plugin system; horus-os v0.5 = Datasette's installer + Home Assistant's manifest + VS Code's first-run consent prompt + v0.4's observability stack, wired together rather than re-engineered.

The recommended approach is to add exactly two new runtime dependencies (`pydantic>=2.7,<3` and `packaging>=24.0`) and rely on stdlib for everything else (`tomllib`, `importlib.metadata`, `importlib.util`, `subprocess`, `hashlib`). The architecture is a six-phase per-plugin pipeline (Discover -> Validate -> Permission gate -> Load -> Start -> Health) where each phase has a single failure mode and a single registry mutation, mirroring the v0.3 `discover_adapters` shape but with explicit status surfacing. Capability enforcement is wrapped at the **registration boundary** (inside `PluginLoader.load()`), not at the call site, so built-in tools stay byte-identical to v0.4 and `ToolRegistry.invoke` does not learn about plugins.

Key risks are concentrated in two areas. **Security:** in-process plugin code is arbitrary code execution, and PROJECT.md explicitly defers OS sandboxing to v0.6+, so the trust contract is "default-deny capability grants + plain-English first-run prompt + per-version grant keying with re-prompt on manifest-hash change." Pitfall 1 (default-allow normalizes compromise) and Pitfall 5 (silent capability expansion on upgrade) are non-negotiable to prevent at the schema layer, not bolt-on later. **Compatibility:** the v5→v6 SQLite migration must be additive-only (per v0.4 Phase 32 precedent), the `importlib.metadata.entry_points()` API drifted 3.10→3.12 so `pkg_resources` is lint-banned, and `pip install` must be two-phase (download + validate before install) to defeat the `setup.py` arbitrary-code-execution escape hatch.

## Key Findings

### Recommended Stack

Two new direct dependencies, both in the base `[project.dependencies]` list (NOT an optional extra), plus stdlib. See STACK.md for full rationale and rejected alternatives.

**Core technologies:**

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| `tomllib` | stdlib (3.11+) | Read `horus-plugin.toml` manifest | Already in stdlib at horus-os's 3.11+ floor; zero new dep |
| `importlib.metadata` | stdlib (3.11+) | Discover plugins via `entry_points(group="horus_os.plugins")` | Canonical replacement for deprecated `pkg_resources`; same shape `discover_adapters()` already uses |
| `importlib.util` + `importlib.machinery` | stdlib | Load plugin modules from `~/.horus-os/plugins/` (dev path) | `spec_from_file_location` + `module_from_spec` + `exec_module`; no `sys.path` mutation needed |
| `subprocess` | stdlib | Wrap `pip install` / `uninstall` / `show` for installer | pip explicitly forbids `import pip`; canonical pattern uses `sys.executable` (encodes active venv) |
| `pathlib.Path` | stdlib | All filesystem paths | Already the horus-os convention; cross-OS clean |
| `hashlib` | stdlib | SHA-256 of manifest capabilities for re-prompt detection | O(1) change check against persisted `grant_hash` |
| `pydantic` | `>=2.7,<3` | Manifest schema validation | Structured `ValidationError.errors()` for clean installer error messages; Rust core fast. **New direct dep in v0.5** (v0.4 `dependencies = []`) |
| `packaging` | `>=24.0` | `SpecifierSet` for `horus_os_compat`; `Requirement` to parse install spec | Only correct PEP 440 implementation (`~=` compatible-release operator) |

**Explicitly rejected:** `pkg_resources` (deprecated, slow), `pluggy` (hook fan-out doesn't fit), `stevedore` (10x bigger surface than needed), `import pip` (forbidden by pip itself), `tomli` (stdlib has it now), `tomlkit` (we never write manifests), `marshmallow`/`attrs`/`voluptuous` (lose to pydantic v2), `RestrictedPython` / in-process sandbox (illusion of safety), `pip --user` and `pip --target` (defeat venv entry-point discovery), hand-rolled PEP 440 parsing.

### Expected Features

FEATURES.md confirms eight REQUIREMENTS.md categories. Each category below maps 1:1 to a section the requirement writer should produce.

**Must have (table stakes, P1, all ship in v0.5.0):**

| Category | What ships | Anchored by |
|----------|-----------|-------------|
| **MANIFEST** (01-05) | `horus-plugin.toml` with name, version, description, author, license, homepage, `horus_os_compat`, declared tools/adapters, requested capabilities. Strict pydantic-backed schema validation at install with line-numbered errors. `manifest_version: int` required from day one. | Home Assistant `manifest.json`, VS Code `package.json contributes`, `pyproject.toml` shape |
| **DISCOVERY** (01-02) | Entry-points group `horus_os.plugins` (primary, pip-installed) + `~/.horus-os/plugins/` directory drop-in (dev path). Same `PluginSpec` output. | Datasette `--plugins-dir`, pytest `pytest11`, Home Assistant `custom_components/` |
| **INSTALL** (01-06) | `horus-os plugins install \| uninstall \| list \| info \| enable \| disable \| update` subcommands wrapping `pip` in the active venv. Two-phase install: download → validate manifest + show capabilities → confirm → install. | Datasette `datasette install` |
| **PERMISSION** (01-04) | Default-deny posture; grants persisted in SQLite keyed on `(plugin_name, plugin_version, capability)`; revocable from dashboard; **re-prompt when manifest hash changes**; closed enum of capability strings via `capability_catalog.py` with plain-English descriptions. | VS Code 1.97+ Workspace Trust, Home Assistant policy, mobile OS permission re-prompt on scope expansion |
| **ISOLATE** (01-04) | Failure containment: bad import / bad manifest / `start()` exception / runtime exception caught and reported, never crashes host. Per-plugin error-status surface. Enable/disable toggle. **Slow-start timeout via `asyncio.wait_for(start, timeout=2.0)`**. | Home Assistant `ConfigEntryNotReady` + Recovery Mode; v0.4 Phase 38 `OtelAdapter` 2000ms precedent |
| **DASH** (01-03) | `/plugins` dashboard tab listing installed plugins with version, declared contributions, granted capabilities, lifecycle status, last error, error rate. Per-plugin enable/disable toggle. Author/homepage/issue-tracker hyperlinks. | Existing v0.3 `/adapters` tab |
| **OBSERVE** (01) | **The v0.5 differentiator.** Add `plugin_name TEXT NULL` column to `llm_calls` and `tool_invocations`; render per-plugin error rate + p95 latency on `/observability`. NULL = "horus-os core". | None of the seven competitor systems surface this; it's our edge |
| **REFERENCE** (01-02) | Published `horus-os-example-plugin` (separate package, same monorepo at `examples/horus-os-example-plugin/`) demonstrating four scenarios. Plugin-author docs at `docs/PLUGINS.md`. **Public API surface is `horus_os.plugins.api` ONLY** — reference plugin lint-rejects any other `from horus_os` import. | Datasette cookiecutter, Home Assistant `example_integration`, VS Code `vscode-extension-samples` |

**Should have (P2):** OBSERVE-02 (per-plugin LLM cost attribution — include in v0.5 only if literal column addition), REFERENCE-03 (cookiecutter template).

**Defer (P3, v0.6+):** OS-level subprocess/container sandbox, hosted plugin catalog, plugin signing / Sigstore, schema-driven plugin settings UI, hot-reload, auto-update on start.

**Anti-features (reject explicitly):** Default-allow on first install, grants keyed on `plugin_name` only without version, in-process Python sandbox via `RestrictedPython`, pluggy-style hook framework.

### Architecture Approach

A new `src/horus_os/plugins/` package containing eight modules, sitting **on top of** the existing v0.1-v0.4 registries (which stay byte-identical). One-way dependency: plugins → registries, never the reverse. Capability enforcement is wrapped at registration time so built-ins never go through the guard codepath.

**The six-phase pipeline (one pass per plugin, inside FastAPI lifespan):**

1. **Discover** — `entry_points(group="horus_os.plugins")` + filesystem walk of `~/.horus-os/plugins/`. Returns `list[PluginSpec]`. No registry side effects.
2. **Validate** — parse `horus-plugin.toml` via `tomllib`, validate via pydantic, check `horus_os_compat` against `__version__` via `packaging.SpecifierSet`. On failure: `status="error", error_phase="validate"`.
3. **Permission gate** — compare manifest capabilities against persisted `plugin_capabilities` rows. Manifest-hash mismatch flips previously-granted capabilities to `pending`.
4. **Load** — import entry-point module via `EntryPoint.load()` (or `importlib.util.spec_from_file_location` for filesystem plugins). Register tools via `ToolRegistry.register(tool)`; each plugin-contributed tool handler is wrapped with `CapabilityGuard` before being registered.
5. **Start** — for adapter-providing plugins, call `start(AdapterContext)` wrapped in `asyncio.wait_for(start(ctx), timeout=2.0)`.
6. **Health** — `PluginHealthSubscriber` subscribes to `ObservationBus`. Filters per-plugin, rolls up error rate + p95 latency in-memory ring buffers.

**Major components:** `plugins/spec.py`, `plugins/manifest.py`, `plugins/discovery.py`, `plugins/registry.py`, `plugins/permissions.py` (+ `capability_catalog.py`), `plugins/loader.py`, `plugins/health.py`, `plugins/api.py` (the only public re-export surface).

**Persistence (v5 → v6, additive only):**

```sql
CREATE TABLE IF NOT EXISTS plugins (...);                  -- installed list + manifest_hash
CREATE TABLE IF NOT EXISTS plugin_capabilities (...);      -- per-capability grant + manifest_hash
CREATE TABLE IF NOT EXISTS plugin_status (...);            -- last_seen, error_count, last_error
ALTER TABLE llm_calls ADD COLUMN plugin_name TEXT;         -- NULLABLE
ALTER TABLE tool_invocations ADD COLUMN plugin_name TEXT;  -- NULLABLE
CREATE INDEX idx_tool_invocations_plugin ON tool_invocations(plugin_name, created_at);
```

No DROP. No RENAME. No NOT NULL on existing columns. v0.4 fixture must round-trip.

**Hard architectural rules:**

- Capability enforcement at the **registration boundary**, never at the call site.
- **Manifest hash drives re-prompt** (`grant_hash = sha256(capabilities_set)`).
- **v5 → v6 is additive only.** Three new tables + two NULLABLE columns + one index.
- **Bounded `asyncio.wait_for(start, timeout=2.0)`** on every plugin lifecycle hook.
- **`plugin_name` column added to both `llm_calls` and `tool_invocations`.**

### Critical Pitfalls

The four highest-stakes pitfalls condensed. See PITFALLS.md for the full twelve.

1. **Default-allow capability grants normalize compromise (Pitfall 1).** In-process plugin code is arbitrary code execution; v0.5 defers OS sandboxing. **Avoid:** `DEFAULT_GRANT_POLICY = "deny"`; helper shims raise `PermissionDenied` if grant row missing; closed enum in `capability_catalog.py`; mandatory `docs/PLUGIN-SECURITY.md`.
2. **Silent capability expansion on plugin upgrade (Pitfall 5).** v1.0 grants don't carry to v1.1 if v1.1 widens the requested set. **Avoid:** grants keyed on `(plugin_name, plugin_version, capability)` AND tied to `manifest_hash`; three diff outcomes (unchanged auto / reduced auto / expanded re-prompt).
3. **`pip install` corrupts the host venv (Pitfall 4).** Six concrete failure shapes including `setup.py` arbitrary code execution, `.pth`-file persistent execution, dependency downgrade breaking horus-os itself. **Avoid:** refuse install outside a venv (`sys.prefix == sys.base_prefix` check); **two-phase install** (`pip download --no-deps` → validate → install `--no-build-isolation`); refuse sdist by default; refuse `.pth` files in wheel RECORD; refuse runtime-dep downgrade.
4. **Plugin failures crash horus-os instead of degrading (Pitfall 6).** v0.3 `server/api.py:99-116` wraps `start/stop` in try/except but **without a timeout**. **Avoid:** wrap every lifecycle boundary; **bounded `asyncio.wait_for(start, timeout=2.0)`**; `--disable-all-plugins` CLI escape hatch.

Two more that earn their own phase ownership:

5. **Manifest schema drift (Pitfall 2).** `manifest_version: int` required from day one; unknown fields warn but never refuse; additive-only future-compat rule encoded as a `tests/fixtures/manifest_v1_minimum.toml` round-trip test.
6. **Entry-point discovery API drift + `pkg_resources` cost (Pitfall 3).** `importlib.metadata.entry_points(group=...)` keyword-arg API only; lint-ban `pkg_resources`; cold-start <100ms benchmark.

## Implications for Roadmap

### Single recommended phase decomposition

**Adopt the 11-phase decomposition (Phases 40-50).** ARCH.md proposes 8 work-items; PITFALLS.md proposes 11 phases. They converge: ARCH's 8 work-items collapse cleanly into Phases 41-49 with Phase 40 (baseline) and Phase 50 (release) as the GSD bookends v0.4 also used. Splitting docs/tests/reference/gate into their own phases (vs. folding into feature phases) prevents the Pitfall 12 docs-drift trap.

**Phase 40** — v0.5 baseline artifact (mirror of v0.4 Phase 32). Pure infrastructure: snapshot v0.4 cold-start perf so a future plugin-discovery-overhead benchmark has a pinned reference.

**Phase 41** — Manifest schema + persistence + public API surface. `plugins/spec.py`, `plugins/manifest.py`, `MANIFEST_V1_SCHEMA`, `plugins/api.py`, `capability_catalog.py`, v5→v6 additive migration. Addresses MANIFEST-01..05, OBSERVE-01 (schema half), MIG-05. Avoids Pitfalls 2, 7, 8, 9, 12.

**Phase 42** — Discovery + loading + failure isolation. `plugins/discovery.py`, `plugins/loader.py` (guard stubbed pass-through), `plugins/registry.py`, ruff ban on `pkg_resources`, cold-start benchmark, 3.11+3.12 parametrized discovery test. Avoids Pitfalls 3, 6 (discover+load half).

**Phase 43** — Permission model + bounded lifecycle. `plugins/permissions.py`, helper shims (`ctx.filesystem`, `ctx.secrets`, `ctx.net`, `ctx.process`, `ctx.env`), per-version grants + `manifest_hash` tie, `asyncio.wait_for(start, timeout=2.0)`, `plugin_capability_grants_log` audit table. Avoids Pitfalls 1, 5, 6 (bounded-lifecycle half), 10.

**Phase 44** — Installer flow (two-phase install + upgrade diff). `cli/plugins_cmd.py` with `install/uninstall/list/info/enable/disable/update/grant/revoke`. `subprocess.check_call([sys.executable, "-m", "pip", "install", "--require-virtualenv", spec])`. Two-phase: download → validate → install `--no-build-isolation`. Upgrade-with-diff: unchanged auto / reduced auto / expanded re-prompt. Avoids Pitfalls 4, 5, 10.

**Phase 45** — REST API + dashboard plugins tab. Six `/api/plugins` routes; `/plugins` dashboard tab; `/api/observability/plugins` route; dashboard rollup tile on `/observability`. Addresses DASH-01..03, OBSERVE-01 (read path). Avoids Pitfalls 5, 7, 10.

**Phase 46** — Test surface (three-tier fixtures + pitfall regression tests). `fake_plugin_entry_points` monkeypatch fixture; `clean_venv` fixture (opt-in via `@pytest.mark.installer_e2e`); `tests/test_plugin_pitfalls/` with one test per pitfall; broken-plugin fixtures. Avoids Pitfall 11.

**Phase 47** — Documentation refresh (docs trio). `docs/PLUGINS.md`, `docs/PLUGIN-SECURITY.md` (Threat Model section), `docs/MIGRATION-v0.4-to-v0.5.md`. Docs-build step diffs `MANIFEST_V1_SCHEMA` runtime vs. `docs/manifest-v1.schema.json`. Avoids Pitfalls 1, 12.

**Phase 48** — Reference plugin (`horus-os-example-plugin`). Separate package at `examples/horus-os-example-plugin/`; four scenarios (simple tool + capability, config-reading tool, lifecycle adapter, two-tools-one-adapter). CI lint rejects any `from horus_os` import not from `horus_os.plugins.api`. CI runs `pip install -e ./examples/horus-os-example-plugin` and asserts plugin appears in `/api/plugins`. Avoids Pitfall 8.

**Phase 49** — Three-OS install gate + release-gate extension. `scripts/release_gate.py` gains docs-drift check, plugin install-smoke on each OS, manifest schema-in-docs equality with runtime constant, reference plugin manifest validates, v0.4 fixture round-trip survives v5→v6.

**Phase 50** — v0.5.0 release. Tag, CHANGELOG, GitHub Release with migration notes.

**Phase ordering rationale:**

- **Schema before behavior.** Phase 41's `PluginSpec`, `MANIFEST_V1_SCHEMA`, `plugins/api.py`, and v5→v6 migration are consumed by every later phase.
- **Discovery + load before permissions.** Permission model needs the database from Phase 41 and the registry from Phase 42; the loader can run without permission enforcement during Phase 42 (guard stubbed).
- **Installer before dashboard.** The CLI is the test substrate for the API. The dashboard is the second consumer.
- **Tests + docs + reference + gate in their own phases**, not folded into prior phases (v0.4 lesson: docs slip when folded).
- **Phase 44 ∥ Phase 45 is the only legitimate parallelism** once Phase 43 ships (mirrors v0.4's Phase 36 ∥ 37). Everything else has hard dependencies.

### Research flags for plan time

- **Phase 41:** pydantic v2 error-formatting UX for plugin authors, JSON-Schema export, exact SQLite `ADD COLUMN` idempotency pattern.
- **Phase 44:** `pip download --no-deps --report -` JSON shape across pip versions, `.pth`-file detection inside wheel RECORD, cross-OS path normalization, Windows line-ending sensitivity on `pip freeze` round-trip.
- **Phase 49:** Windows + Python Microsoft Store path quirks; synthetic broken-plugin install test on macOS arm64, Ubuntu, Windows.

**Phases with standard patterns (skip research-phase):** 40, 42, 43, 45, 46, 47, 48, 50.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All verified against stdlib docs, PyPI, pip user guide; two new deps current as of 2026-04/05. |
| Features | HIGH | Cross-verified across Datasette, pytest, Home Assistant, Sphinx, JupyterLab, VS Code. |
| Architecture | HIGH | Direct line-of-sight to existing v0.1-v0.4 source; six-phase pipeline internally consistent. |
| Pitfalls | HIGH | Twelve pitfalls verified against named source incidents (Wiz LiteLLM TeamPCP 2025, Checkmarx Command-Jacking, CPython 3.10/3.11/3.12 docs). |

**Overall confidence:** HIGH. Ready for requirements + roadmap.

### Gaps to address at plan time

- Pydantic error formatting UX (Phase 41 fixture).
- `.pth`-file detection inside wheel before install (Phase 44 spike).
- `pip download --report -` JSON output stability across pip versions (Phase 44 floor pin).
- Capability catalog plain-English copy (Phase 41 draft, Phase 47 refine).
- Per-plugin LLM cost attribution OBSERVE-02 (Phase 41 30-min spike).
- Resolve `horus_os_compat` (PEP 440 SpecifierSet) vs `min_horus_os_version` (raw string) — recommendation: `horus_os_compat`.

---
*Research completed: 2026-05-26*
*Ready for roadmap: yes*
