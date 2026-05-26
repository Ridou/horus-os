# Pitfalls Research

**Domain:** Adding a third-party plugin system to horus-os v0.5 — manifest contract, entry-point + local-directory discovery, capability-declared permission grants, `pip install`-wrapped installer, dashboard plugins tab, in-process execution (no OS-level sandbox in v0.5).
**Researched:** 2026-05-26
**Confidence:** HIGH for the failure modes (verified against pytest/pluggy, Datasette, Pelican namespace-package design, `importlib.metadata` 3.10→3.12 behavior change documented in CPython docs, Wiz / Truesec / Checkmarx writeups on PyPI supply-chain attacks via entry points and `.pth` files, OTel-bounded-shutdown precedent shipped in v0.4 Phase 38). MEDIUM only on "what fraction of v0.5 plugin authors will trip Pitfall 3 vs Pitfall 5" — those are guesses; the trap itself is verified.

## Scope and Sibling Cross-References

This file ONLY covers v0.5 plugin-system pitfalls. Generic FastAPI / SQLite / Python pitfalls and v0.4-resolved observability pitfalls are out of scope (see the prior PITFALLS.md committed 2026-05-25 for those).

Where existing horus-os v0.4 code already locks a position, this file builds on it instead of re-arguing:

- **`src/horus_os/adapters/base.py:233`** already swallows `Exception` in `discover_adapters()` so a broken third-party adapter cannot kill the app. That is the right shape; Pitfall 6 builds on it with a stronger "swallow plus emit a structured failure" contract for plugins.
- **`src/horus_os/server/api.py:99-116`** wraps adapter `start`/`stop` in `try/except` but **without a timeout**. That is fine when we ship the adapters ourselves; it is not fine when a third-party plugin's `start()` decides to `time.sleep(600)` or wait on a dead network. Pitfall 7 mandates `asyncio.wait_for` in v0.5 in the same shape v0.4 Phase 38 used for `OtelAdapter.shutdown(timeout=2000ms)`.
- **`src/horus_os/observability/bus.py`** (`ObservationBus`) is the v0.4 substrate. Pitfall 8 says every plugin-emitted event must carry a `plugin_name` attribution column, otherwise v0.4's rollups will attribute errors to "the registry" rather than to the offending plugin.
- **`src/horus_os/storage.py:28`** has `SCHEMA_VERSION = 5`. Pitfall 10 mandates v5→v6 is additive-only and v0.4 databases must continue to read — the same contract v0.4 Phase 32 honored on v4→v5.
- **`src/horus_os/tools/registry.py:23`** already raises `ValueError("Tool ... is already registered")` on duplicate registration. Pitfall 3 builds on that with a plugin-attributed error message so the user sees *which* plugin lost the collision.

The v0.5 milestone PROJECT.md is explicit that **OS-level sandbox isolation is out of scope for v0.5**. Every pitfall below assumes in-process loading. That assumption is also the single largest threat-model surface, which is why Pitfall 1 is non-negotiable.

