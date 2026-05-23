# Phase 23 Context: Discord adapter

**Date:** 2026-05-24
**Phase:** 23
**Status:** Context captured

## Domain

Phase 23 ships the first long-running v0.3 adapter. It exercises the
Phase 22 lifecycle gate end to end: `start` opens a Discord gateway
connection in the background, `stop` closes it cleanly, and the
adapter touches the registry on every successful message dispatch
so `/api/adapters` reflects liveness.

The adapter listens for two trigger shapes:

1. `@bot` mentions in a guild text channel
2. Direct messages to the bot

When either fires, the adapter looks up an `AgentProfile` from the
SQLite store, runs one `run_agent` turn synchronously inside the
event handler, then posts the response back to the same channel or
DM. Discord's 2000-character limit on a single message means long
responses chunk into multiple messages.

## Canonical refs

- `.planning/ROADMAP.md` Phase 23 success criteria
- `.planning/REQUIREMENTS.md` DISC-01, DISC-02, DISC-03
- `src/horus_os/adapters/base.py` LifecycleAdapter Protocol, AdapterRegistry
- `src/horus_os/adapters/webhook.py` reference adapter
- `src/horus_os/agent.py` `run_agent` (sync)
- `src/horus_os/storage.py` `Database.load_profile`
- Phase 22 summary for the lifespan dispatch contract

## Decisions

### 1. SDK choice: discord.py

`discord.py` is the de-facto Python Discord library. It exposes
`discord.Client` with `intents`, the async `start(token)` loop, and
the `on_message` event hook. The alternatives (`nextcord`, `py-cord`)
are forks with API drift; `discord.py` is the canonical reference.

The dependency lands as an **optional** extra:

```
[project.optional-dependencies]
discord = ["discord.py>=2.3"]
```

Users install with `pip install horus-os[discord]`. Tests run with
the extra NOT installed; the adapter module must import cleanly
without `discord.py` on the path.

### 2. Lazy import inside `start`

`import discord` happens inside `start(context)`, not at module top.
This means:

- `from horus_os.adapters.discord_adapter import DiscordAdapter` works
  even when the extra is not installed
- `DiscordAdapter()` constructs cleanly without `discord` available
- `start(context)` is where a missing dep surfaces as a captured
  registry error, not an import crash that breaks discovery

If `import discord` raises `ImportError`, the adapter calls
`context.registry.mark_error(self.name, "...")` with a clear
"install horus-os[discord]" message and returns. The Phase 22
lifespan already isolates one adapter's start failure from siblings.

### 3. Auth via `HORUS_OS_DISCORD_TOKEN`

The bot token is read from the environment variable
`HORUS_OS_DISCORD_TOKEN` inside `start`. If unset, `start` flips
the registry entry to `error` with a message naming the env var
and returns without raising. Other adapters keep running. The
setup guide documents how to mint a token in the Discord
Developer Portal.

No token ever appears in code, tests, or committed config.

### 4. Intents

Discord's gateway requires explicit intents per
`discord.Intents`. The adapter requests:

- `intents.guilds = True` (basic guild metadata)
- `intents.guild_messages = True` (read messages in guild channels)
- `intents.dm_messages = True` (read direct messages)
- `intents.message_content = True` (read the body of messages)

`message_content` is a **privileged intent**: the bot owner must
enable it in the Discord Developer Portal under
"Bot" -> "Privileged Gateway Intents" -> "Message Content Intent".
Without it the bot connects but every message body is empty. The
setup guide calls this out as the most common gotcha.

### 5. Reconnect behavior

`discord.py` handles reconnects internally via its own backoff:
the library's `Client.connect(reconnect=True)` (set by default in
`Client.start`) retries with exponential backoff on transient
disconnects. The adapter does not need to roll its own retry
loop. The decision is to document this and surface a single
configuration knob via env var `HORUS_OS_DISCORD_RECONNECT_CAP`
(maximum seconds between retries) that the adapter passes
through if set, otherwise the library default applies.

DISC-03 is satisfied by the library plus this knob; we do not
re-implement an outer retry loop because that would race with
the SDK's internal one.

### 6. Profile routing

The adapter looks up an `AgentProfile` via `db.load_profile(name)`.
Default profile name is `"default"`. Override via the env var
`HORUS_OS_DISCORD_AGENT_PROFILE`. If the named profile is missing
from the database, the adapter falls back to no profile (no
system_prompt, default provider+model from `Config`). This
matches the webhook adapter's pattern: a missing profile is
non-fatal at runtime, only surfaced via the reply text.

### 7. Reply behavior and message chunking

