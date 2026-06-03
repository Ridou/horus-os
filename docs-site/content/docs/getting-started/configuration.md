---
title: "Configuration"
description: "How a horus-os installation is configured, including the data directory layout and every config.toml section with its keys and defaults."
---

## Overview

A horus-os installation keeps everything (settings, database, vault, downloaded models) in a single data directory. Runtime settings live in one file, `config.toml`, at the root of that directory. The CLI reads `config.toml` on startup, applies a small set of environment overrides, and falls back to built-in defaults for anything the file does not set.

Editing configuration is additive and safe: a key you omit simply takes its default. You never have to write a full file by hand.

> [!IMPORTANT]
> Provider API keys are never stored in `config.toml`. They come from environment variables (for example `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `HORUS_OS_WEB_SEARCH_KEY`). This keeps secrets out of committed or shared config files.

## The data directory

All persistent state lives under one directory. The default location depends on your platform:

| Platform | Default data directory |
| --- | --- |
| macOS | `~/Library/Application Support/horus-os` |
| Linux | `$XDG_DATA_HOME/horus-os`, or `~/.local/share/horus-os` if `XDG_DATA_HOME` is unset |
| Windows | `%APPDATA%\horus-os` |

Set the `HORUS_OS_DATA_DIR` environment variable to override the location. This is useful for running multiple isolated installations or pointing at an external disk.

```bash
export HORUS_OS_DATA_DIR=~/horus-data
horus-os doctor
```

### Layout

Inside the data directory you will find:

| Path | What it holds |
| --- | --- |
| `config.toml` | The installation settings described on this page |
| `horus.sqlite` | The authoritative SQLite database (audited storage) |
| `notes/` | The vault, plain markdown files |
| `skills/` | Discoverable skill files |
| `models/` | Downloaded embedding models (created lazily) |
| `vectors.sqlite` | The on-device vector index, a rebuildable cache |

> [!NOTE]
> `vectors.sqlite` is a cache, not audited storage. You can delete it and rebuild it with `horus-os memory reindex` without touching the `horus.sqlite` audit trail.

## Creating config.toml

Run `horus-os init` to create the data directory and write a starter `config.toml`. The interactive flag walks you through the common settings.

```bash
horus-os init --interactive
```

To regenerate the file from current settings, use `horus-os init --force`. You can also edit `config.toml` by hand with any text editor; horus-os reads it on the next startup.

## A representative config.toml

The following file shows the always-present sections plus the optional ones a typical setup enables. Optional sections are only written when you diverge from defaults, so a fresh install starts smaller than this.

```toml
# horus-os configuration
# Edit by hand or via `horus-os init --force`.

[providers]
default = "anthropic"
anthropic_model = "claude-sonnet-4-6"
gemini_model = "gemini-2.5-flash"

[storage]
db_path = "/Users/you/Library/Application Support/horus-os/horus.sqlite"

[notes]
notes_dir = "/Users/you/Library/Application Support/horus-os/notes"

[skills]
dir = "/Users/you/Library/Application Support/horus-os/skills"

[local]
base_url = "http://localhost:11434/v1"
model = "llama3.1"
context_window = 4096

[memory]
vector_enabled = true
embedding_model = "BAAI/bge-small-en-v1.5"

[tools.web_search]
provider = "searxng"
base_url = "http://localhost:8080"

[research]
max_sources = 10
max_iterations = 5

[shell]
enabled = false
timeout_seconds = 30
output_cap_bytes = 1048576
type = "auto"
confirm = false
```

> [!TIP]
> Paths are written as forward-slash strings, even on Windows. The loader expands a leading `~` for you.

## Section reference

The sections below describe every `config.toml` table that horus-os recognizes. The `[providers]`, `[storage]`, `[notes]`, `[skills]`, and `[shell]` tables are always written. The rest are written only when you change a value from its default.

### [providers]

Chooses the LLM provider and the model used for each provider. API keys are not set here; they come from environment variables.

| Key | Default | Purpose |
| --- | --- | --- |
| `default` | `"anthropic"` | The provider used when none is specified |
| `anthropic_model` | `"claude-sonnet-4-6"` | Model for the Anthropic provider |
| `gemini_model` | `"gemini-2.5-flash"` | Model for the Gemini provider |

### [storage]

Locates the SQLite database.

| Key | Default | Purpose |
| --- | --- | --- |
| `db_path` | `<data_dir>/horus.sqlite` | Absolute path to the database file |

### [notes]

Locates the vault, a folder of plain markdown files.

| Key | Default | Purpose |
| --- | --- | --- |
| `notes_dir` | `<data_dir>/notes` | Directory that holds the vault |

> [!NOTE]
> The vault is plain markdown. horus-os does not parse Obsidian wikilinks, tags, or YAML frontmatter as metadata; they are stored as plain text. See [The Vault](/concepts/the-vault/).

### [skills]

Locates the skills folder, the filesystem source of truth for discoverable skill files.

| Key | Default | Purpose |
| --- | --- | --- |
| `dir` | `<data_dir>/skills` | Directory that holds skill files |

### [pricing]

Overrides the bundled token pricing table. This section is written only when you set a custom path.

| Key | Default | Purpose |
| --- | --- | --- |
| `path` | bundled package data | Absolute path to a custom `pricing.json` |

The `HORUS_OS_PRICING_PATH` environment variable, when set, takes precedence over this key.

### [local]

Settings for a local OpenAI-compatible model server (for example an Ollama endpoint). This section is written only when you set a model or change the base URL.

| Key | Default | Purpose |
| --- | --- | --- |
| `base_url` | `"http://localhost:11434/v1"` | Loopback URL of your local model server |
| `model` | `""` (unset) | Model name your local server serves |
| `context_window` | `4096` | Context budget the tool loop plans against |

> [!CAUTION]
> Keep `base_url` on a loopback address. Pointing it at `0.0.0.0` would expose the local model API to your LAN.

### [memory]

On-device hybrid vector memory. The feature is off by default. You must opt in and run `horus-os memory download-model` before any embedding happens, so a fresh install starts and serves notes offline with no model file present. This requires the `local-memory` extra, which is not included in `all`.

| Key | Default | Purpose |
| --- | --- | --- |
| `vector_enabled` | `false` | Turns on the vector memory feature |
| `embedding_model` | `"BAAI/bge-small-en-v1.5"` | Embedding model name |
| `models_dir` | `<data_dir>/models` | Directory for downloaded model files |

This section is written only when you enable vector memory, change the embedding model, or set a custom `models_dir`.

### [tools.web_search]

Bring-your-own web search. The web search tool is absent from the default tool registry until you configure a provider (default-deny). This section is written only when `provider` is set.

| Key | Default | Purpose |
| --- | --- | --- |
| `provider` | none | One of `searxng`, `brave`, or `tavily` |
| `base_url` | none | SearXNG instance URL (required for `searxng`, optional for hosted providers) |

The provider API key is read from the `HORUS_OS_WEB_SEARCH_KEY` environment variable and is never written to `config.toml`.

### [research]

Hard caps for an autonomous Deep Research run. These are limits the coordinator can never silently exceed. This section is written only when a cap diverges from its default.

| Key | Default | Purpose |
| --- | --- | --- |
| `max_sources` | `10` | Maximum distinct URLs a research run will accept |
| `max_iterations` | `5` | Maximum iterations across the whole delegation tree |

See [Autonomous research](/guides/autonomous-research/).

### [shell]

Gated shell execution. This encodes default-deny: the shell execution tool is absent from the registry until you opt in. This table is always written so the gate state and safety limits round-trip.

| Key | Default | Purpose |
| --- | --- | --- |
| `enabled` | `false` | Enables the shell execution tool |
| `working_dir` | `<data_dir>/shell` | Safe root directory for shell commands |
| `timeout_seconds` | `30` | Per-command timeout |
| `output_cap_bytes` | `1048576` | Maximum captured output per command |
| `type` | `"auto"` | One of `bash`, `powershell`, `cmd`, or `auto` (auto detects at runtime) |
| `confirm` | `false` | Whether to require confirmation before running a command |

> [!NOTE]
> The `HORUS_OS_SHELL_ENABLED` environment variable is a runtime gate read when the tool registry is built. It is intentionally not a `config.toml` key, so toggling it never requires rewriting the file.

## Verifying your configuration

After editing `config.toml`, run the health check to confirm horus-os can load it and reach your configured providers.

```bash
horus-os doctor
```

## See also

- [Reference: Configuration](/reference/configuration/) for the full key table
- [Reference: Environment variables](/reference/environment-variables/) for every supported variable
- [Installation](/getting-started/installation/) for pip extras
- [The Vault](/concepts/the-vault/) for how notes are stored
