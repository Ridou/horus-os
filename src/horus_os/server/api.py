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

import json
import os
import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import asdict
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
    latency_p50_p95,
    parse_window,
    tool_reliability,
)
from horus_os.storage import Database, TraceRecord
from horus_os.tools import ToolRegistry, read_file_tool
from horus_os.types import AgentProfile, AgentResult, NoteWrite, ToolCallEvent, ToolResult

DEFAULT_MAX_ITERATIONS = 10


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

    @asynccontextmanager
    async def _lifespan(_app: Any) -> AsyncGenerator[None, None]:
        # Startup: call `start(context)` on each adapter that has one.
        # A failing start is captured into the registry; other adapters
        # still get their turn.
        for _a in _adapters:
            _start = getattr(_a, "start", None)
            if _start is None:
                continue
            try:
                await _start(_adapter_context)
            except Exception as exc:
                _registry.mark_error(_a.name, f"{type(exc).__name__}: {exc}")
        try:
            yield
        finally:
            # Shutdown: call `stop()` on each adapter that has one,
            # in reverse order. A failing stop bumps error_count but
            # never aborts shutdown.
            for _a in reversed(_adapters):
                _stop = getattr(_a, "stop", None)
                if _stop is None:
                    continue
                try:
                    await _stop()
                except Exception as exc:
                    _registry.mark_error(_a.name, f"{type(exc).__name__}: {exc}")

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
            base = _profile_to_dict(
                profile, last_activity_at=_last_activity_for(db, profile.name)
            )
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
