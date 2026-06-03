---
title: "Plugins"
description: "Build and install third-party horus-os plugins, declare capabilities in a TOML manifest, and understand discovery, install, and the default-deny grant model."
---

## What a plugin is

A plugin is a Python package that ships a `horus-plugin.toml` manifest, declares the capabilities it needs, and contributes tools and/or adapters to a running horus-os instance.

- **Tools** extend the agent's tool registry, so your agents can call them like any built-in tool.
- **Adapters** extend the FastAPI app with new routes, background tasks, or external integrations.

A single package can contribute both. Plugins run in the same Python process as horus-os itself. Capability grants narrow what a plugin is allowed to touch, but they do not sandbox it from the rest of the interpreter. Read [Plugin security](/extending/plugin-security/) before granting capabilities to a plugin you did not author.

> [!IMPORTANT]
> Install plugins only from sources you trust. A granted capability gives the plugin real access to your files, secrets, or network, and the process boundary is shared with horus-os. The grant prompt exists so you make that decision deliberately, not so it is safe to skip.

## The manifest contract

Every plugin ships a `horus-plugin.toml` at its wheel root (or inside the package directory as package data). This is the v1 manifest contract. The shape below shows every documented field. For a field-by-field schema, see the [manifest reference](/extending/manifest-reference/).

```toml
manifest_version = 1
name = "horus-os-example-plugin"
version = "0.1.0"
description = "Reference plugin demonstrating the v0.5 contract."
author = "horus-os contributors"
license = "Apache-2.0"
horus_os_compat = ">=0.5,<0.6"
homepage = "https://github.com/your-org/your-plugin"
issue_tracker = "https://github.com/your-org/your-plugin/issues"
capabilities = [
    "filesystem.read",
    "secrets.read",
]

[[contributions.tools]]
name = "echo_text_tool"
entry_point = "horus_os_example_plugin.tools:echo_text_tool"

[[contributions.tools]]
name = "lookup_secret_tool"
entry_point = "horus_os_example_plugin.tools:lookup_secret_tool"

[[contributions.adapters]]
name = "example_adapter"
entry_point = "horus_os_example_plugin.adapter:ExampleAdapter"
```

Key fields:

