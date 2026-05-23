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

import os
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from horus_os import __version__
from horus_os.agent import SUPPORTED_PROVIDERS, run_agent_loop
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
from horus_os.types import AgentResult, NoteWrite, ToolResult

DEFAULT_MAX_ITERATIONS = 10


def create_app(data_dir: str | Path | None = None) -> Any:
    """Return a configured FastAPI instance backed by the given data_dir."""
    from fastapi import Body, FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse
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
