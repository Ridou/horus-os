# Phase 26 Context: Google Calendar adapter

**Date:** 2026-05-24
**Phase:** 26
**Status:** Context captured

## Domain

Phase 26 ships the fourth and final v0.3 adapter. Unlike the
Discord, Slack, and Email adapters that receive inbound events
and route them into `run_agent`, the Calendar adapter is the
opposite shape: it exposes tools the agent can call. The agent
asks for "what's on my schedule today?" and calls
`list_calendar_events_today`; the agent decides to book a slot
and calls `create_calendar_event` (when write access is allowed).

This is a tool-providing adapter. It implements `Adapter` (so it
participates in entry-point discovery, the registry, and the
`/api/adapters` status surface) but NOT `LifecycleAdapter`
(there is no background socket to maintain and no inbox to
poll). All work happens at `bind` time: validate config, load
OAuth credentials, register tools onto the master tool registry.

## Canonical refs

- `.planning/ROADMAP.md` Phase 26 success criteria
- `.planning/REQUIREMENTS.md` CAL-01, CAL-02
- `src/horus_os/adapters/base.py` Adapter Protocol, AdapterContext, AdapterRegistry
- `src/horus_os/adapters/webhook.py` HTTP-only adapter (no lifecycle) reference
- `src/horus_os/tools/registry.py` ToolRegistry shape
- `src/horus_os/tools/builtin.py` tool factory pattern (`read_file_tool`)
- `src/horus_os/types.py` Tool dataclass
- Phase 22 summary for adapter status semantics
- Phase 23 summary for the lazy-import + sys.modules test pattern

## Decisions

### 1. SDK choice: google-api-python-client + google-auth-oauthlib

These are the canonical Google libraries for non-browser Python
clients. The dependency lands as an optional extra:

```
[project.optional-dependencies]
calendar = [
    "google-api-python-client>=2.110",
    "google-auth-oauthlib>=1.2",
]
```

Users install with `pip install horus-os[calendar]`. Tests run
with the extra NOT installed; the adapter module must import
cleanly without the Google libraries on the path.

### 2. Tool injection mechanism: extend AdapterContext

The Calendar adapter needs to register tools onto whatever
ToolRegistry the agent loop will consume. The minimal scope
expansion is to add an optional `tool_registry` field on
`AdapterContext`:

```
@dataclass(frozen=True)
class AdapterContext:
    config: Config
    data_dir: Path
    registry: AdapterRegistry = field(default_factory=AdapterRegistry)
    tool_registry: ToolRegistry | None = None
```

`tool_registry` is None by default. When None, an adapter that
wants to register tools logs a clear "no tool registry was
provided" error into the AdapterRegistry and returns without
registering anything. Wiring this field through to `create_app`
is left to Phase 27 (the dashboard adapter management view will
also need it). For now, callers that want the Calendar adapter
to register tools construct the `AdapterContext` with a
ToolRegistry explicitly. This keeps the change additive and
backwards-compatible.

Alternative considered: a separate `get_tools()` method on the
adapter that the agent layer calls to collect tools. Rejected
because it inverts the registration model. Today tools register
themselves; agent reads from the registry. A pull-from-adapter
model would create a new code path in the agent. The dataclass
addition is one line and preserves the existing direction.

### 3. Adapter is `Adapter` only, not `LifecycleAdapter`

The Calendar adapter has nothing to start and nothing to drain.
The OAuth refresh and the actual Calendar API calls are
on-demand from tool handlers; there is no background task.

This matches the WebhookAdapter shape (Adapter with no
lifecycle). Status semantics: `running` once tools are
registered and OAuth credentials are usable. `error` if the SDK
is missing, the OAuth client path env var is not set, the token
file is missing or unrefreshable, or no tool_registry was
provided.

`bind` does all the work:

1. Lazy import the Google libraries. On `ImportError`, mark error.
2. Read `HORUS_OS_CALENDAR_OAUTH_CLIENT_PATH`. If missing or
   the file is unreadable, mark error.
3. Read the token from `data_dir / "calendar-token.json"`. If
   missing, mark error with the "run horus-os calendar auth"
   hint (the auth CLI command is deferred to a follow-up phase).
4. If the token is expired, attempt refresh. Refresh failure
   marks error.
