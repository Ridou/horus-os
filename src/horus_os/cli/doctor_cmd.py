"""`horus-os doctor` subcommand."""

from __future__ import annotations

import argparse
import os
from typing import TextIO

# The horus-os synced tables that must exist with RLS enabled for the
# integration to be healthy (mirrors SYNC_TABLES plus the sync_health heartbeat).
EXPECTED_SYNCED_TABLES = ("traces", "agent_profiles", "tasks", "sync_health")


def run_doctor(args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO) -> int:
    """Report integration health and configuration status.

    With --supabase, calls the check_rls_status() RPC via PostgREST and
    reports per-table RLS status. Returns 0 only when every expected horus-os
    synced table (traces, agent_profiles, tasks, sync_health) is present with
    rls_enabled=true. An empty RPC result or any missing/RLS-off expected table
    is reported as unhealthy. Never prints the service key.

    With --service, queries the OS supervisor and reports whether the always-on
    service is registered and running. Returns 0 only when it is running. The
    query never crashes when the supervisor binary is absent; it reports
    install guidance and returns non-zero instead (D-12).
    """
    supabase: bool = getattr(args, "supabase", False)
    service: bool = getattr(args, "service", False)

    if service:
        return _check_service(stdout, stderr)

    if not supabase:
        stdout.write(
            "Usage: horus-os doctor --supabase\n"
            "       horus-os doctor --service\n"
            "\n"
            "  --supabase    Report per-table RLS status via Supabase PostgREST RPC.\n"
            "  --service     Report whether the always-on service is registered and running.\n"
        )
        return 0

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")

    if not url or not key:
        stderr.write("Supabase is not configured; set SUPABASE_URL and SUPABASE_SERVICE_KEY\n")
        return 1

    try:
        import httpx
    except ImportError:
        stderr.write("httpx is not installed; run: pip install 'horus-os[supabase]'\n")
        return 1

    rpc_url = f"{url.rstrip('/')}/rest/v1/rpc/check_rls_status"
    headers = {
        "Authorization": f"Bearer {key}",
        "apikey": key,
        "Content-Type": "application/json",
    }

    try:
        response = httpx.post(rpc_url, headers=headers, json={})
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        stderr.write(
            f"Supabase RPC returned HTTP {exc.response.status_code}. "
            "Ensure check_rls_status() is defined in your migration.\n"
        )
        return 1
    except httpx.RequestError as exc:
        stderr.write(f"Supabase connection error: {type(exc).__name__}\n")
        return 1

    rows: list[dict] = response.json()

    if not isinstance(rows, list):
        stderr.write("Unexpected response from check_rls_status RPC.\n")
        return 1

    # An empty result means nothing was verified; report it as unhealthy rather
    # than silently passing (WR-02).
    if not rows:
        stderr.write(
            "check_rls_status returned no rows; cannot verify RLS. "
            "Apply supabase/migrations/001_initial.sql to your project.\n"
        )
        return 1

    # Index the reported tables and print every row (extra non-horus tables are
    # shown for context but do not by themselves flip the result to failure).
    reported: dict[str, bool] = {}
    for row in rows:
        table = row.get("table_name", "?")
        rls_on = bool(row.get("rls_enabled", False))
        policies = row.get("policy_count", 0)
        status = "on" if rls_on else "OFF"
        stdout.write(f"{table}: RLS={status} policies={policies}\n")
        reported[table] = rls_on

    # Scope pass/fail to the known synced tables: each must be present AND have
    # RLS enabled. A missing expected table is reported loudly (WR-03).
    all_ok = True
    for expected in EXPECTED_SYNCED_TABLES:
        if expected not in reported:
            stderr.write(f"expected table {expected!r} is absent; migration not applied?\n")
            all_ok = False
        elif not reported[expected]:
            stderr.write(f"expected table {expected!r} has RLS disabled.\n")
            all_ok = False

    return 0 if all_ok else 2


def _check_service(stdout: TextIO, stderr: TextIO) -> int:
    """Report always-on service health via the OS supervisor.

    Returns 0 only when the service is registered and running. Detect-and-guide
    (not crash) when the supervisor binary is missing: manager.status() returns
    a guidance report and a False running flag, which we surface and map to a
    non-zero exit code.
    """
    from horus_os.service import manager

    running, report = manager.status()
    stdout.write(report)
    if not running:
        stderr.write("The horus-os always-on service is not registered or not running.\n")
        return 1
    return 0
