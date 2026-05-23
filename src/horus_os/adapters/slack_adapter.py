"""Slack adapter for horus-os.

Mounts two FastAPI routes that handle Slack's Events API and slash
commands. Unlike the Discord adapter (Phase 23) which holds a
persistent gateway connection, Slack uses HTTP webhooks for both
event delivery and slash commands, so this adapter satisfies only
the `Adapter` Protocol; no background task and no
`LifecycleAdapter.start`/`stop` hooks.

Routes:

- `POST /api/adapters/slack/events`: Slack's Events API delivery
  endpoint. Handles the `url_verification` challenge during
  initial setup, and routes `app_mention` plus DM `message`
  events through `run_agent`.
- `POST /api/adapters/slack/commands`: slash command receiver.
  Slack sends form-encoded payloads here when a user invokes a
  configured slash command.

Both routes verify the request signature using Slack's
signing-secret HMAC-SHA256 scheme over the exact byte string
`v0:{timestamp}:{body}` with a 300-second replay-protection
window. The comparison uses `hmac.compare_digest` for constant
time.

The `slack_sdk` import is lazy inside `bind` so this module
imports cleanly when the optional extra is not installed. Tests
inject a fake `slack_sdk` module into `sys.modules` to exercise
the adapter without the SDK on the path.

Configuration via environment variables:

- `HORUS_OS_SLACK_BOT_TOKEN`: Bot token (xoxb-...). Required to
  post replies via `WebClient.chat_postMessage`.
- `HORUS_OS_SLACK_SIGNING_SECRET`: Signing secret from the Slack
  app's Basic Information page. Required to verify inbound
  requests.
- `HORUS_OS_SLACK_AGENT_PROFILE`: Agent profile name to load.
  Defaults to "default". Missing profile is non-fatal.

The adapter is declared as an entry point in pyproject under
`[project.entry-points."horus_os.adapters"]`.
"""

from __future__ import annotations

import collections
import contextlib
import hashlib
import hmac
import json
import os
import re
import time
import urllib.parse
from typing import Any

from horus_os.adapters.base import AdapterContext
from horus_os.agent import run_agent
from horus_os.config import Config
from horus_os.storage import Database

TOKEN_ENV = "HORUS_OS_SLACK_BOT_TOKEN"
SIGNING_SECRET_ENV = "HORUS_OS_SLACK_SIGNING_SECRET"
AGENT_ENV = "HORUS_OS_SLACK_AGENT_PROFILE"
DEFAULT_AGENT = "default"
EVENT_DEDUP_CAP = 1000
SLACK_TIMESTAMP_MAX_DRIFT = 300  # seconds, per Slack docs
SIGNATURE_VERSION = "v0"


