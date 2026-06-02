"""Bring-your-own web search tool (WEB-01).

The tool is a factory mirroring `read_file_tool`: `web_search_tool(provider,
api_key, base_url)` returns a `Tool` named `web_search`. It is registered into
the agent registry ONLY when a provider is configured in `[tools.web_search]`
(server/api.py `_build_default_registry`), so a default install has no web
search tool at all (default-deny, T-72-03).

Three providers share one thin wrapper, all called over httpx (already a
transitive dependency via openai/supabase; the `[web]` extra lists it
explicitly): self-hosted SearXNG, Brave Search, and Tavily. Each provider's
response shape is normalized to a uniform list of {title, url, snippet} dicts.

Every outbound request passes its base URL through the SSRF guard
(`_ssrf.guard_url`) BEFORE the request is built and again after each redirect,
so a provider URL (or a redirect) that resolves to a loopback, private,
link-local, or cloud-metadata address is refused before a socket opens
(WEB-03). The query is checked for secret-looking patterns and a warning is
logged (never a hard block) so the user can audit what left the machine
(WA-2).
"""

from __future__ import annotations

import logging
import re

from horus_os.tools import _ssrf
from horus_os.types import Tool

_log = logging.getLogger(__name__)

# WA-2: a single GET/POST is enough for a search; bound it so a slow or hung
# provider cannot wedge the agent loop.
_REQUEST_TIMEOUT_SECONDS = 15.0
# Re-guard each redirect hop ourselves; never let the client silently follow a
# redirect into a blocked address, so we cap and walk hops explicitly.
_MAX_REDIRECTS = 5

_WEB_SEARCH_PARAMETERS: dict = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": (
                "The search query. Construct this explicitly; do not paste raw "
                "note or document content, which may contain secrets that would "
                "be sent to the external search provider."
            ),
        },
    },
    "required": ["query"],
}

# WA-2: secret-shaped patterns. Matching one only WARNS; it never blocks, so a
# legitimate query that happens to look secret-ish still runs while the user
# gets an auditable signal that a secret may have left the machine.
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9]{16,}"),
    re.compile(r"ghp_[A-Za-z0-9]{16,}"),
    re.compile(r"[0-9a-fA-F]{40,}"),
)


def _looks_like_secret(query: str) -> bool:
    """Return True when `query` matches a known secret shape (WA-2).

    The caller logs a warning on a match but never raises, so search still
    runs. This is an audit aid, not an access control.
    """
    return any(pattern.search(query) for pattern in _SECRET_PATTERNS)


def _guarded_get(client, url: str, **kwargs):
    """Issue a GET, re-running the SSRF guard on every redirect hop.

    `_ssrf.guard_url` is invoked on the initial URL and again on each redirect
    Location before that hop is followed, so a provider that 30x-redirects into
    a loopback/private/metadata address is refused mid-chain (WEB-03,
    redirect-recheck). Redirects are followed manually with follow_redirects
    left off on the client.
    """
    target = url
    for _ in range(_MAX_REDIRECTS + 1):
        _ssrf.guard_url(target)
        response = client.get(target, follow_redirects=False, **kwargs)
        if response.is_redirect and "location" in response.headers:
            target = str(response.url.join(response.headers["location"]))
            continue
        return response
    raise RuntimeError(f"web_search: too many redirects following {url!r}")


def _search_searxng(client, base_url: str, query: str) -> list[dict]:
    endpoint = base_url.rstrip("/") + "/search"
    response = _guarded_get(
        client,
        endpoint,
        params={"q": query, "format": "json"},
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    results = []
    for item in payload.get("results", []) or []:
        results.append(
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("content", ""),
            }
        )
    return results


def _search_brave(client, base_url: str, api_key: str | None, query: str) -> list[dict]:
    endpoint = (base_url or "https://api.search.brave.com/res/v1/web/search").rstrip("/")
    headers = {"Accept": "application/json"}
    if api_key:
        headers["X-Subscription-Token"] = api_key
    response = _guarded_get(
        client,
        endpoint,
        params={"q": query},
        headers=headers,
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    results = []
    web = payload.get("web", {}) or {}
    for item in web.get("results", []) or []:
        results.append(
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("description", ""),
            }
        )
    return results


def _search_tavily(client, base_url: str, api_key: str | None, query: str) -> list[dict]:
    endpoint = (base_url or "https://api.tavily.com/search").rstrip("/")
    # Tavily takes a POST; guard the endpoint URL before the request (no
    # redirect chain to walk for a POST, so guard_url is called directly).
    _ssrf.guard_url(endpoint)
    body: dict = {"query": query}
    if api_key:
        body["api_key"] = api_key
    response = client.post(
        endpoint,
        json=body,
        follow_redirects=False,
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    results = []
    for item in payload.get("results", []) or []:
        results.append(
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("content", ""),
            }
        )
    return results


def web_search_tool(
    provider: str,
    api_key: str | None = None,
    base_url: str | None = None,
) -> Tool:
    """Return a `Tool` that runs a web search against a BYO provider (WEB-01).

    `provider` is one of "searxng", "brave", or "tavily". `api_key` (read by
    the caller from HORUS_OS_WEB_SEARCH_KEY, never persisted to config) is sent
    only to providers that need it. `base_url` is required for SearXNG (the
    self-hosted instance) and optional for Brave/Tavily, which default to their
    public endpoints.

    The handler lazy-imports httpx (same idiom as adapters/supabase_adapter.py
    and cli/doctor_cmd.py) so a bare install without the `[web]` extra never
    imports httpx at module load, and runs every outbound URL through
    `_ssrf.guard_url` before the request.
    """
    normalized = provider.strip().lower()

    def handler(query: str) -> list[dict]:
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover - exercised via extras matrix
            raise RuntimeError(
                "web_search requires httpx; run: pip install 'horus-os[web]'"
            ) from exc

        if _looks_like_secret(query):
            # WA-2: warn but proceed. Never log the query text itself, which is
            # the very secret we are worried about leaking.
            _log.warning(
                "web_search query matches a secret-shaped pattern; it will be "
                "sent to the %s provider. Audit the trace before reusing.",
                normalized,
            )

        with httpx.Client() as client:
            if normalized == "searxng":
                if not base_url:
                    raise RuntimeError("web_search provider 'searxng' requires a base_url")
                return _search_searxng(client, base_url, query)
            if normalized == "brave":
                return _search_brave(client, base_url, api_key, query)
            if normalized == "tavily":
                return _search_tavily(client, base_url, api_key, query)
            raise RuntimeError(f"web_search: unknown provider {provider!r}")

    description = (
        "Search the web with the configured provider and return a list of "
        "results, each with title, url, and snippet. Construct the query "
        "explicitly; do not paste raw note or document content."
    )
    return Tool(
        name="web_search",
        description=description,
        parameters=_WEB_SEARCH_PARAMETERS,
        handler=handler,
    )
