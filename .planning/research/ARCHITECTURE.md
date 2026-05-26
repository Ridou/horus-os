# Architecture Research

**Domain:** v0.5 Plugin System — in-process third-party plugin loading with declared capabilities
**Researched:** 2026-05-26
**Confidence:** HIGH

This file is the integration blueprint for v0.5. It assumes the reader has read PROJECT.md and ROADMAP.md and is familiar with the AdapterRegistry (Phase 22), the ToolRegistry (Phase 04), the ObservationBus (Phase 32), and the lazy-import pattern used by `OtelAdapter` (Phase 38). It maps every new component to a file path, every integration point to a named method, and proposes a strict build order with named dependencies.

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  CLI / DASHBOARD SURFACE                                                     │
│  ┌───────────────────────────┐  ┌────────────────────────────────────────┐   │
│  │ horus-os plugins install  │  │ /plugins dashboard tab                 │   │
│  │ horus-os plugins list     │  │ list / enable / disable / grant        │   │
│  │ horus-os plugins enable   │  │ status, error count, capability chips  │   │
│  └─────────────┬─────────────┘  └────────────────┬───────────────────────┘   │
│                │                                   │                          │
├────────────────┼───────────────────────────────────┼─────────────────────────┤
│  API LAYER (FastAPI on app.state)                  │                          │
│  ┌─────────────▼───────────────────────────────────▼───────────────────────┐ │
│  │  /api/plugins  (GET list, GET :name, POST :name/enable, /disable,      │ │
│  │  POST :name/grant, DELETE :name/grant/:capability)                     │ │
│  └─────────────┬───────────────────────────────────────────────────────────┘ │
├────────────────┼───────────────────────────────────────────────────────────────┤
│  PLUGIN RUNTIME (new — src/horus_os/plugins/)                                │
│  ┌─────────────▼───────────────────────────────────────────────────────────┐ │
│  │ PluginRegistry  (app.state.plugin_registry — sibling of adapter_registry│ │
│  │                  and tool_registry; PluginEntry rows)                   │ │
│  └─────┬──────────────────────────────┬──────────────────────────────┬────┘ │
│        │                              │                              │      │
│  ┌─────▼─────┐                  ┌─────▼─────┐                  ┌─────▼─────┐│
│  │ Discoverer│                  │ Validator │                  │ Permission││
│  │  EP scan +│                  │ manifest +│                  │  Gate     ││
│  │  fs scan  │                  │ compat +  │                  │  grant    ││
│  │           │                  │ shape     │                  │  check    ││
│  └─────┬─────┘                  └─────┬─────┘                  └─────┬─────┘│
│        │                              │                              │      │
│        └────────────────┬─────────────┴───────────────┬──────────────┘      │
│                         ▼                             ▼                     │
│              ┌──────────────────────┐      ┌──────────────────────┐        │
│              │ Loader               │      │ HealthSubscriber     │        │
│              │ - import entry mods  │      │ subscribes to        │        │
│              │ - register tools via │      │ ObservationBus       │        │
│              │   ToolRegistry       │      │ filters per-plugin   │        │
│              │ - register adapters  │      │ surfaces err rate /  │        │
│              │   via AdapterRegistry│      │ p95 latency          │        │
│              │ - wrap with capability│     └──────────────────────┘        │
│              │   enforcement        │                                       │
│              └─────────┬────────────┘                                       │
├────────────────────────┼──────────────────────────────────────────────────────┤
│  EXISTING REGISTRIES (reused — no API breakage)                              │
│  ┌─────────────────────▼──────┐    ┌──────────────────────────────────────┐  │
│  │ ToolRegistry (v0.1)        │    │ AdapterRegistry (v0.3)               │  │
│  │ - register(tool)           │    │ - register(name)                     │  │
│  │ - invoke(name, input)      │    │ - mark_running / mark_error / touch  │  │
│  └────────────────────────────┘    └──────────────────────────────────────┘  │
├──────────────────────────────────────────────────────────────────────────────┤
│  PERSISTENCE (schema v5 → v6)                                                 │
│  ┌──────────────────┐  ┌────────────────────────┐  ┌──────────────────────┐  │
│  │ plugins          │  │ plugin_capabilities    │  │ plugin_status        │  │
│  │ (installed list, │  │ (per-capability grant: │  │ (last_seen, error    │  │
│  │  manifest hash)  │  │  state, granted_at)    │  │  count, last_error)  │  │
│  └──────────────────┘  └────────────────────────┘  └──────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | New / Modified | Location | Responsibility |
|-----------|----------------|----------|----------------|
| `PluginSpec` (dataclass) | NEW | `src/horus_os/plugins/spec.py` | In-memory parsed manifest. One per discovered plugin. |
| `PluginEntry` (dataclass) | NEW | `src/horus_os/plugins/registry.py` | One row per plugin: name, status, last error, granted capabilities. Mirror of v0.3 `AdapterEntry`. |
| `PluginRegistry` | NEW | `src/horus_os/plugins/registry.py` | Per-app registry attached to `app.state.plugin_registry`. Mirror of v0.3 `AdapterRegistry`. |
| `discover_plugins()` | NEW | `src/horus_os/plugins/discovery.py` | Walk `entry_points(group="horus_os.plugins")` plus scan `~/.horus-os/plugins/`. Return `list[PluginSpec]`. Mirror of v0.3 `discover_adapters()`. |
| `validate_manifest()` | NEW | `src/horus_os/plugins/manifest.py` | Parse `horus-plugin.toml` via stdlib `tomllib`. Enforce field shape + horus_os_compat range. |
| `PermissionGate` | NEW | `src/horus_os/plugins/permissions.py` | Compare declared capabilities against persisted grants. Returns `(grant_state, pending_capabilities)`. |
| `CapabilityGuard` | NEW | `src/horus_os/plugins/permissions.py` | Decorator-style wrapper around plugin-provided tool handlers and adapter `bind`. Refuses calls when capability is not granted. |
| `PluginLoader` | NEW | `src/horus_os/plugins/loader.py` | Imports entry-point modules. Threads `ToolRegistry` + `AdapterRegistry` references into plugin-provided tools and adapters. Wraps them with `CapabilityGuard`. |
| `PluginHealthSubscriber` | NEW | `src/horus_os/plugins/health.py` | Subscribes to `ObservationBus`. Per-plugin error rate and latency p95 over a rolling window. Reads but never writes. |
| Schema migration v5→v6 | MODIFIED | `src/horus_os/storage.py` | Three new tables: `plugins`, `plugin_capabilities`, `plugin_status`. Additive-only. v0.4 databases keep reading. |
| `Database.{save,load,list}_plugin*` | NEW | `src/horus_os/storage.py` | CRUD for the three new tables. Same pattern as `save_profile` / `load_profile`. |
| `/api/plugins` routes | NEW | `src/horus_os/server/api.py` | List / enable / disable / grant / revoke. Reads from `app.state.plugin_registry`, writes to `Database`. |
| `/plugins` dashboard tab | NEW | `src/horus_os/server/static/index.html` + JS | Vanilla-JS, same pattern as v0.3 `/adapters` and v0.4 `/observability`. |
| `horus-os plugins` CLI | NEW | `src/horus_os/cli/plugins_cmd.py` | Subcommands: `install`, `uninstall`, `list`, `info`, `enable`, `disable`. |
| `ToolRegistry` | UNCHANGED (used as-is) | `src/horus_os/tools/registry.py` | Plugin loader calls `register(tool)` with `replace=False` default. Duplicate names rejected. |
| `AdapterRegistry` | UNCHANGED (used as-is) | `src/horus_os/adapters/base.py` | Plugin loader calls `register(name)` on plugin-provided adapters; lifespan hooks already cover `start`/`stop`. |
| `ObservationBus` | UNCHANGED (used as-is) | `src/horus_os/observability/bus.py` | `PluginHealthSubscriber.on_event` is subscribed alongside `CostAnnotator` and `SQLitePersister`. |