Discord caps a single message at 2000 characters. Long agent
responses are chunked: the adapter splits the response into
2000-char segments and sends them in order via
`message.channel.send(chunk)`. The first segment goes to the
same channel (or DM) as the inbound message; subsequent chunks
follow in the same channel for thread continuity.

Empty replies (the agent returned an empty string) post a single
"(no response)" placeholder so the user knows the bot received
the mention.

### 8. Error isolation inside on_message

A `run_agent` exception inside the `on_message` handler is
caught, logged via the registry's `mark_error`, and a brief
"Sorry, that failed: ..." message is posted back. The exception
does not propagate up the gateway loop; the connection stays
open. The handler also ignores its own messages (`message.author
== client.user`) to avoid feedback loops, and ignores non-mention
messages in guild channels (only DMs and mentions trigger a run).

### 9. start/stop shape

```
async def start(self, context):
    import discord  # lazy
    token = os.environ.get("HORUS_OS_DISCORD_TOKEN")
    if not token:
        context.registry.mark_error(self.name, "HORUS_OS_DISCORD_TOKEN not set")
        return
    intents = discord.Intents.none()
    intents.guilds = True
    intents.guild_messages = True
    intents.dm_messages = True
    intents.message_content = True
    self._client = discord.Client(intents=intents)
    self._client.event(self._on_ready)
    self._client.event(self._on_message)
    self._task = asyncio.create_task(self._client.start(token))
    context.registry.mark_running(self.name)

async def stop(self):
    if self._client is not None:
        await self._client.close()
    if self._task is not None:
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await self._task
```

`bind(app, context)` is a no-op (Discord doesn't need HTTP routes).
The adapter stores `context` on `self._context` during `start` so
the event handlers can reach `registry`, `config`, and `data_dir`.

### 10. Test strategy: fake `discord` module

Tests must run with `discord.py` not installed. The strategy:

- A `_FakeDiscordModule` builder constructs a `MagicMock` shaped
  like the relevant slice of the `discord` package: `Intents`,
  `Intents.none()`, `Client`, `Message`, etc.
- Tests inject the fake into `sys.modules["discord"]` before
  calling `start`. The lazy `import discord` inside `start` picks
  up the fake.
- The fake `Client` records calls to `start(token)` and `close()`;
  tests assert on those.
- Message routing: the test invokes the adapter's bound
  `on_message` handler directly with a fake `Message` and asserts
  `channel.send` was called with the expected text.
- `run_agent` is monkeypatched at the adapter module level so no
  provider SDK is needed and no network call happens.

This pattern keeps the test surface offline, deterministic, and
fast, and proves the adapter wires up correctly without
exercising the SDK's transport.

### 11. Entry point

```
[project.entry-points."horus_os.adapters"]
webhook = "horus_os.adapters.webhook:WebhookAdapter"
discord = "horus_os.adapters.discord_adapter:DiscordAdapter"
```

The adapter is discoverable out of the box; whether it actually
runs depends only on whether `HORUS_OS_DISCORD_TOKEN` is set
and whether `discord.py` is installed.

### 12. Module name: discord_adapter.py

We cannot name the module `discord.py` because that would shadow
the `discord` package on the import path. `discord_adapter.py`
is unambiguous and matches the existing `webhook.py` pattern
loosely.

## Execution split

Single plan: 23-01. The adapter, the entry point, the optional
extra, the tests, and the setup guide land as a coherent unit;
splitting would create awkward intermediate states.

Atomic commits:

- `docs(23)`: plan + context
- `feat(23)`: DiscordAdapter module, entry-point declaration, optional extra
- `test(23)`: adapter tests (fake `discord` module)
- `docs(23)`: setup guide at `docs/adapters/DISCORD.md`
- `docs(23)`: phase summary

The two `feat` and `test` commits may be combined if the diff is
small. Plan/context and summary commits are always separate.

## Deferred / not in scope

- Slash commands (`/ask`, `/agent`). Phase 23 covers mentions and
  DMs only; slash commands need `discord.app_commands` and
  per-guild registration which is a Phase 28 documentation concern
- Voice channels, reactions, threads, file uploads. The handler
  only consumes text and only replies with text
- Multi-bot support (one process, multiple Discord apps). Single
  token, single client
- Per-channel agent routing. The adapter uses a single configured
  profile; per-channel routing is a v0.4 concern
- Streaming responses to Discord. The full response is awaited then
  chunked; mid-stream typing indicators are a future polish
- Outbound notifications (the adapter as a sender). Phase 23 is
  inbound only; outbound is part of the broader v0.4 plan
