# Migration from v0.7 to v0.8

## TL;DR

v0.8 is purely additive and opt-in. Every v0.7 surface continues to
work byte-identical: the dashboard, the starter team, the agent
runtime, the two providers, the adapters, the plugin system, the
observability stack, and the CLI. No removals, no deprecations, no
breaking changes.

What lights up in v0.8 is a full local-first capability layer plus a
flagship Deep Research workflow, and every piece is gated behind an
optional extra or a config flag. A bare `pip install --upgrade
horus-os` changes nothing about how the system runs: it still starts
with only an LLM key and activates none of the new features. You turn
each capability on by installing its extra and setting its config or
env flag. The one schema change, an additive SCHEMA_VERSION 12 to 13
migration for the new skills and shell_invocations tables, runs
automatically on first start and needs no action from you.

## What is new

### Local LLM provider

The optional `[local-llm]` extra adds an OpenAI-compatible provider
that points at any local server (Ollama, llama.cpp, LM Studio, vLLM,
OpenRouter) through a single `base_url` override. The provider is
constructed lazily, so a bare install never imports the `openai` SDK.
Set `HORUS_OS_LOCAL_BASE_URL` (or `base_url` under `[local]` in
`<data_dir>/config.toml`) to wire the endpoint, set the model name via
`model` under the same `[local]` table, and optionally set
`HORUS_OS_LOCAL_API_KEY` for servers that require one. Then run
`horus-os doctor --local` to validate the base URL
(a wildcard bind is rejected so the model API is not exposed to the
LAN) and live-probe the endpoint. No key ever prints.

### On-device vector memory

The optional `[local-memory]` extra adds local ONNX text embeddings
(`fastembed`) and a `sqlite-vec` KNN index alongside the markdown
vault, with zero network egress on memory writes. The feature is OFF
by default. To use it, install the extra, enable it in config, and run
`horus-os memory download-model` once to fetch the small embedding
model. The vector index lives in its own rebuildable `vectors.sqlite`
cache, not in the authoritative database, so it triggers no schema
bump. `horus-os doctor --memory` reports model and index status
without ever downloading.

Intel macOS note: the `onnxruntime` pin is `>=1.17.0,<1.24.0` so an
Intel-macOS wheel is available (universal2 through 1.22.x, explicit
x86_64 in 1.23.x; 1.24.1+ ships arm64 only). This is why
`[local-memory]` is intentionally NOT part
of the `[all]` extra: it keeps a fresh `.[all]` install cross-OS
clean, and the extra gets its own dedicated install-smoke variant in
CI.

### MCP client

The optional `[mcp]` extra adds the official Anthropic Model Context
Protocol client. horus-os connects to explicitly-allowlisted MCP
servers over stdio, SSE, and streamable-http transports, and each
discovered tool registers under a `mcp:{server}:{tool}` namespace.
Servers activate ONLY through `<data_dir>/mcp.toml`: an absent or
empty file registers zero MCP tools and triggers no network probe.
`horus-os doctor --mcp` reports the configured allowlist.

### Web access

The optional `[web]` extra adds a bring-your-own `web_search` tool
(SearXNG, Brave, or Tavily) and an SSRF-guarded web fetch that
extracts the main article text from noisy HTML. The `web_search` tool
is ABSENT from the default registry until a provider is configured in
`[tools.web_search]`. The provider key is read from
`HORUS_OS_WEB_SEARCH_KEY` and is never written to `config.toml`.

### Vision and PDF analysis

The optional `[pdf]` extra adds pure-Python PDF text extraction, and
the `[vision]` extra adds Pillow for image resize and format
conversion before a vision call. The `analyze_file` tool is scoped to
`<data_dir>/uploads/`, so it cannot read arbitrary local files. Vision
reuses the existing Anthropic and Gemini multimodal message support;
there is no new provider dependency.

### Deep Research

Deep Research is a native coordinator workflow, not a new dependency.
It receives a research question, delegates to a Researcher sub-agent
with the web tools, and synthesizes a structured Markdown report with
citations. It runs on the existing multi-agent delegation runtime with
hard caps (`research_max_sources`, `research_max_iterations`) the
coordinator can never silently exceed. Enabling it requires the
`[web]` extra and a configured search provider.

### Skills system

Skills are reusable, TOML-defined agent behaviors discovered from
`<data_dir>/skills/` and composed onto an agent at runtime via the
`use_skill` tool. Skills use stdlib `tomllib`, so they add no
dependency. `use_skill` registers ONLY when a skill exists, so an
install with no skills behaves exactly as before. Code-bearing skills
are denied by default, and a skill whose name collides with a builtin
or plugin tool is refused.

### Gated shell execution

