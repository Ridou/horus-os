"""Slack adapter example: HMAC-signed `app_mention` POST through TestClient.

This example shows how to:

1. Stub the optional `slack-sdk` SDK via `sys.modules` injection so
   `SlackAdapter` runs without the package installed. The fake
   `WebClient` records every `chat_postMessage` call so the example
   can show what would have posted back to Slack.
2. `bind` the adapter onto a FastAPI app, the same shape `create_app`
   uses at startup.
3. Build an `app_mention` Events API payload, compute the exact
   HMAC-SHA256 signature Slack would send (`v0:{ts}:{body}` keyed by
   the signing secret), and POST it through `fastapi.testclient.TestClient`.
4. Print the response shape plus the captured `chat_postMessage` call
   so both the inbound and outbound surfaces are visible.

The script runs end to end with no Slack credentials, no `slack-sdk`
install, and no network. `run_agent` is monkeypatched at the adapter
module level to return a canned `AgentResult`.

For a live run set:

    HORUS_OS_SLACK_BOT_TOKEN=your-bot-token-here       # xoxb-...
    HORUS_OS_SLACK_SIGNING_SECRET=your-signing-secret-here
    HORUS_OS_SLACK_AGENT_PROFILE=default               # optional

then `pip install 'horus-os[slack]'` and `horus-os serve`. Point the
Slack app's Event Subscriptions URL at
`https://your-host/api/adapters/slack/events`. See
`docs/adapters/SLACK.md` for the full setup walkthrough.

Run it:

    python examples/slack_adapter.py
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import tempfile
import time
import types
from pathlib import Path
from typing import Any

from horus_os import (
    AdapterContext,
    AdapterRegistry,
    Config,
    Database,
)
from horus_os.adapters import SlackAdapter
from horus_os.adapters import slack_adapter as slack_adapter_module
from horus_os.types import AgentResult

SECRET = "your-signing-secret-here"
BOT_TOKEN = "xoxb-your-bot-token-here"


def _install_fake_slack_sdk() -> types.SimpleNamespace:
    """Inject a fake `slack_sdk` module into sys.modules."""
    fake = types.ModuleType("slack_sdk")
    fake_errors = types.ModuleType("slack_sdk.errors")

    handles = types.SimpleNamespace(chat_calls=[])

    class _SlackApiError(Exception):
        pass

    fake_errors.SlackApiError = _SlackApiError

    class _WebClient:
        def __init__(self, token: str | None = None, **_: Any) -> None:
            self.token = token

        def chat_postMessage(self, **kwargs: Any) -> dict[str, Any]:
            handles.chat_calls.append(kwargs)
            return {"ok": True, "ts": "1.2"}

    fake.WebClient = _WebClient
    fake.errors = fake_errors
    sys.modules["slack_sdk"] = fake
    sys.modules["slack_sdk.errors"] = fake_errors
    return handles


def _stub_run_agent() -> None:
    def fake_run_agent(prompt: str, **kwargs: Any) -> AgentResult:
        return AgentResult(
            text=f"[stub agent] received: {prompt!r}",
            provider="stub",
            model="stub-model",
            usage={"input_tokens": 0, "output_tokens": 0},
        )

    slack_adapter_module.run_agent = fake_run_agent


def _sign(body: bytes, timestamp: str, secret: str) -> str:
    """Compute the Slack `X-Slack-Signature` header value.

    Signed string is `f"v0:{timestamp}:{body.decode('utf-8')}"`. The
    header is `v0=<hex>` where `<hex>` is the HMAC-SHA256 digest keyed
    by the signing secret. This is the same shape `SlackAdapter`
    re-runs server-side via `hmac.compare_digest`.
    """
    base = f"v0:{timestamp}:{body.decode('utf-8')}".encode()
    digest = hmac.new(secret.encode("utf-8"), base, hashlib.sha256).hexdigest()
    return f"v0={digest}"


def main() -> None:
    handles = _install_fake_slack_sdk()
    _stub_run_agent()

    # FastAPI + TestClient are part of the `dashboard` and `dev` extras.
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        config = Config.with_defaults(data_dir)
        config.save()
        Database(config.db_path).init()

        registry = AdapterRegistry()
        registry.register("slack")
        ctx = AdapterContext(config=config, data_dir=data_dir, registry=registry)

        # Required env vars; the placeholder values are fine offline.
        os.environ["HORUS_OS_SLACK_BOT_TOKEN"] = BOT_TOKEN
        os.environ["HORUS_OS_SLACK_SIGNING_SECRET"] = SECRET

        app = FastAPI()
        adapter = SlackAdapter()
        adapter.bind(app, ctx)
        client = TestClient(app)

        payload = {
            "type": "event_callback",
            "event_id": "Ev01",
            "event": {
                "type": "app_mention",
                "text": "<@U0BOT> what is the weather today?",
                "channel": "C123",
                "user": "U456",
            },
        }
        body = json.dumps(payload).encode("utf-8")
        ts = str(int(time.time()))
        sig = _sign(body, ts, SECRET)

        response = client.post(
            "/api/adapters/slack/events",
            content=body,
            headers={
                "X-Slack-Request-Timestamp": ts,
                "X-Slack-Signature": sig,
                "Content-Type": "application/json",
            },
        )

        print(f"Response: HTTP {response.status_code} body={response.json()}")
        print()
        print("Captured WebClient.chat_postMessage calls:")
        for call in handles.chat_calls:
            print(f"  channel={call.get('channel')!r} text={call.get('text')!r}")
        print()
        entry = registry.get("slack")
        print(f"Registry entry: status={entry.status} last_activity_at={entry.last_activity_at}")


if __name__ == "__main__":
    main()
