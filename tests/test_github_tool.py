"""Tests for the optional read-only GitHub agent tool (GH-02).

The tool is a `Tool` factory (`make_github_read_tool`) that reads
repository data via the GitHub REST API. Its HTTP client is the
stdlib `urllib.request`, lazy-imported inside the handler so the
module imports cleanly with no extra installed. The server-side
`GITHUB_TOKEN` is read from `os.environ`; unauthenticated public
reads work when it is absent. On any failure the handler returns
`{"error": type(exc).__name__}` and never echoes the token.
"""

from __future__ import annotations

import io
import json
import pathlib
from contextlib import contextmanager
from typing import Any
from unittest import mock

import pytest

from horus_os.tools.github_tool import make_github_read_tool


@contextmanager
def _fake_urlopen(payload: dict[str, Any]):
    """Patch urllib.request.urlopen to return a context manager whose
    .read() yields the JSON-encoded payload. Returns the mock so callers
    can inspect the Request that was passed in."""
    body = json.dumps(payload).encode("utf-8")

    class _Resp(io.BytesIO):
        status = 200

        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *exc: object) -> None:
            self.close()

    def _urlopen(req: Any, timeout: float | None = None) -> _Resp:
        _urlopen.last_request = req  # type: ignore[attr-defined]
        _urlopen.last_timeout = timeout  # type: ignore[attr-defined]
        return _Resp(body)

    with mock.patch("urllib.request.urlopen", _urlopen):
        yield _urlopen


def test_handler_returns_repo_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    tool = make_github_read_tool()
    payload = {"full_name": "octocat/Hello-World", "default_branch": "main"}
    with _fake_urlopen(payload) as urlopen:
        result = tool.handler(owner="octocat", repo="Hello-World")
    assert result == payload
    # Repo-root metadata URL is used when no path is given.
    assert urlopen.last_request.full_url == "https://api.github.com/repos/octocat/Hello-World"


def test_handler_returns_contents_when_path_given(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    tool = make_github_read_tool()
    payload = {"name": "README.md", "type": "file", "encoding": "base64"}
    with _fake_urlopen(payload) as urlopen:
        result = tool.handler(owner="octocat", repo="Hello-World", path="README.md")
    assert result == payload
    # Contents endpoint URL is selected when path is non-empty.
    assert (
        urlopen.last_request.full_url
        == "https://api.github.com/repos/octocat/Hello-World/contents/README.md"
    )


def test_no_token_public_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """With GITHUB_TOKEN unset the handler still issues the request and
    sends no Authorization header (unauthenticated public read, D-08)."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    tool = make_github_read_tool()
    with _fake_urlopen({"full_name": "octocat/Hello-World"}) as urlopen:
        result = tool.handler(owner="octocat", repo="Hello-World")
    assert result == {"full_name": "octocat/Hello-World"}
    # urllib lowercases header keys via Request.headers; no auth header present.
    header_keys = {k.lower() for k in urlopen.last_request.headers}
    assert "authorization" not in header_keys


def test_token_used_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_secretvalue123")
    tool = make_github_read_tool()
    with _fake_urlopen({"full_name": "octocat/Hello-World"}) as urlopen:
        tool.handler(owner="octocat", repo="Hello-World")
    # Authorization header is added (urllib capitalizes to "Authorization").
    assert urlopen.last_request.get_header("Authorization") == "Bearer ghp_secretvalue123"


def test_token_never_echoed_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the request raises, the handler returns only the exception
    class name and the token value never appears in the result (T-67-07)."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_secretvalue123")
    tool = make_github_read_tool()

    def _boom(req: Any, timeout: float | None = None) -> Any:
        raise RuntimeError("boom ghp_secretvalue123 leaked")

    with mock.patch("urllib.request.urlopen", _boom):
        result = tool.handler(owner="octocat", repo="Hello-World")

    assert result == {"error": "RuntimeError"}
    assert "ghp_secretvalue123" not in json.dumps(result)
    assert "boom" not in json.dumps(result)


def test_factory_name_and_lazy_import() -> None:
    """make_github_read_tool().name == 'github_read' and importing the
    module succeeds with no httpx/PyGithub installed (HTTP client import
    is inside the handler)."""
    tool = make_github_read_tool()
    assert tool.name == "github_read"
    assert tool.parameters["required"] == ["owner", "repo"]
    assert set(tool.parameters["properties"]) == {"owner", "repo", "path"}


def test_token_never_appears_in_request_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """The token lives only in the Authorization header, never the URL (WR-04 info)."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_secretvalue123")
    tool = make_github_read_tool()
    with _fake_urlopen({"full_name": "octocat/Hello-World"}) as urlopen:
        tool.handler(owner="octocat", repo="Hello-World", path="docs/README.md")
    assert "ghp_secretvalue123" not in urlopen.last_request.full_url


def test_crafted_segments_are_url_encoded_no_host_escape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Crafted owner/path values are percent-encoded so the request host stays
    api.github.com and cannot be redirected to a foreign host (WR-02)."""
    import urllib.parse

    monkeypatch.setenv("GITHUB_TOKEN", "ghp_secretvalue123")
    tool = make_github_read_tool()
    with _fake_urlopen({"x": 1}) as urlopen:
        tool.handler(owner="../../@evil.com", repo="r", path="../../etc/passwd")
    parsed = urllib.parse.urlparse(urlopen.last_request.full_url)
    # The bearer token cannot be redirected off api.github.com.
    assert parsed.netloc == "api.github.com"
    assert parsed.path.startswith("/repos/")
    # The crafted owner is encoded (slashes and @ escaped), not left literal.
    assert "/repos/..%2F..%2F" in urlopen.last_request.full_url
    assert "@evil.com/" not in urlopen.last_request.full_url


def test_http_error_surfaces_status_without_leaking_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An HTTP error returns the class name plus the numeric status (404/403/401)
    so the agent can distinguish failure modes, with no token leak (WR-04)."""
    import urllib.error

    monkeypatch.setenv("GITHUB_TOKEN", "ghp_secretvalue123")
    tool = make_github_read_tool()

    def _raise_404(req: Any, timeout: float | None = None) -> Any:
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found ghp_secretvalue123", {}, None)

    with mock.patch("urllib.request.urlopen", _raise_404):
        result = tool.handler(owner="octocat", repo="nope")

    assert result == {"error": "HTTPError", "status": 404}
    assert "ghp_secretvalue123" not in json.dumps(result)


def test_source_has_no_pygithub_reference() -> None:
    """The module source must not import PyGithub (its compiled pynacl
    transitive dep threatens the three-OS gate, D-08)."""
    import horus_os.tools.github_tool as mod

    source = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    assert "import github" not in source
    assert "from github" not in source
    assert "PyGithub" not in source
