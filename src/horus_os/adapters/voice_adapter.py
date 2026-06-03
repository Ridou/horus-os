"""Voice / reservations adapter for horus-os.

Ships behind the optional ``[voice]`` extra. Lets an agent place an
outbound phone call (via Twilio) to request or confirm a reservation,
records every call, classifies the outcome from the call transcript,
and, when a reservation is confirmed, writes a calendar event and posts
an optional notification.

Like the Calendar adapter this is primarily a tool provider: it
registers agent-callable tools onto the master tool registry during
``bind`` and mounts a few diagnostic / callback HTTP routes. The
``twilio`` SDK import is lazy inside ``bind`` and the tool handlers so
this module imports cleanly when the extra is not installed; tests
inject a fake ``twilio`` module into ``sys.modules`` to exercise the
adapter offline.

Safety posture (two gates, both re-checked at call time):

- ``HORUS_OS_VOICE_CALLS_ALLOWED`` must equal the string ``"true"``
  before any call is placed. This is the ask-first rail: an agent can
  never autonomously dial out unless the operator has explicitly armed
  calling.
- A reservation is only written to the calendar when the call outcome
  classifies as ``confirmed`` AND the calendar adapter's
  ``create_calendar_event`` tool is registered (which itself requires
  ``HORUS_OS_CALENDAR_WRITE_ALLOWED=true``).

Configuration via environment variables:

- ``HORUS_OS_TWILIO_ACCOUNT_SID`` / ``HORUS_OS_TWILIO_AUTH_TOKEN`` /
  ``HORUS_OS_TWILIO_FROM_NUMBER``: the Twilio REST credentials and the
  caller-id number. All three are required for the tools to register.
- ``HORUS_OS_VOICE_PUBLIC_BASE_URL``: the public base URL Twilio can
  reach to fetch call TwiML and open the media stream (for example an
  ngrok or Cloudflare tunnel, or your deployed origin). Required to
  place a call.
- ``HORUS_OS_VOICE_CALLS_ALLOWED``: arm outbound calling (ask-first).
- ``HORUS_OS_VOICE_NOTIFY_WEBHOOK``: optional URL that receives a JSON
  ``{"content": ...}`` notification when a call completes.

The live, two-way audio bridge (Twilio Media Streams to a realtime
voice model) runs over the ``/api/adapters/voice/media`` websocket and
needs a public URL plus a realtime voice provider; see
``docs/adapters/VOICE.md`` for the deploy walkthrough. Call placement,
outcome classification, and the calendar / notify side effects all work
and are tested without any live telephony.

The adapter satisfies the ``Adapter`` Protocol (name, bind). It does
not implement ``LifecycleAdapter``; there is no background task to run.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from horus_os.adapters.base import AdapterContext
from horus_os.types import Tool

ACCOUNT_SID_ENV = "HORUS_OS_TWILIO_ACCOUNT_SID"
AUTH_TOKEN_ENV = "HORUS_OS_TWILIO_AUTH_TOKEN"
FROM_NUMBER_ENV = "HORUS_OS_TWILIO_FROM_NUMBER"
PUBLIC_BASE_URL_ENV = "HORUS_OS_VOICE_PUBLIC_BASE_URL"
CALLS_ALLOWED_ENV = "HORUS_OS_VOICE_CALLS_ALLOWED"
NOTIFY_WEBHOOK_ENV = "HORUS_OS_VOICE_NOTIFY_WEBHOOK"

VOICE_EXTRA_HINT = "voice adapter requires pip install 'horus-os[voice]'"
CALENDAR_TOOL_NAME = "create_calendar_event"
DEFAULT_RESERVATION_MINUTES = 90
STORE_FILENAME = "calls.json"

# Unambiguous outcome markers. Soft words (for example "sorry") stay out
# of the decline set so a polite confirmation is not misread, and the bare
# word "booked" stays out of the confirm set because "fully booked" is a
# decline.
_CONFIRM_MARKERS = (
    "confirmed",
    "reserved",
    "your table",
    "see you then",
    "we have you",
    "all set",
)
_DECLINE_MARKERS = (
    "fully booked",
    "no availability",
    "no tables",
    "cannot accommodate",
    "unavailable",
    "we are closed",
)
_CALLBACK_MARKERS = (
    "call you back",
    "call back",
    "ring you back",
    "let me check and",
)


def classify_call_outcome(transcript: str) -> dict[str, Any]:
    """Classify a reservation call transcript into a coarse outcome.

    Returns ``{"status": ..., "matched": [...]}`` where status is one of
    ``confirmed``, ``declined``, ``callback``, or ``unclear``. The match
    is a deterministic keyword scan so the result is reproducible and
    testable without a model; the complete route accepts an explicit
    ``outcome`` override for callers that classify with an LLM upstream.
    """
    text = (transcript or "").lower()
    confirm = [m for m in _CONFIRM_MARKERS if m in text]
    decline = [m for m in _DECLINE_MARKERS if m in text]
    callback = [m for m in _CALLBACK_MARKERS if m in text]
    if confirm and not decline:
        return {"status": "confirmed", "matched": confirm}
    if decline and not confirm:
        return {"status": "declined", "matched": decline}
    if callback and not (confirm and decline):
        return {"status": "callback", "matched": callback}
    return {"status": "unclear", "matched": []}


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _reservation_window(reservation_datetime: str) -> tuple[str, str] | None:
    """Return (start_iso, end_iso) for a reservation, or None if unparseable."""
    try:
        start = datetime.fromisoformat(reservation_datetime)
    except (TypeError, ValueError):
        return None
    end = start + timedelta(minutes=DEFAULT_RESERVATION_MINUTES)
    return start.isoformat(), end.isoformat()


class VoiceCallStore:
    """A small JSON-backed log of reservation calls under data_dir/voice/."""

    def __init__(self, data_dir: Path) -> None:
        self._path = Path(data_dir) / "voice" / STORE_FILENAME

    def _load(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            return []
        return data if isinstance(data, list) else []

    def _write(self, records: list[dict[str, Any]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(records, indent=2), encoding="utf-8")

    def list(self) -> list[dict[str, Any]]:
        return self._load()

    def add(self, record: dict[str, Any]) -> None:
        records = self._load()
        records.append(record)
        self._write(records)

    def update(self, record_id: str, **fields: Any) -> dict[str, Any] | None:
        records = self._load()
        updated: dict[str, Any] | None = None
        for record in records:
            if record.get("id") == record_id:
                record.update(fields)
                updated = record
        if updated is not None:
            self._write(records)
        return updated


class VoiceAdapter:
    """Outbound reservation-call adapter backed by Twilio."""

    name = "voice"

    def __init__(self) -> None:
        self._context: AdapterContext | None = None
        self._store: VoiceCallStore | None = None

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": 1,
            "transport": "twilio-voice",
            "env": ACCOUNT_SID_ENV,
            "endpoints": [
                "/api/adapters/voice/status",
                "/api/adapters/voice/twiml",
                "/api/adapters/voice/calls/{record_id}/complete",
            ],
        }

    def bind(self, app: Any, context: AdapterContext) -> None:
        """Mount the diagnostic routes and, when configured, the call tools.

        Mirrors the Calendar adapter: a missing dependency or missing
        config flips the registry entry to ``error`` and returns without
        raising so the rest of the dashboard keeps running. Tools are
        registered only when fully configured, so a zero-config install
        auto-registers nothing (REL-19).
        """
        import os

        context.registry.register(self.name)
        self._context = context
        self._store = VoiceCallStore(context.data_dir)

        self._mount_routes(app, context)

        if context.tool_registry is None:
            context.registry.mark_error(
                self.name,
                "AdapterContext.tool_registry is None; the voice adapter needs a "
                "ToolRegistry on the context to register its tools",
            )
            return

        try:
            import twilio  # noqa: F401  (presence-check only)
        except ImportError:
            context.registry.mark_error(self.name, VOICE_EXTRA_HINT)
            return

        missing = [
            env
            for env in (ACCOUNT_SID_ENV, AUTH_TOKEN_ENV, FROM_NUMBER_ENV)
            if not os.environ.get(env)
        ]
        if missing:
            context.registry.mark_error(
                self.name,
                f"voice adapter is not configured; set {', '.join(missing)}",
            )
            return

        context.tool_registry.register(_request_call_tool(self), replace=True)
        context.tool_registry.register(_list_calls_tool(self), replace=True)
        context.registry.mark_running(self.name)

    def _mount_routes(self, app: Any, context: AdapterContext) -> None:
        # Lazy FastAPI import + globals rebind so stringified annotations
        # resolve (mirrors the webhook adapter). create_app only ever calls
        # bind when FastAPI is present, so this import always succeeds here.
        import os

        from fastapi import HTTPException, Request, Response

        globals()["Request"] = Request
        globals()["HTTPException"] = HTTPException
        globals()["Response"] = Response

        store = self._store
        assert store is not None

        @app.get("/api/adapters/voice/status")
        async def _voice_status() -> dict[str, Any]:
            calls = store.list()
            return {
                "configured": all(
                    os.environ.get(env)
                    for env in (ACCOUNT_SID_ENV, AUTH_TOKEN_ENV, FROM_NUMBER_ENV)
                ),
                "calls_allowed": os.environ.get(CALLS_ALLOWED_ENV) == "true",
                "public_url_set": bool(os.environ.get(PUBLIC_BASE_URL_ENV)),
                "total_calls": len(calls),
                "pending": sum(1 for c in calls if c.get("status") in ("initiated", "ringing")),
            }

        @app.get("/api/adapters/voice/twiml")
        async def _voice_twiml() -> Response:
            # Minimal TwiML that connects the answered call to the media
            # stream bridge. Twilio fetches this URL when the call connects.
            base = os.environ.get(PUBLIC_BASE_URL_ENV, "")
            ws_base = base.replace("https://", "wss://").replace("http://", "ws://")
            xml = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                "<Response><Connect>"
                f'<Stream url="{ws_base}/api/adapters/voice/media"/>'
                "</Connect></Response>"
            )
            return Response(content=xml, media_type="text/xml")

        @app.post("/api/adapters/voice/calls/{record_id}/complete")
        async def _voice_complete(record_id: str, request: Request) -> dict[str, Any]:
            try:
                body = await request.json()
            except ValueError as exc:
                raise HTTPException(400, detail=f"invalid JSON body: {exc}") from exc
            if not isinstance(body, dict):
                raise HTTPException(400, detail="body must be a JSON object")

            transcript = str(body.get("transcript", "") or "")
            override = body.get("outcome")
            outcome = (
                str(override)
                if isinstance(override, str) and override
                else classify_call_outcome(transcript)["status"]
            )

            record = store.update(
                record_id,
                status=outcome,
                transcript=transcript,
                completed_at=_now_iso(),
            )
            if record is None:
                raise HTTPException(404, detail=f"call record {record_id!r} not found")

            if outcome == "confirmed":
                self._on_confirmed(record)

            context.registry.touch(self.name)
            return record

    def _on_confirmed(self, record: dict[str, Any]) -> None:
        """Write a calendar event for a confirmed reservation and notify.

        Both side effects are best-effort: a missing calendar tool or a
        failed notification never turns a confirmed call into an error.
        """
        import os

        context = self._context
        store = self._store
        if context is None or store is None:
            return

        registry = context.tool_registry
        window = _reservation_window(str(record.get("reservation_datetime", "")))
        if registry is not None and CALENDAR_TOOL_NAME in registry and window is not None:
            start_iso, end_iso = window
            party = record.get("party_size")
            summary = f"Reservation: {record.get('venue_name', 'venue')}"
            if party:
                summary = f"{summary} (party of {party})"
            try:
                result = registry.invoke(
                    CALENDAR_TOOL_NAME,
                    {
                        "summary": summary,
                        "start_iso": start_iso,
                        "end_iso": end_iso,
                        "description": str(record.get("notes", "") or ""),
                    },
                )
                event_id = result.get("id") if isinstance(result, dict) else None
                store.update(record.get("id", ""), calendar_event_id=event_id)
                # Reflect it on the in-memory record the route returns.
                record["calendar_event_id"] = event_id
            except Exception:
                # A calendar failure must not fail the call completion.
                pass

        webhook = os.environ.get(NOTIFY_WEBHOOK_ENV)
        if webhook:
            _post_notification(
                webhook,
                f"Reservation confirmed at {record.get('venue_name', 'venue')} "
                f"for {record.get('reservation_datetime', 'the requested time')}.",
            )


def _post_notification(webhook_url: str, content: str) -> None:
    """Best-effort POST of a JSON notification; never raises."""
    try:
        import httpx
    except ImportError:
        return
    try:
        httpx.post(webhook_url, json={"content": content}, timeout=10.0)
    except Exception:
        return


_REQUEST_CALL_PARAMETERS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "venue_name": {
            "type": "string",
            "description": "Name of the restaurant or venue being called.",
        },
        "to_number": {
            "type": "string",
            "description": "The venue phone number in E.164 format, for example +14155551234.",
        },
        "reservation_datetime": {
            "type": "string",
            "description": (
                "Requested reservation time in ISO 8601 with timezone offset, "
                "for example 2026-06-10T19:00:00-07:00."
            ),
        },
        "party_size": {
            "type": "integer",
            "description": "Number of guests.",
        },
        "caller_name": {
            "type": "string",
            "description": "Name to give the venue for the booking.",
        },
        "notes": {
            "type": "string",
            "description": "Optional notes (seating preference, occasion, dietary needs).",
        },
    },
    "required": ["venue_name", "to_number", "reservation_datetime"],
}

_LIST_CALLS_PARAMETERS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "description": (
                "Optional status filter: initiated, ringing, confirmed, "
                "declined, callback, unclear, or error."
            ),
        },
    },
    "required": [],
}


def _request_call_tool(adapter: VoiceAdapter) -> Tool:
    """Build the ``request_reservation_call`` tool, closed over the adapter."""

    def handler(
        venue_name: str,
        to_number: str,
        reservation_datetime: str,
        party_size: int = 2,
        caller_name: str = "",
        notes: str = "",
    ) -> dict[str, Any]:
        import os

        # Ask-first rail, re-checked at call time so flipping the flag off
        # mid-session takes effect immediately.
        if os.environ.get(CALLS_ALLOWED_ENV) != "true":
            return {
                "error": (
                    "outbound calling is not authorized; set "
                    f"{CALLS_ALLOWED_ENV}=true to arm the voice adapter "
                    "(ask-first safety rail)"
                )
            }
        base = os.environ.get(PUBLIC_BASE_URL_ENV)
        if not base:
            return {
                "error": (
                    f"{PUBLIC_BASE_URL_ENV} is not set; Twilio needs a public URL "
                    "to fetch call TwiML and open the media stream"
                )
            }

        store = adapter._store
        context = adapter._context
        assert store is not None

        record_id = uuid.uuid4().hex
        record: dict[str, Any] = {
            "id": record_id,
            "created_at": _now_iso(),
            "venue_name": venue_name,
            "to_number": to_number,
            "reservation_datetime": reservation_datetime,
            "party_size": party_size,
            "caller_name": caller_name,
            "notes": notes,
            "status": "initiated",
            "call_sid": None,
        }

        try:
            from twilio.rest import Client
        except ImportError:
            return {"error": VOICE_EXTRA_HINT}

        try:
            client = Client(
                os.environ.get(ACCOUNT_SID_ENV),
                os.environ.get(AUTH_TOKEN_ENV),
            )
            call = client.calls.create(
                to=to_number,
                from_=os.environ.get(FROM_NUMBER_ENV),
                url=f"{base}/api/adapters/voice/twiml?record={record_id}",
            )
            record["call_sid"] = getattr(call, "sid", None)
            record["status"] = "ringing"
            store.add(record)
            if context is not None:
                context.registry.touch(adapter.name)
            return {
                "record_id": record_id,
                "call_sid": record["call_sid"],
                "status": record["status"],
                "message": (
                    f"Calling {venue_name} to request a table for {party_size} "
                    f"at {reservation_datetime}."
                ),
            }
        except Exception as exc:
            record["status"] = "error"
            record["error"] = f"{type(exc).__name__}: {exc}"
            store.add(record)
            if context is not None:
                context.registry.mark_error(adapter.name, f"{type(exc).__name__}: {exc}")
            return {"error": f"{type(exc).__name__}: {exc}", "record_id": record_id}

    return Tool(
        name="request_reservation_call",
        description=(
            "Place an outbound phone call to a venue to request or confirm a "
            "reservation. Requires the operator to have armed calling via "
            f"{CALLS_ALLOWED_ENV}=true. Returns a record id and Twilio call sid; "
            "the outcome is recorded once the call completes."
        ),
        parameters=_REQUEST_CALL_PARAMETERS,
        handler=handler,
    )


def _list_calls_tool(adapter: VoiceAdapter) -> Tool:
    """Build the ``get_reservation_calls`` tool, closed over the adapter."""

    def handler(status: str = "") -> list[dict[str, Any]]:
        store = adapter._store
        assert store is not None
        calls = store.list()
        if status:
            calls = [c for c in calls if c.get("status") == status]
        return calls

    return Tool(
        name="get_reservation_calls",
        description=(
            "List recorded reservation calls and their outcomes. Pass an "
            "optional status filter (initiated, ringing, confirmed, declined, "
            "callback, unclear, error)."
        ),
        parameters=_LIST_CALLS_PARAMETERS,
        handler=handler,
    )
