"""FastAPI APIRouter for the ``/api/plugins/*`` + ``/api/observability/plugins`` surface.

Lives in a dedicated module so ``api.py`` stays under 1200 lines. The
router is mounted via ``app.include_router(router)`` in ``create_app``
immediately after the adapter bind loop; the order matters only because
the router reads ``request.app.state.plugin_registry`` which the lifespan
populates BEFORE include_router is called.

Six routes for plugin management:

  GET    /api/plugins                          -> list_plugins
  GET    /api/plugins/{name}                   -> get_plugin
  POST   /api/plugins/{name}/enable            -> enable_plugin
  POST   /api/plugins/{name}/disable           -> disable_plugin
  POST   /api/plugins/{name}/grant             -> grant_capability
  DELETE /api/plugins/{name}/grant/{capability} -> revoke_capability

One route for per-plugin observability rollup:

  GET    /api/observability/plugins?since=7d|30d

Per-request DB pattern: each handler re-opens ``Database(cfg.db_path)``
to honor the same liveness contract the existing list_traces handler at
``api.py:411`` follows. The PluginRegistry on ``app.state`` is the
authoritative in-memory view; SQLite is the persistence layer.

T-45-01 mitigation: every grant / revoke route hard-codes
``actor='dashboard'`` -- the wire contract does NOT accept an actor
from the request body. The SQLite CHECK constraint on
``plugin_capability_grants_log.actor`` is the second line of defense.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request

from horus_os.config import Config
from horus_os.observability.queries import parse_window, per_plugin_rollup
from horus_os.plugins.capability_catalog import DESCRIPTIONS, Capability
from horus_os.plugins.permissions import PermissionGate, PermissionService
from horus_os.plugins.registry import PluginEntry, PluginRegistry
from horus_os.storage import Database

router = APIRouter()


def _config_for_request(request: Request) -> Config:
    """Resolve the Config the same way the existing handlers do.

    The factory passes the data_dir through ``app.state.data_dir`` (set
    by ``create_app`` below); fall back to ``Config.load(None)`` for the
    default-paths case. This avoids the implicit closure-capture of
    ``data_dir`` that the existing api.py handlers use, since the router
    is constructed outside ``create_app``.
    """
    data_dir = getattr(request.app.state, "data_dir", None)
    if data_dir is not None:
        return Config.load(Path(data_dir).expanduser())
    return Config.load(None)


def _truncate_error(message: str | None, *, limit: int = 200) -> str | None:
    """Truncate error_message to first ``limit`` chars (Pitfall 6 hygiene)."""
    if message is None:
        return None
    if len(message) <= limit:
        return message
    return message[:limit]


def _entry_to_plugin_info(
    entry: PluginEntry,
    registry: PluginRegistry,
    db: Database,
) -> dict[str, Any]:
    """Map one PluginEntry -> PluginInfo-shaped dict.

    Spec-derived fields default to ``''`` / ``None`` / empty tuple when
    ``entry.spec is None`` (DiscoveryError-only rows). Otherwise the
    PermissionGate resolves the requested cap set into (granted, pending)
    sets which we serialize as sorted string tuples for deterministic
    test output.
    """
    spec = entry.spec
    if spec is not None:
        gate = PermissionGate(db)
        granted, pending = gate.resolve(spec)
        granted_strs = tuple(sorted(c.value for c in granted))
        pending_strs = tuple(sorted(c.value for c in pending))
        version = spec.version
        author = spec.author
        homepage = spec.homepage
        issue_tracker = spec.issue_tracker
    else:
        granted_strs = ()
        pending_strs = ()
        version = ""
        author = ""
        homepage = None
        issue_tracker = None

    return {
        "name": entry.name,
        "version": version,
        "status": entry.status,
        "error_phase": entry.error_phase,
        "last_error": _truncate_error(entry.error_message),
        "declared_tools": list(entry.registered_tools),
        "declared_adapters": list(entry.registered_adapters),
        "granted_capabilities": list(granted_strs),
        "pending_capabilities": list(pending_strs),
        "enabled": registry.is_enabled(entry.name),
        "manifest_homepage": homepage,
        "manifest_issue_tracker": issue_tracker,
        "manifest_author": author,
    }


def _grants_log_for(db: Database, plugin_name: str, *, limit: int = 20) -> list[dict[str, Any]]:
    """Read the last ``limit`` audit-log rows for ``plugin_name``, newest first."""
    with db._connect() as conn:
        rows = conn.execute(
            """
            SELECT capability, action, actor, manifest_hash, timestamp
            FROM plugin_capability_grants_log
            WHERE plugin_name = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (plugin_name, limit),
        ).fetchall()
    return [
        {
            "capability": row["capability"],
            "action": row["action"],
            "actor": row["actor"],
            "manifest_hash": row["manifest_hash"],
            "timestamp": row["timestamp"],
        }
        for row in rows
    ]


def _require_registry(request: Request) -> PluginRegistry:
    registry = getattr(request.app.state, "plugin_registry", None)
    if registry is None:
        # Should be impossible -- create_app wires this. Surface as 503
        # mirroring the existing "database not initialized" pattern.
        raise HTTPException(503, detail="plugin registry not initialized")
    return registry


