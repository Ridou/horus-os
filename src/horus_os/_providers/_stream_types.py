"""Private shared sentinel types for the provider streaming path.

`_StreamUsage` is the terminal sentinel both Anthropic and Gemini
streaming generators yield after the last text chunk and any
ToolCallEvents. The SSE handler in `server/api.py` isinstance-checks
each chunk, extracts the terminal usage when this sentinel is seen,
and consumes it (never forwards it to the wire).

Public consumers (the SSE handler, the observability publishers) treat
this as a private contract: the underscore prefix marks it
non-public, but the providers cannot use a true `_dataclass` because
isinstance() across module boundaries needs a single shared class.

Phase 33 (PITFALLS.md Pitfall 2): the SSE branch must read terminal
usage from the provider's final message and persist non-zero token
counts whenever the stream produced text. This sentinel is how the
provider's stream tells the consumer what those token counts are.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class _StreamUsage:
    """Terminal sentinel yielded by provider streaming generators.

    `usage` holds the provider's native usage dict shape (Anthropic uses
    input_tokens / output_tokens / cache_*; Gemini uses
    prompt_token_count / candidates_token_count). The SSE handler
    normalizes both shapes into the LLMCallEvent fields.

    An empty dict signals "stream completed but usage was not available"
    so the consumer can hit its char-count fallback estimate (never
    persist zero tokens for a non-empty stream).
    """

    usage: dict[str, Any] = field(default_factory=dict)


__all__ = ["_StreamUsage"]
