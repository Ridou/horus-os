# Stack Research

**Domain:** Python plugin system for a local-first, single-process AI command center (horus-os v0.5 milestone)
**Researched:** 2026-05-26
**Confidence:** HIGH

Scope is intentionally narrow. The existing horus-os runtime contract is already settled (Python 3.11+, FastAPI, SQLite/aiosqlite, Anthropic/Gemini SDKs, Next.js dashboard, Apache 2.0, existing `ToolRegistry` and `AdapterRegistry`). This document covers only the additions needed to declare, discover, validate, install, and isolate third-party plugins on top of those contracts.

## Existing primitives v0.5 builds on

These are already in tree at v0.4.0 and the plugin system extends them rather than replaces them:

- `horus_os.adapters.base.discover_adapters()` — entry-point walker over group `horus_os.adapters`, swallowing per-entry exceptions so one broken adapter does not kill startup. Already uses `importlib.metadata.entry_points` (src/horus_os/adapters/base.py:217). The v0.5 plugin loader follows the same swallow-and-skip pattern.
- `AdapterRegistry` — per-FastAPI-app status tracker with `register`, `mark_running`, `mark_stopped`, `mark_error`, `touch` (src/horus_os/adapters/base.py:59). The plugin system reuses this for adapter-providing plugins, and mirrors the same lifecycle shape for tool-providing plugins.
- `ToolRegistry` — duplicate-safe in-memory tool map keyed by name with `register/unregister/invoke` (src/horus_os/tools/registry.py:16). Plugins call `register(tool)` during their load hook; the existing `replace=False` semantics give v0.5 free protection against two plugins claiming the same tool name.
- SQLite (WAL mode, additive migrations via `CREATE TABLE IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS`) — already the only persistence layer. Capability grants land in a new additive table; no v0.4 on-disk database becomes unreadable.
- Entry-point group convention — `horus_os.adapters` already exists. v0.5 adds a sibling group `horus_os.plugins` so plugins that ship both tools and adapters can be declared in one place.

## Recommended Stack

### Core Technologies (all stdlib; no new runtime deps)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `tomllib` | stdlib (Python 3.11+) | Read `horus-plugin.toml` manifest | Already shipped in stdlib, zero new dep. horus-os already pins `requires-python = ">=3.11"` (pyproject.toml:10), so the conditional `tomli` fallback used by older projects is not needed. Must open files in `"rb"` binary mode, `tomllib.load()` enforces UTF-8 + no universal newlines, which is the spec-correct way to read TOML. |
| `importlib.metadata` | stdlib (Python 3.11+) | Discover plugins via entry-point group | Canonical replacement for the deprecated `pkg_resources`. The exact call is `entry_points(group="horus_os.plugins")` returning an `EntryPoints` collection (each `EntryPoint` exposes `.name`, `.value`, `.load()`, `.dist`). Already used by `discover_adapters()` so v0.5 inherits the same swallow-on-failure pattern. The `dist` attribute is critical, it gives plugin version and installed-package name without re-parsing entry_points twice. |
| `importlib.util` + `importlib.machinery` | stdlib | Load plugin modules from the local `~/.horus-os/plugins/` directory (dev plugins not installed via pip) | The directory-mode loader walks each subdirectory for a `horus-plugin.toml` manifest, then uses `spec_from_file_location` + `module_from_spec` + `exec_module` to import the plugin entry module. Pure stdlib, deterministic, no `sys.path` mutation needed if the spec carries `submodule_search_locations`. |
| `subprocess` | stdlib | Wrap `pip install` / `pip uninstall` / `pip show` for the installer flow | The pip project explicitly forbids `import pip`, pip "assumes that once it has finished its work, the process will terminate" and is not thread-safe. The only supported pattern is `subprocess.check_call([sys.executable, "-m", "pip", "install", spec])`. Using `sys.executable` (not the literal string `"python"`) makes the call work inside venvs and on Windows where the venv `python.exe` is in a different folder. |
| `pathlib.Path` | stdlib | All filesystem paths (manifest discovery, local plugins dir, cache locations) | Already the convention in horus-os (`Path` used in `AdapterContext.data_dir`). Keeps cross-OS behavior (the three-OS hard gate at REL-08) free of `os.path.join` ambiguity. |
| `hashlib` | stdlib | Optional plugin manifest checksum for the "this plugin's capabilities changed since last grant" check | The grant model in PROJECT.md requires "never silently re-granted across plugin upgrades that change the requested set." Hashing the capabilities array from the manifest gives an O(1) check against the persisted grant hash. SHA-256 is fine; no security claim, just change detection. |

