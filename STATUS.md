# Project Status

This page is the canonical "where is horus-os right now" view. It
exists so people following the project from the outside have a
single URL to check, and so the "is this accepting contributions
yet?" question has a clear, dated answer.

For the deep planning detail, read `ROADMAP.md` and `.planning/`.
For release contents, read `CHANGELOG.md`.

**Last updated:** 2026-05-31.

## TL;DR

- horus-os is in **solo development mode**, with two milestones in
  active development: **v0.6 Contribution Gate** and **v0.7 Look and
  Feel + Starter Team**.
- Outside pull requests are **not being merged yet**. Issue claim
  comments ("on it", "claim this", "assign to me") are **not honored
  yet**.
- The project opens for outside contributions once an internal
  supply-chain readiness gate is met. That gate is the **v0.6**
  milestone, now in active development. Not promised, not scheduled.
- You can, and this is the most valuable input right now: file bug
  reports, open Discussions, star or watch the repo, and run
  horus-os locally and report what worked.
- You cannot yet: open PRs from a fork, claim issues, or get assigned
  to work.

## Milestone timeline

| Milestone | Scope | State | Tag | Date |
|-----------|-------|-------|-----|------|
| v0.1 Foundation | Single-agent runtime, two providers, CLI, dashboard, three-OS install gate | **SHIPPED** | `v0.1.0` | 2026-05-23 |
| v0.2 Multi-Agent + Streaming | Named agent profiles, `delegate_to_agent`, provider streaming, adapter plugin contract | **SHIPPED** | `v0.2.0` | 2026-05-23 |
| v0.3 Adapter Ecosystem | Discord, Slack, Email, Calendar adapters, lifecycle hooks, dashboard adapters view | **SHIPPED** | `v0.3.0` | 2026-05-24 |
| v0.4 Observability | Cost tracking, latency, tool reliability, observability dashboard tab, opt-in OTel exporter, `horus-os usage` CLI | **SHIPPED** | `v0.4.0` | 2026-05-26 |
| v0.5 Plugin System | Third-party tools and adapters loadable from a `horus-plugin.toml` manifest. Default-deny capability grants, two-phase installer, `/plugins` dashboard tab, per-plugin observability, reference plugin. | **SHIPPED** | `v0.5.0` | 2026-05-27 |
| v0.6 Contribution Gate | Supply-chain hardening: keyless sigstore signing, CycloneDX SBOMs, pip-audit, SHA-pinned actions, refreshed contributor docs, release-gate extended to 13 checks. The readiness gate for opening outside contributions. | **IN DEVELOPMENT** | TBD | TBD |
| v0.7 Look and Feel + Starter Team | A bundled Next.js dashboard, a seeded five-agent starter team with SOUL personas, an example vault, eye-of-Horus branding, and a unified marketing and demo site. | **IN DEVELOPMENT** | TBD | TBD |

State legend: **SHIPPED** means tagged and on the Releases page.
**IN DEVELOPMENT** means the roadmap is committed and phases are
executing, but it is not tagged yet. **NOT PLANNED** means scope is
sketched with no commitment and no schedule.

## Currently working on

Two milestones are in active development.

**v0.6 Contribution Gate** is rehearsal-ready. It builds the trust
and supply-chain substrate that makes "outside PRs welcome" safe:
keyless sigstore signing on wheels, sdists, SBOMs, and tags;
CycloneDX 1.6 SBOMs generated against a fresh install-from-wheel
venv; pip-audit on every PR; Dependabot for pip and GitHub Actions;
every action `uses:` pinned to a commit SHA; `pull_request_target`
forbidden by default; refreshed contributor docs and a SECURITY
disclosure flow; and the release gate extended from 8 to 13 checks.
This is the readiness gate that opening outside contributions
depends on.

**v0.7 Look and Feel + Starter Team** makes horus-os feel like a
product on first run. It adds a real Next.js dashboard (team org
view, memory browser, activity timeline, traces explorer, and a
costs and observability page) static-exported and bundled into the
wheel so it runs with no Node; a seeded five-agent starter team
(Coordinator, Engineer, Researcher, Writer, Operator) with
`SOUL.md` personas, an example vault, and a demo trace on first
`init`; the eye-of-Horus brand and design system; and a unified
marketing and demo site with a guided Get Started flow. Try the
live demo at https://horus-os-demo.vercel.app.

For the live phase pointer, read `.planning/STATE.md`. For the
phase breakdown, read `.planning/ROADMAP.md`. For the requirement
list, read `.planning/REQUIREMENTS.md`.

## How to follow along

1. **Watch the repo** on GitHub. Releases and Discussions surface
   in your notifications.
2. **Read `CHANGELOG.md`** for what changed in each release.
3. **Read `.planning/STATE.md`** for the live phase pointer (what
   the maintainer is actively working on).
4. **Subscribe to the pinned "Project Status" Discussion** for
   forward-looking updates without a commit.

## When collaboration opens

The project opens for outside contributions once an internal
supply-chain readiness gate is met. **That gate is the v0.6
milestone, now in active development.** When it lands, this page
flips first, and the pinned Discussion gets a follow-up reply.
`CONTRIBUTING.md` already documents the full standards and the
day-to-day flow that will apply, so you can read them in advance.

Why the gate exists: horus-os was open-sourced from a working
private command center that runs against the maintainer's real
data and home PC. One bad merge could compromise that PC, the
downstream package, or both. A readiness gate is the precondition
for any open contribution model.

Until then, the most valuable outside contribution is **real-use
feedback in Discussions**. Run horus-os against a real workload
and write up what worked and what did not. That feedback shapes
the roadmap.

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
