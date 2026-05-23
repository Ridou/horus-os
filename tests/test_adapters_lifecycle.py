"""Tests for adapter lifecycle hooks, the AdapterRegistry, and FastAPI lifespan integration."""

from __future__ import annotations

import re
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
    AdapterEntry,
    AdapterRegistry,
    LifecycleAdapter,
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


# -- registry ------------------------------------------------------------------


def test_registry_register_creates_stopped_entry() -> None:
    reg = AdapterRegistry()
    entry = reg.register("alpha")
    assert isinstance(entry, AdapterEntry)
    assert entry.name == "alpha"
    assert entry.status == ADAPTER_STATUS_STOPPED
    assert entry.last_activity_at is None
    assert entry.error_count == 0
    assert entry.error_message is None


def test_registry_register_is_idempotent() -> None:
    reg = AdapterRegistry()
    a = reg.register("alpha")
    b = reg.register("alpha")
    assert a is b
    assert len(reg.entries()) == 1


def test_registry_mark_running_transitions_status() -> None:
    reg = AdapterRegistry()
    reg.register("alpha")
    reg.mark_running("alpha")
    assert reg.get("alpha").status == ADAPTER_STATUS_RUNNING


def test_registry_mark_stopped_transitions_status() -> None:
    reg = AdapterRegistry()
    reg.register("alpha")
    reg.mark_running("alpha")
    reg.mark_stopped("alpha")
    assert reg.get("alpha").status == ADAPTER_STATUS_STOPPED


def test_registry_mark_error_increments_count_and_stores_message() -> None:
    reg = AdapterRegistry()
    reg.register("alpha")
    reg.mark_error("alpha", "RuntimeError: boom")
    entry = reg.get("alpha")
    assert entry.status == ADAPTER_STATUS_ERROR
    assert entry.error_count == 1
    assert entry.error_message == "RuntimeError: boom"
    reg.mark_error("alpha", "ValueError: nope")
    entry = reg.get("alpha")
    assert entry.error_count == 2
    assert entry.error_message == "ValueError: nope"


def test_registry_touch_writes_iso8601_timestamp() -> None:
    reg = AdapterRegistry()
    reg.register("alpha")
    reg.touch("alpha")
    ts = reg.get("alpha").last_activity_at
    assert ts is not None
    # UTC iso8601 with a +00:00 offset
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?\+00:00$", ts)


def test_registry_entries_sorted_by_name() -> None:
    reg = AdapterRegistry()
    reg.register("zebra")
    reg.register("alpha")
    reg.register("mango")
    names = [e.name for e in reg.entries()]
    assert names == ["alpha", "mango", "zebra"]


def test_registry_mutators_are_noops_for_unknown_names() -> None:
    reg = AdapterRegistry()
    reg.mark_running("ghost")
    reg.mark_stopped("ghost")
    reg.mark_error("ghost", "boom")
    reg.touch("ghost")
    assert reg.entries() == []


# -- LifecycleAdapter Protocol -------------------------------------------------


def test_lifecycle_adapter_runtime_checkable_passes_when_both_methods_present() -> None:
    class _Full:
        name = "full"

        async def start(self, context: AdapterContext) -> None:
            return None

        async def stop(self) -> None:
            return None

    assert isinstance(_Full(), LifecycleAdapter)


def test_lifecycle_adapter_runtime_checkable_fails_when_method_missing() -> None:
    class _OnlyStart:
        name = "half"

        async def start(self, context: AdapterContext) -> None:
            return None

    # Missing `stop` means the Protocol attribute check fails.
    assert not isinstance(_OnlyStart(), LifecycleAdapter)


# -- AdapterContext default factory --------------------------------------------


def test_adapter_context_default_registry_is_empty(tmp_path: Path) -> None:
    cfg = Config.with_defaults(tmp_path)
    ctx = AdapterContext(config=cfg, data_dir=tmp_path)
    assert isinstance(ctx.registry, AdapterRegistry)
    assert ctx.registry.entries() == []


def test_adapter_context_accepts_explicit_registry(tmp_path: Path) -> None:
    cfg = Config.with_defaults(tmp_path)
    reg = AdapterRegistry()
    reg.register("alpha")
    ctx = AdapterContext(config=cfg, data_dir=tmp_path, registry=reg)
    assert ctx.registry is reg
    assert [e.name for e in ctx.registry.entries()] == ["alpha"]


# -- lifespan integration via TestClient ---------------------------------------


class _StartOnlyAdapter:
    name = "starter"

    def __init__(self) -> None:
        self.started = 0
        self.context_seen: AdapterContext | None = None

    def bind(self, app: Any, context: AdapterContext) -> None:
        return None

    async def start(self, context: AdapterContext) -> None:
        self.started += 1
        self.context_seen = context


class _StopOnlyAdapter:
    name = "stopper"

    def __init__(self) -> None:
        self.stopped = 0

    def bind(self, app: Any, context: AdapterContext) -> None:
        return None

    async def stop(self) -> None:
        self.stopped += 1


