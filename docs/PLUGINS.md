# Plugins

A single-source authoring guide for third-party `horus-os` plugins.

Read [`docs/PLUGIN-SECURITY.md`](PLUGIN-SECURITY.md) before granting capabilities to a plugin you have not authored yourself. The security doc states the trust contract that the capability prompt asks you to accept.

## What is a plugin?

A plugin is a Python package that ships a `horus-plugin.toml` manifest, declares the capabilities it needs (`filesystem.read`, `filesystem.write`, `net.outbound`, `secrets.read`), and contributes tools and/or adapters to a running `horus-os` instance. Tools extend the agent's tool registry; adapters extend the FastAPI app with new routes, background tasks, or external integrations. Discovery happens through two channels: Python entry points (`importlib.metadata.entry_points(group="horus_os.plugins")`) for pip-installed plugins, and a local `~/.horus-os/plugins/<name>/` directory for in-tree development.

Every plugin runs in the same Python process as `horus-os` itself. Capability grants reduce the surface a plugin can touch, but they do not sandbox the plugin from the rest of the interpreter. See `docs/PLUGIN-SECURITY.md` for the threat model.

## Anatomy of `horus-plugin.toml`

Every plugin ships a `horus-plugin.toml` at its wheel root (or inside the package directory as package data). The shape below is the v1 manifest contract validated by `horus_os.plugins.manifest.MANIFEST_V1_SCHEMA`; the JSON-Schema mirror lives at [`docs/manifest-v1.schema.json`](manifest-v1.schema.json).

```toml
manifest_version = 1
name = "horus-os-test-full"
version = "1.2.3"
description = "Full horus-plugin.toml fixture exercising every documented field."
author = "horus-os contributors"
license = "Apache-2.0"
horus_os_compat = ">=0.5,<0.7,!=0.5.1"
homepage = "https://github.com/example/horus-os-test-full"
issue_tracker = "https://github.com/example/horus-os-test-full/issues"
capabilities = [
    "filesystem.read",
    "filesystem.write",
    "net.outbound",
    "secrets.read",
]

[[contributions.tools]]
name = "alpha_tool"
entry_point = "example_plugin.tools:alpha"

[[contributions.tools]]
name = "beta_tool"
entry_point = "example_plugin.tools:beta"

[[contributions.adapters]]
name = "alpha_adapter"
entry_point = "example_plugin.adapters:AlphaAdapter"

[[contributions.adapters]]
name = "beta_adapter"
entry_point = "example_plugin.adapters:BetaAdapter"
```

Field-by-field:

- `manifest_version` (int, required). Always `1` in v0.5. Older or newer values are refused at validation time; a future v2 manifest will be parsed by a separate `MANIFEST_V2_SCHEMA` and the installer will switch on this integer.
- `name` (string, required). Lowercase ASCII letters, digits, and hyphens. Becomes the row key in `plugins.name`, the prefix on every contributed tool's qualified name, and the argument to `horus-os plugins {info,enable,disable,update,grant,revoke}`.
- `version` (string, required). PEP 440. Stored on `plugins.version` and pinned into every `plugin_capabilities` row so that a version bump invalidates prior grants automatically.
- `description` (string, required, ≤200 chars). One-line plain-English summary; appears in the dashboard's `/plugins` tab and in `horus-os plugins info <name>` output.
- `author` (string, required). Non-empty. Shown next to the description in the capability grant prompt.
- `license` (string, required). SPDX identifier preferred. Surfaced in dashboard listings.
- `horus_os_compat` (string, required). PEP 440 specifier set, e.g. `>=0.5,<0.7,!=0.5.1`. Parsed via `packaging.specifiers.SpecifierSet`; the installer refuses to load a plugin whose specifier excludes the running `horus-os` version.
- `homepage`, `issue_tracker` (URL, optional). Surfaced in the dashboard.
- `capabilities` (list of strings, optional). Closed enum drawn from `horus_os.plugins.capability_catalog.Capability`. Unknown values are refused at validation time.
- `[[contributions.tools]]` / `[[contributions.adapters]]` (optional repeat tables). Each entry has a `name` (lowercase ASCII identifier scoped within the plugin) and an `entry_point` (dotted-path import with an optional `:Symbol` suffix). The Phase 42 loader instantiates each entry at startup.

