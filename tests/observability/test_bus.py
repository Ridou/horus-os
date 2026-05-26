"""Unit tests for ObservationBus dispatch semantics.

The bus is the central contract every Phase 33+ subscriber depends on.
These tests pin down: synchronous in-call dispatch, per-subscriber
exception swallow, unsubscribe semantics, and subscribe-order preservation.

Phase 33 also covers the module-level singleton accessor
`get_observation_bus()` and the `create_app()` wiring that subscribes
`SQLitePersister` on app construction.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from horus_os import AgentResult, Database
from horus_os.observability import (
    get_observation_bus,
    reset_observation_bus_for_tests,
)
from horus_os.observability.bus import (
    LLMCallEvent,
    ObservationBus,
    ObservationEvent,
    RunEndEvent,
)


def _llm_event(trace_id: str = "t1") -> LLMCallEvent:
    return LLMCallEvent(
        trace_id=trace_id,
        iteration_idx=0,
        provider="anthropic",
        model="claude-sonnet-4-6",
        latency_ms=1,
    )


def test_synchronous_dispatch() -> None:
    bus = ObservationBus()
    received: list[ObservationEvent] = []
    bus.subscribe(received.append)
    bus.publish(_llm_event())
    # Subscriber must have seen the event in the same call frame.
    assert len(received) == 1
    assert received[0].trace_id == "t1"


def test_subscriber_exception_swallowed() -> None:
    bus = ObservationBus()

    def boom(_: ObservationEvent) -> None:
        raise RuntimeError("subscriber died")

    received: list[ObservationEvent] = []
    bus.subscribe(boom)
    bus.subscribe(received.append)
    # The bus must not propagate the boom exception. The second
    # subscriber must still receive the event.
    bus.publish(_llm_event())
    assert len(received) == 1


def test_unsubscribe_removes_handler() -> None:
    bus = ObservationBus()
    received: list[ObservationEvent] = []
    unsubscribe = bus.subscribe(received.append)
    bus.publish(_llm_event())
    assert len(received) == 1
    unsubscribe()
    bus.publish(_llm_event())
    # No new event after unsubscribe.
    assert len(received) == 1
    # Calling unsubscribe twice is a no-op (idempotent).
    unsubscribe()


def test_subscriber_order_preserved() -> None:
    bus = ObservationBus()
    order: list[str] = []
    bus.subscribe(lambda _e: order.append("first"))
    bus.subscribe(lambda _e: order.append("second"))
    bus.subscribe(lambda _e: order.append("third"))
    bus.publish(RunEndEvent(trace_id="t1", latency_ms=10))
    assert order == ["first", "second", "third"]


def test_get_observation_bus_is_singleton() -> None:
    """Two calls to get_observation_bus return the same instance."""
    reset_observation_bus_for_tests()
    bus_a = get_observation_bus()
    bus_b = get_observation_bus()
    assert bus_a is bus_b


def test_reset_observation_bus_for_tests_yields_fresh_instance() -> None:
    """After reset_observation_bus_for_tests, the next get returns a different object."""
    reset_observation_bus_for_tests()
    bus_a = get_observation_bus()
    fresh = reset_observation_bus_for_tests()
    bus_b = get_observation_bus()
    assert fresh is bus_b
    assert bus_a is not bus_b


def test_create_app_subscribes_sqlitepersister(tmp_path: Path) -> None:
    """create_app() wires SQLitePersister onto the singleton bus.

    Proves the Phase 33 wiring contract: a synthetic LLMCallEvent published
    after create_app() returns lands a row in `llm_calls` via the wired
    persister, without any runner code involvement.
    """
    from fastapi.testclient import TestClient

    from horus_os import create_app

    reset_observation_bus_for_tests()
    # Seed a Database under tmp_path so create_app's lazy db_path resolves
    # to a real file. The wizard normally does this; the test does it
    # inline.
    db_path = tmp_path / "horus.sqlite"
    db = Database(db_path)
    db.init()
    seeded_trace_id = db.record_trace(
        "seed prompt", AgentResult(text="seed", provider="anthropic", model="claude-sonnet-4-6")
    )

    app = create_app(data_dir=tmp_path)
    # Use TestClient as a context manager so lifespan startup runs cleanly.
    with TestClient(app):
        # The bus on app.state must be the same singleton get_observation_bus returns.
        assert app.state.observation_bus is get_observation_bus()

        # Publish a synthetic event. The wired SQLitePersister should write it.
        get_observation_bus().publish(
            LLMCallEvent(
                trace_id=seeded_trace_id,
                iteration_idx=0,
                provider="anthropic",
                model="claude-sonnet-4-6",
                input_tokens=7,
                output_tokens=3,
                latency_ms=5,
            )
        )

    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute(
            "SELECT input_tokens, output_tokens, latency_ms FROM llm_calls WHERE trace_id = ?",
            (seeded_trace_id,),
        ).fetchone()
    assert row is not None
    assert row[0] == 7
    assert row[1] == 3
    assert row[2] == 5
