"""Coexistence of all v0.3 adapters through create_app discover_adapters.

Phase 29 gaps C, D, and G. Each of phases 23 through 27 tested its
own adapter against a hand-built or stubbed environment. No prior
test mounted Discord, Slack, Email, Calendar, and the live webhook
adapter together through `create_app` to confirm none of them
interfere with each other, that an error in one does not block
the others, and that `/api/chat` traces stay clean while the
adapter ring is bound.

Discord and Email here are exercised via their realistic
no-env-configured error path (start hook marks registry error,
adapter does not crash). Slack mounts routes regardless of SDK
presence; missing SDK marks bind-time error. Calendar runs the
happy path with stubbed google modules so app.state.tool_registry
sees the tool. The reference WebhookAdapter ships in pyproject
and resolves through the stubbed entry-point list when the test
includes it explicitly.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from horus_os import Config, Database, create_app
from horus_os.adapters import (
    ADAPTER_ENTRY_POINT_GROUP,
    ADAPTER_STATUS_ERROR,
    ADAPTER_STATUS_RUNNING,
    CalendarAdapter,
    DiscordAdapter,
    EmailAdapter,
    SlackAdapter,
    WebhookAdapter,
)
from horus_os.adapters import base as adapters_base
from horus_os.types import AgentResult

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


def _write_fake_calendar_token(data_dir: Path) -> None:
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


def _install_fake_google_minimal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install only the surface CalendarAdapter.bind needs (happy path)."""
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

    google_oauth2_credentials.Credentials = _Credentials

    googleapiclient_pkg = types.ModuleType("googleapiclient")
    googleapiclient_discovery = types.ModuleType("googleapiclient.discovery")
    googleapiclient_errors = types.ModuleType("googleapiclient.errors")
    googleapiclient_pkg.discovery = googleapiclient_discovery
    googleapiclient_pkg.errors = googleapiclient_errors

    class _HttpError(Exception):
        pass

    googleapiclient_errors.HttpError = _HttpError

    def _build(service: str, version: str, credentials: Any = None) -> Any:
        return types.SimpleNamespace()

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


def _prep_calendar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HORUS_OS_CALENDAR_OAUTH_CLIENT_PATH", "/tmp/fake-client.json")
    monkeypatch.delenv("HORUS_OS_CALENDAR_WRITE_ALLOWED", raising=False)
    _write_fake_calendar_token(tmp_path)
    _install_fake_google_minimal(monkeypatch)


def _strip_real_adapter_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make sure Discord and Email start hooks deterministically error."""
    for var in (
        "HORUS_OS_DISCORD_TOKEN",
        "HORUS_OS_EMAIL_IMAP_HOST",
        "HORUS_OS_EMAIL_IMAP_USER",
        "HORUS_OS_EMAIL_IMAP_PASSWORD",
        "HORUS_OS_EMAIL_SMTP_HOST",
    ):
        monkeypatch.delenv(var, raising=False)


# -- tests ---------------------------------------------------------------------


def test_all_five_adapters_listed_via_api_adapters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """create_app + the four new adapters + webhook = five entries.

    Gap C: the new adapters coexist through one discover_adapters
    pass without one shadowing another and without create_app
    crashing on the lifespan. The status field per adapter is
    `running` or `error` depending on configuration; the test
    asserts on the membership and on `/api/agents` still working,
    not on the per-adapter status (which is exercised by the
    isolation test below).
    """
    _init_db(tmp_path)
    _strip_real_adapter_env(monkeypatch)
    _prep_calendar(tmp_path, monkeypatch)
    _stub_entry_points(
        monkeypatch,
        [
            _FakeEntryPoint("discord", DiscordAdapter),
            _FakeEntryPoint("slack", SlackAdapter),
            _FakeEntryPoint("email", EmailAdapter),
            _FakeEntryPoint("calendar", CalendarAdapter),
            _FakeEntryPoint("webhook", WebhookAdapter),
        ],
    )
    app = create_app(data_dir=tmp_path)
    with TestClient(app) as client:
        adapters_payload = client.get("/api/adapters").json()["adapters"]
        names = {a["name"] for a in adapters_payload}
        assert names == {"discord", "slack", "email", "calendar", "webhook"}

        # The agents view stays available even with the adapter ring up.
        agents_resp = client.get("/api/agents")
        assert agents_resp.status_code == 200
        assert "agents" in agents_resp.json()


def test_adapter_error_isolation_across_real_adapters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A broken adapter does not prevent siblings from binding.

    Gap D: Discord with no token marks the registry entry `error`
    during lifespan start, but Calendar and webhook still bind
    `running`. This is the realistic operator state: half the
    integrations are configured, half are not, and the dashboard
    needs to keep functioning regardless.
    """
    _init_db(tmp_path)
    _strip_real_adapter_env(monkeypatch)
    _prep_calendar(tmp_path, monkeypatch)
    _stub_entry_points(
        monkeypatch,
        [
            _FakeEntryPoint("discord", DiscordAdapter),
            _FakeEntryPoint("calendar", CalendarAdapter),
            _FakeEntryPoint("webhook", WebhookAdapter),
        ],
    )
    app = create_app(data_dir=tmp_path)
    with TestClient(app) as client:
        entries = {a["name"]: a for a in client.get("/api/adapters").json()["adapters"]}
        # Discord errored at start (no token in env).
        assert entries["discord"]["status"] == ADAPTER_STATUS_ERROR
        assert entries["discord"]["error_count"] >= 1
        # Calendar and webhook are running despite Discord's failure.
        assert entries["calendar"]["status"] == ADAPTER_STATUS_RUNNING
        assert entries["webhook"]["status"] == ADAPTER_STATUS_RUNNING
        # The calendar tool reached app state regardless of Discord.
        tool_names = {t.name for t in app.state.tool_registry.list()}
        assert "list_calendar_events_today" in tool_names


