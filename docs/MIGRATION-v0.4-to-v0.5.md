# Migration from v0.4 to v0.5

## TL;DR

v0.5 is purely additive. Every v0.4 surface (`ObservationBus`,
`SQLitePersister`, the `llm_calls` and `tool_invocations` child
tables, the bundled `pricing.json`, the `CostAnnotator`, the
`/observability` dashboard tab, the `horus-os usage` CLI, the opt-in
`OtelAdapter` behind the `[otel]` extra, the four v0.3 adapters,
the JSON API, the CLI subcommands) continues to work byte-identical.
No removals. No deprecations.

What lights up: a third-party plugin system with default-deny
capability grants pinned to `(plugin_name, plugin_version,
manifest_hash)`, a `/plugins` dashboard tab, a `horus-os plugins`
CLI subcommand family (9 subcommands), per-plugin observability
attribution that lands the plugin name on every `llm_calls` and
`tool_invocations` row, a `--disable-all-plugins` boot escape
hatch, and three new documentation files plus a JSON-Schema mirror
of the manifest contract.

## What is new

### Plugin manifest contract

Every plugin ships a `horus-plugin.toml` validated by
`horus_os.plugins.manifest.MANIFEST_V1_SCHEMA` (pydantic v2). Required
fields: `manifest_version`, `name`, `version`, `description`,
`author`, `license`, `horus_os_compat`. Optional fields:
`contributions.tools`, `contributions.adapters`, `capabilities`,
`homepage`, `issue_tracker`. Unknown top-level keys emit a
`UserWarning` (forward-compat: a v2-authored manifest still loads
under a v0.5 horus-os, with warnings).

### Two-phase installer

`horus-os plugins install <package-spec>` walks a five-phase pipeline:
`pip download --no-deps` into a tmpdir, refuse-by-default sdist
detection (override with `--allow-sdist`), manifest validation and
wheel-RECORD `.pth` refusal and `Requires-Dist` downgrade-of-runtime
refusal, capability grant prompt (no half-grant state per
INSTALL-05), `pip install --no-deps --no-build-isolation`. Any
failure rolls back to the pre-install state via `pip uninstall -y`
plus a `DELETE FROM plugins`.

### Default-deny capability grants

Four-capability v1 catalog: `filesystem.read`, `filesystem.write`,
`net.outbound`, `secrets.read`. Every capability is denied until the
user explicitly grants it at install time. Grants are pinned to the
`(plugin_name, plugin_version, manifest_hash)` triple. A version
upgrade or capability-set edit re-prompts. The grant transitions
(issue, revoke, expire, re-grant) append to a persistent audit log
that survives plugin uninstall.

### Bounded lifecycle

`asyncio.wait_for(start, timeout=2.0)` wraps every plugin adapter's
`start(ctx)` hook (ISOLATE-02). A hung `start` becomes a load-time
`PluginLoadError`, never a 60-second startup stall. The same bound
applies to `stop()` on shutdown.

### `/plugins` dashboard tab

A sixth nav tab joins Chat / Traces / Writes / Agents / Adapters /
Observability. Renders one row per discovered plugin with manifest
metadata, granted-capability pills, status (pending / running /
error / disabled), error message, and per-plugin Enable / Disable /
Revoke buttons.

### Per-plugin observability

Two new NULLABLE columns: `tool_invocations.plugin_name` and
`llm_calls.plugin_name`. The runner publishes these on every event;
pre-v0.5 rows stay NULL, surfaced in the dashboard as "horus-os
core" attribution. The existing observability queries
(`agent_totals`, `cost_by_agent`, `latency_p50_p95`,
`tool_reliability`) gain optional plugin-attribution filters.

## Schema migration v5 to v6

v0.4 databases upgrade cleanly on first v0.5 startup. The migration is
additive only.

Three new tables:

- `plugins` — one row per discovered or installed plugin. Carries
  `name`, `version`, `manifest_hash`, `enabled`, `installed_at`,
  `source` (entry_point or filesystem).
