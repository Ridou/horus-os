# Phase 24 Context: Slack adapter

**Date:** 2026-05-24
**Phase:** 24
**Status:** Context captured

## Domain

Phase 24 ships the second v0.3 adapter. Unlike Phase 23 (Discord),
which uses a persistent gateway connection and therefore implements
`LifecycleAdapter`, Slack's Events API is HTTP-only. The adapter
binds two FastAPI routes and never opens a background socket. It
satisfies only the `Adapter` Protocol; once `bind` returns the
registry entry stays `running` until shutdown.

Inbound shapes the adapter handles:

1. `app_mention` events posted by Slack to `/api/adapters/slack/events`
2. `message` events with `channel_type == "im"` (direct messages to the bot)
3. Slash commands posted as form-encoded payloads to `/api/adapters/slack/commands`

Outbound: replies are posted via `slack_sdk.web.WebClient.chat_postMessage`
back to the source channel, using `thread_ts` when the inbound
event arrived inside a thread.

## Canonical refs

- `.planning/ROADMAP.md` Phase 24 success criteria
- `.planning/REQUIREMENTS.md` SLAK-01, SLAK-02, SLAK-03
- `src/horus_os/adapters/base.py` Adapter Protocol, AdapterRegistry
- `src/horus_os/adapters/webhook.py` HMAC-signature precedent (Phase 17)
- `src/horus_os/adapters/discord_adapter.py` lazy-import + env-var + run_agent precedent (Phase 23)
- Slack API docs: https://api.slack.com/authentication/verifying-requests-from-slack
- Slack API docs: https://api.slack.com/apis/events-api

## Decisions

### 1. SDK choice: slack-sdk (official slack_sdk package)

`slack-sdk` is the official Python SDK from Slack. It wraps the
HTTP Web API under `slack_sdk.web.WebClient` (sync) and exposes
`slack_sdk.signature.SignatureVerifier` as a convenience, though
we hand-roll the HMAC inside the adapter so the signed-string
format is explicit and reviewable.

The dependency lands as an **optional** extra:

```
[project.optional-dependencies]
slack = ["slack-sdk>=3.27"]
```

Users install with `pip install horus-os[slack]`. Tests run with
the extra NOT installed; the adapter module must import cleanly
without `slack_sdk` on the path.

### 2. Receive via Events API webhook, NOT Socket Mode

