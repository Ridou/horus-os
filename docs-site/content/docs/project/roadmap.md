---
title: "Roadmap"
description: "Where horus-os is right now, what has shipped from v0.1 to v0.8, and what comes next."
---

## Current status

The latest shipped release is **v0.8.0** ("Local-first and Autonomous
Research"), tagged on 2026-06-02. The runtime is Python 3.11+, the
dashboard is a static-exported Next.js app bundled into the wheel, and
persistence is a single SQLite file at database **schema version 13**.

horus-os is in active solo development. Outside pull requests are not
being merged yet, and issue claim comments are not honored yet. The
most valuable outside input right now is real-use feedback: run
horus-os against a real workload, then open a GitHub Discussion about
what worked and what did not. For the full collaboration policy, read
the [security policy](/project/security-policy/) and
[contributing guide](/project/contributing/).

> [!NOTE]
> Planning detail lives in the repository's `.planning/` directory and
> `ROADMAP.md`. This page summarizes the public-facing status. For the
> exact contents of each release, read the
> [changelog](/reference/changelog/) and the
> [GitHub Releases page](https://github.com/Ridou/horus-os/releases).

## Milestone timeline

Each milestone is a set of phases that ships as one tagged release. A
milestone is **shipped** when it is tagged and published on the
Releases page.

| Milestone | Scope | State | Tag | Date |
|-----------|-------|-------|-----|------|
| v0.1 Foundation | Single-agent runtime, two providers, CLI, dashboard, three-OS install gate | Shipped | `v0.1.0` | 2026-05-23 |
| v0.2 Multi-Agent + Streaming | Named agent profiles, `delegate_to_agent`, provider streaming, adapter plugin contract | Shipped | `v0.2.0` | 2026-05-23 |
| v0.3 Adapter Ecosystem | Discord, Slack, Email, and Calendar adapters, lifecycle hooks, dashboard adapters view | Shipped | `v0.3.0` | 2026-05-24 |
| v0.4 Observability | Cost, latency, and tool-reliability tracking, observability dashboard tab, opt-in OpenTelemetry exporter, `horus-os usage` | Shipped | `v0.4.0` | 2026-05-26 |
| v0.5 Plugin System | Third-party tools and adapters from a `horus-plugin.toml` manifest, default-deny capability grants, two-phase installer | Shipped | `v0.5.0` | 2026-05-27 |
| v0.6 Contribution Gate | Supply-chain hardening and contributor readiness work. Folded into the contribution gate, never tagged as its own release. | Folded in | (none) | n/a |
| v0.7 Command Center | Bundled Next.js dashboard, Setup-and-Verify integrations surface, Discord control bot, Supabase sync, cron scheduler, opt-in Vercel deploy | Shipped | `v0.7.0` | 2026-06-02 |
| v0.8 Local-first + Autonomous Research | Local LLM provider, on-device vector memory, MCP client, web access, vision and PDF, Deep Research, skills, gated shell, all opt-in | Shipped | `v0.8.0` | 2026-06-02 |

> [!NOTE]
> v0.6 (Contribution Gate) was never published as its own tag. Its
> supply-chain and contributor-readiness work landed without a release,
> so `v0.7.0` follows `v0.5.0` directly in the tag history.

## What has shipped

### v0.8 Local-first and Autonomous Research

The local-first milestone. A bare `pip install 'horus-os'` still starts
with only an LLM key and activates none of the new features; each
capability lives behind its own optional extra so you install exactly
what you turn on.

- **Local LLM provider** (extra: `local-llm`). Point horus-os at any
  OpenAI-compatible local server (Ollama, llama.cpp, LM Studio, vLLM,
  OpenRouter) through a `base_url` override.
- **On-device vector memory** (extra: `local-memory`, off by default).
  Local ONNX text embeddings and a KNN index in a rebuildable
  `vectors.sqlite` cache, with zero network egress on memory writes.
  See [the vault](/concepts/the-vault/).
- **MCP client** (extra: `mcp`). Connect to allowlisted Model Context
  Protocol servers over stdio, SSE, and streamable-http. See the
  [MCP integration](/integrations/mcp/).
- **Web access** (extra: `web`). A bring-your-own `web_search` tool and
  an SSRF-guarded web fetch. See [web access](/integrations/web-access/).
- **Vision and PDF analysis** (extras: `vision`, `pdf`). An
  `analyze_file` tool scoped to the data directory's `uploads/` folder.
- **Deep Research** (flagship). A coordinator workflow that delegates
  to a Researcher sub-agent and synthesizes a cited Markdown report.
  See [autonomous research](/guides/autonomous-research/).
- **Skills system.** Reusable, TOML-defined agent behaviors discovered
  from the data directory's `skills/` folder.
- **Gated shell execution.** A `shell_exec` tool behind a double lock
  (`HORUS_OS_SHELL_ENABLED=true` plus an explicit `allowed_tools`
  grant), audited to SQLite.

Schema moved from 12 to 13 (additive, idempotent). The `local-memory`
extra is intentionally excluded from `[all]`.

### v0.7 Command Center

Turned horus-os into a polished command center on first run.

- Bundled Next.js dashboard with a design system and a locked sidebar.
  See the [dashboard guide](/guides/dashboard/).
- Setup-and-Verify integrations surface with per-integration
  walkthroughs and a key-write and verification flow.
- Opt-in Discord control bot, opt-in Supabase sync loop, a cron
  scheduler with an always-on service, and an opt-in Vercel deploy path.
  See [scheduling agents](/guides/scheduling-agents/) and
  [running as a service](/guides/running-as-a-service/).
- Four new opt-in extras: `discord`, `supabase`, `vercel`, `github`,
  all excluded from `[all]`. Schema advanced to v12.

### v0.5 Plugin System

Third-party tools and adapters loadable from a `horus-plugin.toml`
manifest, with default-deny capability grants, a two-phase installer,
a `/plugins` dashboard tab, and per-plugin observability. See
[plugins](/extending/plugins/) and
[plugin security](/extending/plugin-security/). Schema v5 to v6.

### v0.4 Observability

Cost, latency, and tool-reliability tracking per agent run, an
`/observability` dashboard tab, the `horus-os usage` CLI, and an opt-in
OpenTelemetry exporter behind the `otel` extra. See
[observability](/operations/observability/) and
[OpenTelemetry](/operations/opentelemetry/).

### v0.3 Adapter Ecosystem

Adapter lifecycle hooks plus four first-party adapters: Discord, Slack,
Email (IMAP and SMTP), and Calendar (Google), with an `AdapterRegistry`
and a dashboard adapters tab. See the
[integrations overview](/integrations/overview/).

### v0.2 Multi-Agent + Streaming

Named agent profiles in SQLite with parent and child trace links, the
`delegate_to_agent` tool, streaming responses via provider streaming
APIs, and the adapter plugin contract. See the
[agent team](/concepts/agent-team/).

### v0.1 Foundation

The first public alpha: a single-agent runtime, two providers
(Anthropic and Gemini), one tool, persistent SQLite, and a CLI plus
local dashboard, gated behind a three-OS install check.

## What comes next

Milestone scope beyond v0.8 is not yet committed. The project opens for
outside contributions once an internal supply-chain readiness gate is
met. Until then, the highest-value contribution is real-use feedback in
GitHub Discussions, which shapes the roadmap.

## Anti-goals

These are out of scope and stay out of scope, even after contributions
open:

- A hosted SaaS offering of horus-os.
- Coupling to any single cloud provider beyond your chosen LLM API.
- Features that require a paid third-party account beyond optional
  LLM API keys.
- Multi-tenant deployment patterns.

## See also

- [Changelog](/reference/changelog/)
- [Introduction](/getting-started/introduction/)
- [Architecture](/concepts/architecture/)
- [Contributing](/project/contributing/)
