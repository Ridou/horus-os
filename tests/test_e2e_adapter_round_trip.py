"""Adapter contract round-trip tests.

Phase 19 gap C: prior tests cover entry-point discovery and the
reference webhook adapter as separate units. This file walks the full
contract: a third-party adapter declared via a stubbed entry point
gets discovered by `create_app`, mounts its route, validates a signed
POST, calls a stubbed `run_agent`, and persists a trace through the
same `Database` create_app uses. The second test confirms the live
`webhook` entry-point declaration still resolves through
`discover_adapters` after `create_app` runs.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

from horus_os import AgentResult, Config, Database, create_app
from horus_os.adapters import ADAPTER_ENTRY_POINT_GROUP, AdapterContext
from horus_os.adapters import base as adapters_base

_SECRET_ENV = "FAKE_THIRD_PARTY_SECRET"


class _FakeEntryPoint:
    def __init__(self, name: str, target: Any) -> None:
        self.name = name
        self._target = target

    def load(self) -> Any:
        return self._target


def _stub_entry_points(monkeypatch: pytest.MonkeyPatch, eps: list[_FakeEntryPoint]) -> None:
    def fake(group: str | None = None) -> list[_FakeEntryPoint]:
        if group != ADAPTER_ENTRY_POINT_GROUP:
            return []
        return eps

    monkeypatch.setattr(adapters_base, "entry_points", fake)


def _sign(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


class _EchoAdapter:
    """A minimal third-party-style adapter.

    Demonstrates the contract a real third-party would follow:
    - Declared via the `horus_os.adapters` entry point group.
    - Stores the AdapterContext at bind time and uses it to open a
      Database connection per request.
    - Validates an HMAC signature.
    - Calls a top-level entry point (here: stubbed `_run_agent`) and
      records a trace.
    """

    name = "echo_third_party"

    def __init__(self) -> None:
        self.context: AdapterContext | None = None

    def bind(self, app: Any, context: AdapterContext) -> None:
        self.context = context
        secret_env = _SECRET_ENV

        @app.post("/api/adapters/echo_third_party")
        async def _handle(request: Request) -> dict[str, Any]:
            import os

            secret = os.environ.get(secret_env, "")
            if not secret:
                raise HTTPException(503, detail=f"{secret_env} unset")
            raw = await request.body()
            sig = request.headers.get("X-Echo-Signature", "")
            if not sig.startswith("sha256="):
                raise HTTPException(401, detail="bad signature scheme")
            expected = _sign(raw, secret)
            if not hmac.compare_digest(expected, sig):
                raise HTTPException(401, detail="bad signature")
            payload = json.loads(raw.decode("utf-8"))
            prompt = payload.get("prompt", "")
            result = _run_agent(prompt)
            db = Database(context.config.db_path)
            trace_id = db.record_trace(prompt, result)
            return {"trace_id": trace_id, "text": result.text}


# Module-level so the test can monkeypatch it.
def _run_agent(prompt: str) -> AgentResult:
    return AgentResult(text=f"echo: {prompt}", provider="anthropic", model="m")


def _init_data_dir(tmp_path: Path) -> None:
    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    db = Database(cfg.db_path)
    db.init()


def test_third_party_adapter_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A fake third-party adapter gets discovered via entry_points,
    mounted by create_app, accepts a signed POST, runs a stubbed
    agent, and persists a trace through the same DB the dashboard
    uses.

    This closes the seam between adapter discovery and webhook-style
    request handling end-to-end (not adapter discovery alone, not
    direct WebhookAdapter().bind(app) alone).
    """
    _init_data_dir(tmp_path)
    monkeypatch.setenv(_SECRET_ENV, "topsecret")
    _stub_entry_points(
        monkeypatch,
        [_FakeEntryPoint("echo_third_party", _EchoAdapter)],
    )

    client = TestClient(create_app(data_dir=tmp_path))
    body = json.dumps({"prompt": "ping"}).encode()
    response = client.post(
        "/api/adapters/echo_third_party",
        content=body,
        headers={"X-Echo-Signature": _sign(body, "topsecret")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["text"] == "echo: ping"
    trace_id = payload["trace_id"]

    # The trace landed in the same SQLite file the core dashboard reads.
    cfg = Config.with_defaults(tmp_path)
    db = Database(cfg.db_path)
    record = db.get_trace(trace_id)
    assert record is not None
    assert record.prompt == "ping"
    assert record.response_text == "echo: ping"

    # And the dashboard surface sees the trace too.
    listed = client.get("/api/traces").json()
    assert any(t["trace_id"] == trace_id for t in listed["traces"])


def test_third_party_adapter_signature_rejection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A wrong signature on a discovered adapter route returns 401,
    no trace persists.

    Pairs with the happy-path test to lock in the security boundary
    on the discovery + handler integration path, not just on
    WebhookAdapter().bind(app) in isolation.
    """
    _init_data_dir(tmp_path)
    monkeypatch.setenv(_SECRET_ENV, "topsecret")
    _stub_entry_points(
        monkeypatch,
        [_FakeEntryPoint("echo_third_party", _EchoAdapter)],
    )
    client = TestClient(create_app(data_dir=tmp_path))
    body = json.dumps({"prompt": "ping"}).encode()
    response = client.post(
        "/api/adapters/echo_third_party",
        content=body,
        headers={"X-Echo-Signature": "sha256=deadbeef"},
    )
    assert response.status_code == 401

    cfg = Config.with_defaults(tmp_path)
    db = Database(cfg.db_path)
    # No trace was recorded because the adapter rejected before record_trace.
    assert db.list_traces() == []


def test_reference_webhook_adapter_mounted_via_create_app(tmp_path: Path) -> None:
    """Without stubbing entry_points at all, the live entry-point
    registration declared in pyproject.toml means the reference
    WebhookAdapter is automatically discovered and bound to the app.

    Closes the seam between `pyproject.toml`'s
    `[project.entry-points."horus_os.adapters"]` declaration and the
    live `create_app(data_dir)` flow. The webhook adapter tests in
    Phase 17 used WebhookAdapter().bind(app, ctx) directly, bypassing
    this path.
    """
    _init_data_dir(tmp_path)
    client = TestClient(create_app(data_dir=tmp_path))
    # Without HORUS_OS_WEBHOOK_SECRET, the route returns 503 (not 404),
    # which means it is mounted. 404 would mean the entry-point was
    # never discovered and the route was never registered.
    response = client.post(
        "/api/adapters/webhook",
        content=b"{}",
        headers={"X-Horus-Signature": "x"},
    )
    assert response.status_code != 404
    assert response.status_code in (401, 503)
