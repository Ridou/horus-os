"""Markup-presence tests for the new /plugins dashboard tab + by-plugin obs panel.

The dashboard is a single static HTML file with inline JS; no React, no
build step, no Playwright fixture. These tests boot a TestClient, fetch
``/``, and assert the new markup is present. The DOM behavior itself is
covered by ``test_dashboard_hyperlinks_sanitized.py`` (source-code
regression).
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from horus_os import Config, Database, create_app


def _init_data_dir(tmp_path: Path) -> Path:
    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    db = Database(cfg.db_path)
    db.init()
    return tmp_path


def test_plugins_tab_renders(tmp_path: Path) -> None:
    """GET / returns HTML with the new Plugins nav button + tab section."""
    _init_data_dir(tmp_path)
    client = TestClient(create_app(data_dir=tmp_path))
    with client:
        response = client.get("/")
    assert response.status_code == 200
    body = response.text
    # Nav button.
    assert 'data-tab="plugins"' in body
    # Tab section.
    assert 'id="plugins"' in body
    # Refresh handler.
    assert "loadPlugins" in body
    # Render helper present.
    assert "renderPluginTile" in body


def test_observability_includes_by_plugin_panel(tmp_path: Path) -> None:
    """The Observability tab carries the fourth obs-plugins-panel."""
    _init_data_dir(tmp_path)
    client = TestClient(create_app(data_dir=tmp_path))
    with client:
        response = client.get("/")
    body = response.text
    assert 'id="obs-plugins-panel"' in body
    assert 'id="obs-plugins-body"' in body
