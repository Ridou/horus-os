"""Tests for the enable/disable adapter routes and tool_registry wiring."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from horus_os import Config, Database, create_app
from horus_os.adapters import (
    ADAPTER_ENTRY_POINT_GROUP,
    ADAPTER_STATUS_ERROR,
    ADAPTER_STATUS_RUNNING,
    ADAPTER_STATUS_STOPPED,
    AdapterContext,
)
from horus_os.adapters import base as adapters_base
from horus_os.tools import ToolRegistry
from horus_os.types import Tool

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


# -- adapter fixtures ----------------------------------------------------------


class _LifecycleAdapter:
    name = "lifecycle"

    def __init__(self) -> None:
        self.start_calls = 0
        self.stop_calls = 0

    def bind(self, app: Any, context: AdapterContext) -> None:
        return None

    async def start(self, context: AdapterContext) -> None:
        self.start_calls += 1

    async def stop(self) -> None:
        self.stop_calls += 1


class _StartRaisesAdapter:
    name = "start_boom"

    def bind(self, app: Any, context: AdapterContext) -> None:
        return None

    async def start(self, context: AdapterContext) -> None:
        raise RuntimeError("start failed")

    async def stop(self) -> None:
        return None


class _StopRaisesAdapter:
    name = "stop_boom"

    def bind(self, app: Any, context: AdapterContext) -> None:
        return None

    async def start(self, context: AdapterContext) -> None:
        return None

    async def stop(self) -> None:
        raise RuntimeError("stop failed")


class _BindOnlyAdapter:
    """An adapter with no lifecycle hooks at all."""

    name = "bindonly"

    def bind(self, app: Any, context: AdapterContext) -> None:
        return None


class _ToolProvidingAdapter:
    """A Calendar-shaped adapter: registers tools at bind time."""

    name = "toolprovider"

    def bind(self, app: Any, context: AdapterContext) -> None:
        if context.tool_registry is None:
            return
        context.tool_registry.register(
            Tool(
                name="adapter_echo",
                description="echo for tests",
                parameters={"type": "object", "properties": {}},
                handler=lambda **kw: {"echoed": True},
            )
        )


# -- toggle route tests --------------------------------------------------------


def test_disable_404_when_adapter_unknown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_db(tmp_path)
    _stub_entry_points(monkeypatch, [])
    app = create_app(data_dir=tmp_path)
    with TestClient(app) as client:
        r = client.post("/api/adapters/ghost/disable")
        assert r.status_code == 404
        assert "not found" in r.json()["detail"]


def test_enable_404_when_adapter_unknown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_db(tmp_path)
    _stub_entry_points(monkeypatch, [])
    app = create_app(data_dir=tmp_path)
    with TestClient(app) as client:
        r = client.post("/api/adapters/ghost/enable")
        assert r.status_code == 404


def test_disable_400_when_adapter_has_no_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_db(tmp_path)
    _stub_entry_points(monkeypatch, [_FakeEntryPoint("bindonly", _BindOnlyAdapter)])
    app = create_app(data_dir=tmp_path)
    with TestClient(app) as client:
        r = client.post("/api/adapters/bindonly/disable")
        assert r.status_code == 400
        assert "does not support disable" in r.json()["detail"]


def test_enable_400_when_adapter_has_no_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_db(tmp_path)
    _stub_entry_points(monkeypatch, [_FakeEntryPoint("bindonly", _BindOnlyAdapter)])
    app = create_app(data_dir=tmp_path)
    with TestClient(app) as client:
        r = client.post("/api/adapters/bindonly/enable")
        assert r.status_code == 400
        assert "does not support enable" in r.json()["detail"]


def test_disable_flips_status_and_calls_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_db(tmp_path)
    adapter = _LifecycleAdapter()
    _stub_entry_points(monkeypatch, [_FakeEntryPoint(adapter.name, lambda: adapter)])
    app = create_app(data_dir=tmp_path)
    with TestClient(app) as client:
        # Lifespan start fired during TestClient enter; status is running.
        before = next(
            e for e in client.get("/api/adapters").json()["adapters"] if e["name"] == adapter.name
        )
        assert before["status"] == ADAPTER_STATUS_RUNNING

        r = client.post(f"/api/adapters/{adapter.name}/disable")
        assert r.status_code == 200
        assert r.json() == {"name": adapter.name, "status": ADAPTER_STATUS_STOPPED}
        assert adapter.stop_calls == 1

        after = next(
            e for e in client.get("/api/adapters").json()["adapters"] if e["name"] == adapter.name
        )
        assert after["status"] == ADAPTER_STATUS_STOPPED


def test_enable_flips_status_and_calls_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_db(tmp_path)
    adapter = _LifecycleAdapter()
    _stub_entry_points(monkeypatch, [_FakeEntryPoint(adapter.name, lambda: adapter)])
    app = create_app(data_dir=tmp_path)
    with TestClient(app) as client:
        # Disable first so we can re-enable from a stopped baseline.
        client.post(f"/api/adapters/{adapter.name}/disable")
        adapter.start_calls = 0  # ignore the lifespan start call

        r = client.post(f"/api/adapters/{adapter.name}/enable")
        assert r.status_code == 200
        assert r.json() == {"name": adapter.name, "status": ADAPTER_STATUS_RUNNING}
        assert adapter.start_calls == 1

        after = next(
            e for e in client.get("/api/adapters").json()["adapters"] if e["name"] == adapter.name
        )
        assert after["status"] == ADAPTER_STATUS_RUNNING


def test_disable_500_when_stop_raises_marks_registry_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_db(tmp_path)
    _stub_entry_points(monkeypatch, [_FakeEntryPoint("stop_boom", _StopRaisesAdapter)])
    app = create_app(data_dir=tmp_path)
    with TestClient(app) as client:
        r = client.post("/api/adapters/stop_boom/disable")
        assert r.status_code == 500
        assert "stop hook raised" in r.json()["detail"]
        entries = {e["name"]: e for e in client.get("/api/adapters").json()["adapters"]}
        assert entries["stop_boom"]["status"] == ADAPTER_STATUS_ERROR
        assert entries["stop_boom"]["error_count"] >= 1
        assert "RuntimeError" in (entries["stop_boom"]["error_message"] or "")


def test_enable_500_when_start_raises_marks_registry_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_db(tmp_path)
    _stub_entry_points(monkeypatch, [_FakeEntryPoint("start_boom", _StartRaisesAdapter)])
    app = create_app(data_dir=tmp_path)
    with TestClient(app) as client:
        # Lifespan start already errored; the route firing again is a manual
        # operator retry that should also fail and re-mark error.
        r = client.post("/api/adapters/start_boom/enable")
        assert r.status_code == 500
        assert "start hook raised" in r.json()["detail"]
        entries = {e["name"]: e for e in client.get("/api/adapters").json()["adapters"]}
        assert entries["start_boom"]["status"] == ADAPTER_STATUS_ERROR
        assert entries["start_boom"]["error_count"] >= 1


def test_supports_toggle_field_present_per_adapter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_db(tmp_path)
    adapter = _LifecycleAdapter()
    _stub_entry_points(
        monkeypatch,
        [
            _FakeEntryPoint("lifecycle", lambda: adapter),
            _FakeEntryPoint("bindonly", _BindOnlyAdapter),
        ],
    )
    app = create_app(data_dir=tmp_path)
    with TestClient(app) as client:
        entries = {e["name"]: e for e in client.get("/api/adapters").json()["adapters"]}
        assert entries["lifecycle"]["supports_toggle"] is True
        assert entries["bindonly"]["supports_toggle"] is False


# -- tool_registry wiring tests (Phase 26 deferred) ----------------------------


def test_app_state_tool_registry_is_a_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_db(tmp_path)
    _stub_entry_points(monkeypatch, [])
    app = create_app(data_dir=tmp_path)
    assert isinstance(app.state.tool_registry, ToolRegistry)


def test_tool_providing_adapter_registers_tool_on_app_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_db(tmp_path)
    _stub_entry_points(monkeypatch, [_FakeEntryPoint("toolprovider", _ToolProvidingAdapter)])
    app = create_app(data_dir=tmp_path)
    # bind already ran during create_app; the tool should be on app state.
    tools = app.state.tool_registry.list()
    assert any(t.name == "adapter_echo" for t in tools)


def test_app_state_adapters_lists_discovered_adapters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_db(tmp_path)
    adapter = _LifecycleAdapter()
    _stub_entry_points(monkeypatch, [_FakeEntryPoint(adapter.name, lambda: adapter)])
    app = create_app(data_dir=tmp_path)
    names = [a.name for a in app.state.adapters]
    assert adapter.name in names