- `manifest_version` (int, required). Always `1` today. Older or newer values are refused at validation time.
- `name` (string, required). Lowercase ASCII letters, digits, and hyphens. It is the prefix on every contributed tool's qualified name and the argument to the `horus-os plugins` subcommands.
- `version` (string, required, PEP 440). A version bump invalidates prior capability grants automatically (see [Capability grants](#capability-grants-default-deny)).
- `description` (string, required, 200 chars or fewer). Shown in the dashboard `/plugins` tab and in `horus-os plugins info <name>`.
- `author`, `license` (strings, required). The author appears in the grant prompt; the license is surfaced in dashboard listings.
- `horus_os_compat` (string, required). A PEP 440 specifier set such as `>=0.5,<0.6`. The installer refuses to load a plugin whose specifier excludes the running horus-os version.
- `homepage`, `issue_tracker` (URLs, optional). Surfaced in the dashboard.
- `capabilities` (list of strings, optional). A closed enum. Unknown values are refused at validation time. See [Plugin security](/extending/plugin-security/) for the full catalog and what each capability does and does not allow.
- `[[contributions.tools]]` and `[[contributions.adapters]]` (optional repeat tables). Each entry has a `name` (lowercase ASCII identifier scoped within the plugin) and an `entry_point` (a dotted import path with an optional `:Symbol` suffix). The loader instantiates each entry at startup.

## Discovery

horus-os finds plugins through two channels, and the dashboard `/plugins` tab and the `horus-os plugins list` CLI surface both in the same view.

### Entry points (pip-installed plugins)

Declare a `[project.entry-points."horus_os.plugins"]` table in your `pyproject.toml` whose key matches your manifest `name` and whose value points at your plugin's package. horus-os walks `importlib.metadata.entry_points(group="horus_os.plugins")` to discover installed plugins.

```toml
[project.entry-points."horus_os.plugins"]
horus-os-example-plugin = "horus_os_example_plugin"
```

### Local filesystem (in-tree plugins)

Drop a `horus-plugin.toml` plus the Python module under `~/.horus-os/plugins/<plugin_name>/` and restart horus-os to pick it up. There is no hot-reload command; restart after adding a filesystem plugin. Override the directory with the `HORUS_OS_PLUGIN_DIR` environment variable.

When the same plugin name is discovered from both channels, the entry-point version wins, the filesystem duplicate is dropped, and a warning names both source paths.

## Installing a plugin

Install a pip-distributed plugin with the CLI:

```bash
horus-os plugins install <package-spec>
```

The installer runs in two phases so nothing is committed to your environment until the manifest has been validated and you have answered the grant prompt:

1. **Download and validate.** `pip download --no-deps` fetches the distribution into a temporary directory. The manifest is then validated. By default the installer refuses sdist installs, refuses any wheel that lists a `.pth` file in its RECORD, and refuses any wheel whose `Requires-Dist` would downgrade `pydantic` or `packaging`.
2. **Grant and install.** You are shown the capability grant prompt, and only after you accept does `pip install --no-deps --no-build-isolation` commit the wheel.

Any failure rolls back to the pre-install state. If a distribution is sdist-only, pass `--allow-sdist`; you will see a separate refusal text explaining the arbitrary-code-execution risk before it proceeds.

## Capability grants (default-deny)

horus-os is default-deny: a freshly installed plugin holds no capabilities until you grant them. Grants are recorded per capability and pinned to a hash computed from the plugin's declared capabilities at install time.

Because the hash is tied to the version and capability set, a version bump or a change to the requested capabilities invalidates the prior grants. On the next load the affected capabilities transition back to pending, and horus-os re-prompts you instead of silently carrying old grants forward. A grant only stays active when the stored hash still matches the loaded manifest.

Manage grants from the CLI:

```bash
# Grant or revoke a single capability
horus-os plugins grant <name> <capability>
horus-os plugins revoke <name> <capability>

# Grant everything the manifest requests
horus-os plugins grant <name> --all

# Inspect grants and recent audit entries
horus-os plugins info <name>
```

`enable` and `disable` toggle a discovered plugin between active and inactive without removing it or changing its grants. `update` runs the upgrade-diff classifier and re-runs the install flow, re-prompting for any capability whose grant the new version invalidates. `uninstall` removes the plugin.

For the full list of capabilities and the exact access each one confers, see [Plugin security](/extending/plugin-security/).

## Lifecycle hooks

An adapter contribution may implement an async `start(ctx)` hook and/or a `stop()` hook. horus-os calls these inside the FastAPI lifespan.

- `start(ctx)` runs once per adapter at startup. The `ctx` argument is a `PluginContext` carrying the plugin's name, version, per-plugin data directory, and three capability-gated shim namespaces: `ctx.filesystem` (`read`/`write` against granted paths), `ctx.secrets` (`read` against granted secret keys), and `ctx.net` (`outbound` against granted hosts). Each shim raises `PermissionDenied` when the underlying capability has not been granted.
- `stop()` runs once per adapter at shutdown. Release file handles, cancel background tasks, and flush pending writes here.

Both hooks are bounded by `asyncio.wait_for(..., timeout=2.0)`. A hook that blocks past that ceiling becomes a load-time error instead of stalling startup or shutdown. If your adapter needs a long-running task, fire it off with `asyncio.create_task(...)` inside `start` rather than blocking the hook, and cancel it in `stop`.

## Failure isolation

Discovery never raises out of the loader. Each plugin source that fails to parse its TOML or validate against the schema is registered as an error-status plugin in the registry, and horus-os keeps booting. A broken or untrusted plugin does not take the host down with it.

Exceptions raised from `stop()` are captured and surfaced through the adapter registry rather than crashing the process. If you need to disable plugins entirely for a boot, the serve command exposes an escape hatch that turns all plugins off.

## The reference plugin

A complete, installable reference plugin lives at `examples/horus-os-example-plugin/` in the [repository](https://github.com/Ridou/horus-os/tree/main/examples/horus-os-example-plugin). It demonstrates four scenarios in a single package:

1. A capability-gated filesystem tool (`echo_text_tool`) that reads a file via `ctx.filesystem.read(path)` and requires `filesystem.read`.
2. A capability-gated secret tool (`lookup_secret_tool`) that reads an env var via `ctx.secrets.read(key)` and returns `None` (not an exception) on a missing key. Requires `secrets.read`.
3. A bounded-lifecycle adapter (`ExampleAdapter`) whose `start(ctx)` schedules a background task and whose `stop()` cancels and awaits it, both well inside the 2-second timeout.
4. One package contributing both `[[contributions.tools]]` entries and a `[[contributions.adapters]]` entry, proving a single distribution can contribute multiple surfaces.

Install it from a checkout that already has horus-os in editable mode:

```bash
pip install -e ./examples/horus-os-example-plugin
horus-os plugins grant horus-os-example-plugin --all
```

To start a new plugin, copy that directory and rename three identifiers: the distribution name `horus-os-example-plugin` (in `pyproject.toml`, the manifest `name`, and the entry-point key), the Python package `horus_os_example_plugin` (the directory under `src/`, the dotted prefix in every `entry_point`, and the entry-point value), and the `ExampleAdapter` class. Then redeclare your `capabilities` set, adjust your contributions, and run `pip install -e .` against the host environment.

## Public API surface

`horus_os.plugins.api` is the only supported import surface for plugin authors. Plugins that import from internal horus-os modules should expect those imports to break on minor releases. The reference plugin imports only from `horus_os.plugins.api`. Notable names:

- `Adapter`, `LifecycleAdapter`, `AdapterContext` for adapter contributions.
- `Tool` and `require_capability` for tool registration; the decorator attaches the required capability set to a tool handler.
- `Capability` for the closed enum of capability strings.
- `PluginContext`, `PluginSpec` for the runtime and discovery shapes.

For how to build an adapter against this surface, see [Writing an adapter](/extending/writing-an-adapter/).

## See also

- [Plugin security](/extending/plugin-security/)
- [Manifest reference](/extending/manifest-reference/)
- [Writing an adapter](/extending/writing-an-adapter/)
- [Environment variables](/reference/environment-variables/)
