"""FastAPI app factory and route handlers for the horus-os dashboard.

The full server depends on FastAPI and uvicorn. Install the optional
extra to use it:

    pip install 'horus-os[dashboard]'

The factory pattern lets tests construct an isolated app per case via
TestClient without touching the network. Each request opens its own
Database connection so the app is safe to serve from multiple worker
processes.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from horus_os import __version__
from horus_os._providers._stream_types import _StreamUsage
from horus_os.adapters.base import AdapterContext, AdapterRegistry, discover_adapters
from horus_os.agent import SUPPORTED_PROVIDERS, run_agent_loop, run_agent_stream
from horus_os.config import Config
from horus_os.memory import NotesStore
from horus_os.memory.tools import (
    append_note_tool,
    create_note_tool,
    list_notes_tool,
    read_note_tool,
    search_notes_tool,
)
from horus_os.observability import (
    CostAnnotator,
    PricingTable,
    SQLitePersister,
    get_observation_bus,
)
from horus_os.observability.bus import LLMCallEvent, RunEndEvent
from horus_os.observability.queries import (
    agent_totals,
    cost_by_agent,
    cost_by_model,
    latency_p50_p95,
    parse_window,
    tool_reliability,
)
from horus_os.plugins import (
    PLUGIN_STATUS_LOADED,
    CapabilityGuard,
    PermissionGate,
    PluginContext,
    PluginLoader,
    PluginRegistry,
    discover_plugins,
)
from horus_os.server.plugins_api import router as plugins_router
from horus_os.storage import Database, TraceRecord
from horus_os.tools import ToolRegistry, read_file_tool
from horus_os.types import AgentProfile, AgentResult, NoteWrite, ToolCallEvent, ToolResult

DEFAULT_MAX_ITERATIONS = 10

# ISOLATE-02: bounded plugin-lifecycle timeout. Mirrors the v0.4
# Phase 38 OtelAdapter precedent (FORCE_FLUSH_TIMEOUT_MS = 2000); a
# misbehaving plugin's start/stop is wrapped in
# ``asyncio.wait_for(..., timeout=PLUGIN_LIFECYCLE_TIMEOUT_S)`` so a
# hang or runaway loop cannot block FastAPI lifespan startup or
# shutdown beyond this budget.
PLUGIN_LIFECYCLE_TIMEOUT_S = 2.0


def create_app(data_dir: str | Path | None = None) -> Any:
    """Return a configured FastAPI instance backed by the given data_dir."""
    from fastapi import Body, FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, Response, StreamingResponse
    from fastapi.staticfiles import StaticFiles

    # Discover adapters before FastAPI instantiation so the lifespan
    # context manager can close over the resolved adapter list.
    _adapters = discover_adapters()
    _registry = AdapterRegistry()
    for _adapter in _adapters:
        _registry.register(_adapter.name)

    _resolved_data_dir = (
        Path(data_dir).expanduser() if data_dir is not None else Config.load(None).data_dir
    )
    # Phase 27 wiring: build one app-level ToolRegistry so tool-providing
    # adapters (Calendar today) can register tools at bind time. Exposed
    # on app.state.tool_registry below for future surfaces to read.
    _app_tool_registry = ToolRegistry()
    _adapter_context = AdapterContext(
        config=Config.load(Path(data_dir).expanduser() if data_dir is not None else None),
        data_dir=_resolved_data_dir,
        registry=_registry,
        tool_registry=_app_tool_registry,
    )

    # Phase 42/43 wiring: discover + validate + permission + load
    # third-party plugins into the master ToolRegistry / AdapterRegistry.
    # Each failure (DiscoveryError, validate failure, permission denial,
    # load failure) is routed to plugin_registry.mark_error and the
    # loop continues — broken plugins NEVER crash lifespan startup
    # (ISOLATE-01).
    #
    # Phase 43 additions:
    # 1. HORUS_OS_DISABLE_PLUGINS env var short-circuits the entire
    #    pipeline (ISOLATE-03 escape hatch). PluginRegistry stays empty.
    # 2. Per-spec PluginRegistry.is_enabled gate — disabled plugins
    #    skip clean (no validate / load / start).
    # 3. PermissionGate.resolve between register and load — missing
    #    grants flip status to error / error_phase='permission'.
    # 4. Lifespan loop below wraps plugin adapter start/stop in
    #    asyncio.wait_for(timeout=PLUGIN_LIFECYCLE_TIMEOUT_S).
    _plugins_disabled_globally = (
        os.environ.get("HORUS_OS_DISABLE_PLUGINS", "").lower() == "true"
    )
    _plugin_db: Database | None = None
    try:
        _plugin_db_path = Config.load(_resolved_data_dir).db_path
        if _plugin_db_path.exists():
            _plugin_db = Database(_plugin_db_path)
    except Exception:
        _plugin_db = None
    _plugin_registry = PluginRegistry(db=_plugin_db)
    _plugin_loader = PluginLoader(
        tool_registry=_app_tool_registry,
        adapter_registry=_registry,
    )
    # Materialized adapter instances by name — populated as plugins
    # load, consumed by the lifespan to call start/stop under the
    # bounded wait. Kept separate from AdapterRegistry (which stores
    # names only).
    _plugin_adapter_instances: dict[str, object] = {}

    if _plugins_disabled_globally:
        # ISOLATE-03: skip discovery entirely. The empty lists below
        # cause the per-spec / per-error loops to no-op.
        _plugin_specs, _plugin_discovery_errors = [], []
    else:
        try:
            _plugin_specs, _plugin_discovery_errors = discover_plugins()
        except Exception:
            # discover_plugins() is contracted to never raise out, but
            # the belt-and-suspenders catch here honors ISOLATE-01 if
            # the contract ever drifts.
            _plugin_specs, _plugin_discovery_errors = [], []
    for _err in _plugin_discovery_errors:
        try:
            _plugin_registry.register_discovery_error(
                _err.name,
                source=_err.source,
                source_detail=_err.source_detail,
                error_phase=_err.error_phase,
                error_message=_err.error_message,
            )
        except Exception:
            # A registry mutator must not crash startup.
            continue
    for _spec in _plugin_specs:
        try:
            _plugin_registry.register(_spec)
        except Exception as _exc:
            _plugin_registry.register_discovery_error(
                _spec.name,
                source=_spec.source,
                source_detail=_spec.source_detail,
                error_phase="validate",
                error_message=f"{type(_exc).__name__}: {_exc}",
            )
            continue

        # ISOLATE-03 per-plugin gate: disabled plugins skip clean.
        # The check runs AFTER register so the in-memory entry exists
        # and the disabled status surfaces in /api/plugins.
        if _plugin_db is not None and not _plugin_registry.is_enabled(_spec.name):
            _plugin_registry.mark_disabled(_spec.name)
            continue

        # Phase 43 permission gate: resolve the spec's requested caps
        # against persisted grants. Any cap that lands in `pending`
        # (not granted, manifest_hash mismatch, or revoked) blocks the
        # load and flips the entry to error_phase='permission'.
        if _plugin_db is not None:
            try:
                _gate = PermissionGate(_plugin_db)
                _granted, _pending = _gate.resolve(_spec)
            except Exception as _exc:
                # An unknown capability name (ValueError from
                # Capability(name)) or any other gate failure lands as
                # error_phase='permission' so the dashboard pill
                # surfaces the failure plainly. ISOLATE-01 keeps the
                # loop running.
                _plugin_registry.mark_error(
                    _spec.name, "permission",
                    f"{type(_exc).__name__}: {_exc}",
                )
                continue
            if _pending:
                _plugin_registry.mark_error(
                    _spec.name, "permission",
                    f"missing grants: {sorted(c.value for c in _pending)}",
                )
                continue
            # Inject the resolved-grant guard into the loader so the
            # tool-handler wrap site sees the real granted set.
            _guard = CapabilityGuard(
                _spec.name, granted_capabilities=_granted,
            )
            _plugin_loader._guards[_spec.name] = _guard

        try:
            _result = _plugin_loader.load(_spec)
        except Exception as _exc:
            # PluginLoader.load() must never raise; this catch is the
            # belt-and-suspenders ISOLATE-01 guard.
            _plugin_registry.mark_error(
                _spec.name, "load", f"{type(_exc).__name__}: {_exc}"
            )
            continue
        if _result.status == "loaded":
            _plugin_registry.mark_loaded(
                _spec.name,
                registered_tools=_result.registered_tools,
                registered_adapters=_result.registered_adapters,
            )
            # Phase 43: stash materialized adapter instances for the
            # bounded start/stop calls in the lifespan below.
            for _adapter_name, _adapter_obj in _result.materialized_adapters:
                _plugin_adapter_instances[_adapter_name] = _adapter_obj
        else:
            _plugin_registry.mark_error(
                _spec.name,
                _result.error_phase or "load",
                _result.error or "",
            )

    @asynccontextmanager
    async def _lifespan(_app: Any) -> AsyncGenerator[None, None]:
        # Startup: call `start(context)` on each first-party adapter.
        # A failing start is captured into the registry; other adapters
        # still get their turn. First-party adapters (discord, slack,
        # otel, ...) stay on the v0.3 unbounded-wait path — they are
        # trusted code shipped with the package.
        for _a in _adapters:
            _start = getattr(_a, "start", None)
            if _start is None:
                continue
            try:
                await _start(_adapter_context)
            except Exception as exc:
                _registry.mark_error(_a.name, f"{type(exc).__name__}: {exc}")

        # Phase 43 / ISOLATE-02: plugin-adapter starts under bounded
        # asyncio.wait_for(start, timeout=PLUGIN_LIFECYCLE_TIMEOUT_S).
        # A hang or runaway loop in a third-party plugin's start()
        # cannot block the lifespan beyond this budget; the failure
        # surfaces as status='error' / error_phase='start' on the
        # plugin entry. Lifespan continues to the next plugin /
        # request-serving phase regardless.
        for _entry in _plugin_registry.all():
            if _entry.status != PLUGIN_STATUS_LOADED:
                continue
            for _adapter_name in _entry.registered_adapters:
                _adapter_obj = _plugin_adapter_instances.get(_adapter_name)
                if _adapter_obj is None:
                    continue
                _start_fn = getattr(_adapter_obj, "start", None)
                if _start_fn is None:
                    continue
                _guard_for_ctx = _plugin_loader._guards.get(
                    _entry.name,
                    CapabilityGuard(_entry.name),
                )
                _plugin_ctx = PluginContext(
                    plugin_name=_entry.name,
                    plugin_version=_entry.spec.version if _entry.spec else "",
                    data_dir=_resolved_data_dir / "plugins" / _entry.name,
                    guard=_guard_for_ctx,
                )
                try:
                    await asyncio.wait_for(
                        _start_fn(_plugin_ctx),
                        timeout=PLUGIN_LIFECYCLE_TIMEOUT_S,
                    )
                except TimeoutError:
                    _plugin_registry.mark_error(
                        _entry.name, "start",
                        f"start() exceeded {PLUGIN_LIFECYCLE_TIMEOUT_S}s",
                    )
                except Exception as exc:
                    _plugin_registry.mark_error(
                        _entry.name, "start",
                        f"{type(exc).__name__}: {exc}",
                    )

        try:
            yield
        finally:
            # Shutdown: first-party adapters in reverse, unbounded.
            for _a in reversed(_adapters):
                _stop = getattr(_a, "stop", None)
                if _stop is None:
                    continue
                try:
                    await _stop()
                except Exception as exc:
                    _registry.mark_error(_a.name, f"{type(exc).__name__}: {exc}")

            # Phase 43: plugin-adapter stops under bounded wait,
            # reverse order. Symmetric to the start path above.
            for _entry in reversed(_plugin_registry.all()):
                if _entry.status != PLUGIN_STATUS_LOADED:
                    continue
                for _adapter_name in reversed(_entry.registered_adapters):
                    _adapter_obj = _plugin_adapter_instances.get(_adapter_name)
                    if _adapter_obj is None:
                        continue
                    _stop_fn = getattr(_adapter_obj, "stop", None)
                    if _stop_fn is None:
                        continue
                    try:
                        await asyncio.wait_for(
                            _stop_fn(),
                            timeout=PLUGIN_LIFECYCLE_TIMEOUT_S,
                        )
                    except TimeoutError:
                        _plugin_registry.mark_error(
                            _entry.name, "stop",
                            f"stop() exceeded {PLUGIN_LIFECYCLE_TIMEOUT_S}s",
                        )
                    except Exception as exc:
                        _plugin_registry.mark_error(
                            _entry.name, "stop",
                            f"{type(exc).__name__}: {exc}",
                        )

    app = FastAPI(
        title="horus-os",
        version=__version__,
        docs_url="/api/docs",
        redoc_url=None,
        lifespan=_lifespan,
    )
    app.state.adapter_registry = _registry
    app.state.tool_registry = _app_tool_registry
    app.state.adapters = list(_adapters)
    # Phase 45: the new plugins_api router resolves Config per-request
    # via Config.load(app.state.data_dir). Storing the resolved data_dir
    # here lets the router stay decoupled from the create_app closure
    # while still honoring the tmp_path-injected data_dir in tests.
    app.state.data_dir = _resolved_data_dir
    # Phase 42: plugin pipeline already ran above (before the lifespan
    # was constructed) so the registry is fully populated by the time
    # FastAPI starts serving. Exposed on app.state for the upcoming
    # /api/plugins route (Phase 45) and for tests that inspect
    # plugin_registry.error() / .enabled() to verify ISOLATE-01.
    app.state.plugin_registry = _plugin_registry
    # Phase 43: expose the materialized adapter instances + loader so
    # tests that need to inspect what got wired in past the registry
    # name-only surface have a handle. Production callers use the
    # registry; this is for diagnostics.
    app.state.plugin_adapter_instances = _plugin_adapter_instances
    app.state.plugin_loader = _plugin_loader
    # Phase 33 wiring: the ObservationBus is the central pub-sub for
    # LLMCallEvent / ToolCallEvent / RunEndEvent. Phase 34 CostAnnotator
    # subscribes here BEFORE the persister so the persister writes
    # mutated cost_usd / pricing_missing. Phase 38 will subscribe an
    # OtelExporter AFTER the persister. The persister holds a Database
    # that resolves its path lazily on each write, so it stays correct
    # even if the config file is rewritten between requests.
    _bus = get_observation_bus()
    _pricing_table = PricingTable(Config.load(_resolved_data_dir).pricing_path)
    _bus.subscribe(CostAnnotator(_pricing_table).on_event)
    _bus.subscribe(SQLitePersister(Database(Config.load(_resolved_data_dir).db_path)).on_event)
    app.state.observation_bus = _bus
    # Phase 36 wiring: expose the PricingTable on app.state so the
    # new /api/observability/pricing-status route reads from the same
    # instance the CostAnnotator subscriber uses. Guards against silent
    # dual-construction; pinned by tests/test_server_pricing_status.py.
    app.state.pricing_table = _pricing_table
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=False,
    )

    static_dir = Path(__file__).parent / "static"
    index_html = static_dir / "index.html"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/")
    def index() -> Any:
        return FileResponse(str(index_html))

    def _config() -> Config:
        return Config.load(Path(data_dir).expanduser() if data_dir is not None else None)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/api/traces")
    def list_traces(limit: int = 50, offset: int = 0) -> dict[str, Any]:
        cfg = _config()
        if not cfg.db_path.exists():
            raise HTTPException(503, detail="database not initialized; run `horus-os init`")
        db = Database(cfg.db_path)
        traces = db.list_traces(limit=max(1, limit), offset=max(0, offset))
        return {"traces": [_trace_to_dict(t) for t in traces]}

    @app.get("/api/traces/{trace_id}")
    def get_trace(trace_id: str) -> dict[str, Any]:
        cfg = _config()
        if not cfg.db_path.exists():
            raise HTTPException(503, detail="database not initialized; run `horus-os init`")
        db = Database(cfg.db_path)
        record = db.get_trace(trace_id)
        if record is None:
            raise HTTPException(404, detail=f"trace {trace_id!r} not found")
        return _trace_to_dict(record)

    @app.get("/api/traces/{trace_id}/children")
    def get_trace_children(trace_id: str) -> dict[str, Any]:
        cfg = _config()
        if not cfg.db_path.exists():
            raise HTTPException(503, detail="database not initialized; run `horus-os init`")
        db = Database(cfg.db_path)
        children = db.list_child_traces(trace_id)
        return {"children": [_trace_to_dict(c) for c in children]}

    @app.get("/api/agents")
    def agents_list() -> dict[str, Any]:
        cfg = _config()
        if not cfg.db_path.exists():
            raise HTTPException(503, detail="database not initialized; run `horus-os init`")
        db = Database(cfg.db_path)
        profiles = db.list_profiles()
        # Phase 35 DASH-4-04 extension: merge per-agent rollup over the 7d
        # default window. Agents with zero in-window runs get default
        # zero/null rollup fields so the existing v0.3 surface stays
        # byte-identical for any agent that already returned a row.
        rollups = {row["agent"]: row for row in agent_totals(db, "7d")}
        agents = []
        for profile in profiles:
            base = _profile_to_dict(profile, last_activity_at=_last_activity_for(db, profile.name))
            rollup = rollups.get(profile.name)
            if rollup is None:
                base.update(
                    {
                        "total_runs": 0,
                        "total_cost_usd": None,
                        "latency_p50_ms": None,
                        "latency_p95_ms": None,
                        "uncosted_runs": 0,
                    }
                )
            else:
                base.update(
                    {
                        "total_runs": rollup["total_runs"],
                        "total_cost_usd": rollup["total_cost_usd"],
                        "latency_p50_ms": rollup["latency_p50_ms"],
                        "latency_p95_ms": rollup["latency_p95_ms"],
                        "uncosted_runs": rollup["uncosted_runs"],
                    }
                )
            agents.append(base)
        return {"agents": agents}

    @app.get("/api/agents/{name}")
    def agents_show(name: str) -> dict[str, Any]:
        cfg = _config()
        if not cfg.db_path.exists():
            raise HTTPException(503, detail="database not initialized; run `horus-os init`")
        db = Database(cfg.db_path)
        profile = db.load_profile(name)
        if profile is None:
            raise HTTPException(404, detail=f"agent profile {name!r} not found")
        return _profile_to_dict(profile, last_activity_at=_last_activity_for(db, name))

    @app.post("/api/agents")
    def agents_create(payload: dict = Body(...)) -> dict[str, Any]:  # noqa: B008
        cfg = _config()
        if not cfg.db_path.exists():
            raise HTTPException(503, detail="database not initialized; run `horus-os init`")
        if not isinstance(payload, dict):
            raise HTTPException(400, detail="payload must be a JSON object")
        name = payload.get("name")
        system_prompt = payload.get("system_prompt")
        if not isinstance(name, str) or not name.strip():
            raise HTTPException(400, detail="name is required")
        if not isinstance(system_prompt, str):
            raise HTTPException(400, detail="system_prompt is required")
        db = Database(cfg.db_path)
        if db.load_profile(name) is not None:
            raise HTTPException(409, detail=f"agent profile {name!r} already exists")
        allowed = payload.get("allowed_tools")
        if allowed is not None and not isinstance(allowed, list):
            raise HTTPException(400, detail="allowed_tools must be a list or null")
        profile = AgentProfile(
            name=name,
            system_prompt=system_prompt,
            default_model=payload.get("default_model"),
            allowed_tools=list(allowed) if isinstance(allowed, list) else None,
            memory_scope=payload.get("memory_scope"),
        )
        db.save_profile(profile)
        saved = db.load_profile(name)
        assert saved is not None
        return _profile_to_dict(saved, last_activity_at=None)

    @app.patch("/api/agents/{name}")
    def agents_edit(name: str, payload: dict = Body(...)) -> dict[str, Any]:  # noqa: B008
        cfg = _config()
        if not cfg.db_path.exists():
            raise HTTPException(503, detail="database not initialized; run `horus-os init`")
        db = Database(cfg.db_path)
        profile = db.load_profile(name)
        if profile is None:
            raise HTTPException(404, detail=f"agent profile {name!r} not found")
        if not isinstance(payload, dict):
            raise HTTPException(400, detail="payload must be a JSON object")
        if "system_prompt" in payload:
            sp = payload["system_prompt"]
            if not isinstance(sp, str):
                raise HTTPException(400, detail="system_prompt must be a string")
            profile.system_prompt = sp
        if "default_model" in payload:
            profile.default_model = payload["default_model"]
        if "allowed_tools" in payload:
            at = payload["allowed_tools"]
            if at is not None and not isinstance(at, list):
                raise HTTPException(400, detail="allowed_tools must be a list or null")
            profile.allowed_tools = list(at) if isinstance(at, list) else None
        if "memory_scope" in payload:
            profile.memory_scope = payload["memory_scope"]
        db.save_profile(profile)
        saved = db.load_profile(name)
        assert saved is not None
        return _profile_to_dict(saved, last_activity_at=_last_activity_for(db, name))

    @app.delete("/api/agents/{name}", status_code=204, response_class=Response)
    def agents_delete(name: str):
        cfg = _config()
        if not cfg.db_path.exists():
            raise HTTPException(503, detail="database not initialized; run `horus-os init`")
        db = Database(cfg.db_path)
        deleted = db.delete_profile(name)
        if not deleted:
            raise HTTPException(404, detail=f"agent profile {name!r} not found")
        return Response(status_code=204)

    @app.get("/api/writes")
    def list_writes(limit: int = 50, offset: int = 0) -> dict[str, Any]:
        cfg = _config()
        if not cfg.db_path.exists():
            raise HTTPException(503, detail="database not initialized; run `horus-os init`")
        db = Database(cfg.db_path)
        writes = db.list_note_writes(limit=max(1, limit), offset=max(0, offset))
        return {"writes": [_write_to_dict(w) for w in writes]}

    @app.get("/api/observability/cost")
    def observability_cost(since: str = "7d") -> dict[str, Any]:
        cfg = _config()
        if not cfg.db_path.exists():
            raise HTTPException(503, detail="database not initialized; run `horus-os init`")
        try:
            rows = cost_by_agent(Database(cfg.db_path), since)
        except ValueError as exc:
            raise HTTPException(400, detail=str(exc)) from exc
        return {"agents": rows}

    @app.get("/api/observability/cost-by-model")
    def observability_cost_by_model(since: str = "7d") -> dict[str, Any]:
        cfg = _config()
        if not cfg.db_path.exists():
            raise HTTPException(503, detail="database not initialized; run `horus-os init`")
        try:
            rows = cost_by_model(Database(cfg.db_path), since)
        except ValueError as exc:
            raise HTTPException(400, detail=str(exc)) from exc
        return {"models": rows}

    @app.get("/api/observability/latency")
    def observability_latency(since: str = "7d") -> dict[str, Any]:
        cfg = _config()
        if not cfg.db_path.exists():
            raise HTTPException(503, detail="database not initialized; run `horus-os init`")
        try:
            return latency_p50_p95(Database(cfg.db_path), since)
        except ValueError as exc:
            raise HTTPException(400, detail=str(exc)) from exc

    @app.get("/api/observability/tools")
    def observability_tools(since: str = "7d") -> dict[str, Any]:
        cfg = _config()
        if not cfg.db_path.exists():
            raise HTTPException(503, detail="database not initialized; run `horus-os init`")
        try:
            rows = tool_reliability(Database(cfg.db_path), since)
        except ValueError as exc:
            raise HTTPException(400, detail=str(exc)) from exc
        return {"tools": rows}

    @app.get("/api/observability/llm-calls")
    def observability_llm_calls(since: str = "7d") -> dict[str, Any]:
        # Drilldown row-level route for the Phase 36 dashboard. Selects an
        # explicit column list that deliberately omits the text-content
        # error column on llm_calls; only error_type (exception class name)
        # flows to the wire so user-supplied content embedded in an
        # exception text never leaves the persister write path
        # (Pitfalls 7 + 9).
        cfg = _config()
        if not cfg.db_path.exists():
            raise HTTPException(503, detail="database not initialized; run `horus-os init`")
        try:
            threshold = parse_window(since)
        except ValueError as exc:
            raise HTTPException(400, detail=str(exc)) from exc
        db = Database(cfg.db_path)
        with db._connect() as conn:
            cursor = conn.execute(
                """
                SELECT call_id, trace_id, iteration_idx, created_at, provider, model,
                       input_tokens, output_tokens, cache_creation_input_tokens,
                       cache_read_input_tokens, cost_usd, pricing_missing,
                       latency_ms, status, error_type
                FROM llm_calls
                WHERE created_at >= ?
                ORDER BY created_at DESC
                LIMIT 100
                """,
                (threshold,),
            )
            calls = [dict(row) for row in cursor.fetchall()]
        return {"calls": calls}

    @app.get("/api/observability/pricing-status")
    def observability_pricing_status() -> dict[str, Any]:
        """Return staleness metadata for the active PricingTable.

        Phase 36 banner data source. Reads from app.state.pricing_table
        (same instance the CostAnnotator subscriber uses). Pitfall 5:
        the dashboard banner pulls updated_at_age_days from here and
        switches color at 30 days (yellow) and 90 days (red).
        """
        pt = app.state.pricing_table
        now = datetime.now(UTC)
        return {
            "updated_at": pt.updated_at.isoformat(),
            "updated_at_age_days": pt.updated_at_age_days(now),
            "is_stale": pt.is_stale(now, 30),
        }

    @app.post("/api/chat")
    async def chat(payload: dict = Body(...)) -> dict[str, Any]:  # noqa: B008
        prompt = (payload.get("prompt") or "").strip() if isinstance(payload, dict) else ""
        if not prompt:
            raise HTTPException(400, detail="prompt is required")
        cfg = _config()
        if not cfg.db_path.exists():
            raise HTTPException(503, detail="database not initialized; run `horus-os init`")
        provider = payload.get("provider") or cfg.default_provider
        if provider not in SUPPORTED_PROVIDERS:
            raise HTTPException(400, detail=f"unknown provider {provider!r}")
        if not _api_key_for(provider):
            env_var = "ANTHROPIC_API_KEY" if provider == "anthropic" else "GEMINI_API_KEY"
            raise HTTPException(503, detail=f"no API key for {provider}; set {env_var}")
        model = payload.get("model") or _model_for(cfg, provider)
        max_iterations = int(payload.get("max_iterations") or DEFAULT_MAX_ITERATIONS)

        db = Database(cfg.db_path)
        notes_store = NotesStore(cfg.notes_dir, on_write=lambda w: _persist_write(db, w))
        registry = _build_default_registry(cfg, notes_store)
        tool_log: list[ToolResult] = []
        # Phase 33: pre-generate the trace_id so the same id flows into
        # the LLMCallEvents published inside run_agent_loop, the traces
        # row record_trace writes, and the RunEndEvent that triggers the
        # rollup UPDATE.
        _trace_id = uuid.uuid4().hex
        start = time.perf_counter()
        try:
            result = run_agent_loop(
                prompt,
                registry=registry,
                provider=provider,
                model=model,
                max_iterations=max_iterations,
                on_tool_result=tool_log.append,
                trace_id=_trace_id,
            )
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            db.record_trace(
                prompt,
                AgentResult(text="", provider=provider, model=model),
                latency_ms=latency_ms,
                status="error",
                error_message=f"{type(exc).__name__}: {exc}",
                trace_id=_trace_id,
            )
            # RunEndEvent fires AFTER record_trace so the persister's
            # UPDATE matches the row we just inserted.
            get_observation_bus().publish(RunEndEvent(trace_id=_trace_id, latency_ms=latency_ms))
            raise HTTPException(
                500, detail={"error": f"{type(exc).__name__}: {exc}", "trace_id": _trace_id}
            ) from exc

        latency_ms = int((time.perf_counter() - start) * 1000)
        db.record_trace(prompt, result, latency_ms=latency_ms, trace_id=_trace_id)
        # RunEndEvent fires AFTER record_trace so the persister's UPDATE
        # matches the row we just inserted.
        get_observation_bus().publish(RunEndEvent(trace_id=_trace_id, latency_ms=latency_ms))
        return {
            "trace_id": _trace_id,
            "result": _agent_result_to_dict(result),
            "tool_log": [asdict(r) for r in tool_log],
            "latency_ms": latency_ms,
        }

    @app.post("/api/chat/stream")
    async def chat_stream(payload: dict = Body(...)) -> StreamingResponse:  # noqa: B008
        prompt = (payload.get("prompt") or "").strip() if isinstance(payload, dict) else ""
        if not prompt:
            raise HTTPException(400, detail="prompt is required")
        cfg = _config()
        if not cfg.db_path.exists():
            raise HTTPException(503, detail="database not initialized; run `horus-os init`")
        provider = payload.get("provider") or cfg.default_provider
        if provider not in SUPPORTED_PROVIDERS:
            raise HTTPException(400, detail=f"unknown provider {provider!r}")
        if not _api_key_for(provider):
            env_var = "ANTHROPIC_API_KEY" if provider == "anthropic" else "GEMINI_API_KEY"
            raise HTTPException(503, detail=f"no API key for {provider}; set {env_var}")
        db = Database(cfg.db_path)
        raw_agent = payload.get("agent")
        agent_name: str | None = None
        profile: AgentProfile | None = None
        if isinstance(raw_agent, str) and raw_agent:
            profile = db.load_profile(raw_agent)
            if profile is None:
                raise HTTPException(404, detail=f"agent profile {raw_agent!r} not found")
            agent_name = raw_agent
        model = (
            payload.get("model")
            or (profile.default_model if profile else None)
            or _model_for(cfg, provider)
        )
        system_prompt = profile.system_prompt if profile else None

        # Phase 33 SSE capture: pre-generate trace_id so LLMCallEvent +
        # RunEndEvent and the traces row all share the same id. Track
        # text_parts for the (Pitfall 2) char-count fallback when the
        # provider does not surface terminal usage.
        _trace_id = uuid.uuid4().hex
        _bus = get_observation_bus()

        async def _event_stream() -> AsyncGenerator[bytes, None]:
            text_parts: list[str] = []
            terminal_usage: dict[str, Any] = {}
            start = time.perf_counter()
            try:
                async for chunk in run_agent_stream(
                    prompt,
                    provider=provider,
                    model=model,
                    system=system_prompt,
                ):
                    if isinstance(chunk, _StreamUsage):
                        # private: consume, never forward to the wire.
                        terminal_usage = chunk.usage
                        continue
                    if isinstance(chunk, ToolCallEvent):
                        yield _sse(
                            {
                                "type": "tool_call",
                                "name": chunk.name,
                                "input": chunk.input,
                            }
                        )
                        continue
                    text_parts.append(chunk)
                    yield _sse({"type": "token", "text": chunk})
            except Exception as exc:
                latency_ms = int((time.perf_counter() - start) * 1000)
                # Pitfall 2: never persist 0 output_tokens for a
                # non-empty stream even on mid-flight error. Estimate
                # from text accumulated so far via the 4-char-per-token
                # heuristic. estimated=True flag is on the event status.
                est_in, est_out, est_cc, est_cr = _resolve_stream_usage(
                    provider, terminal_usage, text_parts
                )
                _bus.publish(
                    LLMCallEvent(
                        trace_id=_trace_id,
                        iteration_idx=0,
                        provider=provider,
                        model=model or "",
                        input_tokens=est_in,
                        output_tokens=est_out,
                        cache_creation_input_tokens=est_cc,
                        cache_read_input_tokens=est_cr,
                        latency_ms=max(0, latency_ms),
                        status="error",
                        error_type=type(exc).__name__,
                        error_message=type(exc).__name__,
                    )
                )
                db.record_trace(
                    prompt,
                    AgentResult(
                        text="".join(text_parts),
                        tool_uses=[],
                        provider=provider,
                        model=model,
                        usage={},
                    ),
                    latency_ms=latency_ms,
                    status="error",
                    error_message=f"{type(exc).__name__}: {exc}",
                    agent_profile_name=agent_name,
                    trace_id=_trace_id,
                )
                _bus.publish(RunEndEvent(trace_id=_trace_id, latency_ms=latency_ms))
                yield _sse(
                    {
                        "type": "error",
                        "message": f"{type(exc).__name__}: {exc}",
                        "trace_id": _trace_id,
                    }
                )
                return
            latency_ms = int((time.perf_counter() - start) * 1000)
            # Success path: extract terminal usage with provider-specific
            # key normalization. When usage is empty (provider did not
            # surface it) and the stream produced text, fall back to a
            # char-count estimate. NEVER persist 0 tokens for a
            # non-empty stream (Pitfall 2).
            est_in, est_out, est_cc, est_cr = _resolve_stream_usage(
                provider, terminal_usage, text_parts
            )
            _bus.publish(
                LLMCallEvent(
                    trace_id=_trace_id,
                    iteration_idx=0,
                    provider=provider,
                    model=model or "",
                    input_tokens=est_in,
                    output_tokens=est_out,
                    cache_creation_input_tokens=est_cc,
                    cache_read_input_tokens=est_cr,
                    latency_ms=max(0, latency_ms),
                    status="success",
                )
            )
            db.record_trace(
                prompt,
                AgentResult(
                    text="".join(text_parts),
                    tool_uses=[],
                    provider=provider,
                    model=model,
                    usage={},
                ),
                latency_ms=latency_ms,
                agent_profile_name=agent_name,
                trace_id=_trace_id,
            )
            _bus.publish(RunEndEvent(trace_id=_trace_id, latency_ms=latency_ms))
            yield _sse({"type": "done", "trace_id": _trace_id, "latency_ms": latency_ms})

        return StreamingResponse(_event_stream(), media_type="text/event-stream")

    @app.get("/api/adapters")
    def list_adapters() -> dict[str, Any]:
        """Return the per-adapter status snapshot from the registry.

        Phase 27 addition: each entry carries a `supports_toggle` field
        so the dashboard can disable the toggle button for adapters
        without `start`/`stop` hooks.
        """
        by_name = {a.name: a for a in _adapters}
        out: list[dict[str, Any]] = []
        for entry in _registry.entries():
            adapter = by_name.get(entry.name)
            supports_toggle = (
                adapter is not None and hasattr(adapter, "start") and hasattr(adapter, "stop")
            )
            out.append(
                {
                    "name": entry.name,
                    "status": entry.status,
                    "last_activity_at": entry.last_activity_at,
                    "error_count": entry.error_count,
                    "error_message": entry.error_message,
                    "supports_toggle": supports_toggle,
                }
            )
        return {"adapters": out}

    @app.post("/api/adapters/{name}/disable")
    async def disable_adapter(name: str) -> dict[str, Any]:
        """Call the adapter's stop hook and flip status to stopped.

        Returns 404 if the adapter is not discovered, 400 if the
        adapter has no stop hook, 500 if the hook raises (the
        registry entry is marked error in that case so the next
        dashboard poll surfaces the failure).
        """
        by_name = {a.name: a for a in _adapters}
        adapter = by_name.get(name)
        if adapter is None:
            raise HTTPException(404, detail=f"adapter {name!r} not found")
        stop = getattr(adapter, "stop", None)
        if stop is None:
            raise HTTPException(
                400,
                detail=f"adapter {name!r} does not support disable; it has no stop() hook",
            )
        try:
            await stop()
        except Exception as exc:
            _registry.mark_error(name, f"{type(exc).__name__}: {exc}")
            raise HTTPException(
                500, detail=f"stop hook raised: {type(exc).__name__}: {exc}"
            ) from exc
        _registry.mark_stopped(name)
        entry = _registry.get(name)
        return {"name": name, "status": entry.status if entry is not None else "stopped"}

    @app.post("/api/adapters/{name}/enable")
    async def enable_adapter(name: str) -> dict[str, Any]:
        """Call the adapter's start hook and flip status to running.

        Same error semantics as disable: 404 unknown, 400 missing
        hook, 500 with registry error capture on hook raise.
        """
        by_name = {a.name: a for a in _adapters}
        adapter = by_name.get(name)
        if adapter is None:
            raise HTTPException(404, detail=f"adapter {name!r} not found")
        start = getattr(adapter, "start", None)
        if start is None:
            raise HTTPException(
                400,
                detail=f"adapter {name!r} does not support enable; it has no start() hook",
            )
        try:
            await start(_adapter_context)
        except Exception as exc:
            _registry.mark_error(name, f"{type(exc).__name__}: {exc}")
            raise HTTPException(
                500, detail=f"start hook raised: {type(exc).__name__}: {exc}"
            ) from exc
        _registry.mark_running(name)
        entry = _registry.get(name)
        return {"name": name, "status": entry.status if entry is not None else "running"}

    # Bind each discovered adapter. Discovery already happened above
    # so the lifespan can close over the adapter list; here we just
    # mount routes and flip registry status. A bind failure is
    # captured into the registry but does not break the core
    # dashboard.
    for _adapter in _adapters:
        try:
            _adapter.bind(app, _adapter_context)
        except Exception as exc:
            _registry.mark_error(_adapter.name, f"{type(exc).__name__}: {exc}")
            continue
        _registry.mark_running(_adapter.name)

    # Phase 45: mount the /api/plugins/* + /api/observability/plugins
    # router. Lives in a dedicated module so api.py stays under 1200
    # lines. Mounted AFTER the adapter bind loop so it shares the same
    # boot-order contract -- all routes are wired before the first
    # request can hit them.
    app.include_router(plugins_router)

    return app


def _api_key_for(provider: str) -> str | None:
    if provider == "anthropic":
        return os.environ.get("ANTHROPIC_API_KEY")
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def _model_for(cfg: Config, provider: str) -> str:
    if provider == "anthropic":
        return cfg.anthropic_model
    return cfg.gemini_model


def _build_default_registry(cfg: Config, notes_store: NotesStore) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(read_file_tool(base_dir=cfg.notes_dir))
    registry.register(list_notes_tool(notes_store))
    registry.register(search_notes_tool(notes_store))
    registry.register(read_note_tool(notes_store))
    registry.register(create_note_tool(notes_store))
    registry.register(append_note_tool(notes_store))
    return registry


def _persist_write(db: Database, write: NoteWrite) -> None:
    db.record_note_write(
        operation=write.operation,
        rel_path=write.rel_path,
        bytes_before=write.bytes_before,
        bytes_after=write.bytes_after,
        content=write.content,
    )


def _trace_to_dict(record: TraceRecord) -> dict[str, Any]:
    data = asdict(record)
    data["tool_uses"] = [asdict(use) for use in record.tool_uses]
    return data


def _write_to_dict(write: NoteWrite) -> dict[str, Any]:
    return asdict(write)


def _agent_result_to_dict(result: AgentResult) -> dict[str, Any]:
    data = asdict(result)
    data["tool_uses"] = [asdict(use) for use in result.tool_uses]
    return data


def _profile_to_dict(profile: AgentProfile, *, last_activity_at: str | None) -> dict[str, Any]:
    return {
        "name": profile.name,
        "system_prompt": profile.system_prompt,
        "default_model": profile.default_model,
        "allowed_tools": (
            list(profile.allowed_tools) if profile.allowed_tools is not None else None
        ),
        "memory_scope": profile.memory_scope,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
        "last_activity_at": last_activity_at,
    }


def _last_activity_for(db: Database, name: str) -> str | None:
    with db._connect() as conn:
        row = conn.execute(
            "SELECT MAX(created_at) AS ts FROM traces WHERE agent_profile_name = ?",
            (name,),
        ).fetchone()
        if row is None:
            return None
        return row["ts"]


def _sse(payload: dict[str, Any]) -> bytes:
    """Encode one SSE frame as bytes."""
    return f"data: {json.dumps(payload)}\n\n".encode()


def _resolve_stream_usage(
    provider: str,
    terminal_usage: dict[str, Any],
    text_parts: list[str],
) -> tuple[int, int, int, int]:
    """Normalize provider usage into LLMCallEvent token fields with fallback.

    Returns (input_tokens, output_tokens, cache_creation_input_tokens,
    cache_read_input_tokens).

    When the provider surfaced terminal usage, returns the canonical
    values. When the dict is empty AND the stream produced text, falls
    back to a char-count estimate via the 4-char-per-token heuristic
    (PITFALLS.md Pitfall 2 line 55) so non-empty streams never persist
    output_tokens=0. When the dict is empty AND no text was produced
    (a degenerate or aborted stream), returns all zeros.
    """
    if terminal_usage:
        if provider == "gemini":
            return (
                int(terminal_usage.get("prompt_token_count", 0) or 0),
                int(terminal_usage.get("candidates_token_count", 0) or 0),
                0,
                0,
            )
        return (
            int(terminal_usage.get("input_tokens", 0) or 0),
            int(terminal_usage.get("output_tokens", 0) or 0),
            int(terminal_usage.get("cache_creation_input_tokens", 0) or 0),
            int(terminal_usage.get("cache_read_input_tokens", 0) or 0),
        )
    accumulated = "".join(text_parts)
    if accumulated:
        # Pitfall 2: never persist 0 output_tokens for a non-empty
        # stream; estimate via 4-char-per-token heuristic per
        # PITFALLS.md line 55.
        est_out = max(1, len(accumulated) // 4)
        return (0, est_out, 0, 0)
    return (0, 0, 0, 0)
