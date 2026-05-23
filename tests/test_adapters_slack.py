"""Tests for the Slack adapter.

All tests run with `slack_sdk` simulated as either missing or
stubbed via a fake module installed into `sys.modules`. No live
Slack API call happens in any test.

`run_agent` is monkeypatched at the adapter module level so no
provider SDK is required and no network call happens.

The HMAC signature fixtures use the exact format documented by
Slack: the signed string is `f"v0:{timestamp}:{body.decode('utf-8')}"`
and the expected `X-Slack-Signature` header is
`v0=<hex>` where `<hex>` is the HMAC-SHA256 digest keyed by the
signing secret. Reviewers can cross-check this against
https://api.slack.com/authentication/verifying-requests-from-slack
"""

from __future__ import annotations

import hashlib
import hmac
import json
import sys
import time
import types
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from horus_os import Config, Database
from horus_os.adapters import (
    ADAPTER_STATUS_ERROR,
    ADAPTER_STATUS_RUNNING,
    AdapterContext,
    AdapterRegistry,
    SlackAdapter,
)
from horus_os.adapters import slack_adapter as slack_adapter_module
from horus_os.types import AgentResult

# -- fixtures ------------------------------------------------------------------


def _make_context(tmp_path: Path) -> AdapterContext:
    """Build a registry + context with the adapter pre-registered."""
    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    db = Database(cfg.db_path)
    db.init()
    reg = AdapterRegistry()
    reg.register("slack")
    return AdapterContext(config=cfg, data_dir=tmp_path, registry=reg)


def _install_fake_slack_sdk(monkeypatch: pytest.MonkeyPatch) -> types.SimpleNamespace:
    """Inject a fake `slack_sdk` module into sys.modules.

    Returns a SimpleNamespace exposing the recorded WebClient calls
    so tests can assert that `chat_postMessage` was invoked with
    the expected channel and text.
    """
    fake = types.ModuleType("slack_sdk")
    fake_errors = types.ModuleType("slack_sdk.errors")

    handles = types.SimpleNamespace(
        chat_calls=[],
        clients=[],
    )

    class _SlackApiError(Exception):
        pass

    fake_errors.SlackApiError = _SlackApiError

    class _WebClient:
        def __init__(self, token: str | None = None, **_: Any) -> None:
            self.token = token
            handles.clients.append(self)

        def chat_postMessage(self, **kwargs: Any) -> dict[str, Any]:
            handles.chat_calls.append(kwargs)
            return {"ok": True, "ts": "1.2"}

    fake.WebClient = _WebClient
    fake.errors = fake_errors

    monkeypatch.setitem(sys.modules, "slack_sdk", fake)
    monkeypatch.setitem(sys.modules, "slack_sdk.errors", fake_errors)
    return handles


def _make_app(tmp_path: Path) -> tuple[TestClient, SlackAdapter, AdapterContext]:
    """Build a FastAPI app with only the Slack adapter mounted."""
    ctx = _make_context(tmp_path)
    app = FastAPI()
    adapter = SlackAdapter()
    adapter.bind(app, ctx)
    return TestClient(app), adapter, ctx


def _sign(body: bytes, timestamp: str, secret: str) -> str:
    """Compute Slack's `X-Slack-Signature` value for `body` + `timestamp`.

    The signed string is `v0:{timestamp}:{body.decode("utf-8")}`. The
    header value is `v0=<hex>` where `<hex>` is the HMAC-SHA256 digest
    keyed by the signing secret. This is the same shape the adapter
    re-computes inside `_verify_signature`.
    """
    base = f"v0:{timestamp}:{body.decode('utf-8')}".encode()
    digest = hmac.new(secret.encode("utf-8"), base, hashlib.sha256).hexdigest()
    return f"v0={digest}"


def _now_ts() -> str:
    return str(int(time.time()))


SECRET = "test-signing-secret"
BOT_TOKEN = "xoxb-test-not-real"


# -- construction --------------------------------------------------------------


def test_construct_clean_without_slack_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    """`SlackAdapter()` works even when sys.modules has no `slack_sdk` entry."""
    monkeypatch.setitem(sys.modules, "slack_sdk", None)
    adapter = SlackAdapter()
    assert adapter.name == "slack"
    assert adapter._client is None
    assert adapter._sdk_available is False
    assert adapter._seen_event_ids == {}