The `shell_exec` tool is gated by a double lock: it registers ONLY
when `HORUS_OS_SHELL_ENABLED=true` AND the agent profile explicitly
lists `shell_exec` in its `allowed_tools`. An unrestricted profile
never gains shell. Every run is confined to a safe working directory,
capped by an output byte limit and a timeout, and written to a SQLite
audit row. `horus-os doctor --shell` reports the gate state and the
safe working directory without spawning a process.

## New optional extras

v0.8 adds seven optional extras. None of them is installed by a bare
`pip install horus-os`, and none activates a feature on install:
installing an extra only makes its dependency available, the feature
still has to be configured or flagged on. Install only what you turn
on.

| Extra | pip install | Pins |
|-------|-------------|------|
| `local-llm` | `pip install 'horus-os[local-llm]'` | `openai>=2.40.0` |
| `local-memory` | `pip install 'horus-os[local-memory]'` | `fastembed>=0.8.0`, `onnxruntime>=1.17.0,<1.24.0`, `sqlite-vec>=0.1.9` |
| `mcp` | `pip install 'horus-os[mcp]'` | `mcp>=1.27.2` |
| `web` | `pip install 'horus-os[web]'` | `readability-lxml>=0.8.4.1`, `httpx>=0.27.0` |
| `pdf` | `pip install 'horus-os[pdf]'` | `pypdf>=6.12.2` |
| `vision` | `pip install 'horus-os[vision]'` | `Pillow>=10.0` |
| `research` | `pip install 'horus-os[research]'` | meta-extra: pulls `local-llm`, `local-memory`, `mcp`, `web`, `pdf`, `vision` |

The `[research]` convenience meta-extra installs the full v0.8
infrastructure layer in one command. It is self-referential, so it
inherits every pin above, including the `local-memory` onnxruntime
Intel macOS pin.

The `[local-memory]` extra is deliberately NOT folded into the `[all]`
extra. Its `onnxruntime` wheels need the Intel-macOS pin and are not
universally available, so `[all]` stays cross-OS clean and
`[local-memory]` is an explicit opt-in exercised by its own
install-smoke variant. The light v0.8 extras (`local-llm`, `mcp`,
`web`, `pdf`, `vision`) ARE part of `[all]`.

## Schema migration v12 to v13

The skills system and the gated-shell audit log each add one new table
(`skills` and `shell_invocations`), so SCHEMA_VERSION moves from 12 (the
version v0.7 shipped, with its `schedules` cron table) to 13. The
migration is additive and idempotent: it adds the two new tables and
changes nothing about existing rows, including the v0.7 `schedules`
table. It runs automatically on the first `horus-os` start after the
upgrade. v0.7 (v12) databases load cleanly under v13 and read back
byte-identical, the same property proven by the v12-to-v13 migration
test (MIG-07). No user action is required, and there is nothing to back
up beyond your normal habits.

There is no downgrade path back to v0.7 once the v12 to v13 migration
has run. The new tables remain in the database forever; v0.7 code does
not read them, so the file grows slightly but reads stay identical. If
you must stay on v0.7, do not run a v0.8 binary against a v0.7
database; keep a separate data directory for the upgrade.

## Upgrade steps

1. Upgrade the package:

   ```
   pip install --upgrade horus-os
   ```

2. Start horus-os once. The v12 to v13 schema migration runs
   automatically on first start. No flags, no manual SQL.

   ```
   horus-os serve
   ```

3. Optionally add the extras for the capabilities you want, for
   example the full local-first stack in one command:

   ```
   pip install 'horus-os[research]'
   ```

   or a single capability:

   ```
   pip install 'horus-os[local-llm]'
   ```

4. If and only if you enable vector memory, download the embedding
   model once (this is the single step that touches the network, and
   only when you opt in):

   ```
   horus-os memory download-model
   ```

## Breaking change scan

There are no breaking changes to v0.7 features. Every public API,
every persisted schema column, every CLI flag, every dashboard tab,
every adapter, and every plugin contract from v0.7 continues to work
byte-identical under v0.8.

## Verification

The migration ran successfully when the SQLite `schema_version` table
reports 13:

```
sqlite3 <data_dir>/horus.sqlite "SELECT version FROM schema_version"
```

`<data_dir>` defaults to `~/Library/Application Support/horus-os` on
macOS, `%APPDATA%\horus-os` on Windows, and `~/.local/share/horus-os`
on Linux, unless overridden via `HORUS_OS_DATA_DIR`.

Expected output: `13`. Later releases bump this number as they add
additive tables, so a value above `13` is also healthy. If the value
is `12`, the v0.8 runtime did not finish its startup migration. Check
the server logs for the migration error and re-run `horus-os serve`.

## See also

- `CHANGELOG.md` `[0.8.0]` section: the complete v0.8 change log.
- `docs/MCP.md`: the MCP client schema, the three transports, and the
  threat model.
- `docs/MIGRATION-v0.4-to-v0.5.md`: the prior migration guide this one
  mirrors.
