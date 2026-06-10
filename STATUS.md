# Project Status

This page is the canonical "where is horus-os right now" view. It
exists so people following the project from the outside have a
single URL to check, and so the "is this accepting contributions
yet?" question has a clear, dated answer.

For the deep planning detail, read `ROADMAP.md` and `.planning/`.
For release contents, read `CHANGELOG.md`.

**Last updated:** 2026-06-10.

## TL;DR

- horus-os is **open for outside contributions** as of 2026-06-10.
  The supply-chain readiness gate (the v0.6 Contribution Gate
  milestone) shipped, and the contribution flow in `CONTRIBUTING.md`
  is live.
- v0.1 through v0.8 have shipped. v0.6 (Contribution Gate) was never
  tagged; v0.7 and v0.8 shipped on 2026-06-03. See `CHANGELOG.md` for
  what is in each release.
- Since the v0.8.0 tag, more product surfaces (a streaming dashboard
  chat, an agent store, an opt-in Twilio voice adapter, a 10-step
  onboarding tour, and an agent Standup view) have landed on `main`
  and sit unreleased in the changelog `[Unreleased]` section. They
  ship in the next tagged cut. The next planned milestone is
  **v0.9, Autonomy and Control** (planned, not yet committed to phases).
- You can now: claim issues labeled `good-first-issue` or
  `help-wanted` (comment to claim, the maintainer assigns), open PRs
  from a fork against assigned issues, and propose features through
  Discussions.
- Still the most valuable input: file bug reports, open Discussions,
  star or watch the repo, and run horus-os locally and report what
  worked.

## Milestone timeline

| Milestone | Scope | State | Tag | Date |
|-----------|-------|-------|-----|------|
| v0.1 Foundation | Single-agent runtime, two providers, CLI, dashboard, three-OS install gate | **SHIPPED** | `v0.1.0` | 2026-05-23 |
| v0.2 Multi-Agent + Streaming | Named agent profiles, `delegate_to_agent`, provider streaming, adapter plugin contract | **SHIPPED** | `v0.2.0` | 2026-05-23 |
| v0.3 Adapter Ecosystem | Discord, Slack, Email, Calendar adapters, lifecycle hooks, dashboard adapters view | **SHIPPED** | `v0.3.0` | 2026-05-24 |
| v0.4 Observability | Cost tracking, latency, tool reliability, observability dashboard tab, opt-in OTel exporter, `horus-os usage` CLI | **SHIPPED** | `v0.4.0` | 2026-05-26 |
| v0.5 Plugin System | Third-party tools and adapters loadable from a `horus-plugin.toml` manifest. Default-deny capability grants, two-phase installer, `/plugins` dashboard tab, per-plugin observability, reference plugin. | **SHIPPED** | `v0.5.0` | 2026-05-27 |
| v0.6 Contribution Gate | Supply-chain hardening: keyless sigstore signing, CycloneDX SBOMs, pip-audit, SHA-pinned actions, refreshed contributor docs, an extended release gate. The readiness gate that opened outside contributions on 2026-06-10. | **DELIVERED** | never tagged (skipped; v0.7.0 follows v0.5.0) | 2026-06-02 |
| v0.7 Command Center | A bundled Next.js dashboard, a seeded five-agent starter team with SOUL personas, an example vault, eye-of-Horus branding, a unified marketing and demo site, a Discord control bot, a Supabase sync loop, a cron scheduler with an always-on service, and a Vercel deploy path. | **SHIPPED** | `v0.7.0` | 2026-06-03 |
| v0.8 Local-first and Autonomous Research | Local LLM provider, on-device vector memory via `sqlite-vec`, MCP client, web access and search, vision and PDF analysis, a Deep Research flagship workflow, a skills system, gated shell execution, the `[research]` meta-extra. (A streaming dashboard chat, an agent store, and an opt-in Twilio voice adapter landed on `main` after the tag and are unreleased.) | **SHIPPED** | `v0.8.0` | 2026-06-03 |
| v0.9 Autonomy and Control | Event and lifecycle-hook substrate, monetary budgets that pause on breach, risk-tiered approvals, secrets redaction, priority execution lanes, watch rules, controlled overnight autonomy, and a minimal supervision surface (approvals queue, unified inbox, run-liveness watchdog). | **PLANNED** | (none) | program drafted 2026-06-03 |

State legend: **SHIPPED** means tagged and on the Releases page.
**DELIVERED** means the milestone's scope landed on `main` but no tag
was cut. **IN DEVELOPMENT** means the roadmap is committed and phases
are executing, but it is not tagged yet. **PLANNED** means a
program-level roadmap exists but the milestone is not yet broken into
committed phases. **NOT PLANNED** means scope is sketched with no
commitment and no schedule.

## Recently shipped

**v0.8 Local-first and Autonomous Research (shipped 2026-06-03)**
introduces a full local-first capability layer plus a flagship Deep
Research workflow. All pieces are opt-in: a bare `pip install horus-os`
still starts with only an LLM key and activates none of the new
features. Each capability lives behind its own optional extra.