# -- missing SDK ---------------------------------------------------------------


def test_bind_without_sdk_marks_error_and_routes_return_503(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "slack_sdk", None)
    ctx = _make_context(tmp_path)
    app = FastAPI()
    adapter = SlackAdapter()
    adapter.bind(app, ctx)
    entry = ctx.registry.get("slack")
    assert entry.status == ADAPTER_STATUS_ERROR
    assert "slack-sdk" in (entry.error_message or "")
    client = TestClient(app)
    # No env vars set; SDK check is the first short-circuit so 503 first.
    resp = client.post("/api/adapters/slack/events", content=b"{}")
    assert resp.status_code == 503
    assert "slack-sdk" in resp.json()["detail"]
    resp2 = client.post(
        "/api/adapters/slack/commands",
        content=b"command=/horus",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp2.status_code == 503


# -- missing env vars ----------------------------------------------------------


def test_missing_env_vars_returns_503(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_slack_sdk(monkeypatch)
    monkeypatch.delenv("HORUS_OS_SLACK_BOT_TOKEN", raising=False)
    monkeypatch.delenv("HORUS_OS_SLACK_SIGNING_SECRET", raising=False)
    client, _adapter, ctx = _make_app(tmp_path)
    # Signature header content does not matter; env-var check fires first.
    resp = client.post(
        "/api/adapters/slack/events",
        content=b"{}",
        headers={
            "X-Slack-Request-Timestamp": _now_ts(),
            "X-Slack-Signature": "v0=deadbeef",
        },
    )
    assert resp.status_code == 503
    assert "HORUS_OS_SLACK" in resp.json()["detail"]
    entry = ctx.registry.get("slack")
    assert entry.status == ADAPTER_STATUS_ERROR


# -- HMAC signature ------------------------------------------------------------


def test_signature_verification_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_slack_sdk(monkeypatch)
    monkeypatch.setenv("HORUS_OS_SLACK_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("HORUS_OS_SLACK_SIGNING_SECRET", SECRET)
    client, _adapter, _ctx = _make_app(tmp_path)

    body = json.dumps({"type": "url_verification", "challenge": "abc123"}).encode("utf-8")
    ts = _now_ts()
    sig = _sign(body, ts, SECRET)
    resp = client.post(
        "/api/adapters/slack/events",
        content=body,
        headers={
            "X-Slack-Request-Timestamp": ts,
            "X-Slack-Signature": sig,
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 200
    assert resp.json() == {"challenge": "abc123"}


def test_signature_verification_bad_signature_returns_401(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_slack_sdk(monkeypatch)
    monkeypatch.setenv("HORUS_OS_SLACK_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("HORUS_OS_SLACK_SIGNING_SECRET", SECRET)
    client, _a, _c = _make_app(tmp_path)
    resp = client.post(
        "/api/adapters/slack/events",
        content=b'{"type":"url_verification","challenge":"x"}',
        headers={
            "X-Slack-Request-Timestamp": _now_ts(),
            "X-Slack-Signature": "v0=deadbeefdeadbeef",
        },
    )
    assert resp.status_code == 401


def test_signature_verification_missing_signature_returns_401(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_slack_sdk(monkeypatch)
    monkeypatch.setenv("HORUS_OS_SLACK_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("HORUS_OS_SLACK_SIGNING_SECRET", SECRET)
    client, _a, _c = _make_app(tmp_path)
    resp = client.post(
        "/api/adapters/slack/events",
        content=b"{}",
        headers={"X-Slack-Request-Timestamp": _now_ts()},
    )
    assert resp.status_code == 401


def test_replay_protection_old_timestamp_returns_401(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_slack_sdk(monkeypatch)
    monkeypatch.setenv("HORUS_OS_SLACK_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("HORUS_OS_SLACK_SIGNING_SECRET", SECRET)
    client, _a, _c = _make_app(tmp_path)
    body = b'{"type":"url_verification","challenge":"x"}'
    # 600 seconds in the past, well past the 300-second drift cap.
    old_ts = str(int(time.time()) - 600)
    sig = _sign(body, old_ts, SECRET)
    resp = client.post(
        "/api/adapters/slack/events",
        content=body,
        headers={
            "X-Slack-Request-Timestamp": old_ts,
            "X-Slack-Signature": sig,
        },
    )
    assert resp.status_code == 401


# -- event routing -------------------------------------------------------------


def test_url_verification_returns_challenge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_slack_sdk(monkeypatch)
    monkeypatch.setenv("HORUS_OS_SLACK_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("HORUS_OS_SLACK_SIGNING_SECRET", SECRET)
    client, _a, _c = _make_app(tmp_path)
    body = json.dumps({"type": "url_verification", "challenge": "the-challenge"}).encode("utf-8")
    ts = _now_ts()
    sig = _sign(body, ts, SECRET)
    resp = client.post(
        "/api/adapters/slack/events",
        content=body,
        headers={"X-Slack-Request-Timestamp": ts, "X-Slack-Signature": sig},
    )
    assert resp.status_code == 200
    assert resp.json()["challenge"] == "the-challenge"


def test_app_mention_runs_agent_and_posts_reply(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    handles = _install_fake_slack_sdk(monkeypatch)
    monkeypatch.setenv("HORUS_OS_SLACK_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("HORUS_OS_SLACK_SIGNING_SECRET", SECRET)
    fake_run = MagicMock(
        return_value=AgentResult(text="hello back", provider="anthropic", model="m")
    )
    monkeypatch.setattr(slack_adapter_module, "run_agent", fake_run)
    client, _a, ctx = _make_app(tmp_path)

    payload = {
        "type": "event_callback",
        "event_id": "Ev01",
        "event": {
            "type": "app_mention",
            "text": "<@U0BOT> hello there",
            "channel": "C123",
            "user": "U456",
        },
    }
    body = json.dumps(payload).encode("utf-8")
    ts = _now_ts()
    sig = _sign(body, ts, SECRET)
    resp = client.post(
        "/api/adapters/slack/events",
        content=body,
        headers={"X-Slack-Request-Timestamp": ts, "X-Slack-Signature": sig},
    )
    assert resp.status_code == 200
    assert fake_run.call_count == 1
    assert fake_run.call_args.args[0] == "hello there"
    assert handles.chat_calls
    assert handles.chat_calls[-1]["channel"] == "C123"
    assert handles.chat_calls[-1]["text"] == "hello back"
    assert ctx.registry.get("slack").last_activity_at is not None


def test_dm_message_runs_agent_and_posts_reply(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    handles = _install_fake_slack_sdk(monkeypatch)
    monkeypatch.setenv("HORUS_OS_SLACK_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("HORUS_OS_SLACK_SIGNING_SECRET", SECRET)
    fake_run = MagicMock(return_value=AgentResult(text="dm reply", provider="anthropic", model="m"))
    monkeypatch.setattr(slack_adapter_module, "run_agent", fake_run)
    client, _a, _c = _make_app(tmp_path)

    payload = {
        "type": "event_callback",
        "event_id": "Ev02",
        "event": {
            "type": "message",
            "channel_type": "im",
            "text": "ping",
            "channel": "D123",
            "user": "U456",
        },
    }
    body = json.dumps(payload).encode("utf-8")
    ts = _now_ts()
    sig = _sign(body, ts, SECRET)
    resp = client.post(
        "/api/adapters/slack/events",
        content=body,
        headers={"X-Slack-Request-Timestamp": ts, "X-Slack-Signature": sig},
    )
    assert resp.status_code == 200
    assert fake_run.call_count == 1
    assert fake_run.call_args.args[0] == "ping"
    assert handles.chat_calls[-1]["channel"] == "D123"
    assert handles.chat_calls[-1]["text"] == "dm reply"


def test_bot_message_is_ignored_no_echo_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    handles = _install_fake_slack_sdk(monkeypatch)
    monkeypatch.setenv("HORUS_OS_SLACK_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("HORUS_OS_SLACK_SIGNING_SECRET", SECRET)
    fake_run = MagicMock(return_value=AgentResult(text="x", provider="anthropic", model="m"))
    monkeypatch.setattr(slack_adapter_module, "run_agent", fake_run)
    client, _a, _c = _make_app(tmp_path)

    payload = {
        "type": "event_callback",
        "event_id": "Ev03",
        "event": {
            "type": "message",
            "channel_type": "im",
            "subtype": "bot_message",
            "text": "loop bait",
            "channel": "D123",
            "bot_id": "B999",
        },
    }
    body = json.dumps(payload).encode("utf-8")
    ts = _now_ts()
    sig = _sign(body, ts, SECRET)
    resp = client.post(
        "/api/adapters/slack/events",
        content=body,
        headers={"X-Slack-Request-Timestamp": ts, "X-Slack-Signature": sig},
    )
    assert resp.status_code == 200
    assert fake_run.call_count == 0
    assert handles.chat_calls == []


def test_event_dedup_drops_second_occurrence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    handles = _install_fake_slack_sdk(monkeypatch)
    monkeypatch.setenv("HORUS_OS_SLACK_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("HORUS_OS_SLACK_SIGNING_SECRET", SECRET)
    fake_run = MagicMock(return_value=AgentResult(text="reply", provider="anthropic", model="m"))
    monkeypatch.setattr(slack_adapter_module, "run_agent", fake_run)
    client, _a, _c = _make_app(tmp_path)

    payload = {
        "type": "event_callback",
        "event_id": "EvDup",
        "event": {
            "type": "app_mention",
            "text": "<@U0BOT> hi",
            "channel": "C123",
        },
    }
    body = json.dumps(payload).encode("utf-8")
    ts = _now_ts()
    sig = _sign(body, ts, SECRET)
    headers = {"X-Slack-Request-Timestamp": ts, "X-Slack-Signature": sig}
    resp1 = client.post("/api/adapters/slack/events", content=body, headers=headers)
    resp2 = client.post("/api/adapters/slack/events", content=body, headers=headers)
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    # Only the first event triggered the agent.
    assert fake_run.call_count == 1
    assert len(handles.chat_calls) == 1


# -- slash commands ------------------------------------------------------------


def test_slash_command_verifies_signature_runs_agent_returns_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_slack_sdk(monkeypatch)
    monkeypatch.setenv("HORUS_OS_SLACK_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("HORUS_OS_SLACK_SIGNING_SECRET", SECRET)
    fake_run = MagicMock(return_value=AgentResult(text="ack", provider="anthropic", model="m"))
    monkeypatch.setattr(slack_adapter_module, "run_agent", fake_run)
    client, _a, _c = _make_app(tmp_path)

    body = (
        b"token=verification-token"
        b"&team_id=T0001"
        b"&command=%2Fhorus"
        b"&text=what+is+the+time"
        b"&channel_id=C123"
        b"&user_id=U456"
    )
    ts = _now_ts()
    sig = _sign(body, ts, SECRET)
    resp = client.post(
        "/api/adapters/slack/commands",
        content=body,
        headers={
            "X-Slack-Request-Timestamp": ts,
            "X-Slack-Signature": sig,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["response_type"] == "in_channel"
    assert payload["text"] == "ack"
    assert fake_run.call_count == 1
    assert fake_run.call_args.args[0] == "what is the time"


def test_slash_command_bad_signature_returns_401(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_slack_sdk(monkeypatch)
    monkeypatch.setenv("HORUS_OS_SLACK_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("HORUS_OS_SLACK_SIGNING_SECRET", SECRET)
    client, _a, _c = _make_app(tmp_path)
    resp = client.post(
        "/api/adapters/slack/commands",
        content=b"command=/horus&text=hi",
        headers={
            "X-Slack-Request-Timestamp": _now_ts(),
            "X-Slack-Signature": "v0=deadbeef",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    assert resp.status_code == 401


# -- profile routing -----------------------------------------------------------


def test_profile_env_var_picks_a_different_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_slack_sdk(monkeypatch)
    monkeypatch.setenv("HORUS_OS_SLACK_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("HORUS_OS_SLACK_SIGNING_SECRET", SECRET)
    monkeypatch.setenv("HORUS_OS_SLACK_AGENT_PROFILE", "scribe")
    fake_run = MagicMock(return_value=AgentResult(text="ok", provider="anthropic", model="m"))
    monkeypatch.setattr(slack_adapter_module, "run_agent", fake_run)
    client, _a, ctx = _make_app(tmp_path)

    # Seed the database with a `scribe` profile.
    db = Database(ctx.config.db_path)
    from horus_os.types import AgentProfile

    db.save_profile(
        AgentProfile(
            name="scribe",
            system_prompt="you are scribe",
            default_model="claude-test",
        )
    )

    payload = {
        "type": "event_callback",
        "event_id": "EvProf",
        "event": {
            "type": "message",
            "channel_type": "im",
            "text": "please write a note",
            "channel": "D123",
        },
    }
    body = json.dumps(payload).encode("utf-8")
    ts = _now_ts()
    sig = _sign(body, ts, SECRET)
    resp = client.post(
        "/api/adapters/slack/events",
        content=body,
        headers={"X-Slack-Request-Timestamp": ts, "X-Slack-Signature": sig},
    )
    assert resp.status_code == 200
    assert fake_run.call_count == 1
    kwargs = fake_run.call_args.kwargs
    assert kwargs["system_prompt"] == "you are scribe"
    assert kwargs["model"] == "claude-test"


# -- error isolation -----------------------------------------------------------


def test_run_agent_exception_surfaces_as_reply_and_registry_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    handles = _install_fake_slack_sdk(monkeypatch)
    monkeypatch.setenv("HORUS_OS_SLACK_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("HORUS_OS_SLACK_SIGNING_SECRET", SECRET)

    def boom(*_args: Any, **_kwargs: Any) -> AgentResult:
        raise RuntimeError("provider down")

    monkeypatch.setattr(slack_adapter_module, "run_agent", boom)
    client, _a, ctx = _make_app(tmp_path)

    payload = {
        "type": "event_callback",
        "event_id": "EvErr",
        "event": {
            "type": "app_mention",
            "text": "<@U0BOT> hi",
            "channel": "C123",
        },
    }
    body = json.dumps(payload).encode("utf-8")
    ts = _now_ts()
    sig = _sign(body, ts, SECRET)
    resp = client.post(
        "/api/adapters/slack/events",
        content=body,
        headers={"X-Slack-Request-Timestamp": ts, "X-Slack-Signature": sig},
    )
    # Slack expects 200 even on internal failure so it does not retry.
    assert resp.status_code == 200
    # A brief failure reply was posted.
    assert handles.chat_calls
    assert "RuntimeError" in handles.chat_calls[-1]["text"]
    entry = ctx.registry.get("slack")
    assert entry.error_count >= 1
    assert "RuntimeError" in (entry.error_message or "")


# -- bind side-effects ---------------------------------------------------------


def test_bind_with_sdk_marks_registry_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_slack_sdk(monkeypatch)
    monkeypatch.setenv("HORUS_OS_SLACK_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("HORUS_OS_SLACK_SIGNING_SECRET", SECRET)
    _client, _a, ctx = _make_app(tmp_path)
    entry = ctx.registry.get("slack")
    assert entry.status == ADAPTER_STATUS_RUNNING


# -- helpers -------------------------------------------------------------------


def test_verify_signature_helper_round_trip() -> None:
    """Document the exact signed-string format used by the adapter.

    Signed string: `v0:{timestamp}:{body.decode("utf-8")}`. Header
    format: `v0=<hex>`. See
    https://api.slack.com/authentication/verifying-requests-from-slack
    """
    from horus_os.adapters.slack_adapter import _verify_signature

    secret = "shhh"
    body = b'{"hello":"world"}'
    ts = str(int(time.time()))
    sig = _sign(body, ts, secret)
    assert _verify_signature(secret, body, ts, sig) is True
    assert _verify_signature(secret, body, ts, "v0=wrong") is False
    assert _verify_signature(secret, body, ts, "") is False
    # Non-numeric timestamp -> fail.
    assert _verify_signature(secret, body, "not-a-number", sig) is False


def test_strip_user_mentions_removes_leading_tokens() -> None:
    from horus_os.adapters.slack_adapter import _strip_user_mentions

    assert _strip_user_mentions("<@U0BOT> hello") == "hello"
    assert _strip_user_mentions("  <@U0BOT>   hi there  ") == "hi there  "
    assert _strip_user_mentions("<@U1><@U2> double") == "double"
    assert _strip_user_mentions("no mention here") == "no mention here"