- `plugin_capabilities` — one row per granted or pending capability,
  pinned to `(plugin_name, plugin_version, capability)`. State is
  one of `granted`, `pending`, `revoked`, `expired`. CASCADE deletes
  on plugin removal.
- `plugin_status` — one row per plugin carrying runtime status
  (`pending`, `running`, `error`, `disabled`) plus `error_phase`,
  `error_message`, `last_seen`.

Two new NULLABLE columns:

- `tool_invocations.plugin_name TEXT NULL` — set on every tool call
  contributed by a plugin; NULL for v0.4 core tool calls (the
  dashboard renders these as "horus-os core" attribution).
- `llm_calls.plugin_name TEXT NULL` — set on every LLM call made
  inside a plugin-contributed tool's handler; NULL for v0.4 core
  LLM calls.

One new index, on `(plugin_name, plugin_version)`, supporting the
upgrade-diff classifier in `update_plugin`.

All additive. Pre-v0.5 rows read back byte-identical: existing
`llm_calls` and `tool_invocations` rows have `plugin_name = NULL`,
the three new tables are empty, and the new index does not change
any existing query plan.

## New base dependencies

Two pure-Python packages are now declared in
`[project.dependencies]`:

- `pydantic>=2.7,<3` powers manifest validation. The pydantic v2
  `BaseModel.model_json_schema()` export produces
  `docs/manifest-v1.schema.json`, the human-readable JSON-Schema
  mirror that `scripts/release_gate.py` diffs at release time.
- `packaging>=24.0` powers PEP 440 specifier parsing. The
  `horus_os_compat` field is validated through
  `packaging.specifiers.SpecifierSet`; the installer's runtime-dep
  downgrade gate parses `Requires-Dist` lines through
  `packaging.requirements.Requirement`.

Both are universal pure-Python wheels — no 3-OS install-smoke
impact, no Windows wheel gap, no native build step. A bare
`pip install horus-os` pulls both at install time without any extra
flag.

## How to roll back

There is no downgrade path back to v0.4 once the v5→v6 migration has
run. The three new tables, two new NULLABLE columns, and one new
index remain in the database forever. v0.4 code does not read any of
them, so the file size grows but reads stay byte-identical.

The safety hatch is the boot flag `--disable-all-plugins`, wired in
`src/horus_os/__main__.py` and consumed in
`src/horus_os/cli/serve_cmd.py`. Pass the CLI flag (or set the
`HORUS_OS_DISABLE_ALL_PLUGINS=1` env var) and `horus-os` starts with
entry-point discovery and local-directory discovery both skipped.
Every adapter loads as if v0.4 — the four shipped v0.3 adapters plus
the v0.4 OtelAdapter — while every third-party plugin stays dormant.
Use this when a third-party plugin is misbehaving and you need to
keep the rest of the system running.

## Breaking change scan

There are no breaking changes to v0.4 features. Every public API,
every persisted schema column, every CLI flag, every dashboard tab,
and every adapter contract from v0.4 continues to work byte-identical
under v0.5.

## Verification

The migration ran successfully when the SQLite `user_version` pragma
reports `6`:

```
sqlite3 ~/.horus-os/data.db "PRAGMA user_version"
```

Expected output: `6`. If the value is `5`, the v0.5 runtime did not
finish its startup migration — check the server logs for the
migration error and re-run `horus-os serve`.

## See also

- `docs/PLUGINS.md`: plugin-author guide. Anatomy of the manifest,
  capability catalog, lifecycle hooks, three-tier testing fixtures,
  reference-plugin walkthrough, public API surface, distribution.
- `docs/PLUGIN-SECURITY.md`: threat model, trust contract,
  out-of-scope defenses, recommended user practices. Linked from
  the installer's capability grant prompt.
- `docs/manifest-v1.schema.json`: JSON-Schema mirror of the
  pydantic manifest contract. Phase 49 release-gate diff target.
- `CHANGELOG.md` `[0.5.0]` section: complete v0.5 change log.
