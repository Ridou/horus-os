---
title: "Changelog"
description: "Condensed release history for horus-os, from the v0.1 foundation through v0.8 local-first and autonomous research."
---

## Overview

This page summarizes the headline features of each shipped horus-os release. It is a curated digest, not the complete record. For the full per-release list of additions, changes, fixes, and migrations, read the canonical changelog and the GitHub Releases page.

- Full changelog: [CHANGELOG.md on GitHub](https://github.com/Ridou/horus-os/blob/main/CHANGELOG.md)
- Releases: [github.com/Ridou/horus-os/releases](https://github.com/Ridou/horus-os/releases)

The changelog follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> [!NOTE]
> Every schema bump in horus-os history has been additive and idempotent, and runs automatically on first startup after upgrade. The current database schema version is 13. See [Migrations](/reference/migrations/) for details.

## Unreleased

Landed on `main` after the v0.8.0 tag, shipping in the next tagged cut:

- **Streaming dashboard chat.** A first-class chat surface that streams tokens live as the team works, over the existing `POST /api/chat/stream` SSE path, with tool-call and done frames surfaced inline.
- **Agent store and custom-agent builder.** Browse and install featured agent bundles (Atlas, Vitriol, Sol) or build your own with no code. Installs are additive and never overwrite an existing profile.
- **Voice and reservations adapter** (`[voice]` extra). An opt-in Twilio `VoiceAdapter` for outbound calls and phone reservations, with the SDK imported lazily so a bare install never pulls it. See [the voice adapter](/integrations/voice/).

## v0.8.0 (2026-06-03) Local-first and Autonomous Research

The eighth alpha adds a full local-first capability layer plus a flagship Deep Research workflow, and every piece is opt-in. A bare `pip install horus-os` still starts with only an LLM key and activates none of the new features; each capability lives behind its own optional extra, so you install exactly what you turn on.

Highlights:

- **Local LLM provider** (`[local-llm]` extra). Point horus-os at any OpenAI-compatible local server (Ollama, llama.cpp, LM Studio, vLLM, OpenRouter) through a single `base_url` override.
- **On-device vector memory** (`[local-memory]` extra). Local ONNX text embeddings and a `sqlite-vec` KNN index alongside the markdown vault, OFF by default. Run `horus-os memory download-model` before any embedding happens. This extra is intentionally excluded from `[all]`.
- **MCP client** (`[mcp]` extra). Connect to explicitly allowlisted Model Context Protocol servers over stdio, SSE, and streamable-http, activated only through a `<data_dir>/mcp.toml` trust gate. See [MCP](/integrations/mcp/).
- **Web access** (`[web]` extra). A bring-your-own `web_search` tool and an SSRF-guarded web fetch. See [Web access](/integrations/web-access/).
- **Vision and PDF analysis** (`[pdf]` and `[vision]` extras). An `analyze_file` tool scoped to `<data_dir>/uploads/`.
- **Deep Research** (flagship). A coordinator workflow that delegates to a Researcher sub-agent and synthesizes a cited Markdown report, with hard source and iteration caps. See [Autonomous research](/guides/autonomous-research/).
- **Skills system.** Reusable, TOML-defined agent behaviors discovered from `<data_dir>/skills/` and composed via the `use_skill` tool.
- **Gated shell execution.** A `shell_exec` tool behind a double lock (`HORUS_OS_SHELL_ENABLED=true` plus an explicit `allowed_tools` entry) with an audited working directory.
- **`[research]` convenience meta-extra.** Installs the full v0.8 infrastructure layer (`local-llm`, `local-memory`, `mcp`, `web`, `pdf`, `vision`) in one command.
- **Schema 12 to 13.** Two additive tables (`skills`, `shell_invocations`).

## v0.7.0 (2026-06-03) Command Center

The Command Center milestone turns horus-os from a single-page vanilla-JS dashboard into a polished Next.js command center. (v0.6 was never tagged, so 0.7.0 follows 0.5.0 in the tag history.) Every v0.5 surface keeps working, a no-extras install still runs the full local runtime, and the schema upgrade is additive.

Highlights:

- **Design system and layout shell.** A Tailwind v4 token source, Radix-backed primitives, and an `AppShell` with a ten-item sidebar.
- **Integrations surface.** A ten-card Integrations page with per-integration walkthroughs and a read-only `GET /api/integrations` route that never echoes secrets. See [Integrations overview](/integrations/overview/).
- **Key-write endpoint and verification engine.** A loopback-guarded key write plus a verify probe that writes `.env` with restrictive permissions and never echoes the key value.
- **Tier-1 dashboard pages.** A `/tasks` page, a `/team/[slug]` agent detail route, a guided tour, and idempotent seed content (a starter team and demo tasks). See the [Dashboard guide](/guides/dashboard/).
- **Discord control bot** (`[discord]` adapter). Create-only channel bootstrap, deny-by-default admin gating, slash commands, and a thread-dispatch flow. See [Discord](/integrations/discord/).
- **Supabase sync loop** (`[supabase]` extra). Pushes traces, agent profiles, and tasks through a background sync loop with local cursors and Row Level Security. See [Supabase](/integrations/supabase/).
- **Cron scheduler and always-on service.** A `SchedulerAdapter` that fires agent profiles on cron schedules, a `horus-os schedule` subcommand family, and a cross-platform `horus-os service` install path (systemd, launchd, NSSM). See [Scheduling agents](/guides/scheduling-agents/) and [Running as a service](/guides/running-as-a-service/).
- **Vercel deploy path and GitHub tool.** A `NEXT_PUBLIC_API_BASE` abstraction, an opt-in `[vercel]` deploy path, and an opt-in read-only `github_read` tool behind the `[github]` extra. See [Deploy to Vercel](/operations/deploy-to-vercel/) and [GitHub](/integrations/github/).
- **Schema 6 to 12.** Five new tables and three nullable columns, all additive.

## v0.5.0 (2026-05-27) Plugin system

The fifth alpha adds a third-party plugin system on top of the v0.4 observability substrate. Plugins are Python packages that ship a `horus-plugin.toml` manifest, contribute tools and/or adapters, and run with default-deny capability grants.

Highlights:

- **Plugin manifest contract.** A pydantic v2 schema with required and optional fields and a single `validate_manifest` entry point. See the [Manifest reference](/extending/manifest-reference/).
- **Two-phase installer.** `horus-os plugins install <spec>` downloads with `--no-deps`, refuses sdists by default, refuses `.pth`-shipping wheels and dependency-downgrading wheels, prompts for capability grants, then installs.
- **Default-deny capability grants.** A four-capability catalog (`filesystem.read`, `filesystem.write`, `net.outbound`, `secrets.read`) with an append-only audit log that survives uninstall. See [Plugin security](/extending/plugin-security/).
- **Bounded lifecycle.** A 2-second timeout wraps every plugin adapter's `start` and `stop` hooks.
- **`/plugins` dashboard tab** and a nine-subcommand `horus-os plugins` CLI surface.
- **Per-plugin observability.** Plugin attribution on every LLM call and tool invocation.
- **Reference plugin** under `examples/horus-os-example-plugin/` as a starting template. See the [Plugins guide](/extending/plugins/).
- **Schema 5 to 6.** Three new tables, two nullable columns, and one index.

## v0.4.0 (2026-05-26) Observability

The fourth alpha turns horus-os from "agents run" into "agents run and you know what they cost, what they took, and what broke." Local-first cost, latency, and tool-reliability instrumentation against a SQLite source of truth.

Highlights:

- **Observability capture pipeline.** An `ObservationBus` plus a SQLite persister that writes one row per LLM call and one per tool call.
- **Pricing table and cost annotation.** A bundled cache-aware pricing table; unknown models record NULL rather than a false zero. Override via `HORUS_OS_PRICING_PATH`.
- **`/observability` dashboard tab.** Cost by agent, latency p50/p95, and tool reliability, with a windowed selector and a pricing-staleness banner.
- **`horus-os usage` CLI subcommand.** Stdlib-only usage rollups in JSON, CSV, or table form.
- **OpenTelemetry exporter** (`[otel]` extra). Opt-in OTLP HTTP exporter, default-deny on body content, with a bounded shutdown. See [OpenTelemetry](/operations/opentelemetry/).
- **Cost-correctness fixes.** Per-iteration token undercount and silent $0 on streamed runs, both fixed. See [Traces and observability](/concepts/traces-and-observability/).
- **Schema 4 to 5.** Four nullable rollup columns on `traces` and two new child tables.

## v0.3.0 (2026-05-24) Adapter ecosystem

The third alpha takes the v0.2 adapter interface from one reference webhook to a real ecosystem: four first-class adapters on top of new lifecycle hooks and an adapter registry surfaced through both a JSON API and a Dashboard Adapters tab.

Highlights:

- **LifecycleAdapter protocol** with async `start` and `stop` hooks, tied into the FastAPI app lifespan.
- **AdapterRegistry** with per-adapter status tracking, surfaced at `GET /api/adapters` and through enable/disable toggle routes.
- **Discord, Slack, Email, and Calendar adapters.** Calendar is the first tool-providing adapter, registering calendar tools onto a shared `ToolRegistry`. See [Discord](/integrations/discord/), [Slack](/integrations/slack/), [Email](/integrations/email/), and [Calendar](/integrations/calendar/).
- **Dashboard Adapters tab** with color-coded status pills and per-adapter toggle controls.

## v0.2.0 (2026-05-23) Agent team

The second alpha moves from one agent answering questions to a personal team of agents that hand off to each other, with live streaming in the CLI and dashboard.

Highlights:

- **Agent profiles.** A persisted `agent_profiles` table with a bootstrapped `default` profile. See [The agent team](/concepts/agent-team/).
- **Multi-agent runtime.** A `delegate_to_agent` tool with a shared iteration budget across the delegation tree and concurrent parallel delegation.
- **Parent and child traces.** Coordinator-to-sub-agent trace linkage.
- **Streaming runtime.** Token streaming for both Anthropic and Gemini, in the CLI and the dashboard SSE chat surface.
- **CLI multi-agent surface.** A `horus-os agents` group and `horus-os run --agent <name>`.
- **Adapter contract.** The `horus_os.adapters` package and a reference `WebhookAdapter`. See [Writing an adapter](/extending/writing-an-adapter/).
- **Schema upgraded to version 4** automatically and idempotently.

## v0.1.0 (2026-05-23) Foundation

The first alpha. Install the package, run an agent through the CLI or local web chat, and read or write a markdown notes folder with a full SQLite audit trail.

Highlights:

- **Agent runtime** with sync and async paths and a multi-turn tool-execution loop.
- **Anthropic and Google Gemini providers** with a shared surface.
- **Tool registry** plus a built-in file-read tool with optional path sandboxing.
- **Markdown vault memory layer** with list, search, read, create, and append tools. See [The vault](/concepts/the-vault/).
- **SQLite persistence** with WAL mode and a reviewable audit trail for every note write.
- **CLI surface.** `horus-os init`, `init --interactive`, `traces`, `run`, and `serve`. See the [CLI guide](/guides/cli/).
- **Local web dashboard** served by FastAPI, plus a JSON API under `/api`.

## See also

- [Migrations](/reference/migrations/)
- [Configuration reference](/reference/configuration/)
- [CLI reference](/reference/cli-reference/)
- [Roadmap](/project/roadmap/)
