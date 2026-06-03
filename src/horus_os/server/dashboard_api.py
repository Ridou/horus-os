"""FastAPI APIRouter for the read-only v0.7 dashboard JSON surface.

Seven routes back the new dashboard. Every response shape mirrors
``frontend/lib/types.ts`` exactly; the Pydantic models in
``server.schemas`` pin the contract so a typo in a handler fails at
serialization time instead of shipping a body the dashboard cannot
parse.

  GET /api/team                 -> TeamResponse
  GET /api/team/{name}          -> AgentDetailResponse (404 on unknown name)
  GET /api/memory?q=            -> MemoryResponse
  GET /api/memory/note?path=    -> MemoryNoteDetail (404 on missing, 400 on escape)
  GET /api/activity?limit=      -> ActivityResponse
  GET /api/health               -> HealthResponse (always 200; degrades gracefully)
  GET /api/settings             -> SettingsResponse (no secrets, ever)

Per-request DB pattern: each handler resolves ``Config`` via
``app.state.data_dir`` (the same wiring ``plugins_api`` uses) and opens
a fresh ``Database`` / ``NotesStore`` per request. This mirrors the
liveness contract the existing ``api.py`` handlers follow.

Security note for ``/api/settings``: the response carries only the
user's own local filesystem paths and the configured model ids. It
NEVER carries API keys, environment secrets, or any other sensitive
value. The ``SettingsResponse`` model uses ``extra='forbid'`` so a
handler cannot accidentally widen the body with a secret-bearing field.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from horus_os import __version__
from horus_os.config import Config
from horus_os.memory.notes import NotesStore, _extract_title
from horus_os.seed import vault_notes
from horus_os.server.integrations import INTEGRATION_REGISTRY, compute_status
from horus_os.server.integrations_write import _require_loopback
from horus_os.server.schemas import (
    ActivityEvent,
    ActivityResponse,
    AgentDetail,
    AgentDetailResponse,
    HealthResponse,
    IntegrationsResponse,
    IntegrationStatus,
    MemoryNote,
    MemoryNoteDetail,
    MemoryResponse,
    SettingsCounts,
    SettingsResponse,
    TaskRow,
    TasksResponse,
    TeamAgent,
    TeamResponse,
    TraceSummary,
    VercelStatusResponse,
)
from horus_os.storage import SCHEMA_VERSION, Database
from horus_os.types import AgentProfile

# Filenames of seed vault notes (top-level .md files from horus_os.seed.vault_notes).
# Used to compute ``is_example`` for GET /api/memory/note.
_SEED_VAULT_FILENAMES: frozenset[str] = frozenset(name for name, _ in vault_notes())

# Allowed values for the tasks status query param. Mirrors the CHECK constraint
# on tasks.status in the schema. An invalid value returns HTTP 400.
_VALID_TASK_STATUSES: frozenset[str] = frozenset(
    {"pending", "running", "completed", "error", "cancelled"}
)

router = APIRouter()

# How recently an agent must have run to count as "active" rather than
# "idle". Kept deliberately simple: a single 24h window, evaluated
# against the agent's most recent trace timestamp.
ACTIVE_WINDOW_HOURS = 24

# Default and ceiling for the /api/activity feed. The ceiling bounds the
# query so a hostile ?limit= cannot pull the whole table.
DEFAULT_ACTIVITY_LIMIT = 50
MAX_ACTIVITY_LIMIT = 200

# Recent traces returned on an agent detail.
AGENT_DETAIL_TRACE_LIMIT = 10

# Characters of a prompt surfaced as an activity summary.
ACTIVITY_SUMMARY_CHARS = 120


def _config_for_request(request: Request) -> Config:
    """Resolve Config the same way ``plugins_api`` does.

    ``create_app`` stores the resolved data_dir on ``app.state.data_dir``;
    fall back to ``Config.load(None)`` for the default-paths case.
    """
    data_dir = getattr(request.app.state, "data_dir", None)
    if data_dir is not None:
        return Config.load(Path(data_dir).expanduser())
    return Config.load(None)


def _parse_iso(value: str | None) -> datetime | None:
    """Parse a stored ISO 8601 UTC timestamp (``...Z``) into a datetime."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _agent_status(last_active_at: str | None, *, now: datetime) -> str:
    """Derive a simple status: 'active' if a trace ran in the last 24h, else 'idle'."""
    parsed = _parse_iso(last_active_at)
    if parsed is None:
        return "idle"
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    if now - parsed <= timedelta(hours=ACTIVE_WINDOW_HOURS):
        return "active"
    return "idle"


