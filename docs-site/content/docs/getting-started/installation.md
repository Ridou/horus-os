---
title: "Installation"
description: "Install horus-os with pip, choose the optional extras you need, and verify the install with horus-os doctor."
---

horus-os is a Python package. It needs **Python 3.11 or newer** and runs on
macOS, Linux, and Windows.

## Install with pip

The fastest way to a working install is the `all` extra, which pulls both AI
providers, the dashboard, and the common integrations in one command:

```bash
pip install 'horus-os[all]'
```

A bare install (`pip install horus-os`) gives you the agent runtime and the CLI
with no provider SDK, no dashboard, and no integrations. You then add only the
extras you want, which keeps the dependency footprint small.

> [!TIP]
> Use a virtual environment so horus-os and its dependencies stay isolated from
> your system Python.
>
> ```bash
> python -m venv .venv
> source .venv/bin/activate   # on Windows: .venv\Scripts\activate
> pip install 'horus-os[all]'
> ```

## Choosing extras

Every optional feature ships as a pip extra so a bare install pulls nothing it
does not need. Combine them in one set of brackets, for example
`pip install 'horus-os[anthropic,dashboard,discord]'`.

| Extra | Adds |
|-------|------|
| `anthropic` | The Anthropic (Claude) provider SDK |
| `gemini` | The Google Gemini provider SDK |
| `local-llm` | An OpenAI-compatible client for a local model server (Ollama, llama.cpp, LM Studio, vLLM) |
| `dashboard` | The local web dashboard (FastAPI + Uvicorn) |
| `discord` | The Discord adapter and control bot |
| `slack` | The Slack adapter |
| `calendar` | The Google Calendar adapter |
| `supabase` | The optional Supabase sync loop |
| `vercel` | The Vercel deploy-status surface |
| `github` | The read-only GitHub tool |
| `mcp` | The Model Context Protocol client |
| `web` | Bring-your-own web fetch and search tools |
| `pdf`, `vision` | PDF text extraction and image input |
| `otel` | OpenTelemetry export |

Two meta-extras bundle common sets:

- **`all`** installs both providers, the dashboard, and the light cross-platform
  integrations. It is the recommended starting point.
- **`research`** installs the full local-first stack for Deep Research: the
  local LLM client, on-device vector memory, the MCP client, web access, PDF,
  and vision.

```bash
# Everything for Deep Research and the local-first stack.
pip install 'horus-os[research]'
```

> [!NOTE]
> The on-device vector memory extra (`local-memory`) is **not** included in
> `all`, because its native dependencies need platform-specific wheels. Install
> it explicitly with `pip install 'horus-os[local-memory]'` or as part of the
> `research` extra. See [The vault](/concepts/the-vault/) for how vector memory
> works.

## Verify the install

Confirm the CLI is on your path and check the version:

```bash
horus-os --version
```

After you initialize an installation (see the [Quickstart](/getting-started/quickstart/)),
`horus-os doctor` reports the available subsystem checks and your skills folder:

```bash
horus-os doctor
```

Pass a flag to run a specific check, for example `horus-os doctor --local`,
`--memory`, `--mcp`, `--shell`, `--supabase`, or `--service`. See the [CLI
reference](/reference/cli-reference/) for the full list.

> [!NOTE]
> `horus-os doctor` checks integrations and local subsystems, not your cloud
> provider keys. The simplest way to confirm an Anthropic or Gemini key works is
> to run a prompt with `horus-os run`.

## Where horus-os stores its data

horus-os keeps everything for one installation under a single **data
directory**. The default location is platform-specific:

| Platform | Default data directory |
|----------|------------------------|
| macOS | `~/Library/Application Support/horus-os` |
| Linux | `$XDG_DATA_HOME/horus-os`, or `~/.local/share/horus-os` |
| Windows | `%APPDATA%\horus-os` |

Override it for any command by setting `HORUS_OS_DATA_DIR`:

```bash
export HORUS_OS_DATA_DIR="$HOME/horus-data"
```

Inside the data directory you will find `config.toml` (settings),
`horus.sqlite` (the database and audit log), `notes/` (your vault), and
`skills/`. See the [Configuration](/getting-started/configuration/) page for the
full layout and every setting.

## Next steps

- [Quickstart](/getting-started/quickstart/) initializes an installation and
  runs your first prompt.
- [Configuration](/getting-started/configuration/) covers provider keys,
  `config.toml`, and environment variables.
