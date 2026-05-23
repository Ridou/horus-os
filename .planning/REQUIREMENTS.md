# Requirements

## v0.1 Foundation

### Core runtime (CORE)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| CORE-01 | Run as a single Python process on macOS, Ubuntu, Windows 11 | active | 01, 10 |
| CORE-02 | Accept user prompts via a CLI command and return a structured result | active | 07 |
| CORE-03 | Accept user prompts via a local web chat and return a streaming result | active | 08 |
| CORE-04 | Configure via a single `.env` file | active | 09 |
| CORE-05 | Run with user-supplied API keys (Anthropic and Google Gemini both supported) | active | 02, 09 |

### Agent (AGENT)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| AGENT-01 | One named agent can invoke at least one registered tool | active | 02, 04 |
| AGENT-02 | Every agent run produces a structured trace stored in SQLite | active | 02, 03 |
| AGENT-03 | Agent runtime supports both Anthropic SDK and Google Gemini SDK | active | 02 |

### Tool registry (TOOL)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| TOOL-01 | Register a Python callable as a tool with a JSON schema | active | 04 |
| TOOL-02 | Every tool invocation is logged with input, output, and duration | active | 04 |
| TOOL-03 | At least one example tool ships: read a local file | active | 04 |

### Memory (MEM)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| MEM-01 | Agent can search a markdown notes folder and read individual files | active | 05 |
| MEM-02 | Agent can append to a markdown notes folder | active | 06 |
| MEM-03 | Every memory write is reviewable in the dashboard | active | 06, 08 |

### Dashboard (DASH)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| DASH-01 | Local Next.js dashboard lists recent agent runs and their traces | active | 08 |
| DASH-02 | Dashboard hosts a chat surface that sends prompts to the agent runtime | active | 08 |
| DASH-03 | Dashboard renders each trace with full input, output, and tool invocations | active | 08 |

### Setup wizard (WIZARD)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| WIZARD-01 | `horus-os init` walks a new user through configuration | active | 09 |
| WIZARD-02 | Wizard validates API keys with a live ping before saving | active | 09 |
| WIZARD-03 | Wizard provides direct hyperlinks to Anthropic console and Google AI Studio | active | 09 |
| WIZARD-04 | Wizard is idempotent and resumable (state in `.horus-init-state.json`) | active | 09 |

### Test and CI (TEST)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| TEST-01 | Lint passes (ruff) on Ubuntu, macOS, Windows in GitHub Actions | active | 01 |
| TEST-02 | Unit tests pass (pytest) on Ubuntu, macOS, Windows in GitHub Actions | active | 01 |
| TEST-03 | Fresh-VM install completes on Ubuntu 22.04, macOS, Windows 11 | active | 10 |

### Release (REL)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| REL-01 | Tag v0.1.0 and write release notes | active | 11 |
| REL-02 | Public GitHub repo published with README, LICENSE, CONTRIBUTING | active | 11 |

## v0.2 Multi-Agent + Streaming

### Multi-agent (MA)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| MA-01 | Named agent profiles persist in SQLite (name, system prompt, default model, allowed tools, memory scope) | active | 12 |
| MA-02 | A coordinator agent can delegate to one or more sub-agents via a registered tool | active | 13 |
| MA-03 | Every multi-agent run produces a trace with parent/child linkage | active | 13 |
| MA-04 | At least one default agent profile is auto-created on `horus-os init` | active | 12 |

### Streaming (STREAM)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| STREAM-01 | `run_agent_stream` yields incremental tokens from Anthropic and Gemini | active | 14 |
| STREAM-02 | CLI `run` shows streamed output by default; `--no-stream` falls back to v0.1 behavior | active | 15 |
| STREAM-03 | Dashboard chat surface renders streamed tokens live | active | 16 |

### Adapter (ADAPT)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| ADAPT-01 | Plugin contract defined via `horus_os.adapters` entry point | active | 17 |
| ADAPT-02 | One reference adapter ships: HTTP webhook receiver | active | 17 |
| ADAPT-03 | Third-party adapters register without forking horus-os | active | 17 |

### Migration (MIG)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| MIG-01 | v0.1 SQLite database upgrades to v0.2 schema idempotently | active | 12 |
| MIG-02 | v0.1 single-agent traces remain readable in the v0.2 dashboard | active | 12, 16 |
| MIG-03 | Migration is one-way; downgrade is not supported and is documented | active | 18 |

