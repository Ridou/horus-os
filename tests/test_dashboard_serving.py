"""Serving contract: bundled Next.js export vs the legacy HTML fallback.

The v0.7 dashboard ships as a static export bundled into the wheel at
``server/dashboard_dist/``. When present it is mounted at ``/`` AFTER every
``/api`` route, so the JSON API always takes precedence. When absent (for
example an editable install with no Node build) the server falls back to the
legacy single-page HTML dashboard.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from horus_os.server.api import create_app


def _make_export(tmp_path: Path) -> Path:
    dist = tmp_path / "dashboard_dist"
    (dist / "team").mkdir(parents=True)
    (dist / "_next" / "static").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>home</title>BUNDLED_HOME")
    (dist / "team" / "index.html").write_text("<!doctype html><title>team</title>BUNDLED_TEAM")
    (dist / "_next" / "static" / "app.js").write_text("console.log('ok')")
    return dist


def test_serves_bundled_dashboard_when_present(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    dist = _make_export(tmp_path)
    client = TestClient(create_app(data_dir=data_dir, dashboard_dist=dist))

    root = client.get("/")
    assert root.status_code == 200
    assert "BUNDLED_HOME" in root.text

    team = client.get("/team/")
    assert team.status_code == 200
    assert "BUNDLED_TEAM" in team.text

    asset = client.get("/_next/static/app.js")
    assert asset.status_code == 200

    # The /api surface must still win over the root static mount.
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"


def test_falls_back_to_legacy_html_when_export_absent(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    absent = tmp_path / "no_export"  # no index.html inside

    client = TestClient(create_app(data_dir=data_dir, dashboard_dist=absent))

    root = client.get("/")
    assert root.status_code == 200
    assert "<" in root.text  # the legacy dashboard is an HTML document

    health = client.get("/api/health")
    assert health.status_code == 200