- Local LLM provider (Ollama, llama.cpp, LM Studio, vLLM, OpenRouter)
  via the `[local-llm]` extra and a single `base_url` override.
- On-device ONNX vector embeddings and a `sqlite-vec` KNN index via
  the `[local-memory]` extra, with zero network egress on memory
  writes; off by default until you run `horus-os memory download-model`.
- MCP client via the `[mcp]` extra; servers activate only through
  `<data_dir>/mcp.toml`.
- Web search (bring-your-own: SearXNG, Brave, Tavily) and an
  SSRF-guarded fetch via the `[web]` extra.
- Vision (image resize and format conversion) via the `[vision]`
  extra and pure-Python PDF text extraction via the `[pdf]` extra.
- Deep Research coordinator workflow: takes a question, delegates to
  a Researcher sub-agent with the web tools, and synthesizes a
  structured Markdown report with citations.
- Skills system: reusable, TOML-defined agent behaviors discovered
  from `<data_dir>/skills/`.
- Gated shell execution: `shell_exec` registers only when both
  `HORUS_OS_SHELL_ENABLED=true` AND the agent profile explicitly
  lists it in `allowed_tools`.
- `[research]` meta-extra: installs the full local-first stack at once.

Several product surfaces on top of the v0.8 core landed on `main`
after the v0.8.0 tag and currently sit in the changelog `[Unreleased]`
section, so they are not part of v0.8.0 itself and ship in the next
tagged cut: a streaming chat surface in the dashboard that streams
tokens live as the team works; an agent store with featured bundles
(Atlas, Vitriol, Sol) and a custom-agent builder; an optional Twilio
voice and reservations adapter behind the `[voice]` extra; a 10-step
onboarding tour across the dashboard; and a mobile sidebar drawer
plus an agent Standup view.

The SQLite schema advanced from v12 to v13 (additive and idempotent):
two new tables (`skills`, `shell_invocations`). v0.7 databases load
cleanly under v13. See `docs/MIGRATION-v0.7-to-v0.8.md` for upgrade
notes.

**v0.7 Command Center (shipped 2026-06-03)** turned horus-os from a
single-page vanilla-JS dashboard into a polished Next.js command
center with a design system, a Setup-and-Verify integrations surface,
an opt-in Discord control bot, an opt-in Supabase sync loop, a cron
scheduler with an always-on service, and an opt-in Vercel deploy
path. It also seeds a five-agent starter team (Coordinator, Engineer,
Researcher, Writer, Operator) with `SOUL.md` personas, an example
vault, and a demo trace on first `init`. v0.6 (Contribution Gate) was
never tagged, so v0.7.0 follows v0.5.0 directly in the tag history.

For the live phase pointer, read `.planning/STATE.md`. For the
phase breakdown, read `.planning/ROADMAP.md`. For the requirement
list, read `.planning/REQUIREMENTS.md`.

## Next up: v0.9 Autonomy and Control

The next planned milestone is **v0.9, Autonomy and Control**. v0.8
shipped raw power (autonomous research, gated shell, metered but
unbounded spend); v0.9 lands the rails that make it safe to turn
agents loose: an event and lifecycle-hook substrate, monetary budgets
that pause on breach, risk-tiered approvals, secrets redaction,
priority execution lanes so background work never starves user work,
watch rules, and controlled overnight or idle autonomy that rides
behind every gate, with a minimal supervision surface (approvals
queue, unified inbox, run-liveness watchdog).

v0.9 is the first of a six-milestone program, v0.9 through v0.14, that
absorbs the full v0.9 gap analysis: v0.10 Memory and Learning, v0.11
Work Legibility, v0.12 Workspace and Models, v0.13 Interop and
Distribution, and v0.14 Interaction Modality. This is a program-level
map, not a committed milestone plan; each milestone is finalized
through the normal planning flow before any phase work begins. The
map lives in `.planning/PROGRAM-v0.9-v0.14.md` and the underlying
analysis in `.planning/research/v0.9-gap-analysis.md`.

## How to follow along

1. **Watch the repo** on GitHub. Releases and Discussions surface
   in your notifications.
2. **Read `CHANGELOG.md`** for what changed in each release.
3. **Read `.planning/STATE.md`** for the live phase pointer (what
   the maintainer is actively working on).
4. **Subscribe to the pinned "Project Status" Discussion** for
   forward-looking updates without a commit.
