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
from collections.abc import AsyncGenerator
from dataclasses import asdict
from pathlib import Path
from typing import Any

from horus_os import __version__
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

    app = FastAPI(
        title="horus-os",
        version=__version__,
        docs_url="/api/docs",
        redoc_url=None,
    )
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
        return {
            "agents": [
                _profile_to_dict(p, last_activity_at=_last_activity_for(db, p.name))
                for p in profiles
            ]
        }

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
        start = time.perf_counter()
        try:
            result = run_agent_loop(
                prompt,
                registry=registry,
                provider=provider,
                model=model,
                max_iterations=max_iterations,
                on_tool_result=tool_log.append,
            )
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            trace_id = db.record_trace(
                prompt,
                AgentResult(text="", provider=provider, model=model),
                latency_ms=latency_ms,
                status="error",
                error_message=f"{type(exc).__name__}: {exc}",
            )
            raise HTTPException(
                500, detail={"error": f"{type(exc).__name__}: {exc}", "trace_id": trace_id}
            ) from exc

        latency_ms = int((time.perf_counter() - start) * 1000)
        trace_id = db.record_trace(prompt, result, latency_ms=latency_ms)
        return {
            "trace_id": trace_id,
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

        async def _event_stream() -> AsyncGenerator[bytes, None]:
            text_parts: list[str] = []
            start = time.perf_counter()
            try:
                async for chunk in run_agent_stream(
                    prompt,
                    provider=provider,
                    model=model,
                    system=system_prompt,
                ):
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
                trace_id = db.record_trace(
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
                )
                yield _sse(
                    {
                        "type": "error",
                        "message": f"{type(exc).__name__}: {exc}",
                        "trace_id": trace_id,
                    }
                )
                return
            latency_ms = int((time.perf_counter() - start) * 1000)
            trace_id = db.record_trace(
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
            )
            yield _sse({"type": "done", "trace_id": trace_id, "latency_ms": latency_ms})

        return StreamingResponse(_event_stream(), media_type="text/event-stream")

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
