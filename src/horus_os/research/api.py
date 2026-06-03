"""FastAPI APIRouter for the Deep Research HTTP surface (RESEARCH-02 / RESEARCH-05).

This is the server half of the Phase 73 research engine. It exposes the
73-01 `ResearchOrchestrator` over five routes:

  POST /api/research                  -> plan a run; returns a plan + task_id and
                                         writes a 'pending' task row WITHOUT
                                         spending any tokens (plan-before-execute).
                                         confirm/start=true also schedules the run.
  POST /api/research/{id}/start       -> confirm the plan and schedule the run.
  GET  /api/research/{id}/progress    -> live phase / sources_found / iterations
                                         against the budget for an in-flight run.
  GET  /api/research/{id}/report       -> the rendered cited markdown once done.
  POST /api/research/{id}/cancel       -> cancel at the plan stage or mid-run.

Two guarantees back RESEARCH-02 and RESEARCH-05:

  * Plan-before-execute and cancelable: POST /api/research only plans; the run
    starts only on an explicit confirm/start, and a cancel at the plan stage or
    mid-run flips the task to 'cancelled' and halts further work (the running
    orchestrator polls a per-task cancel flag between delegation turns via a
    _CancelableBudget). A cancelled run still writes a trace row.
  * Audited note + inspectable trace: on completion the report is persisted via
    NotesStore.create_note under a server-generated research/<task_id>.md path,
    so the existing on_write -> record_note_write audit hook fires; the task
    row's trace_id equals the run's recorded trace so GET /api/traces/{id}
    resolves it and the task status is visible in GET /api/tasks.

Security (matches dashboard_api): the per-request Database + Config pattern is
reused, and the two mutating routes (POST start, POST cancel) reuse the
dashboard_api loopback guard so a non-local client cannot start or cancel a
costly run (T-73-04).
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Body, HTTPException, Request

from horus_os.config import Config
from horus_os.memory import NotesStore, build_vector_index
from horus_os.research.orchestrator import ResearchOrchestrator
from horus_os.server.integrations_write import _require_loopback
from horus_os.storage import Database, TaskRecord
from horus_os.types import NoteWrite

router = APIRouter()

# Characters of the question surfaced as the task title in /api/tasks.
_TITLE_CHARS = 120


def _config_for_request(request: Request) -> Config:
    """Resolve Config the same way dashboard_api / plugins_api do."""
    data_dir = getattr(request.app.state, "data_dir", None)
    if data_dir is not None:
        return Config.load(Path(data_dir).expanduser())
    return Config.load(None)


def _require_db(request: Request) -> Database:
    """Open a per-request Database, mirroring dashboard_api._require_db."""
    cfg = _config_for_request(request)
    if not cfg.db_path.exists():
        raise HTTPException(503, detail="database not initialized; run `horus-os init`")
    return Database(cfg.db_path)


def _progress_store(request: Request) -> dict[str, dict[str, Any]]:
    """Return the per-task progress dict held on app.state.

    create_app initializes app.state.research_progress; this falls back to a
    fresh dict so the router stays usable even in a test that builds the app
    without the wiring (defensive, never hit in production).
    """
    store = getattr(request.app.state, "research_progress", None)
    if store is None:
        store = {}
        request.app.state.research_progress = store
    return store


def _persist_write(db: Database, write: NoteWrite) -> None:
    """NotesStore on_write hook: record the audited note_writes row.

    Identical to server/api.py:_persist_write so a research report written via
    NotesStore.create_note lands in the same audit trail as every other note
    write (RESEARCH-05 reviewable note).
    """
    db.record_note_write(
        operation=write.operation,
        rel_path=write.rel_path,
        bytes_before=write.bytes_before,
        bytes_after=write.bytes_after,
        content=write.content,
    )


def _build_orchestrator(cfg: Config, db: Database) -> ResearchOrchestrator:
    """Construct a ResearchOrchestrator wired to the audited notes path.

    The NotesStore on_write callback is the audit hook; the master registry is
    the default builtin set (web search, notes, analyze_file). Built here so
    both the plan call and the background run share one construction path.
    """
    notes_store = NotesStore(
        cfg.notes_dir,
        on_write=lambda w: _persist_write(db, w),
        vector_index=build_vector_index(cfg),
    )
    # Local import to avoid importing the server module at package import time
    # (research.api is imported by server.api, so the reverse import must be
    # deferred to call time to break the cycle).
    from horus_os.server.api import _build_default_registry

    master_registry = _build_default_registry(cfg, notes_store)
    return ResearchOrchestrator(
        db,
        master_registry,
        notes_store=notes_store,
        cfg=cfg,
        provider=cfg.default_provider,
    )


def _plan_to_dict(plan: Any) -> dict[str, Any]:
    """Serialize a ResearchPlan into the JSON body shape the dashboard reads."""
    return {
        "question": plan.question,
        "subtopics": [{"title": s.title, "query": s.query} for s in plan.subtopics],
    }


def _run_research(
    *,
    data_dir: Path | None,
    task_id: str,
    trace_id: str,
    question: str,
    progress: dict[str, dict[str, Any]],
) -> None:
    """Execute one research run as a FastAPI background task.

    Opens its own Config + Database (the run outlives the request), updates the
    per-task progress record on app.state as it moves through phases, persists
    the finished report as an audited note (research/<task_id>.md), records the
    generating trace under the pre-generated trace_id, and flips the task to its
    terminal status. A SourceBudgetExceeded degrades to a graceful partial that
    still completes; a cancel observed between turns flips the run to cancelled.
    Any unexpected failure flips the task to 'error' but always leaves a row.
    """
    cfg = Config.load(data_dir)
    db = Database(cfg.db_path)
    state = progress.setdefault(task_id, {})
    state["phase"] = "searching"
    state["iteration_budget"] = cfg.research_max_iterations

    def _should_cancel() -> bool:
        return bool(progress.get(task_id, {}).get("cancel_requested"))

    orchestrator = _build_orchestrator(cfg, db)
    start = time.perf_counter()
    try:
        # The orchestrator pre-links the run to the trace_id already written on
        # the task row so /api/traces/{trace_id} resolves the generating trace.
        result = orchestrator.run(
            question,
            task_id=task_id,
            parent_trace_id=None,
            trace_id=trace_id,
            should_cancel=_should_cancel,
        )
    except Exception as exc:  # background task must not leak an exception
        latency_ms = int((time.perf_counter() - start) * 1000)
        from horus_os.types import AgentResult

        db.record_trace(
            question,
            AgentResult(text="", provider=cfg.default_provider, model=""),
            trace_id=trace_id,
            agent_profile_name="Research Coordinator",
            latency_ms=latency_ms,
            status="error",
            error_message=f"{type(exc).__name__}: {exc}",
        )
        state["phase"] = "error"
        db.update_task_status(task_id, "error")
        return

    state["sources_found"] = result.sources
    # The run has returned, so the iteration budget is fully accounted for; the
    # progress surface reports the full budget as iterations_used for a finished
    # run (the orchestrator does not surface its per-run budget after the fact).
    state["iterations_used"] = cfg.research_max_iterations
    # Phase label reflects the terminal outcome the progress surface shows.
    if result.cancelled:
        state["phase"] = "cancelled"
        db.update_task_status(task_id, "cancelled")
        return

    state["phase"] = "synthesizing"
    # RESEARCH-05 audited note: write the cited report under a server-generated
    # path so the on_write -> record_note_write hook fires. The task_id is the
    # only path component and is server-generated, so no client-controlled value
    # can steer the write outside the notes dir (T-73-05).
    orchestrator._notes.create_note(f"research/{task_id}.md", result.report)

    state["report"] = result.report
    state["phase"] = "done"
    db.update_task_status(task_id, "completed")


@router.post("/api/research")
def start_research(
    request: Request,
    background_tasks: BackgroundTasks,
    payload: dict = Body(...),  # noqa: B008
) -> dict[str, Any]:
    """Plan a research run and (optionally) schedule it.

    Validates the question, builds the orchestrator, and calls plan() WITHOUT
    running any search or fetch (RESEARCH-02 plan-before-execute). Writes a
    'pending' task row carrying a pre-generated trace_id, seeds the progress
    record, and returns the plan + task_id. When confirm/start is true the run
    is also scheduled (status flips to 'running'); otherwise the caller must
    POST /api/research/{id}/start to begin.

    Mutating route: reuses the dashboard loopback guard so a non-local client
    cannot kick off a costly run (T-73-04).
    """
    _require_loopback(request)
    question = (payload.get("question") or "").strip() if isinstance(payload, dict) else ""
    if not question:
        raise HTTPException(400, detail="question is required")

    cfg = _config_for_request(request)
    if not cfg.db_path.exists():
        raise HTTPException(503, detail="database not initialized; run `horus-os init`")
    db = Database(cfg.db_path)

    orchestrator = _build_orchestrator(cfg, db)
    plan = orchestrator.plan(question)

    task_id = uuid.uuid4().hex
    trace_id = uuid.uuid4().hex
    db.save_task(
        TaskRecord(
            task_id=task_id,
            title=question[:_TITLE_CHARS],
            description=question,
            status="pending",
            agent_profile_name="Research Coordinator",
            trace_id=trace_id,
            is_demo_seed=False,
            created_at="",
            updated_at="",
        )
    )

    store = _progress_store(request)
    store[task_id] = {
        "phase": "plan",
        "sources_found": 0,
        "iterations_used": 0,
        "iteration_budget": cfg.research_max_iterations,
        "cancel_requested": False,
        "trace_id": trace_id,
    }

    confirm = bool(payload.get("confirm") or payload.get("start"))
    if confirm:
        _schedule_run(request, background_tasks, db, task_id, trace_id, question)

    return {
        "task_id": task_id,
        "trace_id": trace_id,
        "status": "running" if confirm else "pending",
        "plan": _plan_to_dict(plan),
    }


@router.post("/api/research/{task_id}/start")
def confirm_research(
    task_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Confirm a planned run and schedule the background execution.

    404 when the task_id is unknown, 409 when it is not in 'pending' (a run is
    already underway or finished). Reuses the loopback guard (T-73-04).
    """
    _require_loopback(request)
    db = _require_db(request)
    tasks = {t.task_id: t for t in db.list_tasks(limit=500)}
    task = tasks.get(task_id)
    if task is None:
        raise HTTPException(404, detail=f"research task {task_id!r} not found")
    if task.status != "pending":
        raise HTTPException(409, detail=f"task {task_id!r} is already {task.status}")

    trace_id = task.trace_id or uuid.uuid4().hex
    _schedule_run(request, background_tasks, db, task_id, trace_id, task.description)
    return {"task_id": task_id, "status": "running"}


