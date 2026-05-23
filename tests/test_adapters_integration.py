"""Tests for adapter discovery and FastAPI integration via TestClient."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from horus_os import Config, Database, create_app
from horus_os.adapters import ADAPTER_ENTRY_POINT_GROUP, AdapterContext
from horus_os.adapters import base as adapters_base


class _FakeEntryPoint:
    def __init__(self, name: str, target: Any) -> None:
        self.name = name
        self._target = target

    def load(self) -> Any:
        return self._target


class _MountingAdapter:
    """A test adapter that mounts a single GET route announcing itself."""

    name = "fake_third_party"

    def __init__(self) -> None:
        self.captured_context: AdapterContext | None = None

    def bind(self, app: Any, context: AdapterContext) -> None:
        self.captured_context = context

        @app.get(f"/api/adapters/{self.name}/ping")
        def _ping() -> dict[str, str]:
            return {"adapter": self.name, "data_dir": str(context.data_dir)}


class _RaisingAdapter:
    name = "raises_on_bind"

    def bind(self, app: Any, context: AdapterContext) -> None:
        raise RuntimeError("simulated bind failure")


def _init_db(tmp_path: Path) -> None:
    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    db = Database(cfg.db_path)
    db.init()


def _stub_entry_points(monkeypatch: pytest.MonkeyPatch, eps: list[_FakeEntryPoint]) -> None:
    def fake(group: str | None = None) -> list[_FakeEntryPoint]:
        if group != ADAPTER_ENTRY_POINT_GROUP:
            return []
        return eps

    monkeypatch.setattr(adapters_base, "entry_points", fake)


def test_create_app_without_adapters_keeps_core_routes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_db(tmp_path)
    _stub_entry_points(monkeypatch, [])
    client = TestClient(create_app(data_dir=tmp_path))
    response = client.get("/api/health")
    assert response.status_code == 200


def test_third_party_adapter_route_is_mounted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_db(tmp_path)
    _stub_entry_points(
        monkeypatch,
        [_FakeEntryPoint("fake_third_party", _MountingAdapter)],
    )
    client = TestClient(create_app(data_dir=tmp_path))
    response = client.get("/api/adapters/fake_third_party/ping")
    assert response.status_code == 200
    body = response.json()
    assert body["adapter"] == "fake_third_party"
    assert body["data_dir"] == str(tmp_path)


def test_adapter_bind_failure_does_not_break_app(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_db(tmp_path)
    _stub_entry_points(
        monkeypatch,
        [
            _FakeEntryPoint("raises_on_bind", _RaisingAdapter),
            _FakeEntryPoint("fake_third_party", _MountingAdapter),
        ],
    )
    client = TestClient(create_app(data_dir=tmp_path))
    # core route still works
    assert client.get("/api/health").status_code == 200
    # the well-behaved adapter still mounted despite the sibling failure
    assert client.get("/api/adapters/fake_third_party/ping").status_code == 200


def test_adapter_context_uses_resolved_data_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_db(tmp_path)
    adapter = _MountingAdapter()
    _stub_entry_points(
        monkeypatch,
        [_FakeEntryPoint("fake_third_party", lambda: adapter)],
    )
    create_app(data_dir=tmp_path)
    assert adapter.captured_context is not None
    assert adapter.captured_context.data_dir == tmp_path
    assert adapter.captured_context.config.data_dir == tmp_path
