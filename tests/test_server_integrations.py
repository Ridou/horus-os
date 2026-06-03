"""Tests for the GET /api/integrations route.

Boots a FastAPI TestClient against create_app. Tests assert the response
shape matches frontend/lib/types.ts::IntegrationsResponse, that status
values are only "missing" or "configured-unverified" in Phase 61, and
that no env var value is ever echoed in the response body.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from horus_os import create_app


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(data_dir=tmp_path))


def test_integrations_returns_10_items(tmp_path: Path) -> None:
    """GET /api/integrations returns the correct envelope shape and 10 connectors."""
    response = _client(tmp_path).get("/api/integrations")
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"integrations", "demo_mode"}
    assert len(payload["integrations"]) == 10

    first = payload["integrations"][0]
    assert set(first) == {
        "id",
        "name",
        "category",
        "description",
        "status",
        "env_var",
        "required_vars",
        "credential_portal_url",
    }


def test_no_secret_echo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The response body must never contain the actual value of an env var."""
    secret = "sk-ant-supersecret-value-that-must-not-appear"
    monkeypatch.setenv("ANTHROPIC_API_KEY", secret)
    response = _client(tmp_path).get("/api/integrations")
    assert response.status_code == 200
    body = response.text
    assert secret not in body


def test_status_values_are_missing_or_configured_unverified(tmp_path: Path) -> None:
    """Phase 61 never emits 'verified' or 'error' - those are Phase 62 states."""
    response = _client(tmp_path).get("/api/integrations")
    assert response.status_code == 200
    valid_states = {"missing", "configured-unverified"}
    for item in response.json()["integrations"]:
        assert item["status"] in valid_states, f"{item['id']} has invalid status {item['status']!r}"


def test_configured_unverified_when_env_var_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Setting the primary env var for an integration produces 'configured-unverified'."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-value")
    response = _client(tmp_path).get("/api/integrations")
    assert response.status_code == 200
    items = {i["id"]: i["status"] for i in response.json()["integrations"]}
    assert items["anthropic"] == "configured-unverified"
    assert items["gemini"] == "missing"


def test_discord_required_vars_include_guild_and_admin_role(tmp_path: Path) -> None:
    """Discord registry entry must list all three required env vars after Phase 64."""
    response = _client(tmp_path).get("/api/integrations")
    assert response.status_code == 200
    items = {i["id"]: i for i in response.json()["integrations"]}
    discord_entry = items["discord"]
    required = discord_entry["required_vars"]
    assert "HORUS_OS_DISCORD_TOKEN" in required
    assert "HORUS_OS_DISCORD_GUILD_ID" in required
    assert "HORUS_OS_DISCORD_ADMIN_ROLE_ID" in required
