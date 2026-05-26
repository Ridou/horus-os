# Feature Research

**Domain:** Plugin system for a self-hosted Python AI command center (horus-os v0.5)
**Researched:** 2026-05-26
**Confidence:** HIGH (cross-verified across 6 named plugin systems; v0.5 already locked PROJECT.md decisions on entry-points + local dir + TOML manifest + default-deny capabilities + in-process loading)

## Scope

horus-os v0.1-v0.4 already shipped: Tool registry, Adapter Protocol with lifecycle hooks (start/stop/error states), AdapterRegistry, ObservationBus + per-event SQLite persistence, `/observability` dashboard tab with cost/latency/reliability panels, `horus-os usage` CLI, opt-in OTel exporter behind `[otel]` extra. v0.5 adds **third-party packaging on top of those primitives** — manifest, installer, discovery, capability declarations, and dashboard surface for plugins. It does NOT introduce a new hook framework, a new persistence layer, or OS-level sandboxing.

PROJECT.md has already locked:
- TOML manifest format (`horus-plugin.toml`)
- Discovery via Python entry-points (group `horus_os.plugins`) + `~/.horus-os/plugins/` directory drop-in
- Default-deny capability grants persisted in SQLite, revocable from dashboard
- `horus-os plugins install|uninstall|list|info` CLI wrapping `pip`
- One reference plugin (`horus-os-example-plugin`)
- No HTTP catalog, no OS-level isolation in v0.5

This research feeds the **REQUIREMENTS.md categories** (MANIFEST, DISCOVERY, INSTALL, PERMISSION, ISOLATE, DASH, REFERENCE, plus continuation TEST/REL/MIG). Each finding is tagged **table-stakes**, **differentiator**, or **anti-feature**.

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist in any modern Python plugin system. Missing these = product feels half-finished. Each row is backed by 2+ named examples.

