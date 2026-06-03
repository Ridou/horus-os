---
title: "Schema and migrations"
description: "How horus-os upgrades its SQLite schema automatically, how to verify the current version, and an index of the version-to-version migration guides."
---

## How migrations work

horus-os keeps all authoritative state in a single SQLite database (`horus.sqlite`) inside your [data directory](/getting-started/configuration/). Each release that adds tables or columns bumps an internal `SCHEMA_VERSION`. The current value is **13**.

You do not run migrations by hand. When you start a newer version of horus-os against an older database, the runtime applies the schema upgrade automatically on first start. There are no manual SQL steps, no flags, and no separate migration command.

Every migration shipped so far follows the same two rules:

- **Additive only.** Migrations add new tables, add new nullable columns, and add indexes. No existing column changes type, and no existing row is rewritten. Data written by an older version reads back byte-identical under the newer schema.
- **Idempotent.** Re-running the upgrade is safe. If a migration has already run, starting again is a no-op.

Because every change is additive, upgrading the package and starting horus-os once is the entire upgrade procedure:

```bash
pip install --upgrade horus-os
horus-os serve
```

> [!NOTE]
> There is no automated downgrade path. Once a migration runs, the new tables and columns stay in the database permanently. Older code does not read them, so the file grows slightly but reads stay identical. If you need to keep running an older version, point it at a separate data directory with `HORUS_OS_DATA_DIR` and do not run a newer binary against the older database.

## Verify the current schema version

The schema version lives in the `schema_version` table. Query it with the `sqlite3` CLI, pointing at `horus.sqlite` inside your platform's data directory:

```bash
# macOS
sqlite3 "$HOME/Library/Application Support/horus-os/horus.sqlite" "SELECT version FROM schema_version"

# Linux
sqlite3 "$HOME/.local/share/horus-os/horus.sqlite" "SELECT version FROM schema_version"
```

```text
# Windows (PowerShell)
sqlite3 "$env:APPDATA\horus-os\horus.sqlite" "SELECT version FROM schema_version"
```

If you set `HORUS_OS_DATA_DIR`, the database is `horus.sqlite` inside that directory instead.

The expected output for the current release is `13`. Later releases bump this number as they add additive tables, so a value above `13` is also healthy. A value below the version your installed runtime expects means the startup migration did not finish: check the server logs for the migration error and re-run `horus-os serve`.

> [!TIP]
> `horus-os doctor` runs a broad health check, including database access. Run it after any upgrade to confirm the runtime opened the database cleanly.

## Migration guides

Each version-to-version upgrade has a detailed guide in the repository. They are not separate documentation pages here; follow the GitHub links below for the full text, including the per-release table list, new extras, and breaking-change scan (every release so far is purely additive).

### v0.7 to v0.8 (schema 12 to 13)

The current upgrade. v0.8 adds a full local-first capability layer and the Deep Research workflow, all gated behind optional extras or config flags. A bare upgrade activates none of them. The schema moves from 12 to 13 by adding two new tables, `skills` (for the [skills system](/extending/plugins/)) and `shell_invocations` (the gated-shell audit log). Existing rows, including the v0.7 `schedules` table, are unchanged.

Read it on GitHub: [docs/MIGRATION-v0.7-to-v0.8.md](https://github.com/Ridou/horus-os/blob/main/docs/MIGRATION-v0.7-to-v0.8.md)

### v0.5 to v0.7 (schema 6 to 12)

v0.6 (Contribution Gate) was never tagged, so v0.7.0 follows v0.5.0 directly. v0.7 adds the Next.js command center, an integrations surface with a read-only API and a loopback-guarded key-write endpoint, opt-in Discord and Supabase adapters, a cron scheduler with an always-on service, and an opt-in Vercel deploy path with a read-only GitHub tool. Five new tables land (`integration_verification_state`, `tasks`, `discord_feedback`, `sync_cursors`, `schedules`), plus three nullable columns on `agent_profiles` for the starter team.

Read it on GitHub: [docs/MIGRATION-v0.5-to-v0.7.md](https://github.com/Ridou/horus-os/blob/main/docs/MIGRATION-v0.5-to-v0.7.md)

### v0.4 to v0.5 (schema 5 to 6)

v0.5 adds the third-party plugin system with default-deny capability grants and per-plugin observability attribution. Three new tables land (`plugins`, `plugin_capabilities`, `plugin_status`), plus two nullable `plugin_name` columns on `tool_invocations` and `llm_calls` and one supporting index. The `--disable-all-plugins` boot flag (or `HORUS_OS_DISABLE_PLUGINS=true`) starts the runtime with all plugin discovery skipped if a third-party plugin misbehaves.

Read it on GitHub: [docs/MIGRATION-v0.4-to-v0.5.md](https://github.com/Ridou/horus-os/blob/main/docs/MIGRATION-v0.4-to-v0.5.md)

## See also

- [Changelog](/reference/changelog/) for the complete per-release change log.
- [Configuration](/getting-started/configuration/) for the data directory layout and `HORUS_OS_DATA_DIR`.
- [Environment variables](/reference/environment-variables/) for the full env-var reference.
- [CLI reference](/reference/cli-reference/) for `horus-os doctor` and the other commands.