def _schedule_run(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Database,
    task_id: str,
    trace_id: str,
    question: str,
) -> None:
    """Flip the task to 'running' and enqueue the background research run."""
    db.update_task_status(task_id, "running")
    store = _progress_store(request)
    state = store.setdefault(task_id, {})
    state.setdefault("cancel_requested", False)
    state["phase"] = "searching"
    state["trace_id"] = trace_id
    data_dir = getattr(request.app.state, "data_dir", None)
    background_tasks.add_task(
        _run_research,
        data_dir=Path(data_dir).expanduser() if data_dir is not None else None,
        task_id=task_id,
        trace_id=trace_id,
        question=question,
        progress=store,
    )


@router.get("/api/research/{task_id}/progress")
def research_progress(task_id: str, request: Request) -> dict[str, Any]:
    """Return the live progress record for a run. 404 on unknown task_id.

    Surfaces the current phase (plan|searching|reading|synthesizing|done|
    cancelled|error), sources_found, iterations_used, and the iteration budget,
    so the dashboard can render a live progress panel (RESEARCH-02).
    """
    store = _progress_store(request)
    state = store.get(task_id)
    if state is None:
        raise HTTPException(404, detail=f"research task {task_id!r} not found")
    return {
        "task_id": task_id,
        "phase": state.get("phase", "plan"),
        "sources_found": state.get("sources_found", 0),
        "iterations_used": state.get("iterations_used", 0),
        "iteration_budget": state.get("iteration_budget", 0),
    }