| Feature | Why Expected | Complexity | Examples / Sources |
|---------|--------------|------------|--------------------|
| **MANIFEST-01: Declared name + version + horus-os-compatibility range** | Every plugin system declares these. They are the minimum a user needs to answer "what is this and will it work?" before granting trust. | LOW | Home Assistant `manifest.json` (domain, name, version, requirements); VS Code `package.json` (name, version, engines.vscode); pyproject.toml (name, version, requires-python) |
| **MANIFEST-02: Declared entry points (which tools and adapters this plugin contributes)** | Users and the dashboard must know what the plugin contributes before loading it, not after. "Contribution points" are the canonical pattern. | LOW | VS Code `contributes` section (commands, views, languages, etc.); Home Assistant `integration_type` + dependencies; Datasette plugin hooks listed in `/-/plugins` |
| **MANIFEST-03: Declared capabilities/permissions requested** | Users grant trust on declared scope. A plugin that silently grabs file/network access is the canonical anti-pattern. | MEDIUM | Home Assistant manifest permission policy (entity/domain grants, "True or None=deny" default); VS Code `capabilities.untrustedWorkspaces.supported` + restrictedConfigurations; Datasette's `actor_from_request` + permission hooks |
| **MANIFEST-04: Declared author / homepage / issue tracker** | Required to triage bugs and verify provenance. Users won't install plugins without an "I know where to report this" path. | LOW | Home Assistant `codeowners` + `issue_tracker` + `documentation` (required for core); VS Code `publisher` + `repository` + `bugs.url` |
| **DISCOVERY-01: Python entry-points group as primary discovery** | The canonical Python plugin discovery mechanism. Works for `pip install`-ed plugins out of the box. Two named ecosystems use it identically. | LOW | pytest `pytest11` group; Datasette `datasette` group; Sphinx setup() via `extensions = []` in conf.py (different mechanism but same intent); JupyterLab via labextension entry points |
| **DISCOVERY-02: Local directory drop-in for unpublished/dev plugins** | Without this, plugin development requires `pip install -e` round-trips. Every mature ecosystem has both paths. | LOW | Datasette `--plugins-dir=plugins/`; pytest `conftest.py` auto-discovery; Sphinx local extensions via `sys.path.append`; Home Assistant `custom_components/` |
| **INSTALL-01: `install <pip-spec>` wraps pip into active venv** | "Open a shell and run pip" is unacceptable UX for a self-hosted product. Every successful plugin system ships its own wrapper. | LOW | Datasette `datasette install <name>` (explicitly documented as "thin wrapper around pip install"); JupyterLab `pip install` + `jupyter labextension enable`; HACS download-to-custom_components |
| **INSTALL-02: `uninstall <name>`** | Symmetrical with install. Users expect to remove what they install via the same surface. | LOW | Datasette `datasette uninstall`; pip uninstall; HACS Remove action |
| **INSTALL-03: `list` shows installed plugins with version + status** | "What's installed?" is the first question a user has after install. | LOW | Datasette `datasette plugins`; `pip list`; JupyterLab `jupyter labextension list`; Home Assistant Integrations page |
| **INSTALL-04: `info <name>` shows manifest contents + granted capabilities** | "What does this plugin do and what can it touch?" before users grant trust. | LOW | `pip show`; VS Code Extensions detail pane; Home Assistant integration detail page |
| **INSTALL-05: First-run capability prompt — display requested capabilities, require explicit user confirmation** | Default-deny posture requires an explicit grant. Plugins that activate without consent are the canonical security anti-pattern. | MEDIUM | VS Code 1.97+ "trust the publisher" dialog on first install; Home Assistant config_flow consent step; mobile app permission prompts (the obvious analog) |
| **PERMISSION-01: Default-deny posture — declared capability is not the same as granted capability** | Industry consensus across security and plugin systems. "Default-allow" plugin systems get owned. | LOW | Home Assistant policy: `True=grant, None=use default=deny`; sandbox firewall guidance ("treat it like a firewall: default-deny, then explicitly allow"); VS Code Restricted Mode default-disables extensions in untrusted workspaces |
| **PERMISSION-02: Grants persisted with the plugin name + version on which they were granted; re-prompt when a plugin upgrade widens the requested set** | Users will accept a narrow set then never see the upgrade that widens it, otherwise. Already locked in PROJECT.md as a design constraint. | MEDIUM | Mobile OS permission models (iOS/Android re-prompt on scope expansion); VS Code workspace trust re-prompts when extension publisher changes |
| **PERMISSION-03: Grants are revocable from the dashboard at any time** | Symmetrical with grant. If a user can grant from the UI, they must be able to revoke from the UI. | LOW | VS Code Manage Trusted Domains; Home Assistant per-entity permissions; iOS/Android settings |
| **ISOLATE-01: A broken plugin (import error, manifest validation failure, exception in start hook) MUST NOT crash horus-os** | The single most common reason users abandon a plugin host. Home Assistant recovery mode and pytest's plugin error handling both exist because this happens. | MEDIUM | Home Assistant: `ConfigEntryNotReady` triggers retry, never crashes core; Recovery Mode boots minimal set if a user-configured integration takes down startup; pytest plugin load errors are caught and reported; pluggy `_multicall` wraps hook impls in try/except |
| **ISOLATE-02: Plugin load failures degrade to a visible "plugin error" status, not silent removal** | "Why isn't my plugin working?" with no surface in the dashboard is the worst possible UX. | LOW | Home Assistant integration page "Failed setup, will retry" + error log link; VS Code Extensions view error indicator; JupyterLab disable-on-error pattern |
| **ISOLATE-03: Plugin enable/disable toggle without uninstall** | Users need to A/B isolate which plugin is causing trouble. Uninstall is too coarse. | LOW | JupyterLab `jupyter labextension disable/enable`; Home Assistant Integrations disable toggle; VS Code Enable/Disable per-extension; Datasette `--plugins-dir` filtering |
| **DASH-01: Plugins tab listing installed plugins with name, version, declared tools/adapters, granted capabilities, lifecycle status, last error** | Already locked in PROJECT.md. Minimum dashboard surface to make a user trust the plugin set. | MEDIUM | Home Assistant Integrations page (status, last activity, error count); VS Code Extensions view; Datasette `/-/plugins` JSON endpoint |
| **DASH-02: Per-plugin enable/disable toggle on the plugins tab** | Symmetrical with the CLI toggle. v0.3 already shipped this pattern for adapters at `/adapters`. | LOW | Existing horus-os v0.3 `/adapters` page (precedent); Home Assistant; JupyterLab Plugin Manager |
| **REFERENCE-01: One published reference plugin in the same repo, demonstrating the full happy path** | Without a working example, third-party authors abandon plugin development. Already locked in PROJECT.md as `horus-os-example-plugin`. | LOW | Datasette `datasette-plugin` cookiecutter template (creates skeleton + test + CI workflow); pytest plugin examples in docs; Home Assistant `example_integration` in core; VS Code `vscode-extension-samples` repo |
| **REFERENCE-02: Plugin author docs — manifest schema, capability list, lifecycle contract, test harness** | "I want to write one of these" is a documented user need. Without docs, only the maintainer ships plugins. | MEDIUM | Datasette `Writing plugins`; Home Assistant Developer Docs `creating_integration_manifest`; VS Code Extension API docs; pytest "Writing plugins" |

### Differentiators (Competitive Advantage)

Features that set horus-os v0.5 apart from a generic plugin system. Not required for launch, but valuable. Each is tagged for inclusion or deferral.