def _team_agent(
    profile: AgentProfile,
    activity: dict[str, tuple[int, str | None]],
    *,
    now: datetime,
) -> TeamAgent:
    """Map an AgentProfile + activity rollup into a TeamAgent."""
    trace_count, last_active_at = activity.get(profile.name, (0, None))
    return TeamAgent(
        name=profile.name,
        color=profile.color or "",
        description=profile.description or "",
        default_model=profile.default_model,
        soul_path=profile.soul_path or "",
        status=_agent_status(last_active_at, now=now),
        trace_count=trace_count,
        last_active_at=last_active_at,
    )


def _require_db(request: Request) -> Database:
    cfg = _config_for_request(request)
    if not cfg.db_path.exists():
        raise HTTPException(503, detail="database not initialized; run `horus-os init`")
    return Database(cfg.db_path)


@router.get("/api/team", response_model=TeamResponse)
def get_team(request: Request) -> TeamResponse:
    """Return every agent profile with its derived trace activity."""
    db = _require_db(request)
    now = datetime.now(UTC)
    activity = db.agent_activity()
    agents = [_team_agent(profile, activity, now=now) for profile in db.list_profiles()]
    return TeamResponse(agents=tuple(agents))


@router.get("/api/team/{name}", response_model=AgentDetailResponse)
def get_team_member(name: str, request: Request) -> AgentDetailResponse:
    """Return one agent's full detail, persona markdown, and recent traces.

    404 when no profile by ``name`` exists. ``soul_markdown`` is the
    contents of ``notes_dir / soul_path`` when that file resolves safely
    under notes_dir and exists, else null.
    """
    cfg = _config_for_request(request)
    db = _require_db(request)
    profile = db.load_profile(name) or db.load_profile_icase(name)
    if profile is None:
        raise HTTPException(404, detail=f"agent {name!r} not found")

    now = datetime.now(UTC)
    activity = db.agent_activity()
    base = _team_agent(profile, activity, now=now)
    detail = AgentDetail(**base.model_dump(), system_prompt=profile.system_prompt)

    soul_markdown = _read_soul(cfg.notes_dir, profile.soul_path)

    recent_traces = tuple(
        TraceSummary(
            trace_id=t.trace_id,
            created_at=t.created_at,
            prompt=t.prompt,
            status=t.status,
        )
        for t in db.list_traces_for_agent(profile.name, limit=AGENT_DETAIL_TRACE_LIMIT)
    )

    return AgentDetailResponse(
        agent=detail,
        soul_markdown=soul_markdown,
        recent_traces=recent_traces,
    )


def _read_soul(notes_dir: Path, soul_path: str | None) -> str | None:
    """Read a persona file under notes_dir, guarding against path escapes.

    Returns the file contents, or null when ``soul_path`` is unset, the
    path escapes notes_dir, or the file does not exist. Path safety reuses
    the same NotesStore ``_resolve`` guard the memory routes rely on.
    """
    if not soul_path:
        return None
    store = NotesStore(notes_dir)
    try:
        return store.read_note(soul_path)
    except (FileNotFoundError, PermissionError, OSError):
        return None


@router.get("/api/memory", response_model=MemoryResponse)
def get_memory(request: Request, q: str = Query(default="")) -> MemoryResponse:
    """List all notes, or search them when ``q`` is non-empty."""
    cfg = _config_for_request(request)
    store = NotesStore(cfg.notes_dir)
    refs = store.search_notes(q) if q.strip() else store.list_notes()
    notes = tuple(
        MemoryNote(
            path=ref.path,
            title=ref.title,
            size_bytes=ref.size_bytes,
            modified_at=ref.modified_at,
            preview=ref.preview,
        )
        for ref in refs
    )
    return MemoryResponse(notes=notes)


@router.get("/api/memory/note", response_model=MemoryNoteDetail)
def get_memory_note(request: Request, path: str = Query(...)) -> MemoryNoteDetail:
    """Return one note's full markdown. 404 on missing, 400 on path escape."""
    cfg = _config_for_request(request)
    store = NotesStore(cfg.notes_dir)
    try:
        resolved = store._resolve(path)
    except PermissionError as exc:
        raise HTTPException(400, detail="path resolves outside the notes directory") from exc
    if not resolved.is_file():
        raise HTTPException(404, detail=f"note {path!r} not found")

    markdown = resolved.read_text(errors="replace")
    stat = resolved.stat()
    modified_at = datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat().replace("+00:00", "Z")
    # A note is example content when it is a seeded top-level vault note or an
    # agents/*/SOUL.md file written by _seed_starter_content on first init.
    note_path = Path(path)
    is_example = note_path.name in _SEED_VAULT_FILENAMES or (
        len(note_path.parts) == 3 and note_path.parts[0] == "agents" and note_path.name == "SOUL.md"
    )
    return MemoryNoteDetail(
        path=path,
        title=_extract_title(markdown, fallback=resolved.stem),
        markdown=markdown,
        modified_at=modified_at,
        is_example=is_example,
    )


