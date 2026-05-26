"""Internal OTel-canonical constants package (Phase 38).

This package is INTERNAL (leading underscore) on purpose. It exists to
isolate OpenTelemetry GenAI semantic-convention attribute names from the
rest of the codebase so that:

1. Only the OTel adapter (`adapters/otel_adapter.py`) and its tests
   import these constants. Core capture code in `observability/` has no
   business reaching the OTel attribute strings.
2. When the OTel GenAI semconv spec stabilizes (it is in "Development"
   status as of May 2026 per STACK.md), one file changes (`semconv.py`)
   to track upstream rename or value-list edits.

This package is distinct from `horus_os.observability/` which holds the
bus, persister, cost annotator, pricing table, and queries. The two
packages are deliberately separate; importing one does NOT import the
other.

Constants re-exported here are the canonical 8 GenAI attribute keys per
STACK.md §"GenAI semconv adoption" plus our own `horus_os.cost_usd`
extension. The deprecated `gen_ai.prompt` / `gen_ai.completion` /
`gen_ai.input.messages` / `gen_ai.output.messages` constants are
deliberately ABSENT (Pitfall 7 default-deny posture at the constants
layer; having the constant would invite a contributor to use it).
"""

from __future__ import annotations

from horus_os._observability.semconv import (
    ERROR_TYPE,
    GEN_AI_OPERATION_NAME,
    GEN_AI_REQUEST_MODEL,
    GEN_AI_SYSTEM,
    GEN_AI_USAGE_CACHED_TOKENS,
    GEN_AI_USAGE_INPUT_TOKENS,
    GEN_AI_USAGE_OUTPUT_TOKENS,
    HORUS_OS_COST_USD,
)

__all__ = [
    "ERROR_TYPE",
    "GEN_AI_OPERATION_NAME",
    "GEN_AI_REQUEST_MODEL",
    "GEN_AI_SYSTEM",
    "GEN_AI_USAGE_CACHED_TOKENS",
    "GEN_AI_USAGE_INPUT_TOKENS",
    "GEN_AI_USAGE_OUTPUT_TOKENS",
    "HORUS_OS_COST_USD",
]
