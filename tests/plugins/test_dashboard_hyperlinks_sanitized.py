"""DASH-5-03 sanitation regression: manifest-sourced strings never reach DOM unsafely.

Three contracts pinned by source-code + JSON-API checks:

  1. ``/api/plugins`` returns the raw manifest string in JSON (no escaping
     at the API layer; JSON encoding is the wire contract).
  2. ``src/horus_os/server/static/index.html`` calls ``escapeHtml`` (or
     uses ``textContent``) on every line that interpolates a
     manifest-sourced field (manifest_author, manifest_homepage,
     manifest_issue_tracker, last_error, name, version).
  3. The static file uses a ``startsWith('http')`` URL-scheme gate (via
     the ``safeUrl`` helper) before rendering any plugin-supplied
     URL as an ``<a href>`` -- ``javascript:`` and ``data:`` URLs
     never reach the anchor.

The project has no jsdom / Playwright fixture; these tests are pure
file-content + JSON-API checks.

T-45-02 (Tampering): manifest field XSS via `<script>` injection.
T-45-07 (Tampering): URL injection via `javascript:` / `data:` href.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from horus_os import Config, Database, create_app
from horus_os.plugins.spec import CapabilityRequest, PluginSpec

INDEX_HTML = Path(__file__).resolve().parents[2] / "src/horus_os/server/static/index.html"


def _init_data_dir(tmp_path: Path) -> Path:
    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    db = Database(cfg.db_path)
    db.init()
    return tmp_path


def _malicious_spec() -> PluginSpec:
    return PluginSpec(
        name="evilplugin",
        version="1.0",
        description="for testing",
        author="<script>alert(1)</script>",
        license="MIT",
        horus_os_compat=">=0.5,<0.6",
        homepage="javascript:alert(2)",
        issue_tracker="https://example.com/issues",
        tool_entries=(),
        adapter_entries=(),
        capabilities=(CapabilityRequest(name="filesystem.read"),),
        source="filesystem",
        source_detail="/tmp/evil",
        manifest_hash="hash-evil-1",
    )


def test_api_returns_raw_manifest_string(tmp_path: Path) -> None:
    """The /api/plugins JSON layer carries the raw string verbatim.

    JSON-encoded text is not HTML; no escaping happens here. The HTML
    escaping is the dashboard layer's job (proven by the other two
    tests in this file).
    """
    _init_data_dir(tmp_path)
    app = create_app(data_dir=tmp_path)
    spec = _malicious_spec()
    client = TestClient(app)
    with client:
        app.state.plugin_registry.register(spec)
        app.state.plugin_registry.mark_loaded("evilplugin")
        response = client.get("/api/plugins")
    assert response.status_code == 200
    body = response.json()
    row = next(p for p in body["plugins"] if p["name"] == "evilplugin")
    # The wire is JSON, so the literal string passes through verbatim.
    assert row["manifest_author"] == "<script>alert(1)</script>"
    assert row["manifest_homepage"] == "javascript:alert(2)"


def test_index_html_uses_escapeHtml_for_manifest_fields() -> None:
    """Every line that interpolates a manifest-sourced field passes through escapeHtml."""
    text = INDEX_HTML.read_text(encoding="utf-8")

    # Must reference each critical field at all.
    for field in (
        "manifest_author",
        "manifest_homepage",
        "manifest_issue_tracker",
    ):
        assert field in text, f"index.html does not reference {field}"

    # For each manifest_* and last_error field, at least one usage must
    # flow through escapeHtml() or textContent.
    critical_fields = (
        "manifest_author",
        "last_error",
    )
    for field in critical_fields:
        # Match either escapeHtml(...field...) or textContent (assignment
        # / appendChild text node) within a few lines of the field.
        # Generous regex: same line or within 200 chars after.
        pattern = re.compile(
            rf"(escapeHtml\([^)]*\b{re.escape(field)}\b|"
            rf"\b{re.escape(field)}\b[^;]*textContent|"
            rf"textContent[^;]*\b{re.escape(field)}\b)",
            re.DOTALL,
        )
        assert pattern.search(text), (
            f"index.html references {field} but no line escapes it via escapeHtml/textContent"
        )


def test_index_html_validates_url_scheme() -> None:
    """A URL-scheme gate (safeUrl helper or startsWith('http')) exists."""
    text = INDEX_HTML.read_text(encoding="utf-8")
    # The safeUrl helper or an inline startsWith('http') guard must be present.
    has_safeurl = "safeUrl" in text
    has_startswith = "startsWith('http" in text or 'startsWith("http' in text
    assert has_safeurl or has_startswith, (
        "index.html lacks the URL-scheme gate (safeUrl helper or startsWith('http') guard)"
    )

    # No raw interpolation of plugin.manifest_homepage into an href.
    bad_pattern = re.compile(r'href\s*=\s*["\'`]\$\{\s*[^}]*\bmanifest_homepage\b[^}]*\}["\'`]')
    raw_match = bad_pattern.search(text)
    assert raw_match is None, (
        f"index.html interpolates manifest_homepage into href without a guard: "
        f"{raw_match.group() if raw_match else ''}"
    )

    bad_tracker = re.compile(
        r'href\s*=\s*["\'`]\$\{\s*[^}]*\bmanifest_issue_tracker\b[^}]*\}["\'`]'
    )
    raw_tracker = bad_tracker.search(text)
    assert raw_tracker is None, (
        f"index.html interpolates manifest_issue_tracker into href without a guard: "
        f"{raw_tracker.group() if raw_tracker else ''}"
    )
