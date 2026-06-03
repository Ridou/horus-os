---
title: "Configuration reference"
description: "A complete reference for every section and key in the horus-os config.toml file, including types, defaults, and behavior."
---

## Overview

horus-os reads a single TOML file, `config.toml`, from its data directory on
startup. The file holds the installation's runtime settings: which provider to
use, where storage and the vault live, and which gated features (local models,
vector memory, web search, the shell tool) are turned on.

The data directory location is platform specific and can be overridden with the
`HORUS_OS_DATA_DIR` environment variable. See the
[configuration guide](/getting-started/configuration/) for how to find and
create the file, and the
[environment variables reference](/reference/environment-variables/) for the
runtime overrides that take precedence over file values.

```text
<data_dir>/config.toml
```

The schema is intentionally additive. Every key has a default, so a missing key
falls back to its built in value, and an empty `config.toml` behaves exactly
like the platform defaults. You can edit the file by hand or regenerate it with
`horus-os init --force`.

> [!NOTE]
> If `config.toml` is missing or fails to parse, horus-os silently falls back
> to the built in defaults rather than erroring. Run `horus-os doctor` to
> confirm the values that were actually loaded.

## How values are resolved

Several keys can also be supplied through environment variables, and a few
secrets are read only from the environment and never written to the file.

- Two settings have an environment override that wins over the file value:
  `HORUS_OS_PRICING_PATH` overrides the `[pricing]` `path` key, and
  `HORUS_OS_DATA_DIR` overrides the data directory itself.
- Secrets are never persisted to `config.toml`. Provider API keys
  (`ANTHROPIC_API_KEY`, `GEMINI_API_KEY`) and the web search provider key
  (`HORUS_OS_WEB_SEARCH_KEY`) are read from the environment at runtime.
- Sections for optional features are only written to the file when you diverge
  from the defaults. A freshly generated `config.toml` always contains
  `[providers]`, `[storage]`, `[notes]`, `[skills]`, and `[shell]`. The
  `[pricing]`, `[local]`, `[memory]`, `[tools.web_search]`, and `[research]`
  sections appear only once a value in them differs from its default.

## `[providers]`

Selects the default LLM provider and the model used for each provider. Provider
API keys are not configured here; they are read from environment variables.

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `default` | string | `anthropic` | The provider used when a run does not specify one. |
| `anthropic_model` | string | `claude-sonnet-4-6` | The Anthropic model identifier sent to the Anthropic SDK. |
| `gemini_model` | string | `gemini-2.5-flash` | The Google Gemini model identifier sent to the Gemini SDK. |

```toml
[providers]
default = "anthropic"
anthropic_model = "claude-sonnet-4-6"
gemini_model = "gemini-2.5-flash"
```

> [!IMPORTANT]
> Set `ANTHROPIC_API_KEY` and `GEMINI_API_KEY` in your environment, not in
> `config.toml`. See [environment variables](/reference/environment-variables/).

## `[storage]`

Controls where the authoritative SQLite database lives. This database holds the
audited storage, including the note write trail.

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `db_path` | path | `<data_dir>/horus.sqlite` | Filesystem path to the main SQLite database. A leading `~` is expanded. |

```toml
[storage]
db_path = "/Users/you/Library/Application Support/horus-os/horus.sqlite"
```

## `[notes]`

Controls where the vault lives. The vault is a directory of plain markdown
files. See [the vault](/concepts/the-vault/).

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `notes_dir` | path | `<data_dir>/notes` | Filesystem path to the vault directory. A leading `~` is expanded. |

```toml
[notes]
notes_dir = "/Users/you/Library/Application Support/horus-os/notes"
```

## `[skills]`

Controls where discoverable skill files live. This folder is the filesystem
source of truth for skills.

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `dir` | path | `<data_dir>/skills` | Filesystem path to the skills directory. A leading `~` is expanded. |

```toml
[skills]
dir = "/Users/you/Library/Application Support/horus-os/skills"
```

## `[pricing]`

Points to a custom pricing table. When unset, horus-os uses the pricing data
bundled with the package. This section is only written to the file when a path
is set.

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `path` | path | unset (bundled pricing) | Filesystem path to a pricing JSON file. A leading `~` is expanded. |

```toml
[pricing]
path = "/Users/you/horus-os/pricing.json"
```

> [!NOTE]
> The `HORUS_OS_PRICING_PATH` environment variable overrides this key. When
> both are set, the environment variable wins.

## `[local]`