## Capability catalog

Every capability a plugin can request is a member of the closed `Capability` enum in `src/horus_os/plugins/capability_catalog.py`. The descriptions below are the verbatim strings the installer's capability grant prompt prints to your terminal.

| Capability | Description |
| --- | --- |
| `filesystem.read` | Read files from disk paths the plugin declares. Does NOT include writing, deleting, or modifying files. |
| `filesystem.write` | Create, modify, and delete files at disk paths the plugin declares. Implies read access to the same paths. |
| `net.outbound` | Open outbound network connections to hosts the plugin declares. Does NOT permit inbound listeners or connections to third-party hosts the manifest did not list. |
| `secrets.read` | Read secret values (API keys, tokens) the plugin declares by key name. Does NOT permit listing all secrets or writing new ones. |
| `skill.exec` | Run the embedded steps of a code-bearing skill. Prompt-template skills never need this; only a skill marked kind=code is gated on it. |

Adding a new capability is a coordinated change: add the `Capability` enum member, add the `DESCRIPTIONS` entry (the module-level assert refuses to import otherwise), wire enforcement at the `CapabilityGuard` shim layer, and re-run `python scripts/build_manifest_schema.py` to refresh the JSON-Schema mirror.

## Lifecycle hooks

A plugin's adapter contributions may implement an async `start(ctx)` and/or `stop()` hook. `horus-os` calls these inside the FastAPI lifespan.

### `start(ctx)` contract

`start(ctx)` is called once per adapter at FastAPI startup. The `ctx` argument is a `PluginContext` (from `horus_os.plugins.api`) carrying the plugin's name, version, per-plugin data directory, and three capability-gated shim namespaces: `ctx.filesystem` (`read`/`write` against the granted paths), `ctx.secrets` (`read` against the granted secret keys), and `ctx.net` (`outbound` against the granted hosts). Each shim raises `PermissionDenied` when the underlying capability has not been granted.

### `stop()` contract

`stop()` is called once per adapter at FastAPI shutdown. Plugins must release file handles, cancel background tasks, and flush any pending writes. The hook is awaited and may run cleanup logic; exceptions are captured and surfaced through the `/api/adapters` registry without crashing the process.

### Bounded lifecycle (`asyncio.wait_for(timeout=2.0)`)

Both hooks are wrapped in `asyncio.wait_for(..., timeout=2.0)` per ISOLATE-02. A hung `start(ctx)` becomes a load-time `PluginLoadError`, never a 60-second startup stall — the same shape the v0.4 `OtelAdapter` uses for its bounded shutdown. Plugins that need a long-running task should fire-and-forget it (`asyncio.create_task(...)`) inside `start`, not block the hook.

## Testing your plugin

Phase 46 shipped a three-tier fixture strategy for testing plugins without the install-cost overhead of a real `pip install` on every test. Pick the tier that matches what your test actually needs to exercise.

### Tier 1: `make_synthetic_plugin(name, capabilities)`

In-process plugin synthesis. Returns a `PluginSpec` with the requested capability list bound, ready to thread through `PermissionService` and `CapabilityGuard` without touching pip or the filesystem. Use this tier for unit tests of capability-gated tool handlers, permission gate transitions, and the manifest schema itself. Hundreds of these tests run in a few hundred milliseconds because no subprocess and no I/O is involved.

### Tier 2: `fake_plugin_entry_points`

Discovery-walk monkeypatch. Patches `importlib.metadata.entry_points` so `discover_plugins()` walks a fabricated entry-point set without a real `pip install`. Use this tier for tests of the discovery + loader pipeline, registry-status transitions, and adapter lifecycle hooks. Still fast — no subprocess — but exercises the entry-point seam end-to-end.

### Tier 3: `clean_venv` (gated)

End-to-end install in a throwaway venv. Gated by the `--run-installer-e2e` pytest flag because each invocation creates a new virtualenv and runs the real `pip install` chain. Use this tier sparingly for the small set of tests that need to verify the full two-phase installer, including wheel download, sdist refusal, RECORD parsing, and runtime-dep gating. The Phase 49 release-gate matrix is the main consumer.

