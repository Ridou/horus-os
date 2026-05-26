"""Tests for the Phase 36 /agents tab cost/latency extension.

Phase 35 backend extension added five new fields to /api/agents
(total_runs, total_cost_usd, latency_p50_ms, latency_p95_ms,
uncosted_runs). This task is the frontend half that surfaces them.

Pitfall 11 contract: pre-v0.4 trace rows where total_cost_usd is null
render the em-dash with hover "no cost data captured before v0.4"
across the cost and latency cells. An explanatory tile above the
table shows "N runs from before v0.4 (no cost data)" so the missing
dollars are explained, not hidden.

v0.3 backward-compat: the original 5 columns (name, default_model,
allowed_tools, last_activity_at, system_prompt) all stay; the new
columns insert AFTER name and BEFORE default_model so cost/latency
sit visually adjacent to the agent identity.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from horus_os import create_app


def test_agents_tab_new_column_headers(tmp_path: Path) -> None:
    """Four new column headers (cost, p50 ms, p95 ms, uncosted) are rendered."""
    body = TestClient(create_app(data_dir=tmp_path)).get("/").text
    assert ">cost</th>" in body
    assert ">p50 ms</th>" in body
    assert ">p95 ms</th>" in body
    assert ">uncosted</th>" in body


def test_agents_tab_pitfall_11_hover_copy(tmp_path: Path) -> None:
    """Verbatim hover string for pre-v0.4 NULL cells."""
    body = TestClient(create_app(data_dir=tmp_path)).get("/").text
    assert "no cost data captured before v0.4" in body


def test_agents_tab_uncosted_tile_present(tmp_path: Path) -> None:
    """Tile container exists so loadAgents can show/hide it."""
    body = TestClient(create_app(data_dir=tmp_path)).get("/").text
    assert 'id="agents-uncosted-tile"' in body
    # Tile copy template appears in the JS (interpolated with N at render).
    assert "runs from before v0.4" in body


def test_agents_tab_null_render_branch_present(tmp_path: Path) -> None:
    """The NULL render branch is the JS guard that switches to em-dash."""
    body = TestClient(create_app(data_dir=tmp_path)).get("/").text
    assert "total_cost_usd === null" in body


def test_agents_tab_uncosted_runs_sum_logic(tmp_path: Path) -> None:
    """uncosted_runs is referenced in row render AND in the tile sum.

    grep count >= 2: per-row render + reduce() across rows for the
    tile visibility decision.
    """
    body = TestClient(create_app(data_dir=tmp_path)).get("/").text
    assert body.count("uncosted_runs") >= 2
    assert "reduce" in body


def test_agents_tab_v03_columns_preserved(tmp_path: Path) -> None:
    """All 5 v0.3 column headers stay present (backward-compat).

    The new columns slot in between name and default_model; they do
    not displace any of the original columns.
    """
    body = TestClient(create_app(data_dir=tmp_path)).get("/").text
    assert ">name</th>" in body
    assert ">default_model</th>" in body
    assert ">allowed_tools</th>" in body
    assert ">last_activity_at</th>" in body
    assert ">system_prompt</th>" in body
