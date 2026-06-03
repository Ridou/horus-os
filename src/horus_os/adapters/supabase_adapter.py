"""Optional Supabase push-only sync adapter.

Incrementally pushes local SQLite rows to Supabase PostgREST using a
per-table cursor persisted in the local `sync_cursors` table (Phase 65,
Plan 01). The adapter is a silent no-op when SUPABASE_URL and
SUPABASE_SERVICE_KEY are absent so the local runtime starts cleanly with
zero Supabase configuration (SUPA-05).

The service key never leaves the backend process, never appears in a log
message, and is never mounted on a browser-accessible route (SUPA-02).
httpx is imported lazily inside `start()` so this module loads cleanly
even when the [supabase] optional extra is not installed.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
from datetime import UTC, datetime
from typing import Any

from horus_os.adapters.base import AdapterContext
from horus_os.storage import Database

SUPABASE_URL_ENV = "SUPABASE_URL"
SUPABASE_KEY_ENV = "SUPABASE_SERVICE_KEY"
SYNC_INTERVAL_SECS = 30
SYNC_PAGE_LIMIT = 500

# Tables eligible for Supabase push-only sync and their cursor columns.
# Matches the subset of _SYNC_ALLOWLIST that is meaningful for the remote
# dashboard (traces, agent_profiles, tasks). Plugin/capability tables are
# internal plumbing and are NOT synced.
SYNC_TABLES: dict[str, str] = {
    "traces": "created_at",
    "agent_profiles": "updated_at",
    "tasks": "updated_at",
}


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string with a Z suffix."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _sync_headers(key: str) -> dict[str, str]:
    """Return the PostgREST upsert headers for a given service key.

    Factored out so tests can assert the exact header shape without
    running the full sync loop.
    """
    return {
        "Authorization": f"Bearer {key}",
        "apikey": key,
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }


class SupabaseAdapter:
    """Background sync adapter that pushes local SQLite rows to Supabase.

    With no Supabase env vars configured, `start()` returns immediately
    without touching the adapter registry (SUPA-05: zero-config no-op).
    When both SUPABASE_URL and SUPABASE_SERVICE_KEY are present the
    adapter launches a non-blocking asyncio background task that runs
    an incremental push every SYNC_INTERVAL_SECS seconds.
    """

    name = "supabase"

    def __init__(self) -> None:
        self._task: asyncio.Task[Any] | None = None
        self._context: AdapterContext | None = None

    def bind(self, app: Any, context: AdapterContext) -> None:
        """No HTTP routes needed; the service key must never reach a browser route."""
        return None

    async def start(self, context: AdapterContext) -> None:
        """Launch the background sync task if both env vars are present.

        Order of guards:
        1. Env vars (SUPA-05): missing config means "not opted in". Silent
           return, no mark_error, no mark_running. Health check stays clean.
        2. httpx import: if the [supabase] extra is missing, record an error
           and return so the user knows what to install.
        3. Launch asyncio.create_task and mark_running.
        """
        self._context = context

        # Guard 1: env vars - silent no-op when not configured (SUPA-05, T-65-06)
        url = os.environ.get(SUPABASE_URL_ENV)
        key = os.environ.get(SUPABASE_KEY_ENV)
        if not url or not key:
            return  # health check stays clean; no error registered

        # Guard 2: lazy import - keeps module importable without the extra
        try:
            import httpx  # noqa: F401
        except ImportError:
            context.registry.mark_error(
                self.name,
                "httpx not installed; pip install 'horus-os[supabase]'",
            )
            return

        # Launch the sync loop as a non-blocking background task
        self._task = asyncio.create_task(self._sync_loop(url, key, context))
        context.registry.mark_running(self.name)

    async def stop(self) -> None:
        """Cancel the background sync task without raising.

        Suppress only asyncio.CancelledError (raised by the awaited cancel) and
        incidental task Exceptions. KeyboardInterrupt and SystemExit are NOT
        suppressed so interpreter-control signals still propagate during shutdown
        (Phase 65 WR-01).
        """
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._task

    async def _sync_loop(self, url: str, key: str, context: AdapterContext) -> None:
        """Run the incremental sync loop until cancelled.

        Each tick:
        1. Syncs each table in SYNC_TABLES, isolated in its own try/except so one
           table failing does not suppress the others (Phase 65 WR-04).
        2. ALWAYS pushes a denormalized sync_health row carrying the list of
           tables that synced cleanly this tick, then calls touch(), regardless
           of per-table failures so the heartbeat is never hidden (WR-04).
        3. On a fully-clean tick clears the adapter error state via mark_running
           so recovery is visible; only marks error when this tick had failures
           (Phase 65 WR-05).
        4. Sleeps SYNC_INTERVAL_SECS.

        Transient httpx errors mark the adapter as errored but do NOT kill the
        loop (T-65-05: DoS protection). asyncio.CancelledError is re-raised so
        stop() works correctly.
        """
        import httpx

        db = Database(context.config.db_path)
        async with httpx.AsyncClient() as client:
            while True:
                synced_ok: list[str] = []
                failures: list[str] = []
                for table, cursor_col in SYNC_TABLES.items():
                    try:
                        await _sync_table(db, client, url, key, table, cursor_col)
                        synced_ok.append(table)
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        failures.append(f"{table}: {type(exc).__name__}: {exc}")

                # Always attempt the health push and touch so one failing table
                # never hides the heartbeat or the other tables' successes (WR-04).
                try:
                    await _push_sync_health(client, url, key, synced_ok)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    failures.append(f"sync_health: {type(exc).__name__}: {exc}")

                context.registry.touch(self.name)

                if failures:
                    # Transient error: mark but continue the loop (T-65-05).
                    context.registry.mark_error(self.name, "; ".join(failures))
                else:
                    # Fully-clean tick: clear any prior error so recovery is
                    # visible instead of reading as errored forever (WR-05).
                    context.registry.mark_running(self.name)

                await asyncio.sleep(SYNC_INTERVAL_SECS)


def _parse_cursor(cursor: str) -> tuple[str, int]:
    """Split a composite cursor string into (timestamp, id).

    The persisted cursor is a single opaque "<timestamp>|<id>" string the
    adapter owns. The epoch default ("1970-01-01T00:00:00.000000Z") has no
    "|" separator and parses to id 0, so storage stays generic and the
    Plan 01 default still works unchanged (Phase 65 CR-02).
    """
    ts, sep, id_part = cursor.rpartition("|")
    if not sep:
        return cursor, 0
    try:
        return ts, int(id_part)
    except ValueError:
        # Malformed id segment: fall back to the full string with id 0 rather
        # than risk skipping rows.
        return cursor, 0


async def _sync_table(
    db: Database,
    client: Any,
    url: str,
    key: str,
    table: str,
    cursor_col: str,
) -> None:
    """Sync one table: read cursor, drain new rows page by page, advance cursor.

    Loops within the tick until a page returns fewer than SYNC_PAGE_LIMIT rows so
    a backlog larger than one page drains in a single tick. The cursor is a
    composite (timestamp, id) keyset, which is lossless: rows that share a
    boundary timestamp are never skipped across page boundaries (Phase 65 CR-02).

    The local surrogate id is stripped from each row before the POST because the
    remote tables key on the natural column (trace_id / name / task_id) and have
    no id column; PostgREST would reject an unknown column (Phase 65 CR-01).

    When list_rows_after returns no rows the POST is skipped and the cursor is
    unchanged (no unnecessary network call).
    """
    while True:
        cursor = db.get_sync_cursor(table)
        ts, last_id = _parse_cursor(cursor)
        rows = db.list_rows_after(table, cursor_col, ts, id_after=last_id, limit=SYNC_PAGE_LIMIT)
        if not rows:
            return
        # Strip the local autoincrement id from the POST payload (CR-01). Keep it
        # locally for keyset cursor advancement below.
        payload = [{k: v for k, v in row.items() if k != "id"} for row in rows]
        resp = await client.post(
            f"{url}/rest/v1/{table}",
            json=payload,
            headers=_sync_headers(key),
        )
        resp.raise_for_status()
        last_row = rows[-1]
        new_cursor = f"{last_row[cursor_col]}|{last_row['id']}"
        db.upsert_sync_cursor(table, new_cursor)
        if len(rows) < SYNC_PAGE_LIMIT:
            return


async def _push_sync_health(
    client: Any, url: str, key: str, synced_tables: list[str] | None = None
) -> None:
    """Push a denormalized sync_health row to Supabase.

    The row carries last_synced_at so the remote dashboard can display when the
    last successful sync occurred, plus synced_tables: the list of tables that
    synced cleanly this tick, JSON-encoded to match the remote TEXT column
    (Phase 65 WR-04). The sync_health table is created by the Plan 03 Postgres
    migration with synced_tables TEXT NOT NULL DEFAULT '[]'.
    """
    resp = await client.post(
        f"{url}/rest/v1/sync_health",
        json=[
            {
                "id": "local",
                "last_synced_at": _now_iso(),
                "synced_tables": json.dumps(synced_tables or []),
            }
        ],
        headers=_sync_headers(key),
    )
    resp.raise_for_status()
