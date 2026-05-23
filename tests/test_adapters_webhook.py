"""End-to-end tests for the reference HTTP webhook adapter."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from horus_os import Config, Database
from horus_os.adapters import AdapterContext, WebhookAdapter
from horus_os.adapters import webhook as webhook_mod
from horus_os.types import AgentProfile, AgentResult


def _init_db(tmp_path: Path) -> Database:
    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    db = Database(cfg.db_path)
    db.init()
    return db


def _client(tmp_path: Path) -> TestClient:
    """Build a FastAPI app with only the webhook adapter mounted."""
    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    db = Database(cfg.db_path)
    db.init()

    app = FastAPI()
    adapter = WebhookAdapter()
    adapter.bind(app, AdapterContext(config=cfg, data_dir=tmp_path))
    return TestClient(app)


def _sign(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _fake_run_agent(captured: dict[str, Any], *, text: str = "ok") -> Any:
    def _impl(prompt: str, **kwargs: Any) -> AgentResult:
        captured["prompt"] = prompt
        captured["kwargs"] = kwargs
        return AgentResult(text=text, provider="anthropic", model="m")

    return _impl


def test_webhook_returns_503_when_secret_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("HORUS_OS_WEBHOOK_SECRET", raising=False)
    response = _client(tmp_path).post(
        "/api/adapters/webhook", content=b"{}", headers={"X-Horus-Signature": "x"}
    )
    assert response.status_code == 503
    assert "HORUS_OS_WEBHOOK_SECRET" in response.json()["detail"]


def test_webhook_returns_401_when_signature_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HORUS_OS_WEBHOOK_SECRET", "topsecret")
    response = _client(tmp_path).post("/api/adapters/webhook", content=b"{}")
    assert response.status_code == 401


def test_webhook_returns_401_when_scheme_wrong(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HORUS_OS_WEBHOOK_SECRET", "topsecret")
    response = _client(tmp_path).post(
        "/api/adapters/webhook",
        content=b"{}",
        headers={"X-Horus-Signature": "md5=abcd"},
    )
    assert response.status_code == 401


def test_webhook_returns_401_when_signature_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HORUS_OS_WEBHOOK_SECRET", "topsecret")
    response = _client(tmp_path).post(
        "/api/adapters/webhook",
        content=b'{"prompt":"hi"}',
        headers={"X-Horus-Signature": "sha256=deadbeef"},
    )
    assert response.status_code == 401


def test_webhook_returns_400_on_invalid_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HORUS_OS_WEBHOOK_SECRET", "topsecret")
    body = b"not json"
    response = _client(tmp_path).post(
        "/api/adapters/webhook",
        content=body,
        headers={"X-Horus-Signature": _sign(body, "topsecret")},
    )
    assert response.status_code == 400


def test_webhook_returns_400_when_prompt_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HORUS_OS_WEBHOOK_SECRET", "topsecret")
    body = b"{}"
    response = _client(tmp_path).post(
        "/api/adapters/webhook",
        content=body,
        headers={"X-Horus-Signature": _sign(body, "topsecret")},
    )
    assert response.status_code == 400


def test_webhook_returns_404_on_unknown_agent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HORUS_OS_WEBHOOK_SECRET", "topsecret")
    captured: dict[str, Any] = {}
    monkeypatch.setattr(webhook_mod, "run_agent", _fake_run_agent(captured))
    body = json.dumps({"prompt": "hi", "agent": "ghost"}).encode()
    response = _client(tmp_path).post(
        "/api/adapters/webhook",
        content=body,
        headers={"X-Horus-Signature": _sign(body, "topsecret")},
    )
    assert response.status_code == 404


def test_webhook_returns_400_on_unknown_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HORUS_OS_WEBHOOK_SECRET", "topsecret")
    body = json.dumps({"prompt": "hi", "provider": "openai"}).encode()
    response = _client(tmp_path).post(
        "/api/adapters/webhook",
        content=body,
        headers={"X-Horus-Signature": _sign(body, "topsecret")},
    )
    assert response.status_code == 400


def test_webhook_happy_path_runs_agent_and_records_trace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HORUS_OS_WEBHOOK_SECRET", "topsecret")
    captured: dict[str, Any] = {}
    monkeypatch.setattr(webhook_mod, "run_agent", _fake_run_agent(captured, text="hi back"))
    body = json.dumps({"prompt": "hello world"}).encode()
    response = _client(tmp_path).post(
        "/api/adapters/webhook",
        content=body,
        headers={"X-Horus-Signature": _sign(body, "topsecret")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["text"] == "hi back"
    assert isinstance(payload["trace_id"], str) and len(payload["trace_id"]) == 32
    assert payload["latency_ms"] >= 0
    assert captured["prompt"] == "hello world"
    # the trace row was persisted
    cfg = Config.with_defaults(tmp_path)
    db = Database(cfg.db_path)
    record = db.get_trace(payload["trace_id"])
    assert record is not None
    assert record.prompt == "hello world"


def test_webhook_forwards_agent_profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HORUS_OS_WEBHOOK_SECRET", "topsecret")
    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    db = Database(cfg.db_path)
    db.init()
    db.save_profile(
        AgentProfile(
            name="terse",
            system_prompt="be terse",
            default_model="claude-sonnet-4-6",
        )
    )

    captured: dict[str, Any] = {}
    monkeypatch.setattr(webhook_mod, "run_agent", _fake_run_agent(captured))

    body = json.dumps({"prompt": "hi", "agent": "terse"}).encode()
    app = FastAPI()
    adapter = WebhookAdapter()
    adapter.bind(app, AdapterContext(config=cfg, data_dir=tmp_path))
    client = TestClient(app)

    response = client.post(
        "/api/adapters/webhook",
        content=body,
        headers={"X-Horus-Signature": _sign(body, "topsecret")},
    )
    assert response.status_code == 200
    assert captured["kwargs"].get("system_prompt") == "be terse"
    assert captured["kwargs"].get("model") == "claude-sonnet-4-6"

    record = db.get_trace(response.json()["trace_id"])
    assert record is not None
    assert record.agent_profile_name == "terse"


def test_webhook_user_model_wins_over_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HORUS_OS_WEBHOOK_SECRET", "topsecret")
    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    db = Database(cfg.db_path)
    db.init()
    db.save_profile(
        AgentProfile(
            name="terse",
            system_prompt="be terse",
            default_model="profile-model",
        )
    )
    captured: dict[str, Any] = {}
    monkeypatch.setattr(webhook_mod, "run_agent", _fake_run_agent(captured))

    body = json.dumps({"prompt": "hi", "agent": "terse", "model": "override"}).encode()
    app = FastAPI()
    WebhookAdapter().bind(app, AdapterContext(config=cfg, data_dir=tmp_path))
    response = TestClient(app).post(
        "/api/adapters/webhook",
        content=body,
        headers={"X-Horus-Signature": _sign(body, "topsecret")},
    )
    assert response.status_code == 200
    assert captured["kwargs"].get("model") == "override"


def test_webhook_adapter_describe_metadata(tmp_path: Path) -> None:
    adapter = WebhookAdapter()
    meta = adapter.describe()
    assert meta["name"] == "webhook"
    assert meta["endpoint"] == "/api/adapters/webhook"
    assert meta["auth"] == "hmac-sha256"
    assert meta["env"] == "HORUS_OS_WEBHOOK_SECRET"


def test_webhook_run_agent_exception_recorded_as_error_trace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HORUS_OS_WEBHOOK_SECRET", "topsecret")

    def _boom(prompt: str, **kwargs: Any) -> AgentResult:
        raise RuntimeError("provider exploded")

    monkeypatch.setattr(webhook_mod, "run_agent", _boom)
    body = json.dumps({"prompt": "hi"}).encode()
    response = _client(tmp_path).post(
        "/api/adapters/webhook",
        content=body,
        headers={"X-Horus-Signature": _sign(body, "topsecret")},
    )
    assert response.status_code == 500
    detail = response.json()["detail"]
    assert "RuntimeError" in detail["error"]
    cfg = Config.with_defaults(tmp_path)
    db = Database(cfg.db_path)
    record = db.get_trace(detail["trace_id"])
    assert record is not None
    assert record.status == "error"


def test_webhook_entry_point_registered() -> None:
    """The reference adapter is declared in pyproject and discoverable."""
    from importlib.metadata import entry_points

    eps = list(entry_points(group="horus_os.adapters"))
    names = {ep.name for ep in eps}
    assert "webhook" in names
    webhook_ep = next(ep for ep in eps if ep.name == "webhook")
    assert webhook_ep.load() is WebhookAdapter