### Supporting Libraries (new direct deps)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `packaging` | `>=24.0` (current latest at research time: 26.2, released 2026-04-24, calendar-versioned `YY.N`) | `packaging.specifiers.SpecifierSet` for the `horus_os_compat` field in the manifest; `packaging.requirements.Requirement` to parse the pip spec the user passes to `horus-os plugins install <spec>` before handing it to pip | This is the only library in the Python packaging ecosystem that correctly implements PEP 440 version specifiers (`~=`, `>=`, `<`, `!=`, `===`, `==`, `>`). Hand-rolling this is a known pitfall, semver libs misparse PEP 440's `~=` compatible-release operator. Pin `>=24.0` for the stable `Specifier`/`SpecifierSet`/`Version` API surface. Lowercased min keeps the `[dev]` extra cheap; pip already ships `packaging` transitively so most installs already have a compatible version. |
| `pydantic` | `>=2.7,<3` (current latest at research time: 2.13.4, released 2026-05-06; Python 3.9+) | Manifest schema validation: parse `horus-plugin.toml` into a typed `PluginManifest` model, fail loudly with clean error messages before activation | `pydantic` v2 is the right tool here, not v1, the Rust core is fast enough to validate every plugin manifest on every startup without measurable overhead, error messages are structured (`pydantic.ValidationError.errors()` returns a list of dicts the installer can render directly to the user), and v2's `model_validate` is the canonical entry point. Cap below `3` to avoid the inevitable v3 break. Floor at `>=2.7` because that's the line where `model_validate` and `BaseModel` semantics stabilized. **Note:** pydantic is NOT yet in the tree at v0.4 (see pyproject.toml:24, `dependencies = []`); v0.5 introduces it. That is a deliberate dependency addition justified by manifest validation, NOT a sneak, call it out in REL-10 release notes. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `pip --dry-run` | Preflight an install spec before activating it, surface the resolved version + transitive deps to the user before they confirm | Available since pip 22.2. Use in the installer's "preview" step: `pip install --dry-run --report -` returns a JSON report on stdout the installer parses to show the user "this will install plugin X version Y plus N transitive deps" without actually mutating the venv. |
| `pip show` | Read the installed plugin's `Location`, `Version`, `Name` after install to confirm the entry-point landed in the active venv | Pairs with the `EntryPoint.dist` data from `importlib.metadata` for the dashboard plugins-tab "installed at" column. |
| `pip uninstall -y` | Remove a plugin without an interactive prompt | The `-y` matters, the installer is being driven by the dashboard/CLI; an interactive `yes/no` prompt would hang the subprocess. |
| Plugin scaffold via in-repo example | Reference plugin (`horus-os-example-plugin`) committed as a sibling directory in the horus-os repo at `examples/horus-os-example-plugin/` | No template engine needed, the example IS the template. Users `cp -r examples/horus-os-example-plugin/ my-plugin/`, edit `pyproject.toml` and `horus-plugin.toml`, run `pip install -e .` into their horus-os venv. Keeps the contract reference and the working example as one artifact. |

## Installation

```bash
# Core (new in v0.5)
pip install "packaging>=24.0" "pydantic>=2.7,<3"

# All other deps remain v0.4 baseline. No new optional extras.
```

In `pyproject.toml`, these go in the **base** `dependencies` list, not an optional extra. Every horus-os install must be able to validate a plugin manifest, otherwise a freshly-installed third-party plugin would fail differently for users with/without an extra installed. Concretely:

```toml
[project]
dependencies = [
    "packaging>=24.0",
    "pydantic>=2.7,<3",
]
```

The v0.4 `dependencies = []` line (pyproject.toml:24) is preserved-by-replacement: those two libraries are the only base runtime deps the project gains in v0.5. Everything else (`anthropic`, `google-genai`, `fastapi`, `discord.py`, etc.) stays under `[project.optional-dependencies]` as it is today.