@router.get("/api/activity", response_model=ActivityResponse)
def get_activity(
    request: Request,
    limit: int = Query(default=DEFAULT_ACTIVITY_LIMIT),
) -> ActivityResponse:
    """Return the most recent traces as activity-feed events, newest first."""
    db = _require_db(request)
    bounded = max(1, min(limit, MAX_ACTIVITY_LIMIT))
    traces = db.list_traces(limit=bounded)
    events = tuple(
        ActivityEvent(
            trace_id=t.trace_id,
            created_at=t.created_at,
            agent=t.agent_profile_name or "default",
            kind="agent_run",
            summary=t.prompt[:ACTIVITY_SUMMARY_CHARS],
            status=t.status,
        )
        for t in traces
    )
    return ActivityResponse(events=events)


@router.get("/api/tasks", response_model=TasksResponse)
def get_tasks(
    request: Request,
    status: str = Query(default=""),
) -> TasksResponse:
    """Return all tasks, optionally filtered by status.

    The ``status`` query parameter is validated against the allowed set
    (pending, running, completed, error, cancelled). An invalid value
    returns HTTP 400. Omitting ``status`` (or passing an empty string)
    returns all tasks.
    """
    status_filter = status or None
    if status_filter is not None and status_filter not in _VALID_TASK_STATUSES:
        raise HTTPException(400, detail=f"invalid status {status_filter!r}")
    db = _require_db(request)
    tasks = db.list_tasks(status=status_filter)
    return TasksResponse(
        tasks=tuple(
            TaskRow(
                task_id=t.task_id,
                title=t.title,
                description=t.description,
                status=t.status,
                agent_profile_name=t.agent_profile_name,
                created_at=t.created_at,
                updated_at=t.updated_at,
            )
            for t in tasks
        )
    )


@router.delete("/api/tasks/{task_id}", status_code=204, response_class=Response)
def delete_task(task_id: str, request: Request) -> Response:
    """Cancel/delete one task by task_id. 404 when not found.

    Loopback guard mirrors the credential write endpoints: only local
    clients may mutate task rows.
    """
    _require_loopback(request)
    db = _require_db(request)
    deleted = db.delete_task(task_id)
    if not deleted:
        raise HTTPException(404, detail=f"task {task_id!r} not found")
    return Response(status_code=204)


@router.delete("/api/traces/{trace_id}", status_code=204, response_class=Response)
def delete_trace(trace_id: str, request: Request) -> Response:
    """Delete one trace by trace_id. Used to clear the demo trace. 404 when not found.

    Loopback guard mirrors the credential write endpoints: only local
    clients may delete trace rows.
    """
    _require_loopback(request)
    db = _require_db(request)
    deleted = db.delete_trace(trace_id)
    if not deleted:
        raise HTTPException(404, detail=f"trace {trace_id!r} not found")
    return Response(status_code=204)


@router.get("/api/health", response_model=HealthResponse)
def get_health(request: Request) -> HealthResponse:
    """Return server health and live counts. Always 200; degrades gracefully.

    When the database file does not yet exist, ``db_size_bytes`` and every
    count fall back to 0 so the endpoint stays a cheap liveness probe.
    """
    cfg = _config_for_request(request)
    store = NotesStore(cfg.notes_dir)
    note_count = len(store.list_notes())

    db_size_bytes = 0
    trace_count = 0
    agent_count = 0
    if cfg.db_path.exists():
        db_size_bytes = cfg.db_path.stat().st_size
        db = Database(cfg.db_path)
        trace_count = db.count_traces()
        agent_count = len(db.list_profiles())

    return HealthResponse(
        status="ok",
        version=__version__,
        db_size_bytes=db_size_bytes,
        trace_count=trace_count,
        note_count=note_count,
        agent_count=agent_count,
    )


