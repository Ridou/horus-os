# Examples

Runnable, offline introductions to the v0.2 and v0.3 public API.
Every script executes end to end with no API keys, no network, and
no extra installs. Each one stubs the provider call, the adapter
SDK, or the IMAP / SMTP modules inline; the docstrings document how
to swap the stub for a live call.

Run from the repo root after `pip install '.[dev]'` (or `'.[all]'`).

## `multi_agent.py`

Coordinator-to-sub-agent delegation. Builds a temp SQLite database,
saves a `summarizer` profile alongside the bootstrapped `default`
profile, registers `delegate_to_agent` via `make_delegate_tool`, and
prints the resulting parent/child trace linkage.

```
python examples/multi_agent.py
```

## `streaming.py`

`run_agent_stream` consumption. Stubs the Anthropic streaming helper
so the example paints tokens to stdout offline, then surfaces a
`ToolCallEvent` on stderr after the text stream drains. Mirrors what
the CLI does for `horus-os run` when streaming is on.

```
python examples/streaming.py
```

## `custom_adapter.py`

Implementing the `Adapter` Protocol. Defines a `HelloAdapter` class,
registers it through an inline `entry_points` stub (a real adapter
declares its entry point in `pyproject.toml` instead), and calls
`create_app(data_dir=...)` to mount the route. Prints every
`/api/adapters/...` route the resulting FastAPI app has.

```
python examples/custom_adapter.py
```

## `discord_adapter.py`

`DiscordAdapter` end to end. Injects a fake `discord` module into
`sys.modules` (`Intents.none()` plus a `Client` whose `start` blocks
forever and `close` records), starts the adapter so the gateway
client is wired and the `on_message` coroutine is captured, then
fabricates a guild mention message and dispatches it through
`on_message`. Prints what the channel would have replied and the
`AdapterRegistry` entry's status. See `docs/adapters/DISCORD.md` for
live-run setup.

```
python examples/discord_adapter.py
```

## `slack_adapter.py`

`SlackAdapter` end to end. Injects a fake `slack_sdk` whose
`WebClient.chat_postMessage` records every call, binds the adapter
onto a FastAPI app, builds an `app_mention` Events API payload,
computes the same HMAC-SHA256 signature Slack would send
(`v0:{timestamp}:{body}` keyed by the signing secret), and POSTs it
through `fastapi.testclient.TestClient`. Prints the response shape
and the captured `chat_postMessage` calls. See
`docs/adapters/SLACK.md` for live-run setup.

```
python examples/slack_adapter.py
```

## `email_adapter.py`

`EmailAdapter` end to end. Replaces `imaplib.IMAP4_SSL` and
`smtplib.SMTP_SSL` on the adapter module with `_FakeIMAP` /
`_FakeSMTP` stand-ins seeded with one unseen RFC 822 message, then
drives one `_poll_once()` iteration directly (no loop, no sleep, no
background task). Prints the captured IMAP search / fetch / store
calls and the SMTP reply, including the `In-Reply-To` and
`References` headers so the RFC 5322 threading proof is visible. See
`docs/adapters/EMAIL.md` for live-run setup.

```
python examples/email_adapter.py
```

## `calendar_adapter.py`

`CalendarAdapter` end to end. Injects fake `google.*` and
`googleapiclient.*` modules so `bind` succeeds without the
`google-api-python-client` install, writes a placeholder
`calendar-token.json` into a temp data dir, and registers tools onto
a real `ToolRegistry` carried on `AdapterContext.tool_registry`.
Then invokes `list_calendar_events_today` via the registry the same
way the agent runtime would, and prints the structured result plus
the underlying Google API call kwargs. See
`docs/adapters/CALENDAR.md` for live-run setup.

```
python examples/calendar_adapter.py
```

## Running against live providers

Each script's docstring describes which stub to remove and which env
var to set for a live run. The shape of the script does not change.
For example, in `streaming.py`, delete the `_stub_anthropic_stream()`
call, set `ANTHROPIC_API_KEY=sk-ant-...`, and rerun.

See `docs/MIGRATION-v0.1-to-v0.2.md` and
`docs/MIGRATION-v0.2-to-v0.3.md` for the broader upgrade paths, and
`ARCHITECTURE.md` for the system shape these examples touch.