def test_chat_trace_clean_while_adapters_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POST /api/chat works and traces stay clean while adapters are bound.

    Gap G: with the four new adapters bound (some erroring, some
    running), POST /api/chat continues to dispatch a stubbed
    run_agent_loop, the trace lands via /api/traces, and
    /api/agents does not mistakenly attribute the chat trace to
    any agent profile (because /api/chat is the unscoped path; the
    profile field stays NULL on the trace row).
    """
    _init_db(tmp_path)
    _strip_real_adapter_env(monkeypatch)
    _prep_calendar(tmp_path, monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-real")
    _stub_entry_points(
        monkeypatch,
        [
            _FakeEntryPoint("discord", DiscordAdapter),
            _FakeEntryPoint("slack", SlackAdapter),
            _FakeEntryPoint("email", EmailAdapter),
            _FakeEntryPoint("calendar", CalendarAdapter),
        ],
    )

    captured: dict[str, Any] = {}

    def _fake_loop(prompt: str, **kwargs: Any) -> AgentResult:
        captured["prompt"] = prompt
        captured["kwargs"] = kwargs
        return AgentResult(
            text="stubbed agent reply",
            tool_uses=[],
            provider=kwargs.get("provider", "anthropic"),
            model=kwargs.get("model", "test-model"),
            usage={},
        )

    # Patch on the server module since api.py does
    # `from horus_os.agent import run_agent_loop`.
    from horus_os.server import api as server_api

    monkeypatch.setattr(server_api, "run_agent_loop", _fake_loop)

    app = create_app(data_dir=tmp_path)
    with TestClient(app) as client:
        resp = client.post("/api/chat", json={"prompt": "hello", "provider": "anthropic"})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["result"]["text"] == "stubbed agent reply"
        chat_trace_id = body["trace_id"]

        # /api/traces surfaces the new trace.
        traces_payload = client.get("/api/traces").json()["traces"]
        assert any(t["trace_id"] == chat_trace_id for t in traces_payload)
        chat_trace = next(t for t in traces_payload if t["trace_id"] == chat_trace_id)
        # /api/chat is the unscoped path; agent_profile_name stays None.
        assert chat_trace.get("agent_profile_name") is None

        # /api/agents still works and lists the seeded default profile.
        agents_payload = client.get("/api/agents").json()["agents"]
        names = {a["name"] for a in agents_payload}
        assert "default" in names
        # The default profile's last_activity_at remains None because no
        # agent-scoped run has happened; the chat trace did not leak.
        default_entry = next(a for a in agents_payload if a["name"] == "default")
        assert default_entry["last_activity_at"] is None

    assert captured.get("prompt") == "hello"
