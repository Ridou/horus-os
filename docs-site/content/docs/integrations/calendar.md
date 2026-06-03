---
title: "Calendar"
description: "Connect horus-os to Google Calendar so your agents can read today's schedule and, optionally, create events."
---

## Overview

The Calendar integration is a tool-providing adapter. Unlike the [Discord](/integrations/discord/), [Slack](/integrations/slack/), and [Email](/integrations/email/) adapters, which route inbound events into your agent team, the Calendar adapter registers agent-callable tools on the horus-os tool registry. Your agent can ask "what is on my schedule today?" and the adapter answers by calling the Google Calendar API.

Two tools ship with the adapter:

- `list_calendar_events_today(calendar_id="primary")` returns a list of today's events. It is always registered when the adapter binds successfully.
- `create_calendar_event(summary, start_iso, end_iso, ...)` creates a single event. It is off by default. Set `HORUS_OS_CALENDAR_WRITE_ALLOWED=true` to register it.

> [!NOTE]
> The Calendar adapter is read only out of the box. Event creation stays disabled until you explicitly opt in, which keeps an agent from writing to your real calendar by accident.

## 1. Install the calendar extra

```bash
pip install 'horus-os[calendar]'
```

This pulls in `google-api-python-client` and `google-auth-oauthlib`. Without these libraries the adapter loads cleanly but `bind` marks itself in error and registers no tools.

## 2. Create a Google Cloud project

Visit https://console.cloud.google.com and create a new project, or pick an existing one. Note the project ID; the steps below refer to it as `your-project-id`.

## 3. Enable the Google Calendar API

In the Cloud Console, open "APIs and Services" then "Library." Search for "Google Calendar API" and click "Enable" for your project.

## 4. Create OAuth 2.0 credentials

In "APIs and Services" then "Credentials," click "Create Credentials" and pick "OAuth client ID." Choose the "Desktop app" application type. Give it any name, then download the resulting JSON file. Save it somewhere the horus-os process can read, for example `~/.config/horus-os/your-oauth-client.json`.

If this is your first OAuth client in the project, you also need to fill in the "OAuth consent screen" page. Pick "External," add yourself as a test user, and set the scope to one of:

- `https://www.googleapis.com/auth/calendar` for read and write access.
- `https://www.googleapis.com/auth/calendar.readonly` for read-only access.

## 5. Bootstrap the OAuth token (one time)

The adapter expects a refreshable token at `<data_dir>/calendar-token.json`. Generate it once with a short standalone script.

```python
# bootstrap_calendar_token.py
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

CLIENT_PATH = "your-oauth-client.json"
DATA_DIR = Path("your-data-dir")  # the same path you configured for horus-os
SCOPES = ["https://www.googleapis.com/auth/calendar"]

flow = InstalledAppFlow.from_client_secrets_file(CLIENT_PATH, SCOPES)
creds = flow.run_local_server(port=0)
DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "calendar-token.json").write_text(creds.to_json())
print("Wrote calendar-token.json")
```

Run it once:

```bash
python bootstrap_calendar_token.py
```

A browser window opens and walks you through the OAuth consent. After you approve, the script writes the refreshable token into `<data_dir>/calendar-token.json`. Restart horus-os and the adapter picks it up.

For read-only access, use the `calendar.readonly` scope in the `SCOPES` list. Switching scopes later requires re-running the bootstrap.

> [!TIP]
> The default data directory varies by platform: `~/Library/Application Support/horus-os` on macOS, `~/.local/share/horus-os` (or `$XDG_DATA_HOME/horus-os`) on Linux, and `%APPDATA%\horus-os` on Windows. Override it with `HORUS_OS_DATA_DIR`. Use that same path for `DATA_DIR` in the bootstrap script. See [Configuration](/getting-started/configuration/) for details.

## 6. Configure environment variables

