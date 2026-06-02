"""`horus-os doctor` subcommand."""

from __future__ import annotations

import argparse
import os
from collections.abc import Callable
from pathlib import Path
from typing import TextIO
from urllib.parse import urlsplit

# The horus-os synced tables that must exist with RLS enabled for the
# integration to be healthy (mirrors SYNC_TABLES plus the sync_health heartbeat).
EXPECTED_SYNCED_TABLES = ("traces", "agent_profiles", "tasks", "sync_health")

# Hosts that keep the local model API on the machine itself. A base_url whose
# host is one of these (or a 127.0.0.0/8 address) is safe; anything else is at
# least a LAN-exposure warning and 0.0.0.0 is a hard reject (LP-4). The literal
# "0.0.0.0" never appears in a suggestion; it is only matched as rejected input.
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "[::1]"})

# A live probe must not hang on an unresponsive endpoint (T-69-06).
_PROBE_TIMEOUT_SECONDS = 5.0

# Probe callable: base_url -> (reachable, model_count_or_None, error_or_None).
LocalProber = Callable[[str], "tuple[bool, int | None, str | None]"]


def _validate_local_base_url(base_url: str) -> tuple[str, str | None]:
    """Classify a local provider base_url for safe binding (LP-4).

    Returns a (status, message) pair where status is one of:
      "invalid" - empty or wildcard host (the model API would be exposed to
                  every interface); hard reject with a nonzero exit.
      "warn"    - a syntactically valid but non-loopback host (a LAN address);
                  the model API may be reachable from other machines.
      "ok"      - a loopback host; the model API stays on this machine.
    The message is None for "ok".
    """
    host = (urlsplit(base_url).hostname or "").strip()
    if not host or host == "0.0.0.0" or host == "::":
        return (
            "invalid",
            f"local_base_url {base_url!r} binds a wildcard address; point it at a "
            "loopback host such as http://localhost:11434/v1 so the model API is "
            "not exposed to the LAN.",
        )
    lowered = host.lower()
    if lowered in _LOOPBACK_HOSTS or lowered.startswith("127."):
        return "ok", None
    return (
        "warn",
        f"local_base_url host {host!r} is not a loopback address; the local model "
        "API may be reachable from other machines on your network.",
    )


def _probe_local_endpoint(base_url: str) -> tuple[bool, int | None, str | None]:
    """Live GET {base_url}/models with a short timeout (default prober).

    Returns (reachable, model_count, error). Lazily imports httpx and never
    raises out to the caller; a connection failure becomes (False, None,
    short_message). No secret is ever included in the message.
    """
    try:
        import httpx
    except ImportError:
        return False, None, "httpx is not installed; run: pip install 'horus-os[supabase]'"
    url = f"{base_url.rstrip('/')}/models"
    try:
        response = httpx.get(url, timeout=_PROBE_TIMEOUT_SECONDS)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        return False, None, f"HTTP {exc.response.status_code}"
    except httpx.RequestError as exc:
        return False, None, type(exc).__name__
    try:
        data = response.json().get("data", [])
        count = len(data) if isinstance(data, list) else None
    except (ValueError, AttributeError):
        count = None
    return True, count, None


def _run_doctor_local(
    args: argparse.Namespace,
    *,
    stdout: TextIO,
    stderr: TextIO,
    probe: LocalProber | None = None,
) -> int:
    """Validate the configured local base_url and live-probe it (LP-4).

    Loads Config, rejects a wildcard base_url before any network call,
    warns on a non-loopback host, and probes a loopback/LAN endpoint via an
    injectable prober. Returns 0 only when the base_url is acceptable AND the
    endpoint is reachable. Never prints a key.
    """
    from horus_os.config import Config

    probe = probe or _probe_local_endpoint
    data_dir: Path | None = getattr(args, "data_dir", None)
    config = Config.load(data_dir)
    base_url = config.local_base_url

    status, message = _validate_local_base_url(base_url)
    if status == "invalid":
        stderr.write(f"local endpoint base URL is invalid: {message}\n")
        return 1
    if status == "warn":
        stdout.write(f"WARNING: {message}\n")

    reachable, count, error = probe(base_url)
    if not reachable:
        detail = f" ({error})" if error else ""
        stderr.write(f"local endpoint unreachable at {base_url}{detail}\n")
        return 1

    suffix = f" ({count} models)" if count is not None else ""
    stdout.write(f"local endpoint reachable at {base_url}{suffix}\n")
    return 0


