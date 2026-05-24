"""Calendar tool wiring end-to-end through create_app + discover_adapters.

Phase 29 gaps E and F: Phase 26 covered `CalendarAdapter.bind` with
an explicit `AdapterContext.tool_registry`; Phase 27 covered a
stub `_ToolProvidingAdapter` going through `create_app`. No test
combined the two: the real `CalendarAdapter` discovered via a
stubbed entry point, bound through `create_app`, registering tools
onto `app.state.tool_registry`, and invoked through that registry.

These tests close that seam for both the read-only path
(`list_calendar_events_today`, always registered) and the
write-gated path (`create_calendar_event`, gated on
`HORUS_OS_CALENDAR_WRITE_ALLOWED=true`).
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import Any

import pytest

from horus_os import Config, Database, create_app
from horus_os.adapters import (
    ADAPTER_ENTRY_POINT_GROUP,
    ADAPTER_STATUS_RUNNING,
    CalendarAdapter,
)
from horus_os.adapters import base as adapters_base

# -- helpers -------------------------------------------------------------------


class _FakeEntryPoint:
    def __init__(self, name: str, target: Any) -> None:
        self.name = name
        self._target = target

    def load(self) -> Any:
        return self._target


def _stub_entry_points(monkeypatch: pytest.MonkeyPatch, eps: list[_FakeEntryPoint]) -> None:
    def fake(group: str | None = None) -> list[_FakeEntryPoint]:
        if group != ADAPTER_ENTRY_POINT_GROUP:
            return []
        return eps

    monkeypatch.setattr(adapters_base, "entry_points", fake)


def _init_db(tmp_path: Path) -> None:
    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    db = Database(cfg.db_path)
    db.init()


def _write_fake_token(data_dir: Path) -> None:
    """Drop a placeholder Google OAuth token JSON into the data dir."""
    (data_dir / "calendar-token.json").write_text(
        json.dumps(
            {
                "token": "fake-access-token",
                "refresh_token": "fake-refresh-token",
                "client_id": "fake-client-id",
                "client_secret": "fake-client-secret",
            }
        )
    )


def _install_fake_google(
    monkeypatch: pytest.MonkeyPatch,
    *,
    list_response: dict | None = None,
    insert_response: dict | None = None,
) -> types.SimpleNamespace:
    """Inject fake google.* and googleapiclient.* modules into sys.modules.

    Slim variant of the helper in tests/test_adapters_calendar.py: only
    the surface these wiring tests need. The token state is always
    `valid` so bind succeeds without exercising the refresh path
    (already covered by Phase 26).
    """
    handles = types.SimpleNamespace(list_calls=[], insert_calls=[])

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

        def refresh(self, request: Any) -> None:
            return None

    google_oauth2_credentials.Credentials = _Credentials

    googleapiclient_pkg = types.ModuleType("googleapiclient")
    googleapiclient_discovery = types.ModuleType("googleapiclient.discovery")
    googleapiclient_errors = types.ModuleType("googleapiclient.errors")
    googleapiclient_pkg.discovery = googleapiclient_discovery
    googleapiclient_pkg.errors = googleapiclient_errors

    class _HttpError(Exception):
        pass

    googleapiclient_errors.HttpError = _HttpError

    _list_payload = list_response if list_response is not None else {"items": []}
    _insert_payload = insert_response if insert_response is not None else {"id": "fake-event-id"}

    def _build(service: str, version: str, credentials: Any = None) -> Any:
        class _Execute:
            def __init__(self, payload: dict) -> None:
                self._payload = payload

            def execute(self) -> dict:
                return self._payload

        class _Events:
            def list(self, **kwargs: Any) -> Any:
                handles.list_calls.append(kwargs)
                return _Execute(_list_payload)

            def insert(self, calendarId: str, body: dict) -> Any:
                handles.insert_calls.append({"calendarId": calendarId, "body": body})
                return _Execute(_insert_payload)

        class _Service:
            def events(self) -> _Events:
                return _Events()

        return _Service()

    googleapiclient_discovery.build = _build

    monkeypatch.setitem(sys.modules, "google", google_pkg)
    monkeypatch.setitem(sys.modules, "google.auth", google_auth)
    monkeypatch.setitem(sys.modules, "google.auth.transport", google_auth_transport)
    monkeypatch.setitem(
        sys.modules, "google.auth.transport.requests", google_auth_transport_requests
    )
    monkeypatch.setitem(sys.modules, "google.oauth2", google_oauth2)
    monkeypatch.setitem(sys.modules, "google.oauth2.credentials", google_oauth2_credentials)
    monkeypatch.setitem(sys.modules, "googleapiclient", googleapiclient_pkg)
    monkeypatch.setitem(sys.modules, "googleapiclient.discovery", googleapiclient_discovery)
    monkeypatch.setitem(sys.modules, "googleapiclient.errors", googleapiclient_errors)

    return handles


def _prep_calendar_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    write_allowed: str | None = None,
) -> None:
    """Common setup for a calendar-via-create_app test."""
    _init_db(tmp_path)
    monkeypatch.setenv("HORUS_OS_CALENDAR_OAUTH_CLIENT_PATH", "/tmp/fake-client.json")
    if write_allowed is None:
        monkeypatch.delenv("HORUS_OS_CALENDAR_WRITE_ALLOWED", raising=False)
    else:
        monkeypatch.setenv("HORUS_OS_CALENDAR_WRITE_ALLOWED", write_allowed)
    _write_fake_token(tmp_path)


# -- tests ---------------------------------------------------------------------


def test_calendar_list_tool_registered_on_app_state_via_discover_adapters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """create_app + CalendarAdapter -> app.state.tool_registry holds list tool.

    Gap E: prior tests bind CalendarAdapter with an explicit
    AdapterContext.tool_registry, never via the create_app
    discover_adapters path. This test confirms the discovery-to-
    bind-to-app-state plumbing works end-to-end.
    """
    _prep_calendar_env(tmp_path, monkeypatch)
    _install_fake_google(monkeypatch)
    _stub_entry_points(monkeypatch, [_FakeEntryPoint("calendar", CalendarAdapter)])
    app = create_app(data_dir=tmp_path)

    tools = {t.name for t in app.state.tool_registry.list()}
    assert "list_calendar_events_today" in tools
    # Write tool stays off by default; the gate test below covers the
    # registered case explicitly.
    assert "create_calendar_event" not in tools

    registry = app.state.adapter_registry
    entry = registry.get("calendar")
    assert entry is not None
    assert entry.status == ADAPTER_STATUS_RUNNING


def test_calendar_list_tool_invocable_through_app_state_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Invoking the registered tool returns serialized events.

    Gap E continued: the tool reaches app.state.tool_registry AND
    is callable through that registry with the same shape Phase 26
    tests exercise on a hand-built registry. Confirms the wiring
    does not interfere with handler closure state.
    """
    _prep_calendar_env(tmp_path, monkeypatch)
    canned = {
        "items": [
            {
                "summary": "Standup",
                "start": {"dateTime": "2026-05-24T09:00:00Z"},
                "end": {"dateTime": "2026-05-24T09:15:00Z"},
                "location": "Zoom",
                "attendees": [{"email": "ops@example.test"}],
            }
        ]
    }
    handles = _install_fake_google(monkeypatch, list_response=canned)
    _stub_entry_points(monkeypatch, [_FakeEntryPoint("calendar", CalendarAdapter)])
    app = create_app(data_dir=tmp_path)

    result = app.state.tool_registry.invoke("list_calendar_events_today", {})
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0] == {
        "summary": "Standup",
        "start": "2026-05-24T09:00:00Z",
        "end": "2026-05-24T09:15:00Z",
        "location": "Zoom",
        "attendees": ["ops@example.test"],
    }
    assert handles.list_calls
    assert handles.list_calls[0]["calendarId"] == "primary"