Cited prior art (URLs at the bottom): CPython `importlib.metadata` 3.10/3.11/3.12 docs, [pypa/setuptools#510](https://github.com/pypa/setuptools/issues/510) (`pkg_resources` import cost), [catkin/catkin_tools#297](https://github.com/catkin/catkin_tools/issues/297) (entry-point discovery >200ms), [unslothai/unsloth#1859](https://github.com/unslothai/unsloth/issues/1859) (60s import via entry points), Datasette plugin model and `datasette install` shape, Pelican 4.5+ namespace-package plugins, pluggy hook-collision design, [Wiz LiteLLM TeamPCP writeup](https://www.wiz.io/blog/threes-a-crowd-teampcp-trojanizes-litellm-in-continuation-of-campaign) on PyPI supply-chain, [Checkmarx Command-Jacking](https://checkmarx.com/blog/this-new-supply-chain-attack-technique-can-trojanize-all-your-cli-commands/) on entry-point hijacks and `.pth` arbitrary execution, Confluent / Conduktor schema-evolution rules.

## Critical Pitfalls

### Pitfall 1: Default-allow capability grants normalize compromise

**What goes wrong:**
v0.5 ships in-process plugin execution. A plugin's code runs in the same Python process as horus-os, with the same file descriptors, the same env vars, and access to the same `~/.horus-os/secrets.json`. If `horus-plugin.toml` lists `capabilities = ["filesystem.read", "filesystem.write", "net.outbound", "secrets.read"]` and we render that as a one-button "Install" with no per-capability prompt, the user has effectively granted a stranger arbitrary code execution on their laptop. The Wiz/Truesec LiteLLM writeups (PyPI v1.82.7 / 1.82.8 trojanized within hours of publication, 2025) and Checkmarx's command-jacking research show this is not theoretical: malicious entry-point hijacks and `.pth`-file arbitrary execution are an active 2025-2026 attack surface in PyPI. Plugin code IS arbitrary code execution — the only question is whether the user knowingly grants it.

**Why it happens:**
Adoption pressure. The frictionless "datasette install datasette-foo" UX is what made the Datasette plugin ecosystem viable, and a v0.5 reviewer will reasonably argue that any prompt the user does not understand will be click-throughed. That reviewer is correct that prompts get ignored — but the right response is to make the *prompt content* legible (one-line plain-English capability descriptions, not a JSON dump), not to remove the prompt. Datasette itself does NOT have a capability grant model on plugin install for exactly this reason: it punts to the user's pip trust. horus-os v0.5 must do better because we are a single-user desktop product with credentials on disk — the blast radius is higher than a multi-tenant API gateway.

**How to avoid:**
- **Default-deny posture in code, not just docs.** `src/horus_os/plugins/permissions.py` exposes `check_capability(plugin_name, capability) -> bool` that returns False unless an explicit grant row exists in `plugin_capability_grants` for the *exact (plugin_name, plugin_version, capability)* tuple. Plugin-facing helpers (a `filesystem` shim, a `secrets` shim, a `net` shim) call `check_capability` first and raise `PermissionDenied` otherwise. The default for every shim is deny; the grant table is the only path to allow.
- **Capabilities are declared in `horus-plugin.toml` and re-prompted on every change.** If v1.0 of plugin foo requested `filesystem.read` and v1.1 requests `filesystem.read, filesystem.write`, the upgrade is gated by a re-prompt; the existing grant does NOT carry forward. Pinned to `plugin_version` in the grant table; never to `plugin_name` alone.
- **One-line plain-English description per capability** lives in `src/horus_os/plugins/capability_catalog.py`. Example: `"filesystem.read": "Read any file in your home directory, including notes, secrets, and SSH keys."` The installer surfaces this string verbatim, never the dotted-key. The catalog is closed: a plugin requesting an unknown capability key is **refused** at install time (`ManifestError: unknown capability 'filesystem.god_mode'`), not silently granted nothing.
- **Threat model lives in `docs/PLUGIN-SECURITY.md`** and is linked from the install confirmation screen. Explicit statement: "Plugins run in the same Python process as horus-os. A plugin you have granted `filesystem.read` can read your secrets file. We do not sandbox plugins at the OS level in v0.5. Only install plugins from authors you trust." That sentence is the truth and refusing to write it down does not change it.
- **No `eval`, no `exec`, no `__import__` from plugin-supplied strings.** Plugin code is loaded via the entry-point mechanism only. The installer never accepts a `code` string field.

**Warning signs:**
- Any code path where `plugin_capability_grants` is checked-then-not-used (TOCTOU); the helper shims must raise before returning, not return-and-trust the caller.
- A capability declared in `horus-plugin.toml` is never actually consumed by the plugin — sign the plugin is over-requesting; the dashboard should show "requested but never used in last 30d" as a hint to revoke.
- A plugin process opens a file outside `~/.horus-os/plugins/<plugin_name>/` without holding the `filesystem.read` grant. (We cannot strictly enforce this without OS isolation; we *can* monkey-patch `builtins.open` in the plugin's module namespace and lint for raw `open()` in PR review of the reference plugin.)

**Phase to address:**
**Phase 41-42 (manifest schema + permission model substrate)**, **Phase 44 (installer surface)**, **Phase 47 (docs trio including threat model)**. Owned by PLUG-01, PLUG-02 (default-deny), MANIFEST-03 (capability declaration), and a `docs/PLUGIN-SECURITY.md` deliverable on the release-gate phase. The default-deny posture must land BEFORE the installer ships; an installer that grants by default then "we will tighten it later" is the trap that turns into the v0.6 CVE.

---

### Pitfall 2: Manifest schema drift — adding a v2 field silently breaks every v1 plugin OR silently underuses every v2 plugin

**What goes wrong:**
v0.5 ships `manifest_version = 1` with five top-level fields (`name`, `version`, `entry_points`, `capabilities`, `horus_os_compat`). v0.6 wants to add a `signing_key_fingerprint` field. Naively, the loader either (a) refuses to load v1 plugins because they are missing the new field, breaking every published plugin, or (b) loads v2 plugins under a v1 codepath that never reads the new field, silently granting unsigned plugins the trust they would have been denied. Confluent and Conduktor's schema-evolution rules call this out as the "add an optional field with a default" discipline; Pelican learned it the hard way in the v4.5 namespace-package migration when older plugins stopped working without an explicit shim.

**Why it happens:**
The first version of a schema is always under-specified. A v0.5 reviewer optimistically declares "we can add fields later." That is *true*, but only if v1 was designed knowing that. If `manifest_version` is not a top-level field from day one, you cannot tell v1 from v2. If unknown fields raise instead of being ignored, every v1 loader rejects v2 plugins. If unknown fields are silently ignored without a corresponding `min_loader_version` field on the manifest, the plugin author cannot signal "I require a feature that landed in v0.6 to function correctly."

**How to avoid:**
- **`manifest_version: int` is a required top-level field from day one.** v0.5 ships `manifest_version = 1`. The loader reads it first and refuses any value it does not know how to load (`ManifestError: manifest_version=2 not supported by horus-os 0.5; please upgrade`).
- **Forward-compatibility rule: additive only.** v6 (whenever it ships) may add new optional top-level fields with default values; may NOT remove fields, rename fields, or change a field's type. This is the Confluent "Forward" compatibility class. Encoded as a test fixture: `tests/fixtures/manifest_v1_minimum.toml` ships at v0.5 and MUST continue to load unmodified through every future loader version. CI runs a parametrized test across every shipped manifest version.
- **`min_horus_os_version: str` is a required top-level field** so a v0.6-only plugin can refuse to load on v0.5 with a clear error rather than crashing at runtime when the missing API is called.
- **Unknown top-level fields are warned, not refused.** When loading a v1 manifest with an unknown key `signing_key_fingerprint`, the loader logs `WARN: unknown manifest field 'signing_key_fingerprint' in plugin foo; this field is ignored under manifest_version=1.` This way a plugin can be authored against v2 and still load (with warnings) on v0.5; the user sees an actionable upgrade message.
- **Migration is a pure function, tested explicitly.** `src/horus_os/plugins/manifest.py` exposes `load_manifest(path: Path) -> PluginManifest` that normalizes v1 manifests to the current internal representation. The v2-loader normalizes v1 by filling defaults. A test asserts `load_manifest('v1.toml') == load_manifest('v2_same_intent.toml')` after normalization.

**Warning signs:**
- Anything that reads `manifest['some_field']` without going through `PluginManifest.field_with_default`. Direct dict access is the place schema drift hides.
- A field renamed in a PR (e.g. `entry_points` → `entrypoints`). That is always a breaking change; the reviewer must add a deprecation alias for at least one minor version.
- The `min_horus_os_version` field is not enforced — a plugin built against v0.7 features installs cleanly on v0.5 and crashes at first invocation.

**Phase to address:**
**Phase 41 (manifest schema)**, owned by MANIFEST-01 (versioned manifest), MANIFEST-02 (top-level required-fields contract), MANIFEST-04 (forward-compat test matrix). The `manifest_version` field decision must be locked at requirements time; renaming it post-launch is itself a breaking change.

---

### Pitfall 3: Entry-point discovery API drift (3.10 → 3.11) and `pkg_resources` import cost

**What goes wrong:**
Two distinct traps under one name:

1. **API drift.** `importlib.metadata.entry_points()` returned a `dict`-like `SelectableGroups` in 3.10; returns an `EntryPoints` object that no longer supports the dict interface starting 3.12 (selectable API is the only supported shape; the dict shim was removed). The horus-os 3-OS gate covers 3.11 and 3.12. Code written naively as `entry_points()['horus_os.plugins']` works on 3.11 (with a `DeprecationWarning`), raises `TypeError` on 3.12. The bug appears only on the second Python version in CI; a developer who only runs locally on 3.11 will not see it.
2. **`pkg_resources` is the WRONG mechanism.** [`pypa/setuptools#510`](https://github.com/pypa/setuptools/issues/510) and [`catkin/catkin_tools#297`](https://github.com/catkin/catkin_tools/issues/297) document `pkg_resources` import cost at 1.3-1.5 seconds and entry-point discovery at >200ms. [`unslothai/unsloth#1859`](https://github.com/unslothai/unsloth/issues/1859) reports 60-second `import` times via entry points. If a v0.5 contributor reaches for `pkg_resources` (the older sibling, still widely shown in stale tutorials), the horus-os CLI startup goes from "instant" to "second and a half" — exactly the regression v0.4 Phase 33's capture-overhead benchmark was designed to catch but does not (it does not exercise plugin discovery).

**Why it happens:**
The two APIs (`pkg_resources` and `importlib.metadata`) overlap, and Stack Overflow's top result is still the deprecated one. The selectable-API migration in 3.10→3.12 is documented but easy to miss when copy-pasting old code. The error shape is "works on my machine" because the maintainer's local Python matches the deprecated shim.

**How to avoid:**
- **`src/horus_os/plugins/discovery.py` uses `importlib.metadata.entry_points(group=...)` only.** Already the shape used in `src/horus_os/adapters/base.py:217`; copy that shape verbatim. Forbid `pkg_resources` via a ruff rule: `grep -r "import pkg_resources\|from pkg_resources" src/ && exit 1` in CI.
- **Entry-point group is namespaced: `horus_os.plugins`** (matching the existing `horus_os.adapters` shape). Sub-groups for tool plugins vs adapter plugins are nested: `horus_os.plugins.tools`, `horus_os.plugins.adapters`. Namespacing per the [Python packaging spec](https://packaging.python.org/specifications/entry-points/) prevents collisions with unrelated `tools` entry-point groups in the global PyPI namespace.
- **Discovery is lazy.** `src/horus_os/plugins/discovery.py` does NOT call `entry_points(...)` at module import. It exposes `discover_plugins(force_refresh=False) -> list[PluginRecord]`, called once during FastAPI lifespan startup and cached. CLI subcommands that do not touch plugins (e.g. `horus-os --version`) never trigger discovery. A `tests/test_cli_cold_start_perf.py` test asserts `horus-os --version` completes in <100ms cold (per the v0.3 baseline shape).
- **Test on both 3.11 and 3.12 in CI.** The existing 3-OS matrix already does this; add a parametrized test `tests/test_plugin_discovery_api_shape.py` that walks the EntryPoints object both ways (`select()` and iteration) so a 3.12-only shape is structurally required.
- **Name-collision handling is explicit and attributed.** If two plugins both declare a tool named `read_file`, the second registration call goes through `ToolRegistry.register(replace=False)` and raises `ValueError("Tool 'read_file' is already registered")` — that v0.3 shape is correct. The plugin loader catches this and surfaces `PluginConflictError: plugin 'bar' tried to register tool 'read_file' but it is already provided by plugin 'foo'. Disable one of them in the dashboard.` Never silently overwrite; never raw-raise the ValueError without plugin attribution.

**Warning signs:**
- Any `import pkg_resources` in `src/` — fail the build.
- `entry_points()` called without a `group=` keyword argument — works on 3.10 deprecation shim, breaks 3.12 in unpredictable ways. Lint rule.
- A `PluginConflictError` raised without a `plugin_name` attribution string in its `__str__` — the user must always know *which* plugin lost.
- `horus-os --version` cold-start regresses past 100ms.

**Phase to address:**
**Phase 42 (discovery + loading)**, owned by PLUG-03 (entry-point discovery) + PLUG-04 (local-directory discovery). The lint rule and cold-start benchmark must land in the same phase so the regression cannot ship.

---

### Pitfall 4: `pip install`-wrapped installer can corrupt the host venv

**What goes wrong:**
`horus-os plugins install foo` shells out to `pip install foo` in the active venv. Six concrete failure shapes, each producing a different broken state:

1. **Network failure mid-install.** Wheel partially downloaded; pip leaves a half-written `.dist-info` directory; subsequent `pip list` shows the package, but the import target is missing files. The next horus-os startup sees the entry point, tries to load it, raises `ModuleNotFoundError`.
2. **Conflicting dependency pin.** Plugin foo requires `httpx==0.25.0`; horus-os is on `httpx==0.27.0`. `pip install` downgrades httpx without asking and breaks horus-os itself.
3. **Wheel incompatibility.** Plugin foo ships only manylinux2014 wheels; user is on macOS arm64. pip falls back to sdist, which fails to build because `gcc` is not installed. The installer reports "install failed" and the venv is fine, but the error message is the pip backtrace, not "this plugin is not compatible with your platform."
4. **Permission denied.** User is running horus-os under a system Python (not a venv). `pip install` tries to write into `/usr/lib/python3.12/site-packages` and fails. Or the user is on Windows with the Python from the Microsoft Store and writes go to `%LOCALAPPDATA%\Packages\PythonSoftwareFoundation.*` — pip succeeds but the entry point is invisible to the horus-os runtime because the import path differs.
5. **`pip install` triggers `setup.py` arbitrary code execution.** A malicious sdist's `setup.py` runs at install time, in the active venv, BEFORE the manifest is ever validated. The capability-grant prompt happens too late: the attacker already executed code during the pip step.
6. **`pip install` succeeds, plugin imports successfully, plugin's `.pth` file adds an arbitrary directory to `sys.path`** (the [Checkmarx command-jacking technique](https://checkmarx.com/blog/this-new-supply-chain-attack-technique-can-trojanize-all-your-cli-commands/)). The malicious code runs on every subsequent Python invocation, not just inside horus-os.

**Why it happens:**
`subprocess.run(["pip", "install", spec])` is the obvious-feeling first implementation. Datasette's `datasette install` shape (a thin wrapper around `pip install` in the same venv) IS what we want for v0.5, but Datasette's documented stance is "trust pip"; horus-os v0.5 cannot accept that wholesale because we have credentials on disk and ship a capability grant model that promises trust boundaries.

**How to avoid:**
- **Refuse to install if not inside a venv.** `sys.prefix == sys.base_prefix` is True for system Python and False for venv/virtualenv. The installer refuses with `RuntimeError: horus-os plugins install must be run inside a virtualenv. See docs/PLUGINS.md.` Documented in `docs/PLUGINS.md`. This is a hard wall; do not paper over with `--user`.
- **Use the same Python that's running horus-os, never bare `pip`.** Shell out to `[sys.executable, "-m", "pip", "install", "--require-virtualenv", spec]`. The `--require-virtualenv` flag is pip's built-in version of the previous rule, defense-in-depth.
- **Two-phase install: download-only, then validate, then install.** Phase A: `pip download --no-deps --dest <tmp> <spec>` resolves the wheel/sdist but does NOT execute setup.py. Phase B: unpack the wheel (or refuse if only sdist available — see below), parse `horus-plugin.toml`, surface the capability prompt, get user consent. Phase C: `pip install --no-deps --no-build-isolation <wheel>` actually installs. **Refuse sdist by default.** A `--allow-sdist` flag is available for developers shipping their own plugins; the documented warning is "sdist installs execute arbitrary code in your venv before manifest validation. Only allow sdist installs for plugins you author." This closes the Pitfall 1 / setup.py escape hatch.
- **Dependency-pin policy: refuse to downgrade horus-os runtime deps.** Phase B parses the wheel's `METADATA` for `Requires-Dist:` lines. If any pin would conflict with horus-os's own pinned deps (the lock file shipped at release), the installer refuses with a precise error: `PluginInstallError: plugin foo requires httpx<0.26 but horus-os requires httpx>=0.27. This plugin is not compatible with this version of horus-os.` Never silently downgrade.
- **Detect `.pth` files in the wheel before install.** A `.pth` file in a plugin wheel is a red flag (it runs at every Python startup, not just when the plugin is loaded). Phase B refuses any wheel containing `*.pth` in `RECORD` with `PluginInstallError: plugin foo ships a .pth file, which would execute on every Python startup. This is not allowed for horus-os plugins.`
- **Rollback on partial failure.** If install fails midway (wheel downloaded but install errored), Phase C calls `pip uninstall -y <plugin>` immediately. The `tests/test_installer_rollback.py` fixture simulates a wheel that imports cleanly but raises in its `__post_init__`; assertion: venv state after rollback equals venv state before install (`pip freeze | sha256sum` round-trip).

**Warning signs:**
- A `pip install` step in the installer that runs BEFORE manifest validation. Setup.py executes during install; the prompt is too late.
- The installer ever calls `pip` with a string command (`subprocess.run("pip install ...", shell=True)`) — both because shell=True invites injection and because it bypasses `sys.executable -m pip`.
- A plugin install succeeds but `horus-os plugins list` doesn't show the new plugin. Means the entry point is registered to a different Python interpreter than the one running horus-os; the venv check failed.
- A `pip install` corrupted the venv such that `from horus_os.config import Config` no longer imports. The smoke test in CI must catch this: after every installer test, `python -c "import horus_os; horus_os.__version__"` must succeed.

**Phase to address:**
**Phase 44 (installer flow)**, owned by DIST-01 (installer CLI), DIST-02 (two-phase install), DIST-03 (venv check + sdist refusal + .pth refusal), DIST-04 (rollback on partial failure). The sdist-refusal default must land in v0.5; relaxing it later is easier than tightening it.

---

### Pitfall 5: Permission grant model abused via plugin update — silent capability expansion

**What goes wrong:**
User installs plugin `foo` v1.0 which requests `filesystem.read`. User grants. User runs `horus-os plugins upgrade foo` and v1.1 has expanded to `filesystem.read, filesystem.write, net.outbound, secrets.read`. If the grant is keyed on `plugin_name` rather than `(plugin_name, plugin_version, requested_capability_set)`, the upgrade silently inherits the v1.0 grant — and the user just gave a plugin author the keys to their notes and outbound network access without a re-prompt. This is the [Wiz LiteLLM TeamPCP](https://www.wiz.io/blog/threes-a-crowd-teampcp-trojanizes-litellm-in-continuation-of-campaign) shape: not the v1.0 author being malicious, but the v1.0 author's PyPI account being compromised and a malicious v1.1 being published. The user had no reason to suspect the upgrade.

**Why it happens:**
"Grants are per-plugin" is the obvious-feeling first model; "users hate re-prompts" is the obvious-feeling first UX rule. Both are wrong when combined. The right model is "grants are per (plugin_name, plugin_version)" with an explicit re-prompt on capability change; the right UX is to make the re-prompt zero-friction for the *unchanged* capability set ("foo upgraded from 1.0 to 1.1; no new permissions requested; OK to proceed?" → enter to confirm) and high-friction for the *expanded* set ("foo upgraded from 1.0 to 1.1; it now wants to: WRITE to your filesystem, MAKE OUTBOUND NETWORK CALLS, READ your secrets file. Type 'grant' to allow these new permissions, or 'skip' to upgrade with only the previously-granted permissions.")

**How to avoid:**
- **Grants are keyed on `(plugin_name, plugin_version_major_minor, capability)`.** Schema in `plugin_capability_grants`: `(plugin_name TEXT, plugin_version TEXT, capability TEXT, granted_at TIMESTAMP, granted_by TEXT, PRIMARY KEY (plugin_name, plugin_version, capability))`. On upgrade, the grants for v1.0 are NOT inherited by v1.1; the installer computes the diff between v1.0's manifest capability set and v1.1's set.
- **Three diff outcomes, three UX shapes:**
  1. **Set unchanged.** Installer auto-grants all v1.1 capabilities (silent inherit) and shows a one-line confirmation: `foo upgraded 1.0 → 1.1; no permission changes.`
  2. **Set shrunk** (v1.1 wants strictly fewer caps). Installer auto-grants v1.1's set; shows `foo upgraded 1.0 → 1.1; permissions reduced to: filesystem.read.`
  3. **Set expanded or replaced.** Installer surfaces the diff as a re-prompt; user types `grant` or `skip`. `skip` upgrades the plugin but keeps only the *intersection* of old and new grants; the plugin may fail at runtime when it tries to use an ungranted capability, which is the correct behavior (fail-closed).
- **Audit log on every grant.** `plugin_capability_grants_log` table appends one row per grant/revoke with `actor` (the user, via the CLI prompt or dashboard click), `timestamp`, `from_state`, `to_state`. Surfaced in the dashboard's plugin detail page so the user can answer "when did I grant write access?"
- **Grant fatigue mitigation: bundles, not enumeration.** Common capability bundles are named in `capability_catalog.py`: `"basic_tool"` = `{filesystem.read_plugin_dir, net.outbound_for_declared_hosts}`, `"read_only_assistant"` = `{filesystem.read, net.outbound}`. The reference plugin uses a bundle, not a long list of dotted caps, so authors see "use a bundle" as the path of least resistance. Bundles are still backed by individual cap rows in the grants table so revocation can be granular.
- **The grant prompt is interactive in the CLI, modal in the dashboard.** Never a YAML config the user is expected to edit; that path is the "grant fatigue → curl | bash this YAML" anti-pattern.

**Warning signs:**
- A grant lookup uses `WHERE plugin_name = ?` without `plugin_version`. Code review red flag.
- Plugin upgrade does not log a row to `plugin_capability_grants_log`. The audit gap is the symptom; the grant inheritance bug is the cause.
- A capability used by a plugin without a grant row in the table at the requesting version. The shim helper must raise `PermissionDenied` at runtime; if it returns instead, the model is leaking.
- Dashboard plugin detail page does not show the granted capability set. Users cannot reason about trust they cannot see.

**Phase to address:**
**Phase 43 (permission model substrate)** + **Phase 45 (dashboard plugins tab — UI for grant prompts and audit log)**. Owner: PLUG-05 (per-version grant keying), PLUG-06 (diff-based re-prompt), DASH-5-02 (audit log surface). The per-version keying must land BEFORE the installer ships upgrade support, otherwise v1.0 → v1.1 ships with the inheritance bug baked in.

---

### Pitfall 6: Plugin failures crash horus-os instead of degrading to "plugin error" status

**What goes wrong:**
A third-party plugin's `bind()` raises `TypeError` because the author called `app.add_router` instead of `app.include_router`. If the FastAPI lifespan does not catch it, the entire horus-os process exits at startup. The user has no dashboard to disable the broken plugin, no CLI subcommand to mark it disabled (the CLI starts the same FastAPI app and dies the same way), and no recovery path other than uninstalling the wheel manually. v0.4's `src/horus_os/adapters/base.py:233` already swallows exceptions in `discover_adapters`, but `bind` and `start` lifecycle hooks are NOT wrapped at the same isolation level for third-party plugins.

**Why it happens:**
The v0.1-0.4 adapters are first-party code — if `bind()` raises, the maintainer's CI catches it before users see it. Third-party plugin authors do not run our CI. The first time a malformed `bind()` happens in production is on a user's laptop, and we cannot ship a patch as fast as we can ship a "your plugin foo is in error state; disable it from /plugins" message.

**How to avoid:**
- **Every third-party plugin entry point is wrapped in `try/except Exception` at every lifecycle boundary** (discover, manifest-load, bind, start, stop, tool-invoke, adapter-event). A failure marks the plugin as `status=error` in `plugin_registry`, records the exception's `type(e).__name__: str(e)` (never the user-supplied content of the exception's args — same rule as Pitfall 9 in v0.4 PITFALLS.md), and continues the rest of startup. Failure modes:
  - **discover failure** (entry point dotted path does not resolve): plugin record is created in `plugin_registry` with `status=error`, `error_message="ImportError: ..."`, `last_error_at=now`. Other plugins still discover.
  - **manifest-load failure** (`horus-plugin.toml` invalid): plugin record `status=manifest_error`. Plugin code is NEVER imported until the manifest validates.
  - **bind failure**: `status=bind_error`. The plugin's tools / adapters are unregistered from the master registries (no half-bound state).
  - **start/stop failure**: `status=lifecycle_error`. Already the shape used for first-party adapters at `server/api.py:99-116`; extend to plugins.
  - **tool-invoke failure**: tool returns an error result (the v0.3 `ToolResult.error` shape), increments `plugin_registry.error_count`, does NOT change `status` (a tool error is normal; a *consistently failing* tool is a separate concern handled in Pitfall 8).
- **Plugins can be disabled without uninstalling.** `plugin_registry.enabled BOOLEAN DEFAULT 1`; the dashboard toggle and `horus-os plugins disable <name>` set it to 0. A disabled plugin is skipped during discovery (not bound, not started, no tools registered). The user has a recovery path that doesn't require touching pip.
- **Bounded timeouts on lifecycle hooks** — same shape as v0.4 Phase 38's OTel bounded shutdown:
  - `bind(app, context)` is called synchronously (matches v0.4 adapter shape); a synchronous hang in `bind` is the plugin author's problem to fix and is observable (the lifespan never completes). We DO log `WARN: plugin foo bind() has been running for >5s` from a watchdog task to surface the hang.
  - `start(context)` is `await asyncio.wait_for(plugin.start(ctx), timeout=2.0)`. Hard 2s budget. Plugins that need a long-running task to be fully ready before serving requests must do their own backgrounding inside the 2s budget — schedule a `loop.create_task(self._connect())` and return; the background task can take as long as it wants. v0.4 Phase 38 used 2000ms for the same reason on OtelAdapter shutdown.
  - `stop()` is `await asyncio.wait_for(plugin.stop(), timeout=2.0)`. Same shape.
- **Lifespan continues on plugin failure.** The current `server/api.py:99-116` shape does this for `start`. v0.5 extends it to bound the wait *and* to surface the failure in the dashboard's plugin tab, not just the error log.

**Warning signs:**
- A plugin's `start()` raise that propagates out of the lifespan. Means the wrapper is missing or `wait_for` is missing.
- The horus-os process exits during startup with a plugin's exception class in the traceback. Hard regression: filed as a P0.
- `plugin_registry` table never has a row with `status=lifecycle_error` even though the dev-fixture broken-plugin test exists. Means the wrapper is catching too late.
- `horus-os plugins list` hangs because a plugin's `bind()` is in an infinite loop. The watchdog log should warn at 5s; the user has the option to Ctrl-C and disable the plugin via `--disable-all-plugins` flag.

**Phase to address:**
**Phase 42 (discovery + loading)** for the discover/manifest wrappers, **Phase 43 (lifecycle integration)** for bind/start/stop wrappers with `asyncio.wait_for`, **Phase 46 (failure-isolation tests)** for the broken-plugin fixture. Owned by ISOLATE-01 (status enum), ISOLATE-02 (bounded lifecycle), ISOLATE-03 (broken-plugin fixture in tests). The bounded-timeout pattern is a direct port of the v0.4 TEST-14 contract.

---

### Pitfall 7: Plugin observability gaps — v0.4 rollups attribute errors to "the registry" not to the plugin

**What goes wrong:**
v0.4's `ObservationBus` publishes `LLMCallEvent`, `ToolCallEvent`, `RunEndEvent`. The `ToolCallEvent.tool_name` field identifies *which tool* was called but does NOT identify *which plugin* registered that tool. When a third-party plugin's tool `read_file` fails on every invocation, the v0.4 observability rollup shows "tool read_file: 47 errors in last 24h" attributed to nothing in particular. The user has no way to answer "which plugin do I disable to make this stop?" — they have to grep the codebase to find out who registered `read_file`, and that's assuming they have the source for every installed plugin.

**Why it happens:**
v0.4's bus was designed when all tools were first-party; the bus events did not need to carry plugin attribution because the answer was always "horus-os core." v0.5 changes that assumption silently if we don't update the bus. The v0.4 schema migration (v4→v5) added rollup columns to `traces`; v0.5 needs another migration (v5→v6) to add `plugin_name` to `llm_calls` and `tool_invocations`.

**How to avoid:**
- **v5→v6 additive migration adds `plugin_name TEXT NULL` to `llm_calls` and `tool_invocations`.** NULL = first-party tool / core LLM call. Non-NULL = a specific plugin. Index on `(plugin_name, created_at)` for the dashboard rollup.
- **Every event emitted from a plugin's code path carries `plugin_name`.** The plugin context (`PluginContext`, sibling to `AdapterContext`) holds the plugin's name; the helper shim `ctx.tool_registry.register(...)` injects the plugin name into a closure around the tool's handler so the resulting `ToolCallEvent` carries `plugin_name = ctx.plugin_name` automatically. Plugin authors do not have to remember to do this; the registry wrapper does it for them.
- **v0.4 rollup queries grow a `GROUP BY plugin_name` axis.** New routes: `/api/observability/plugins` returns `{plugin_name, total_invocations, error_count, p50_latency_ms, last_error_at}` per installed plugin. The dashboard's existing `/observability` tab gains a "by plugin" filter selector. Pre-v0.5 rows (where `plugin_name IS NULL`) roll up under `plugin_name = "horus-os core"` so the math stays honest.
- **Per-plugin error rate surfaces on the plugins dashboard tab.** Above each plugin's row, the dashboard shows "12 tool invocations in last 24h, 2 errors (16.7% error rate)." A red badge appears if error rate exceeds a configurable threshold (default 50%). The user has a visible signal that one plugin is misbehaving without leaving the plugins page.
- **`scripts/release_gate.py`** (extending the v0.4 gate from Phase 39) adds a check that `plugin_name` is required-non-NULL in any row inserted via the plugin code path; a fixture plugin emits a tool call and the test asserts `SELECT COUNT(*) FROM tool_invocations WHERE plugin_name IS NULL AND created_at > <fixture_start>` returns 0.

**Warning signs:**
- A plugin's tool fails repeatedly but the dashboard's observability tab shows the error count rolling up under no plugin attribution. Means the `ctx.plugin_name` injection is not wired.
- A SELECT against `tool_invocations` after a real plugin invocation returns a row with `plugin_name IS NULL`. Hard regression.
- The v0.4 dashboard's `/observability` tab shows new plugin tools without any per-plugin rollup. Means Phase 45 (dashboard plugins tab) shipped without the v0.4 backend extension.

**Phase to address:**
**Phase 41 (manifest schema includes plugin_name as a required field)** sets up the attribution; **Phase 42-43 (loading + lifecycle)** wires `PluginContext.plugin_name` through to tool/adapter registration; **Phase 45 (dashboard + new /api/observability/plugins route)**. v5→v6 migration must land in Phase 41 alongside the manifest schema; the new columns must be NULLABLE so v0.4 databases continue to read (per Pitfall 10).

---

### Pitfall 8: The reference plugin is either too simple to teach or too coupled to internals

**What goes wrong:**
v0.5 ships `horus-os-example-plugin` as the "this is how you write a plugin" reference. Two failure shapes:

1. **Too simple to be useful.** The example plugin registers one tool that returns `"hello world"`. Plugin authors copy it and immediately have questions the example does not answer: how do I declare capabilities? How do I read config? How do I store state? What does `bind()` actually look like for a real adapter? The example becomes a starting point that nobody can extend. They copy patterns from the first-party adapters in `src/horus_os/adapters/` instead, which couples them to internal APIs that we may refactor.
2. **Too coupled to internals.** The example plugin imports from `horus_os._private` (or the equivalent leading-underscore module) because that's what the maintainer reaches for when they need the helpers. Now every third-party plugin imports `horus_os._private.foo`, and we cannot refactor it without breaking the ecosystem. This is the trap the Pelican 4.5 namespace-package migration walked into and had to clean up by carving out a stable public API.

**Why it happens:**
The example plugin is the last thing built before release, when the maintainer is fatigued and reaches for whatever's easiest. There's no rule that says "the example may only import from the public API" because there's no documented public API surface yet — v0.5 *is* the moment we draw that line.

**How to avoid:**
- **Define `src/horus_os/plugins/api.py` as the SINGLE public API surface for plugin authors.** Everything a third-party plugin needs is re-exported here: `PluginContext`, `Capability`, `Tool`, `Adapter`, `LifecycleAdapter`, `register_tool`, `require_capability`, `PluginConfig`. The example plugin's only `from horus_os` imports are `from horus_os.plugins.api import ...`. A CI lint rule rejects any other `from horus_os` import in the example: `grep -E "from horus_os\\.(?!plugins\\.api)" examples/horus-os-example-plugin/ && exit 1`.
- **Example covers four scenarios in one repo:**
  1. A simple tool that takes a capability (filesystem.read) and returns structured data — teaches capability checks.
  2. A "needs config" tool that reads from `ctx.plugin_config` — teaches plugin-local config.
  3. A "lifecycle adapter" with `start()` / `stop()` — teaches the async lifecycle shape.
  4. A "registers two tools and one adapter" plugin — teaches the manifest's `entry_points` table.
- **Example is shipped as a separate PyPI package** (`horus-os-example-plugin`) installed via the actual installer: `horus-os plugins install horus-os-example-plugin`. The example proves the install flow works end-to-end at every release. The release gate asserts the example installs cleanly into a fresh venv on each OS.
- **Example's README is THE plugin authoring guide.** It explains the manifest, the capability model, the registry, and the lifecycle in the order an author needs to learn them. `docs/PLUGINS.md` is a one-page "where to find what" pointer to the example's README and the api.py docstrings. Avoids the dual-source-of-truth trap where docs drift from code.
- **Reference plugin is dogfooded.** The example plugin's tools are wired into the existing `pytest` suite as a fixture so they run on every CI build. If we accidentally break the public API, the example's tests turn red BEFORE we cut a release. This is the v0.4 lesson learned the hard way: docs that aren't tested drift; examples that are tested don't.

**Warning signs:**
- The example's source has any `from horus_os._` (leading underscore) imports. CI rejects.
- A third-party plugin author opens an issue asking "how do I do X?" where X is something the example doesn't cover but the first-party adapters do. Means the example needs scenario expansion.
- The example's manifest uses a field that's not documented in `docs/PLUGINS.md`. Drift signal.
- `docs/PLUGINS.md` describes a pattern that the example doesn't implement. Same drift signal in reverse.

**Phase to address:**
**Phase 48 (reference plugin)** — owned by REL-10 (example plugin). The `plugins/api.py` public API surface must be **defined in Phase 41** (manifest schema phase) and the example built against it — not the other way around. Building the example first and then "deciding what's public" is how you end up exporting internal helpers.

---

### Pitfall 9: v5→v6 schema migration breaks v0.4 databases

**What goes wrong:**
v0.5 needs new tables (`plugin_registry`, `plugin_capability_grants`, `plugin_capability_grants_log`) and new columns (`plugin_name` on `llm_calls`, `tool_invocations`). A naive migration ALTER-TABLEs in `NOT NULL` columns, or DROP-TABLEs an old table that "we don't need anymore," or renames a column. Every one of those is a breaking change for v0.4 databases. A user who upgrades horus-os from 0.4.0 to 0.5.0 in place watches their database get corrupted at first startup. v0.4 Phase 32 set the precedent (v4→v5 was additive only, v0.3 fixture continued to read); v0.5 must hold the same line.

**Why it happens:**
The "we're adding plugin attribution; tool_invocations.tool_name and llm_calls.model_name should now be `NOT NULL`" is a tempting clean-up. So is "the schema_version table from v0.1 is awkward; let's normalize it." Both feel like good engineering hygiene; both break migration.

**How to avoid:**
- **`SCHEMA_VERSION = 6` in `src/horus_os/storage.py`. The v5→v6 migration is additive ONLY.** Concretely:
  - `CREATE TABLE IF NOT EXISTS plugin_registry (...)` — new table.
  - `CREATE TABLE IF NOT EXISTS plugin_capability_grants (...)` — new table.
  - `CREATE TABLE IF NOT EXISTS plugin_capability_grants_log (...)` — new table.
  - `ALTER TABLE llm_calls ADD COLUMN plugin_name TEXT` — NULLABLE; existing rows get NULL.
  - `ALTER TABLE tool_invocations ADD COLUMN plugin_name TEXT` — NULLABLE.
  - `CREATE INDEX IF NOT EXISTS idx_tool_invocations_plugin ON tool_invocations(plugin_name, created_at)`.
  - **Nothing dropped. Nothing renamed. Nothing made NOT NULL.**
- **`tests/fixtures/v0_4_database.sqlite3` is checked into the repo** (same pattern as `v0_3_database.sqlite3` for v4→v5). The test `tests/test_v5_to_v6_migration.py` opens the v0.4 fixture, calls `Database.init()`, asserts (a) all old tables still exist with their original schemas, (b) all old rows still read with their original values, (c) new tables exist and are empty, (d) new columns exist on old tables with NULL on pre-v0.5 rows, (e) running `init()` a second time is a no-op (idempotent).
- **Idempotency: running `init()` against an already-v6 database is a no-op.** SQLite's `IF NOT EXISTS` handles tables. For columns, the migration wraps each `ALTER TABLE` in a try/except for `sqlite3.OperationalError: duplicate column name` and swallows. Same pattern v0.4 Phase 32 used.
- **No DROP statements, anywhere.** Even for tables we are "sure" nobody uses. The cost of keeping them is one disk page; the cost of dropping them is a data-loss bug we cannot recall.
- **Migration runs BEFORE the bus and persister are wired** (matches v0.4 Phase 32's ordering). If migration raises, the rest of the app does not start; the database is in a known state (still v5, untouched).

**Warning signs:**
- A code review PR that adds `ALTER TABLE ... DROP COLUMN` or `ALTER TABLE ... RENAME COLUMN` — both are breaking changes, both should fail the review.
- A migration adds a column with `NOT NULL` default — works on empty databases, breaks on populated ones. Lint rule: `grep -E "ADD COLUMN.*NOT NULL" src/horus_os/storage.py && exit 1`.
- `tests/test_v5_to_v6_migration.py` fixture missing or test deleted. Hard block on release-gate.
- The v0.4 fixture's data does not survive the migration intact. Run a hash of `SELECT * FROM traces ORDER BY trace_id` before and after migration; it must match.

**Phase to address:**
**Phase 41 (schema migration)** must land BEFORE any plugin code that writes to the new tables. Owner: MIG-05 (v5→v6 additive migration), TEST-16 (v0.4 fixture round-trip test). Same shape as v0.4 Phase 32's BASELINE-01 ordering — schema infrastructure first, behavior change second.

---

### Pitfall 10: Default-deny vs default-allow first-run friction

**What goes wrong:**
The two failure modes are equally bad:

- **Default-deny is principled but creates friction.** User installs `horus-os-foo-plugin`, types `horus-os run`, sees `PermissionDenied: plugin foo requires capability filesystem.read which has not been granted.` User does not know what to do. The plugin's tools never run. The user uninstalls horus-os, writes a HN comment about how it's "too restrictive."
- **Default-allow gets adoption but undermines the model.** User installs a plugin, all capabilities are silently granted at install time, plugin works immediately. The capability declaration becomes decorative; the grant prompt becomes a TODO. When a malicious plugin ships, the user is unprotected.

The trap is choosing the wrong default to keep momentum.

**Why it happens:**
"Adoption first, security later" is the obvious startup intuition. It's wrong for a single-user desktop product with credentials on disk because "later" never happens — the user base now expects the default-allow behavior and tightening it is a breaking change.

**How to avoid:**
- **The v0.5 default IS default-deny, but with a frictionless first-prompt UX.** Concrete shape:
  - `horus-os plugins install foo` runs the two-phase install (Pitfall 4). Phase B's prompt is interactive in the CLI and modal in the dashboard. The prompt is ALWAYS shown — never skipped with a `-y` flag in v0.5. (A `-y` flag IS available but documented as "for CI use; not recommended for personal installs." That's the right balance: power users can script it, accidental users cannot click-through.)
  - The prompt's content is plain-English (per Pitfall 1's catalog), with the plugin's declared `description` field surfaced verbatim and an explicit link to the plugin's PyPI page so the user can see who published it.
  - **No grant carries forward from `pip install` itself.** The user explicitly granted `pip install` the ability to download and install packages; the user has NOT explicitly granted plugin foo `filesystem.read`. These are separate consents.
  - On first plugin run after install (if the user somehow installed via raw `pip install` and bypassed the prompt), the helper shim raises `PermissionDenied` with a recovery path: `Run 'horus-os plugins grant foo' to grant the required capabilities, or 'horus-os plugins disable foo' to disable.`
- **The reference plugin and the docs lean into the prompt as a *feature*, not a tax.** `docs/PLUGINS.md` opens with "Plugins declare what they want; you decide what they get. The first install of a plugin always shows you the requested capabilities." Users who read this know what to expect; users who don't read it see the prompt and learn.
- **Bundles (per Pitfall 5) reduce per-cap clicks.** A reference plugin that uses `basic_tool` bundle has one prompt: "Allow plugin foo to do the things a basic tool does: read its own plugin directory and make outbound HTTPS calls to declared hosts? [y/N]". Three caps under the hood; one clickable prompt on the surface.
- **No "remember this choice for this plugin family" mass-grant.** That would re-introduce default-allow through the back door. Per-(plugin, version, cap) grants only; no wildcards.

**Warning signs:**
- A `-y` / `--yes` flag on `plugins install` that is documented as "the default for personal use." Reverse it: the default IS interactive.
- The dashboard's plugin install flow has a "skip permission review" toggle. Should not exist.
- A user-facing doc page that uses the word "frictionless" to describe the permission flow. The permission flow is the friction; the rest of the install should be frictionless to compensate.

**Phase to address:**
**Phase 43 (permission model)** + **Phase 44 (installer)** + **Phase 45 (dashboard prompt)**. The default-deny posture is a one-line constant in `src/horus_os/plugins/permissions.py` (`DEFAULT_GRANT_POLICY = "deny"`). The complete UX is the rest of the milestone. Owner: PLUG-01 (default-deny), PLUG-07 (bundles), DIST-05 (interactive prompt with `-y` documented as CI-only).

---

### Pitfall 11: Plugin tests pollute the host venv or the entry-point cache

**What goes wrong:**
Plugin tests need to exercise: (a) the discovery path (pip-installed plugins via entry points), (b) the local-directory path (`~/.horus-os/plugins/`), (c) the installer end-to-end (pip install / uninstall / list), (d) failure modes (broken manifest, broken bind, broken stop). The straightforward test approach is to actually `pip install` a fixture plugin into the test venv. That has three failure modes:

1. **Test order dependence.** Test A installs `horus-os-test-fixture-plugin v1.0`; Test B installs v1.1. If they run in the wrong order or in parallel, one's assertions become the other's setup. Worse: the test runner's own venv is now permanently dirty for the rest of the CI job.
2. **`entry_points()` cache.** `importlib.metadata.entry_points()` is cached at the OS path level; a plugin installed mid-test is not visible until `importlib.metadata.distributions()` is re-invoked. Tests that don't refresh see stale state and pass spuriously.
3. **Three-OS hard gate amplification.** v0.5 must pass the 3-OS install matrix. A test that subprocess-installs into the test venv on Ubuntu may behave differently on macOS (different cache paths) and very differently on Windows (different path separators, different default user site-packages location). One platform's flake is another platform's hard failure.

**Why it happens:**
"Just use a real pip install in tests, it's more honest" is intuitive. It's also slow (5-30 seconds per install on a fresh wheel) and brittle for the reasons above. Mocking `pip install` entirely is the opposite extreme and misses the actual install path bugs (Pitfall 4) that need real coverage.

**How to avoid:**
- **Three-tier test fixture strategy:**
  1. **In-memory plugin records.** For testing the registry, lifecycle hooks, permission model, observability attribution. Use `PluginRecord(name="foo", version="1.0", entry_points={"tool": "fake.module:foo"}, capabilities=["filesystem.read"])` constructed directly in the test. No pip, no entry points. Covers >80% of plugin logic.
  2. **Monkeypatched entry-point discovery.** For testing the discovery path. `tests/conftest.py` exposes a `fake_plugin_entry_points` fixture that monkeypatches `horus_os.plugins.discovery.entry_points` (rebound at module level for exactly this reason, mirroring `src/horus_os/adapters/base.py:22` which already does this for first-party adapters). Tests inject a list of `EntryPoint` objects whose `load()` returns in-memory fakes. Covers the discovery code path without touching the venv.
  3. **Per-test temp venv for installer end-to-end.** For testing `horus-os plugins install` itself. `tests/conftest.py` exposes a `clean_venv` fixture: creates a venv in `tmp_path`, returns the python executable, tears it down after the test. The fixture is `@pytest.mark.installer_e2e` opt-in so the slow tests don't run by default; CI runs them once per OS in a dedicated job. Each test pip-installs a fixture wheel (`tests/fixtures/fake_plugin-1.0.whl`, checked into the repo, hand-built once) into the temp venv and asserts horus-os in that venv discovers it. Covers the actual install path on each OS.
- **Never `pip install` into the test runner's venv.** A CI lint rule: `grep -rE "pip.*install" tests/ --include="*.py" | grep -v "clean_venv\|sys\.executable" && exit 1`. The only allowed pattern is shelling into the per-test temp venv.
- **`importlib.metadata.distributions()` cache invalidation pattern.** The monkeypatched fixture in tier 2 already side-steps the cache. For tier 3, after a `pip install` in the temp venv, the test invokes horus-os IN that temp venv via subprocess (`[venv_python, "-m", "horus_os.cli", "plugins", "list"]`); the subprocess has its own fresh `importlib.metadata` state, so no cache invalidation is needed.
- **One test per pitfall in this document.** `tests/test_plugin_pitfalls/` directory mirrors this file: `test_pitfall_01_default_allow.py`, `test_pitfall_02_manifest_drift.py`, etc. Each test enforces the prevention pattern as a property of the system. When a future PR breaks Pitfall N's prevention, exactly one test turns red and the failure message points back to this document.

**Warning signs:**
- Test count balloons by 50+ but CI runtime balloons by 20+ minutes. Means too many tests fell into tier 3 instead of tiers 1-2.
- Tests pass locally on Ubuntu, fail in macOS CI. Almost always a path-separator or `tempfile.gettempdir()` difference in tier 3 fixture handling.
- A test calls `subprocess.run(["pip", "install", ...])` directly without going through the `clean_venv` fixture. Lint rule catches; review rejects.
- The `horus-os plugins list` CLI subcommand has no test that exercises it end-to-end. Means the installer e2e tier is empty and the install-flow bugs from Pitfall 4 are uncovered.

**Phase to address:**
**Phase 46 (test surface)** for the three-tier fixture strategy and the `tests/test_plugin_pitfalls/` directory; **Phase 49 (3-OS install verification)** for the installer-e2e tier running against the 3-OS matrix. Owner: TEST-16 (in-memory + monkeypatch fixtures), TEST-17 (clean_venv fixture + installer e2e), TEST-18 (pitfall regression tests).

---

### Pitfall 12: Documentation drift between manifest spec, reference plugin, and `docs/PLUGINS.md`

**What goes wrong:**
The plugin contract has at least three sources of truth: (a) the manifest schema in `src/horus_os/plugins/manifest.py`, (b) the reference plugin in `examples/horus-os-example-plugin/`, (c) the prose guide in `docs/PLUGINS.md`. The first time these drift is the first time a third-party author files a bug. The second time is when they file three. The third time is when they stop trying.

**Why it happens:**
The docs are written before the code lands and never updated. The example uses a field that the docs don't mention. The schema adds a field in PR #237 and the docs are "to be updated in a follow-up." Same shape as v0.4's `docs/OTEL.md` Threat-model section, which Phase 38 had to add explicitly to the success criteria to avoid landing OTel without it.

**How to avoid:**
- **Single source of truth for the manifest schema: a `MANIFEST_V1_SCHEMA` constant in `src/horus_os/plugins/manifest.py`** that is both the validator and the JSON-Schema export. The validator runs on every manifest load. The JSON-Schema export feeds `docs/PLUGINS.md` via a docs-build step that errors if the rendered schema in the docs differs from the runtime constant. (Mechanism: docs build runs `python -c "from horus_os.plugins.manifest import MANIFEST_V1_SCHEMA; import json; print(json.dumps(MANIFEST_V1_SCHEMA, indent=2))"`, diffs against `docs/manifest-v1.schema.json`, fails if drift.)
- **The reference plugin's manifest is parsed by the v0.5 loader as part of the test suite.** `tests/test_reference_plugin_manifest.py`: `assert load_manifest(EXAMPLE_PLUGIN_PATH / "horus-plugin.toml")` succeeds. If a future PR changes the schema in a way the reference plugin doesn't satisfy, the test turns red, the PR doesn't merge until the example is updated.
- **`docs/PLUGINS.md` includes the reference plugin's manifest verbatim via include.** Same `docs/<file>` includes the example's full manifest as a code block, generated at docs-build from the live file. Authors reading the doc see the actual current manifest; not a stale screenshot.
- **A "Threat Model" section in `docs/PLUGINS.md`** (mandated by Pitfall 1) with explicit copy: "Plugins execute in the horus-os Python process. Granted capabilities are de-facto access to your machine within those domains. The capability model reduces the attack surface but does not sandbox plugins."
- **Plugin authoring guide order: manifest → first tool → capability → adapter.** Mirroring the four scenarios in the reference plugin (Pitfall 8). The doc is a walkthrough of the example, not a separate independent treatise.
- **The release gate (Phase 49, REL-11) checks docs.** Concretely: `scripts/release_gate.py` (extending the v0.4 gate) adds a check that `docs/PLUGINS.md`, `docs/PLUGIN-SECURITY.md`, and `docs/MIGRATION-v0.4-to-v0.5.md` all exist; that the manifest schema in the docs matches the runtime constant; that the reference plugin's manifest validates against the current schema.

**Warning signs:**
- A code review PR that changes the manifest schema and does NOT touch the reference plugin or the docs. Pre-merge check fails.
- A third-party author asks "what does field X do?" where X is in the schema but not in the docs. The schema is the source of truth; the docs are the cache, and the cache is stale.
- The reference plugin's `horus-plugin.toml` uses a field that the docs don't list. Drift the other direction; same fix.
- `docs/PLUGINS.md` was last updated more than one minor version ago. Release gate flags.

**Phase to address:**
**Phase 47 (documentation refresh)** lands the docs trio (`PLUGINS.md`, `PLUGIN-SECURITY.md`, `MIGRATION-v0.4-to-v0.5.md`); **Phase 49 (3-OS gate)** wires the docs-freshness check into the release gate. Owner: REL-11 (docs trio), REL-12 (release-gate docs check). The "single source of truth for manifest schema" constant must exist by Phase 41 so the docs build can read from it.

---

## Technical Debt Patterns

Shortcuts that look reasonable but compound. v0.5-specific only; v0.4 patterns are out of scope here.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Default-allow at install time | Frictionless adoption, lower churn | Capability model becomes decorative; first malicious plugin compromises every user; tightening later is a breaking change | **Never.** Per Pitfall 10. |
| Grants keyed on plugin_name only (not version) | Upgrades feel seamless | Silent permission expansion on `pip upgrade`; the LiteLLM TeamPCP attack shape | **Never.** Per Pitfall 5. |
| `pkg_resources` for entry-point discovery | "Tutorial used it" / first thing that searches | 1.3s import cost on every CLI startup; deprecated API; `EntryPoint` shape will keep shifting | **Never.** Per Pitfall 3. Use `importlib.metadata`. |
| `pip install` plugin code BEFORE manifest validation | Simplest installer | `setup.py` arbitrary code execution before the capability prompt — defeats the model | **Never.** Per Pitfall 4. Two-phase install or wheel-only. |
| Allowing sdist installs by default | Plugin authors don't need to wheel-build | Same `setup.py` problem; also blocks the Phase B "parse METADATA before install" check | **Never** by default. `--allow-sdist` flag for plugin authors developing their own. |
| Lifecycle hooks with no timeout | Looks like the v0.4 adapter shape (it is); simpler code | A buggy third-party plugin's `start()` hangs the entire FastAPI lifespan → server unreachable | **Never** for plugins. `asyncio.wait_for(timeout=2.0)` always. v0.4 first-party adapters can be exempted because we own the code. |
| `manifest_version` as optional field, defaulting to 1 | One less field for authors to remember | Cannot tell v1 from v2 manifests; cannot evolve the schema safely | **Never.** Required from day one. |
| Plugin observability inheriting v0.4 schema without plugin_name | "v0.4 just shipped, don't churn it" | Dashboard rollups attribute plugin failures to no one; users can't diagnose which plugin to disable | **Never.** v5→v6 must add the column. |
| Reference plugin importing from `horus_os._private` | Maintainer reaches for the helper that exists | Every plugin author copies the pattern; we can't refactor internals without breaking the ecosystem | **Never.** Plugin-facing API is `horus_os.plugins.api` and nothing else. |
| `pip install` in CI test runner's own venv | "More honest than mocking" | Test order dependence; entry-point cache pollution; CI runtime balloon; cross-OS flakes | **Never.** Use the three-tier fixture strategy from Pitfall 11. |
| Skipping the permission prompt on `horus-os plugins install -y` (default-on `-y`) | Faster install for known-good plugins | Re-introduces default-allow through the back door; users learn to type `-y` reflexively | Only when `-y` is OFF by default and documented as "CI use only." |
| Dropping or renaming a SQLite table/column on v5→v6 | Schema hygiene | Every v0.4 user's database breaks on upgrade; data loss | **Never.** Additive only. Same rule as v0.4 Phase 32. |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| `importlib.metadata.entry_points()` | `entry_points()['horus_os.plugins']` — dict shim works on 3.10/3.11, raises on 3.12 | `entry_points(group='horus_os.plugins')` — selectable API; works on every supported version |
| `subprocess.run(["pip", "install", ...])` | Bare `pip` resolves to whatever's first on PATH; may not be the venv's pip | `[sys.executable, "-m", "pip", "install", "--require-virtualenv", ...]` |
| Plugin's `setup.py` | Runs at install time as arbitrary Python code | Refuse sdist by default (`--allow-sdist` flag for plugin developers); wheels only for end-user installs |
| Plugin's `.pth` file in the wheel | Executes on every Python startup (Checkmarx `.pth` attack shape) | Refuse wheels containing `*.pth` in RECORD during Phase B validation |
| `entry_points()` cache during tests | Caches by interpreter; tests that install mid-run see stale state | Per-test temp venv (tier 3 fixture from Pitfall 11) or monkeypatch (`fake_plugin_entry_points` fixture, tier 2) |
| FastAPI lifespan unbounded `await plugin.start()` | A hung plugin blocks the entire server startup | `asyncio.wait_for(plugin.start(ctx), timeout=2.0)` — same shape as v0.4 OTel adapter shutdown |
| Plugin tool registration | Two plugins both want tool name `read_file`; second one raw-raises `ValueError` from ToolRegistry | Loader catches and wraps with `PluginConflictError` carrying both plugin names; user disables one in the dashboard |
| Permission shim's `check_capability` | TOCTOU pattern: check, return True, caller-then-uses-the-cap | Helper shim MUST raise if the cap is missing; never return True without performing the privileged op |
| Anthropic / Gemini SDK calls from a plugin | Plugin imports `from horus_os._providers.anthropic import client` directly | Plugin requests `llm.call` capability and goes through `ctx.llm.call_anthropic(...)` which respects rate limits and observability |
| `plugin_capability_grants` lookup | `WHERE plugin_name = ?` only — inherits across versions | `WHERE plugin_name = ? AND plugin_version = ?` — pinned per version |

## Performance Traps

Patterns that look fine for one plugin and fall over as the plugin count grows. Hand-sized for a single-user desktop product; not Datasette-scale.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Eager entry-point scan at module import | `horus-os --version` takes >1s cold | Lazy discovery: `discover_plugins()` called once during FastAPI lifespan, cached on `app.state.plugins`; CLI subcommands that don't need plugins never trigger it | Past ~10 installed plugins; or any installed plugin that re-exports a heavy ML library at import time |
| `pkg_resources` import in any code path | `horus-os --version` takes 1.3-1.5s cold | Lint rule: `grep -r "import pkg_resources" src/ && exit 1` | Always; the cost is in the import itself, not the call |
| Synchronous IO in plugin `start()` | Server startup takes longer per plugin installed; a network blip on one plugin's connect hangs all of them | `asyncio.wait_for(plugin.start(ctx), timeout=2.0)`; plugins that need to wait on a network do it in a background task scheduled from `start()` | At 3+ network-using plugins (Discord adapter style) installed |
| Per-event subscriber inside `ObservationBus` doing SQL writes synchronously | Capture-overhead benchmark from v0.4 Phase 33 regresses past +50ms baseline | SQLitePersister batches writes (already the v0.4 shape); plugin observability lives ON the same bus and inherits the batching | Past ~100 events/second sustained — unlikely for a single user but plausible during a multi-agent fan-out |
| Plugin's tool handler doing blocking IO inside the agent loop | Streaming responses stall; user sees the SSE pause | Tool handlers are sync but should not block longer than a single agent turn budget (~10s); plugins doing long IO must use an async tool handler or a background task | Past one plugin doing >2s blocking IO per tool call |
| Manifest loaded from disk on every tool invocation | CPU spike on hot loops; first symptom is laptop fan during agent runs | Manifest loaded once at discovery, cached on `PluginRecord`; only re-loaded on `plugins refresh` or restart | Past ~10 tool invocations per second |
| Capability check doing SQL lookup on every shim call | Same pattern; SQLite is fast but not free | `PermissionCache` in-memory dict per-process, populated at startup from `plugin_capability_grants`; invalidated on grant change | Past ~100 capability checks per second; not realistic for v0.5 but cheap to do right |
| Three-OS install matrix has flaky teardown | CI minutes balloon; tests pass-then-fail on retry | `clean_venv` fixture uses `pytest`'s `tmp_path` (auto-cleaned) and never leaves writes outside it; never tampers with the runner's venv | Always; CI flakes compound |

## Security Mistakes

Plugin-system-specific. The v0.4 OTel/PII pitfalls in the prior PITFALLS.md are not duplicated here.

| Mistake | Risk | Prevention |
|---------|------|------------|
| In-process plugin code with read access to `~/.horus-os/secrets.json` | Plugin reads Anthropic API key, exfiltrates via the `net.outbound` capability | `secrets.read` is a separate capability from `filesystem.read`; the secrets file is read via a `ctx.secrets.get(provider="anthropic")` shim that checks the capability AND scrubs the returned key with a `RevealedSecret` wrapper that only stringifies for the inner SDK call site |
| Plugin sets env vars in the parent process | Plugin's `os.environ['ANTHROPIC_API_KEY'] = '...'` overrides horus-os's own key for the rest of the process | Capability `env.write` is its own narrow capability; default-deny; the helper shim makes a private env-overlay scoped to the plugin's own subprocesses, never mutates `os.environ` |
| Plugin reads from `os.environ` directly | Bypasses the secrets capability; reads `ANTHROPIC_API_KEY` straight from the process env | Documented anti-pattern in `docs/PLUGIN-SECURITY.md`; we cannot strictly enforce this in v0.5 (no OS sandbox), but the docs warn and the linter for the reference plugin rejects `os.environ` access outside of declared env vars |
| Plugin imports `from horus_os._providers.anthropic import client` and uses it raw | Bypasses observability, rate limits, capability checks for LLM use | `horus_os._providers` is a leading-underscore (private) module; the public API `horus_os.plugins.api.LLM` re-exports a wrapped client that respects the `llm.call` capability and ObservationBus; lint rejects `_providers` imports in any plugin |
| Plugin's manifest declares a capability the plugin never uses | The user grants more than the plugin needs; on supply-chain compromise the unused grants become the attacker's playground | Dashboard plugins tab shows "requested but never used in 30d" badge; periodic re-prompt offers to revoke unused caps; the Wiz LiteLLM writeup specifically called out over-broad pre-grants as the foothold |
| Plugin loads code from a URL at runtime | Pre-install review is moot; the plugin pulls live code | `net.outbound` capability is required even for the plugin to make any HTTP call; in v0.5 we don't strictly enforce "no code-loading endpoints" — we DO require the plugin to declare which hosts it talks to in its manifest, and the helper HTTP shim refuses requests to undeclared hosts |
| Plugin spawns subprocess (e.g. shells out to `git`) | Bypasses every check; subprocess inherits all of horus-os's privileges | `process.spawn` is a separate capability; default-deny; the helper shim is the only path that respects it; raw `subprocess.run(...)` from plugin code is a documented anti-pattern (we cannot strictly enforce without OS sandbox in v0.5) |
| Manifest signed-by field is unverified | Anyone can claim to be plugin author "foo"; users trust the wrong identity | v0.5 deliberately ships WITHOUT signature verification (out of scope for the milestone); manifest carries an `author` and `homepage` field that the installer surfaces verbatim with a "verify on PyPI" link; signature verification is v0.6+ (documented in `docs/PLUGIN-SECURITY.md` as a known gap) |
| `pip install` from a path outside PyPI (`pip install ./local-foo`) skips PyPI's malware scanning | Local-dev path is also the local-malware path | Local-directory install (`~/.horus-os/plugins/` per PROJECT.md) is allowed for "dev plugins"; documented warning that local plugins are unscanned; same capability prompt applies; future v0.6+ could add a "dev mode" flag that's off by default |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Permission prompt shows raw capability dotted-keys (`filesystem.read`) | User has no idea what filesystem.read actually permits; click-throughs the prompt | Plain-English per-cap descriptions from `capability_catalog.py`; the prompt shows the description, the dotted-key is in tooltip / `--verbose` mode |
| Re-prompt on every plugin upgrade even when capability set is unchanged | Grant fatigue; user reflexively types `y` | Three-outcome diff (Pitfall 5): silent auto-grant when unchanged or reduced, re-prompt only on expansion |
| Plugin error rolls up under "registry error" with no plugin name | User can't diagnose which plugin broke; suspects horus-os itself | Per-plugin attribution column (`plugin_name`) on every observability event; per-plugin rollup tile on dashboard |
| `horus-os plugins list` shows enabled status but not grant status | User installs a plugin, doesn't realize they declined a capability, plugin "doesn't work" | `plugins list` shows `(2/3 capabilities granted)`; `plugins info <name>` shows the full grant table |
| Manifest error during install dumps a JSON-Schema validation error | User sees `"properties.capabilities.0: not in enum"` and has no clear next step | Manifest validation errors are formatted by `src/horus_os/plugins/manifest.py:format_validation_error()` into "Field 'capabilities[0]' has value 'fs.read'. Valid values are: filesystem.read, filesystem.write, net.outbound, ..." with a doc link |
| `pip install` fails for a non-plugin reason (network, wheel build) and the user thinks it's a plugin bug | They give up on horus-os | Installer's error handler classifies failures: NetworkError → "Check connection and retry"; WheelBuildError → "This plugin doesn't ship a wheel for your platform; contact the plugin author"; ManifestError → "This plugin is incompatible with horus-os v0.5" |
| The dashboard plugins tab takes >1s to load because it shells out to `pip list` | First-impression of "the plugin system is slow" | Plugin list is cached on `app.state.plugins` from lifespan discovery; refreshed only on explicit refresh button or `horus-os plugins refresh`; not on every page load |
| "Plugin disabled" hides the plugin from `plugins list` | User forgets they disabled it; can't find it to re-enable | Disabled plugins appear in `plugins list` with `(disabled)` tag and an `enable` action; never hidden |
| No way to test a plugin without publishing it | Plugin authors can't iterate locally | `~/.horus-os/plugins/<name>/` local-directory discovery (per PROJECT.md); plus `horus-os plugins install --editable .` runs `pip install -e .` for local development |

## "Looks Done But Isn't" Checklist

Plugin-system completeness verification. Use during execution.

- [ ] **Capability declaration:** Every declared cap is in `capability_catalog.py`; unknown caps are rejected at manifest load (Pitfall 1).
- [ ] **Capability enforcement:** Every helper shim (`ctx.filesystem`, `ctx.secrets`, `ctx.net`, `ctx.process`, `ctx.env`) raises `PermissionDenied` if the cap is missing — verify by removing a grant and asserting the test plugin fails (Pitfall 1).
- [ ] **Manifest schema:** `manifest_version` is required; unknown fields warn but do not refuse; v1 fixture continues to load (Pitfall 2).
- [ ] **Discovery API:** Only `importlib.metadata.entry_points(group=...)` is used; `pkg_resources` is lint-rejected; 3.11 and 3.12 both green in CI (Pitfall 3).
- [ ] **Discovery is lazy:** `horus-os --version` cold start <100ms; CLI subcommands that don't need plugins do not call `discover_plugins()` (Pitfall 3).
- [ ] **Installer venv check:** `sys.prefix == sys.base_prefix` rejection works; tested with system Python in CI (Pitfall 4).
- [ ] **Two-phase install:** Manifest validation happens BEFORE `pip install`; sdist rejected by default; `.pth`-containing wheels rejected (Pitfall 4).
- [ ] **Rollback:** A failed install leaves the venv state byte-identical to pre-install (`pip freeze` hash round-trip) (Pitfall 4).
- [ ] **Grant per-version keying:** `plugin_capability_grants` schema has `(plugin_name, plugin_version, capability)` as PK; upgrade does not inherit (Pitfall 5).
- [ ] **Grant diff UX:** Three outcomes (unchanged/reduced/expanded) wired in CLI prompt and dashboard modal (Pitfall 5).
- [ ] **Bounded lifecycle:** Every `plugin.start()` and `plugin.stop()` call wrapped in `asyncio.wait_for(timeout=2.0)`; broken-plugin fixture test asserts the lifespan completes (Pitfall 6).
- [ ] **Failure isolation:** Broken plugin marks `status=error` and other plugins continue; horus-os server stays up (Pitfall 6).
- [ ] **Plugin can be disabled without uninstalling:** `plugin_registry.enabled = 0` skips discovery for that plugin (Pitfall 6).
- [ ] **Observability attribution:** Every `ToolCallEvent` and `LLMCallEvent` from a plugin carries `plugin_name`; pre-v0.5 rows are NULL and roll up under "horus-os core" (Pitfall 7).
- [ ] **`/api/observability/plugins`:** Returns per-plugin rollups; dashboard plugins tab shows error rate (Pitfall 7).
- [ ] **Reference plugin:** Imports only from `horus_os.plugins.api`; covers four scenarios; installs via the actual installer flow; tests run in CI (Pitfall 8).
- [ ] **v5→v6 migration is additive only:** No DROP, no RENAME, no NOT NULL on existing columns; v0.4 fixture survives the migration (Pitfall 9).
- [ ] **Default-deny posture:** `DEFAULT_GRANT_POLICY = "deny"` in code; `-y` flag is documented as CI-only; no skip-permissions toggle in the dashboard (Pitfall 10).
- [ ] **Three-tier test fixtures:** In-memory PluginRecord, monkeypatched entry-points, per-test `clean_venv`; no `pip install` ever touches the runner's venv (Pitfall 11).
- [ ] **Docs / schema / example parity:** `docs/PLUGINS.md` includes the live example manifest verbatim; release-gate test asserts no drift between code and docs (Pitfall 12).
- [ ] **Threat model is written down:** `docs/PLUGIN-SECURITY.md` exists; first-paragraph statement: "Plugins execute in the horus-os Python process" — linked from the installer prompt (Pitfall 1).

## Recovery Strategies

When pitfalls occur despite prevention.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Default-allow shipped accidentally | HIGH | Emergency v0.5.1 that flips to default-deny; reset all grants in users' databases; force re-prompt on next install; mailing-list announcement with explanation. Painful but survivable; the alternative is shipping a permanent CVE class. |
| Manifest schema drift (v1 manifests break under v2 loader) | HIGH | Ship a v0.5.x patch that loads v1 manifests via the v2 loader's normalize() function; add the missing forward-compat test fixture; document the regression in CHANGELOG |
| `pkg_resources` snuck into the import path | MEDIUM | Identify the import chain via `python -X importtime -c "import horus_os"`; replace with `importlib.metadata`; add the lint rule that should have caught it |
| Plugin corrupted the venv | MEDIUM | Document the manual fix in `docs/PLUGIN-RECOVERY.md`: `rm -rf venv && python -m venv venv && pip install horus-os && horus-os plugins reinstall-all`; harden the rollback test |
| Capability silent expansion bug shipped | HIGH | Audit `plugin_capability_grants` for any row where `plugin_version` is the latest but `granted_at` predates the version's release date — those are the silently inherited grants; revoke them, force re-prompt; release announcement |
| Plugin hung the server | LOW | User runs `horus-os --disable-all-plugins` (CLI flag that loads with empty plugin list); identifies the offending plugin via `plugin_registry.status`; disables it; restarts; opens an issue. The bounded-lifecycle fix lands in a patch release. |
| v0.4 database broke on v0.5 upgrade | HIGH | Patch release that rolls the migration forward in a safer order; provide `horus-os migrate --from v0.4` rescue script; back up the database before running |
| Reference plugin used internal API | LOW | Refactor the example, ship a patch, mark the offending internal symbol as `__deprecated__` for one minor version, then move it out from underscore-prefix |
| Plugin observability has no attribution | MEDIUM | Backfill `plugin_name` on existing rows where the trace_id can be cross-referenced with the active plugin at the time; ship the column-required-non-NULL gate in a patch |
| Default-deny created adoption friction | LOW | Improve copy in the prompt; add bundles for common patterns; do NOT relax the default. Adoption-friction is a UX problem; default-allow is a security problem. |
| Test isolation broke (pip in test runner venv) | MEDIUM | Reset CI runner image; refactor to three-tier fixtures; add the lint rule |
| Docs drift caught after release | LOW | Patch release with docs only; release-gate check enforces no future drift |

## Pitfall-to-Phase Mapping

Maps each pitfall to the v0.5 phase that owns its prevention. Phase numbers continue from v0.4's Phase 39, so v0.5 phases start at 40.

| Pitfall | Prevention Phase(s) | Verification |
|---------|---------------------|--------------|
| 1: Default-allow normalizes compromise | 41 (manifest), 43 (permission model), 47 (docs) | Test removing a grant and asserting helper shim raises `PermissionDenied`; `docs/PLUGIN-SECURITY.md` exists; capability catalog is closed |
| 2: Manifest schema drift | 41 (manifest) | v1 fixture loads unmodified through every future loader version; `manifest_version` is required; unknown fields warn |
| 3: Entry-point API drift + `pkg_resources` cost | 42 (discovery) | Lint rejects `pkg_resources`; 3.11 + 3.12 both green; cold-start <100ms benchmark |
| 4: Installer corrupts venv | 44 (installer) | `clean_venv` fixture tests round-trip pip-freeze hash; sdist rejected; `.pth` rejected; venv check enforced |
| 5: Grant expansion on upgrade | 43 (permission model), 44 (installer upgrade) | Per-(name,version,cap) PK; diff-based re-prompt test; audit log appended |
| 6: Plugin failures crash horus-os | 42 (discovery), 43 (lifecycle), 46 (tests) | Broken-plugin fixture causes `status=error`; lifespan completes; bounded `wait_for(2.0)` |
| 7: Observability attribution gap | 41 (schema migration), 45 (dashboard + new route) | Every plugin event has non-NULL `plugin_name`; per-plugin rollup query returns correct counts |
| 8: Reference plugin trap | 41 (define `plugins/api.py`), 48 (reference plugin) | Reference plugin imports only from `horus_os.plugins.api`; tested in CI; covers four scenarios |
| 9: v5→v6 breaks v0.4 databases | 41 (schema migration) | v0.4 fixture round-trip test; no DROP/RENAME/NOT-NULL in migration; idempotent re-run |
| 10: Default-deny friction tradeoff | 43 (permission model), 44 (installer), 45 (dashboard) | `DEFAULT_GRANT_POLICY = "deny"` constant; `-y` flag is opt-in; bundles surface; reference plugin uses a bundle |
| 11: Test isolation pollution | 46 (test surface), 49 (3-OS gate) | Three-tier fixture strategy; lint rejects `pip install` in runner venv; cross-OS tests use `clean_venv` only |
| 12: Documentation drift | 41 (single source of truth in `MANIFEST_V1_SCHEMA`), 47 (docs), 49 (release-gate docs check) | Docs include live example verbatim; release gate diffs schema-in-docs vs runtime constant |

**Suggested v0.5 phase outline (for the roadmapper to refine):**

- **Phase 40** — v0.4 retrospective + v0.5 baseline artifact (mirror Phase 32's structure): commit `tests/perf/v0_4_baseline.json` so a future plugin-discovery-overhead benchmark has a pinned reference.
- **Phase 41** — Manifest schema, `MANIFEST_V1_SCHEMA` constant, `plugins/api.py` public API surface, v5→v6 migration, plugin_name column additions, `capability_catalog.py`. Pure infrastructure. Pitfalls 2, 7, 8, 9, 12.
- **Phase 42** — Discovery and loading: `entry_points`-based + local-directory; failure-isolation wrappers (discover, manifest-load); lint rule for `pkg_resources`. Pitfalls 3, 6.
- **Phase 43** — Permission model: `plugin_capability_grants`, helper shims, `check_capability`, `DEFAULT_GRANT_POLICY = "deny"`, bounded lifecycle (start/stop with `wait_for(2.0)`). Pitfalls 1, 5, 6, 10.
- **Phase 44** — Installer flow: `horus-os plugins install/uninstall/list/info`, two-phase install, venv check, sdist refusal, `.pth` refusal, rollback, upgrade-with-diff prompt. Pitfalls 4, 5, 10.
- **Phase 45** — Dashboard plugins tab: list, enable/disable, grant prompt modal, audit log surface, per-plugin observability rollup; `/api/observability/plugins` route. Pitfalls 5, 7, 10.
- **Phase 46** — Test surface expansion: three-tier fixtures (in-memory PluginRecord, monkeypatched entry points, `clean_venv`), broken-plugin fixture, `tests/test_plugin_pitfalls/` directory. Pitfall 11.
- **Phase 47** — Documentation refresh: `docs/PLUGINS.md`, `docs/PLUGIN-SECURITY.md` (with explicit Threat Model section), `docs/MIGRATION-v0.4-to-v0.5.md`. Pitfalls 1, 12.
- **Phase 48** — Reference plugin (`horus-os-example-plugin` as a separate package): four scenarios, dogfooded tests, README is the authoring guide. Pitfall 8.
- **Phase 49** — Three-OS install verification (v0.5) + release gate (`scripts/release_gate.py` extension): docs-drift check, plugin install-smoke on each OS for 3.11 and 3.12. Pitfalls 4, 11, 12.
- **Phase 50** — v0.5.0 release: tag, CHANGELOG, GitHub Release with migration notes.

Execution order is mostly sequential because each phase consumes the prior phase's substrate. Legitimate parallel opportunity: Phase 44 (installer) and Phase 45 (dashboard) can run in parallel once Phase 43 (permission model) ships, since both consume the same grant-table schema without depending on each other — mirrors the v0.4 (36 ∥ 37) opportunity.

## Sources

**`importlib.metadata` API evolution:**
- [importlib.metadata 3.10 docs](https://docs.python.org/3.10/library/importlib.metadata.html) — selectable entry points introduced; dict shim with deprecation warning
- [importlib.metadata 3.12 docs](https://docs.python.org/3.12/library/importlib.metadata.html) — dict interface removed; only EntryPoints returned
- [importlib.metadata 3.13 docs](https://docs.python.org/3.13/library/importlib.metadata.html) — `EntryPoint` no longer presents tuple-like interface

**Entry-point discovery cost:**
- [pypa/setuptools#510](https://github.com/pypa/setuptools/issues/510) — `pkg_resources` import is 1.3-1.5s
- [catkin/catkin_tools#297](https://github.com/catkin/catkin_tools/issues/297) — `pkg_resources.entry_points` >200ms latency
- [unslothai/unsloth#1859](https://github.com/unslothai/unsloth/issues/1859) — 60s import via entry points
- [Python Packaging spec: Entry points](https://packaging.python.org/specifications/entry-points/) — namespacing best practice

**Plugin-system precedents:**
- [Datasette plugins](https://docs.datasette.io/en/stable/plugins.html) and [Datasette plugin system deep dive](https://deepwiki.com/simonw/datasette/5-plugin-system) — `datasette install` as a thin wrapper around `pip install` in the same venv; pluggy hook-based architecture
- [Pelican plugins (4.5+ namespace packages)](https://docs.getpelican.com/en/latest/plugins.html) — namespace-package migration lessons
- [pluggy framework](https://pluggy.readthedocs.io/en/latest/) — hook signature conflicts, plugin manager design
- [validate-pyproject conflict resolution](https://validate-pyproject.readthedocs.io/en/latest/dev-guide.html) — priority-based duplicate-entry-point resolution

**Supply-chain attack surface (in-process plugin code):**
- [Wiz LiteLLM TeamPCP writeup](https://www.wiz.io/blog/threes-a-crowd-teampcp-trojanizes-litellm-in-continuation-of-campaign) — PyPI 1.82.7/1.82.8 trojanized
- [Truesec LiteLLM compromise](https://www.truesec.com/hub/blog/malicious-pypi-package-litellm-supply-chain-compromise) — same incident, defender angle
- [Checkmarx Command-Jacking](https://checkmarx.com/blog/this-new-supply-chain-attack-technique-can-trojanize-all-your-cli-commands/) — entry-point hijacks, `.pth`-file arbitrary execution
- [Bolster PyPI security](https://bolster.ai/blog/pypi-supply-chain-attacks) — 2025 PyPI attack-vector landscape
- [Designing Secure Plugin Architectures](https://dev.to/cyberpath/designing-secure-plugin-architectures-for-desktop-applications-1meh) — capability-based vs identity-based access control

**Schema evolution discipline:**
- [Confluent schema evolution](https://docs.confluent.io/platform/current/schema-registry/fundamentals/schema-evolution.html) — Forward/Backward/Full compatibility classes
- [Conduktor schema evolution best practices](https://www.conduktor.io/glossary/schema-evolution-best-practices)
- [Zuplo API backwards-compatibility](https://zuplo.com/learning-center/api-versioning-backward-compatibility-best-practices)

**FastAPI lifespan and bounded timeouts:**
- [FastAPI Lifespan events](https://fastapi.tiangolo.com/advanced/events/)
- [FastAPI lifespan startup timeout discussion](https://github.com/fastapi/fastapi/discussions/13346)
- v0.4 internal precedent: `tests/test_otel_bounded_shutdown.py` and Phase 38 success criterion 3 — `await adapter.stop()` completes in <3s with `BatchSpanProcessor.force_flush(2000)` then `shutdown()`

**Internal cross-references:**
- `/Users/santino/Projects/horus-os/src/horus_os/adapters/base.py:22` — `entry_points` rebinding pattern (monkeypatch-friendly)
- `/Users/santino/Projects/horus-os/src/horus_os/adapters/base.py:233` — broad `Exception` catch in `discover_adapters`
- `/Users/santino/Projects/horus-os/src/horus_os/server/api.py:99-116` — lifespan `start`/`stop` wrapping without `wait_for` (the v0.5 must-fix)
- `/Users/santino/Projects/horus-os/src/horus_os/storage.py:28` — `SCHEMA_VERSION = 5` baseline for v5→v6 additive migration
- `/Users/santino/Projects/horus-os/src/horus_os/tools/registry.py:23` — duplicate-tool-name `ValueError` already in place
- `/Users/santino/Projects/horus-os/.planning/research/PITFALLS.md` (v0.4 prior art, committed 2026-05-25) — pitfall format precedent; v0.4 ObservationBus / OTel pitfalls inherited as substrate for Pitfalls 6, 7, 9

---
*Pitfalls research for: v0.5 third-party plugin system*
*Researched: 2026-05-26*
