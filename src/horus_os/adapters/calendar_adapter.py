"""Google Calendar adapter for horus-os.

Unlike the Discord, Slack, and Email adapters that route inbound
events into `run_agent`, the Calendar adapter is a tool provider:
it registers agent-callable tools onto the master tool registry
during `bind` and does no background work after that.

Tools exposed:

- `list_calendar_events_today(calendar_id="primary") -> list[dict]`
  Always registered when bind succeeds.
- `create_calendar_event(summary, start_iso, end_iso, ...) -> dict`
  Registered only when `HORUS_OS_CALENDAR_WRITE_ALLOWED == "true"`.

The `google-api-python-client` and `google-auth-oauthlib` imports
are lazy inside `bind` and the tool factories so this module
imports cleanly when the optional extra is not installed. Tests
inject fake modules into `sys.modules` to exercise the adapter
without the SDK on the path.

Configuration via environment variables:

- `HORUS_OS_CALENDAR_OAUTH_CLIENT_PATH`: Path to the OAuth client
  secret JSON downloaded from Google Cloud. Required.
- `HORUS_OS_CALENDAR_WRITE_ALLOWED`: When exactly the string
  `"true"`, the create-event tool is registered. Unset / any
  other value means read-only.

The OAuth refreshable token lives at
`config.data_dir / "calendar-token.json"`. The setup guide at
`docs/adapters/CALENDAR.md` documents the one-time bootstrap
that writes this file.

The adapter satisfies the `Adapter` Protocol (name, bind). It
does NOT implement `LifecycleAdapter`; there is no background
task to start or drain.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from horus_os.adapters.base import AdapterContext
from horus_os.types import Tool

OAUTH_CLIENT_PATH_ENV = "HORUS_OS_CALENDAR_OAUTH_CLIENT_PATH"
WRITE_ALLOWED_ENV = "HORUS_OS_CALENDAR_WRITE_ALLOWED"
TOKEN_FILENAME = "calendar-token.json"
CALENDAR_API_NAME = "calendar"
CALENDAR_API_VERSION = "v3"


class CalendarAdapter:
    """A tool-providing adapter for Google Calendar."""

    name = "calendar"

    def __init__(self) -> None:
        # All Google-side state is allocated in `bind` so the
        # constructor stays cheap and import-clean.
        self._creds: Any = None
        self._context: AdapterContext | None = None

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": 1,
            "transport": "google-calendar-api",
            "auth": "oauth2-installed-app",
            "env": OAUTH_CLIENT_PATH_ENV,
        }

    def bind(self, app: Any, context: AdapterContext) -> None:
        """Load credentials and register the calendar tools.

        Failure modes (missing dependency, missing env vars,
        missing token, refresh failure) flip the registry entry to
        `error` and return without raising so other adapters keep
        running.
        """
        context.registry.register(self.name)
        self._context = context

        if context.tool_registry is None:
            context.registry.mark_error(
                self.name,
                (
                    "AdapterContext.tool_registry is None; the Calendar adapter "
                    "needs a ToolRegistry on the context to register its tools"
                ),
            )
            return

        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
        except ImportError:
            context.registry.mark_error(
                self.name,
                (
                    "google-api-python-client / google-auth-oauthlib are not "
                    "installed; pip install 'horus-os[calendar]'"
                ),
            )
            return

        client_path = os.environ.get(OAUTH_CLIENT_PATH_ENV)
        if not client_path:
            context.registry.mark_error(
                self.name,
                (
                    f"{OAUTH_CLIENT_PATH_ENV} is not set; download the OAuth "
                    "client JSON from Google Cloud and point this env var at it"
                ),
            )
            return

        token_path = Path(context.data_dir) / TOKEN_FILENAME
        if not token_path.exists():
            context.registry.mark_error(
                self.name,
                (
                    f"calendar token file not found at {token_path}; run the "
                    "OAuth bootstrap (see docs/adapters/CALENDAR.md)"
                ),
            )
            return

        try:
            creds = Credentials.from_authorized_user_file(str(token_path))
        except Exception as exc:
            context.registry.mark_error(
                self.name,
                f"failed to load calendar token: {type(exc).__name__}: {exc}",
            )
            return

        if getattr(creds, "expired", False):
            try:
                creds.refresh(Request())
            except Exception as exc:
                context.registry.mark_error(
                    self.name,
                    f"calendar token refresh failed: {type(exc).__name__}: {exc}",
                )
                return

        self._creds = creds
        context.tool_registry.register(_list_events_tool(self), replace=True)
        if os.environ.get(WRITE_ALLOWED_ENV) == "true":
            context.tool_registry.register(_create_event_tool(self), replace=True)
        context.registry.mark_running(self.name)


def _today_utc_window() -> tuple[str, str]:
    """Return iso8601 (start, end) for the current UTC day, inclusive."""
    now = datetime.now(UTC)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = now.replace(hour=23, minute=59, second=59, microsecond=0)
    return start.isoformat(), end.isoformat()


def _serialize_event(item: dict[str, Any]) -> dict[str, Any]:
    """Project a Google Calendar event payload to the tool result shape."""
    start = item.get("start") or {}
    end = item.get("end") or {}
    raw_attendees = item.get("attendees") or []
    attendees = [att.get("email", "") for att in raw_attendees if isinstance(att, dict)]
    return {
        "summary": item.get("summary", "") or "",
        "start": start.get("dateTime") or start.get("date", "") or "",
        "end": end.get("dateTime") or end.get("date", "") or "",
        "location": item.get("location", "") or "",
        "attendees": attendees,
    }


_LIST_PARAMETERS: dict = {
    "type": "object",
    "properties": {
        "calendar_id": {
            "type": "string",
            "description": ("Google Calendar ID. Defaults to the user's primary calendar."),
        },
    },
    "required": [],
}

_CREATE_PARAMETERS: dict = {
    "type": "object",
    "properties": {
        "summary": {
            "type": "string",
            "description": "Event title.",
        },
        "start_iso": {
            "type": "string",
            "description": (
                "Event start time in ISO 8601 format including timezone "
                "offset, for example 2026-05-24T15:00:00-07:00."
            ),
        },
        "end_iso": {
            "type": "string",
            "description": "Event end time in ISO 8601 format including timezone offset.",
        },
        "calendar_id": {
            "type": "string",
            "description": "Calendar ID. Defaults to the user's primary calendar.",
        },
        "description": {
            "type": "string",
            "description": "Optional event description.",
        },
    },
    "required": ["summary", "start_iso", "end_iso"],
}


def _list_events_tool(adapter: CalendarAdapter) -> Tool:
    """Build the `list_calendar_events_today` tool, closed over the adapter."""

    def handler(calendar_id: str = "primary") -> list[dict[str, Any]]:
        # Lazy import so this module loads without the SDK installed.
        from googleapiclient.discovery import build

        ctx = adapter._context
        try:
            start_iso, end_iso = _today_utc_window()
            service = build(CALENDAR_API_NAME, CALENDAR_API_VERSION, credentials=adapter._creds)
            response = (
                service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=start_iso,
                    timeMax=end_iso,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            items = response.get("items", []) or []
            events = [_serialize_event(item) for item in items]
            if ctx is not None:
                ctx.registry.touch(adapter.name)
            return events
        except Exception as exc:
            if ctx is not None:
                ctx.registry.mark_error(adapter.name, f"{type(exc).__name__}: {exc}")
            return [{"error": f"{type(exc).__name__}: {exc}"}]

    return Tool(
        name="list_calendar_events_today",
        description=(
            "List today's events from the configured Google Calendar. "
            "Returns a list of objects with summary, start, end, location, "
            "and attendees. The window is the current UTC day."
        ),
        parameters=_LIST_PARAMETERS,
        handler=handler,
    )


def _create_event_tool(adapter: CalendarAdapter) -> Tool:
    """Build the `create_calendar_event` tool, closed over the adapter.

    The handler re-checks `HORUS_OS_CALENDAR_WRITE_ALLOWED` at call
    time so an operator who flips the flag off mid-run gets the
    deny path even though the tool was already registered.
    """

    def handler(
        summary: str,
        start_iso: str,
        end_iso: str,
        calendar_id: str = "primary",
        description: str | None = None,
    ) -> dict[str, Any]:
        if os.environ.get(WRITE_ALLOWED_ENV) != "true":
            return {
                "error": (f"calendar write not allowed; set {WRITE_ALLOWED_ENV}=true to enable")
            }
        from googleapiclient.discovery import build

        ctx = adapter._context
        try:
            service = build(CALENDAR_API_NAME, CALENDAR_API_VERSION, credentials=adapter._creds)
            body: dict[str, Any] = {
                "summary": summary,
                "start": {"dateTime": start_iso},
                "end": {"dateTime": end_iso},
            }
            if description is not None:
                body["description"] = description
            response = service.events().insert(calendarId=calendar_id, body=body).execute()
            if ctx is not None:
                ctx.registry.touch(adapter.name)
            return response if isinstance(response, dict) else {"result": response}
        except Exception as exc:
            if ctx is not None:
                ctx.registry.mark_error(adapter.name, f"{type(exc).__name__}: {exc}")
            return {"error": f"{type(exc).__name__}: {exc}"}

    return Tool(
        name="create_calendar_event",
        description=(
            "Create a single event on the configured Google Calendar. "
            f"Requires {WRITE_ALLOWED_ENV}=true."
        ),
        parameters=_CREATE_PARAMETERS,
        handler=handler,
    )
