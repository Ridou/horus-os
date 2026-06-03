"""Write path for integration credentials.

Provides two secured POST endpoints:
  POST /api/integrations/{name}/keys   -- persist a credential to data_dir/.env
  POST /api/integrations/{name}/verify -- run the integration probe and record result

Security constraints implemented here (all are hard requirements):
  - Loopback guard: request.client.host (TCP socket peer) must be a loopback address.
    Non-loopback peers receive HTTP 403. NEVER uses X-Forwarded-For or any header.
  - Demo-mode refusal: HORUS_OS_DEMO=1 returns 403 from both endpoints before any write.
  - chmod 600: .env file is written at mode 0600 on posix, guarded with os.name == 'posix'
    so Windows CI passes.
  - No secret echo: neither response, nor error message, ever contains the credential value.
    KeyWriteResponse and VerifyResponse use extra='forbid'.
  - Key-hash invalidation: saving a NEW credential value resets that integration's
    verified state to False. Re-saving the same value (same hash) preserves an
    existing verified=True state without requiring re-verification.
    compute_status re-checks the hash on each GET request.
  - Rotation detection: the Wave 1 SQL ON CONFLICT logic resets verified to 0 when the
    key hash changes, so a rotation outside the dashboard also invalidates the green light.
"""

from __future__ import annotations

import hashlib
import ipaddress
import os
import stat
import tempfile
from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from horus_os.config import Config
from horus_os.server.integrations import INTEGRATION_REGISTRY
from horus_os.server.schemas import KeyWriteRequest, KeyWriteResponse, VerifyResponse
from horus_os.storage import Database

router = APIRouter()

# Loopback address set for fast membership check before ipaddress fallback.
_LOOPBACK_HOSTS: frozenset[str] = frozenset({"127.0.0.1", "::1", "localhost"})


# ---------------------------------------------------------------------------
# Security helpers
# ---------------------------------------------------------------------------


def _require_loopback(request: Request) -> None:
    """Raise HTTP 403 if the request did not arrive from a loopback address.

    Decision is based exclusively on request.client.host (the TCP socket peer).
    No header is read for this decision.
    """
    client = request.client
    if client is None:
        raise HTTPException(status_code=403, detail="loopback access required")
    host = client.host
    if host in _LOOPBACK_HOSTS:
        return
    try:
        if ipaddress.ip_address(host).is_loopback:
            return
    except ValueError:
        pass
    raise HTTPException(status_code=403, detail="loopback access required")


def _is_demo_mode() -> bool:
    """Return True when HORUS_OS_DEMO=1 is set in the environment."""
    return os.environ.get("HORUS_OS_DEMO", "") == "1"


# ---------------------------------------------------------------------------
# Config resolution
# ---------------------------------------------------------------------------


def _config_for_request(request: Request) -> Config:
    """Resolve Config the same way dashboard_api does.

    create_app stores the resolved data_dir on app.state.data_dir;
    fall back to Config.load(None) for the default-paths case.
    """
    data_dir = getattr(request.app.state, "data_dir", None)
    if data_dir is not None:
        return Config.load(Path(data_dir).expanduser())
    return Config.load(None)


# ---------------------------------------------------------------------------
# .env file helpers (copied verbatim from wizard.py)
# ---------------------------------------------------------------------------


def _load_env(data_dir: Path) -> dict[str, str]:
    env_path = data_dir / ".env"
    if not env_path.exists():
        return {}
    result: dict[str, str] = {}
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        result[key.strip()] = value.strip()
    return result


def _write_env(data_dir: Path, env: dict[str, str]) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    env_path = data_dir / ".env"
    lines = [f"{k}={v}" for k, v in env.items()]
    _atomic_write(env_path, "\n".join(lines) + "\n")
    if os.name == "posix":
        try:
            os.chmod(env_path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix="." + path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def _write_single_key(data_dir: Path, env_var: str, value: str) -> None:
    """Update exactly one key in data_dir/.env without clobbering others.

    The value is stripped of leading/trailing whitespace so the stored
    hash matches the hash computed after reload (which also strips).
    """
    value = value.strip()
    env = _load_env(data_dir)
    env[env_var] = value
    _write_env(data_dir, env)


# ---------------------------------------------------------------------------
# Key hashing
# ---------------------------------------------------------------------------


def _compute_key_hash(value: str) -> str:
    """Return a SHA-256 hex digest of the credential value."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Verification probes
# ---------------------------------------------------------------------------


def _probe_anthropic() -> tuple[bool, str | None]:
    """Probe Anthropic by making a minimal API call. Reads key from os.environ."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return False, "ANTHROPIC_API_KEY not set"
    try:
        from anthropic import Anthropic, AuthenticationError
    except ImportError:
        return False, "anthropic SDK not installed"
    client = Anthropic(api_key=key)
    try:
        client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1,
            messages=[{"role": "user", "content": "ping"}],
        )
    except AuthenticationError:
        return False, "authentication failed"
    except Exception as exc:
        # Return only the exception type name to avoid echoing key material.
        return False, type(exc).__name__
    return True, None