| Feature | Value Proposition | Complexity | v0.5 verdict |
|---------|-------------------|------------|--------------|
| **OBSERVE-01: Per-plugin error rate and latency on the existing `/observability` tab** | v0.4 already ships ObservationBus + SQLite persistence + p50/p95 + tool reliability. Extending `tool_invocations.plugin_name` is a column-level migration, not a new pipeline. "Plugin X tools fail 12% of the time" is a unique trust signal no other Python plugin system surfaces by default. | LOW (column addition + label propagation; query module already exists) | **INCLUDE in v0.5.** This is the single highest-leverage feature for differentiation. Reuses v0.4 entirely. |
| **OBSERVE-02: Per-plugin LLM cost attribution (which plugin's tools spent which dollars)** | If a plugin calls back into the LLM via `delegate_to_agent` or via a tool the plugin contributes, v0.4's cost annotation should attribute that cost to the plugin. Closes the "I installed a plugin and my Anthropic bill doubled — which one?" question. | LOW-MEDIUM (column on `llm_calls`, attribution via trace context) | **INCLUDE in v0.5 if it's a column addition.** Defer if it requires new instrumentation; that's a v0.6 conversation. |
| **MANIFEST-05: Strict TOML schema validation at install time — reject bad manifests with line-numbered errors** | `validate-pyproject` proves the pattern works; the cost is shipping a JSON schema file and a CI validator. Plugins with malformed manifests fail at install (loud), not at runtime (silent). | LOW | **INCLUDE in v0.5.** Cheap, defensible, prevents an entire class of "why doesn't my plugin work?" bug reports. |
| **PERMISSION-04: Capability strings are a closed, documented set (not free-form), with copy that explains each in user-facing terms** | Free-form capability strings invite typos and plugin sprawl. A documented closed enum (`filesystem.read`, `filesystem.write`, `net.outbound`, `secrets.read`, `process.spawn`, `agent.delegate`) keeps prompts and audit honest. | LOW (it's a Python enum + docs page) | **INCLUDE in v0.5.** Bake the enum in code, render the friendly strings in the dashboard prompt. |
| **ISOLATE-04: Slow-start timeout — if a plugin's `start()` hook blocks more than N seconds, mark it as `slow_start` and continue boot** | Single slow plugin should not delay horus-os boot. Inherited from v0.3's adapter lifecycle (which already has start/stop). | LOW (asyncio.wait_for around start) | **INCLUDE in v0.5.** Extension of existing v0.3 pattern. |
| **REFERENCE-03: Cookiecutter template (`horus-os-plugin-template`) — `cookiecutter gh:Ridou/horus-os-plugin-template`** | Datasette's single biggest accelerant for third-party authors. The cookiecutter generates manifest + setup.py + test + GH Actions CI in one command. | LOW-MEDIUM (it's a template repo + 1 docs page) | **CONSIDER for v0.5.** Could land in v0.5 release week or be the first follow-up. The reference plugin (`horus-os-example-plugin`) is the must-have; the cookiecutter is the nice-have. |
| **DASH-03: Plugin-author hyperlinks on the plugins tab (homepage, issue tracker, source)** | Cheap to render from manifest fields. Closes the "I want to file a bug" loop. | LOW | **INCLUDE in v0.5.** Manifest fields exist, render them. |
| **MANIFEST-06: `quality_scale` analog (bronze/silver/gold) declared by the author and renderable in dashboard** | Home Assistant's quality_scale gives users a quick trust signal independent of stars. For v0.5 we likely just want a "verified by maintainer" badge for the reference plugin, not a tier system. | LOW (just a field) but conceptual complexity (governance) | **DEFER to v0.6+.** A self-declared quality scale is meaningless without governance. Skip. |
| **INSTALL-06: `horus-os plugins update <name>` and `horus-os plugins update --all`** | Symmetrical with install. Datasette ships `--upgrade` via pip pass-through, but `update` as a first-class verb is more discoverable. | LOW (pip install --upgrade pass-through) | **INCLUDE in v0.5.** It is literally one argparse subcommand. |
| **PERMISSION-05: Read-only "dry-run" mode — load a plugin with all capabilities denied, see what it tries to do, then grant** | Useful for sketchy third-party plugins; lets users see the actual access pattern before granting. | MEDIUM (requires instrumenting every capability check to log on deny) | **DEFER to v0.6+.** Conceptually elegant, but the value is concentrated on a small audience and the cost is real. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that look good in v0.5 brainstorms but create rewrite cost, security debt, or scope sprawl. Ship none of these in v0.5. PROJECT.md already calls out the hosted catalog and OS-level isolation; this section adds the ones not yet in `Out of Scope`.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Hosted plugin marketplace / catalog API in v0.5** | "Users will want to browse plugins from the dashboard." | Hosted catalog = hosted service = paid ops + an attack surface (typosquatting, supply chain). Datasette ships a static `datasette.io/plugins` page generated from a repo, which is what a small project should do. PROJECT.md already deferred this. | Static `docs/plugins.md` in the horus-os repo listing the few existing plugins + the reference. Link to PyPI search `horus-os` namespace. |
| **OS-level sandbox (subprocess or container) for plugin execution in v0.5** | "What if a plugin is malicious?" | In-process Python sandboxing is broken by design (pysandbox is the canonical cautionary tale). OS-level isolation is real work — IPC contract, lifecycle complexity, performance hit on every tool call. PROJECT.md already deferred this. | Default-deny capability declarations + clear "you trust this plugin's author" prompt + revocable grants. Trust model = "you `pip install`-ed it, you took the risk." Same model Datasette, Sphinx, pytest all use. |
| **Custom in-process Python sandbox (RestrictedPython, AST whitelisting, etc.)** | "What about default-deny that actually blocks code?" | Strictly worse than no sandbox — it provides the illusion of safety while every introspection feature in Python is a bypass (`__import__`, `__builtins__`, `__class__.__mro__`, etc.). Industry consensus: do not ship this. | Same as above: clear consent + revocable grants. If a plugin author is hostile, no in-process sandbox will save you. |
| **Pluggy-style hook framework for v0.5** | "Datasette and pytest use pluggy, we should too." | We already have a Tool registry (v0.1) and an Adapter Protocol with lifecycle hooks (v0.2/v0.3). Pluggy is for systems with many extension points and complex multicall semantics. horus-os has two extension points: tools and adapters. A separate hook framework would compete with the existing registries. | Stay with the existing protocols. v0.5 just packages them behind a manifest. The plugin "contributes Tool X via the manifest" — no new hook system needed. |
| **Auto-update plugins on horus-os start** | "Users want plugins to stay current." | Auto-update silently widening capability grants (PERMISSION-02 violation) or breaking on a new version is the worst possible v0.5 first impression. Home Assistant integrations explicitly require a restart after install. | Notification-style "3 plugins have updates available" in the dashboard. User clicks update, sees the re-grant prompt if capabilities expanded. |
| **Plugin signing / Sigstore verification in v0.5** | "Supply chain attacks are real." | Plugin signing requires a publisher identity model, a signature distribution channel, and revocation. Real work — and pip itself doesn't enforce it. v0.5 is too early. | Pin versions in `horus-plugin.toml`. Show "installed from PyPI on date X" in the dashboard. Add Sigstore in v0.6+ if real-world abuse warrants it. |
| **Hot-reload of plugins without restart** | "It would be cool to swap a plugin in without a server restart." | Python doesn't really support clean module unload (sys.modules is sticky, references to old class objects persist). Hot-reload becomes a long tail of "why isn't my new code running?" bug reports. JupyterLab and Datasette both require restart. | Toggle disable, restart, toggle enable. The restart cost is seconds in horus-os. |
| **Manifest in JSON instead of TOML** | "JSON is everywhere, TOML is niche." | PROJECT.md already locked TOML. JSON is fine but TOML matches `pyproject.toml`, ships in stdlib (`tomllib`) on 3.11+, and supports comments which a manifest will want. | TOML, as locked. |
| **Per-plugin Python virtualenv** | "Two plugins might want conflicting versions of a library." | Real work (subprocess + IPC) for a marginal case. pip itself surfaces the conflict at install time. | Let pip resolve. If two plugins genuinely conflict, the user picks one or files an issue against the offending author. |
| **Plugin "settings UI" — dynamic forms rendered from manifest schema** | "Adapters get config in the dashboard, plugins should too." | A schema-driven form renderer is its own product (think Home Assistant config_flow). For v0.5 the plugin reads env vars and config files like the rest of horus-os. | Document env-var conventions in the plugin author guide. Defer schema-driven forms to v0.6+. |

## Feature Dependencies

```
MANIFEST-01..04 (declared name/version/entry points/capabilities)
    └──required-by──> DISCOVERY-01 (entry-points loader)
                          └──required-by──> INSTALL-01 (install command must validate manifest after pip install)
                                                └──required-by──> INSTALL-05 (capability prompt reads manifest)
                                                                       └──required-by──> PERMISSION-01..03 (grant model + revocation)
                                                                                              └──required-by──> ISOLATE-01..03 (a denied capability is enforced at runtime; ISOLATE-01 also catches load errors before grants are persisted)
                                                                                                                     └──required-by──> DASH-01..03 (dashboard surfaces what the grant model + isolation produced)
                                                                                                                                            └──enables──> OBSERVE-01..02 (per-plugin telemetry attaches plugin name to existing observation events)

REFERENCE-01..02 (example plugin + author docs)
    └──validates──> MANIFEST-01..04 + DISCOVERY-01..02 + INSTALL-01..06
                    (if the reference plugin doesn't install and run cleanly via the documented path, nothing else does)

MANIFEST-05 (strict schema validation)
    └──enhances──> INSTALL-01 (validation at install rejects bad plugins before the SQLite grant row is written)

ISOLATE-04 (slow-start timeout)
    └──extends──> v0.3 adapter lifecycle hooks (start/stop already exist)

OBSERVE-01..02 (per-plugin telemetry)
    └──reuses──> v0.4 ObservationBus + SQLitePersister + queries.py
                 (column-level extension: add plugin_name to llm_calls + tool_invocations)
```

### Dependency Notes

- **MANIFEST is the spine.** All seven categories below it depend on a parsed, validated manifest. The schema decision (TOML, locked) and the closed capability enum (PERMISSION-04) must land in the first plugin-system phase, before anything else.
- **DISCOVERY-01 (entry points) + DISCOVERY-02 (local dir) are both required.** Entry points is the third-party distribution path; local dir is the dev path. PROJECT.md already commits to both. They share the same loader code but the load path differs (importlib.metadata vs filesystem walk).
- **PERMISSION-02 (re-prompt on widened scope) is a hard ordering constraint.** It must land in the same phase as INSTALL-05 (first-run prompt) or it creates a security regression on every plugin upgrade. Don't ship the prompt without the re-prompt logic.
- **ISOLATE-01 (no host crash) blocks REL.** Three-OS install verification can't go green if a synthetic broken plugin can take down the server. The "broken plugin" test fixture is part of REFERENCE.
- **OBSERVE-01 (per-plugin error rate) is the killer differentiator** and it's almost free given v0.4. Don't drop it. It also makes ISOLATE-02 (last error visible) much richer: the dashboard shows not just "plugin error" but "plugin error 14% of the time across 320 calls in the last 7 days."
- **REFERENCE-01 (example plugin) blocks REL too.** The release gate should refuse to tag if the example plugin doesn't install and pass its smoke test on the three-OS matrix. This is the v0.5 equivalent of v0.4's two-variant install-smoke.

## MVP Definition

### Launch With (v0.5.0)

Minimum viable v0.5 — the smallest plugin system that earns user trust and unblocks third-party authors. Mapped to PROJECT.md's locked decisions plus the table-stakes rows above. Each row is the v0.5.0 release gate.

- [ ] **MANIFEST-01..04 + MANIFEST-05** — `horus-plugin.toml` with name, version, compatible-horus-os range, declared tools + adapters, requested capabilities, author/homepage/issue tracker; strict TOML schema validation at install with line-numbered errors.
- [ ] **DISCOVERY-01 + DISCOVERY-02** — Entry points group `horus_os.plugins` (loaded via `importlib.metadata`) + `~/.horus-os/plugins/` directory drop-in. Same loader, different inputs.
- [ ] **INSTALL-01..06** — `horus-os plugins install|uninstall|list|info|update` subcommands wrapping pip; first-run capability prompt with explicit consent.
- [ ] **PERMISSION-01..04** — Default-deny posture; grants persisted in SQLite keyed by `(plugin_name, plugin_version)`; revocable from dashboard; re-prompt on version-upgrade scope widening; closed enum of capability strings.
- [ ] **ISOLATE-01..04** — Plugin load failure or runtime exception caught and reported, never propagates to host; per-plugin error status surface; enable/disable toggle; slow-start timeout that doesn't block boot.
- [ ] **DASH-01..03** — `/plugins` tab listing installed plugins with version, declared contributions, granted capabilities, lifecycle status, last error; per-plugin enable/disable toggle; manifest hyperlinks (homepage, issue tracker).
- [ ] **OBSERVE-01** — Extend v0.4 `tool_invocations` with `plugin_name`; render per-plugin error rate on `/observability`. **This is the v0.5 differentiator. Don't cut it.**
- [ ] **REFERENCE-01..02** — Published `horus-os-example-plugin` in the same repo as a separate package; plugin author docs (`docs/PLUGINS.md`) covering manifest, capabilities, lifecycle, testing.
- [ ] **MIG-05** — Additive v4→v5 SQLite migration (plugin_grants table + plugin_name column on tool_invocations); v0.4 databases continue to read.
- [ ] **TEST/REL** — Three-OS install gate (Ubuntu, macOS, Windows × Python 3.11 + 3.12) including a synthetic broken-plugin fixture that proves ISOLATE-01.

### Add After v0.5.0 (v0.5.x or v0.6 follow-ups)

Features that strengthen the plugin system once the core has shipped. Each row has a trigger condition — do not ship speculatively.

- [ ] **REFERENCE-03 cookiecutter template** — Add when the first third-party author opens an issue asking for one (very likely within v0.5's first month).
- [ ] **OBSERVE-02 per-plugin LLM cost attribution** — Add when the first user asks "which plugin spent the most on Anthropic this week?" (deferral OK; ship in v0.5 only if it's a literal column addition).
- [ ] **Notification-style update banner on dashboard** — Add when the second plugin author ships and users have stale installs.

### Future Consideration (v0.6+ and beyond)

Features that need more validation, more governance, or more user demand before they're worth building.

- [ ] **OS-level sandbox (subprocess or container)** — Defer until there is a documented real-world abuse case for an in-process plugin. PROJECT.md already lists this in Out of Scope.
- [ ] **Hosted plugin catalog / browse-and-install UI** — Defer until there are 10+ plugins and the static repo page has hit its limits.
- [ ] **Plugin signing / Sigstore verification** — Defer until the supply chain attack happens to a horus-os user. Pin versions in the meantime.
- [ ] **Schema-driven plugin settings UI** — Defer until config sprawl is a documented user complaint.
- [ ] **PERMISSION-05 dry-run mode** — Defer until at least one third-party plugin is sketchy enough to warrant the engineering investment.
- [ ] **Self-declared quality_scale tiers** — Defer indefinitely. Meaningless without governance.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| MANIFEST-01..04 (declared name/version/entry points/capabilities/author) | HIGH | LOW | **P1** |
| MANIFEST-05 (strict schema validation at install) | MEDIUM | LOW | **P1** |
| DISCOVERY-01 (entry points loader) | HIGH | LOW | **P1** |
| DISCOVERY-02 (local directory loader) | MEDIUM | LOW | **P1** |
| INSTALL-01..04 (install/uninstall/list/info) | HIGH | LOW | **P1** |
| INSTALL-05 (first-run capability prompt) | HIGH | MEDIUM | **P1** |
| INSTALL-06 (update subcommand) | MEDIUM | LOW | **P1** |
| PERMISSION-01..03 (default-deny + persisted + revocable) | HIGH | MEDIUM | **P1** |
| PERMISSION-04 (closed capability enum) | MEDIUM | LOW | **P1** |
| ISOLATE-01 (no host crash on plugin failure) | HIGH | MEDIUM | **P1** |
| ISOLATE-02 (last error surface) | HIGH | LOW | **P1** |
| ISOLATE-03 (enable/disable toggle) | HIGH | LOW | **P1** |
| ISOLATE-04 (slow-start timeout) | MEDIUM | LOW | **P1** |
| DASH-01 (plugins tab) | HIGH | MEDIUM | **P1** |
| DASH-02 (enable/disable from dashboard) | HIGH | LOW | **P1** |
| DASH-03 (author hyperlinks) | LOW | LOW | **P1** |
| REFERENCE-01 (example plugin) | HIGH | MEDIUM | **P1** |
| REFERENCE-02 (author docs) | HIGH | LOW | **P1** |
| OBSERVE-01 (per-plugin error rate) | HIGH | LOW | **P1** |
| OBSERVE-02 (per-plugin LLM cost) | MEDIUM | LOW-MEDIUM | **P2** |
| REFERENCE-03 (cookiecutter template) | MEDIUM | LOW-MEDIUM | **P2** |
| MANIFEST-06 (quality_scale tier) | LOW | LOW | **P3** |
| PERMISSION-05 (dry-run mode) | LOW | MEDIUM | **P3** |
| Hosted catalog | LOW (today) | HIGH | **P3** |
| OS-level sandbox | LOW (today) | HIGH | **P3** |
| Plugin signing | LOW (today) | HIGH | **P3** |
| Hot-reload | LOW | HIGH | **P3** (anti-feature for v0.5) |
| Auto-update on start | NEGATIVE | LOW | **anti-feature** |
| In-process Python sandbox | NEGATIVE (illusion of safety) | MEDIUM | **anti-feature** |

**Priority key:**
- **P1:** Must ship in v0.5.0. The minimum that earns trust.
- **P2:** Should ship in v0.5.x as fast follow.
- **P3:** Defer to v0.6+ until user demand validates the cost.
- **anti-feature:** Do not ship. Listed for explicit rejection.

## Competitor Feature Analysis

How the named plugin systems handle the same surface horus-os v0.5 is building. Use this table when implementation questions arise — do what at least two of them do, deviate only with documented reason.

| Capability | Datasette | pytest | Home Assistant | Sphinx | JupyterLab | VS Code | horus-os v0.5 plan |
|------------|-----------|--------|----------------|--------|------------|---------|-----|
| **Manifest format** | None (setup.py entry_points only) | None (setup.py entry_points only) | `manifest.json` (per integration) | None (setup.py + setup() function returns dict) | `package.json` + `jupyter-config-data` | `package.json` with `contributes` | `horus-plugin.toml` (TOML, stdlib `tomllib`) |
| **Required manifest fields** | name + entry_points | name + entry_points | domain, name, codeowners, integration_type | name in setup.py | name, version, jupyterlab field | name, version, publisher, engines.vscode | name, version, horus_os_compatible_range, contributions |
| **Discovery — primary** | entry-points group `datasette` | entry-points group `pytest11` | core integrations bundled + `custom_components/` dir | `conf.py extensions = []` list | entry-points + `jupyter labextension install` | VS Code marketplace + local install | entry-points group `horus_os.plugins` |
| **Discovery — drop-in dir** | `--plugins-dir=plugins/` | `conftest.py` auto-discovery | `custom_components/` | `sys.path.append('exts')` then list in conf.py | `--app-dir` | n/a | `~/.horus-os/plugins/` |
| **Install command** | `datasette install <name>` (pip wrapper) | `pip install` (no wrapper) | HACS (third-party UI) | `pip install` (no wrapper) | `pip install` + `jupyter labextension enable` | Marketplace UI + CLI | `horus-os plugins install <pip-spec>` |
| **Uninstall command** | `datasette uninstall <name>` | `pip uninstall` | HACS Remove | `pip uninstall` | `jupyter labextension uninstall` | Marketplace UI + CLI | `horus-os plugins uninstall <name>` |
| **List command** | `datasette plugins` | n/a (`pip list \| grep pytest-`) | Settings > Devices & Services | n/a (read conf.py) | `jupyter labextension list` | Extensions view | `horus-os plugins list` |
| **Permission model** | None (in-process trust) | None (in-process trust) | Entity-level grants in policy | None (in-process trust) | None (in-process trust) | Workspace Trust + publisher trust + `capabilities.untrustedWorkspaces` | Closed enum of capability strings, default-deny, per-plugin grant persisted in SQLite |
| **First-run consent prompt** | No | No | Config flow per integration | No | No | Yes (1.97+: trust the publisher dialog) | Yes |
| **Failure isolation** | pluggy try/except per hook | pytest plugin load errors caught + reported | `ConfigEntryNotReady` triggers retry; Recovery Mode for catastrophic failures | Errors surface in build log; one bad extension can break build | Errors caught, plugin disabled | Extension host crash isolated from editor | Try/except around load + start + tool invocations; degrade to "plugin error" status; never crash host |
| **Per-plugin observability** | `/-/plugins` JSON; no error rate | Plugin name shows in test output; no error rate | System Health endpoint per integration; error count on integrations page | Build log per extension; no telemetry | Plugin Manager surface; no error rate | Extensions view + extension host metrics | **Per-plugin error rate + latency p50/p95 on `/observability` (v0.4 reuse). This is the differentiator.** |
| **Enable/disable toggle** | No (uninstall = remove) | n/a | Yes (per integration) | No (edit conf.py) | Yes (`jupyter labextension disable`) | Yes (per extension) | Yes |
| **Reference / template** | `simonw/datasette-plugin` cookiecutter | Examples in docs | `example_integration` in core | Various tutorial extensions | `extension-cookiecutter-ts` | `vscode-extension-samples` repo | `horus-os-example-plugin` (separate package) + future cookiecutter |
| **Hosted catalog** | Static `datasette.io/plugins` page | None | HACS (third-party UI on top of GitHub) | None | PyPI search + Plugin Manager UI | Yes (Marketplace) | None in v0.5 (static `docs/plugins.md`) |

**Pattern that emerges:** Datasette is the closest analog — a small Python-first project with entry-points + a cookiecutter + a CLI wrapper around pip + a JSON endpoint listing installed plugins. horus-os v0.5 = Datasette's plugin model + Home Assistant's manifest + capability declaration + VS Code's first-run consent prompt + v0.4's existing observability stack. None of those four pieces is new engineering; the work is wiring them together cleanly.

## Sources

### Datasette (primary analog)
- [Plugins — Datasette documentation](https://docs.datasette.io/en/stable/plugins.html) — `datasette install/uninstall/plugins` CLI; entry-points group `datasette`; `/-/plugins` endpoint; pluggy hook system
- [Writing plugins — Datasette documentation](https://docs.datasette.io/en/stable/writing_plugins.html) — minimum setup.py, one-off plugin pattern via `--plugins-dir`, hookimpl decorator
- [simonw/datasette-plugin cookiecutter template](https://github.com/simonw/datasette-plugin) — reference structure for third-party authors
- [A cookiecutter template for writing Datasette plugins (Simon Willison)](https://simonwillison.net/2020/Jun/20/cookiecutter-plugins/) — author rationale

### pytest
- [Writing plugins — pytest documentation](https://docs.pytest.org/en/stable/how-to/writing_plugins.html) — three plugin types: builtin, external (entry points), conftest auto-discovery
- [How to install and use plugins — pytest documentation](https://docs.pytest.org/en/stable/how-to/plugins.html) — `pytest11` entry-points group
- [pluggy default multicall exception handling — issue 259](https://github.com/pytest-dev/pluggy/issues/259) — failure isolation behavior

### Home Assistant
- [Integration manifest — Home Assistant Developer Docs](https://developers.home-assistant.io/docs/creating_integration_manifest/) — manifest.json schema, required vs optional fields
- [Permissions — Home Assistant Developer Docs](https://developers.home-assistant.io/docs/auth_permissions/) — policy model, default-deny via `True=grant, None=deny`
- [Handling setup failures — Home Assistant Developer Docs](https://developers.home-assistant.io/docs/integration_setup_failures/) — `ConfigEntryNotReady`, retry semantics, recovery patterns
- [Recovery mode — Home Assistant](https://www.home-assistant.io/integrations/recovery_mode/) — fallback boot model when user integrations break startup
- [Integration system health — Home Assistant Developer Docs](https://developers.home-assistant.io/docs/core/integration/system_health/) — per-integration health surface
- [HACS — Home Assistant Community Store](https://www.hacs.xyz/) — community plugin manager UX patterns

### Sphinx
- [Sphinx Extensions — Sphinx documentation](https://documentation.help/Sphinx/extensions.html) — setup() function contract, `extensions = []` config
- [Sphinx API — Sphinx documentation](https://www.sphinx-doc.org/en/master/extdev/index.html) — setup() return dict (version, env_version, parallel_read_safe)

### JupyterLab
- [Extensions — JupyterLab documentation (stable)](https://jupyterlab.readthedocs.io/en/stable/user/extensions.html) — enable/disable, discovery, `jupyter labextension` CLI
- [Is there a way to enable/disable a lab extension through entries in a .py file — Jupyter Discourse](https://discourse.jupyter.org/t/is-there-a-way-to-enable-disable-a-lab-extension-through-entries-in-a-py-file/18141) — config-driven disable

### VS Code
- [Extension Manifest — Visual Studio Code Extension API](https://code.visualstudio.com/api/references/extension-manifest) — package.json fields, contributes section
- [Activation Events — Visual Studio Code Extension API](https://code.visualstudio.com/api/references/activation-events) — `activationEvents` declarative startup
- [Workspace Trust Extension Guide — Visual Studio Code Extension API](https://code.visualstudio.com/api/extension-guides/workspace-trust) — `capabilities.untrustedWorkspaces.supported`, `restrictedConfigurations`, Restricted Mode
- [Extension runtime security — Visual Studio Code](https://code.visualstudio.com/docs/configure/extensions/extension-runtime-security) — trust-the-publisher dialog from 1.97+

### Python packaging primitives
- [Creating and discovering plugins — Python Packaging User Guide](https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/) — entry points vs namespace packages vs naming convention
- [Entry points specification — Python Packaging User Guide](https://packaging.python.org/specifications/entry-points/) — spec for the discovery mechanism we'll use
- [validate-pyproject — PyPI](https://pypi.org/project/validate-pyproject/) — pattern for strict TOML manifest validation
- [Python and TOML: Read, Write, and Configure with tomllib — Real Python](https://realpython.com/python-toml/) — `tomllib` in stdlib 3.11+

### Security model
- [Sandboxing Untrusted Python Code (UBOS)](https://ubos.tech/news/sandboxing-untrusted-python-code-secure-execution-strategies-and-ubos-solutions/) — default-deny posture as industry consensus
- [pysandbox — vstinner](https://github.com/vstinner/pysandbox) — canonical "in-process Python sandboxing is broken by design" reference
- [Running Untrusted Python Code (Andrew Healey)](https://healeycodes.com/running-untrusted-python-code) — practical failure modes

---
*Feature research for: horus-os v0.5 Plugin System*
*Researched: 2026-05-26*
*Consumer: REQUIREMENTS.md categories MANIFEST, DISCOVERY, INSTALL, PERMISSION, ISOLATE, DASH, OBSERVE, REFERENCE — each row above is REQ-ID-able as listed.*
