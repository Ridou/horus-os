"""Description-sanitization unit tests (Pitfall MC-2, tool poisoning).

Pins that `sanitize_tool_description` strips Unicode tag characters, drops
zero-width / format controls, length-caps to MCP_DESCRIPTION_MAX_CHARS, and
never raises on malformed input.
"""

from __future__ import annotations

from horus_os.mcp_client.sanitize import (
    MCP_DESCRIPTION_MAX_CHARS,
    sanitize_tool_description,
)


def test_unicode_tag_chars_stripped() -> None:
    # U+E0001 (language tag) and U+E0041 (tag latin capital A) are invisible
    # smuggling characters; both must be removed, leaving the visible text.
    payload = "search\U000e0001 the web\U000e0041 now"
    cleaned = sanitize_tool_description(payload)
    assert "\U000e0001" not in cleaned
    assert "\U000e0041" not in cleaned
    assert cleaned == "search the web now"


def test_zero_width_and_format_controls_stripped() -> None:
    # Zero-width space (U+200B, Cf) and a bidi override (U+202E, Cf) are
    # dropped; ordinary whitespace is preserved.
    payload = "read​file‮ here\tnow"
    cleaned = sanitize_tool_description(payload)
    assert "​" not in cleaned
    assert "‮" not in cleaned
    assert "\t" in cleaned


def test_length_capped() -> None:
    cleaned = sanitize_tool_description("x" * 5000)
    assert len(cleaned) <= MCP_DESCRIPTION_MAX_CHARS


def test_length_cap_marks_truncation() -> None:
    cleaned = sanitize_tool_description("y" * 5000)
    assert cleaned.endswith("...")
    assert len(cleaned) <= MCP_DESCRIPTION_MAX_CHARS


def test_short_description_unchanged() -> None:
    assert sanitize_tool_description("A normal tool.") == "A normal tool."


def test_malformed_description_does_not_raise() -> None:
    # None and non-str inputs return a str and never raise.
    assert sanitize_tool_description(None) == ""
    assert sanitize_tool_description(12345) == ""
    assert sanitize_tool_description(["not", "a", "string"]) == ""
    assert isinstance(sanitize_tool_description(None), str)