5. Register `list_calendar_events_today` onto `ctx.tool_registry`.
6. If `HORUS_OS_CALENDAR_WRITE_ALLOWED == "true"`, also register
   `create_calendar_event`.
7. Mark running.

### 4. Token storage

The OAuth refreshable token lives at
`config.data_dir / "calendar-token.json"`. The format matches
`google.oauth2.credentials.Credentials.to_json()` output so
`Credentials.from_authorized_user_info` (or its file variant)
can deserialize it. The auth bootstrap (running the
InstalledAppFlow in a browser) is documented in the setup
guide but not implemented as a CLI command in this phase.
Once the token is written, it self-refreshes lazily.

The adapter stores credentials on `self._creds` after a
successful bind so tool handlers do not re-read the file on
every call. Each tool handler calls `creds.refresh(Request())`
if `creds.expired` before making the API call, which the
Google library guards against unnecessary refreshes internally.

### 5. Tool: list_calendar_events_today

Signature:
```
list_calendar_events_today(calendar_id: str = "primary") -> list[dict]
```

Returns a list of `{summary, start, end, location, attendees}`
dicts for events whose `start` falls within today's window.

Time window choice: 00:00:00 UTC to 23:59:59 UTC of the current
UTC date. Pinning to UTC is the deterministic choice and the
one the tests can assert on without depending on the host's
timezone. The setup guide documents this and suggests setting
the calendar's preferred timezone via the Calendar API or
filtering downstream if a local-day window is preferred. Local
timezone variants can be a follow-up.

Body shape passed to the Google API:
```
events().list(
    calendarId=calendar_id,
    timeMin=<today 00:00:00 UTC iso>,
    timeMax=<today 23:59:59 UTC iso>,
    singleEvents=True,
    orderBy="startTime",
).execute()
```

`singleEvents=True` expands recurring events into individual
instances so the agent sees what is actually happening today,
not a series spec.

Empty result returns `[]`. API errors are caught and returned
as `[{"error": "..."}]` so the agent loop does not crash.

### 6. Tool: create_calendar_event (gated)

Signature:
```
create_calendar_event(
    summary: str,
    start_iso: str,
    end_iso: str,
    calendar_id: str = "primary",
    description: str | None = None,
) -> dict
```

Gated by `HORUS_OS_CALENDAR_WRITE_ALLOWED == "true"`. The check
runs at `bind` time: when the env var is not exactly the string
`"true"`, the tool is never registered. The agent will see
`create_calendar_event` as an unknown tool and surface that to
the user, which is the correct UX: writes are off by default.

A second safety net runs inside the handler: even when the tool
IS registered, the handler re-checks the env var at call time
and returns `{"error": "calendar write not allowed; set
HORUS_OS_CALENDAR_WRITE_ALLOWED=true to enable"}` if it was
flipped off after registration. This catches the operator who
flips the flag mid-run to disable writes without restarting.

Body shape passed to the Google API:
```
events().insert(
    calendarId=calendar_id,
    body={
        "summary": summary,
        "description": description,
        "start": {"dateTime": start_iso},
        "end": {"dateTime": end_iso},
    },
).execute()
```

Returns the created event payload (the Google API echoes the
full event with the assigned `id`, `htmlLink`, etc). Errors are
caught and returned as `{"error": "..."}`.

### 7. Tool handler error isolation

Every tool handler wraps the Google API call in a try/except
that catches `Exception` (which subsumes `HttpError` from
`googleapiclient.errors`) and returns a dict with an `"error"`
key. The agent loop sees this as a normal tool result, not a
runtime exception, and can decide to surface it or retry.

On error, the adapter calls
`ctx.registry.mark_error(self.name, ...)` to increment the
adapter's error counter for the dashboard view.

On success, the adapter calls `ctx.registry.touch(self.name)`
to bump `last_activity_at`.

### 8. Lazy module-level imports

`google.oauth2`, `google.auth.transport.requests`, and
`googleapiclient.discovery` are imported inside `bind` (and
re-imported lazily inside the tool factories that need them).
The module imports cleanly without the Google libraries
installed. Tests inject fakes into `sys.modules` for each
google submodule we touch.

### 9. Configuration via env vars