def _require_db(request: Request) -> Database:
    cfg = _config_for_request(request)
    if not cfg.db_path.exists():
        raise HTTPException(503, detail="database not initialized; run `horus-os init`")
    return Database(cfg.db_path)


def _capability_or_400(name: str) -> Capability:
    """Resolve a string to ``Capability`` or raise HTTPException(400)."""
    try:
        return Capability(name)
    except ValueError as exc:
        valid = sorted(c.value for c in Capability)
        raise HTTPException(
            400,
            detail=f"unknown capability {name!r}; must be one of {valid}",
        ) from exc


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------


@router.get("/api/plugins")
def list_plugins(request: Request) -> dict[str, list[dict[str, Any]]]:
    registry = _require_registry(request)
    db = _require_db(request)
    plugins = [_entry_to_plugin_info(entry, registry, db) for entry in registry.all()]
    return {"plugins": plugins}


@router.get("/api/plugins/{name}")
def get_plugin(name: str, request: Request) -> dict[str, Any]:
    registry = _require_registry(request)
    entry = registry.get(name)
    if entry is None:
        raise HTTPException(404, detail=f"plugin {name!r} not found")
    db = _require_db(request)
    info = _entry_to_plugin_info(entry, registry, db)
    info["grants_log"] = _grants_log_for(db, name)
    return info


@router.post("/api/plugins/{name}/enable")
def enable_plugin(name: str, request: Request) -> dict[str, Any]:
    registry = _require_registry(request)
    entry = registry.get(name)
    if entry is None:
        raise HTTPException(404, detail=f"plugin {name!r} not found")
    registry.enable(name)
    return {"name": name, "enabled": True, "needs_restart": True}


@router.post("/api/plugins/{name}/disable")
def disable_plugin(name: str, request: Request) -> dict[str, Any]:
    registry = _require_registry(request)
    entry = registry.get(name)
    if entry is None:
        raise HTTPException(404, detail=f"plugin {name!r} not found")
    registry.disable(name)
    return {"name": name, "enabled": False, "needs_restart": True}


@router.post("/api/plugins/{name}/grant")
def grant_capability(
    name: str,
    request: Request,
    payload: dict[str, Any] = Body(default_factory=dict),  # noqa: B008
) -> dict[str, Any]:
    """Grant one capability to a plugin. T-45-01: actor hard-coded to 'dashboard'.

    Validation order:
      1. body has 'capability' key -> else 400
      2. capability string in closed enum -> else 400
      3. registry has entry for name -> else 404
      4. registry entry has spec (not a DiscoveryError row) -> else 409
      5. PermissionService.grant + return PluginInfo-shaped dict
    """
    if not isinstance(payload, dict) or "capability" not in payload:
        raise HTTPException(400, detail="missing required field: 'capability'")
    cap_name = payload["capability"]
    if not isinstance(cap_name, str):
        raise HTTPException(400, detail="'capability' must be a string")
    capability = _capability_or_400(cap_name)

    registry = _require_registry(request)
    entry = registry.get(name)
    if entry is None:
        raise HTTPException(404, detail=f"plugin {name!r} not found")
    if entry.spec is None:
        raise HTTPException(
            409,
            detail="cannot grant capability for an unloaded plugin (no spec)",
        )

    db = _require_db(request)
    # T-45-01: actor hard-coded; wire contract never sees it.
    PermissionService(db).grant(
        plugin_name=name,
        plugin_version=entry.spec.version,
        capability=capability.value,
        actor="dashboard",
        manifest_hash=entry.spec.manifest_hash,
    )
    return _entry_to_plugin_info(entry, registry, db)


@router.delete("/api/plugins/{name}/grant/{capability}")
def revoke_capability(
    name: str,
    capability: str,
    request: Request,
) -> dict[str, Any]:
    """Revoke one capability from a plugin. T-45-01: actor hard-coded to 'dashboard'."""
    cap = _capability_or_400(capability)

    registry = _require_registry(request)
    entry = registry.get(name)
    if entry is None:
        raise HTTPException(404, detail=f"plugin {name!r} not found")
    if entry.spec is None:
        raise HTTPException(
            409,
            detail="cannot revoke capability for an unloaded plugin (no spec)",
        )

    db = _require_db(request)
    PermissionService(db).revoke(
        plugin_name=name,
        plugin_version=entry.spec.version,
        capability=cap.value,
        actor="dashboard",
    )
    return _entry_to_plugin_info(entry, registry, db)


@router.get("/api/observability/plugins")
def observability_plugins(request: Request, since: str = "7d") -> dict[str, Any]:
    """Per-plugin rollup over the window. 400 on bad ``since``."""
    try:
        parse_window(since)
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    db = _require_db(request)
    rollups = per_plugin_rollup(db, since)
    return {"plugins": rollups}


# Re-export DESCRIPTIONS so future callers that import this module can
# render capability descriptions without a second import.
__all__ = ["DESCRIPTIONS", "router"]
