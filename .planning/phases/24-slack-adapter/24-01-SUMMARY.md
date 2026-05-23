---
phase: 24-slack-adapter
plan: "01"
subsystem: adapters
tags: [adapter, slack, http, hmac, optional-dep]

requires:
  - phase: "23-01"
provides:
  - "SlackAdapter with lazy slack_sdk import, HMAC verification, Events API + slash command routes"
  - "slack-sdk>=3.27 as an optional pip extra"
  - "horus_os.adapters entry-point declaration for slack"
  - "docs/adapters/SLACK.md setup guide"

requirements-completed:
  - SLAK-01  # Events API endpoint handles app_mention and DM events
  - SLAK-02  # Signature verification via signing-secret HMAC-SHA256 over body and timestamp
  - SLAK-03  # Slash command support routing to an agent profile

duration: ~40m
completed: 2026-05-24
total-tests: 380
delta-tests: +19
v0.3-progress: Phase 24 of 31 complete (second v0.3 adapter shipped)
---

# Phase 24 Plan 01 Summary: Slack adapter

## What shipped

The second v0.3 adapter. Unlike the Discord adapter (Phase 23),
which holds a persistent gateway connection and implements
`LifecycleAdapter`, Slack uses HTTP webhooks for both Events API
delivery and slash commands. The Slack adapter therefore
satisfies only the `Adapter` Protocol: it binds two FastAPI
routes during `bind` and runs no background task.

### New module

`src/horus_os/adapters/slack_adapter.py` defines `SlackAdapter`.
The class satisfies the `Adapter` Protocol (name, `bind`) and is
NOT a `LifecycleAdapter`. Phase 22's lifespan dispatch uses
`hasattr` so adapters without `start`/`stop` are handled as
no-ops.

| Surface | Behavior |
|---------|----------|
| `bind(app, context)` | Lazily imports `slack_sdk`. Missing SDK flips the registry to `error` with an install hint but routes still mount so the URLs exist and handlers return 503 with the same hint. Successful import marks the registry `running`. |
| `POST /api/adapters/slack/events` | Verifies HMAC signature, handles `url_verification` challenge, routes `app_mention` and DM `message` events through `run_agent`, posts the reply via `WebClient.chat_postMessage` with `thread_ts` when in-thread. Returns 200 even on agent failure (failure becomes a brief reply plus a registry `mark_error`) so Slack does not retry. |
| `POST /api/adapters/slack/commands` | Verifies HMAC signature, parses the form-encoded body, runs `run_agent`, returns `{"response_type": "in_channel", "text": "..."}` inline. |
| `_verify_signature` | `hmac.compare_digest` over `v0:{timestamp}:{body.decode("utf-8")}` with a 300-second replay window. Constant-time comparison. |
| `_dispatch_event_payload` | Pure routing: dedup, bot-message guard, event-type filter, prompt extraction, agent run, reply post. |
| `_dispatch_command_form` | Pure routing for slash commands: extract `text`, run agent, format response. |
| `_dispatch(prompt)` | Loads `AgentProfile` by `HORUS_OS_SLACK_AGENT_PROFILE` (defaults to `default`); missing profile is non-fatal (no `system_prompt`, default provider+model). |

Event handling features:

- In-memory LRU dedup of `event_id` (cap 1000) so Slack's 3-second
  retry does not double-trigger the agent
- `bot_message` subtype and `bot_id` guards prevent echo loops
- Failed `chat_postMessage` calls are suppressed; the HTTP route
  still returns 200

### Optional dependency

`pyproject.toml` gains:

```
[project.optional-dependencies]
slack = ["slack-sdk>=3.27"]

[project.entry-points."horus_os.adapters"]
webhook = "horus_os.adapters.webhook:WebhookAdapter"
discord = "horus_os.adapters.discord_adapter:DiscordAdapter"
slack = "horus_os.adapters.slack_adapter:SlackAdapter"
```