def test_calendar_create_tool_registered_when_flag_true_via_create_app(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gap F: WRITE_ALLOWED=true puts create_calendar_event on app state.

    The handler then routes through the fake build to return the
    insert response, proving the env gate is honored at the
    discover_adapters boundary (not just on a hand-built context).
    """
    _prep_calendar_env(tmp_path, monkeypatch, write_allowed="true")
    canned_insert = {"id": "evt-99", "summary": "Lunch", "htmlLink": "https://example.test/evt-99"}
    handles = _install_fake_google(monkeypatch, insert_response=canned_insert)
    _stub_entry_points(monkeypatch, [_FakeEntryPoint("calendar", CalendarAdapter)])
    app = create_app(data_dir=tmp_path)

    tools = {t.name for t in app.state.tool_registry.list()}
    assert "list_calendar_events_today" in tools
    assert "create_calendar_event" in tools

    result = app.state.tool_registry.invoke(
        "create_calendar_event",
        {
            "summary": "Lunch",
            "start_iso": "2026-05-24T12:00:00-07:00",
            "end_iso": "2026-05-24T13:00:00-07:00",
        },
    )
    assert result == canned_insert
    assert handles.insert_calls
    assert handles.insert_calls[0]["calendarId"] == "primary"
    assert handles.insert_calls[0]["body"]["summary"] == "Lunch"


def test_calendar_create_tool_off_when_flag_not_true_via_create_app(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gap F: WRITE_ALLOWED unset OR any non-`true` value keeps create off.

    Two parametric checks in one test: unset and the literal string
    `false`. The discover_adapters path must not silently register
    the write tool when the flag is anything other than exactly
    `true`.
    """
    # Variant 1: unset.
    _prep_calendar_env(tmp_path, monkeypatch)
    _install_fake_google(monkeypatch)
    _stub_entry_points(monkeypatch, [_FakeEntryPoint("calendar", CalendarAdapter)])
    app = create_app(data_dir=tmp_path)
    tools = {t.name for t in app.state.tool_registry.list()}
    assert "create_calendar_event" not in tools

    # Variant 2: explicit `false`. Build a fresh tmp_path so a new
    # create_app sees a clean app.state.tool_registry.
    tmp2 = tmp_path / "second"
    tmp2.mkdir()
    _prep_calendar_env(tmp2, monkeypatch, write_allowed="false")
    _install_fake_google(monkeypatch)
    _stub_entry_points(monkeypatch, [_FakeEntryPoint("calendar", CalendarAdapter)])
    app2 = create_app(data_dir=tmp2)
    tools2 = {t.name for t in app2.state.tool_registry.list()}
    assert "create_calendar_event" not in tools2