## Manifest format, concrete schema

For downstream consumers (requirements + roadmapper), the manifest schema is anchored here so phase plans can reference it. Plugins ship a `horus-plugin.toml` at package root:

```toml
[plugin]
name = "example-weather"             # unique, lowercase, hyphen-separated; matches PyPI dist name when published
version = "0.1.0"                    # PEP 440 version of THIS plugin (not horus-os)
description = "Brief one-liner shown in dashboard"
horus_os_compat = ">=0.5,<0.6"       # SpecifierSet validated via packaging.specifiers
entry_point = "example_weather.plugin:Plugin"  # module:attr resolved via importlib

[plugin.capabilities]
"filesystem.read" = ["~/Documents/weather"]   # path globs, declarative
"net.outbound" = ["api.weather.example"]      # hostnames, declarative
"secrets.read" = ["WEATHER_API_KEY"]          # env-var names, declarative

[[plugin.tools]]
name = "get_weather"
description = "Look up forecast for a city"

[[plugin.adapters]]
name = "weather_webhook"
```

Loaded into a pydantic `PluginManifest` model. Failed validation raises `pydantic.ValidationError`, the installer catches it and renders the structured errors to the user, never aborts silently.

## Integration with existing horus-os primitives

This is the part where v0.5 either feels like a natural extension or a parallel system. The deliberate choice is "natural extension":

1. **Entry-point group `horus_os.plugins` is a SIBLING of `horus_os.adapters`**, not a replacement. A plugin's `entry_point` resolves to a `Plugin` object (new contract) whose `register(context: PluginContext) -> None` method calls into the existing `ToolRegistry.register()` and (for adapter-providing plugins) the existing `AdapterRegistry.register()`. Built-in adapters keep using `horus_os.adapters` unchanged, zero refactor of v0.3 adapters.
2. **The new `PluginContext`** carries `tool_registry: ToolRegistry`, `adapter_registry: AdapterRegistry`, `data_dir: Path`, `config: Config`, `grants: dict[str, list[str]]` (the persisted capability grants, declarative, plugin code reads them, no enforcement layer in v0.5 per the OS-isolation anti-goal). This mirrors `AdapterContext` (src/horus_os/adapters/base.py:120) so the cognitive load on plugin authors who already wrote a v0.3 adapter is near zero.
3. **The discovery walker reuses the same exception-swallow pattern** as `discover_adapters` (src/horus_os/adapters/base.py:217-235). A bad plugin entry point is logged + recorded in the new SQLite `plugin_errors` table, then skipped. The dashboard plugins tab surfaces these via the v0.4 ObservationBus, fulfilling the "failure isolation" target feature.
4. **Capability grants in SQLite** use an additive table:
   ```sql
   CREATE TABLE IF NOT EXISTS plugin_grants (
     plugin_name TEXT NOT NULL,
     capability  TEXT NOT NULL,
     granted_at  TEXT NOT NULL,
     grant_hash  TEXT NOT NULL,   -- sha256 of the capabilities subset granted
     PRIMARY KEY (plugin_name, capability)
   );
   ```
   The `grant_hash` field is what the PROJECT.md "never silently re-granted across plugin upgrades that change the requested set" rule keys on: on upgrade, hash the new manifest's capability set, compare to the stored hash, prompt the user again if they differ.
