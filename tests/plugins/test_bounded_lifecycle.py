"""ISOLATE-02 coverage: bounded asyncio.wait_for(start, timeout=2.0).

A 5-second sleep in a synthetic plugin adapter's ``start()`` MUST be
cut by the lifespan's wait_for budget within ~2.5 seconds of wall
clock. The failure surfaces as ``status='error'`` /
``error_phase='start'`` on the plugin registry entry; FastAPI lifespan
continues serving requests.

The synthetic SlowAdapter is wired by monkeypatching
``PluginLoader.load`` to return a PluginLoadResult that pre-materializes
the adapter, so the test does not depend on any real entry-point
discovery or filesystem fixture.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from horus_os.plugins import (
    PLUGIN_STATUS_ERROR,
    PLUGIN_STATUS_LOADED,
    PluginLoadResult,
)

# --- Synthetic adapter fixtures --------------------------------------------


class _SlowStartAdapter:
    """Sleeps 5.0s in start; ``asyncio.wait_for(2.0)`` should cut it."""

    name = "slow-start-adapter"

    async def start(self, _ctx: object) -> None:
        await asyncio.sleep(5.0)

    async def stop(self) -> None:
        return None


class _SlowStopAdapter:
    """Returns from start instantly; sleeps 5.0s in stop."""

    name = "slow-stop-adapter"

    async def start(self, _ctx: object) -> None:
        return None

    async def stop(self) -> None:
        await asyncio.sleep(5.0)


class _RaisingStartAdapter:
    """start() raises ValueError → status='error', error_phase='start'."""

    name = "raises-on-start-adapter"

    async def start(self, _ctx: object) -> None:
        raise ValueError("synthetic start failure")

    async def stop(self) -> None:
        return None


class _RaisingStopAdapter:
    """stop() raises → status='error', error_phase='stop'."""

    name = "raises-on-stop-adapter"

    async def start(self, _ctx: object) -> None:
        return None

    async def stop(self) -> None:
        raise RuntimeError("synthetic stop failure")


class _FastAdapter:
    """Returns immediately from both start and stop."""

    name = "fast-adapter"

    async def start(self, _ctx: object) -> None:
        return None

    async def stop(self) -> None:
        return None


# --- Test harness ----------------------------------------------------------


def _make_synthetic_spec(name: str) -> object:
    """Build a minimal PluginSpec that the lifespan can register.

    The spec carries zero tool_entries / adapter_entries — we route
    the adapter into the lifespan via the monkeypatched
    PluginLoader.load return value (PluginLoadResult.materialized_adapters)
    rather than through entry-point resolution.
    """
    from horus_os.plugins.spec import PluginSpec

    return PluginSpec(
        name=name,
        version="0.1.0",
        description="synthetic",
        author="test",
        license="Apache-2.0",
        horus_os_compat=">=0.5,<0.6",
        homepage=None,
        issue_tracker=None,
        tool_entries=(),
        adapter_entries=(),
        capabilities=(),  # zero caps → permission gate passes trivially.
        source="filesystem",
        source_detail=f"<synthetic:{name}>",
        manifest_hash="synth",
    )


@pytest.fixture
def lifecycle_data_dir(tmp_path: Path) -> Path:
    from horus_os.storage import Database

    data_dir = tmp_path / "horus_data"
    data_dir.mkdir()
    db = Database(data_dir / "horus.sqlite")
    db.init()
    return data_dir


def _patch_loader_to_inject(
    monkeypatch: pytest.MonkeyPatch,
    adapters: list[object],
) -> None:
    """Monkeypatch PluginLoader.load to return synthetic adapters.

    Each adapter becomes one synthetic spec; the loader's load() is
    replaced with a stub that pre-materializes the adapter and returns
    a PluginLoadResult(status='loaded', materialized_adapters=...).
    discover_plugins is also stubbed to yield the synthetic specs.
    """
    specs = [_make_synthetic_spec(getattr(a, "name", f"synth-{i}"))
             for i, a in enumerate(adapters)]
    by_name = {s.name: a for s, a in zip(specs, adapters, strict=True)}

    def _fake_discover() -> tuple[list[object], list[object]]:
        return list(specs), []

    def _fake_load(self: object, spec: object) -> PluginLoadResult:
        adapter = by_name[spec.name]
        return PluginLoadResult(
            status="loaded",
            error_phase=None,
            error=None,
            registered_tools=(),
            registered_adapters=(adapter.name,),
            materialized_adapters=((adapter.name, adapter),),
        )

    monkeypatch.setattr(
        "horus_os.server.api.discover_plugins", _fake_discover,
    )
    monkeypatch.setattr(
        "horus_os.plugins.loader.PluginLoader.load", _fake_load,
    )


# --- The actual tests ------------------------------------------------------


def test_start_timeout_marks_error(
    monkeypatch: pytest.MonkeyPatch,
    lifecycle_data_dir: Path,
) -> None:
    """5s sleep in start → wait_for(2.0) cuts it; error_phase='start'; wall < 3s."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from horus_os.server.api import create_app

    slow = _SlowStartAdapter()
    fast = _FastAdapter()
    _patch_loader_to_inject(monkeypatch, [slow, fast])

    app = create_app(data_dir=lifecycle_data_dir)
    t0 = time.perf_counter()
    with TestClient(app) as client:
        r = client.get("/api/health")
        assert r.status_code == 200
    elapsed = time.perf_counter() - t0

    # Wall clock budget: 2.0s timeout + harness overhead. 3.0s is the
    # contracted ceiling (Pitfall 6 / TEST-14 mirror in PITFALLS.md).
    assert elapsed < 3.0, f"lifespan blocked for {elapsed:.2f}s (budget 2.5)"

    registry = app.state.plugin_registry
    entry = registry.get(slow.name)
    assert entry is not None
    assert entry.status == PLUGIN_STATUS_ERROR
    assert entry.error_phase == "start"
    # The fast adapter still loaded — the SlowAdapter's failure did
    # not abort the loop (ISOLATE-01).
    fast_entry = registry.get(fast.name)
    assert fast_entry is not None
    assert fast_entry.status == PLUGIN_STATUS_LOADED