Slack offers two ways to receive events: Events API (HTTP webhook,
the operator's server must be publicly reachable) and Socket Mode
(persistent WebSocket, no public URL required). We pick Events API
for v0.3 because:

- The HTTP surface is explicit and visible in the FastAPI route list
- No background task means no lifecycle hook, simpler reasoning
- Operators already have a public dashboard URL for the v0.2 webhook
- Socket Mode adds a separate token type (`xapp-`) and another
  lifecycle hook, deferred to a later phase

The setup guide recommends ngrok for local development so the
operator does not need a fixed public IP to test.

### 3. Lazy import inside `bind`

`import slack_sdk` happens inside `bind(app, context)`, not at
module top. This means:

- `from horus_os.adapters.slack_adapter import SlackAdapter` works
  even when the extra is not installed
- `SlackAdapter()` constructs cleanly without `slack_sdk` available
- `bind` is where a missing dep surfaces as a registry error;
  routes are still mounted but every request returns 503

If `import slack_sdk` raises `ImportError`, the adapter calls
`context.registry.mark_error(self.name, "...")` with a clear
"install horus-os[slack]" hint. The routes are still bound (so
`/api/adapters/slack/events` does not 404) but the handlers
short-circuit to a 503 with the same install hint in the body.

### 4. Auth: bot token + signing secret

Two environment variables, both required at runtime:

- `HORUS_OS_SLACK_BOT_TOKEN`: `xoxb-...`. Used by `WebClient` for
  outbound `chat_postMessage` calls.
- `HORUS_OS_SLACK_SIGNING_SECRET`: 32-char hex string from the
  Slack app's "Basic Information" page. Used for HMAC verification
  of every inbound request.

If either is missing at request time, the adapter returns 503 with
a body naming the missing env var. The registry entry is also
flipped to `error` on the first missing-env-var hit. Setup guide
documents both.

No token or secret ever appears in code, tests, or committed config.

### 5. HMAC signature verification (SLAK-02)

Per Slack docs, every inbound request includes:

- `X-Slack-Request-Timestamp: <unix-seconds>`
- `X-Slack-Signature: v0=<hex>`

The signed string is exactly `f"v0:{timestamp}:{body.decode('utf-8')}"`
where `body` is the raw request body bytes. Compute
`hmac.new(signing_secret.encode("utf-8"), signed_string.encode("utf-8"),
hashlib.sha256).hexdigest()` and compare with `hmac.compare_digest`
(constant time, no timing oracle).

Replay protection: reject if `abs(time.time() - int(timestamp)) > 300`
(5 minutes per Slack's recommendation). Missing or non-numeric
timestamp returns 401.

The exact signed-string format is documented in test fixtures so
reviewers can cross-check against the Slack docs without re-reading
the implementation.

### 6. Routes

- `POST /api/adapters/slack/events`: JSON body. Handles
  `url_verification` challenge (returns the challenge string
  verbatim) and `event_callback` wrapping `app_mention` or DM
  `message` events.
- `POST /api/adapters/slack/commands`: form-encoded body
  (`application/x-www-form-urlencoded`). Slash commands like
  `/horus what time is it`. Returns JSON `{"text": "..."}` for
  inline replies. (Long-running commands could use the
  `response_url` for async replies, deferred.)

Both routes verify the signature BEFORE parsing the body further.
Both routes touch the registry on every successfully handled
request via `context.registry.touch(self.name)`.

### 7. Event deduplication

Slack retries every event up to 3 times if the receiver does not
respond with 2xx within 3 seconds (which can happen when the
agent takes longer than that). To avoid double-processing the
same event_id, the adapter keeps an in-memory LRU set capped at
1000 entries. On a duplicate event_id the handler returns 200 OK
immediately and does not invoke `run_agent`.

A real production deployment would persist this set to SQLite to
survive restarts, but for v0.3 the in-memory cap is sufficient
and matches the simplicity bar set by other v0.3 adapters.

### 8. Event filtering

- `app_mention`: always handled
- `message` with `channel_type == "im"`: handled (DM)
- Any `message` with `subtype == "bot_message"` or a non-empty
  `bot_id` field is ignored (no echo loop with our own bot or
  other bots)
- Any other event subtype is acknowledged (200 OK) but not routed

### 9. Profile routing

The adapter looks up an `AgentProfile` via `db.load_profile(name)`.
Default profile name is `"default"`. Override via the env var
`HORUS_OS_SLACK_AGENT_PROFILE`. Missing profile is non-fatal:
the adapter falls back to no `system_prompt` and default
provider+model from `Config`. Matches the Discord and webhook
adapters.

### 10. Reply behavior

For events, the adapter posts via
`WebClient.chat_postMessage(channel=channel, text=reply,
thread_ts=thread_ts if in_thread else None)`. Long replies do not
chunk like Discord does; Slack supports messages up to 40000
characters (text field), which is well above any agent output we
expect. If a reply is empty, the adapter posts `(no response)` as
a placeholder so the user knows the bot received the trigger.

For slash commands, the reply is returned inline in the HTTP
response body as `{"response_type": "in_channel", "text": "..."}`
so all channel members see it. The synchronous shape constrains
us to responses that the agent can produce in under 3 seconds; a
follow-up phase can switch to deferred `response_url` posting.

### 11. Error isolation

A `run_agent` exception inside an event handler is caught, the
registry is flipped to `error` with the exception message, and
a brief "Sorry, that failed: <ExceptionType>" reply is posted.
The route returns 200 OK so Slack does not retry. For slash
commands the same brief failure goes in the JSON response body.

### 12. Adapter shape (no LifecycleAdapter)

```
class SlackAdapter:
    name = "slack"

    def __init__(self):
        self._client = None
        self._signing_secret = None
        self._seen_event_ids = collections.OrderedDict()

    def bind(self, app, context):
        try:
            import slack_sdk
        except ImportError:
            context.registry.mark_error(self.name, "...")
            # still bind routes so the URL exists; handlers 503
            ...
        ...
        @app.post("/api/adapters/slack/events")
        async def events(request): ...
        @app.post("/api/adapters/slack/commands")
        async def commands(request): ...
```

No `start` or `stop`. The Phase 22 lifespan handler treats
adapters without lifecycle methods as no-ops (Phase 22 dispatch
uses `hasattr`).

To make the Phase 22 lifespan show `slack` as `running` once
`bind` succeeds, the adapter calls `context.registry.mark_running`
at the end of `bind` (success path). Phase 22 already accepts
that pattern: `WebhookAdapter` also marks itself running from
`bind`.

### 13. Test strategy: fake `slack_sdk` module

Tests must run with `slack-sdk` not installed. The strategy:

- A `_install_fake_slack_sdk(monkeypatch)` helper builds a fake
  `slack_sdk` module exposing only what the adapter touches:
  `slack_sdk.WebClient` (a class) and `slack_sdk.errors.SlackApiError`
  (to keep the import statement syntactically valid even when the
  adapter does not catch on it).
- The fake `WebClient` records `chat_postMessage` calls; tests
  assert on the recorded calls.
- HMAC fixtures: tests compute the expected signature against
  fixed `(timestamp, body, secret)` triples so reviewers can
  verify the format against Slack docs.
- `run_agent` is monkeypatched at the adapter module level.
- The FastAPI route is exercised via `fastapi.testclient.TestClient`,
  same pattern as `test_adapters_webhook.py`.

### 14. Entry point

```
[project.entry-points."horus_os.adapters"]
webhook = "horus_os.adapters.webhook:WebhookAdapter"
discord = "horus_os.adapters.discord_adapter:DiscordAdapter"
slack = "horus_os.adapters.slack_adapter:SlackAdapter"
```

The adapter is discoverable out of the box; whether it actually
runs depends on whether `slack-sdk` is installed AND both env
vars are set.

### 15. Module name: slack_adapter.py

Mirrors `discord_adapter.py`. Cannot be `slack.py` because that
shadows the slack-sdk import path in some configurations and is
inconsistent with the Phase 23 pattern.

## Execution split

Single plan: 24-01. The adapter, the entry point, the optional
extra, the tests, and the setup guide land as one coherent unit
just like Phase 23.

Atomic commits:

- `docs(24)`: plan + context
- `feat(24)`: SlackAdapter module, entry-point declaration, optional extra
- `test(24)`: adapter tests (fake `slack_sdk` module)
- `docs(24)`: setup guide at `docs/adapters/SLACK.md`
- `docs(24)`: phase summary

## Deferred / not in scope

- Socket Mode (`xapp-` tokens, persistent WebSocket). Phase 24
  ships HTTP-only; Socket Mode is a future enhancement
- Interactive components: buttons, modals, view submissions
  (`/interactive` endpoint, `block_actions` payloads). Out of scope
- Workflow steps, shortcuts, message actions
- `response_url` deferred replies for slash commands. v0.3 returns
  the response inline within Slack's 3-second window; deferred
  delivery is a follow-up
- File uploads, attachments, reactions
- Per-channel agent routing. Single `HORUS_OS_SLACK_AGENT_PROFILE`
  applies to every inbound event
- Streaming responses (Slack does not support streaming a single
  message; multi-message updates via `chat_update` are a future
  polish)
- Outbound notifications (the adapter as a sender). v0.3 ships
  inbound-only adapters
- Persisting the event-id dedup set across restarts. v0.3 keeps
  the LRU in memory
