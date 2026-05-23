"""Reference HTTP webhook adapter for horus-os.

Mounts `POST /api/adapters/webhook`. Validates an HMAC-SHA256
signature on every request, parses a JSON body, looks up an
optional agent profile, runs one `run_agent` turn, records a
trace row, and returns the trace id with the final text.

Security: the adapter refuses to run when `HORUS_OS_WEBHOOK_SECRET`
is unset. Requests must include `X-Horus-Signature: sha256=<hex>`
where `<hex>` is the HMAC-SHA256 of the raw request body keyed
by the configured secret. A constant-time comparison via
`hmac.compare_digest` is used to avoid timing oracles.

This adapter satisfies the `Adapter` Protocol from
`horus_os.adapters.base`. It is declared as the package's reference
adapter in pyproject under `[project.entry-points."horus_os.adapters"]`.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from typing import Any

from horus_os.adapters.base import AdapterContext
from horus_os.agent import SUPPORTED_PROVIDERS, run_agent
from horus_os.config import Config
from horus_os.storage import Database

WEBHOOK_SECRET_ENV = "HORUS_OS_WEBHOOK_SECRET"
SIGNATURE_HEADER = "X-Horus-Signature"
SIGNATURE_PREFIX = "sha256="


class WebhookAdapter:
    """An inbound HTTP webhook that routes signed payloads to `run_agent`."""

    name = "webhook"

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": 1,
            "endpoint": "/api/adapters/webhook",
            "auth": "hmac-sha256",
            "env": WEBHOOK_SECRET_ENV,
        }

    def bind(self, app: Any, context: AdapterContext) -> None:
        # Import FastAPI symbols lazily so the package import does not
        # require FastAPI when the dashboard extra is not installed.
        # The classes are also rebound onto this module's globals so
        # that `from __future__ import annotations` does not break
        # FastAPI's signature introspection of the route below: when
        # FastAPI resolves the stringified `Request` annotation it
        # looks up the name in this module's globals.
        from fastapi import HTTPException, Request

        globals()["Request"] = Request
        globals()["HTTPException"] = HTTPException

        @app.post("/api/adapters/webhook")
        async def _handle_webhook(request: Request) -> dict[str, Any]:
            secret = os.environ.get(WEBHOOK_SECRET_ENV) or ""
            if not secret:
                raise HTTPException(
                    503,
                    detail=(f"webhook adapter is not configured; set {WEBHOOK_SECRET_ENV}"),
                )

            raw_body = await request.body()
            signature_header = request.headers.get(SIGNATURE_HEADER, "")
            if not signature_header.startswith(SIGNATURE_PREFIX):
                raise HTTPException(401, detail="missing or malformed signature")
            received_hex = signature_header[len(SIGNATURE_PREFIX) :]
            expected_hex = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected_hex, received_hex):
                raise HTTPException(401, detail="invalid signature")

            try:
                payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
            except (UnicodeDecodeError, ValueError) as exc:
                raise HTTPException(400, detail=f"invalid JSON body: {exc}") from exc
            if not isinstance(payload, dict):
                raise HTTPException(400, detail="payload must be a JSON object")
            prompt = payload.get("prompt")
            if not isinstance(prompt, str) or not prompt.strip():
                raise HTTPException(400, detail="prompt is required")

            cfg = context.config
            provider = payload.get("provider") or cfg.default_provider
            if provider not in SUPPORTED_PROVIDERS:
                raise HTTPException(400, detail=f"unknown provider {provider!r}")

            db = Database(cfg.db_path)
            raw_agent = payload.get("agent")
            agent_name: str | None = None
            profile = None
            if isinstance(raw_agent, str) and raw_agent:
                profile = db.load_profile(raw_agent)
                if profile is None:
                    raise HTTPException(404, detail=f"agent profile {raw_agent!r} not found")
                agent_name = raw_agent

            model = (
                payload.get("model")
                or (profile.default_model if profile else None)
                or _default_model(cfg, provider)
            )
            system_prompt = profile.system_prompt if profile else None

            start = time.perf_counter()
            try:
                result = run_agent(
                    prompt,
                    provider=provider,
                    tools=None,
                    model=model,
                    system_prompt=system_prompt,
                )
            except Exception as exc:
                latency_ms = int((time.perf_counter() - start) * 1000)
                from horus_os.types import AgentResult

                trace_id = db.record_trace(
                    prompt,
                    AgentResult(text="", provider=provider, model=model),
                    latency_ms=latency_ms,
                    status="error",
                    error_message=f"{type(exc).__name__}: {exc}",
                    agent_profile_name=agent_name,
                )
                raise HTTPException(
                    500,
                    detail={
                        "error": f"{type(exc).__name__}: {exc}",
                        "trace_id": trace_id,
                    },
                ) from exc

            latency_ms = int((time.perf_counter() - start) * 1000)
            trace_id = db.record_trace(
                prompt,
                result,
                latency_ms=latency_ms,
                agent_profile_name=agent_name,
            )
            # Bump last_activity_at for this adapter so /api/adapters
            # reflects when the webhook last successfully handled a
            # request.
            context.registry.touch(self.name)
            return {
                "trace_id": trace_id,
                "text": result.text,
                "latency_ms": latency_ms,
            }


def _default_model(cfg: Config, provider: str) -> str:
    if provider == "anthropic":
        return cfg.anthropic_model
    return cfg.gemini_model
