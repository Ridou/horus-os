"""Unit tests for ObservationBus dispatch semantics.

The bus is the central contract every Phase 33+ subscriber depends on.
These tests pin down: synchronous in-call dispatch, per-subscriber
exception swallow, unsubscribe semantics, and subscribe-order preservation.
"""

from __future__ import annotations

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
