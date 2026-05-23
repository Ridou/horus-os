# Google Calendar adapter

The Calendar adapter is the first tool-providing v0.3 adapter.
Instead of routing inbound events into the agent (like the
Discord, Slack, and Email adapters), it registers
agent-callable tools onto the horus-os tool registry. Your
agent can ask "what's on my schedule today?" and the adapter
answers by calling the Google Calendar API.

Two tools ship:

- `list_calendar_events_today(calendar_id="primary")` returns
  a list of today's events. Always registered when the adapter
  binds successfully.
- `create_calendar_event(summary, start_iso, end_iso, ...)`
  creates one event. Off by default. Set
  `HORUS_OS_CALENDAR_WRITE_ALLOWED=true` to register it.

## 1. Install the optional extra

```
pip install 'horus-os[calendar]'
```

This pulls in `google-api-python-client` and
`google-auth-oauthlib`. Without these libraries the adapter
loads cleanly but `bind` marks itself in error and registers
no tools.

## 2. Create a Google Cloud project

Visit https://console.cloud.google.com and create a new
project (or pick an existing one). Note the project ID; the
setup guide refers to it as `your-project-id`.

## 3. Enable the Google Calendar API

In the Cloud Console, open "APIs and Services" then "Library."
Search for "Google Calendar API" and click "Enable" for your
project.

## 4. Create OAuth 2.0 credentials

In "APIs and Services" then "Credentials," click "Create
Credentials" and pick "OAuth client ID." Choose the
"Desktop app" application type. Give it any name, then
download the resulting JSON file. Save it somewhere the
horus-os process can read, for example
`~/.config/horus-os/your-oauth-client.json`.

If this is your first OAuth client in the project, you will
also need to fill in the "OAuth consent screen" page. Pick
"External," add yourself as a test user, and set the scope to
`https://www.googleapis.com/auth/calendar` (read + write) or
`.../calendar.readonly` (read only).

## 5. Bootstrap the OAuth token (one time)

The adapter expects a refreshable token at
`<data_dir>/calendar-token.json`. Generate it once with a
short standalone script:

```
# bootstrap_calendar_token.py
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

CLIENT_PATH = "your-oauth-client.json"
DATA_DIR = Path("your-data-dir")  # same path you configured for horus-os
SCOPES = ["https://www.googleapis.com/auth/calendar"]

flow = InstalledAppFlow.from_client_secrets_file(CLIENT_PATH, SCOPES)
creds = flow.run_local_server(port=0)
DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "calendar-token.json").write_text(creds.to_json())
print("Wrote calendar-token.json")
```

Run it once:

```
python bootstrap_calendar_token.py
```

A browser window opens and walks you through the OAuth
consent. After you approve, the script writes the refreshable
token into `<data_dir>/calendar-token.json`. Restart horus-os
and the adapter picks it up.

For read-only access, use the `calendar.readonly` scope above.
Switching scopes later requires re-running the bootstrap.

## 6. Configure environment variables

```
export HORUS_OS_CALENDAR_OAUTH_CLIENT_PATH=/path/to/your-oauth-client.json
# Optional: enable event creation (off by default for safety).
export HORUS_OS_CALENDAR_WRITE_ALLOWED=true
```

| Variable | Purpose | Default |
|----------|---------|---------|
| `HORUS_OS_CALENDAR_OAUTH_CLIENT_PATH` | Path to the OAuth client JSON | required |
| `HORUS_OS_CALENDAR_WRITE_ALLOWED` | Set to exactly `true` to register `create_calendar_event` | unset (read only) |

`HORUS_OS_CALENDAR_WRITE_ALLOWED` is checked at bind time AND
re-checked inside the create-event handler at call time. You
can flip writes off mid-run without restarting.

## 7. Sample agent usage

With the adapter wired in, your agent can answer prompts like:

> What's on my schedule today?

The agent picks `list_calendar_events_today`, calls it, and
summarizes the result. Each event comes back as:

```
{
  "summary": "Morning standup",
  "start": "2026-05-24T15:00:00Z",
  "end": "2026-05-24T15:30:00Z",
  "location": "Conference room",
  "attendees": ["alice@example.test", "bob@example.test"]
}
```

If writes are enabled, the agent can also handle:

> Book a 30 minute focus block at 2pm.

The agent picks `create_calendar_event`, supplies the
required `summary`, `start_iso`, and `end_iso` arguments, and
returns the API payload with the new event's `id` and
`htmlLink`.

## 8. Token refresh

When the adapter binds, it checks `creds.expired` and calls
`creds.refresh(Request())` if needed. Refresh failures mark
the adapter status as `error` with the underlying exception
captured. The dashboard's adapter view surfaces this.

The token at `<data_dir>/calendar-token.json` self-refreshes
via the refresh token stored alongside the access token. If
you revoke the OAuth grant in your Google account, the next
refresh fails; re-run the bootstrap script to mint a new
token.

## 9. Time zone caveat

The "today" window for `list_calendar_events_today` is the
current UTC day (00:00:00 UTC to 23:59:59 UTC). If your
calendar timezone differs from UTC, events may straddle the
window. For local-day windowing, either filter the result
downstream in the agent prompt or wait for a future
adapter knob.

## 10. Troubleshooting

**Adapter status is `error` with "tool_registry is None":**
The horus-os runtime did not pass a `ToolRegistry` on the
`AdapterContext`. This wiring is set up by `create_app`; if
you are constructing the context manually, pass a
`ToolRegistry()` explicitly.

**Adapter status is `error` with "google-api-python-client ...
not installed":** Run `pip install 'horus-os[calendar]'`.

**Adapter status is `error` with "token file not found":**
Run the bootstrap script from step 5 and confirm the resulting
JSON is at `<data_dir>/calendar-token.json`.

**Adapter status is `error` with "token refresh failed":**
The refresh token is no longer valid (revoked, expired, or
rotated). Re-run the bootstrap script.

**Tool call returns `{"error": "calendar write not allowed"}`:**
Set `HORUS_OS_CALENDAR_WRITE_ALLOWED=true` and restart the
horus-os process so the adapter re-registers the tool.

**Tool call returns `{"error": "...HttpError: 404..."}` or
similar:** The Calendar API returned an error. Common causes:
the `calendar_id` is wrong (use the long string from the
Calendar UI's "Settings and sharing" page; `primary` works
for your default calendar), the OAuth grant lacks the right
scope (re-run the bootstrap with the correct scope), or the
event payload is malformed (check `start_iso` and `end_iso`
are valid ISO 8601 with timezone offsets).

**Tool call returns events but they look stale:** The Calendar
API may take a few seconds to reflect newly added events.
Retry after a short wait.

## 11. Security notes

The token file at `<data_dir>/calendar-token.json` is as
sensitive as your Google account session. Keep your data dir
restrictive (the wizard helper applies 0700-style permissions
on POSIX systems). If the file leaks, revoke the grant at
https://myaccount.google.com/permissions and re-run the
bootstrap.

The OAuth client JSON is less sensitive but still secret; it
identifies your application to Google. Do not commit it to
version control.