class SlackAdapter:
    """An inbound Slack adapter (Events API + slash commands)."""

    name = "slack"

    def __init__(self) -> None:
        self._client: Any = None
        self._sdk_available: bool = False
        self._sdk_import_error: str | None = None
        # Use an OrderedDict as a tiny LRU set keyed by event_id.
        self._seen_event_ids: collections.OrderedDict[str, None] = collections.OrderedDict()
        self._context: AdapterContext | None = None

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": 1,
            "endpoints": [
                "/api/adapters/slack/events",
                "/api/adapters/slack/commands",
            ],
            "auth": "hmac-sha256 signing-secret",
            "env": TOKEN_ENV,
        }

    def bind(self, app: Any, context: AdapterContext) -> None:
        """Mount the two Slack routes onto the FastAPI app.

        The slack_sdk import is lazy. A missing SDK is recorded into
        the registry but does NOT prevent route mounting; the
        handlers themselves short-circuit to 503 so the URLs exist
        and operators get a clear error when they hit them.
        """
        # Import FastAPI symbols lazily so the package import does not
        # require FastAPI when the dashboard extra is not installed.
        # Rebinding onto module globals lets FastAPI's signature
        # introspection resolve stringified `Request` annotations on
        # the route below: `from __future__ import annotations` turns
        # every annotation into a string, and FastAPI looks up the
        # name in this module's globals.
        from fastapi import HTTPException, Request

        globals()["Request"] = Request
        globals()["HTTPException"] = HTTPException

        self._context = context
        try:
            import slack_sdk  # noqa: F401  (presence check; WebClient looked up lazily per request)

            self._sdk_available = True
        except ImportError:
            self._sdk_import_error = "slack-sdk is not installed; pip install 'horus-os[slack]'"
            context.registry.mark_error(self.name, self._sdk_import_error)

        adapter = self

        @app.post("/api/adapters/slack/events")
        async def _handle_events(request: Request) -> Any:
            if not adapter._sdk_available:
                raise HTTPException(503, detail=adapter._sdk_import_error or "slack-sdk missing")

            secret = os.environ.get(SIGNING_SECRET_ENV) or ""
            token = os.environ.get(TOKEN_ENV) or ""
            if not secret or not token:
                missing = SIGNING_SECRET_ENV if not secret else TOKEN_ENV
                if adapter._context is not None:
                    adapter._context.registry.mark_error(adapter.name, f"{missing} is not set")
                raise HTTPException(503, detail=f"{missing} is not set")

            raw_body = await request.body()
            timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
            signature = request.headers.get("X-Slack-Signature", "")
            if not _verify_signature(secret, raw_body, timestamp, signature):
                raise HTTPException(401, detail="invalid signature")

            try:
                payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
            except (UnicodeDecodeError, ValueError) as exc:
                raise HTTPException(400, detail=f"invalid JSON body: {exc}") from exc
            if not isinstance(payload, dict):
                raise HTTPException(400, detail="payload must be a JSON object")

            return adapter._dispatch_event_payload(payload, token=token)

        @app.post("/api/adapters/slack/commands")
        async def _handle_commands(request: Request) -> Any:
            if not adapter._sdk_available:
                raise HTTPException(503, detail=adapter._sdk_import_error or "slack-sdk missing")

            secret = os.environ.get(SIGNING_SECRET_ENV) or ""
            token = os.environ.get(TOKEN_ENV) or ""
            if not secret or not token:
                missing = SIGNING_SECRET_ENV if not secret else TOKEN_ENV
                if adapter._context is not None:
                    adapter._context.registry.mark_error(adapter.name, f"{missing} is not set")
                raise HTTPException(503, detail=f"{missing} is not set")

            raw_body = await request.body()
            timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
            signature = request.headers.get("X-Slack-Signature", "")
            if not _verify_signature(secret, raw_body, timestamp, signature):
                raise HTTPException(401, detail="invalid signature")

            # Slack slash commands arrive as application/x-www-form-urlencoded.
            try:
                form = urllib.parse.parse_qs(raw_body.decode("utf-8"), keep_blank_values=True)
            except UnicodeDecodeError as exc:
                raise HTTPException(400, detail=f"invalid form body: {exc}") from exc
            return adapter._dispatch_command_form(form)

        if self._sdk_available:
            context.registry.mark_running(self.name)

    # -- dispatchers ----------------------------------------------------------

    def _dispatch_event_payload(self, payload: dict[str, Any], *, token: str) -> dict[str, Any]:
        """Route an already-parsed Events API payload.

        Returns the JSON body to send back to Slack. Always 200 OK on
        the wire: any agent failure becomes a brief reply posted to
        the channel plus a registry `mark_error`, never a 5xx, so
        Slack does not retry the same event.
        """
        ptype = payload.get("type")
        if ptype == "url_verification":
            # Slack's one-time URL handshake. Echo the challenge back.
            return {"challenge": payload.get("challenge", "")}

        if ptype != "event_callback":
            # Acknowledge unrecognized envelope types so Slack does
            # not retry; future event types can be added without
            # breaking compatibility.
            return {"ok": True}

        event = payload.get("event") or {}
        if not isinstance(event, dict):
            return {"ok": True}

        # Bot-message guard before dedup so we never even spend an
        # entry on a message we would not act on.
        if event.get("subtype") == "bot_message" or event.get("bot_id"):
            return {"ok": True}

        # Dedup. Slack retries on 3-second timeout up to 3 times.
        event_id = payload.get("event_id") or event.get("event_id")
        if event_id:
            if event_id in self._seen_event_ids:
                return {"ok": True}
            self._remember_event(str(event_id))

        event_type = event.get("type")
        text = event.get("text", "") or ""
        channel = event.get("channel")
        thread_ts = event.get("thread_ts")
        channel_type = event.get("channel_type")

        is_app_mention = event_type == "app_mention"
        is_dm = event_type == "message" and channel_type == "im"
        if not (is_app_mention or is_dm):
            return {"ok": True}

        prompt = _strip_user_mentions(text).strip()
        if not prompt:
            return {"ok": True}

        try:
            reply = self._dispatch(prompt)
        except Exception as exc:
            if self._context is not None:
                self._context.registry.mark_error(self.name, f"{type(exc).__name__}: {exc}")
            reply = f"Sorry, that failed: {type(exc).__name__}"

        with contextlib.suppress(Exception):
            self._post_message(token, channel=channel, text=reply, thread_ts=thread_ts)

        if self._context is not None:
            self._context.registry.touch(self.name)
        return {"ok": True}

    def _dispatch_command_form(self, form: dict[str, list[str]]) -> dict[str, Any]:
        """Route an already-parsed slash command form.

        Returns the JSON body for an inline Slack response. Errors
        become a brief failure message rather than a 5xx.
        """

        def _first(field: str) -> str:
            values = form.get(field, [])
            return values[0] if values else ""

        text = _first("text")
        if not text.strip():
            # Slack still expects a 200 with a body the user can see.
            return {"response_type": "ephemeral", "text": "(empty command text)"}

        try:
            reply = self._dispatch(text)
        except Exception as exc:
            if self._context is not None:
                self._context.registry.mark_error(self.name, f"{type(exc).__name__}: {exc}")
            reply = f"Sorry, that failed: {type(exc).__name__}"

        if self._context is not None:
            self._context.registry.touch(self.name)
        return {"response_type": "in_channel", "text": reply or "(no response)"}

    # -- helpers --------------------------------------------------------------

    def _dispatch(self, prompt: str) -> str:
        """Run one synchronous agent turn against the configured profile."""
        if self._context is None:
            raise RuntimeError("SlackAdapter._dispatch called before bind")
        cfg = self._context.config
        profile_name = os.environ.get(AGENT_ENV, DEFAULT_AGENT)
        profile = None
        if cfg.db_path.exists():
            db = Database(cfg.db_path)
            profile = db.load_profile(profile_name)
        provider = cfg.default_provider
        model = (profile.default_model if profile else None) or _default_model(cfg, provider)
        system_prompt = profile.system_prompt if profile else None
        result = run_agent(
            prompt,
            provider=provider,
            tools=None,
            model=model,
            system_prompt=system_prompt,
        )
        return result.text or ""

    def _post_message(
        self,
        token: str,
        *,
        channel: str | None,
        text: str,
        thread_ts: str | None = None,
    ) -> None:
        """Post a reply via slack_sdk.WebClient.chat_postMessage.

        Looked up lazily from `sys.modules` so the test suite's fake
        module is honored. Posting to a missing channel is suppressed
        by the caller via `contextlib.suppress(Exception)`.
        """
        import slack_sdk  # lazy; resolved against the (possibly faked) module

        if not channel:
            return
        # Reuse a WebClient per token across requests; if env var
        # rotation happens mid-process the cached client is rebuilt.
        if self._client is None or getattr(self._client, "_token", None) != token:
            self._client = slack_sdk.WebClient(token=token)
            # Stash the token for the next comparison without relying
            # on `WebClient.token` existing on every SDK version.
            with contextlib.suppress(Exception):
                self._client._token = token  # type: ignore[attr-defined]
        kwargs: dict[str, Any] = {
            "channel": channel,
            "text": text or "(no response)",
        }
        if thread_ts:
            kwargs["thread_ts"] = thread_ts
        self._client.chat_postMessage(**kwargs)

    def _remember_event(self, event_id: str) -> None:
        """Insert event_id into the LRU dedup set, evicting if at cap."""
        self._seen_event_ids[event_id] = None
        while len(self._seen_event_ids) > EVENT_DEDUP_CAP:
            self._seen_event_ids.popitem(last=False)


