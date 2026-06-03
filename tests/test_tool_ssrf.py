"""TEST-35: SSRF blocklist refusal proof for the web access path (WEB-03).

The guard must refuse loopback, every private range, link-local, and the
169.254.169.254 cloud metadata address before any socket is opened, and must
re-check the resolved IP on every redirect hop. DNS is fully stubbed via the
injectable `resolver` parameter; the suite makes zero real network calls. As a
backstop, the real socket.getaddrinfo is patched to raise if anything reaches
it unexpectedly.
"""

from __future__ import annotations

import socket
import tomllib
from pathlib import Path

import pytest

from horus_os.tools import _ssrf
from horus_os.tools._ssrf import BlockedURLError, guard_url, is_blocked_ip
from horus_os.tools.web_search import web_search_tool


def _resolver_returning(*ips: str):
    """Return a fake socket.getaddrinfo that answers with the given IPs.

    Each call answers for the family it is asked about (AF_INET for IPv4-looking
    strings, AF_INET6 for IPv6) so guard_url's two-family probe gets the address
    once. Families that have no matching IP raise gaierror like the real
    resolver would.
    """

    def fake(host, port, family, *args, **kwargs):
        matches = []
        for ip in ips:
            is_v6 = ":" in ip
            if family == socket.AF_INET6 and is_v6:
                matches.append((family, None, None, "", (ip, 0, 0, 0)))
            elif family == socket.AF_INET and not is_v6:
                matches.append((family, None, None, "", (ip, 0)))
        if not matches:
            raise socket.gaierror("no records for family")
        return matches

    return fake


@pytest.fixture(autouse=True)
def _no_real_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail loudly if any code path reaches the real DNS resolver."""

    def explode(*args, **kwargs):
        raise AssertionError("real socket.getaddrinfo was called; DNS must be stubbed")

    monkeypatch.setattr(socket, "getaddrinfo", explode)


def test_localhost_is_refused() -> None:
    with pytest.raises(BlockedURLError):
        guard_url("http://localhost/api/traces", resolver=_resolver_returning("127.0.0.1"))


def test_cloud_metadata_169_254_169_254_is_refused() -> None:
    # WEB-03: the literal cloud metadata endpoint must be refused.
    with pytest.raises(BlockedURLError):
        guard_url(
            "http://169.254.169.254/latest/meta-data/",
            resolver=_resolver_returning("169.254.169.254"),
        )


@pytest.mark.parametrize(
    "ip",
    ["10.0.0.1", "172.16.0.1", "192.168.0.1", "127.0.0.1", "169.254.0.1", "0.0.0.0"],
)
def test_private_and_special_ranges_are_refused(ip: str) -> None:
    with pytest.raises(BlockedURLError):
        guard_url("http://internal.example/", resolver=_resolver_returning(ip))


def test_ipv6_loopback_is_refused() -> None:
    with pytest.raises(BlockedURLError):
        guard_url("http://ipv6host/", resolver=_resolver_returning("::1"))


@pytest.mark.parametrize("url", ["ftp://example.com/x", "file:///etc/passwd", "data:text/plain,hi"])
def test_non_http_schemes_are_refused(url: str) -> None:
    with pytest.raises(BlockedURLError):
        guard_url(url, resolver=_resolver_returning("93.184.216.34"))


def test_empty_hostname_is_refused() -> None:
    with pytest.raises(BlockedURLError):
        guard_url("http:///no-host", resolver=_resolver_returning("93.184.216.34"))


def test_public_host_passes_and_returns_resolved_ips() -> None:
    resolved = guard_url("http://example.com/", resolver=_resolver_returning("93.184.216.34"))
    assert resolved == ["93.184.216.34"]


def test_dns_rebinding_any_blocked_record_refuses() -> None:
    # A host with one public and one private A record must be refused (T-72-04).
    with pytest.raises(BlockedURLError):
        guard_url(
            "http://multi.example/",
            resolver=_resolver_returning("93.184.216.34", "10.0.0.5"),
        )


def test_is_blocked_ip_classifies_ranges() -> None:
    assert is_blocked_ip("127.0.0.1") is True
    assert is_blocked_ip("169.254.169.254") is True
    assert is_blocked_ip("10.1.2.3") is True
    assert is_blocked_ip("::1") is True
    assert is_blocked_ip("0.0.0.0") is True
    assert is_blocked_ip("not-an-ip") is True
    assert is_blocked_ip("93.184.216.34") is False


class _FakeResponse:
    def __init__(self, *, status_code: int = 200, headers=None, url: str = "", json_body=None):
        self.status_code = status_code
        self.headers = headers or {}
        self.url = httpx_url(url)
        self._json = json_body or {}

    @property
    def is_redirect(self) -> bool:
        return 300 <= self.status_code < 400

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise AssertionError(f"unexpected status {self.status_code}")

    def json(self):
        return self._json


def httpx_url(value: str):
    import httpx

    return httpx.URL(value)


def test_redirect_target_loopback_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """Drive web_search with a stubbed httpx that 30x-redirects to loopback.

    The first host (searxng.example) is public, but its redirect Location points
    at a loopback address. guard_url must be re-invoked on the redirect target
    and refuse it (redirect-recheck, WEB-03). We patch guard_url to a wrapper
    that records each call and uses a stubbed resolver, proving it is invoked on
    BOTH the initial and the redirect URL.
    """
    import httpx

    guarded_urls: list[str] = []

    real_guard = _ssrf.guard_url

    def recording_guard(url: str, resolver=None):
        guarded_urls.append(url)
        host = httpx.URL(url).host
        if host == "searxng.example":
            return real_guard(url, resolver=_resolver_returning("93.184.216.34"))
        # The redirect target resolves to loopback and must be refused.
        return real_guard(url, resolver=_resolver_returning("127.0.0.1"))

    monkeypatch.setattr(_ssrf, "guard_url", recording_guard)

    class _FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get(self, url, follow_redirects=False, **kwargs):
            if "searxng.example" in url:
                return _FakeResponse(
                    status_code=302,
                    headers={"location": "http://127.0.0.1:8765/api/traces"},
                    url=url,
                )
            return _FakeResponse(status_code=200, url=url, json_body={"results": []})

    monkeypatch.setattr(httpx, "Client", lambda *a, **k: _FakeClient())

    tool = web_search_tool("searxng", base_url="http://searxng.example")
    assert tool.handler is not None
    with pytest.raises(BlockedURLError):
        tool.handler(query="hello")
    # guard_url was invoked on the initial URL AND on the loopback redirect.
    assert any("searxng.example" in u for u in guarded_urls)
    assert any("127.0.0.1" in u for u in guarded_urls)


# ---------------------------------------------------------------------------
# pyproject optional-dependencies assertion (TEST-35 companion): the [web] and
# [pdf] extras must exist so web search and PDF reading stay optional.
# ---------------------------------------------------------------------------


def test_pyproject_has_web_and_pdf_extras() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text())
    extras = data["project"]["optional-dependencies"]
    assert "web" in extras, "missing [web] extra"
    assert "pdf" in extras, "missing [pdf] extra"
    assert any("httpx" in dep for dep in extras["web"]), "[web] extra must list httpx"
    assert any("pypdf" in dep for dep in extras["pdf"]), "[pdf] extra must list pypdf"
    # Both must also appear in the aggregate [all] extra.
    all_deps = extras["all"]
    assert any("httpx" in dep for dep in all_deps), "[all] extra must list httpx"
    assert any("pypdf" in dep for dep in all_deps), "[all] extra must list pypdf"
