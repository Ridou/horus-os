"""Tests for the voice / reservations adapter.

The Twilio SDK is simulated via a fake ``twilio`` package injected into
``sys.modules``; no live call is ever placed. The adapter is a
tool-providing adapter (like Calendar) that also mounts a few HTTP
routes, so tests build an explicit ToolRegistry on the context and use a
FastAPI TestClient for the routes.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from horus_os import Config
from horus_os.adapters import (
    ADAPTER_STATUS_ERROR,
    ADAPTER_STATUS_RUNNING,
    AdapterContext,
    AdapterRegistry,
    VoiceAdapter,
)
from horus_os.adapters.voice_adapter import (
    VoiceCallStore,
    classify_call_outcome,
)
from horus_os.tools.registry import ToolRegistry
from horus_os.types import Tool

# -- fixtures -----------------------------------------------------------------


def _make_context(tmp_path: Path, *, include_tool_registry: bool = True) -> AdapterContext:
    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    reg = AdapterRegistry()
    reg.register("voice")
    tool_reg = ToolRegistry() if include_tool_registry else None
    return AdapterContext(
        config=cfg,
        data_dir=tmp_path,
        registry=reg,
        tool_registry=tool_reg,
    )


def _install_fake_twilio(
    monkeypatch: pytest.MonkeyPatch,
    *,
    sid: str = "CA0001",
    raise_on_create: Exception | None = None,
) -> types.SimpleNamespace:
    """Inject a fake ``twilio`` + ``twilio.rest`` into sys.modules."""
    handles = types.SimpleNamespace(create_calls=[], clients=[])

    twilio_pkg = types.ModuleType("twilio")
    twilio_rest = types.ModuleType("twilio.rest")

    class _Call:
        def __init__(self, call_sid: str) -> None:
            self.sid = call_sid

    class _Calls:
        def create(self, **kwargs: Any) -> _Call:
            handles.create_calls.append(kwargs)
            if raise_on_create is not None:
                raise raise_on_create
            return _Call(sid)

    class _Client:
        def __init__(self, account_sid: Any = None, auth_token: Any = None) -> None:
            handles.clients.append((account_sid, auth_token))
            self.calls = _Calls()

    twilio_rest.Client = _Client
    twilio_pkg.rest = twilio_rest
    monkeypatch.setitem(sys.modules, "twilio", twilio_pkg)
    monkeypatch.setitem(sys.modules, "twilio.rest", twilio_rest)
    return handles


def _configure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HORUS_OS_TWILIO_ACCOUNT_SID", "AC_fake")
    monkeypatch.setenv("HORUS_OS_TWILIO_AUTH_TOKEN", "tok_fake")
    monkeypatch.setenv("HORUS_OS_TWILIO_FROM_NUMBER", "+15005550006")


# -- import / bind posture ----------------------------------------------------


def test_module_imports_and_exports_adapter() -> None:
    # The module top-level imports only stdlib + horus_os, so it loads
    # without twilio present.
    assert VoiceAdapter().name == "voice"


def test_bind_marks_error_without_twilio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Force `import twilio` to fail regardless of what is installed.
    monkeypatch.setitem(sys.modules, "twilio", None)
    _configure(monkeypatch)
    ctx = _make_context(tmp_path)
    app = FastAPI()
    VoiceAdapter().bind(app, ctx)
    entry = ctx.registry.get("voice")
    assert entry is not None
    assert entry.status == ADAPTER_STATUS_ERROR
    assert "horus-os[voice]" in (entry.error_message or "")
    # No tools registered on the bad path.
    assert "request_reservation_call" not in ctx.tool_registry


def test_bind_marks_error_without_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_twilio(monkeypatch)
    monkeypatch.delenv("HORUS_OS_TWILIO_ACCOUNT_SID", raising=False)
    monkeypatch.delenv("HORUS_OS_TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("HORUS_OS_TWILIO_FROM_NUMBER", raising=False)
    ctx = _make_context(tmp_path)
    VoiceAdapter().bind(FastAPI(), ctx)
    entry = ctx.registry.get("voice")
    assert entry is not None and entry.status == ADAPTER_STATUS_ERROR
    assert "not configured" in (entry.error_message or "")
    assert "request_reservation_call" not in ctx.tool_registry


def test_bind_registers_tools_when_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_twilio(monkeypatch)
    _configure(monkeypatch)
    ctx = _make_context(tmp_path)
    VoiceAdapter().bind(FastAPI(), ctx)
    entry = ctx.registry.get("voice")
    assert entry is not None and entry.status == ADAPTER_STATUS_RUNNING
    assert "request_reservation_call" in ctx.tool_registry
    assert "get_reservation_calls" in ctx.tool_registry


# -- ask-first rail + call placement ------------------------------------------


def test_request_call_blocked_until_calls_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    handles = _install_fake_twilio(monkeypatch)
    _configure(monkeypatch)
    monkeypatch.setenv("HORUS_OS_VOICE_PUBLIC_BASE_URL", "https://pub.example")
    monkeypatch.delenv("HORUS_OS_VOICE_CALLS_ALLOWED", raising=False)
    ctx = _make_context(tmp_path)
    VoiceAdapter().bind(FastAPI(), ctx)

    result = ctx.tool_registry.invoke(
        "request_reservation_call",
        {
            "venue_name": "Test Bistro",
            "to_number": "+14155551234",
            "reservation_datetime": "2026-06-10T19:00:00+00:00",
        },
    )
    assert "error" in result
    assert "VOICE_CALLS_ALLOWED" in result["error"]
    # The ask-first rail must short-circuit BEFORE any call is placed.
    assert handles.create_calls == []


def test_request_call_requires_public_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    handles = _install_fake_twilio(monkeypatch)
    _configure(monkeypatch)
    monkeypatch.setenv("HORUS_OS_VOICE_CALLS_ALLOWED", "true")
    monkeypatch.delenv("HORUS_OS_VOICE_PUBLIC_BASE_URL", raising=False)
    ctx = _make_context(tmp_path)
    VoiceAdapter().bind(FastAPI(), ctx)

    result = ctx.tool_registry.invoke(
        "request_reservation_call",
        {
            "venue_name": "Test Bistro",
            "to_number": "+14155551234",
            "reservation_datetime": "2026-06-10T19:00:00+00:00",
        },
    )
    assert "error" in result and "PUBLIC_BASE_URL" in result["error"]
    assert handles.create_calls == []


def test_request_call_places_call_and_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    handles = _install_fake_twilio(monkeypatch, sid="CA_live_1")
    _configure(monkeypatch)
    monkeypatch.setenv("HORUS_OS_VOICE_CALLS_ALLOWED", "true")
    monkeypatch.setenv("HORUS_OS_VOICE_PUBLIC_BASE_URL", "https://pub.example")
    ctx = _make_context(tmp_path)
    VoiceAdapter().bind(FastAPI(), ctx)

    result = ctx.tool_registry.invoke(
        "request_reservation_call",
        {
            "venue_name": "Test Bistro",
            "to_number": "+14155551234",
            "reservation_datetime": "2026-06-10T19:00:00+00:00",
            "party_size": 4,
            "caller_name": "Sam",
        },
    )
    assert result.get("call_sid") == "CA_live_1"
    assert result.get("status") == "ringing"
    # Exactly one outbound call, to the right number, from the configured id.
    assert len(handles.create_calls) == 1
    placed = handles.create_calls[0]
    assert placed["to"] == "+14155551234"
    assert placed["from_"] == "+15005550006"
    assert "pub.example/api/adapters/voice/twiml" in placed["url"]
    # The call is recorded and retrievable via the read tool.
    calls = ctx.tool_registry.invoke("get_reservation_calls", {})
    assert len(calls) == 1
    assert calls[0]["venue_name"] == "Test Bistro"
    assert calls[0]["party_size"] == 4


# -- outcome classification ---------------------------------------------------


@pytest.mark.parametrize(
    ("transcript", "expected"),
    [
        ("Great, your table is confirmed for four at seven.", "confirmed"),
        ("I am sorry, we are fully booked tonight.", "declined"),
        ("Let me check and call you back in a moment.", "callback"),
        ("Mmm, hello? Who is this?", "unclear"),
    ],
)
def test_classify_call_outcome(transcript: str, expected: str) -> None:
    assert classify_call_outcome(transcript)["status"] == expected


# -- routes -------------------------------------------------------------------


def _bound_client(tmp_path: Path, ctx: AdapterContext) -> TestClient:
    app = FastAPI()
    VoiceAdapter().bind(app, ctx)
    return TestClient(app)


def test_status_route_reports_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_twilio(monkeypatch)
    _configure(monkeypatch)
    monkeypatch.setenv("HORUS_OS_VOICE_CALLS_ALLOWED", "true")
    monkeypatch.setenv("HORUS_OS_VOICE_PUBLIC_BASE_URL", "https://pub.example")
    ctx = _make_context(tmp_path)
    client = _bound_client(tmp_path, ctx)

    body = client.get("/api/adapters/voice/status").json()
    assert body["configured"] is True
    assert body["calls_allowed"] is True
    assert body["public_url_set"] is True


def test_twiml_route_returns_stream_xml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch)
    monkeypatch.setenv("HORUS_OS_VOICE_PUBLIC_BASE_URL", "https://pub.example")
    ctx = _make_context(tmp_path)
    client = _bound_client(tmp_path, ctx)

    resp = client.get("/api/adapters/voice/twiml")
    assert resp.status_code == 200
    assert "text/xml" in resp.headers["content-type"]
    assert "<Stream" in resp.text
    assert "wss://pub.example/api/adapters/voice/media" in resp.text


def test_complete_route_confirmed_writes_calendar_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure(monkeypatch)
    ctx = _make_context(tmp_path)

    # Register a fake calendar create-event tool so the confirmed-call side
    # effect has something to invoke.
    calendar_calls: list[dict[str, Any]] = []

    def _fake_create_event(**kwargs: Any) -> dict[str, Any]:
        calendar_calls.append(kwargs)
        return {"id": "evt_777"}

    ctx.tool_registry.register(
        Tool(
            name="create_calendar_event",
            description="fake",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=_fake_create_event,
        )
    )

    # Seed a pending call record in the same data dir the adapter reads.
    store = VoiceCallStore(tmp_path)
    store.add(
        {
            "id": "rec1",
            "status": "ringing",
            "venue_name": "Test Bistro",
            "reservation_datetime": "2026-06-10T19:00:00+00:00",
            "party_size": 2,
            "notes": "window seat",
        }
    )

    client = _bound_client(tmp_path, ctx)
    resp = client.post(
        "/api/adapters/voice/calls/rec1/complete",
        json={"transcript": "Your table is confirmed for two at seven."},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "confirmed"
    assert body["calendar_event_id"] == "evt_777"
    # The calendar tool was invoked with the reservation window.
    assert len(calendar_calls) == 1
    assert calendar_calls[0]["start_iso"].startswith("2026-06-10T19:00")


def test_complete_route_declined_skips_calendar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure(monkeypatch)
    ctx = _make_context(tmp_path)
    calendar_calls: list[dict[str, Any]] = []
    ctx.tool_registry.register(
        Tool(
            name="create_calendar_event",
            description="fake",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=lambda **kw: calendar_calls.append(kw),
        )
    )
    store = VoiceCallStore(tmp_path)
    store.add({"id": "rec2", "status": "ringing", "venue_name": "Busy Place"})

    client = _bound_client(tmp_path, ctx)
    resp = client.post(
        "/api/adapters/voice/calls/rec2/complete",
        json={"transcript": "Sorry, we are fully booked tonight."},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "declined"
    assert calendar_calls == []


def test_complete_route_unknown_record_404(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _make_context(tmp_path)
    client = _bound_client(tmp_path, ctx)
    resp = client.post(
        "/api/adapters/voice/calls/nope/complete",
        json={"transcript": "anything"},
    )
    assert resp.status_code == 404