@router.get("/api/research/{task_id}/report")
def research_report(task_id: str, request: Request) -> dict[str, Any]:
    """Return the rendered cited markdown once synthesis completes.

    404 when the task_id is unknown, 409 while the run is still in flight (the
    report does not exist yet), and 200 with the markdown once the task status
    is 'completed'. The report is read back from the audited note so the wire
    body matches exactly what landed in the notes folder.
    """
    db = _require_db(request)
    tasks = {t.task_id: t for t in db.list_tasks(limit=500)}
    task = tasks.get(task_id)
    if task is None:
        raise HTTPException(404, detail=f"research task {task_id!r} not found")
    if task.status != "completed":
        raise HTTPException(409, detail=f"report not ready; task is {task.status}")

    cfg = _config_for_request(request)
    notes_store = NotesStore(cfg.notes_dir)
    try:
        markdown = notes_store.read_note(f"research/{task_id}.md")
    except (FileNotFoundError, PermissionError, OSError) as exc:
        raise HTTPException(404, detail="report note not found") from exc
    return {"task_id": task_id, "trace_id": task.trace_id, "report": markdown}


@router.post("/api/research/{task_id}/cancel")
def cancel_research(task_id: str, request: Request) -> dict[str, Any]:
    """Cancel a run at the plan stage or mid-run.

    Sets the per-task cancel flag the in-flight run polls between delegation
    turns (so it halts before the next turn, T-73-06) and flips the task status
    to 'cancelled'. 404 on unknown task_id. Reuses the loopback guard so a
    non-local client cannot cancel a run (T-73-04).
    """
    _require_loopback(request)
    db = _require_db(request)
    store = _progress_store(request)
    state = store.get(task_id)
    if state is not None:
        state["cancel_requested"] = True
        state["phase"] = "cancelled"
    updated = db.update_task_status(task_id, "cancelled")
    if not updated and state is None:
        raise HTTPException(404, detail=f"research task {task_id!r} not found")
    return {"task_id": task_id, "status": "cancelled"}
