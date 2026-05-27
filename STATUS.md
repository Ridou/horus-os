# Project Status

This page is the canonical "where is horus-os right now" view. It
exists so people following the project from the outside have a
single URL to check, and so the "is this accepting contributions
yet?" question has a clear, dated answer.

For the deep planning detail, read `ROADMAP.md` and `.planning/`.
For release contents, read `CHANGELOG.md`.

**Last updated:** 2026-05-27.

## TL;DR

- horus-os is in **solo development mode**.
- Outside pull requests are **not being merged**. Issue claim
  comments ("on it", "claim this", "assign to me") are **not
  honored**.
- The project opens for outside contributions once an internal
  readiness gate is met. Earliest milestone: **v0.6**. Not
  promised. Not scheduled.
- You can: file bug reports, open Discussions, star or watch the
  repo, run horus-os locally and report what worked.
- You cannot yet: open PRs from a fork, claim issues, get assigned
  to work.

## Milestone timeline

| Milestone | Scope | State | Tag | Date |
|-----------|-------|-------|-----|------|
| v0.1 Foundation | Single-agent runtime, two providers, CLI, dashboard, three-OS install gate | **SHIPPED** | `v0.1.0` | 2026-05-23 |
| v0.2 Multi-Agent + Streaming | Named agent profiles, `delegate_to_agent`, provider streaming, adapter plugin contract | **SHIPPED** | `v0.2.0` | 2026-05-23 |
| v0.3 Adapter Ecosystem | Discord, Slack, Email, Calendar adapters, lifecycle hooks, dashboard adapters view | **SHIPPED** | `v0.3.0` | 2026-05-24 |
| v0.4 Observability | Cost tracking, latency, tool reliability, observability dashboard tab, opt-in OTel exporter, `horus-os usage` CLI | **SHIPPED** | `v0.4.0` | 2026-05-26 |
| v0.5 Plugin System | Third-party tools and adapters loadable from a `horus-plugin.toml` manifest. Default-deny capability grants, two-phase installer, `/plugins` dashboard tab, per-plugin observability, reference plugin. | **SHIPPING** | `v0.5.0` (target) | 2026-05-27 |
| v0.6+ Contribution gate | Earliest possible window for opening outside contributions. Tied to internal readiness. | **NOT PLANNED** | TBD | TBD |

State legend: **SHIPPED** means tagged and on the Releases page.
**SHIPPING** means all phases complete, version bumped, final
release gate in progress (tag and GitHub Release imminent).
**PLANNING** means roadmap drafted, plan or execution in progress.
**NOT PLANNED** means scope is sketched but no commitment, no
schedule.

## Currently working on

**v0.5 Plugin System** is shipping. All 11 phases (40-50) shipped
to `main` on 2026-05-27. 1011 tests passing across the 3-OS × 2-Python
matrix. Final release gate is running through CI; once green, the
maintainer tags `v0.5.0` and publishes the GitHub Release.

v0.5 introduces:
- TOML manifest contract (`horus-plugin.toml`) with pydantic-backed
  schema validation, capability declarations, and PEP 440 compat
  ranges.
- Discovery via Python entry points (`horus_os.plugins` group) plus
  a `~/.horus-os/plugins/` filesystem path for dev plugins.
- Default-deny capability grants (filesystem.read/write, net.outbound,
  secrets.read) keyed on `(plugin_name, plugin_version, capability)`
  and tied to a manifest hash so upgrades that widen requested
  capabilities re-prompt instead of silently inheriting.
- Two-phase installer (`horus-os plugins install <spec>` — download,
  validate, grant prompt, install) that refuses sdists, wheels with
  `.pth` files, and any spec that would downgrade runtime deps.
- Bounded `asyncio.wait_for(timeout=2.0)` on plugin lifecycle hooks
  so a hung `start()` cannot block server boot.
- `/plugins` dashboard tab plus per-plugin observability rollups
  on top of v0.4's `ObservationBus` (new `plugin_name` column on
  `llm_calls` and `tool_invocations`).
- Reference plugin (`examples/horus-os-example-plugin/`) shipping
  as a separate package, with a ruff custom rule pinning the
  public API surface to `horus_os.plugins.api` only.
- v5→v6 additive SQLite schema migration; v0.4 databases continue
  to read.

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
readiness gate is met. **Earliest milestone for this: v0.6.**
Possibly later. Not scheduled, not promised. When it ships, this
page flips first, and the pinned Discussion gets a follow-up
reply.

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
