# Project Status

This page is the canonical "where is horus-os right now" view. It
exists so people following the project from the outside have a
single URL to check, and so the "is this accepting contributions
yet?" question has a clear, dated answer.

For the deep planning detail, read `ROADMAP.md` and `.planning/`.
For release contents, read `CHANGELOG.md`.

**Last updated:** 2026-05-26.

## TL;DR

- horus-os is in **solo development mode**.
- Outside pull requests are **not being merged**. Issue claim
  comments ("on it", "claim this", "assign to me") are **not
  honored**.
- The project opens for outside contributions once the **private
  PR-review pipeline** lands. Earliest milestone: **v0.6**. Not
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
| v0.4 Observability | Cost tracking, latency, tool reliability, observability dashboard tab, opt-in OTel exporter, `horus-os usage` CLI | **PLANNING** | `v0.4.0` (target) | TBD |
| v0.5 Plugin system | Third-party tools and agents load from a manifest. Shape decided in flight. | **NOT PLANNED** | TBD | TBD |
| v0.6+ Contribution gate | Earliest possible window for opening outside contributions. Tied to the private pipeline landing. | **NOT PLANNED** | TBD | TBD |

State legend: **SHIPPED** means tagged and on the Releases page.
**PLANNING** means roadmap drafted, plan or execution in progress.
**NOT PLANNED** means scope is sketched but no commitment, no
schedule.

## Currently working on

**v0.4 Observability** roadmap was created on 2026-05-26. Phases
32-39 map 41 requirements covering cost, latency, tool
reliability, dashboard observability tab, an opt-in OpenTelemetry
exporter (with bounded shutdown and PII-leak guards), and a
`horus-os usage` CLI subcommand. Execution order is
`32 → 33 → 34 → 35 → (36 ∥ 37) → 38 → 39`.

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

The project opens for outside contributions once the **private
PR-review pipeline** is in place. The seed is tracked publicly at
`.planning/seeds/SEED-001-contributor-pipeline.md`.

private is the private security agent that will:

1. Vet contributor identity and prior public work before any PR
   review.
2. Run every incoming PR through static analysis, secret
   scanning, dependency-provenance checks, and a behavior diff
   against `main`, inside a sandbox, before any human review.
3. Surface a verdict to the maintainer's private channel.
4. Never auto-merge. The human decides.

**Earliest milestone for this to land: v0.6.** Possibly later.
Not scheduled, not promised. When it ships, this page flips
first, and the pinned Discussion gets a follow-up reply.

Why the gate exists: horus-os was open-sourced from a working
private command center that runs against the maintainer's real
data and home PC. One bad merge could compromise that PC, the
downstream package, or both. The private gate is the precondition
for any open contribution model.

Until then, the most valuable outside contribution is **real-use
feedback in Discussions**. Run horus-os against a real workload
and write up what worked and what did not. That feedback shapes
the roadmap.

## Shipped milestone detail

For the in-depth breakdown of every shipped phase, see the matching
section of `ROADMAP.md`. Highlights below.

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