| Env var | Purpose | Default |
|---------|---------|---------|
| `HORUS_OS_CALENDAR_OAUTH_CLIENT_PATH` | Path to the OAuth client secret JSON downloaded from Google Cloud | required |
| `HORUS_OS_CALENDAR_WRITE_ALLOWED` | When exactly `"true"`, register `create_calendar_event` | unset (read-only) |

The token path is derived from `data_dir`, not a separate env
var, so operators do not have to track two paths.

### 10. Entry point

```
[project.entry-points."horus_os.adapters"]
webhook = "horus_os.adapters.webhook:WebhookAdapter"
discord = "horus_os.adapters.discord_adapter:DiscordAdapter"
slack = "horus_os.adapters.slack_adapter:SlackAdapter"
email = "horus_os.adapters.email_adapter:EmailAdapter"
calendar = "horus_os.adapters.calendar_adapter:CalendarAdapter"
```

The adapter is discoverable out of the box. Whether it
actually registers tools depends only on env vars + token file.

### 11. Module name: calendar_adapter.py

We cannot name the module `calendar.py` because that would
shadow the stdlib `calendar` package. `calendar_adapter.py`
matches the existing `discord_adapter.py`, `slack_adapter.py`,
and `email_adapter.py` naming.

### 12. Test strategy

All tests offline. The Google libraries are NOT installed in
the dev env; tests inject fakes into `sys.modules` for:

- `google.oauth2.credentials` (with `Credentials.from_authorized_user_info`)
- `google.auth.transport.requests` (with `Request`)
- `googleapiclient.discovery` (with `build`)
- `googleapiclient.errors` (with `HttpError`)

The `Credentials` fake exposes `expired`, `valid`, and `refresh`
attributes so the refresh path can be exercised. The
`discovery.build` fake returns a chainable MagicMock whose
`events().list().execute()` and `events().insert().execute()`
return canned dicts.

Tests cover:

1. Adapter constructs without google libs installed
2. Missing `tool_registry` on context marks error
3. Missing OAuth client path env marks error
4. Missing token file marks error with auth hint
5. Expired token gets refreshed inside bind
6. Refresh failure marks error
7. Successful bind registers `list_calendar_events_today`
8. `create_calendar_event` not registered when flag unset
9. `create_calendar_event` not registered when flag is `"false"`
10. `create_calendar_event` registered when flag is `"true"`
11. `list_calendar_events_today` returns structured events
12. `list_calendar_events_today` uses today's UTC window
13. `create_calendar_event` calls `events().insert` with the
    right body and returns the API response
14. Calendar API errors (raised by the fake) are caught and
    returned as `{"error": "..."}` from the tool, no crash
15. Successful tool call calls `registry.touch`
16. Failed tool call calls `registry.mark_error`

## Execution split

Single plan: 26-01. The adapter, the pyproject entry, the
optional extra, the AdapterContext extension, the tests, and
the setup guide land as a coherent unit.

Atomic commits:

- `docs(26)`: plan + context
- `feat(26)`: AdapterContext.tool_registry, CalendarAdapter,
  pyproject entry + extra
- `test(26)`: adapter tests with fake google modules
- `docs(26)`: setup guide at `docs/adapters/CALENDAR.md`
- `docs(26)`: phase summary

## Deferred / not in scope

- `horus-os calendar auth` CLI command to bootstrap the OAuth
  flow. Operators run a standalone script per the setup guide;
  a built-in CLI command is a Phase 27 / v0.4 polish.
- Multi-calendar selection beyond `calendar_id` parameter
  (e.g., `list_calendars` tool). v0.3 ships `primary` plus
  arbitrary calendar ID.
- Recurring event creation. The agent can create a single
  event; recurrence rules are documented but the create tool
  does not expose the `recurrence` field in v0.3.
- Local-timezone windowing for "today". v0.3 uses UTC; the
  setup guide notes how to adjust.
- Service account auth. OAuth user flow only.
- Update / delete event tools. Read + create is the v0.3 surface.
- Per-event tool calls (`describe_event`, `find_free_slots`).
- Wiring `tool_registry` through `create_app` so the
  `/api/agent` flow auto-exposes adapter tools. Phase 27 is
  the natural home for that (the dashboard view will surface
  registered tools, which requires the same wiring).
