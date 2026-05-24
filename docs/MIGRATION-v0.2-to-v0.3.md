# Migration from v0.2 to v0.3

## TL;DR

v0.3 is purely additive. Every v0.2 surface (`run_agent`,
`run_agent_async`, `run_agent_loop`, `run_agent_stream`,
`Database`, `ToolRegistry`, `Adapter`, `AdapterContext`,
`discover_adapters`, the JSON API, the CLI subcommands, the
dashboard) continues to work byte-identical. There is no schema
migration: SCHEMA_VERSION stays at 4. No deprecations land in
v0.3.

What lights up: an optional lifecycle Protocol on the adapter
contract, a per-app registry that tracks live adapter status,
four shipped first-party adapters (Discord, Slack, Email,
Calendar), three new optional dependency groups, a handful of
new env vars, two new server routes for runtime enable / disable,
and a new Adapters tab in the local dashboard.

## What is new

### Runtime types

- `horus_os.LifecycleAdapter`: optional `runtime_checkable`
  Protocol from `horus_os.adapters`. Adapters with background
  work implement it alongside `Adapter` and get async
  `start(context)` and `stop()` hooks tied to the FastAPI app
  lifespan. Existing `Adapter`-only third-party adapters keep
  working without changes.
- `horus_os.AdapterEntry`: dataclass for one row in the registry.
  Fields: `name`, `status`, `last_activity_at`, `error_count`,
  `error_message`.
- `horus_os.AdapterRegistry`: per-app status tracker. Attached to
  `app.state.adapter_registry`. Adapters call `mark_running`,
  `mark_stopped`, `mark_error`, and `touch` on it; the server
  reads `entries()` for `GET /api/adapters`.
- `ADAPTER_STATUS_RUNNING`, `ADAPTER_STATUS_STOPPED`,
  `ADAPTER_STATUS_ERROR`: the three valid status string constants.

### AdapterContext additions

`horus_os.AdapterContext` gained two additive fields:

- `registry: AdapterRegistry` (default factory). Adapters bump
  `last_activity_at` via `context.registry.touch(name)` and
  surface errors via `context.registry.mark_error(name, ...)`.
- `tool_registry: ToolRegistry | None` (default None).
  Tool-providing adapters (the Calendar adapter today) register
  agent-callable tools onto it during `bind`. A None value is a
  signal: the Calendar adapter checks for it and surfaces a
  clear registry error rather than raising. `create_app` wires a
  fresh `ToolRegistry` through the context, so first-party
  callers always get a non-None value.

Both fields have safe defaults; v0.2 code that builds
`AdapterContext(config=cfg, data_dir=dir)` continues to work.

### Shipped adapters

| Adapter | Lifecycle | Tools | Optional extra | Setup |
|---------|-----------|-------|----------------|-------|
| `DiscordAdapter` | start + stop | none | `[discord]` | `docs/adapters/DISCORD.md` |
| `SlackAdapter` | bind only | none | `[slack]` | `docs/adapters/SLACK.md` |
| `EmailAdapter` | start + stop | none | none (stdlib) | `docs/adapters/EMAIL.md` |
| `CalendarAdapter` | bind only | `list_calendar_events_today`, optional `create_calendar_event` | `[calendar]` | `docs/adapters/CALENDAR.md` |

All four are opt-in: each lazily imports its SDK inside `start`
or `bind` so the package imports cleanly when the optional extra
is not installed. Each declares its entry point in
`pyproject.toml` under `[project.entry-points."horus_os.adapters"]`
so `discover_adapters` picks it up after install.

### New optional dependency groups

```
pip install 'horus-os[discord]'    # discord.py >= 2.3
pip install 'horus-os[slack]'      # slack-sdk >= 3.27
pip install 'horus-os[calendar]'   # google-api-python-client >= 2.110,
                                   # google-auth-oauthlib >= 1.2
```

The `[all]` extra now includes all three. The Email adapter has
no extra: it is stdlib-only (`imaplib`, `smtplib`, `email.*`).

### New environment variables

Discord:

- `HORUS_OS_DISCORD_TOKEN`: bot token. Required.
- `HORUS_OS_DISCORD_AGENT_PROFILE`: profile name. Default `default`.
- `HORUS_OS_DISCORD_RECONNECT_CAP`: optional max backoff seconds
  on the library's internal reconnect loop.

