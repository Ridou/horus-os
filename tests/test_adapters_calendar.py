"""Tests for the Google Calendar adapter.

All tests run with `google-api-python-client` and
`google-auth-oauthlib` simulated via fake modules injected into
`sys.modules`. No live Google Calendar API call is made.

The Calendar adapter is the first tool-providing adapter; it
registers `list_calendar_events_today` (always) and
`create_calendar_event` (when `HORUS_OS_CALENDAR_WRITE_ALLOWED`
is exactly `"true"`) onto `AdapterContext.tool_registry`. Tests
construct an explicit `ToolRegistry` on the context and assert
on the registered tools.
"""

from __future__ import annotations

import json
import sys
import types
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from horus_os import Config
from horus_os.adapters import (
    ADAPTER_STATUS_ERROR,
    ADAPTER_STATUS_RUNNING,
    AdapterContext,
    AdapterRegistry,
    CalendarAdapter,
)
from horus_os.tools.registry import ToolRegistry

# -- fixtures -----------------------------------------------------------------


def _make_context(
    tmp_path: Path,
    *,
    include_tool_registry: bool = True,
) -> AdapterContext:
    """Build a registry + context with the adapter pre-registered."""
    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    reg = AdapterRegistry()
    reg.register("calendar")
    tool_reg = ToolRegistry() if include_tool_registry else None
    return AdapterContext(
        config=cfg,
        data_dir=tmp_path,
        registry=reg,
        tool_registry=tool_reg,
    )


def _write_fake_token(data_dir: Path) -> Path:
    """Drop a placeholder token file into the data dir."""
    token_path = data_dir / "calendar-token.json"
    token_path.write_text(
        json.dumps(
            {
                "token": "fake-access-token",
                "refresh_token": "fake-refresh-token",
                "client_id": "fake-client-id",
                "client_secret": "fake-client-secret",
            }
        )
    )
    return token_path


def _install_fake_google(
    monkeypatch: pytest.MonkeyPatch,
    *,
    token_state: str = "valid",
    list_response: dict | None = None,
    insert_response: dict | None = None,
    raise_on_list: Exception | None = None,
    raise_on_insert: Exception | None = None,
) -> types.SimpleNamespace:
    """Inject fake google.* and googleapiclient.* modules into sys.modules.

    `token_state`:
      - "valid": creds.expired is False; no refresh needed.
      - "expired": creds.expired is True; refresh succeeds.
      - "unrefreshable": creds.expired is True; refresh raises.

    Returns a SimpleNamespace exposing handles for assertions.
    """
    handles = types.SimpleNamespace(
        creds=None,
        refresh_calls=0,
        build_calls=[],
        list_calls=[],
        insert_calls=[],
        from_file_calls=[],
    )

    # google + google.auth + google.auth.transport + google.auth.transport.requests
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

    # google.oauth2 + google.oauth2.credentials
    google_oauth2 = types.ModuleType("google.oauth2")
    google_oauth2_credentials = types.ModuleType("google.oauth2.credentials")
    google_pkg.oauth2 = google_oauth2
    google_oauth2.credentials = google_oauth2_credentials

    class _Credentials:
        def __init__(self) -> None:
            self.expired = token_state == "expired" or token_state == "unrefreshable"
            self.valid = token_state == "valid"

        @classmethod
        def from_authorized_user_file(cls, path: str) -> _Credentials:
            handles.from_file_calls.append(path)
            inst = cls()
            handles.creds = inst
            return inst

        def refresh(self, request: Any) -> None:
            handles.refresh_calls += 1
            if token_state == "unrefreshable":
                raise RuntimeError("refresh token revoked")
            self.expired = False
            self.valid = True

    google_oauth2_credentials.Credentials = _Credentials

    # googleapiclient.discovery
    googleapiclient_pkg = types.ModuleType("googleapiclient")
    googleapiclient_discovery = types.ModuleType("googleapiclient.discovery")
    googleapiclient_errors = types.ModuleType("googleapiclient.errors")
    googleapiclient_pkg.discovery = googleapiclient_discovery
    googleapiclient_pkg.errors = googleapiclient_errors

    class _HttpError(Exception):
        pass

    googleapiclient_errors.HttpError = _HttpError

    _list_response = list_response if list_response is not None else {"items": []}
    _insert_response = insert_response if insert_response is not None else {"id": "fake-event-id"}

    def _build(service: str, version: str, credentials: Any = None) -> Any:
        handles.build_calls.append((service, version, credentials))

        class _Execute:
            def __init__(self, payload: dict | None, raiser: Exception | None) -> None:
                self._payload = payload
                self._raiser = raiser

            def execute(self) -> dict:
                if self._raiser is not None:
                    raise self._raiser
                return self._payload or {}

        class _Events:
            def list(self, **kwargs: Any) -> Any:
                handles.list_calls.append(kwargs)
                return _Execute(_list_response, raise_on_list)

            def insert(self, calendarId: str, body: dict) -> Any:
                handles.insert_calls.append({"calendarId": calendarId, "body": body})
                return _Execute(_insert_response, raise_on_insert)

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


