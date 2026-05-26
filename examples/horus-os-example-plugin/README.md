# horus-os-example-plugin

The canonical reference for v0.5 plugin authors. One installable package
that demonstrates every shape `horus-os` is willing to load and runs
entirely against the single public API surface
`horus_os.plugins.api`.

## What this plugin demonstrates

1. **Capability-gated filesystem tool.** `echo_text_tool` reads a file
   via `ctx.filesystem.read(path)`. Requires `filesystem.read`.
2. **Capability-gated secret tool.** `lookup_secret_tool` reads an env
   var via `ctx.secrets.read(key)` and returns `None` on a missing key
   (not an exception). Requires `secrets.read`.
3. **Bounded-lifecycle adapter.** `ExampleAdapter` implements
   `start(ctx)` + `stop()` against the Phase 43
   `asyncio.wait_for(timeout=2.0)` ceiling. Both hooks return in
   microseconds.
4. **One package contributing both tools and an adapter.** The single
   `horus-plugin.toml` registers both `[[contributions.tools]]` entries
   AND a `[[contributions.adapters]]` entry, proving that one Python
   distribution can contribute multiple plugin surfaces at once.

## How to install

From the repo root, after horus-os is installed in editable mode:

```
pip install -e ./examples/horus-os-example-plugin
horus-os plugins grant horus-os-example-plugin --all
```

The first command installs the plugin into the same Python environment
that runs horus-os. The second confirms the two capability grants
(`filesystem.read` and `secrets.read`) under the default-deny policy.

## Anatomy

`pyproject.toml` is the PEP 621 metadata file. It declares the
`[project.entry-points."horus_os.plugins"]` table — the discovery seam
the host uses to find plugins via `importlib.metadata.entry_points`.
The single entry `horus-os-example-plugin = "horus_os_example_plugin"`
maps the manifest's `name` field to the importable Python package.

`horus-plugin.toml` is the manifest. It declares the eleven top-level
fields the v1 schema requires (`manifest_version`, `name`, `version`,
`description`, `author`, `license`, `horus_os_compat`, `homepage`,
`issue_tracker`, `capabilities`, `contributions`). The
`[[contributions.tools]]` array registers two tools; the
`[[contributions.adapters]]` array registers one adapter. The
`capabilities` array lists the two grants the tools need; the adapter
needs no grant.

`src/horus_os_example_plugin/tools.py` defines `echo_text_tool` and
`lookup_secret_tool`. Each is decorated with
`@require_capability(...)`. The `CapabilityGuard` wrap site reads the
attached `__horus_required_caps__` tuple and raises `PermissionDenied`
when any required cap is missing from the granted set.

`src/horus_os_example_plugin/adapter.py` defines `ExampleAdapter`.
`start(ctx)` schedules a no-op background task with
`asyncio.create_task(asyncio.sleep(0))`. `stop()` cancels and awaits
the task under a `try / except asyncio.CancelledError` block. Both
methods return promptly — well inside the host's 2-second timeout.

`src/horus_os_example_plugin/__init__.py` is a marker module with
empty `__all__`. The public surface is the entry-point group, not bare
attribute imports.

`tests/test_example_plugin.py` covers all four scenarios in-process
with the tier-1 helpers from `tests/plugins/conftest.py`.

## Using this as a starting point

You may copy this directory wholesale and rename three identifiers to
start a new plugin:

* `horus-os-example-plugin` (the distribution name in `pyproject.toml`,
  the manifest `name` field, and the entry-point key) -> your plugin's
  dist name.
* `horus_os_example_plugin` (the Python package directory under
  `src/`, the dotted-path prefix in every manifest entry_point line,
  and the entry-point value) -> your plugin's package name.
* `ExampleAdapter` (the class in `adapter.py` and the
  `[[contributions.adapters]]` entry_point value) -> your adapter
  class.

Then redeclare your `[capabilities]` set, add or remove tool
contributions, and run `pip install -e .` against the host venv.

## See also

* [docs/PLUGINS.md](../../docs/PLUGINS.md): plugin author guide,
  walkthrough of these four scenarios.
* [docs/PLUGIN-SECURITY.md](../../docs/PLUGIN-SECURITY.md): threat
  model, trust contract, what v0.5 does NOT defend against.