## Recommended Project Structure

```
src/horus_os/
├── plugins/                    # NEW — entire plugin runtime lives here
│   ├── __init__.py             # public API: discover_plugins, PluginRegistry, PluginSpec
│   ├── spec.py                 # PluginSpec dataclass (manifest in-memory)
│   ├── manifest.py             # parse horus-plugin.toml, validate, compat-check
│   ├── discovery.py            # entry_points + filesystem scan
│   ├── registry.py             # PluginRegistry + PluginEntry (mirror AdapterRegistry)
│   ├── permissions.py          # PermissionGate + CapabilityGuard
│   ├── loader.py               # import modules, register tools/adapters, wrap with guards
│   └── health.py               # PluginHealthSubscriber, subscribes to ObservationBus
├── adapters/                   # unchanged
├── tools/                      # unchanged
├── observability/              # unchanged (PluginHealthSubscriber subscribes here)
├── server/
│   └── api.py                  # MODIFIED — add /api/plugins routes + lifespan plugin wiring
├── cli/
│   ├── plugins_cmd.py          # NEW — horus-os plugins {install,uninstall,list,info,enable,disable}
│   └── __init__.py             # MODIFIED — re-export run_plugins
├── storage.py                  # MODIFIED — v5→v6 migration + plugin CRUD
└── __main__.py                 # MODIFIED — add `plugins` subparser

tests/
├── plugins/
│   ├── test_manifest.py
│   ├── test_discovery.py
│   ├── test_registry.py
│   ├── test_permissions.py
│   ├── test_loader.py
│   ├── test_loader_isolation.py    # failure containment cases
│   ├── test_health.py
│   └── fixtures/
│       ├── manifest_valid.toml
│       ├── manifest_bad_version.toml
│       └── good_plugin_pkg/        # importable test plugin (entry-point registered via conftest)
├── server/
│   └── test_api_plugins.py
└── cli/
    └── test_plugins_cmd.py

examples/
└── horus-os-example-plugin/        # reference plugin (separate package, same monorepo)
    ├── pyproject.toml              # declares entry-point `horus_os.plugins`
    ├── horus-plugin.toml           # the manifest
    ├── README.md
    └── src/horus_os_example_plugin/
        ├── __init__.py
        ├── tools.py                # echo_text tool
        └── adapter.py              # noop_webhook adapter
```

### Structure Rationale

- **`src/horus_os/plugins/` is one package, not a single file.** v0.3 put adapter discovery in one file (`adapters/base.py`); plugins are a bigger surface (discovery + manifest + permissions + loader + health) so each concern gets its own module. Mirrors the `observability/` package layout from v0.4.
- **Plugin runtime imports `tools.ToolRegistry` and `adapters.base.AdapterRegistry`, never vice versa.** One-way dependency: plugins → registries. Keeps registries reusable by core code that never knew about plugins.
- **Manifest module is pure parsing + validation, no I/O.** `manifest.py` accepts a bytes payload and returns a `PluginSpec` or raises. The filesystem read happens in `discovery.py`. Makes manifest tests synthetic-bytes-only.
- **`PluginHealthSubscriber` reads, never writes.** It subscribes to events that other subscribers (`SQLitePersister`) already persist. Doubling persistence would lie about cost. The v0.4 `tool_invocations` table already has everything needed for per-plugin rollups, identified by tool name.
- **Reference plugin lives in `examples/horus-os-example-plugin/` as a separate installable package.** Same repo, separate `pyproject.toml`. CI installs it from a path dep so the install path matches what third-party authors will use.

## Architectural Patterns

### Pattern 1: Manifest model — TOML on disk, dataclass in memory

**What:** Plugin authors write a `horus-plugin.toml`. The runtime parses it into a frozen `PluginSpec` dataclass on first discovery and stores the hash on disk for change detection.

**When to use:** Every plugin discovered via either entry-point or filesystem scan resolves through this path. There is no second manifest format.

