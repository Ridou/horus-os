"""In-process observability substrate for v0.4. Bus, events, and persister.

Phase 32 shipped the bus, the events, and the SQLitePersister. Phase 33 adds
the module-level singleton accessor `get_observation_bus()` that runner code
and `create_app()` use to publish and subscribe.

The singleton pattern is intentional: a process has exactly one
ObservationBus, which means there is exactly one place to subscribe a Phase
34 CostAnnotator, a Phase 38 OtelExporter, or any future subscriber. Tests
that need isolation call `reset_observation_bus_for_tests()` to clear the
module-level reference.
"""

from __future__ import annotations

from horus_os.observability.bus import (
    LLMCallEvent,
    ObservationBus,
    ObservationEvent,
    RunEndEvent,
    ToolCallEvent,
)
from horus_os.observability.persist import SQLitePersister
from horus_os.observability.pricing import ModelPricing, PricingTable

_BUS: ObservationBus | None = None


def get_observation_bus() -> ObservationBus:
    """Return the process-wide ObservationBus, creating it on first call.

    Idempotent: every subsequent call returns the same instance. This is
    the wiring contract Phase 33's runner depends on: publishers in
    `agent.py`, `tools/loop.py`, and `server/api.py` all reach the same
    bus subscribers via this function.
    """
    global _BUS
    if _BUS is None:
        _BUS = ObservationBus()
    return _BUS


def reset_observation_bus_for_tests() -> ObservationBus:
    """Clear the module-level singleton and return a fresh bus.

    Test-only helper. Production code never calls this. Tests that need
    isolation between cases reset the bus at setup so subscribers do not
    leak across test boundaries.
    """
    global _BUS
    _BUS = None
    return get_observation_bus()


__all__ = [
    "LLMCallEvent",
    "ModelPricing",
    "ObservationBus",
    "ObservationEvent",
    "PricingTable",
    "RunEndEvent",
    "SQLitePersister",
    "ToolCallEvent",
    "get_observation_bus",
    "reset_observation_bus_for_tests",
]