def _block_google_imports(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force `from google.* import ...` to fail with ImportError."""
    for mod in (
        "google",
        "google.auth",
        "google.auth.transport",
        "google.auth.transport.requests",
        "google.oauth2",
        "google.oauth2.credentials",
        "googleapiclient",
        "googleapiclient.discovery",
        "googleapiclient.errors",
    ):
        monkeypatch.setitem(sys.modules, mod, None)


# -- construction -------------------------------------------------------------


def test_construct_clean_without_google_libs(monkeypatch: pytest.MonkeyPatch) -> None:
    """`CalendarAdapter()` works even when sys.modules has no google entries."""
    _block_google_imports(monkeypatch)
    adapter = CalendarAdapter()
    assert adapter.name == "calendar"
    assert adapter._creds is None
    assert adapter._context is None
    # describe is callable without raising.
    info = adapter.describe()
    assert info["name"] == "calendar"


# -- bind error paths ---------------------------------------------------------


def test_bind_with_no_tool_registry_marks_error(tmp_path: Path) -> None:
    """When tool_registry is None on the context, bind records a clear error."""
    ctx = _make_context(tmp_path, include_tool_registry=False)
    adapter = CalendarAdapter()
    adapter.bind(MagicMock(), ctx)
    entry = ctx.registry.get("calendar")
    assert entry is not None
    assert entry.status == ADAPTER_STATUS_ERROR
    assert "tool_registry" in (entry.error_message or "")


def test_bind_with_missing_sdk_marks_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _block_google_imports(monkeypatch)
    monkeypatch.setenv("HORUS_OS_CALENDAR_OAUTH_CLIENT_PATH", "/tmp/fake-client.json")
    ctx = _make_context(tmp_path)
    adapter = CalendarAdapter()
    adapter.bind(MagicMock(), ctx)
    entry = ctx.registry.get("calendar")
    assert entry.status == ADAPTER_STATUS_ERROR
    assert "google-api-python-client" in (entry.error_message or "")


def test_bind_with_missing_oauth_client_path_marks_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_google(monkeypatch)
    monkeypatch.delenv("HORUS_OS_CALENDAR_OAUTH_CLIENT_PATH", raising=False)
    ctx = _make_context(tmp_path)
    adapter = CalendarAdapter()
    adapter.bind(MagicMock(), ctx)
    entry = ctx.registry.get("calendar")
    assert entry.status == ADAPTER_STATUS_ERROR
    assert "HORUS_OS_CALENDAR_OAUTH_CLIENT_PATH" in (entry.error_message or "")


def test_bind_with_missing_token_file_marks_error_with_auth_hint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_google(monkeypatch)
    monkeypatch.setenv("HORUS_OS_CALENDAR_OAUTH_CLIENT_PATH", "/tmp/fake-client.json")
    # Do NOT write a token file into tmp_path.
    ctx = _make_context(tmp_path)
    adapter = CalendarAdapter()
    adapter.bind(MagicMock(), ctx)
    entry = ctx.registry.get("calendar")
    assert entry.status == ADAPTER_STATUS_ERROR
    assert "token file not found" in (entry.error_message or "")
    assert "OAuth bootstrap" in (entry.error_message or "")


def test_bind_with_expired_token_refreshes_then_proceeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    handles = _install_fake_google(monkeypatch, token_state="expired")
    monkeypatch.setenv("HORUS_OS_CALENDAR_OAUTH_CLIENT_PATH", "/tmp/fake-client.json")
    _write_fake_token(tmp_path)
    ctx = _make_context(tmp_path)
    adapter = CalendarAdapter()
    adapter.bind(MagicMock(), ctx)
    entry = ctx.registry.get("calendar")
    assert entry.status == ADAPTER_STATUS_RUNNING
    assert handles.refresh_calls == 1


def test_bind_with_unrefreshable_token_marks_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_google(monkeypatch, token_state="unrefreshable")
    monkeypatch.setenv("HORUS_OS_CALENDAR_OAUTH_CLIENT_PATH", "/tmp/fake-client.json")
    _write_fake_token(tmp_path)
    ctx = _make_context(tmp_path)
    adapter = CalendarAdapter()
    adapter.bind(MagicMock(), ctx)
    entry = ctx.registry.get("calendar")
    assert entry.status == ADAPTER_STATUS_ERROR
    assert "refresh failed" in (entry.error_message or "")


# -- bind happy paths ---------------------------------------------------------


def test_bind_happy_path_registers_list_tool_and_marks_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_google(monkeypatch)
    monkeypatch.setenv("HORUS_OS_CALENDAR_OAUTH_CLIENT_PATH", "/tmp/fake-client.json")
    monkeypatch.delenv("HORUS_OS_CALENDAR_WRITE_ALLOWED", raising=False)
    _write_fake_token(tmp_path)
    ctx = _make_context(tmp_path)
    adapter = CalendarAdapter()
    adapter.bind(MagicMock(), ctx)
    entry = ctx.registry.get("calendar")
    assert entry.status == ADAPTER_STATUS_RUNNING
    assert "list_calendar_events_today" in ctx.tool_registry
    assert "create_calendar_event" not in ctx.tool_registry


def test_create_tool_not_registered_when_flag_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_google(monkeypatch)
    monkeypatch.setenv("HORUS_OS_CALENDAR_OAUTH_CLIENT_PATH", "/tmp/fake-client.json")
    monkeypatch.delenv("HORUS_OS_CALENDAR_WRITE_ALLOWED", raising=False)
    _write_fake_token(tmp_path)
    ctx = _make_context(tmp_path)
    adapter = CalendarAdapter()
    adapter.bind(MagicMock(), ctx)
    assert "create_calendar_event" not in ctx.tool_registry


def test_create_tool_not_registered_when_flag_is_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_google(monkeypatch)
    monkeypatch.setenv("HORUS_OS_CALENDAR_OAUTH_CLIENT_PATH", "/tmp/fake-client.json")
    monkeypatch.setenv("HORUS_OS_CALENDAR_WRITE_ALLOWED", "false")
    _write_fake_token(tmp_path)
    ctx = _make_context(tmp_path)
    adapter = CalendarAdapter()
    adapter.bind(MagicMock(), ctx)
    assert "create_calendar_event" not in ctx.tool_registry


def test_create_tool_registered_when_flag_true(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_google(monkeypatch)
    monkeypatch.setenv("HORUS_OS_CALENDAR_OAUTH_CLIENT_PATH", "/tmp/fake-client.json")
    monkeypatch.setenv("HORUS_OS_CALENDAR_WRITE_ALLOWED", "true")
    _write_fake_token(tmp_path)
    ctx = _make_context(tmp_path)
    adapter = CalendarAdapter()
    adapter.bind(MagicMock(), ctx)
    assert "list_calendar_events_today" in ctx.tool_registry
    assert "create_calendar_event" in ctx.tool_registry


# -- tool call semantics ------------------------------------------------------


def test_list_events_returns_serialized_events_with_utc_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canned_items = [
        {
            "summary": "Morning standup",
            "start": {"dateTime": "2026-05-24T15:00:00Z"},
            "end": {"dateTime": "2026-05-24T15:30:00Z"},
            "location": "Conference room",
            "attendees": [{"email": "alice@example.test"}, {"email": "bob@example.test"}],
        },
        {
            "summary": "All-day offsite",
            "start": {"date": "2026-05-24"},
            "end": {"date": "2026-05-25"},
            # No location, no attendees.
        },
    ]
    handles = _install_fake_google(monkeypatch, list_response={"items": canned_items})
    monkeypatch.setenv("HORUS_OS_CALENDAR_OAUTH_CLIENT_PATH", "/tmp/fake-client.json")
    _write_fake_token(tmp_path)
    ctx = _make_context(tmp_path)
    adapter = CalendarAdapter()
    adapter.bind(MagicMock(), ctx)

    result = ctx.tool_registry.invoke("list_calendar_events_today", {})
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0] == {
        "summary": "Morning standup",
        "start": "2026-05-24T15:00:00Z",
        "end": "2026-05-24T15:30:00Z",
        "location": "Conference room",
        "attendees": ["alice@example.test", "bob@example.test"],
    }
    # All-day event falls back to `date` instead of `dateTime`.
    assert result[1]["start"] == "2026-05-24"
    assert result[1]["end"] == "2026-05-25"
    assert result[1]["attendees"] == []

    # The list call used a UTC today window and singleEvents=True + orderBy=startTime.
    assert handles.list_calls
    call = handles.list_calls[0]
    assert call["calendarId"] == "primary"
    assert call["singleEvents"] is True
    assert call["orderBy"] == "startTime"
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    assert call["timeMin"].startswith(today)
    assert call["timeMin"].endswith("00:00:00+00:00")
    assert call["timeMax"].startswith(today)
    assert call["timeMax"].endswith("23:59:59+00:00")


def test_list_events_touches_registry_on_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_google(monkeypatch, list_response={"items": []})
    monkeypatch.setenv("HORUS_OS_CALENDAR_OAUTH_CLIENT_PATH", "/tmp/fake-client.json")
    _write_fake_token(tmp_path)
    ctx = _make_context(tmp_path)
    adapter = CalendarAdapter()
    adapter.bind(MagicMock(), ctx)
    assert ctx.registry.get("calendar").last_activity_at is None
    ctx.tool_registry.invoke("list_calendar_events_today", {})
    assert ctx.registry.get("calendar").last_activity_at is not None


def test_list_events_api_error_returns_error_dict_and_marks_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_google(monkeypatch, raise_on_list=RuntimeError("api unavailable"))
    monkeypatch.setenv("HORUS_OS_CALENDAR_OAUTH_CLIENT_PATH", "/tmp/fake-client.json")
    _write_fake_token(tmp_path)
    ctx = _make_context(tmp_path)
    adapter = CalendarAdapter()
    adapter.bind(MagicMock(), ctx)

    result = ctx.tool_registry.invoke("list_calendar_events_today", {})
    assert isinstance(result, list)
    assert len(result) == 1
    assert "error" in result[0]
    assert "RuntimeError" in result[0]["error"]
    entry = ctx.registry.get("calendar")
    assert entry.error_count >= 1
    assert "RuntimeError" in (entry.error_message or "")


def test_create_event_calls_insert_with_right_body_and_returns_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canned = {
        "id": "evt-123",
        "summary": "Lunch",
        "htmlLink": "https://example.test/event/evt-123",
    }
    handles = _install_fake_google(monkeypatch, insert_response=canned)
    monkeypatch.setenv("HORUS_OS_CALENDAR_OAUTH_CLIENT_PATH", "/tmp/fake-client.json")
    monkeypatch.setenv("HORUS_OS_CALENDAR_WRITE_ALLOWED", "true")
    _write_fake_token(tmp_path)
    ctx = _make_context(tmp_path)
    adapter = CalendarAdapter()
    adapter.bind(MagicMock(), ctx)

    result = ctx.tool_registry.invoke(
        "create_calendar_event",
        {
            "summary": "Lunch",
            "start_iso": "2026-05-24T12:00:00-07:00",
            "end_iso": "2026-05-24T13:00:00-07:00",
            "description": "Catch up over noodles.",
        },
    )
    assert result == canned
    assert handles.insert_calls
    call = handles.insert_calls[0]
    assert call["calendarId"] == "primary"
    body = call["body"]
    assert body["summary"] == "Lunch"
    assert body["start"] == {"dateTime": "2026-05-24T12:00:00-07:00"}
    assert body["end"] == {"dateTime": "2026-05-24T13:00:00-07:00"}
    assert body["description"] == "Catch up over noodles."


def test_create_event_handler_rechecks_flag_at_call_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Flipping the flag off after bind disables writes immediately."""
    _install_fake_google(monkeypatch)
    monkeypatch.setenv("HORUS_OS_CALENDAR_OAUTH_CLIENT_PATH", "/tmp/fake-client.json")
    monkeypatch.setenv("HORUS_OS_CALENDAR_WRITE_ALLOWED", "true")
    _write_fake_token(tmp_path)
    ctx = _make_context(tmp_path)
    adapter = CalendarAdapter()
    adapter.bind(MagicMock(), ctx)
    assert "create_calendar_event" in ctx.tool_registry

    # Flip the flag off mid-run. Tool stays registered but handler refuses.
    monkeypatch.setenv("HORUS_OS_CALENDAR_WRITE_ALLOWED", "false")
    result = ctx.tool_registry.invoke(
        "create_calendar_event",
        {
            "summary": "Lunch",
            "start_iso": "2026-05-24T12:00:00Z",
            "end_iso": "2026-05-24T13:00:00Z",
        },
    )
    assert isinstance(result, dict)
    assert "error" in result
    assert "HORUS_OS_CALENDAR_WRITE_ALLOWED" in result["error"]


def test_create_event_api_error_returns_error_dict_and_marks_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_google(monkeypatch, raise_on_insert=RuntimeError("calendar not found"))
    monkeypatch.setenv("HORUS_OS_CALENDAR_OAUTH_CLIENT_PATH", "/tmp/fake-client.json")
    monkeypatch.setenv("HORUS_OS_CALENDAR_WRITE_ALLOWED", "true")
    _write_fake_token(tmp_path)
    ctx = _make_context(tmp_path)
    adapter = CalendarAdapter()
    adapter.bind(MagicMock(), ctx)

    result = ctx.tool_registry.invoke(
        "create_calendar_event",
        {
            "summary": "Lunch",
            "start_iso": "2026-05-24T12:00:00Z",
            "end_iso": "2026-05-24T13:00:00Z",
        },
    )
    assert isinstance(result, dict)
    assert "error" in result
    assert "RuntimeError" in result["error"]
    entry = ctx.registry.get("calendar")
    assert entry.error_count >= 1
    assert "RuntimeError" in (entry.error_message or "")