def _run_doctor_memory(
    args: argparse.Namespace,
    *,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    """Report on-device vector-memory status without ever downloading (EM-1/EM-3).

    Loads Config and reports whether vector memory is enabled, the configured
    embedding model, whether the model file is present on disk, whether the
    separate `vectors.sqlite` cache exists, and whether a model/dimension
    mismatch is pending. Prints actionable next steps (download-model or
    reindex) when something is missing. Never triggers a download and never
    embeds; the index is opened read-only-ish (construction touches no network).
    """
    from horus_os.config import Config
    from horus_os.memory.embeddings import ONNXEmbeddingBackend
    from horus_os.memory.vector import (
        EmbeddingDimensionMismatch,
        VectorIndex,
        VectorIndexUnavailable,
    )

    data_dir: Path | None = getattr(args, "data_dir", None)
    config = Config.load(data_dir)

    stdout.write(f"vector_memory_enabled: {config.vector_memory_enabled}\n")
    stdout.write(f"embedding_model: {config.embedding_model}\n")

    try:
        backend = ONNXEmbeddingBackend(config.embedding_model, config.models_path())
    except ValueError as exc:
        stderr.write(f"embedding model misconfigured: {exc}\n")
        return 1

    model_present = backend.is_model_present()
    stdout.write(f"model_present: {model_present}\n")
    if not model_present:
        stdout.write("  next step: run `horus-os memory download-model`\n")

    vectors_path = config.vectors_path()
    index_exists = vectors_path.exists()
    stdout.write(f"index_exists: {index_exists}\n")

    if not index_exists:
        if model_present:
            stdout.write("  next step: run `horus-os memory reindex` to build the index\n")
        return 0

    # The index file exists: report whether it is ready or a model swap is
    # pending. Constructing VectorIndex performs no network call and no embed.
    try:
        index = VectorIndex(vectors_path, backend)
    except VectorIndexUnavailable as exc:
        stderr.write(f"vector index unavailable: {exc}\n")
        return 1
    try:
        if index.mismatch_from is not None:
            stdout.write(
                f"model_mismatch: stored {index.mismatch_from!r}, configured "
                f"{config.embedding_model!r}\n"
            )
            stdout.write("  next step: run `horus-os memory reindex`\n")
        else:
            stdout.write(f"index_ready: {index.is_ready()}\n")
    except EmbeddingDimensionMismatch as exc:
        stdout.write(f"model_mismatch: {exc}\n")
    finally:
        index.close()
    return 0


def run_doctor(
    args: argparse.Namespace,
    *,
    stdout: TextIO,
    stderr: TextIO,
    probe: LocalProber | None = None,
) -> int:
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

    With --local, validates the configured local provider base URL (rejecting a
    wildcard bind per LP-4) and live-probes the endpoint via `probe` (defaults to
    a real short-timeout GET). With --memory, reports on-device vector-memory
    model/index/mismatch status without ever downloading (EM-1/EM-3). Never prints
    any secret.
    """
    supabase: bool = getattr(args, "supabase", False)
    service: bool = getattr(args, "service", False)
    local: bool = getattr(args, "local", False)
    memory: bool = getattr(args, "memory", False)

    if service:
        return _check_service(stdout, stderr)

    if local:
        return _run_doctor_local(args, stdout=stdout, stderr=stderr, probe=probe)

    if memory:
        return _run_doctor_memory(args, stdout=stdout, stderr=stderr)

    if not supabase:
        stdout.write(
            "Usage: horus-os doctor --supabase\n"
            "       horus-os doctor --service\n"
            "       horus-os doctor --local\n"
            "       horus-os doctor --memory\n"
            "\n"
            "  --supabase    Report per-table RLS status via Supabase PostgREST RPC.\n"
            "  --service     Report whether the always-on service is registered and running.\n"
            "  --local       Probe the configured local LLM endpoint and validate its base URL.\n"
            "  --memory      Report on-device vector-memory model and index status.\n"
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
