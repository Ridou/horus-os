# horus-os

[![CI](https://github.com/Ridou/horus-os/actions/workflows/ci.yml/badge.svg)](https://github.com/Ridou/horus-os/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org)
[![Status](https://img.shields.io/badge/status-pre--alpha-orange)](ROADMAP.md)

An open-source, self-hosted autonomous AI command center.

`horus-os` lets one person run a personal team of AI agents from a single workstation. Agents take instructions through a CLI or a local web chat, execute tasks against a persistent knowledge base, and surface results in a local dashboard. The whole stack runs on the user's own hardware. AI calls are billed to the user's own API keys.

## Status

Pre-alpha. No releases yet. See `ROADMAP.md` for the v0.1 plan.

## Quickstart (development)

```
git clone https://github.com/Ridou/horus-os.git
cd horus-os
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e '.[dev]'
pytest -v
horus-os --version
```

The runtime is in active development. Today the CLI prints `--version` and `--help` and that is intentionally all. The agent runtime, persistence layer, tool registry, memory layer, web chat, and setup wizard land across phases 02 to 09 (see `ROADMAP.md`).

## Documents

- `PROJECT.md`, project intent, core values, what is in and out of scope
- `ROADMAP.md`, v0.1 milestone and 11 phases
- `ARCHITECTURE.md`, technical shape (subject to revision per phase)
- `CONTRIBUTING.md`, how to engage during the pre-alpha gate
- `CODE_OF_CONDUCT.md`, Contributor Covenant 2.1

## License

Apache 2.0. See `LICENSE`.
