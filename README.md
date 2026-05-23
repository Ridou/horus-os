# horus-os

[![CI](https://github.com/Ridou/horus-os/actions/workflows/ci.yml/badge.svg)](https://github.com/Ridou/horus-os/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org)
[![Release](https://img.shields.io/badge/release-v0.1.0-blue.svg)](CHANGELOG.md)

An open-source, self-hosted autonomous AI command center.

`horus-os` lets one person run a personal team of AI agents from a single workstation. Agents take instructions through a CLI or a local web chat, execute tasks against a persistent knowledge base, and surface results in a local dashboard. The whole stack runs on the user's own hardware. AI calls are billed to the user's own API keys.

## Status

Alpha, v0.1.0 (2026-05-23). See `CHANGELOG.md` for what's in this release and `ROADMAP.md` for what's next.

## Quickstart

```
git clone https://github.com/Ridou/horus-os.git
cd horus-os
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install '.[all]'

# Initialize, then walk through API key onboarding
horus-os init --interactive

# Or initialize silently and set env vars yourself
horus-os init
export ANTHROPIC_API_KEY=sk-ant-...   # and/or GEMINI_API_KEY

# Ask the agent something. Default tools include reading and writing
# your notes folder, plus reading any file under it. Tokens stream
# to stdout as they arrive; pass --no-stream for the v0.1 behavior.
horus-os run "Summarize the notes in my notes directory."

# Drive the agent through a named profile (the `default` profile is
# bootstrapped on init; create more with `horus-os agents create`).
horus-os agents list
horus-os run --agent default "Summarize today's notes."

# Browse traces or open the local dashboard
horus-os traces
horus-os serve         # http://127.0.0.1:8765
```

## What's included

- **Two providers, your keys.** Anthropic Claude and Google Gemini, called via the official SDKs. No abstraction layer.
- **Tool registry.** Built-in `read_file`, plus six memory tools that read and write a markdown notes folder of your choice.
- **SQLite persistence.** Every agent run produces a trace. Every memory write lands in an audit table.
- **Local web dashboard.** Single-page chat, traces explorer, writes audit view. No npm, no Node, no build step.
- **CLI surface.** `init`, `run`, `traces`, `serve` subcommands. Tested on macOS, Ubuntu, and Windows.
- **Setup wizard.** `horus-os init --interactive` validates your API keys against the live providers before saving anything.

## What is new in v0.2

The active milestone ships multi-agent orchestration, live streaming
responses, and the third-party adapter plugin contract. Highlights:
named agent profiles in SQLite, a `delegate_to_agent` tool, a
`run_agent_stream` async generator, streaming output on the CLI and
dashboard, an `Adapter` Protocol with entry-point discovery, and a
reference HTTP webhook adapter.

- Migration guide: `docs/MIGRATION-v0.1-to-v0.2.md`
- Runnable examples: `examples/`
- v0.2 milestone detail: `ROADMAP.md`

## Documents

- `CHANGELOG.md`, release notes
- `PROJECT.md`, project intent, core values, what is in and out of scope
- `ROADMAP.md`, current milestone and what comes next
- `ARCHITECTURE.md`, technical shape
- `docs/MIGRATION-v0.1-to-v0.2.md`, upgrade notes for v0.1 users
- `examples/`, runnable scripts for multi-agent, streaming, and custom adapters
- `CONTRIBUTING.md`, dev setup, workflow, and code style
- `SECURITY.md`, how to report vulnerabilities
- `CODE_OF_CONDUCT.md`, Contributor Covenant 2.1

## Contributing

Issues and pull requests are welcome. Start with `CONTRIBUTING.md` for
dev setup and the workflow, and `PROJECT.md` for scope. New
contributors should look for the `good first issue` and `help wanted`
labels on the [issues page](https://github.com/Ridou/horus-os/issues).

## License

Apache 2.0. See `LICENSE`.
