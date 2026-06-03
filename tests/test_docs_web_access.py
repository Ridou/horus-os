"""Regression test pinning docs/WEB-ACCESS.md to the shipped behavior (WEB-02).

The doc explains both halves of Phase 72 web access: the bring-your-own
`web_search` tool and Playwright MCP browsing through the phase-71 MCP client.
Asserting on a handful of load-bearing literals keeps the doc from silently
drifting away from what the code actually does (the SSRF refusal address, the
namespaced Playwright tool prefix, the config section, and the package name).
"""

from __future__ import annotations

from pathlib import Path

import pytest

_DOC_PATH = Path(__file__).resolve().parents[1] / "docs" / "WEB-ACCESS.md"


def test_web_access_doc_exists() -> None:
    assert _DOC_PATH.is_file(), f"missing web access doc at {_DOC_PATH}"


@pytest.mark.parametrize(
    "literal",
    [
        "Playwright",
        "mcp:playwright:",
        "[tools.web_search]",
        "169.254.169.254",
    ],
)
def test_web_access_doc_pins_literal(literal: str) -> None:
    text = _DOC_PATH.read_text(encoding="utf-8")
    assert literal in text, f"docs/WEB-ACCESS.md must mention {literal!r}"


def test_web_access_doc_has_no_em_dash() -> None:
    # CI guard analog: no em-dash (U+2014) in committed prose. The forbidden
    # character is built from its codepoint so this test file itself stays free
    # of a literal em-dash glyph.
    em_dash = chr(0x2014)
    text = _DOC_PATH.read_text(encoding="utf-8")
    assert em_dash not in text, "docs/WEB-ACCESS.md must not contain an em-dash"
