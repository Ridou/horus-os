"""Calendar adapter example: register tools and invoke list_calendar_events_today.

This example shows how to:

1. Stub the optional Google client modules (`google.auth.transport.requests`,
   `google.oauth2.credentials`, `googleapiclient.discovery`) via
   `sys.modules` injection so `CalendarAdapter` runs without the
   packages installed. The fake `events().list()` returns a canned
   items list so the structured tool result is deterministic.
2. Build an `AdapterContext` that carries a real `ToolRegistry` so
   `CalendarAdapter` has somewhere to register its agent-callable
   tools (this is the Phase 26 contract the Phase 27 dashboard wiring
   honors end to end).
3. Write a placeholder `calendar-token.json` into the data dir so the
   adapter's bootstrap check passes (the file is not actually read by
   the fake credentials class).
4. Call `bind`, then invoke the registered `list_calendar_events_today`
   tool via `tool_registry.invoke` the way the agent runtime would.

The script runs end to end with no Google credentials, no
`google-api-python-client` install, and no network.

For a live run set:

    HORUS_OS_CALENDAR_OAUTH_CLIENT_PATH=/path/to/your-oauth-client-here.json
    HORUS_OS_CALENDAR_WRITE_ALLOWED=true               # optional, gates create
    HORUS_OS_CALENDAR_AGENT_PROFILE=default            # optional

then `pip install 'horus-os[calendar]'`, run the one-time OAuth
bootstrap described in `docs/adapters/CALENDAR.md` to produce
`calendar-token.json` under the data directory, and `horus-os serve`.

Run it:

    python examples/calendar_adapter.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import types
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from horus_os import (
    AdapterContext,
    AdapterRegistry,
    Config,
    ToolRegistry,
)
from horus_os.adapters import CalendarAdapter


def _install_fake_google(list_response: dict[str, Any]) -> types.SimpleNamespace:
    """Inject fake `google.*` and `googleapiclient.*` modules.

    Returns handles exposing the captured `events().list()` kwargs.
    """
    handles = types.SimpleNamespace(build_calls=[], list_calls=[])

    google_pkg = types.ModuleType("google")
    google_auth = types.ModuleType("google.auth")
    google_auth_transport = types.ModuleType("google.auth.transport")
    google_auth_transport_requests = types.ModuleType("google.auth.transport.requests")

    class _Request:
        pass

    google_auth_transport_requests.Request = _Request
    google_pkg.auth = google_auth
    google_auth.transport = google_auth_transport
    google_auth_transport.requests = google_auth_transport_requests

    google_oauth2 = types.ModuleType("google.oauth2")
    google_oauth2_credentials = types.ModuleType("google.oauth2.credentials")
    google_pkg.oauth2 = google_oauth2
    google_oauth2.credentials = google_oauth2_credentials

    class _Credentials:
        def __init__(self) -> None:
            self.expired = False
            self.valid = True

        @classmethod
        def from_authorized_user_file(cls, path: str) -> _Credentials:
            return cls()

        def refresh(self, request: Any) -> None:  # pragma: no cover
            self.expired = False
            self.valid = True

    google_oauth2_credentials.Credentials = _Credentials

    googleapiclient_pkg = types.ModuleType("googleapiclient")
    googleapiclient_discovery = types.ModuleType("googleapiclient.discovery")
    googleapiclient_pkg.discovery = googleapiclient_discovery

    def _build(service: str, version: str, credentials: Any = None) -> Any:
        handles.build_calls.append((service, version))

        class _Execute:
            def __init__(self, payload: dict[str, Any]) -> None:
                self._payload = payload

            def execute(self) -> dict[str, Any]:
                return self._payload

        class _Events:
            def list(self, **kwargs: Any) -> Any:
                handles.list_calls.append(kwargs)
                return _Execute(list_response)

        class _Service:
            def events(self) -> _Events:
                return _Events()

        return _Service()

    googleapiclient_discovery.build = _build

    for name, module in [
        ("google", google_pkg),
        ("google.auth", google_auth),
        ("google.auth.transport", google_auth_transport),
        ("google.auth.transport.requests", google_auth_transport_requests),
        ("google.oauth2", google_oauth2),
        ("google.oauth2.credentials", google_oauth2_credentials),
        ("googleapiclient", googleapiclient_pkg),
        ("googleapiclient.discovery", googleapiclient_discovery),
    ]:
        sys.modules[name] = module

    return handles


def main() -> None:
    canned_items = [
        {
            "summary": "Morning standup",
            "start": {"dateTime": "2026-05-24T15:00:00Z"},
            "end": {"dateTime": "2026-05-24T15:30:00Z"},
            "location": "Conference room",
            "attendees": [
                {"email": "alice@example.test"},
                {"email": "bob@example.test"},
            ],
        },
        {
            "summary": "All-day offsite",
            "start": {"date": "2026-05-24"},
            "end": {"date": "2026-05-25"},
        },
    ]
    handles = _install_fake_google({"items": canned_items})

    os.environ["HORUS_OS_CALENDAR_OAUTH_CLIENT_PATH"] = "/path/to/your-oauth-client-here.json"

    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        config = Config.with_defaults(data_dir)
        config.save()

        # Drop a placeholder token. The fake `Credentials.from_authorized_user_file`
        # ignores the contents; the adapter only checks that the file exists.
        token_path = data_dir / "calendar-token.json"
        token_path.write_text(
            json.dumps(
                {
                    "token": "your-access-token-here",
                    "refresh_token": "your-refresh-token-here",
                    "client_id": "your-client-id-here",
                    "client_secret": "your-client-secret-here",
                }
            )
        )

        registry = AdapterRegistry()
        registry.register("calendar")
        tool_registry = ToolRegistry()
        ctx = AdapterContext(
            config=config,
            data_dir=data_dir,
            registry=registry,
            tool_registry=tool_registry,
        )

        adapter = CalendarAdapter()
        adapter.bind(MagicMock(), ctx)

        entry = registry.get("calendar")
        print(f"Adapter status after bind: {entry.status}")
        tool_names = sorted(t.name for t in tool_registry.list())
        print(f"Registered tools: {tool_names}")
        print()

        result = tool_registry.invoke("list_calendar_events_today", {})
        print("list_calendar_events_today result:")
        for event in result:
            print(f"  {event}")

        print()
        call = handles.list_calls[0]
        print("Google API events().list() call:")
        print(f"  calendarId   = {call['calendarId']!r}")
        print(f"  timeMin      = {call['timeMin']!r}")
        print(f"  timeMax      = {call['timeMax']!r}")
        print(f"  singleEvents = {call['singleEvents']!r}")
        print(f"  orderBy      = {call['orderBy']!r}")


if __name__ == "__main__":
    main()
