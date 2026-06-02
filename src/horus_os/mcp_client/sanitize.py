"""Tool-description sanitizer for the MCP client (Pitfall MC-2).

Tool descriptions returned by an external MCP server are UNTRUSTED
content. They are not user input, so they bypass the scrutiny applied
to user messages, yet most tool-using agents fold the description into
the system prompt where injected instructions run in the same context
as legitimate ones. This is the "tool poisoning" attack class, the most
prevalent MCP client vulnerability identified by security researchers.

`sanitize_tool_description` is the single choke point every external
description flows through before it reaches the model. It:

- returns "" for None or any non-str input (never raises),
- strips Unicode tag characters U+E0000-U+E007F (the invisible
  instruction-smuggling range),
- drops other format (Cf) and control (Cc) characters except ordinary
  whitespace (newline, tab, carriage return, space),
- collapses the result and length-caps it to MCP_DESCRIPTION_MAX_CHARS.

The function must NEVER raise; a malformed description from a hostile
server must not crash tool registration. A capped description ends with
a short marker so a downstream reader can tell it was truncated.
"""

from __future__ import annotations

import unicodedata

# The description that reaches the model is length-capped. 1024 chars is
# generous for a legitimate tool description and small enough to bound a
# hostile server's prompt-injection payload.
MCP_DESCRIPTION_MAX_CHARS = 1024

# Truncation marker appended INSIDE the cap when a description overflows.
_TRUNCATION_MARKER = "..."

# Unicode tag block: U+E0000-U+E007F. These code points are invisible to
# a human reader but fully visible to the model, making them the canonical
# vehicle for smuggling instructions into a tool description.
_TAG_RANGE_START = 0xE0000
_TAG_RANGE_END = 0xE007F

# Ordinary whitespace we keep even though tab/newline are technically
# control characters (category Cc). Stripping them would mangle legitimate
# multi-line descriptions.
_ALLOWED_WHITESPACE = {"\t", "\n", "\r", " "}


def sanitize_tool_description(text: object) -> str:
    """Return a model-safe version of an MCP tool description.

    Strips Unicode tag characters and other format/control code points,
    collapses whitespace, and length-caps to MCP_DESCRIPTION_MAX_CHARS.
    Returns "" for None or any non-str input. Never raises (MC-2).
    """
    if not isinstance(text, str):
        return ""

    try:
        cleaned_chars: list[str] = []
        for ch in text:
            code = ord(ch)
            # Drop the entire Unicode tag block (invisible smuggling range).
            if _TAG_RANGE_START <= code <= _TAG_RANGE_END:
                continue
            if ch in _ALLOWED_WHITESPACE:
                cleaned_chars.append(ch)
                continue
            # Drop format (Cf) and control (Cc) characters; these include
            # zero-width joiners, bidi overrides, and other invisible
            # code points an attacker can use to hide payloads.
            category = unicodedata.category(ch)
            if category in ("Cf", "Cc"):
                continue
            cleaned_chars.append(ch)

        cleaned = "".join(cleaned_chars)

        if len(cleaned) > MCP_DESCRIPTION_MAX_CHARS:
            # Reserve room for the marker so the final string stays within
            # the cap. The marker tells a reviewer the text was truncated.
            head = cleaned[: MCP_DESCRIPTION_MAX_CHARS - len(_TRUNCATION_MARKER)]
            cleaned = head + _TRUNCATION_MARKER

        return cleaned
    except Exception:
        # Defense in depth: a hostile or malformed description must never
        # crash registration. Fall back to an empty description.
        return ""