**Trade-offs:** TOML is human-edited (good), but `tomllib` is read-only (v0.5 never writes a manifest; the CLI's `install` command runs `pip install` and lets pip stamp the entry point, no manifest mutation needed). Stdlib `tomllib` ships on Python 3.11+ so zero new deps.

**Concrete `horus-plugin.toml` fields:**

```toml
# Identity (required)
name = "horus-os-example-plugin"        # PyPI / dist name; must match entry-point dist
version = "0.1.0"                       # SemVer; the plugin's own version, not horus-os's
description = "A reference plugin demonstrating tool + adapter registration."
author = "Jane Doe <jane@example.com>"
license = "Apache-2.0"
homepage = "https://github.com/janedoe/horus-os-example-plugin"

# Compatibility (required)
horus_os_compat = ">=0.5,<0.7"          # PEP 440 range; checked at validate time

# Entry points (at least one required)
[tools]
echo_text = "horus_os_example_plugin.tools:echo_text_tool"   # dotted-path import

[adapters]
noop_webhook = "horus_os_example_plugin.adapter:NoopWebhookAdapter"

# Declared capabilities (default deny — anything not listed cannot be used)
[[capabilities]]
name = "filesystem.read"
paths = ["~/Documents/**", "/tmp/horus-*"]               # glob list, optional refinement
reason = "Reads the user's reference notes for cross-linking."

[[capabilities]]
name = "net.outbound"
hosts = ["api.example.com"]                              # host allowlist, optional
reason = "Posts a status ping every 5 minutes."

[[capabilities]]
name = "secrets.read"
keys = ["EXAMPLE_API_KEY"]                               # env-var/secret key allowlist
reason = "Authenticates against api.example.com."
```

**`PluginSpec` dataclass shape (the in-memory model):**

```python
# src/horus_os/plugins/spec.py
from dataclasses import dataclass, field

@dataclass(frozen=True)
class CapabilityRequest:
    name: str                           # e.g. "filesystem.read"
    reason: str                         # plugin-author-supplied justification (shown to user)
    paths: tuple[str, ...] = ()         # optional refinement (globs)
    hosts: tuple[str, ...] = ()         # optional refinement (host list)
    keys: tuple[str, ...] = ()          # optional refinement (env/secret keys)

@dataclass(frozen=True)
class PluginSpec:
    # Identity
    name: str
    version: str
    description: str
    author: str
    license: str
    homepage: str | None
    # Compat
    horus_os_compat: str                # PEP 440 spec string
    # Entry points (dotted paths; resolved at load time, not parse time)
    tool_entries: tuple[tuple[str, str], ...]      # ((tool_name, "pkg.mod:factory"), ...)
    adapter_entries: tuple[tuple[str, str], ...]   # ((adapter_name, "pkg.mod:Class"), ...)
    # Capabilities
    capabilities: tuple[CapabilityRequest, ...]
    # Provenance
    source: str                         # "entry_point:horus_os.plugins" or "filesystem:~/.horus-os/plugins/foo"
    manifest_hash: str                  # sha256 of manifest bytes, for change detection
```

### Pattern 2: Discovery + load pipeline as a six-phase pipeline

**What:** The lifespan handler in `server/api.py` runs the same six phases for every plugin. Each phase has a single failure mode and a single registry mutation. Phase boundaries are observable in `/api/plugins`.

**Why six phases not "one big load":** v0.3's `discover_adapters()` is one phase (find-and-instantiate) with one failure mode (silently skip). Plugins have four distinct failure modes (manifest invalid, compat mismatch, permission denied, import error) that need different error surfaces in the dashboard. A single phase would collapse all four into "broken plugin," which is exactly the UX hole v0.3 has on adapter load failures.

**The six phases, with the exact lifespan integration point:**

```python
# src/horus_os/server/api.py — inside create_app()'s _lifespan async ctx mgr
#   (runs after the v0.3 adapter start loop)

# Phase A: Discover (no side effects on registries)
plugin_specs = discover_plugins(
    extra_paths=[_resolved_data_dir.parent / ".horus-os" / "plugins"]
)
plugin_registry = PluginRegistry()

for spec in plugin_specs:
    plugin_registry.register(spec.name, spec=spec)

    # Phase B: Validate (manifest shape + horus_os_compat)
    try:
        validate_manifest(spec, current_version=__version__)
    except ValidationError as exc:
        plugin_registry.mark_error(spec.name, "validate", f"{type(exc).__name__}: {exc}")
        continue

    # Phase C: Permission gate (compare against persisted grants)
    granted, pending = PermissionGate(db).resolve(spec)
    if pending:
        plugin_registry.mark_pending_grants(spec.name, pending)
        continue   # plugin sits in "needs grant" state; not loaded

    # Phase D: Load (import entry-point modules; register tools + adapters via existing registries)
    try:
        loader = PluginLoader(
            tool_registry=_app_tool_registry,
            adapter_registry=_registry,
            guards=CapabilityGuard.for_grants(granted),
        )
        loaded = loader.load(spec)            # returns Loaded(adapters=[...], tools=[...])
        plugin_registry.mark_loaded(spec.name, loaded)
    except Exception as exc:
        plugin_registry.mark_error(spec.name, "load", f"{type(exc).__name__}: {exc}")
        continue

    # Phase E: Start (for adapter lifecycle — reuses v0.3 lifespan code)
    for adapter in loaded.adapters:
        start = getattr(adapter, "start", None)
        if start is None:
            continue
        try:
            await asyncio.wait_for(start(_adapter_context), timeout=10.0)
        except Exception as exc:
            plugin_registry.mark_error(spec.name, "start", f"{type(exc).__name__}: {exc}")

# Phase F: Health (subscribe one watcher per app, filters per-plugin)
_health = PluginHealthSubscriber(plugin_registry)
_bus.subscribe(_health.on_event)

app.state.plugin_registry = plugin_registry
```

**Trade-off:** Six explicit phases is more code than one fused load, but each phase's status is independently surfaceable in `/api/plugins`. The "explain why a plugin is not running" question that haunts every plugin system has a one-word answer from this design.

### Pattern 3: Capability enforcement at the registry boundary, not the call site

**Decision:** Wrap plugin-provided tools at registration time. Built-in tools and built-in adapters skip the wrap entirely (implicit full-grant).

**Where the wrap goes:** Inside `PluginLoader.load(spec)`, before calling `tool_registry.register(tool)`, the loader replaces `tool.handler` with a `CapabilityGuard`-wrapped handler. The same loader wraps the adapter's `bind` to refuse mount when a declared capability is not granted. By the time the tool is in the registry, every invocation already passes through the guard. `tools/loop.py` and `tools/registry.py` see no plugin-specific code.

**Why not at the call site (in `loop.py` or `registry.invoke()`):**

1. The call site doesn't know which tools came from which plugins; that mapping lives in `PluginEntry`. Threading it through changes `ToolRegistry.invoke`'s signature, which v0.4's observability hooks depend on. Wrap-at-registration keeps the v0.4 API surface byte-identical.
2. Built-ins (`read_file_tool`, the memory tools, the calendar adapter's tools) would have to be explicitly allowlisted in the call-site check. Wrap-at-registration means built-ins skip the codepath because the wrap simply isn't applied.
3. The guard naturally composes with the v0.4 cost / latency capture inside `tools/loop.py:_execute_one`: the guard is the outermost wrapper, so a refused call records `status=refused` and `error_type=CapabilityError` in `tool_invocations` without any extra plumbing.

**`CapabilityGuard` surface:**

```python
# src/horus_os/plugins/permissions.py
from typing import Callable

class CapabilityError(PermissionError):
    """Raised when a plugin tool tries to use an un-granted capability."""

class CapabilityGuard:
    def __init__(self, granted: frozenset[str]):
        self._granted = granted

    def wrap_tool_handler(self, plugin_name: str, capabilities: tuple[str, ...],
                          handler: Callable) -> Callable:
        missing = tuple(c for c in capabilities if c not in self._granted)
        if not missing:
            return handler                                # full grant — pass-through

        def _refuse(**kwargs):
            raise CapabilityError(
                f"plugin {plugin_name!r} requires {missing!r} but they are not granted; "
                f"grant via `horus-os plugins grant {plugin_name} --capability {missing[0]}`"
            )
        return _refuse

    @classmethod
    def for_grants(cls, granted: dict[str, frozenset[str]]) -> "GuardFactory":
        # Returns a per-plugin guard lookup so loader can produce one guard per plugin.
        ...
```

**Built-in tools and adapters skip this entirely:** `read_file_tool`, the memory tools, the v0.3 webhook adapter all register through the same `ToolRegistry.register` / `AdapterRegistry.register` calls they already use. The plugin loader is the only caller of `wrap_tool_handler`. Built-ins are "implicit full grant" by construction, not by allowlist.

**Persistence schema for grants (the `plugin_capabilities` table):**

```sql
CREATE TABLE IF NOT EXISTS plugin_capabilities (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    plugin_name   TEXT NOT NULL,
    capability    TEXT NOT NULL,             -- e.g. "filesystem.read"
    state         TEXT NOT NULL,             -- "granted" | "revoked" | "pending"
    refinement    TEXT,                      -- JSON of paths/hosts/keys (NULL = full grant for the capability name)
    requested_at  TEXT NOT NULL,             -- ISO-8601 UTC, when manifest first surfaced this request
    granted_at    TEXT,                      -- ISO-8601 UTC, NULL until user grants
    revoked_at    TEXT,                      -- ISO-8601 UTC, NULL unless revoked
    manifest_hash TEXT NOT NULL,             -- the manifest hash this row was last reconciled against
    UNIQUE (plugin_name, capability)
);

CREATE INDEX IF NOT EXISTS idx_plugin_capabilities_plugin
    ON plugin_capabilities(plugin_name);
```

**Manifest-hash tie is the critical UX detail:** when a plugin update changes the requested capability set, `manifest_hash` no longer matches and the row flips to `state=pending` even if it was previously granted. This implements PROJECT.md's "never silently re-granted across plugin upgrades that change the requested set."

### Pattern 4: Failure isolation by in-process catch-and-degrade

**v0.5 chooses in-process loading** (PROJECT.md "Out of Scope" explicitly defers OS-level isolation to v0.6+). The boundary is a Python `try/except` at every phase boundary plus the subscriber exception-swallow already in `ObservationBus`.

**Per-phase failure containment:**

| Phase | What can fail | Containment | Status in registry |
|-------|---------------|-------------|---------------------|
| A. Discover | importlib EP scan raises, manifest file unreadable | Wrap each EP iteration in try/except (mirror v0.3 `discover_adapters` exception swallow). Skip the broken EP, log to stderr at INFO. | Plugin never appears in `app.state.plugin_registry`; logs explain why. |
| B. Validate | `tomllib.loads` raises, compat range mismatch, unknown field, capability name not on allowlist | `ValidationError` caught in lifespan loop. Plugin registered with `status="error"`, `error_phase="validate"`, error message recorded. | `GET /api/plugins/:name` shows the validation error verbatim. |
| C. Permission gate | Database read fails, manifest hash mismatch | DB read failure crashes start (database is required). Hash mismatch is by design. Plugin sits in `status="pending"`. | `pending` state distinct from `error`; dashboard prompts the user. |
| D. Load | Entry-point import raises, factory returns wrong type, `tool_registry.register` raises `ValueError` on name conflict | Caught in lifespan loop. Plugin registered with `status="error"`, `error_phase="load"`. Any tools already registered earlier in the load are unregistered via a tracked rollback list before the next iteration. | Surfaces `error_phase="load"` + the exception message. |
| E. Start | Adapter `start(ctx)` raises or hangs | `try/except` around start; status flipped to `error`. **Hang containment:** v0.5 wraps each `start` in `asyncio.wait_for(start(ctx), timeout=10.0)`. Adapters that need more than 10s should do that work in a background task spawned from `start`, not block `start` itself. The v0.3 `DiscordAdapter` already follows this pattern. | `status="error"`, `error_phase="start"`, with an explicit `TimeoutError` message if the cap fired. |
| F. Health | Subscriber raises during `on_event` | `ObservationBus.publish` already wraps every handler with bare `try/except BaseException` (see `observability/bus.py` lines 174-181). The plugin runtime gets this isolation for free. | Errors silently absorbed; the plugin's status is unaffected by its own observability subscriber crashing. |

**Tool-invocation-time failure (not at load, at runtime):** a plugin tool that throws on invocation is caught by `tools/loop.py:_execute_one` (already-existing v0.4 capture site). The error is persisted in `tool_invocations` with `status="error"`, `error_type=type(exc).__name__`. The `PluginHealthSubscriber` reads this stream and flips `plugin_status.last_error_at` plus increments `error_count` over the rolling window. Nothing else changes. The v0.4 substrate already does the heavy lifting.

**What in-process containment does not protect against:** a plugin that imports `sys` and calls `sys.exit(1)`, or one that monkey-patches `builtins`, or one that spawns a runaway greenlet. PROJECT.md is explicit that this is acceptable for v0.5; sandboxing is v0.6+. The reference plugin and CONTRIBUTING.md will document "no `sys.exit`, no global monkey-patching, no unbounded background tasks" as conventions, not contracts.

### Pattern 5: Health rollup as a v0.4 ObservationBus consumer

**`PluginHealthSubscriber` reads `LLMCallEvent` and `ToolCallEvent` and rolls up per-plugin numbers in memory.** No new SQLite writes. The v0.4 `tool_invocations` table already records every tool call with `tool_name`, `status`, `latency_ms`. Per-plugin rollup is "which tools did this plugin register?" lookup against `PluginRegistry`, then sum.

```python
# src/horus_os/plugins/health.py
class PluginHealthSubscriber:
    def __init__(self, registry: PluginRegistry, window_seconds: int = 3600):
        self._registry = registry
        self._window = window_seconds
        # ring buffers per plugin, keyed by name
        self._samples: dict[str, deque[tuple[float, str]]] = defaultdict(deque)

    def on_event(self, event: ObservationEvent) -> None:
        if event.kind != "TOOL_CALL":
            return
        plugin_name = self._registry.plugin_for_tool(event.tool_name)
        if plugin_name is None:
            return                                          # built-in tool; ignore
        ts = time.monotonic()
        self._samples[plugin_name].append((ts, event.status))
        self._evict_old(plugin_name, ts)
        if event.status == "error":
            entry = self._registry.get(plugin_name)
            if entry is not None:
                entry.error_count += 1
                entry.last_error_at = event.created_at

    def rollup(self, plugin_name: str) -> PluginHealth: ...
```

This pattern keeps cost where it already is (SQLite), keeps the dashboard read path simple (in-memory rollup), and means the v0.4 `/api/observability/*` routes work unchanged for any user who wants the full SQL view.

## Data Flow

### Startup Sequence (FastAPI lifespan order)

```
create_app() called
    ↓
discover_adapters()                       [v0.3 — built-in adapters]
    ↓
discover_plugins()                        [v0.5 — entry points + ~/.horus-os/plugins/]
    ↓
PluginRegistry constructed
    ↓
ObservationBus subscriptions:
  1. CostAnnotator.on_event              [v0.4 — must run first]
  2. SQLitePersister.on_event            [v0.4 — persists annotated event]
  3. PluginHealthSubscriber.on_event     [v0.5 — reads only, rolls up per-plugin]
    ↓
lifespan startup:
  for adapter in built-in adapters:      [v0.3 unchanged]
      await adapter.start(ctx)
  for spec in plugin_specs:              [v0.5 NEW]
      validate → permission → load → start
    ↓
app yields to FastAPI request loop
```

### Plugin Tool Invocation Path

```
agent.run_agent_loop
    ↓
tools/loop.py:_execute_one(tool_use)     [v0.4 capture site — start perf_counter]
    ↓
ToolRegistry.invoke(name, input)         [v0.1 unchanged]
    ↓
tool.handler(**input)                    [v0.5 NEW — handler is now CapabilityGuard-wrapped]
    ├── CapabilityGuard checks granted set
    │     ├── full grant  → calls original handler
    │     └── missing cap → raises CapabilityError
    ↓
return value flows back up
    ↓
loop.py records ToolCallEvent on the ObservationBus    [v0.4 unchanged]
    ↓
PluginHealthSubscriber sees the event, rolls up        [v0.5 NEW]
```

### Permission Grant Flow (User Action)

```
User opens /plugins tab in dashboard
    ↓
GET /api/plugins                          → returns list with pending_capabilities[] highlighted
    ↓
User clicks "grant" on a capability
    ↓
POST /api/plugins/:name/grant {capability: "filesystem.read"}
    ↓
Database: UPDATE plugin_capabilities SET state='granted', granted_at=now()
    ↓
PluginRegistry.mark_grant_applied(:name, :capability)
    ↓
Response: { "name": ..., "status": "granted_pending_restart", "needs_restart": true }
```

**Restart-required is intentional for v0.5.** Hot-loading a plugin after granting is feasible (re-run phases D-E from the lifespan path) but adds a code path with surprising failure modes (capability cache mismatch, partial load state). v0.5 prompts the user to restart; v0.6 can add hot-reload once the rest of the surface is stable.

### Schema Migration v5 → v6

Additive only. Idempotent under the same `OperationalError`-suppression pattern v0.4 ships (storage.py lines 186-212).

```sql
-- v6: plugin runtime tables

CREATE TABLE IF NOT EXISTS plugins (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    version         TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    author          TEXT,
    license         TEXT,
    homepage        TEXT,
    horus_os_compat TEXT NOT NULL,
    source          TEXT NOT NULL,           -- "entry_point" | "filesystem"
    source_detail   TEXT NOT NULL,           -- "horus_os.plugins:foo" or "/abs/path"
    manifest_hash   TEXT NOT NULL,
    enabled         INTEGER NOT NULL DEFAULT 1,
    installed_at    TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_plugins_name ON plugins(name);

CREATE TABLE IF NOT EXISTS plugin_capabilities (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    plugin_name   TEXT NOT NULL,
    capability    TEXT NOT NULL,
    state         TEXT NOT NULL,             -- "granted" | "revoked" | "pending"
    refinement    TEXT,                      -- JSON of paths/hosts/keys (NULL = full grant)
    reason        TEXT,                      -- author-supplied justification
    requested_at  TEXT NOT NULL,
    granted_at    TEXT,
    revoked_at    TEXT,
    manifest_hash TEXT NOT NULL,             -- breaks the grant when manifest changes
    UNIQUE (plugin_name, capability)
);

CREATE INDEX IF NOT EXISTS idx_plugin_capabilities_plugin
    ON plugin_capabilities(plugin_name);

CREATE TABLE IF NOT EXISTS plugin_status (
    plugin_name      TEXT NOT NULL PRIMARY KEY,
    status           TEXT NOT NULL,          -- "loaded" | "pending" | "error" | "disabled"
    error_phase      TEXT,                   -- "validate" | "load" | "start" | NULL
    last_error       TEXT,
    last_error_at    TEXT,
    error_count      INTEGER NOT NULL DEFAULT 0,
    last_loaded_at   TEXT,
    last_seen_at     TEXT
);
```

`Database.init()` adds a `stored_version < 6` block alongside the existing v4 and v5 blocks. No existing rows touched. v0.4 databases continue to read.

## API Surface

### `GET /api/plugins`

```json
{
  "plugins": [
    {
      "name": "horus-os-example-plugin",
      "version": "0.1.0",
      "status": "loaded",
      "enabled": true,
      "description": "A reference plugin demonstrating tool + adapter registration.",
      "author": "Jane Doe <jane@example.com>",
      "license": "Apache-2.0",
      "homepage": "https://github.com/janedoe/horus-os-example-plugin",
      "source": "entry_point",
      "source_detail": "horus_os.plugins:example",
      "registered_tools": ["echo_text"],
      "registered_adapters": ["noop_webhook"],
      "capabilities": [
        {"name": "filesystem.read", "state": "granted", "reason": "Reads notes.", "granted_at": "..."},
        {"name": "net.outbound",    "state": "pending", "reason": "Pings api.", "granted_at": null}
      ],
      "health": {
        "last_seen_at": "2026-05-26T12:34:56Z",
        "error_count_1h": 0,
        "latency_p95_ms_1h": 23,
        "sample_count_1h": 47
      }
    }
  ]
}
```

### Full route table

| Method | Path | Body | Returns | Notes |
|--------|------|------|---------|-------|
| `GET` | `/api/plugins` | — | `{plugins: [PluginRow, ...]}` | Lists all discovered plugins regardless of state. |
| `GET` | `/api/plugins/{name}` | — | `PluginRow` | 404 if not discovered. |
| `POST` | `/api/plugins/{name}/enable` | `{}` | `PluginRow` | Sets `plugins.enabled=1`; needs_restart=true. |
| `POST` | `/api/plugins/{name}/disable` | `{}` | `PluginRow` | Sets `plugins.enabled=0`; unregisters tools/adapters at restart. |
| `POST` | `/api/plugins/{name}/grant` | `{"capability": "filesystem.read", "refinement": null}` | `PluginRow` | Flips `plugin_capabilities.state` to granted. needs_restart=true on first grant. |
| `DELETE` | `/api/plugins/{name}/grant/{capability}` | — | `PluginRow` | Revokes a capability. needs_restart=true. |
| `POST` | `/api/plugins/refresh` | `{}` | `{discovered: int, new: int}` | Re-runs Phase A (discover) without restart; reports diff. Does not load new plugins (those need restart). |

**Why not `/api/plugins/{name}/reload`?** It is feasible but adds a known-painful code path (live unload + re-register of tools/adapters). v0.5 punts; v0.6 can add it once we see real usage.

## CLI Surface

```
horus-os plugins list                      # table of installed/discovered plugins with status
horus-os plugins list --format json        # same data as /api/plugins, for scripting
horus-os plugins info <name>               # one plugin's full detail (manifest + capabilities + health)
horus-os plugins install <pip-spec>        # pip install <spec> into active venv, then refresh
horus-os plugins uninstall <name>          # pip uninstall <name>, then refresh
horus-os plugins enable <name>             # flip enabled flag
horus-os plugins disable <name>            # flip enabled flag
horus-os plugins grant <name> --capability <cap>     # grant one capability
horus-os plugins grant <name> --all                  # grant everything the manifest requests
horus-os plugins revoke <name> --capability <cap>    # revoke
```

**Integration with existing CLI router (`src/horus_os/__main__.py`):** add one `plugins_p = sub.add_parser("plugins", ...)` block with `plugins_sub = plugins_p.add_subparsers(...)`, mirroring the existing `agents` subcommand pattern (lines 131-207). Each `plugins_sub` op calls back into `run_plugins(args, *, stdout, stderr)` in `cli/plugins_cmd.py`. Zero changes to `init`, `run`, `serve`, `traces`, `usage`, or `agents`.

**`horus-os usage` is unaffected.** It queries `tool_invocations` by `tool_name`, which doesn't change. A future `horus-os usage --by plugin` is feasible but not required for v0.5. `horus-os plugins info <name>` already shows the per-plugin health rollup.

**The `install` subcommand wraps `pip install` against the active venv** via `subprocess.check_call([sys.executable, "-m", "pip", "install", spec])`. Three guard rails:

1. Before install, refuse if `sys.prefix == sys.base_prefix` (no venv active). Installing into the system Python is a footgun. Override with `--allow-system-python`.
2. After install, run a fresh `discover_plugins()` and show the user the manifest of every newly-discovered plugin, with requested capabilities highlighted.
3. Print "review with `horus-os plugins info <name>` before granting capabilities". No automatic grant on install.

## Scaling Considerations

| Scale | Adjustments |
|-------|-------------|
| 0-10 plugins | No adjustments needed. In-memory `PluginRegistry`, in-memory `PluginHealthSubscriber` ring buffers, per-call `CapabilityGuard` lookup is a frozenset membership check (O(1)). |
| 10-100 plugins | Still fine. The ring buffer is bounded per-plugin; total memory is bounded. Discovery walks entry points once at startup; `pip` users are unlikely to install 100+ plugins anyway. |
| 100+ plugins (theoretical) | The discovery scan would dominate startup. Mitigation if this becomes real: cache the manifest_hash → PluginSpec dict on disk in `~/.horus-os/cache/plugin_index.json`, invalidate on `horus-os plugins install`. Premature for v0.5. |

### Scaling Priorities

1. **First bottleneck:** none expected at v0.5 scale. The plugin runtime is in-process and the operations are O(plugins) at startup, O(1) at tool invocation.
2. **Second bottleneck:** memory for `PluginHealthSubscriber` ring buffers if a plugin spams the bus. Mitigation: ring buffer is bounded by max-1000-events-per-plugin, oldest evicted; configurable via `cfg.plugin_health_window`.

## Anti-Patterns

### Anti-Pattern 1: Centralized capability check inside `ToolRegistry.invoke`

**What people do:** Add a `capability_check` parameter to `ToolRegistry.invoke()` and switch on plugin-or-not at every call site.

**Why it's wrong:** Threads plugin awareness into core registry code that v0.1 through v0.4 happily lived without. Every existing call site (tools/loop.py, server/api.py routes, the agent loop) has to learn about plugins. Built-ins need an explicit "skip the check" path. The v0.4 observability hooks become entangled with v0.5 permission logic.

**Do this instead:** Wrap at registration in `PluginLoader.load()`. Built-ins skip the wrap because they don't go through `PluginLoader`. `ToolRegistry.invoke` is byte-identical to v0.4.

### Anti-Pattern 2: Loading plugins synchronously inside `discover_plugins()`

**What people do:** Make `discover_plugins()` return a list of fully-loaded plugins with tools already registered, mirroring v0.3's `discover_adapters()` which returns instantiated adapters.

**Why it's wrong:** Plugins have a permission gate (Phase C) that needs the database, and a separate validate phase (Phase B) that should run with no side effects. Fusing all four into one function means a manifest validation failure tears down the same call path as a permission denial, and you can't tell them apart in the dashboard.

**Do this instead:** `discover_plugins()` returns `list[PluginSpec]` and is side-effect-free. Validation, permission, and load are explicit phases in the lifespan handler. Each phase has a single failure mode and a single registry mutation.

### Anti-Pattern 3: Persisting the full manifest in SQLite

**What people do:** JSON-serialize the entire `PluginSpec` into the `plugins` table.

**Why it's wrong:** Duplicates state. The plugin's pip-installed `horus-plugin.toml` is the source of truth; the database is a runtime view. If they drift (user edits the toml; runtime forgets to re-read), behavior depends on which one wins, and that's a Heisenbug factory.

**Do this instead:** Persist only what the database needs that the manifest doesn't have: `enabled`, grant state, last error, error count. The manifest is re-parsed on every startup. The `manifest_hash` column is the bridge. When it changes, grants flip to `pending` automatically.

### Anti-Pattern 4: Default-allow on a missing manifest field

**What people do:** Treat absence of a `[[capabilities]]` block as "this plugin needs no capabilities" and silently full-grant.

**Why it's wrong:** A plugin author who forgets the block ships an unaudited plugin. The threat model for v0.5 is "ship-fast plugin authors might forget things," not "malicious plugin authors might lie," but "forgot to declare" is the more common failure and it should fail visible.

**Do this instead:** Empty `[[capabilities]]` is treated as "this plugin claims it needs zero capabilities." If the plugin then tries to do anything sensitive (read a file, hit the network), the runtime can't tell because v0.5 doesn't sandbox. The contract is: plugin author declares everything they will use. CONTRIBUTING.md says this in big letters. The reference plugin demonstrates a correctly-declared capability set.

## Integration Points

### Reused from v0.3 / v0.4 (no API breakage)

| Existing component | How v0.5 uses it | Touch |
|--------------------|------------------|-------|
| `ToolRegistry.register(tool)` (`tools/registry.py`) | `PluginLoader` calls this with plugin-provided tools after wrapping handlers with `CapabilityGuard`. Built-ins go through the same call (no wrap). | Zero changes. |
| `ToolRegistry.invoke(name, input)` (`tools/registry.py`) | Unchanged. The wrapped handler is already in place. | Zero changes. |
| `AdapterRegistry` (`adapters/base.py`) | `PluginLoader` calls `register(name)` and `mark_running` / `mark_error` on plugin-provided adapters. Lifespan loop iterates over the merged adapter list (built-in + plugin). | Zero changes to AdapterRegistry. v0.5 merges plugin adapters into `_adapters` before the v0.3 lifespan loop runs. |
| `AdapterContext` (`adapters/base.py`) | Plugin-provided adapters receive the same `AdapterContext` as built-ins; can register tools via `context.tool_registry`. | Zero changes. |
| `ObservationBus` (`observability/bus.py`) | `PluginHealthSubscriber` subscribes alongside the v0.4 CostAnnotator + SQLitePersister. Subscriber exception-swallow already covers misbehaving health subscribers. | Zero changes. |
| `tool_invocations` table (`storage.py`) | Read-only source for per-plugin health rollup. The `tool_name` column joins to `PluginRegistry.plugin_for_tool(name)`. | Zero changes. |
| FastAPI app lifespan (`server/api.py:_lifespan`) | v0.5 extends the existing `for _a in _adapters: await _start(...)` loop with a plugin block that runs after built-in adapter startup. | Adds ~30 lines, replaces nothing. |
| `Config.load()` (`config.py`) | Adds optional `plugin_paths: list[Path]` (defaults to `[~/.horus-os/plugins]`) and `plugin_health_window: int` (default 3600 seconds). Both nullable; existing configs read fine. | One field added. |

### New external integration points

| Integration | Pattern | Notes |
|-------------|---------|-------|
| `pip install` (subprocess) | `horus-os plugins install` shells out to `python -m pip install <spec>`. | Refuses to run without active venv (overridable). Streams pip's stdout/stderr to the user. |
| `importlib.metadata.entry_points(group="horus_os.plugins")` | Standard Python plugin discovery. Same mechanism `discover_adapters()` uses for the `horus_os.adapters` group. | Two distinct groups; one plugin can register under both (the reference plugin does). |
| `~/.horus-os/plugins/` filesystem scan | `discover_plugins()` walks each subdir for a `horus-plugin.toml`. Importable via the subdir's `pyproject.toml` only if it's been `pip install -e`'d; otherwise the toml is parseable but the plugin can't load (status="error", error_phase="load", message points to the missing install). | Provides a path for dev plugins not yet packaged. |
| `tomllib` (stdlib, Python 3.11+) | Parse `horus-plugin.toml`. Read-only. | Zero new deps. |
| `packaging.specifiers.SpecifierSet` (stdlib via `packaging`, already transitive via pip and setuptools) | Validate `horus_os_compat` against `horus_os.__version__`. | If `packaging` is not already pulled, add as direct dep. It is well-tested, pure-Python, three-OS clean. |

## Suggested Build Order

The eight work-items below have explicit dependencies. Anything not in a phase's "depends on" list runs in parallel with it. These map onto GSD phase numbers at roadmapper-time; the labels A–H are research-internal.

### Work-item A: Manifest model + discovery (the foundation)

**Files created:** `plugins/__init__.py`, `plugins/spec.py`, `plugins/manifest.py`, `plugins/discovery.py`.
**Depends on:** nothing in v0.5. v0.4 substrate (ObservationBus, schema v5) is the only prerequisite.
**Acceptance:** `discover_plugins()` returns a `list[PluginSpec]` from a fixture entry-point and a fixture `~/.horus-os/plugins/foo/horus-plugin.toml`. Manifest with invalid horus_os_compat raises `ValidationError`. Zero registry touch.
**Why first:** Everything downstream needs `PluginSpec`. Manifest parsing has no dependencies, so it can land before any runtime wiring.

### Work-item B: Schema migration v5→v6 + persistence

**Files modified:** `storage.py` (v5→v6 block + plugin CRUD methods).
**Files created:** none.
**Depends on:** nothing.
**Acceptance:** `Database.init()` against a v5 fixture database upgrades cleanly to v6; v4 fixture upgrades through v5 to v6; running init twice is a no-op. Three new tables exist; old tables untouched. Plugin CRUD methods round-trip.
**Why early and parallel with A:** Schema lands before registry needs it. Can run in parallel with A because they touch disjoint files (`storage.py` vs `plugins/`).

### Work-item C: Registry + permission model

**Files created:** `plugins/registry.py`, `plugins/permissions.py`.
**Depends on:** A (`PluginSpec`), B (`Database.save_plugin_capability` etc).
**Acceptance:** `PluginRegistry.register(spec)` creates an entry. `PermissionGate.resolve(spec)` returns `(granted_dict, pending_list)`. `CapabilityGuard.wrap_tool_handler(...)` returns a refusing handler when the cap is missing. Manifest-hash mismatch surfaces capabilities as pending.
**Why after A and B:** the registry consumes specs (A) and the permission gate persists / reads through the database (B).

### Work-item D: Loader + registry integration

**Files created:** `plugins/loader.py`, `plugins/health.py`.
**Files modified:** `server/api.py` (lifespan: add the six-phase plugin block after built-in adapter startup, plus the `PluginHealthSubscriber` subscribe).
**Depends on:** A, B, C.
**Acceptance:** A fixture plugin's tool registers in `ToolRegistry`; its adapter registers in `AdapterRegistry`. CapabilityGuard wraps the tool handler. A plugin missing a granted capability refuses to invoke the wrapped handler. A plugin whose entry-point import raises lands in `status="error", error_phase="load"` and does not break other plugins. `PluginHealthSubscriber.rollup(name)` returns sensible numbers after synthetic events.
**Why fourth:** the loader is the integration point. Builds on every prior phase.

### Work-item E: `/api/plugins` REST surface

**Files modified:** `server/api.py` (add 6 routes).
**Files created:** `tests/server/test_api_plugins.py`.
**Depends on:** D (loader writes to the registry; routes read from it).
**Acceptance:** All six routes (`GET /api/plugins`, `GET /api/plugins/{name}`, `POST .../enable`, `POST .../disable`, `POST .../grant`, `DELETE .../grant/{cap}`) round-trip. Disable + restart unregisters. Grant + restart loads.
**Why before CLI and dashboard:** both downstream surfaces should consume `/api/plugins` rather than re-implement the read path.

### Work-item F: `horus-os plugins` CLI

**Files created:** `cli/plugins_cmd.py`.
**Files modified:** `cli/__init__.py` (export `run_plugins`), `__main__.py` (add `plugins` subparser).
**Depends on:** E (CLI's `list` and `info` go through the API; or, equivalently, through the same query module — either way, E's contracts shape F's output).
**Acceptance:** `horus-os plugins list` lists installed plugins. `install` runs pip then refresh. `info` prints the manifest. `grant` flips the database. CI runs `horus-os plugins install -e ./examples/horus-os-example-plugin` and asserts the new plugin appears.

### Work-item G: `/plugins` dashboard tab

**Files modified:** `server/static/index.html` + JS.
**Depends on:** E (consumes `/api/plugins`).
**Acceptance:** `/plugins` tab lists discovered plugins with status badges, capability chips (granted/pending/revoked), enable/disable toggles, "grant" buttons that POST to the API. Pre-v0.4 behavior of `/adapters` and `/observability` tabs unchanged.

### Work-item H: Reference plugin + 3-OS gate + release

**Files created:** `examples/horus-os-example-plugin/` (full package).
**Files modified:** `pyproject.toml` (the host one, if the example is referenced from the install-smoke job), CI workflow, CHANGELOG, docs (`docs/PLUGINS.md`, `docs/MIGRATION-v0.4-to-v0.5.md`).
**Depends on:** F (CLI install path tested against the reference plugin), G (dashboard renders the reference plugin's manifest).
**Acceptance:** `pip install -e ./examples/horus-os-example-plugin` works on three OSes and two Python versions; the plugin shows up in `/plugins`; granting a capability and restarting makes its tool invocable; revoking and restarting makes it refuse. v0.5.0 tag cuts.

**Parallelization map:** A ∥ B → C → D → E → (F ∥ G) → H. The "F ∥ G" parallelism is the only one worth exploiting at execution time; everything else has hard dependencies.

**Roadmapper note:** these eight items above are research-suggested, not yet phase-numbered. The roadmapper should map them to GSD phase numbers, decide whether some collapse (e.g. A and B might be one phase per the "schema migration + skeleton" pattern v0.4 used in Phase 32), and confirm with the user before plan generation. Hard rule: A's `PluginSpec` is consumed by every later phase; do not invert.

## Sources

**Internal (HIGH confidence — read directly):**
- `/Users/santino/Projects/horus-os/.planning/PROJECT.md` — v0.5 milestone target features and decisions
- `/Users/santino/Projects/horus-os/.planning/ROADMAP.md` — v0.3 and v0.4 phase detail
- `/Users/santino/Projects/horus-os/src/horus_os/adapters/base.py` — AdapterRegistry / AdapterEntry / Adapter Protocol / LifecycleAdapter / discover_adapters() shape
- `/Users/santino/Projects/horus-os/src/horus_os/adapters/webhook.py` — reference adapter pattern (bind + lazy FastAPI import)
- `/Users/santino/Projects/horus-os/src/horus_os/tools/registry.py` — ToolRegistry.register / invoke contract
- `/Users/santino/Projects/horus-os/src/horus_os/tools/builtin.py` — built-in tool factory pattern
- `/Users/santino/Projects/horus-os/src/horus_os/observability/bus.py` — ObservationBus subscriber semantics + exception-swallow contract
- `/Users/santino/Projects/horus-os/src/horus_os/storage.py` — schema version + ALTER TABLE idempotency pattern for v5
- `/Users/santino/Projects/horus-os/src/horus_os/server/api.py` — lifespan structure, app.state placements, adapter startup loop
- `/Users/santino/Projects/horus-os/src/horus_os/__main__.py` — subparser pattern (used by the `plugins` subcommand)
- `/Users/santino/Projects/horus-os/.planning/research/STACK.md` — v0.4 stack research, confirms the lazy-import + LifecycleAdapter pattern v0.5 plugins reuse

**External (MEDIUM-HIGH confidence — verified against current docs):**
- [Python entry points specification](https://packaging.python.org/en/latest/specifications/entry-points/) — entry-point group format, dist-info storage, importlib.metadata.entry_points() API
- [Python importlib.metadata reference](https://docs.python.org/3/library/importlib.metadata.html) — entry_points(group=) signature, EntryPoint.load() semantics
- [Creating and discovering plugins (Python Packaging User Guide)](https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/) — recommended discovery pattern (this is the pattern v0.3 AdapterRegistry already uses)
- [VS Code Extension Manifest reference](https://code.visualstudio.com/api/references/extension-manifest) — manifest field structure, activation events, declared contributes; v0.5 borrows the "declare everything statically" pattern but uses TOML not JSON
- [VS Code Activation Events](https://code.visualstudio.com/api/references/activation-events) — confirms the lazy-load-on-need pattern; v0.5's discover-on-startup is simpler because horus-os is a single long-running process
- [VS Code permission system discussion](https://github.com/microsoft/vscode/issues/187386) — confirms the gap in VS Code's model: no declared capability system. v0.5 ships one from day one, learning from VS Code's omission.
- [Designing a plugin architecture in Python (python.org.il)](https://python.org.il/en/presentations/designing-a-plugin-architecture-in-python) — interface + entry-point + manifest layered design; matches the v0.5 layout

**Sanity-check cross-references (MEDIUM confidence):**
- [pytest plugin system docs](https://docs.pytest.org/en/stable/how-to/writing_plugins.html) — entry-point group `pytest11`, fixture-based hook contracts; confirms in-process plugin loading is the default Python pattern
- [Setuptools entry point user guide](https://setuptools.pypa.io/en/latest/userguide/entry_point.html) — pyproject.toml `[project.entry-points."group.name"]` syntax that plugins use

---
*Architecture research for: v0.5 Plugin System on horus-os*
*Researched: 2026-05-26*