def _probe_gemini() -> tuple[bool, str | None]:
    """Probe Gemini by making a minimal API call. Reads key from os.environ."""
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        return False, "GEMINI_API_KEY not set"
    try:
        from google import genai
    except ImportError:
        return False, "google-genai SDK not installed"
    client = genai.Client(api_key=key)
    try:
        client.models.generate_content(model="gemini-2.5-flash", contents="ping")
    except Exception as exc:
        # Return only the exception type name to avoid echoing key material.
        return False, type(exc).__name__
    return True, None


def _probe_github() -> tuple[bool, str | None]:
    """Probe GitHub by making a minimal API call. Reads token from os.environ."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return False, "GITHUB_TOKEN not set"
    try:
        import urllib.request

        req = urllib.request.Request(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {token}", "User-Agent": "horus-os"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                return True, None
            return False, f"HTTP {resp.status}"
    except Exception as exc:
        # Return only the exception type name to avoid echoing token material.
        return False, type(exc).__name__


VERIFICATION_PROBES: dict[str, Callable[[], tuple[bool, str | None]]] = {
    "anthropic": _probe_anthropic,
    "gemini": _probe_gemini,
    "github": _probe_github,
}


# ---------------------------------------------------------------------------
# Registry lookup
# ---------------------------------------------------------------------------


def _find_integration(name: str) -> dict | None:
    """Return the registry entry for the given integration id, or None."""
    return next((e for e in INTEGRATION_REGISTRY if e["id"] == name), None)


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


@router.post("/api/integrations/{name}/keys", response_model=KeyWriteResponse)
def post_integration_key(
    name: str,
    body: KeyWriteRequest,
    request: Request,
) -> KeyWriteResponse:
    """Persist a credential to data_dir/.env at mode 0600 (posix).

    Security constraints enforced:
      - Loopback guard checked first via request.client.host.
      - Demo-mode returns 403 without any write.
      - The credential value is never included in the response.
      - Key hash is recorded and verified state is reset to False.
    """
    _require_loopback(request)
    if _is_demo_mode():
        raise HTTPException(status_code=403, detail="disabled in demo mode")

    entry = _find_integration(name)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"integration {name!r} not found")

    cfg = _config_for_request(request)
    # Normalize whitespace so the stored value, env value, and hash are all
    # consistent with what _load_env returns after a process restart.
    normalized = body.value.strip()
    _write_single_key(cfg.data_dir, entry["env_var"], normalized)
    # Inject into the current process environment so the probe can use it immediately.
    os.environ[entry["env_var"]] = normalized

    # Record key hash and reset verified state. init() is idempotent so the
    # table is created even on a fresh data_dir that has never been initialized.
    db = Database(cfg.db_path)
    db.init()
    db.upsert_integration_verification(name, _compute_key_hash(normalized), verified=False)

    return KeyWriteResponse(ok=True)


@router.post("/api/integrations/{name}/verify", response_model=VerifyResponse)
def post_integration_verify(
    name: str,
    request: Request,
) -> VerifyResponse:
    """Run the integration probe and record the verified state.

    Security constraints enforced:
      - Loopback guard checked first via request.client.host.
      - Demo-mode returns 403.
      - Probe errors return only exception type names, never key material.
      - The credential value is never included in the response.
    """
    _require_loopback(request)
    if _is_demo_mode():
        raise HTTPException(status_code=403, detail="disabled in demo mode")

    entry = _find_integration(name)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"integration {name!r} not found")

    probe = VERIFICATION_PROBES.get(name)
    if probe is None:
        return VerifyResponse(
            ok=False, error="no verification probe available for this integration"
        )

    ok, error = probe()

    if ok:
        # Record verified=True only when the probe succeeds. The stored hash must
        # match the current env value for compute_status to return "verified".
        current_value = os.environ.get(entry["env_var"], "")
        cfg = _config_for_request(request)
        db = Database(cfg.db_path)
        db.init()
        db.upsert_integration_verification(name, _compute_key_hash(current_value), verified=True)

    return VerifyResponse(ok=ok, error=error)
