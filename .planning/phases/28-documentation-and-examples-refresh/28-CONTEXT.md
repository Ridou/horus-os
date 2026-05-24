# Phase 28 Context: Documentation and examples refresh

**Date:** 2026-05-24
**Phase:** 28
**Status:** Context captured

## Domain

The v0.3 milestone shipped six adapter-related phases (22 through
27): a lifecycle Protocol, four concrete inbound adapters (Discord,
Slack, Email, Calendar), and a dashboard tab plus toggle routes for
managing them at runtime. None of that surface area is reflected in
the top-level docs yet. Phase 28 closes that gap before Phase 29
opens the test-surface expansion. Same shape as the v0.2
documentation pass (Phase 18) but scoped to v0.3 additions.

REL-06 in `.planning/REQUIREMENTS.md` is the requirement that lands
here: "v0.3 ships with a refreshed ARCHITECTURE.md, four runnable
adapter examples, a v0.2-to-v0.3 migration guide, and a README that
links to all of it."

## Canonical refs

- `.planning/ROADMAP.md` Phase 28 success criteria
- `.planning/REQUIREMENTS.md` REL-06
- Phase 22 through 27 summaries: the source of truth for what
  the docs pass must describe
- `ARCHITECTURE.md` (v0.2 shape from Phase 18; needs an Adapter
  ecosystem section appended)
- `docs/MIGRATION-v0.1-to-v0.2.md` (template for the new guide)
- `examples/multi_agent.py`, `examples/streaming.py`,
  `examples/custom_adapter.py` (template for the four adapter
  example scripts)

## Decisions

### 1. Four example scripts, one per shipped adapter

`examples/discord_adapter.py`, `examples/slack_adapter.py`,
`examples/email_adapter.py`, `examples/calendar_adapter.py`. Each
demonstrates one inbound (or tool-providing, for Calendar) dispatch
path end to end without the optional SDK installed. The four scripts
mirror the layout of `examples/custom_adapter.py`: short module
docstring, inline stubs of any optional SDKs, a `main()` that walks
the dispatch path, prints what happened, and exits 0.

### 2. SDK stubs via `sys.modules` injection

Every example uses the same fake-module pattern the adapter test
suites use: build a `types.ModuleType("discord")`, attach a tiny
`Client`/`Intents`/`WebClient` fake, then `sys.modules["discord"] = fake`
before importing the adapter under test. `run_agent` is similarly
monkeypatched at the adapter module level with a function that
returns a canned `AgentResult`. No live API calls, no env vars
required, no SDK install needed. The examples document the env vars
operators would set for a live run at the top.

### 3. Examples cover the same dispatch surface the tests do

- Discord: fake mention -> `on_message` -> `_dispatch` -> reply
- Slack: build a valid HMAC signature -> POST events endpoint via
  TestClient -> agent reply via fake `chat_postMessage`
- Email: fake `IMAP4_SSL` with one unseen RFC 822 message -> one
  `_poll_once` iteration -> fake `SMTP_SSL` captures the reply
- Calendar: register tools with the master `ToolRegistry`, invoke
  `list_calendar_events_today` against the fake Google API client,
  print the structured result

### 4. Migration guide lives at `docs/MIGRATION-v0.2-to-v0.3.md`

Mirrors `docs/MIGRATION-v0.1-to-v0.2.md` in structure: TL;DR, what
is new, schema migration (none), user-visible behavior changes,
deprecations (none), downgrade, upgrade code samples. The big honest
note is that v0.3 is purely additive: every v0.2 surface continues
to work byte-identical. The new bits are four optional adapters,
two new optional dependency groups (`discord`, `slack`, `calendar`;
email is stdlib-only), a `LifecycleAdapter` Protocol, an
`AdapterRegistry`, four new server routes, and a Dashboard tab.

### 5. ARCHITECTURE.md keeps every v0.2 section and adds one

The v0.1 and v0.2 sections (single-agent flow, multi-agent shape,
streaming surface, storage shape, configuration, design principles)
remain accurate and stay verbatim. A new "Adapter ecosystem" section
lands after the existing "Adapter interface" section and covers:
the `LifecycleAdapter` Protocol, the `AdapterRegistry`, FastAPI
lifespan integration, the four shipped adapters at a glance, the
toggle routes, the Dashboard Adapters tab, and what is still
deferred. The "What is not in v0.2" section becomes "What is not in
v0.3" and drops items that shipped (Discord, Slack, calendar, email
adapters) while keeping the still-deferred items (cost tracking,
dashboard auth, Socket Mode, OAuth CLI, write-tool merging into the
chat path).

### 6. CHANGELOG `[Unreleased]` only

Phase 31 owns the eventual `[0.3.0]` heading rotation. This phase
populates `[Unreleased]` with `### Added`, `### Changed`, and
`### Documentation` subheadings reflecting every Phase 22-27
deliverable. No `[0.3.0]` heading lands here.

### 7. README stays tight

A new "What is new in v0.3" section between the v0.2 section and
the Documents block. One short paragraph and a bulleted list of
three to five links: the migration guide, the four adapter setup
guides under `docs/adapters/`, and the examples directory.
`docs/MIGRATION-v0.2-to-v0.3.md` joins the Documents block. The
existing Quickstart, What's included, v0.2 section, Contributing,
and License sections are unchanged.

### 8. No em-dashes, no horizontal rules, no blockquotes

Project house style. Every prose file in this phase honors it; the
final smoke check greps for them.

## Execution split

Single plan: 28-01. Four atomic commits land the four docs files
plus README/CHANGELOG:

- `docs(28)`: plan + context (this file plus 28-01-PLAN.md)
- `docs(28)`: refresh ARCHITECTURE.md for v0.3
- `docs(28)`: add four adapter example scripts
- `docs(28)`: add v0.2 to v0.3 migration guide
- `docs(28)`: update README and CHANGELOG for v0.3
- `docs(28)`: summary (28-01-SUMMARY.md)

## Deferred / not in scope

- The `[0.3.0]` CHANGELOG heading rotation (Phase 31)
- The full v0.3 release announcement post (out of repo)
- A guide on rolling your own `LifecycleAdapter`-implementing
  third-party adapter (the existing `examples/custom_adapter.py`
  covers the simpler `Adapter`-only path; a longer-lived adapter
  example would duplicate the four shipped adapters)
- Any new code in `src/`. This phase only touches `ARCHITECTURE.md`,
  `README.md`, `CHANGELOG.md`, `docs/MIGRATION-v0.2-to-v0.3.md`,
  `examples/*_adapter.py`, and `examples/README.md`. No `src/`
  changes; the 437-test surface stays byte-identical.
