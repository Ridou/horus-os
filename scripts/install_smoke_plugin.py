"""Plugin install-smoke test driver — same coverage, no background process.

Phase 49 originally drove the smoke test by launching ``horus-os serve`` as
a background process and polling ``/api/health`` over loopback. That pattern
worked on Linux and macOS but silently failed on the GitHub Actions Windows
runners: ``Start-Process -NoNewWindow`` plus ``System.Diagnostics.Process``
both terminated the Python child before any output buffer was flushed.

The diagnostic confirmed the failure was purely in the PowerShell
process-handling layer, not in the v0.5 plugin code paths:

    create_app OK; route count=36
    plugin_registry present; entries=1
      horus-os-example-plugin: status=error, error_phase=permission

So this driver gives up on the background launch and exercises the same
FastAPI app via ``TestClient`` inside a single Python process. The plugin
discovery, validation, permission gate, loader, lifespan, and REST API
all run; the only thing we lose is the actual TCP bind to port 18000,
which is exercised by separate uvicorn unit tests.

Usage:

    HORUS_DATA=/path/to/data python scripts/install_smoke_plugin.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    sys.exit(1)


def _ok(message: str) -> None:
    print(f"OK: {message}")


def main() -> int:
    data_dir_str = os.environ.get("HORUS_DATA")
    if not data_dir_str:
        _fail("HORUS_DATA env var is required (path to the horus-os data dir)")

    data_dir = Path(data_dir_str)
    if not data_dir.is_dir():
        _fail(f"HORUS_DATA does not exist or is not a directory: {data_dir}")

    # Import lazily so missing-extras errors surface clearly.
    try:
        from fastapi.testclient import TestClient

        from horus_os.config import Config
        from horus_os.plugins.permissions import PermissionService
        from horus_os.server.api import create_app
        from horus_os.storage import Database
    except ImportError as exc:
        _fail(f"missing dependency: {exc}")

    # First boot: discovery runs in the FastAPI lifespan, the plugin lands
    # in plugin_registry with status='error', error_phase='permission'.
    app = create_app(data_dir=data_dir)
    with TestClient(app) as client:
        resp = client.get("/api/plugins")
        if resp.status_code != 200:
            _fail(f"GET /api/plugins -> {resp.status_code}: {resp.text}")
        body = resp.json()
        rows = [p for p in body["plugins"] if p["name"] == "horus-os-example-plugin"]
        if len(rows) != 1:
            _fail(f"expected exactly one row for horus-os-example-plugin, got {rows}")
        row = rows[0]
        if row["status"] not in ("pending", "error"):
            _fail(f"pre-grant: unexpected status {row['status']!r}; row={row}")
        if set(row["pending_capabilities"]) != {"filesystem.read", "secrets.read"}:
            _fail(f"pre-grant: pending capabilities mismatch; row={row}")
        _ok(f"pre-grant: status={row['status']}, pending={sorted(row['pending_capabilities'])}")

    # Grant both capabilities via PermissionService directly (the CLI's
    # `grant` subcommand wraps this same call).
    cfg = Config.load(data_dir)
    db = Database(cfg.db_path)
    db.init()
    service = PermissionService(db)
    # Read the persisted plugin row to discover the version + manifest_hash
    # (the discovery step inserted them into the `plugins` table).
    with db._connect() as conn:
        plugin_row = conn.execute(
            "SELECT version, manifest_hash FROM plugins WHERE name = ?",
            ("horus-os-example-plugin",),
        ).fetchone()
    if plugin_row is None:
        _fail("no row in plugins table after discovery — registry didn't persist")
    version = plugin_row["version"]
    manifest_hash = plugin_row["manifest_hash"]
    for cap in ("filesystem.read", "secrets.read"):
        service.grant(
            "horus-os-example-plugin",
            version,
            cap,
            actor="cli",
            manifest_hash=manifest_hash,
        )
    _ok("granted filesystem.read + secrets.read via PermissionService")

    # Second boot: with both grants in place, the lifespan should load
    # the plugin's tools + adapter into the registries.
    app2 = create_app(data_dir=data_dir)
    with TestClient(app2) as client:
        resp = client.get("/api/plugins")
        if resp.status_code != 200:
            _fail(f"GET /api/plugins (post-grant) -> {resp.status_code}: {resp.text}")
        body = resp.json()
        rows = [p for p in body["plugins"] if p["name"] == "horus-os-example-plugin"]
        if len(rows) != 1:
            _fail(f"post-grant: expected one row, got {rows}")
        row = rows[0]
        if row["status"] != "loaded":
            _fail(f"post-grant: expected status='loaded', got row={row}")
        if set(row["granted_capabilities"]) != {"filesystem.read", "secrets.read"}:
            _fail(f"post-grant: granted set mismatch; row={row}")
        if row["pending_capabilities"]:
            _fail(f"post-grant: pending should be empty; row={row}")
        _ok(f"post-grant: status={row['status']}, granted={sorted(row['granted_capabilities'])}")

    print("smoke OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