class _FullLifecycleAdapter:
    name = "full_lifecycle"

    def __init__(self) -> None:
        self.started = 0
        self.stopped = 0

    def bind(self, app: Any, context: AdapterContext) -> None:
        return None

    async def start(self, context: AdapterContext) -> None:
        self.started += 1

    async def stop(self) -> None:
        self.stopped += 1


class _StartRaisesAdapter:
    name = "start_raises"

    def bind(self, app: Any, context: AdapterContext) -> None:
        return None

    async def start(self, context: AdapterContext) -> None:
        raise RuntimeError("start boom")

    async def stop(self) -> None:
        return None


class _StopRaisesAdapter:
    name = "stop_raises"

    def bind(self, app: Any, context: AdapterContext) -> None:
        return None

    async def start(self, context: AdapterContext) -> None:
        return None

    async def stop(self) -> None:
        raise RuntimeError("stop boom")


def test_lifespan_runs_start_on_enter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_db(tmp_path)
    adapter = _StartOnlyAdapter()
    _stub_entry_points(
        monkeypatch,
        [_FakeEntryPoint(adapter.name, lambda: adapter)],
    )
    app = create_app(data_dir=tmp_path)
    # Before entering the TestClient context, lifespan has not fired.
    assert adapter.started == 0
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        assert adapter.started == 1
        registry: AdapterRegistry = app.state.adapter_registry
        assert registry.get(adapter.name).status == ADAPTER_STATUS_RUNNING


def test_lifespan_runs_stop_on_exit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_db(tmp_path)
    adapter = _StopOnlyAdapter()
    _stub_entry_points(
        monkeypatch,
        [_FakeEntryPoint(adapter.name, lambda: adapter)],
    )
    app = create_app(data_dir=tmp_path)
    with TestClient(app):
        assert adapter.stopped == 0
    assert adapter.stopped == 1


def test_lifespan_runs_full_lifecycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_db(tmp_path)
    adapter = _FullLifecycleAdapter()
    _stub_entry_points(
        monkeypatch,
        [_FakeEntryPoint(adapter.name, lambda: adapter)],
    )
    app = create_app(data_dir=tmp_path)
    with TestClient(app):
        assert adapter.started == 1
        assert adapter.stopped == 0
    assert adapter.stopped == 1


def test_lifespan_start_exception_isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_db(tmp_path)
    broken = _StartRaisesAdapter()
    good = _FullLifecycleAdapter()
    _stub_entry_points(
        monkeypatch,
        [
            _FakeEntryPoint(broken.name, lambda: broken),
            _FakeEntryPoint(good.name, lambda: good),
        ],
    )
    app = create_app(data_dir=tmp_path)
    with TestClient(app) as client:
        # Core route is reachable; the broken adapter did not abort lifespan.
        assert client.get("/api/health").status_code == 200
        registry: AdapterRegistry = app.state.adapter_registry
        broken_entry = registry.get(broken.name)
        assert broken_entry.status == ADAPTER_STATUS_ERROR
        assert broken_entry.error_count >= 1
        assert "RuntimeError" in (broken_entry.error_message or "")
        # The good adapter still started.
        assert good.started == 1
        assert registry.get(good.name).status == ADAPTER_STATUS_RUNNING


def test_lifespan_stop_exception_does_not_break_shutdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_db(tmp_path)
    adapter = _StopRaisesAdapter()
    _stub_entry_points(
        monkeypatch,
        [_FakeEntryPoint(adapter.name, lambda: adapter)],
    )
    app = create_app(data_dir=tmp_path)
    # Entering and exiting the TestClient context must not raise.
    with TestClient(app):
        pass
    registry: AdapterRegistry = app.state.adapter_registry
    entry = registry.get(adapter.name)
    assert entry.error_count >= 1
    assert "RuntimeError" in (entry.error_message or "")


def test_lifespan_dispatch_uses_hasattr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An adapter with only `start` (and no `stop`) still runs cleanly."""
    _init_db(tmp_path)
    adapter = _StartOnlyAdapter()
    assert not hasattr(adapter, "stop")
    _stub_entry_points(
        monkeypatch,
        [_FakeEntryPoint(adapter.name, lambda: adapter)],
    )
    app = create_app(data_dir=tmp_path)
    with TestClient(app):
        assert adapter.started == 1
    # No exception on exit even though there is no stop method.


def test_webhook_adapter_is_running_after_create_app(
    tmp_path: Path,
) -> None:
    """The reference WebhookAdapter has no start/stop but still reports running."""
    _init_db(tmp_path)
    # No entry-point stubbing: the real `webhook` entry point ships in pyproject.
    app = create_app(data_dir=tmp_path)
    with TestClient(app):
        registry: AdapterRegistry = app.state.adapter_registry
        entry = registry.get("webhook")
        assert entry is not None
        assert entry.status == ADAPTER_STATUS_RUNNING