Slack:

- `HORUS_OS_SLACK_BOT_TOKEN`: bot token (xoxb-...). Required.
- `HORUS_OS_SLACK_SIGNING_SECRET`: signing secret from the Slack
  app's Basic Information page. Required.
- `HORUS_OS_SLACK_AGENT_PROFILE`: profile name. Default `default`.

Email:

- `HORUS_OS_EMAIL_IMAP_HOST`: IMAP server. Required.
- `HORUS_OS_EMAIL_IMAP_PORT`: IMAP SSL port. Default 993.
- `HORUS_OS_EMAIL_IMAP_USER`: IMAP login. Required.
- `HORUS_OS_EMAIL_IMAP_PASSWORD`: IMAP password / app password.
  Required.
- `HORUS_OS_EMAIL_SMTP_HOST`: SMTP server. Required.
- `HORUS_OS_EMAIL_SMTP_PORT`: SMTP SSL port. Default 465.
- `HORUS_OS_EMAIL_SMTP_USER`: SMTP login. Defaults to IMAP user.
- `HORUS_OS_EMAIL_SMTP_PASSWORD`: SMTP password. Defaults to IMAP
  password.
- `HORUS_OS_EMAIL_POLL_INTERVAL`: seconds between polls. Default 60.
- `HORUS_OS_EMAIL_AGENT_PROFILE`: profile name. Default `default`.

Calendar:

- `HORUS_OS_CALENDAR_OAUTH_CLIENT_PATH`: path to the OAuth client
  secret JSON downloaded from Google Cloud. Required.
- `HORUS_OS_CALENDAR_WRITE_ALLOWED`: when exactly the string
  `"true"`, the `create_calendar_event` tool is registered.
  Unset or any other value leaves the adapter read-only.
- `HORUS_OS_CALENDAR_AGENT_PROFILE`: profile name. Default
  `default`.

### New server routes

- `GET /api/adapters`: list every registered adapter entry. Each
  object includes `name`, `status` (`running` / `stopped` /
  `error`), `last_activity_at` (UTC iso8601 or null),
  `error_count`, `error_message`, and `supports_toggle`.
- `POST /api/adapters/{name}/enable`: awaits `adapter.start(context)`
  on a lifecycle adapter. 404 unknown, 400 missing hook, 500 on
  hook exception with the registry capturing the error.
- `POST /api/adapters/{name}/disable`: awaits `adapter.stop()`.
  Same error semantics.

The FastAPI app additionally exposes `app.state.tool_registry`
(the master ToolRegistry adapters register onto) and
`app.state.adapters` (the discovered adapter list) for downstream
code.

### Dashboard

A new Adapters tab polls `GET /api/adapters` every five seconds
and renders one row per adapter with a color-coded status pill
(green running, gray stopped, red error), `last_activity_at`,
`error_count`, the truncated `error_message`, and a per-adapter
Enable / Disable / n/a button driven by `supports_toggle`. The
existing Chat, Traces, Writes, and Agents tabs are unchanged.

## Schema migration

None in v0.3. SCHEMA_VERSION stays at 4. v0.2 databases work
under v0.3 byte-identical. No `ALTER TABLE` statements run on
the upgrade. The four shipped adapters add no tables; the
`AdapterRegistry` is in-process state, reset on every
`create_app` call.

## User-visible behavior changes

None for existing v0.2 code paths. Every new surface (the four
adapters, the registry, the toggle routes, the Dashboard tab)
is opt-in. v0.2 scripts that drive `run_agent` or `run_agent_stream`,
v0.2 third-party adapters that implement only `name` + `bind`,
and v0.2 dashboard users who never visit the Adapters tab all
get byte-identical behavior under v0.3.

## Deprecations

None in v0.3.

## Downgrade

Trivial. v0.3 makes no schema changes, so a v0.3 database is
already a valid v0.2 database. To roll back:

```
pip install horus-os==0.2.0
```

Any new shipped-adapter env vars become inert; the new server
routes disappear; the Dashboard tab disappears. Nothing on disk
needs cleaning up.

## Upgrade code samples

### Implementing a LifecycleAdapter

Existing `Adapter`-only adapters keep working. To opt into the
lifecycle hooks, add `async def start(self, context)` and
`async def stop(self)`:

```python
from typing import Any
from horus_os.adapters import Adapter, AdapterContext, LifecycleAdapter


class TickAdapter:
    name = "tick"

    def __init__(self) -> None:
        self._task = None
        self._context: AdapterContext | None = None

    def bind(self, app: Any, context: AdapterContext) -> None:
        # Optional: mount diagnostic HTTP routes on the FastAPI app.
        return None

    async def start(self, context: AdapterContext) -> None:
        import asyncio

        self._context = context
        context.registry.mark_running(self.name)

        async def _loop() -> None:
            while True:
                await asyncio.sleep(60)
                # Lazily import any SDK here so the module import
                # stays clean when the optional extra is absent.
                context.registry.touch(self.name)

        self._task = asyncio.create_task(_loop())

    async def stop(self) -> None:
        import contextlib

        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(BaseException):
                await self._task
        if self._context is not None:
            self._context.registry.mark_stopped(self.name)


assert isinstance(TickAdapter(), Adapter)
# Optional sanity check (Protocol is runtime_checkable):
assert isinstance(TickAdapter(), LifecycleAdapter)
```

The FastAPI lifespan picks up `start` and `stop` automatically
via `hasattr` once the adapter is discovered through its entry
point.

### Querying /api/adapters

```python
import httpx

resp = httpx.get("http://127.0.0.1:8765/api/adapters", timeout=2.0)
resp.raise_for_status()
for entry in resp.json():
    print(
        f"{entry['name']:>10} | {entry['status']:>7} | "
        f"errors={entry['error_count']} | "
        f"toggle={entry['supports_toggle']} | "
        f"last={entry['last_activity_at'] or '(never)'}"
    )
```

Toggle a lifecycle adapter at runtime:

```python
httpx.post("http://127.0.0.1:8765/api/adapters/discord/disable")
httpx.post("http://127.0.0.1:8765/api/adapters/discord/enable")
```

`enable` 400s for adapters with no `start` hook;
`supports_toggle` on the GET payload tells the caller which is
which.

### Configuring the four shipped adapters

Discord:

```
pip install 'horus-os[discord]'
export HORUS_OS_DISCORD_TOKEN=your-bot-token-here
export HORUS_OS_DISCORD_AGENT_PROFILE=default       # optional
horus-os serve
```

See `docs/adapters/DISCORD.md` for the Discord Developer Portal
setup, intents, and OAuth invite URL.

Slack:

```
pip install 'horus-os[slack]'
export HORUS_OS_SLACK_BOT_TOKEN=xoxb-your-bot-token-here
export HORUS_OS_SLACK_SIGNING_SECRET=your-signing-secret-here
export HORUS_OS_SLACK_AGENT_PROFILE=default         # optional
horus-os serve
```

Point the Slack app's Event Subscriptions URL at
`https://your-host/api/adapters/slack/events`. See
`docs/adapters/SLACK.md` for scopes, manifest, and slash command
setup.

Email:

```
# no extra needed; stdlib only
export HORUS_OS_EMAIL_IMAP_HOST=imap.example.com
export HORUS_OS_EMAIL_IMAP_USER=bot@example.com
export HORUS_OS_EMAIL_IMAP_PASSWORD=your-imap-password-here
export HORUS_OS_EMAIL_SMTP_HOST=smtp.example.com
# port defaults: IMAP 993, SMTP 465; poll defaults to 60s
horus-os serve
```

See `docs/adapters/EMAIL.md` for app-password setup, threading
behavior, and the poison-message safety story.

Calendar:

```
pip install 'horus-os[calendar]'
# one-time OAuth bootstrap produces calendar-token.json in the data dir:
#   see docs/adapters/CALENDAR.md
export HORUS_OS_CALENDAR_OAUTH_CLIENT_PATH=/path/to/your-oauth-client-here.json
export HORUS_OS_CALENDAR_WRITE_ALLOWED=true         # optional; default read-only
horus-os serve
```

See `docs/adapters/CALENDAR.md` for the OAuth bootstrap, scopes,
the read-only / write-allowed split, and how the tools surface
to the agent.

For runnable, offline introductions to each adapter, see
`examples/discord_adapter.py`, `examples/slack_adapter.py`,
`examples/email_adapter.py`, and `examples/calendar_adapter.py`.
