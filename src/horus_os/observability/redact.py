"""PII / secret redactor (Phase 38, Pitfall 7 defence-in-depth).

The public `redact(text)` function applies an allowlist of seven
regex patterns (AWS access keys, Anthropic / OpenAI sk-* keys,
GitHub personal-access tokens, Slack tokens, emails, E.164 phone
numbers, GCP API key prefixes) and replaces every match with the
literal string `[REDACTED]`.

`redact()` is the OPT-IN mode safety net for the OTel adapter.
Default-mode OTel emission NEVER attaches body content in the first
place, so the default-deny path NEVER reaches the redactor. Two
layers of defence: (1) default-deny (no body attribute set), (2)
opt-in mode still runs through this redactor.

Patterns are lifted verbatim from PITFALLS.md §Pitfall 7. The E.164
phone pattern `\\+?[1-9]\\d{1,14}` deliberately over-matches on bare
integers; Pitfall 7 chose over-redaction over under-redaction. The
trade-off is documented in docs/OTEL.md `## Threat model` section.

This module is pure stdlib (`re` only) so it imports cleanly under
the no-otel install variant; `adapters/otel_adapter.py` imports
`redact` at module top, which keeps the module-top import contract
opentelemetry-free.
"""

from __future__ import annotations

import re

# Patterns are tuples of (compiled regex, human-readable name) so a
# future maintainer can extend the list without re-flowing the loop.
_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"AKIA[A-Z0-9]{16}"), "aws_access_key"),
    (re.compile(r"sk-[A-Za-z0-9_-]{20,}"), "sk_api_key"),
    (re.compile(r"ghp_[A-Za-z0-9]{36,}"), "github_pat"),
    (re.compile(r"xox[abpre]-[A-Za-z0-9_-]+"), "slack_token"),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "email"),
    (re.compile(r"gcp-[A-Za-z0-9_-]+"), "gcp_api_key_prefix"),
    # E.164 phone numbers. Deliberately over-matches bare integers per
    # Pitfall 7. Runs LAST so the more-specific patterns above (sk-,
    # ghp_, xoxb-, AKIA, gcp-) have already substituted their matches
    # with the digit-free literal [REDACTED] before this loop iteration.
    (re.compile(r"\+?[1-9]\d{1,14}"), "e164_phone"),
)

_PLACEHOLDER = "[REDACTED]"


def redact(text: str) -> str:
    """Replace any allowlisted secret pattern in `text` with `[REDACTED]`.

    Idempotent: `redact(redact(x)) == redact(x)` for any input `x`
    because `[REDACTED]` contains no characters that match any pattern.

    Returns the input unchanged when no pattern matches. Returns the
    empty string for an empty input.
    """
    if not text:
        return text
    result = text
    for pattern, _name in _PATTERNS:
        result = pattern.sub(_PLACEHOLDER, result)
    return result


__all__ = ["redact"]