```bash
export HORUS_OS_CALENDAR_OAUTH_CLIENT_PATH=/path/to/your-oauth-client.json
# Optional: enable event creation (off by default for safety).
export HORUS_OS_CALENDAR_WRITE_ALLOWED=true
```

| Variable | Purpose | Default |
|----------|---------|---------|
| `HORUS_OS_CALENDAR_OAUTH_CLIENT_PATH` | Path to the OAuth client JSON | required |
| `HORUS_OS_CALENDAR_WRITE_ALLOWED` | Set to exactly `true` to register `create_calendar_event` | unset (read only) |

`HORUS_OS_CALENDAR_WRITE_ALLOWED` is checked at bind time and re-checked inside the create-event handler at call time. You can flip writes off mid-run without restarting.

## 7. Sample agent usage

With the adapter wired in, your agent can answer prompts like:

> What is on my schedule today?

The agent picks `list_calendar_events_today`, calls it, and summarizes the result. Each event comes back as:

```json
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

The agent picks `create_calendar_event`, supplies the required `summary`, `start_iso`, and `end_iso` arguments, and returns the API payload with the new event's `id` and `htmlLink`.

## Token refresh

When the adapter binds, it checks whether the credentials are expired and refreshes them if needed. Refresh failures mark the adapter status as `error` with the underlying exception captured, and the dashboard's adapter view surfaces it.

The token at `<data_dir>/calendar-token.json` self-refreshes using the refresh token stored alongside the access token. If you revoke the OAuth grant in your Google account, the next refresh fails; re-run the bootstrap script to mint a new token.

## Time zone caveat

The "today" window for `list_calendar_events_today` is the current UTC day (00:00:00 UTC to 23:59:59 UTC). If your calendar time zone differs from UTC, events may straddle the window. For local-day windowing, filter the result downstream in the agent prompt.

## Troubleshooting

**Adapter status is `error` with "tool_registry is None":** The horus-os runtime did not pass a tool registry on the adapter context. This wiring is set up automatically when the app is created; if you are constructing the context manually, pass a tool registry explicitly.

**Adapter status is `error` with "google-api-python-client ... not installed":** Run `pip install 'horus-os[calendar]'`.

**Adapter status is `error` with "token file not found":** Run the bootstrap script from step 5 and confirm the resulting JSON is at `<data_dir>/calendar-token.json`.

**Adapter status is `error` with "token refresh failed":** The refresh token is no longer valid (revoked, expired, or rotated). Re-run the bootstrap script.

**Tool call returns `{"error": "calendar write not allowed"}`:** Set `HORUS_OS_CALENDAR_WRITE_ALLOWED=true` and restart the horus-os process so the adapter re-registers the tool.

**Tool call returns an HTTP 404 or similar error:** The Calendar API returned an error. Common causes: the `calendar_id` is wrong (use the long string from the Calendar UI's "Settings and sharing" page; `primary` works for your default calendar), the OAuth grant lacks the right scope (re-run the bootstrap with the correct scope), or the event payload is malformed (check that `start_iso` and `end_iso` are valid ISO 8601 with time zone offsets).

**Tool call returns events but they look stale:** The Calendar API may take a few seconds to reflect newly added events. Retry after a short wait.

## Security notes

The token file at `<data_dir>/calendar-token.json` is as sensitive as your Google account session. Keep your data directory restrictive (the setup helper applies 0700-style permissions on POSIX systems). If the file leaks, revoke the grant at https://myaccount.google.com/permissions and re-run the bootstrap.

The OAuth client JSON is less sensitive but still secret; it identifies your application to Google. Do not commit it to version control.

> [!WARNING]
> Never commit `calendar-token.json` or your OAuth client JSON to a repository. Both belong in your data directory or another location outside source control.

## See also

- [Integrations overview](/integrations/overview/)
- [Email integration](/integrations/email/)
- [Configuration](/getting-started/configuration/)
- [Environment variables](/reference/environment-variables/)
