"""Tests for the dashboard static file mount."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from horus_os import create_app


def test_root_returns_dashboard_html(tmp_path: Path) -> None:
    client = TestClient(create_app(data_dir=tmp_path))
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    body = response.text
    assert "horus-os" in body
    assert "/api/chat" in body
    assert "/api/traces" in body
    assert "/api/writes" in body
    # Phase 16 markers: SSE stream endpoint, agents tab, agents endpoint,
    # delegate-tree children fetch. We assert markup-level presence so the
    # build gate fails if the frontend drops a documented endpoint.
    assert "/api/chat/stream" in body
    assert "/api/agents" in body
    assert 'data-tab="agents"' in body
    assert "/children" in body
