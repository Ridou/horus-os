---
phase: 23-discord-adapter
plan: "01"
subsystem: adapters
tags: [adapter, discord, lifecycle, optional-dep, gateway]

requires:
  - phase: "22-01"
provides:
  - "DiscordAdapter with lazy discord.py import and lifecycle hooks"
  - "discord.py>=2.3 as an optional pip extra"
  - "horus_os.adapters entry-point declaration for discord"
  - "docs/adapters/DISCORD.md setup guide"

requirements-completed:
  - DISC-01  # Discord bot connects, listens for mentions and DMs, replies via configured agent
  - DISC-02  # Setup guide documents bot creation, intents, and token env var
  - DISC-03  # Disconnects trigger exponential-backoff reconnect (delegated to discord.py library)

duration: ~45m
completed: 2026-05-24
total-tests: 361
delta-tests: +17
v0.3-progress: Phase 23 of 31 complete (first v0.3 adapter shipped)
---

# Phase 23 Plan 01 Summary: Discord adapter

## What shipped

The first long-running v0.3 adapter. DiscordAdapter exercises the
Phase 22 lifecycle gate end to end: `start` opens a gateway
connection in a background task, `on_message` dispatches mentions
and DMs through `run_agent`, replies chunk back to the source
channel at the 2000-character Discord limit, and `stop` closes
the connection cleanly.

### New module

`src/horus_os/adapters/discord_adapter.py` defines `DiscordAdapter`.
The class satisfies both the `Adapter` Protocol (name, no-op
`bind`) and the `LifecycleAdapter` Protocol (async `start`, async
`stop`).

| Surface | Behavior |
|---------|----------|
| `bind(app, context)` | No-op; Discord uses the gateway, not HTTP routes on FastAPI |
| `start(context)` | Lazy `import discord`. Missing SDK or missing `HORUS_OS_DISCORD_TOKEN` flips registry to `error` with a clear message. Token + SDK: builds `Intents.none()` with `guilds`, `guild_messages`, `dm_messages`, and `message_content` flipped on, constructs `Client`, registers `on_message`, schedules `asyncio.create_task(client.start(token))`, marks registry `running` |
| `stop()` | Awaits `client.close()` and cancels the background task. No-op when start never ran |
| `_make_on_message(client)` | Closure that ignores own messages, ignores non-mention guild messages, strips leading `<@id>`/`<@!id>` tokens, dispatches to `run_agent` with the configured profile, chunks the response at 2000 chars, touches the registry for `last_activity_at` |
| `_dispatch(prompt)` | Loads `AgentProfile` by `HORUS_OS_DISCORD_AGENT_PROFILE` (defaults to `default`); missing profile is non-fatal (no `system_prompt`, default provider+model) |

Errors during `run_agent` are caught and surfaced as a short
"Sorry, that failed: ..." reply plus a `mark_error` entry; the
gateway connection stays open.

### Optional dependency

`pyproject.toml` gains:

```
[project.optional-dependencies]
discord = ["discord.py>=2.3"]

[project.entry-points."horus_os.adapters"]
webhook = "horus_os.adapters.webhook:WebhookAdapter"
discord = "horus_os.adapters.discord_adapter:DiscordAdapter"
```

The `all` extras group also picks up `discord.py>=2.3`. Tests run
with `discord.py` simulated as missing via `sys.modules`
injection; the production code never assumes the dependency is
present until inside `start`.

### Reconnect strategy

`discord.py` handles reconnects internally with exponential
backoff via `Client.start(..., reconnect=True)`. DISC-03 is
satisfied by the library plus an optional
`HORUS_OS_DISCORD_RECONNECT_CAP` env var the adapter forwards
best-effort. We do not roll our own outer retry loop because that
would race with the SDK's internal one.

### Setup guide

`docs/adapters/DISCORD.md` (165 lines) walks operators through:
extras install, bot creation in the Discord Developer Portal,
the Message Content Intent toggle (the single most common
gotcha), OAuth2 invite URL with the minimal permissions
(`View Channels`, `Send Messages`, `Read Message History`), env
var setup, and a troubleshooting section covering empty message
bodies, missing replies, 401 on connect, and reconnect loops.

## Files touched

- `src/horus_os/adapters/discord_adapter.py` (new, 222 lines)
- `src/horus_os/adapters/__init__.py`: re-export `DiscordAdapter`
- `pyproject.toml`: `discord` optional extra, `discord` entry point
- `tests/test_adapters_discord.py` (new, 17 tests)
- `docs/adapters/DISCORD.md` (new, 165 lines)

## Test surface

17 net new tests. All run with `discord.py` simulated as either
missing (`sys.modules["discord"] = None`) or stubbed via a fake
module exposing `Intents` and `Client`. `run_agent` is monkeypatched
at the adapter module level so no provider SDK is needed and no
network call happens.

| Group | Tests |
|-------|-------|
| Construction | clean construct without discord, no-op bind |
| Start errors | missing SDK, missing token |
| Start happy path | task scheduled, intents flipped, registry `running` |
| on_message routing | ignores own messages, ignores non-mention guild messages, responds to DMs, responds to guild mentions, loads configured profile, missing profile non-fatal |
| Chunking | long reply splits at 2000 chars, empty result posts "(no response)" |
| Error isolation | run_agent exception surfaces as reply + mark_error |
| Stop | closes client + cancels task, no-op when start never ran |
| Helpers | _strip_mention removes leading mention tokens |

Full suite: 361 passed in 3.84s (344 baseline + 17 new). All
v0.2, Phase 22, and webhook tests pass byte-identical.

## Lint status

`ruff check .` clean. `ruff format --check .` clean. Auto-fix
removed a quoted `_Intents` forward reference (UP037) in the test
file and applied one format pass on both new files.

## Notable / deferred

- `discord.py` IS installed in the dev environment that ran this
  phase. Tests deliberately do not rely on that fact; they inject
  a fake `discord` module via `sys.modules` so the suite runs
  green even in the CI matrix where the extra is absent. This
  was verified by the missing-SDK test which forces
  `sys.modules["discord"] = None` to trigger ImportError
- The adapter calls `run_agent` (no tools). Tool use over Discord
  is deferred to v0.4. The agent profile's `allowed_tools` field
  is loaded but currently ignored on this code path
- No per-channel or per-user routing. A single profile name from
  `HORUS_OS_DISCORD_AGENT_PROFILE` applies to every inbound
  message. Per-channel routing is a v0.4 backlog item
- No streaming. The full agent response is awaited, then chunked.
  Typing indicators and partial replies are a future polish
- Slash commands (`/ask`, `/agent`) are out of scope. They need
  `discord.app_commands` and per-guild registration, which is a
  Phase 28 documentation concern
- The reconnect cap env var is passed best-effort; if the
  installed `discord.py` version's `Client.start` does not accept
  the `reconnect` kwarg the adapter falls back to the
  parameterless form. The library's internal backoff still
  applies
- Outbound notifications (the adapter as a sender, not just a
  responder) are deferred. v0.3 ships inbound-only adapters
- Phase 24 (Slack), Phase 25 (Email), Phase 26 (Calendar) can
  now ship in parallel. Each follows the same lazy-import,
  fake-SDK-fixture test pattern this phase established
