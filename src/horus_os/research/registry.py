"""Session-scoped source registry for a Deep Research run.

A `SourceRegistry` is created once per research run. It tracks every URL the
research team actually fetched and read, de-duplicating by a normalized URL so
the same source is never counted (or cited) twice (RESEARCH-03), and it
enforces the configured `research_max_sources` hard cap by raising
`SourceBudgetExceeded` rather than silently overrunning it (RESEARCH-04).

Two layers of the engine consume this object:

  * the orchestrator funnels every fetched source through `register_source`,
    converting a raised `SourceBudgetExceeded` into a graceful partial report
    (DR-1) instead of overrunning the cap;
  * the report builder validates each citation URL with `contains` so no URL
    the team never fetched can survive into the rendered report (DR-2).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit


class SourceBudgetExceeded(Exception):
    """Raised when registering a new source would exceed research_max_sources.

    The orchestrator catches this and finishes with a graceful partial report
    (DR-1) so a research run can never silently grow past its source cap.
    """


@dataclass
class Source:
    """One fetched-and-read source recorded in a research session.

    `url` is the normalized URL (the de-duplication key); `title` is an
    optional human label for the reference list; `fetched_at` is an ISO-8601
    UTC timestamp marking when the source was registered.
    """

    url: str
    title: str | None
    fetched_at: str


def _normalize_url(url: str) -> str:
    """Return the de-duplication key for a URL.

    Normalization rule (documented and stable, tests pin it):

      * lowercase the scheme and the host (host comparison is case-insensitive
        per RFC 3986, so ``https://A.TEST/x`` and ``https://a.test/x`` match);
      * strip a single trailing slash from the path so ``/x`` and ``/x/`` match;
      * preserve the path and query verbatim otherwise (no further folding),
        so two genuinely different pages on the same host stay distinct.

    The fragment is dropped because it never identifies a distinct server
    resource. The original URL string is never mutated in place; callers store
    whichever form they pass while the registry keys on this normalized value.
    """
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    host = parts.hostname.lower() if parts.hostname else ""
    # Re-attach an explicit port and userinfo if present so we never silently
    # collapse two distinct authorities. urlsplit splits these out; rebuild the
    # netloc with the lowercased host but the original port/userinfo.
    netloc = host
    if parts.port is not None:
        netloc = f"{host}:{parts.port}"
    if parts.username:
        auth = parts.username
        if parts.password:
            auth = f"{auth}:{parts.password}"
        netloc = f"{auth}@{netloc}"
    path = parts.path
    if path.endswith("/") and len(path) > 1:
        path = path[:-1]
    return urlunsplit((scheme, netloc, path, parts.query, ""))


class SourceRegistry:
    """Insertion-ordered set of fetched sources for one research run.

    The registry keys on the normalized URL so duplicate fetches collapse to a
    single entry, and it refuses to grow past `max_sources` so the source
    budget is a hard cap, never a soft target.
    """

    def __init__(self, max_sources: int) -> None:
        self._max_sources = max_sources
        # Insertion-ordered mapping of normalized URL to its Source record.
        # Insertion order is the 1-based citation index order the report uses.
        self._sources: dict[str, Source] = {}

    def register_source(self, url: str, *, title: str | None = None) -> int:
        """Register a fetched source and return its 1-based citation index.

        A URL already present (after normalization) returns its existing index
        without adding a second entry (RESEARCH-03 de-dup); the title is filled
        in if it was previously unknown. A genuinely new URL is appended unless
        the registry is already at `max_sources`, in which case
        `SourceBudgetExceeded` is raised and nothing is recorded (RESEARCH-04
        hard cap at the source layer).
        """
        key = _normalize_url(url)
        existing = self._sources.get(key)
        if existing is not None:
            if existing.title is None and title is not None:
                existing.title = title
            return self._index_of(key)
        if self.would_exceed_source_budget():
            raise SourceBudgetExceeded(
                f"source budget of {self._max_sources} reached; refusing {url!r}"
            )
        self._sources[key] = Source(
            url=key,
            title=title,
            fetched_at=datetime.now(UTC).isoformat(),
        )
        return self._index_of(key)

    def contains(self, url: str) -> bool:
        """Return True only if `url` (normalized) was actually registered."""
        return _normalize_url(url) in self._sources

    def count(self) -> int:
        """Return the number of distinct registered sources."""
        return len(self._sources)

    def would_exceed_source_budget(self) -> bool:
        """Return True once the registry has reached `max_sources`.

        When this is True, the next genuinely new `register_source` call raises
        `SourceBudgetExceeded`. Re-registering an already-known URL never trips
        the cap because it adds no new entry.
        """
        return self.count() >= self._max_sources

    def ordered_sources(self) -> list[Source]:
        """Return the registered sources in citation (insertion) order."""
        return list(self._sources.values())

    def index_of(self, url: str) -> int | None:
        """Return the 1-based citation index for a registered URL, or None."""
        key = _normalize_url(url)
        if key not in self._sources:
            return None
        return self._index_of(key)

    def _index_of(self, key: str) -> int:
        # The key is guaranteed present; return its 1-based insertion position.
        for idx, existing_key in enumerate(self._sources, start=1):
            if existing_key == key:
                return idx
        # Unreachable: callers only pass keys already in the mapping.
        raise KeyError(key)