### Test and CI (continued from v0.1)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| TEST-04 | Multi-agent end-to-end tests pass on three-OS matrix | active | 19, 20 |
| TEST-05 | Streaming tests pass on three-OS matrix | active | 19, 20 |
| TEST-06 | Adapter contract tests pass on three-OS matrix | active | 19, 20 |

### Release (continued from v0.1)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| REL-03 | Tag v0.2.0 with CHANGELOG and GitHub Release | active | 21 |
| REL-04 | Migration notes documented for v0.1 users | active | 18, 21 |

## v0.3 Adapter Ecosystem

### Adapter Runtime (ART)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| ART-01 | Adapter Protocol gains optional `start(ctx)` and `stop()` lifecycle hooks; v0.2 adapters work unchanged | active | 22 |
| ART-02 | FastAPI lifespan invokes `start` on each discovered adapter at startup and `stop` at shutdown | active | 22 |
| ART-03 | `GET /api/adapters` returns name, status, last_activity_at, error_count per adapter | active | 22, 27 |

### Discord (DISC)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| DISC-01 | Discord bot connects, listens for mentions and DMs, replies via configured agent | active | 23 |
| DISC-02 | Setup guide documents bot creation, intents, and token env var | active | 23, 28 |
| DISC-03 | Disconnects trigger exponential-backoff reconnect with configurable cap | active | 23 |

### Slack (SLAK)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| SLAK-01 | Slack Events API endpoint handles `app_mention` and DM events | active | 24 |
| SLAK-02 | Signature verification via signing-secret HMAC-SHA256 over body and timestamp | active | 24 |
| SLAK-03 | Slash command support routing to an agent profile | active | 24 |

### Email (MAIL)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| MAIL-01 | Email adapter polls IMAP inbox, runs agent on new messages | active | 25 |
| MAIL-02 | Replies sent via SMTP preserve `In-Reply-To` and `References` headers | active | 25 |
| MAIL-03 | Configurable poll interval; sleeps cleanly when no messages | active | 25 |

### Calendar (CAL)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| CAL-01 | Calendar adapter exposes `list_calendar_events_today` tool returning structured events | active | 26 |
| CAL-02 | Optional event creation tool, gated behind `HORUS_OS_CALENDAR_WRITE_ALLOWED=true` | active | 26 |

### Dashboard v0.3 (DASH-3)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| DASH-3-01 | `/adapters` dashboard view lists adapters with status, last activity, error count | active | 27 |
| DASH-3-02 | Enable/disable toggle from dashboard via `POST /api/adapters/{name}/{enable,disable}` | active | 27 |

### Test and CI (continued)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| TEST-07 | Discord adapter mocked-SDK tests pass on three-OS matrix | active | 29, 30 |
| TEST-08 | Slack adapter mocked-SDK tests pass on three-OS matrix | active | 29, 30 |
| TEST-09 | Email adapter mocked tests pass on three-OS matrix | active | 29, 30 |
| TEST-10 | Calendar adapter mocked tests pass on three-OS matrix | active | 29, 30 |

### Release (continued)

| ID | Requirement | Status | Phase |
|----|-------------|--------|-------|
| REL-05 | Tag v0.3.0 with CHANGELOG and GitHub Release | active | 31 |
| REL-06 | Migration notes documented for v0.2 users (additive Protocol change) | active | 28, 31 |

## Coverage summary

| Category | Total | Active | Validated |
|----------|-------|--------|-----------|
| CORE | 5 | 5 | 5 |
| AGENT | 3 | 3 | 3 |
| TOOL | 3 | 3 | 3 |
| MEM | 3 | 3 | 3 |
| DASH | 3 | 3 | 3 |
| WIZARD | 4 | 4 | 4 |
| TEST | 10 | 10 | 6 |
| REL | 6 | 6 | 4 |
| MA | 4 | 4 | 4 |
| STREAM | 3 | 3 | 3 |
| ADAPT | 3 | 3 | 3 |
| MIG | 3 | 3 | 3 |
| ART | 3 | 3 | 0 |
| DISC | 3 | 3 | 0 |
| SLAK | 3 | 3 | 0 |
| MAIL | 3 | 3 | 0 |
| CAL | 2 | 2 | 0 |
| DASH-3 | 2 | 2 | 0 |
| **Total** | **66** | **66** | **44** |

"Validated" means the requirement is covered by a shipped phase. v0.1 and v0.2 requirements are validated (shipped 2026-05-23). v0.3 requirements stay unvalidated until their phases ship.