@router.get("/api/settings", response_model=SettingsResponse)
def get_settings(request: Request) -> SettingsResponse:
    """Return read-only, non-sensitive configuration and live counts.

    NEVER returns API keys or any environment secret. Only the user's own
    local paths and the configured model ids are surfaced.
    """
    cfg = _config_for_request(request)
    store = NotesStore(cfg.notes_dir)
    note_count = len(store.list_notes())

    trace_count = 0
    agent_count = 0
    if cfg.db_path.exists():
        db = Database(cfg.db_path)
        trace_count = db.count_traces()
        agent_count = len(db.list_profiles())

    return SettingsResponse(
        data_dir=cfg.data_dir.as_posix(),
        notes_dir=cfg.notes_dir.as_posix(),
        db_path=cfg.db_path.as_posix(),
        default_provider=cfg.default_provider,
        anthropic_model=cfg.anthropic_model,
        gemini_model=cfg.gemini_model,
        schema_version=SCHEMA_VERSION,
        version=__version__,
        counts=SettingsCounts(
            agents=agent_count,
            notes=note_count,
            traces=trace_count,
        ),
    )


@router.get("/api/integrations", response_model=IntegrationsResponse)
def get_integrations(request: Request) -> IntegrationsResponse:
    """Return integration metadata and live configured status. Never returns secret values."""
    demo_mode = os.environ.get("HORUS_OS_DEMO", "") == "1"
    cfg = _config_for_request(request)
    db = Database(cfg.db_path) if cfg.db_path.exists() else None
    integrations = tuple(
        IntegrationStatus(
            id=entry["id"],
            name=entry["name"],
            category=entry["category"],
            description=entry["description"],
            status=compute_status(entry, db=db),
            env_var=entry["env_var"],
            required_vars=tuple(entry.get("required_vars", [entry["env_var"]])),
            credential_portal_url=entry["credential_portal_url"],
        )
        for entry in INTEGRATION_REGISTRY
    )
    return IntegrationsResponse(integrations=integrations, demo_mode=demo_mode)


# Vercel REST API version pinned to v6 (long-stable). Plan 04's DEPLOY-VERCEL.md
# documents the same version. v6/deployments?limit=1 returns the most recent
# deployment; an optional projectId narrows it to a single project.
_VERCEL_API_URL = "https://api.vercel.com/v6/deployments?limit=1"
_VERCEL_HTTP_TIMEOUT = 10


@router.get("/api/integrations/vercel/status", response_model=VercelStatusResponse)
def get_vercel_status(request: Request) -> VercelStatusResponse:
    """Return the latest Vercel deploy status read via the server-side token.

    Reads HORUS_OS_VERCEL_TOKEN (the canonical registry name, D-06) from the
    process environment and calls the Vercel REST deployments API, returning
    only the derived state/url/created_at. This is a READ endpoint that emits
    no secret, so it intentionally omits ``_require_loopback`` (matching
    ``get_integrations``).

    Token isolation (D-05): the token NEVER appears in the response. When the
    token is absent the endpoint degrades gracefully to ``configured=false``
    with no traceback (D-06, D-12). On any exception only the exception class
    NAME is surfaced via ``type(exc).__name__`` - never ``str(exc)``, which
    could echo the Authorization header (Pitfall 4, the 62-02 precedent).
    """
    token = os.environ.get("HORUS_OS_VERCEL_TOKEN")
    if not token:
        # Graceful not-configured status: no probe, no traceback (D-06, D-12).
        return VercelStatusResponse(configured=False)

    try:
        import urllib.parse
        import urllib.request

        url = _VERCEL_API_URL
        project_id = os.environ.get("HORUS_OS_VERCEL_PROJECT_ID")
        if project_id:
            # URL-encode the project id so a value with reserved characters
            # cannot malform the query string (WR-05).
            url = f"{url}&projectId={urllib.parse.quote(project_id, safe='')}"

        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {token}", "User-Agent": "horus-os"},
        )
        with urllib.request.urlopen(req, timeout=_VERCEL_HTTP_TIMEOUT) as resp:
            body = json.loads(resp.read())
        deployments = body.get("deployments") or []
        if not deployments:
            return VercelStatusResponse(configured=True)
        latest = deployments[0]
        state = latest.get("state") or latest.get("readyState")
        url_field = latest.get("url")
        created = latest.get("createdAt")
        if created is None:
            created = latest.get("created")
        return VercelStatusResponse(
            configured=True,
            state=str(state) if state is not None else None,
            url=str(url_field) if url_field is not None else None,
            created_at=str(created) if created is not None else None,
        )
    except Exception as exc:
        # Return only the exception class name to avoid echoing token material
        # (str(exc) of a URLError can carry the request repr / Authorization).
        return VercelStatusResponse(configured=True, error=type(exc).__name__)


__all__ = ["router"]
