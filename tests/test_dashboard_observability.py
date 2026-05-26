"""Tests for the Phase 36 Observability dashboard tab.

HTML-marker tests that assert the static index.html body contains the
markers the Phase 36 frontend requires: the 6th tab button, the
section, the window selector, the three panel containers, the new JS
function names, the polling reference, the API paths, the Pitfall 10
small-sample render guard, and the v0.3 regression guards.

We deliberately do not execute the JS; this is a build-gate test that
fails when the frontend drops a documented marker.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from horus_os import create_app


def test_observability_tab_nav_and_section_markers(tmp_path: Path) -> None:
    """The 6th tab nav button and section are present."""
    client = TestClient(create_app(data_dir=tmp_path))
    response = client.get("/")
    assert response.status_code == 200
    body = response.text
    # Tab nav marker
    assert 'data-tab="observability"' in body
    # Section marker
    assert 'id="observability"' in body


def test_observability_window_selector_markers(tmp_path: Path) -> None:
    """Window selector with 24h/7d/30d options, 7d selected by default."""
    body = TestClient(create_app(data_dir=tmp_path)).get("/").text
    assert 'id="obs-window"' in body
    assert 'value="24h"' in body
    assert 'value="7d"' in body
    assert 'value="30d"' in body
    # 7d is the default-selected option.
    assert 'value="7d" selected' in body


def test_observability_three_panel_container_markers(tmp_path: Path) -> None:
    """Three panel containers (cost, latency, tools) are present."""
    body = TestClient(create_app(data_dir=tmp_path)).get("/").text
    assert 'id="obs-cost-panel"' in body
    assert 'id="obs-latency-panel"' in body
    assert 'id="obs-tools-panel"' in body


def test_observability_js_function_names_and_api_paths(tmp_path: Path) -> None:
    """JS functions, polling variable, and the three API paths are wired."""
    body = TestClient(create_app(data_dir=tmp_path)).get("/").text
    # JS function names
    assert "loadObservability" in body
    assert "renderCostPanel" in body
    assert "renderLatencyPanel" in body
    assert "renderToolsPanel" in body
    # Polling variable
    assert "observabilityPoll" in body
    # API paths
    assert "/api/observability/cost" in body
    assert "/api/observability/latency" in body
    assert "/api/observability/tools" in body


def test_observability_setTab_dispatch_and_poll_cleanup(tmp_path: Path) -> None:
    """setTab dispatches to observability and the 5s poll clears on switch."""
    body = TestClient(create_app(data_dir=tmp_path)).get("/").text
    # setTab dispatch added for the new tab.
    assert 'name === "observability"' in body
    # Poll cleanup on switch.
    assert "clearInterval(observabilityPoll)" in body
    # 5-second polling cadence (already present from Phase 27 Adapters tab;
    # this just confirms the cadence anchor is still there).
    assert "5000" in body


def test_observability_pitfall_10_small_sample_render(tmp_path: Path) -> None:
    """Pitfall 10: sample_count < 10 renders the em-dash with the hover copy.

    The hover string is pinned verbatim so future copy edits go through
    a test review. The JS render-time guard `sample_count < 10` is also
    pinned so a future refactor cannot silently drop the threshold.
    The em-dash Unicode character must appear in the JS body so the
    below-threshold cells render honestly.
    """
    body = TestClient(create_app(data_dir=tmp_path)).get("/").text
    assert "need at least 10 runs for percentile" in body
    assert "sample_count < 10" in body
    # Em-dash character must be in the rendered HTML/JS.
    assert "—" in body


def test_observability_v03_regression_guard(tmp_path: Path) -> None:
    """All five v0.3 tabs and their JS load functions stay present.

    The Observability tab is the 6th tab; it must not displace any of
    Chat / Traces / Agents / Writes / Adapters. The Phase 27 Adapters
    polling contract (adaptersPoll + clearInterval) also stays.
    """
    body = TestClient(create_app(data_dir=tmp_path)).get("/").text
    # Five existing tab nav buttons.
    assert 'data-tab="chat"' in body
    assert 'data-tab="traces"' in body
    assert 'data-tab="agents"' in body
    assert 'data-tab="writes"' in body
    assert 'data-tab="adapters"' in body
    # Existing JS loaders.
    assert "loadAdapters" in body
    assert "loadAgents" in body
    assert "loadTraces" in body
    assert "loadWrites" in body
    # Phase 27 polling contract.
    assert "adaptersPoll" in body
    assert "clearInterval(adaptersPoll)" in body
