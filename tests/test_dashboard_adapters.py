"""Tests for the dashboard Adapters tab surface.

These tests assert that the static HTML body contains the markers
the Phase 27 frontend requires: the tab button, the section, the
JS function names that drive load and toggle, the polling
reference, and the API paths. We deliberately do not execute the
JS; this is a build-gate test that fails when the frontend drops
a documented marker.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from horus_os import create_app


def test_dashboard_html_contains_adapters_tab_marker(tmp_path: Path) -> None:
    client = TestClient(create_app(data_dir=tmp_path))
    response = client.get("/")
    assert response.status_code == 200
    body = response.text

    # Tab nav marker
    assert 'data-tab="adapters"' in body
    # Section markers
    assert 'id="adapters"' in body
    assert 'id="adapters-body"' in body
    # Refresh button id
    assert 'id="refresh-adapters"' in body

    # JS function names
    assert "loadAdapters" in body
    assert "toggleAdapter" in body

    # Polling: variable name and 5 second interval
    assert "adaptersPoll" in body
    assert "5000" in body

    # API endpoints the tab calls
    assert "/api/adapters" in body

    # Status pill class for the stopped state (added in Phase 27)
    assert ".pill.muted" in body


def test_dashboard_existing_tabs_still_present(tmp_path: Path) -> None:
    """The Adapters tab must not displace v0.2 tabs."""
    client = TestClient(create_app(data_dir=tmp_path))
    body = client.get("/").text
    assert 'data-tab="chat"' in body
    assert 'data-tab="traces"' in body
    assert 'data-tab="agents"' in body
    assert 'data-tab="writes"' in body
    # Existing JS surface stays
    assert "loadTraces" in body
    assert "loadAgents" in body
    assert "loadWrites" in body
