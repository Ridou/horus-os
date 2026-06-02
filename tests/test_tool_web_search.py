"""Tests for the BYO web_search tool (WEB-01).

All httpx calls are stubbed; the suite makes zero real network calls. The
registry-absence proof (no provider configured means no web_search tool) lives
here too.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from horus_os.config import Config
from horus_os.memory import NotesStore
from horus_os.server.api import _build_default_registry
from horus_os.tools import _ssrf
from horus_os.tools.web_search import _looks_like_secret, web_search_tool


@pytest.fixture(autouse=True)
def _guard_passes_public(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub guard_url to a no-op that returns a public IP so tests never hit DNS.

    Individual SSRF refusal behavior is proven in test_tool_ssrf.py; here we
    isolate the provider response mapping from the guard.
    """
    monkeypatch.setattr(_ssrf, "guard_url", lambda url, resolver=None: ["93.184.216.34"])


class _FakeResponse:
    def __init__(self, json_body):
        self._json = json_body
        self.status_code = 200
        self.headers: dict[str, str] = {}

    @property
    def is_redirect(self) -> bool:
        return False

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._json


def _install_fake_httpx(monkeypatch: pytest.MonkeyPatch, *, get_json=None, post_json=None):
    import httpx

    captured: dict = {"get": [], "post": []}

    class _FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get(self, url, follow_redirects=False, **kwargs):
            captured["get"].append({"url": url, **kwargs})
            return _FakeResponse(get_json or {})

        def post(self, url, follow_redirects=False, **kwargs):
            captured["post"].append({"url": url, **kwargs})
            return _FakeResponse(post_json or {})

    monkeypatch.setattr(httpx, "Client", lambda *a, **k: _FakeClient())
    return captured


def test_web_search_tool_metadata() -> None:
    tool = web_search_tool("searxng", base_url="http://searxng.local")
    assert tool.name == "web_search"
    assert tool.parameters["required"] == ["query"]
    assert "query" in tool.parameters["properties"]


def test_searxng_maps_results(monkeypatch: pytest.MonkeyPatch) -> None:
    body = {
        "results": [
            {"title": "T1", "url": "https://a.example/1", "content": "snippet one"},
            {"title": "T2", "url": "https://a.example/2", "content": "snippet two"},
        ]
    }
    captured = _install_fake_httpx(monkeypatch, get_json=body)
    tool = web_search_tool("searxng", base_url="http://searxng.local")
    assert tool.handler is not None
    results = tool.handler(query="python testing")
    assert results == [
        {"title": "T1", "url": "https://a.example/1", "snippet": "snippet one"},
        {"title": "T2", "url": "https://a.example/2", "snippet": "snippet two"},
    ]
    # One GET to the /search path with q + format=json.
    assert len(captured["get"]) == 1
    call = captured["get"][0]
    assert call["url"].endswith("/search")
    assert call["params"] == {"q": "python testing", "format": "json"}


def test_brave_maps_results_and_sends_token(monkeypatch: pytest.MonkeyPatch) -> None:
    body = {
        "web": {
            "results": [
                {"title": "B1", "url": "https://b.example/1", "description": "desc one"},
            ]
        }
    }
    captured = _install_fake_httpx(monkeypatch, get_json=body)
    tool = web_search_tool("brave", api_key="secret-token")
    assert tool.handler is not None
    results = tool.handler(query="rust async")
    assert results == [
        {"title": "B1", "url": "https://b.example/1", "snippet": "desc one"},
    ]
    headers = captured["get"][0]["headers"]
    assert headers["X-Subscription-Token"] == "secret-token"


def test_tavily_posts_and_maps_results(monkeypatch: pytest.MonkeyPatch) -> None:
    body = {
        "results": [
            {"title": "V1", "url": "https://v.example/1", "content": "tav snippet"},
        ]
    }
    captured = _install_fake_httpx(monkeypatch, post_json=body)
    tool = web_search_tool("tavily", api_key="tav-key")
    assert tool.handler is not None
    results = tool.handler(query="vector search")
    assert results == [
        {"title": "V1", "url": "https://v.example/1", "snippet": "tav snippet"},
    ]
    post = captured["post"][0]
    assert post["json"]["query"] == "vector search"
    assert post["json"]["api_key"] == "tav-key"


def test_searxng_requires_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_httpx(monkeypatch, get_json={"results": []})
    tool = web_search_tool("searxng")
    assert tool.handler is not None
    with pytest.raises(RuntimeError, match="requires a base_url"):
        tool.handler(query="x")


def test_unknown_provider_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_httpx(monkeypatch, get_json={"results": []})
    tool = web_search_tool("does-not-exist")
    assert tool.handler is not None
    with pytest.raises(RuntimeError, match="unknown provider"):
        tool.handler(query="x")


def test_guarded_base_url_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    # A base_url resolving to a private IP must be refused before any request.
    _install_fake_httpx(monkeypatch, get_json={"results": []})
    monkeypatch.setattr(
        _ssrf,
        "guard_url",
        lambda url, resolver=None: (_ for _ in ()).throw(_ssrf.BlockedURLError("blocked")),
    )
    tool = web_search_tool("searxng", base_url="http://10.0.0.5:8080")
    assert tool.handler is not None
    with pytest.raises(_ssrf.BlockedURLError):
        tool.handler(query="x")


def test_looks_like_secret_detects_patterns() -> None:
    assert _looks_like_secret("sk-ABCDEFGHIJKLMNOPQRST")
    assert _looks_like_secret("ghp_ABCDEFGHIJKLMNOPQRST")
    assert _looks_like_secret("deadbeef" * 6)  # long hex run
    assert not _looks_like_secret("how do I write a pytest fixture")


def test_secret_query_warns_but_does_not_block(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    captured = _install_fake_httpx(monkeypatch, get_json={"results": []})
    tool = web_search_tool("searxng", base_url="http://searxng.local")
    assert tool.handler is not None
    with caplog.at_level(logging.WARNING):
        results = tool.handler(query="sk-ABCDEFGHIJKLMNOPQRSTUV please summarize")
    assert results == []
    assert len(captured["get"]) == 1  # the search still ran
    assert any("secret-shaped" in rec.message for rec in caplog.records)


# ---------------------------------------------------------------------------
# WEB-01 registry-absence proof.
# ---------------------------------------------------------------------------


def _notes_store(tmp_path: Path) -> NotesStore:
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()
    return NotesStore(notes_dir)


def test_registry_absent_without_provider(tmp_path: Path) -> None:
    cfg = Config.with_defaults(tmp_path)
    assert cfg.web_search_provider is None
    registry = _build_default_registry(cfg, _notes_store(tmp_path))
    assert "web_search" not in registry
    assert registry.get("web_search") is None


def test_registry_present_with_provider(tmp_path: Path) -> None:
    cfg = Config.with_defaults(tmp_path)
    cfg.web_search_provider = "searxng"
    cfg.web_search_base_url = "http://searxng.local"
    registry = _build_default_registry(cfg, _notes_store(tmp_path))
    assert "web_search" in registry
    tool = registry.get("web_search")
    assert tool is not None
    assert tool.name == "web_search"
