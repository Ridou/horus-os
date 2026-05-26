"""OTel-canonical GenAI attribute-name constants (Phase 38, OTEL-05).

These eight string constants are the ONLY source of truth for the
attribute keys the OTel adapter emits. STACK.md §"GenAI semconv
adoption" pins the values; the constants here mirror that table
verbatim.

GenAI semconv is in `Development` status per the OTel spec as of
May 2026, which is why horus-os owns these strings in one place
rather than importing from `opentelemetry-semantic-conventions`
(those live under `.experimental` and may rename without notice).
One-file-change-when-spec-stabilizes is the contract.

The four deprecated body-capture attribute constants (the GenAI
"prompt", "completion", "input messages", and "output messages"
attribute keys per OTel semconv 1.38) are deliberately ABSENT from
this module per Pitfall 7 default-deny posture. The opt-in
body-capture path in `otel_adapter.py` hard-codes the single
attribute key it uses INLINE, NOT via a shared constant here, so
there is no shared constant a non-otel module can grab.
"""

from __future__ import annotations

GEN_AI_SYSTEM = "gen_ai.system"
GEN_AI_OPERATION_NAME = "gen_ai.operation.name"
GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
GEN_AI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
GEN_AI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
GEN_AI_USAGE_CACHED_TOKENS = "gen_ai.usage.cached_tokens"
HORUS_OS_COST_USD = "horus_os.cost_usd"
ERROR_TYPE = "error.type"

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
