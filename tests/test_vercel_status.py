"""Tests for GET /api/integrations/vercel/status (VERCEL-03, D-04, D-05, D-06).

Boots a FastAPI TestClient against create_app. These tests assert three
hard properties of the observe-only Vercel deploy-status endpoint:

1. With HORUS_OS_VERCEL_TOKEN unset, the endpoint returns 200 with
   configured=false and null state/url/created_at/error (D-06 graceful
   path; no traceback).

2. With the token set and the Vercel HTTP call mocked to return one
   deployment, the response carries configured=true plus the derived
   state/url/created_at, and the token value appears nowhere in the body
   (D-05).

3. With the token set and the mocked HTTP call raising, the endpoint
   returns 200 with configured=true and error equal to the exception
   class NAME only (type(exc).__name__, never str(exc)), with the token
   value still absent from the body (D-05; the 62-02 precedent).

The tests use no network: urllib.request.urlopen is patched on the
dashboard_api module so the handler never reaches api.vercel.com.
"""

from __future__ import annotations

import json
import urllib.error
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from horus_os import create_app

_TOKEN = "horus-os-vercel-token-value-that-must-never-leak"


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(data_dir=tmp_path))


def _fake_response(payload: dict) -> object:
    """Build an object that mimics the context-manager urlopen returns."""
    body = json.dumps(payload).encode("utf-8")

    class _Resp:
        status = 200

        def read(self) -> bytes:
            return body

        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *args: object) -> bool:
            return False

    return _Resp()


def test_status_not_configured_is_graceful(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Token unset -> 200, configured=false, null fields, no traceback (D-06)."""
    monkeypatch.delenv("HORUS_OS_VERCEL_TOKEN", raising=False)
    response = _client(tmp_path).get("/api/integrations/vercel/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "configured": False,
        "state": None,
        "url": None,
        "created_at": None,
        "error": None,
    }


def test_status_configured_returns_derived_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Token set + mocked deployment -> derived status, token absent from body."""
    monkeypatch.setenv("HORUS_OS_VERCEL_TOKEN", _TOKEN)
    deployment = {
        "deployments": [
            {
                "state": "READY",
                "url": "horus-os-demo.vercel.app",
                "createdAt": 1717315200000,
            }
        ]
    }

    def _fake_urlopen(req: object, timeout: int = 10) -> object:
        return _fake_response(deployment)

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)

    response = _client(tmp_path).get("/api/integrations/vercel/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is True
    assert payload["state"] == "READY"
    assert payload["url"] == "horus-os-demo.vercel.app"
    assert payload["created_at"] == "1717315200000"
    assert payload["error"] is None
    assert _TOKEN not in response.text


def test_status_uses_exception_type_name_not_str(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mocked failure -> error is the exception class name; token never leaks (D-05)."""
    monkeypatch.setenv("HORUS_OS_VERCEL_TOKEN", _TOKEN)

    def _raising_urlopen(req: object, timeout: int = 10) -> object:
        # str(exc) of a URLError can echo the request repr (incl. the
        # Authorization header). The handler must surface only the class name.
        raise urllib.error.URLError(f"refused while sending {_TOKEN}")

    monkeypatch.setattr("urllib.request.urlopen", _raising_urlopen)

    response = _client(tmp_path).get("/api/integrations/vercel/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is True
    assert payload["error"] == "URLError"
    assert payload["state"] is None
    assert payload["url"] is None
    assert payload["created_at"] is None
    assert _TOKEN not in response.text


def test_status_response_forbids_extra_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The response body never widens beyond the five safe fields (D-05)."""
    monkeypatch.setenv("HORUS_OS_VERCEL_TOKEN", _TOKEN)
    empty = {"deployments": []}

    def _fake_urlopen(req: object, timeout: int = 10) -> object:
        return _fake_response(empty)

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)

    response = _client(tmp_path).get("/api/integrations/vercel/status")
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"configured", "state", "url", "created_at", "error"}
    assert _TOKEN not in response.text
