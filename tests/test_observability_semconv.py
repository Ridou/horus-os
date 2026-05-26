"""Tests for src/horus_os/_observability/semconv.py (Phase 38, OTEL-05).

The 8 canonical GenAI attribute-name constants live here. Spelling
drift or accidental addition of deprecated body-capture constants
fails one of these tests loudly BEFORE it ships.
"""

from __future__ import annotations

from horus_os import _observability as obs_pkg
from horus_os._observability import semconv


def test_eight_constants_exist_with_canonical_string_values() -> None:
    assert semconv.GEN_AI_SYSTEM == "gen_ai.system"
    assert semconv.GEN_AI_OPERATION_NAME == "gen_ai.operation.name"
    assert semconv.GEN_AI_REQUEST_MODEL == "gen_ai.request.model"
    assert semconv.GEN_AI_USAGE_INPUT_TOKENS == "gen_ai.usage.input_tokens"
    assert semconv.GEN_AI_USAGE_OUTPUT_TOKENS == "gen_ai.usage.output_tokens"
    assert semconv.GEN_AI_USAGE_CACHED_TOKENS == "gen_ai.usage.cached_tokens"
    assert semconv.HORUS_OS_COST_USD == "horus_os.cost_usd"
    assert semconv.ERROR_TYPE == "error.type"


def test_deprecated_attribute_constants_absent() -> None:
    # Pitfall 7 default-deny: the deprecated body-capture constant
    # names DO NOT EXIST in the semconv module, so they cannot be
    # imported and used by accident. The opt-in body-capture path
    # hard-codes the attribute key inline (NOT via a shared constant).
    assert not hasattr(semconv, "GEN_AI_PROMPT")
    assert not hasattr(semconv, "GEN_AI_COMPLETION")
    assert not hasattr(semconv, "GEN_AI_INPUT_MESSAGES")
    assert not hasattr(semconv, "GEN_AI_OUTPUT_MESSAGES")


def test_all_export_lists_eight_constants() -> None:
    assert len(semconv.__all__) == 8
    assert set(semconv.__all__) == {
        "ERROR_TYPE",
        "GEN_AI_OPERATION_NAME",
        "GEN_AI_REQUEST_MODEL",
        "GEN_AI_SYSTEM",
        "GEN_AI_USAGE_CACHED_TOKENS",
        "GEN_AI_USAGE_INPUT_TOKENS",
        "GEN_AI_USAGE_OUTPUT_TOKENS",
        "HORUS_OS_COST_USD",
    }


def test_package_init_reexports_eight_constants() -> None:
    # Package init re-exports all 8 constants so callers can do
    # `from horus_os._observability import GEN_AI_SYSTEM`.
    assert obs_pkg.GEN_AI_SYSTEM == "gen_ai.system"
    assert obs_pkg.GEN_AI_OPERATION_NAME == "gen_ai.operation.name"
    assert obs_pkg.GEN_AI_REQUEST_MODEL == "gen_ai.request.model"
    assert obs_pkg.GEN_AI_USAGE_INPUT_TOKENS == "gen_ai.usage.input_tokens"
    assert obs_pkg.GEN_AI_USAGE_OUTPUT_TOKENS == "gen_ai.usage.output_tokens"
    assert obs_pkg.GEN_AI_USAGE_CACHED_TOKENS == "gen_ai.usage.cached_tokens"
    assert obs_pkg.HORUS_OS_COST_USD == "horus_os.cost_usd"
    assert obs_pkg.ERROR_TYPE == "error.type"