def test_start_raises_marks_error(
    monkeypatch: pytest.MonkeyPatch,
    lifecycle_data_dir: Path,
) -> None:
    """start() raises ValueError → status='error', error_phase='start'."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from horus_os.server.api import create_app

    raising = _RaisingStartAdapter()
    _patch_loader_to_inject(monkeypatch, [raising])

    app = create_app(data_dir=lifecycle_data_dir)
    with TestClient(app) as client:
        r = client.get("/api/health")
        assert r.status_code == 200

    entry = app.state.plugin_registry.get(raising.name)
    assert entry is not None
    assert entry.status == PLUGIN_STATUS_ERROR
    assert entry.error_phase == "start"
    assert "ValueError" in (entry.error_message or "")


def test_stop_timeout_marks_error(
    monkeypatch: pytest.MonkeyPatch,
    lifecycle_data_dir: Path,
) -> None:
    """5s sleep in stop → shutdown completes in <3s; error_phase='stop'."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from horus_os.server.api import create_app

    slow = _SlowStopAdapter()
    _patch_loader_to_inject(monkeypatch, [slow])

    app = create_app(data_dir=lifecycle_data_dir)
    t0 = time.perf_counter()
    with TestClient(app) as client:
        r = client.get("/api/health")
        assert r.status_code == 200
    # TestClient context exit triggers the lifespan shutdown.
    elapsed = time.perf_counter() - t0
    assert elapsed < 3.0, f"shutdown blocked for {elapsed:.2f}s (budget 3.0)"

    entry = app.state.plugin_registry.get(slow.name)
    assert entry is not None
    assert entry.error_phase == "stop"


def test_stop_raises_marks_error(
    monkeypatch: pytest.MonkeyPatch,
    lifecycle_data_dir: Path,
) -> None:
    """stop() raises → error_phase='stop'."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from horus_os.server.api import create_app

    raising = _RaisingStopAdapter()
    _patch_loader_to_inject(monkeypatch, [raising])

    app = create_app(data_dir=lifecycle_data_dir)
    with TestClient(app) as client:
        r = client.get("/api/health")
        assert r.status_code == 200

    entry = app.state.plugin_registry.get(raising.name)
    assert entry is not None
    assert entry.error_phase == "stop"


def test_well_behaved_adapter_runs(
    monkeypatch: pytest.MonkeyPatch,
    lifecycle_data_dir: Path,
) -> None:
    """A fast, well-behaved adapter keeps status='loaded' through the lifespan."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from horus_os.server.api import create_app

    fast = _FastAdapter()
    _patch_loader_to_inject(monkeypatch, [fast])

    app = create_app(data_dir=lifecycle_data_dir)
    with TestClient(app) as client:
        r = client.get("/api/health")
        assert r.status_code == 200

    entry = app.state.plugin_registry.get(fast.name)
    assert entry is not None
    assert entry.status == PLUGIN_STATUS_LOADED