5. **Join the [community Discord](https://discord.gg/vwX9WvwQhp)**
   for questions, help, and release chatter; the `#help` channel is
   a searchable forum.

## Collaboration is open

As of 2026-06-10 the project accepts outside contributions.
`CONTRIBUTING.md` documents the full standards and the day-to-day
flow: pick an issue labeled `good-first-issue` or `help-wanted`,
comment to claim it, the maintainer assigns it, and a draft PR is
expected within 7 days. Every PR runs the full three-OS CI matrix
plus the supply-chain scans before human review.

Why there was a gate: horus-os was open-sourced from a working
private command center that runs against real data. The v0.6
Contribution Gate milestone (keyless sigstore signing, CycloneDX
SBOMs, pip-audit, SHA-pinned actions, sandboxed forked-PR CI)
existed so that opening the door would not put the downstream
package or any user at risk. That gate shipped, so the door is open.

Real-use feedback is still gold: run horus-os against a real
workload and write up what worked and what did not in Discussions.
That feedback shapes the roadmap.

## Shipped milestone detail

For the in-depth breakdown of every shipped phase, see the matching
section of `ROADMAP.md`. Highlights below.

### v0.5 Plugin System (shipped 2026-05-27)

- TOML manifest contract (`horus-plugin.toml`) with pydantic-backed
  schema validation, capability declarations, and PEP 440 compat
  ranges (`pydantic>=2.7,<3` and `packaging>=24.0` added as base
  runtime deps).
- Discovery via Python entry points (`horus_os.plugins` group) plus
  a `~/.horus-os/plugins/` filesystem path for dev plugins; cold
  start <100ms with zero plugins installed.
- Default-deny capability grants (filesystem.read/write,
  net.outbound, secrets.read) keyed on
  `(plugin_name, plugin_version, capability)` and tied to a manifest
  hash so upgrades that widen requested capabilities re-prompt
  instead of silently inheriting.
- Two-phase installer (`horus-os plugins install <spec>`) that
  refuses sdists, wheels with `.pth` files, and any spec that would
  downgrade runtime deps. Nine CLI subcommands
  (install/uninstall/list/info/enable/disable/update/grant/revoke).
- Bounded `asyncio.wait_for(timeout=2.0)` on plugin lifecycle hooks
  so a hung `start()` cannot block server boot;
  `--disable-all-plugins` escape hatch.
- `/plugins` dashboard tab plus per-plugin observability rollups on
  top of v0.4's `ObservationBus` (new `plugin_name` column on
  `llm_calls` and `tool_invocations`).
- Reference plugin (`examples/horus-os-example-plugin/`) shipped as
  a separate package, with a ruff custom rule pinning the public API
  surface to `horus_os.plugins.api` only.
- 1011 tests across the 3-OS x 2-Python matrix; three-OS
  install-smoke (including the new plugin-install variant driven
  by `scripts/install_smoke_plugin.py`) green on all 6 combos.
- v5 to v6 additive SQLite schema migration; v0.4 databases continue
  to read.
- See `docs/PLUGINS.md`, `docs/PLUGIN-SECURITY.md`,
  `docs/MIGRATION-v0.4-to-v0.5.md`.

### v0.4 Observability (shipped 2026-05-26)

- `ObservationBus` + SQLite persister capture cost, latency, and
  tool reliability per agent run, per LLM call, per tool invocation.
- Bundled `pricing.json` (LiteLLM-sourced) with user-overridable
  rate cards; 14-day freshness check at release time.
- `/observability` dashboard tab (cost by agent, latency p50/p95,
  tool reliability) plus the `horus-os usage --since 7d` CLI
  subcommand with JSON/CSV/table output.
- Opt-in `OtelAdapter` behind a `[otel]` extra; default-deny content
  capture with a redactor allowlist; bounded `force_flush(2000)`
  shutdown.
- 718 tests across the matrix; three-OS install-smoke green on both
  the `[dev]` no-otel and `[dev,otel]` variants.
- See `docs/MIGRATION-v0.3-to-v0.4.md` and `docs/OBSERVABILITY.md`.

### v0.3 Adapter Ecosystem (shipped 2026-05-24)

- Lifecycle hooks: optional `start(ctx)` and `stop()` async hooks
  on the Adapter Protocol, wired into FastAPI lifespan.
- Four first-party adapters: Discord, Slack, Email (IMAP+SMTP),
  Calendar (Google).
- `AdapterRegistry` surfaces status, last activity, error count.
- Dashboard Adapters tab.
- 447 tests across the matrix, three-OS install-smoke green.
- See `docs/MIGRATION-v0.2-to-v0.3.md`.

### v0.2 Multi-Agent + Streaming (shipped 2026-05-23)

- Named agent profiles in SQLite with parent/child trace links.
- `delegate_to_agent` tool.
- `run_agent_stream` async generator with provider streaming
  (Anthropic + Gemini).
- HMAC-verified webhook reference adapter.
- 319 tests, three-OS install-smoke green.
- See `docs/MIGRATION-v0.1-to-v0.2.md`.

### v0.1 Foundation (shipped 2026-05-23)

- Single-agent runtime, two providers (Anthropic + Gemini), one
  tool, persistent SQLite, CLI plus local dashboard.
- 175 tests, three-OS install-smoke green.
- First public alpha.

## Anti-goals

The project deliberately does not pursue:

- A hosted SaaS offering of horus-os.
- Coupling to any single cloud provider beyond the user's chosen
  LLM API.
- Features that require a paid third-party account.
- Multi-tenant deployment patterns.

If your proposal lives in one of those buckets, the answer is "no"
even after contributions open. Save the design-question energy for
something in scope.
