"""End-to-end adapter lifecycle state-machine arc.

Phase 29 gap A: Phase 22 covered the AdapterRegistry mutators and
the FastAPI lifespan-driven start and stop hooks in isolation. No
single phase exercised the full state-machine arc
`stopped -> running -> error -> stopped -> running` against a real
LifecycleAdapter and confirmed the registry status mirrors every
transition. This file closes that integration seam.

Pattern reuse: monkeypatching `adapters_base.entry_points` to surface
a single fake adapter, then asserting on `AdapterRegistry` state
both directly and via `GET /api/adapters`.
"""

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
    AdapterRegistry,
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


class _ArcAdapter:
    """A lifecycle adapter that records how many times each hook fired."""

    name = "arc"

    def __init__(self) -> None:
        self.start_calls = 0
        self.stop_calls = 0

    def bind(self, app: Any, context: AdapterContext) -> None:
        return None

    async def start(self, context: AdapterContext) -> None:
        self.start_calls += 1

    async def stop(self) -> None:
        self.stop_calls += 1


# -- tests ---------------------------------------------------------------------


def test_full_state_machine_arc_through_registry_only() -> None:
    """Walk the registry through every defined transition.

    `stopped` (register) -> `running` (mark_running) -> `error`
    (mark_error) -> `stopped` (mark_stopped) -> `running`
    (mark_running). `error_count` and the most recent
    `error_message` persist across subsequent status changes;
    `last_activity_at` survives the cycle once `touch` has fired.
    """
    reg = AdapterRegistry()
    entry = reg.register("arc")
    assert entry.status == ADAPTER_STATUS_STOPPED

    reg.mark_running("arc")
    assert reg.get("arc").status == ADAPTER_STATUS_RUNNING

    reg.touch("arc")
    first_touch = reg.get("arc").last_activity_at
    assert first_touch is not None

    reg.mark_error("arc", "RuntimeError: simulated outage")
    err_entry = reg.get("arc")
    assert err_entry.status == ADAPTER_STATUS_ERROR
    assert err_entry.error_count == 1
    assert "simulated outage" in (err_entry.error_message or "")

    reg.mark_stopped("arc")
    stopped_entry = reg.get("arc")
    assert stopped_entry.status == ADAPTER_STATUS_STOPPED
    # Error history persists across the stop transition.
    assert stopped_entry.error_count == 1
    assert "simulated outage" in (stopped_entry.error_message or "")
    # last_activity_at also persists across status transitions.
    assert stopped_entry.last_activity_at == first_touch

    reg.mark_running("arc")
    revived_entry = reg.get("arc")
    assert revived_entry.status == ADAPTER_STATUS_RUNNING
    # And the error history still persists after recovery; the next
    # successful traffic is the operator's signal that things are well.
    assert revived_entry.error_count == 1


def test_lifecycle_arc_through_create_app_disable_enable_round_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same arc, but every transition is driven by FastAPI surfaces.

    `create_app` discovers the adapter -> bind marks running ->
    lifespan start increments start_calls -> POST disable -> POST
    enable -> GET /api/adapters confirms each transition. This
    closes the seam between the registry unit tests and the route
    tests: nothing in the existing suite drives a full
    disable+enable cycle and asserts the round-trip via the public
    API in one test.
    """
    _init_db(tmp_path)
    adapter = _ArcAdapter()
    _stub_entry_points(monkeypatch, [_FakeEntryPoint(adapter.name, lambda: adapter)])
    app = create_app(data_dir=tmp_path)
    with TestClient(app) as client:
        # Lifespan start has fired once during TestClient enter.
        assert adapter.start_calls == 1
        running = next(
            e for e in client.get("/api/adapters").json()["adapters"] if e["name"] == adapter.name
        )
        assert running["status"] == ADAPTER_STATUS_RUNNING

        # Disable: stop hook fires, status flips to stopped.
        r = client.post(f"/api/adapters/{adapter.name}/disable")
        assert r.status_code == 200
        assert r.json()["status"] == ADAPTER_STATUS_STOPPED
        assert adapter.stop_calls == 1
        stopped = next(
            e for e in client.get("/api/adapters").json()["adapters"] if e["name"] == adapter.name
        )
        assert stopped["status"] == ADAPTER_STATUS_STOPPED

        # Enable: start hook fires again, status flips back to running.
        r = client.post(f"/api/adapters/{adapter.name}/enable")
        assert r.status_code == 200
        assert r.json()["status"] == ADAPTER_STATUS_RUNNING
        assert adapter.start_calls == 2
        revived = next(
            e for e in client.get("/api/adapters").json()["adapters"] if e["name"] == adapter.name
        )
        assert revived["status"] == ADAPTER_STATUS_RUNNING
