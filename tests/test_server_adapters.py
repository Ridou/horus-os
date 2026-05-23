"""Tests for the GET /api/adapters status endpoint."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from horus_os import Config, Database, create_app
from horus_os.adapters import (
    ADAPTER_ENTRY_POINT_GROUP,
    ADAPTER_STATUS_ERROR,
    ADAPTER_STATUS_RUNNING,
    AdapterContext,
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


def _sign(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


# -- fake adapters -------------------------------------------------------------


class _MountingAdapter:
    name = "fake_third_party"

    def bind(self, app: Any, context: AdapterContext) -> None:
        @app.get(f"/api/adapters/{self.name}/ping")
        def _ping() -> dict[str, str]:
            return {"adapter": self.name}


class _BindRaisesAdapter:
    name = "broken_bind"

    def bind(self, app: Any, context: AdapterContext) -> None:
        raise RuntimeError("simulated bind failure")


# -- tests ---------------------------------------------------------------------


def test_get_adapters_empty_when_no_adapters_discovered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_db(tmp_path)
    _stub_entry_points(monkeypatch, [])
    app = create_app(data_dir=tmp_path)
    with TestClient(app) as client:
        response = client.get("/api/adapters")
        assert response.status_code == 200
        assert response.json() == {"adapters": []}


def test_get_adapters_returns_expected_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_db(tmp_path)
    _stub_entry_points(
        monkeypatch,
        [_FakeEntryPoint("fake_third_party", _MountingAdapter)],
    )
    app = create_app(data_dir=tmp_path)
    with TestClient(app) as client:
        response = client.get("/api/adapters")
        assert response.status_code == 200
        body = response.json()
        assert "adapters" in body
        assert len(body["adapters"]) == 1
        entry = body["adapters"][0]
        assert set(entry.keys()) == {
            "name",
            "status",
            "last_activity_at",
            "error_count",
            "error_message",
            "supports_toggle",
        }
        assert entry["name"] == "fake_third_party"
        assert entry["status"] == ADAPTER_STATUS_RUNNING
        assert entry["last_activity_at"] is None
        assert entry["error_count"] == 0
        assert entry["error_message"] is None
        # Phase 27: the fake adapter has neither start nor stop.
        assert entry["supports_toggle"] is False


def test_get_adapters_lists_real_webhook_as_running(tmp_path: Path) -> None:
    """No entry-point stub: the real `webhook` entry point ships in pyproject."""
    _init_db(tmp_path)
    app = create_app(data_dir=tmp_path)
    with TestClient(app) as client:
        response = client.get("/api/adapters")
        assert response.status_code == 200
        names = {e["name"]: e for e in response.json()["adapters"]}
        assert "webhook" in names
        assert names["webhook"]["status"] == ADAPTER_STATUS_RUNNING
        assert names["webhook"]["last_activity_at"] is None
        # Phase 27: the reference WebhookAdapter has no lifecycle hooks.
        assert names["webhook"]["supports_toggle"] is False


def test_get_adapters_sorted_by_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_db(tmp_path)

    class _Alpha:
        name = "alpha"

        def bind(self, app: Any, context: AdapterContext) -> None:
            return None

    class _Zebra:
        name = "zebra"

        def bind(self, app: Any, context: AdapterContext) -> None:
            return None

    _stub_entry_points(
        monkeypatch,
        [
            _FakeEntryPoint("zebra", _Zebra),
            _FakeEntryPoint("alpha", _Alpha),
        ],
    )
    app = create_app(data_dir=tmp_path)
    with TestClient(app) as client:
        names = [e["name"] for e in client.get("/api/adapters").json()["adapters"]]
        assert names == ["alpha", "zebra"]


def test_bind_failure_recorded_as_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_db(tmp_path)
    _stub_entry_points(
        monkeypatch,
        [
            _FakeEntryPoint("broken_bind", _BindRaisesAdapter),
            _FakeEntryPoint("fake_third_party", _MountingAdapter),
        ],
    )
    app = create_app(data_dir=tmp_path)
    with TestClient(app) as client:
        body = client.get("/api/adapters").json()
        entries = {e["name"]: e for e in body["adapters"]}
        broken = entries["broken_bind"]
        assert broken["status"] == ADAPTER_STATUS_ERROR
        assert broken["error_count"] >= 1
        assert "RuntimeError" in (broken["error_message"] or "")
        # The other adapter still mounted and runs.
        good = entries["fake_third_party"]
        assert good["status"] == ADAPTER_STATUS_RUNNING
        assert client.get("/api/adapters/fake_third_party/ping").status_code == 200


def test_webhook_request_updates_last_activity_at(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A successful POST to /api/adapters/webhook bumps the registry entry."""
    from horus_os.adapters import webhook as webhook_mod
    from horus_os.types import AgentResult

    _init_db(tmp_path)
    monkeypatch.setenv("HORUS_OS_WEBHOOK_SECRET", "topsecret")

    def _fake_run_agent(prompt: str, **kwargs: Any) -> AgentResult:
        return AgentResult(text="ok", provider="anthropic", model="m")

    monkeypatch.setattr(webhook_mod, "run_agent", _fake_run_agent)

    app = create_app(data_dir=tmp_path)
    with TestClient(app) as client:
        before = client.get("/api/adapters").json()
        before_entry = next(e for e in before["adapters"] if e["name"] == "webhook")
        assert before_entry["last_activity_at"] is None

        body = json.dumps({"prompt": "hi"}).encode()
        response = client.post(
            "/api/adapters/webhook",
            content=body,
            headers={"X-Horus-Signature": _sign(body, "topsecret")},
        )
        assert response.status_code == 200

        after = client.get("/api/adapters").json()
        after_entry = next(e for e in after["adapters"] if e["name"] == "webhook")
        assert after_entry["last_activity_at"] is not None
        assert after_entry["status"] == ADAPTER_STATUS_RUNNING