5. **The reference example plugin lives in-repo** at `examples/horus-os-example-plugin/` with its own `pyproject.toml` that depends on `horus-os` and declares `[project.entry-points."horus_os.plugins"] example = "horus_os_example.plugin:Plugin"`. CI installs it via `pip install -e examples/horus-os-example-plugin/` and the contract test in `tests/plugins/test_reference_plugin.py` asserts the registered tool actually runs.

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `pydantic>=2.7` for manifest validation | `msgspec` | Sub-millisecond validation matters more than ecosystem familiarity. For horus-os it doesn't, manifest validation runs once per plugin per startup, and pydantic's ecosystem familiarity (FastAPI users know it) wins. |
| `pydantic>=2.7` for manifest validation | `dataclasses` + hand-rolled validation | Project wants zero new deps at all costs. For horus-os the discipline cost (every plugin-author error message hand-formatted, every nested-list-of-dict shape hand-checked) is not worth saving one ~10MB dependency. |
| `pydantic>=2.7` for manifest validation | `jsonschema` | Manifest is canonically JSON-Schema'd and shared with non-Python tooling. v0.5 is Python-only, so pydantic's Python-native ergonomics win and the `model_json_schema()` method gives a JSON Schema export for free if v0.6 ever wants one. |
| `subprocess` to `sys.executable -m pip` | `import pip` and call `pip._internal` | NEVER. pip explicitly documents this as unsupported, pip "assumes once it has finished its work, the process will terminate," is not thread-safe, and reserves the right to break any internal API across releases. |
| `subprocess` to `sys.executable -m pip` | `uv` as the installer backend | Speed matters more than ubiquity. For v0.5 we ship to users who have only `pip` (the Python interpreter's batteries), requiring `uv` would add a setup step. Revisit at v0.7 when uv adoption is broader. |
| `importlib.metadata.entry_points(group=...)` | `pluggy` | Hook-style fan-out where many plugins respond to the same named hook (`pytest`'s model). horus-os has a 1-plugin-registers-N-tools-and-adapters shape, pluggy adds HookSpec/HookImpl ceremony for zero benefit. |
| `importlib.metadata.entry_points(group=...)` | `stevedore` | Need OpenStack-style driver enums with single-entry-point-per-name selection (e.g., "pick one storage backend out of N"). horus-os plugins are additive, not exclusive, multiple weather plugins can coexist. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `pkg_resources` (from `setuptools`) | Officially superseded by `importlib.metadata`. Slow (parses every `*.dist-info/entry_points.txt` on import), deprecated by PyPA, will eventually disappear from default setuptools. The existing horus-os `discover_adapters` already uses `importlib.metadata`, using `pkg_resources` in v0.5 would be a regression. | `from importlib.metadata import entry_points; entry_points(group="horus_os.plugins")` |
| `pluggy` | Designed for hook-style plugin systems where many plugins respond to the same well-known hook names (pytest, tox). horus-os plugins register concrete tools and adapters by unique name into existing registries, adding pluggy's `HookspecMarker`/`HookimplMarker`/`PluginManager` layer means three more abstractions for plugin authors to learn for zero new capability. Pluggy is ~5K LOC of indirection horus-os does not need. | The existing `ToolRegistry.register()` + `AdapterRegistry.register()` direct-call model. |
| `stevedore` | OpenStack-grade plugin manager (DriverManager, ExtensionManager, NamedExtensionManager, HookManager, EnabledExtensionManager, six manager classes). The horus-os contract is "load all discovered plugins, let each register multiple tools/adapters, swallow per-plugin failures." Stevedore is a 10x-bigger surface than that. | The custom 50-line `discover_plugins()` walker that mirrors `discover_adapters()`. |
| `import pip` + `pip._internal.main()` | Pip explicitly forbids this. Not thread-safe, mutates global state (logging, stdout), assumes the process exits after the call. Even on success the second invocation in the same process behaves nondeterministically. | `subprocess.check_call([sys.executable, "-m", "pip", "install", spec])` |
| `tomli` (the third-party TOML parser) | Was the right answer on Python 3.7-3.10. horus-os requires Python 3.11+ where `tomllib` is in stdlib (it's literally the same code, `tomllib` was upstreamed from `tomli`). Adding `tomli` would be a useless dep. | `import tomllib; with open(path, "rb") as f: data = tomllib.load(f)` |
| `tomlkit` (TOML round-trip parser preserving comments/formatting) | v0.5 never WRITES the plugin manifest, third-party authors edit it by hand. tomlkit's round-trip features are dead weight when horus-os only reads. | `tomllib` (read-only is the right shape) |
| Heavy schema layers (`marshmallow`, `attrs` + `cattrs`, `voluptuous`) | All three predate pydantic v2's Rust core and lose on every axis that matters here (perf, error-message quality, json-schema export, ecosystem familiarity with FastAPI users). | `pydantic>=2.7` |
| HTTP plugin catalog (anything that talks to a remote index of plugins) | Out of scope at v0.5 per PROJECT.md "Out of Scope" line 88. v0.5 plugin discovery is `pip install <pypi-spec>` and a local directory, no catalog server, no remote signing, no remote ratings. | Defer to v0.6+ when there's real-world adoption data justifying the surface area. |
| OS-level sandboxing libs (`firejail`, `nsjail` Python wrappers, `subprocess` w/ `seccomp`, `RestrictedPython`) | Out of scope at v0.5 per PROJECT.md "Out of Scope" line 89. v0.5 capability model is declarative, plugins state what they need, users grant or deny, but enforcement is by convention not by OS isolation. Adding any of these triples the cross-OS test matrix (these libs all have macOS/Windows gaps). | Defer to v0.6+ if abuse actually warrants it. PROJECT.md is explicit this is a "v0.6+ consideration if real-world abuse warrants it." |
| pip's `--user` flag in the installer | Conflicts with venv installs. horus-os runs inside the user's venv by convention; `pip install --user <plugin>` lands the plugin in `~/.local` instead of the venv, where the venv's `importlib.metadata.entry_points` cannot see it. The plugin appears to install successfully then mysteriously does not load. | Plain `subprocess.check_call([sys.executable, "-m", "pip", "install", spec])`, `sys.executable` already encodes the active venv. |
| `pip install --target <dir>` for the local-plugins-dir flow | `--target` is for installing into a non-`site-packages` location, which means the result is invisible to `importlib.metadata` unless `sys.path` is manually mutated. That defeats the entry-point discovery model. | Two-mode loader: (a) `pip install <spec>` for installed plugins (entry points work natively), (b) a `~/.horus-os/plugins/<name>/` directory loader that reads the manifest and uses `importlib.util.spec_from_file_location` directly (no `sys.path` mutation needed). |
| Custom version-parsing logic for `horus_os_compat` | PEP 440 has six operators (`==`, `!=`, `<`, `<=`, `>`, `>=`, `~=`, `===`); the `~=` compatible-release operator is famously misparsed by semver libs. Hand-rolling this is a guaranteed source of bug reports six months in. | `packaging.specifiers.SpecifierSet` parses + checks correctly the first time. |

## Stack Patterns by Variant

**Plugin shipped via PyPI (the canonical path):**
- Author writes a `pyproject.toml` with `[project.entry-points."horus_os.plugins"] name = "pkg.mod:Plugin"`.
- Ships a `horus-plugin.toml` at the package data root.
- User runs `horus-os plugins install <pypi-name>` → wraps `pip install <pypi-name>` → manifest validated → capabilities prompted → grants persisted → next FastAPI startup auto-discovers via `entry_points(group="horus_os.plugins")`.

**Plugin shipped as a local directory (dev workflow):**
- Developer drops the plugin source at `~/.horus-os/plugins/my-plugin/` with a `horus-plugin.toml` and a single `plugin.py`.
- Discovery walker scans the directory, reads each manifest, loads each plugin module via `importlib.util.spec_from_file_location` directly (no `pip install` step, no entry point needed).
- Useful for plugin authors iterating before publishing to PyPI; useful for users running un-published forks.

**Plugin disabled by the user from the dashboard:**
- Dashboard toggles `enabled=false` in SQLite.
- On next startup, the discovery walker skips disabled plugins entirely, does not load, does not call `register()`, no side effects. (Compare to v0.3 adapters where disable means "stop the lifecycle but keep the bind." For plugins, disable means "don't even load.")

**Plugin upgrade with changed capabilities:**
- Installer re-runs `pip install --upgrade <spec>`, re-parses the manifest, hashes the capabilities set, compares to persisted `grant_hash`.
- If equal: silent upgrade, no re-prompt.
- If different: re-prompt user, persist new `grant_hash` only after consent.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `pydantic>=2.7,<3` | Python 3.11+ | Pydantic 2.x supports Python 3.9+, so the v0.5 floor of 3.11 is comfortably inside the supported range. The v3 cap is conventional defensive pinning, pydantic v3 is not yet announced but the major-version-break habit is well-established. |
| `packaging>=24.0` | All supported Python 3.11+ | calendar-versioned `YY.N` since 22.0. Current latest is `26.2` (2026-04-24). Pin a floor (`>=24.0`) for stable `SpecifierSet`/`Version` API; no upper cap needed, packaging maintains tight backward compat for these specific public APIs. |
| `tomllib` (stdlib) | Python 3.11+ | Read-only. For Python 3.10 and below `tomli` is the back-compat dep but horus-os does not target 3.10 so this is moot. |
| `importlib.metadata` (stdlib) | Python 3.11+ | The `entry_points(group=...)` keyword-arg signature is stable from 3.10 onward (3.9 used positional). horus-os targeting 3.11+ means the keyword-arg signature is always available, no version sniffing needed. |
| `pip` (system) | `>=22.2` for `--dry-run --report -` | The dry-run-with-report JSON output landed in pip 22.2. Most users have a newer pip than this already; the installer should still version-check and fall back to a `pip install` without preview if it sees old pip (rare, log a warning). |
| Reference example plugin | `horus-os>=0.5,<0.6` in its own `horus_os_compat` | The example is the contract reference, its manifest demonstrates the exact `horus_os_compat` syntax third-party authors will copy. Bumping the example's compat range when horus-os ships v0.6 IS the migration test. |

## Sources

- [packaging Python documentation, entry points discovery](https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/) — verified canonical `importlib.metadata.entry_points(group=...)` pattern, deprecation of `pkg_resources`. HIGH confidence.
- [Python stdlib docs, `importlib.metadata`](https://docs.python.org/3.12/library/importlib.metadata.html) — verified `EntryPoints` collection API (`.groups`, `.select()`, `.names`), `EntryPoint.load()` and `EntryPoint.dist`. HIGH confidence.
- [pip user guide, "Using pip from your program"](https://pip.pypa.io/en/stable/user_guide/#using-pip-from-your-program) — verified pip's explicit ban on `import pip`, official `subprocess.check_call([sys.executable, '-m', 'pip', ...])` recommendation, "pip assumes the process terminates after invocation" + not thread-safe. HIGH confidence.
- [pip CLI reference, install options](https://pip.pypa.io/en/stable/cli/pip_install/) — verified `--dry-run`, `--no-deps`, `--target` semantics. Note `--isolated` was not in the fetched doc subset; cross-referenced via separate `pip install --help` knowledge. MEDIUM-HIGH confidence.
- [PyPI, pydantic project page](https://pypi.org/project/pydantic/) — verified latest 2.13.4 released 2026-05-06, Python 3.9+ floor. HIGH confidence.
- [PyPI, packaging project page](https://pypi.org/project/packaging/) — verified latest 26.2 released 2026-04-24, Python 3.8+ floor, calendar-versioned. HIGH confidence.
- [packaging, version specifiers spec](https://packaging.python.org/en/latest/specifications/version-specifiers/) — verified the six PEP 440 operators (`==`, `!=`, `<=`, `<`, `>=`, `>`, `~=`, `===`), `~=` compatible-release semantics. HIGH confidence.
- [Python stdlib docs, `tomllib`](https://docs.python.org/3/library/tomllib.html) — verified `tomllib.load(f)` requires binary-mode file object, parses TOML 1.0.0, no write support. HIGH confidence.
- [GitHub, pytest-dev/pluggy](https://github.com/pytest-dev/pluggy) — verified pluggy is a hook-style plugin manager (pytest model), latest 1.6.0 (2025-05). The hook-style fit is wrong for horus-os; documented why above. HIGH confidence.
- [GitHub, openstack/stevedore](https://github.com/openstack/stevedore) — verified stevedore is OpenStack's setuptools-entry-points manager with multiple Manager flavors; surface area is larger than horus-os needs. HIGH confidence.
- [Sedimental, Plugin Systems survey](https://sedimental.org/plugin_systems.html) — context on the landscape (custom internal plugin systems are common and often better-factored than third-party frameworks). MEDIUM confidence.
- Existing horus-os source as primary evidence:
  - `/Users/santino/Projects/horus-os/src/horus_os/adapters/base.py` (entry-point walker, AdapterRegistry, AdapterContext shapes that v0.5 mirrors).
  - `/Users/santino/Projects/horus-os/src/horus_os/tools/registry.py` (ToolRegistry contract plugins call into).
  - `/Users/santino/Projects/horus-os/pyproject.toml` (current deps = none, v0.5 adds packaging + pydantic to base).

*Stack research for: horus-os v0.5 plugin system additions on top of an established Python 3.11+ FastAPI/SQLite/Anthropic-Gemini runtime.*
*Researched: 2026-05-26*
