"""Citation-validating report builder for a Deep Research run.

`ReportBuilder.render` assembles a structured markdown report from a title and
a list of sections, rewrites the URL-tagged inline citation markers into
sequential `[n]` indices, and appends a numbered `## References` list keyed to
the session `SourceRegistry`.

The load-bearing guarantee (DR-2, anti-hallucination): every citation URL is
validated against `SourceRegistry.contains` before the report is emitted. A
citation pointing at a URL that was never fetched is rejected; under the
default policy `render` raises `UnverifiedCitation`, so a fabricated citation
can never reach the rendered report. Callers that prefer a best-effort partial
report can pass `policy="flag"`, which strips the bad marker from the body and
records it under a `## Flagged citations` block instead of a clean reference.

Inline citation markers in section bodies use the form ``[[<url>]]``. The
builder maps each marker's URL to its 1-based index in
`registry.ordered_sources()` and replaces the marker with ``[n]``. Duplicate
citations to the same registered URL collapse to one reference-list entry and
reuse the same index (RESEARCH-03 dedup carried into the reference list).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from horus_os.research.registry import SourceRegistry

# Inline citation marker: [[https://example.test/page]]. The URL is captured
# non-greedily up to the closing ]]. Whitespace around the URL is tolerated.
_CITATION_RE = re.compile(r"\[\[\s*(?P<url>[^\]]+?)\s*\]\]")


class UnverifiedCitation(Exception):
    """Raised when a cited URL is not present in the session SourceRegistry.

    Under the default "reject" policy this aborts the render so no hallucinated
    citation can survive into the report (DR-2). The message names the offending
    URL so the caller can see which claim lacked a fetched source.
    """


@dataclass
class Section:
    """One section of a research report.

    `heading` is the section title (rendered as H2, or H3 when `level=3`);
    `body` is markdown prose that may contain ``[[url]]`` citation markers.
    """

    heading: str
    body: str
    level: int = 2


class ReportBuilder:
    """Render a cited markdown report validated against a SourceRegistry."""

    def render(
        self,
        title: str,
        sections: list[Section],
        registry: SourceRegistry,
        *,
        policy: str = "reject",
    ) -> str:
        """Render `title` + `sections` into cited markdown.

        Rewrites each ``[[url]]`` marker to the URL's 1-based citation index
        from `registry.ordered_sources()` and appends a numbered `## References`
        list (title, URL, date fetched). Only sources actually cited in the body
        appear in the reference list, in registry order, and each appears once.

        `policy` controls unverified citations (a URL not in the registry):

          * ``"reject"`` (default): raise `UnverifiedCitation` (DR-2 hard stop).
          * ``"flag"``: strip the bad marker from the body and list it under a
            ``## Flagged citations`` block; it never appears as a clean
            reference.
        """
        if policy not in ("reject", "flag"):
            raise ValueError(f"unknown citation policy {policy!r}")

        cited_keys: list[str] = []
        flagged: list[str] = []
        rendered_sections: list[str] = []

        def _replace(match: re.Match[str]) -> str:
            url = match.group("url")
            if not registry.contains(url):
                if policy == "reject":
                    raise UnverifiedCitation(
                        f"citation URL {url!r} was never fetched in this session"
                    )
                if url not in flagged:
                    flagged.append(url)
                # Strip the marker entirely; a flagged URL never renders as a
                # clean [n] citation.
                return ""
            index = registry.index_of(url)
            # index is guaranteed not None because contains() returned True.
            assert index is not None
            key = registry.ordered_sources()[index - 1].url
            if key not in cited_keys:
                cited_keys.append(key)
            return f"[{index}]"

        for section in sections:
            prefix = "#" * max(2, min(section.level, 6))
            body = _CITATION_RE.sub(_replace, section.body)
            rendered_sections.append(f"{prefix} {section.heading}\n\n{body.strip()}\n")

        parts: list[str] = [f"# {title}\n"]
        parts.extend(rendered_sections)

        # References: one numbered entry per cited source, in registry order so
        # the [n] indices line up with the list. Dedup is inherent because we
        # key on the registry index, not on each marker occurrence.
        ordered = registry.ordered_sources()
        ref_lines: list[str] = []
        for idx, source in enumerate(ordered, start=1):
            if source.url not in cited_keys:
                continue
            label = source.title or source.url
            ref_lines.append(f"{idx}. {label} - {source.url} (fetched {source.fetched_at})")
        if ref_lines:
            parts.append("## References\n\n" + "\n".join(ref_lines) + "\n")

        if flagged:
            flag_lines = [f"- {url}" for url in flagged]
            parts.append(
                "## Flagged citations\n\n"
                "The following cited URLs were not fetched in this session and "
                "were removed from the report:\n\n" + "\n".join(flag_lines) + "\n"
            )

        return "\n".join(parts)