The `all` extras group also picks up `slack-sdk>=3.27`. Tests run
with `slack-sdk` NOT installed (verified: the dev environment has
no `slack_sdk` package). The fake-module pattern from Phase 23
extends cleanly to Slack.

### Setup guide

`docs/adapters/SLACK.md` (213 lines) walks operators through:
extras install, Slack app creation, bot scopes
(`chat:write`, `app_mentions:read`, `im:history`, `im:read`,
`commands`), bot token + signing secret retrieval, public-URL
exposure (ngrok for local), Events API enablement and event
subscription, optional slash command registration, env var
setup, and a troubleshooting section covering signature mismatch
(wrong secret, proxy body re-encoding, clock drift), missing
scopes, url_verification handshake failures, Slack's 3-second
timeout, and the two registry error states.

## Files touched

- `src/horus_os/adapters/slack_adapter.py` (new, ~380 lines)
- `src/horus_os/adapters/__init__.py`: re-export `SlackAdapter`
- `pyproject.toml`: `slack` optional extra, `slack` entry point
- `tests/test_adapters_slack.py` (new, 19 tests)
- `docs/adapters/SLACK.md` (new, 213 lines)

## Test surface

19 net new tests. All run with `slack-sdk` simulated as either
missing (`sys.modules["slack_sdk"] = None`) or stubbed via a fake
module exposing `WebClient` (capturing `chat_postMessage` calls)
and `errors.SlackApiError`. `run_agent` is monkeypatched at the
adapter module level.

| Group | Tests |
|-------|-------|
| Construction | clean construct without slack_sdk |
| Missing SDK | bind records error, routes 503 (events + commands) |
| Missing env vars | 503 + registry error |
| HMAC signature | pass, bad signature 401, missing header 401, old timestamp 401 |
| Event routing | url_verification echoes challenge, app_mention runs agent, DM runs agent, bot_message ignored, event_id dedup |
| Slash commands | signature verified, agent runs, JSON response shape, bad signature 401 |
| Profile routing | env var picks scribe profile from DB |
| Error isolation | run_agent exception becomes brief reply + mark_error, route returns 200 |
| Bind side-effects | registry marked running when SDK present |
| Helpers | _verify_signature round-trip + format docs, _strip_user_mentions tokens |

Full suite: 380 passed in 3.89s (361 baseline + 19 new). All
v0.2, Phase 22, and Phase 23 tests pass byte-identical.

## Lint status

`ruff check .` clean. `ruff format --check .` clean. The adapter
defines route handlers as closures inside `bind` (mirroring
`webhook.py`) so `HTTPException` is resolved at the closure
level rather than rebinding to module globals. The closures
delegate to `_dispatch_event_payload` and `_dispatch_command_form`
on the adapter instance for the actual routing logic; that split
keeps each closure short and the routing logic unit-testable
without spinning up FastAPI.

## Notable / deferred

- `slack-sdk` is NOT installed in the dev environment that ran
  this phase. The tests inject a fake module via `sys.modules`
  to exercise the adapter
- Socket Mode (persistent WebSocket via an `xapp-` token) is
  out of scope. v0.3 ships HTTP-only; Socket Mode adds another
  lifecycle hook and is deferred to a later phase
- Interactive components (buttons, modals, view submissions) are
  not handled. The `/interactive` endpoint and `block_actions`
  payloads are a v0.4 concern
- `response_url` deferred replies for slash commands are not
  implemented. The adapter returns the response inline within
  Slack's 3-second window; agents that take longer will see
  Slack timeouts even though the dedup keeps `run_agent` from
  running twice
- File uploads, attachments, reactions are out of scope
- Per-channel agent routing is deferred. A single profile from
  `HORUS_OS_SLACK_AGENT_PROFILE` applies to every inbound event
- The event-id dedup set lives in memory only; a restart clears
  it. A v0.4 enhancement could persist it to SQLite to survive
  restarts
- Streaming responses (multi-message `chat_update` for
  progressive output) are deferred
- Phase 25 (Email) can now proceed, following the same lazy-import
  + fake-SDK-fixture test pattern Phase 23 and Phase 24 established