def _verify_signature(secret: str, body: bytes, timestamp: str, signature: str) -> bool:
    """Verify Slack's HMAC-SHA256 signature on a request.

    Signed string: `v0:{timestamp}:{body.decode("utf-8")}`. Expected
    header: `v0=<hex>`. Constant-time compare via
    `hmac.compare_digest`. Timestamp drift cap is
    `SLACK_TIMESTAMP_MAX_DRIFT` seconds (300, per Slack docs).
    """
    if not secret or not signature or not timestamp:
        return False
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False
    if abs(time.time() - ts) > SLACK_TIMESTAMP_MAX_DRIFT:
        return False
    try:
        body_text = body.decode("utf-8")
    except UnicodeDecodeError:
        return False
    base = f"{SIGNATURE_VERSION}:{timestamp}:{body_text}".encode()
    expected = (
        SIGNATURE_VERSION + "=" + hmac.new(secret.encode("utf-8"), base, hashlib.sha256).hexdigest()
    )
    return hmac.compare_digest(expected, signature)


_MENTION_PATTERN = re.compile(r"^(?:\s*<@[A-Z0-9]+>\s*)+")


def _strip_user_mentions(text: str) -> str:
    """Remove leading `<@UXXXX>` mention tokens that Slack injects.

    Slack puts the mention token at the start of every `app_mention`
    event's text field. We strip the leading mention(s) so the agent
    sees just the natural-language prompt.
    """
    return _MENTION_PATTERN.sub("", text)


def _default_model(cfg: Config, provider: str) -> str:
    if provider == "anthropic":
        return cfg.anthropic_model
    return cfg.gemini_model