Configures an OpenAI compatible local model provider, for example a local model
server on your machine. This section is only written to the file when you set a
model or change the base URL away from its default.

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `base_url` | string | `http://localhost:11434/v1` | Base URL of the OpenAI compatible local endpoint. The default is a loopback address. |
| `model` | string | `""` (unset) | The model name your local server serves. You must set this to use a local model. |
| `context_window` | integer | `4096` | Context window size, in tokens, the tool loop budgets against. |

```toml
[local]
base_url = "http://localhost:11434/v1"
model = "your-local-model"
context_window = 4096
```

> [!CAUTION]
> Keep `base_url` on a loopback address such as `localhost` or `127.0.0.1`.
> Using `0.0.0.0` would expose the local model API to your LAN.

## `[memory]`

Configures on device vector memory. This feature is OFF by default. You must
opt in and download an embedding model with `horus-os memory download-model`
before any embedding happens, and rebuild the index with
`horus-os memory reindex`. The local vector index lives in a separate
`<data_dir>/vectors.sqlite` cache file, not in the main database. This section
is only written to the file when you enable vector memory, change the embedding
model, or set a models directory.

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `vector_enabled` | boolean | `false` | Turns on hybrid vector memory. When `false`, the feature is fully off. |
| `embedding_model` | string | `BAAI/bge-small-en-v1.5` | The embedding model used to index and search vault content. |
| `models_dir` | path | unset (`<data_dir>/models`) | Directory that holds the downloaded embedding model. A leading `~` is expanded. |

```toml
[memory]
vector_enabled = true
embedding_model = "BAAI/bge-small-en-v1.5"
models_dir = "/Users/you/Library/Application Support/horus-os/models"
```

> [!NOTE]
> Vector memory requires the `local-memory` pip extra, which is not part of the
> `all` meta extra. Install it explicitly with `pip install 'horus-os[local-memory]'`.

## `[tools.web_search]`

Configures a bring your own web search provider. The `web_search` tool is
absent from the tool registry until a provider is configured (default deny).
The provider API key is read from the `HORUS_OS_WEB_SEARCH_KEY` environment
variable at registration time and is never written to `config.toml`. This
section is only written to the file when a provider is set.

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `provider` | string | unset | The search backend, one of `searxng`, `brave`, or `tavily`. |
| `base_url` | string | unset | The instance URL. Required for `searxng`; optional for the hosted providers. |

```toml
[tools.web_search]
provider = "searxng"
base_url = "https://your-searxng-instance.example.com"
```

## `[research]`

Sets hard caps for a Deep Research run. These are limits the research
coordinator can never silently exceed. This section is only written to the file
when a value diverges from its default. Neither key has an environment
override.

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `max_sources` | integer | `10` | Maximum number of distinct source URLs a research run will accept. |
| `max_iterations` | integer | `5` | Maximum number of iterations across the whole research delegation tree. |

```toml
[research]
max_sources = 10
max_iterations = 5
```

## `[shell]`

Configures the gated shell execution tool and its safety limits. The
`shell_exec` tool is absent from the registry until you opt in. This section is
always present in a generated `config.toml`.

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `enabled` | boolean | `false` | Turns on the shell execution tool. When `false`, the tool is absent from the registry (default deny). |
| `working_dir` | path | unset (`<data_dir>/shell`) | The safe root directory for shell commands. A leading `~` is expanded. |
| `timeout_seconds` | integer | `30` | Maximum wall clock time, in seconds, for a single shell command. |
| `output_cap_bytes` | integer | `1048576` | Maximum captured output size, in bytes, for a single command (1 MiB). |
| `type` | string | `auto` | The shell to run, one of `bash`, `powershell`, `cmd`, or `auto`. `auto` detects the shell at runtime. |
| `confirm` | boolean | `false` | When `true`, requires confirmation before a shell command runs. |

```toml
[shell]
enabled = false
timeout_seconds = 30
output_cap_bytes = 1048576
type = "auto"
confirm = false
```

> [!WARNING]
> Shell execution lets an agent run commands on your machine. Keep `enabled`
> set to `false` unless you understand the risk, and consider setting
> `confirm = true`. The `HORUS_OS_SHELL_ENABLED` environment variable is a
> runtime only gate that is read at registry build time and is never written to
> `config.toml`, so toggling it does not rewrite your file.

## Full example

A complete `config.toml` with every section present looks like this. In
practice the optional feature sections are only written once you diverge from
their defaults.

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
model = "your-local-model"
context_window = 4096

[memory]
vector_enabled = true
embedding_model = "BAAI/bge-small-en-v1.5"

[tools.web_search]
provider = "searxng"
base_url = "https://your-searxng-instance.example.com"

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

## See also

- [Configuration guide](/getting-started/configuration/)
- [Environment variables](/reference/environment-variables/)
- [CLI reference](/reference/cli-reference/)