## Walkthrough of the reference plugin

Phase 48 will ship `examples/horus-os-example-plugin/` as a reference implementation. Until then, the four scenarios it will demonstrate are a contract, not shipped code:

- (a) A tool requiring `filesystem.read`. Decorated with `@require_capability(Capability.FILESYSTEM_READ)`; reads files via `ctx.filesystem.read(path)`; raises `PermissionDenied` when the user denied the cap at install time.
- (b) A tool requiring `secrets.read`. Reads an API key via `ctx.secrets.read("EXAMPLE_KEY")`; returns `None` (not an exception) when the env var is unset, matching the `DESCRIPTIONS[SECRETS_READ]` semantics.
- (c) A lifecycle adapter with `start(ctx)` and `stop()`. The hook respects the 2.0-second `asyncio.wait_for` bound; `start` schedules a background task with `asyncio.create_task` rather than blocking; `stop` cancels the task and awaits its completion.
- (d) A single package registering BOTH `[[contributions.tools]]` and `[[contributions.adapters]]` in one manifest. Demonstrates that one wheel can contribute multiple surfaces and that the per-surface entry-point resolution is independent.

Phase 48 lands the reference plugin under `examples/horus-os-example-plugin/`. The Phase 48 ruff custom rule will also pin the public-API import surface: the reference plugin's only `from horus_os` imports are from `horus_os.plugins.api`.

## Public API surface

`horus_os.plugins.api` is the ONLY supported import surface for plugin authors. The Phase 48 ruff custom rule (TEST-21) will refuse any other `from horus_os.<submodule>` import inside the reference plugin. Plugins that import from internal modules must expect those imports to break on minor releases.

| Name | Purpose |
| --- | --- |
| `Adapter` | Protocol for adapter contributions; mount routes / handle external integrations. |
| `AdapterContext` | Per-app context handed to `Adapter`s at startup. |
| `Capability` | Closed enum of capability strings (`filesystem.read`, `filesystem.write`, `net.outbound`, `secrets.read`). |
| `LifecycleAdapter` | Optional Protocol extending `Adapter` with async `start(ctx)` and `stop()` hooks. |
| `PluginContext` | Per-plugin context with `filesystem`, `secrets`, `net` shims plus name/version/data_dir. |
| `PluginSpec` | Frozen description of a discovered plugin (name, version, capabilities, contributions). |
| `Tool` | Tool registration shape; mirrors the built-in tool registry. |
| `require_capability` | Decorator that attaches the required capability set to a tool handler. |

`CapabilityGuard` and `PermissionDenied` are reachable via `horus_os.plugins` for plugin authors that need to catch the exception directly, but they are not part of the canonical surface.

## Distributing your plugin

There are two ways to ship a plugin to a `horus-os` user.

### Entry points (pip-installed plugins)

Declare a `[project.entry-points."horus_os.plugins"]` table in your `pyproject.toml` whose value is the dotted path to your plugin's manifest-discovery hook. Ship a `horus-plugin.toml` at the wheel root or under your package directory. A user installs your plugin via:

```
horus-os plugins install <package-spec>
```

The two-phase installer runs: `pip download --no-deps` into a tmpdir; manifest validation (refuses sdist installs by default, refuses any wheel with a `.pth` file in RECORD, refuses any wheel whose `Requires-Dist` would downgrade `pydantic` or `packaging`); capability grant prompt; `pip install --no-deps --no-build-isolation`. Any failure rolls back to the pre-install state. Add `--allow-sdist` if your distribution is sdist-only; the user will see a separate refusal text explaining the arbitrary-code-execution risk.

### Local filesystem (in-tree plugins)

Drop a `horus-plugin.toml` plus the Python module under `~/.horus-os/plugins/<plugin_name>/`. Restart `horus-os` to pick up the new filesystem plugin — `v0.5` does not ship a hot-reload command; the `enable`/`disable` subcommands toggle a discovered plugin between active and inactive without removing it.

The dashboard `/plugins` tab and the `horus-os plugins list` CLI surface both pip-installed and filesystem plugins in the same view.
