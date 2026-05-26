"""TEST-14 bounded-shutdown test (Phase 38, Pitfall 6).

The load-bearing assertion is `test_stop_completes_within_3s_against_closed_port`:
after publishing one LLMCallEvent against `http://127.0.0.1:1` (a port
nothing listens on), `adapter.stop()` returns in less than 3 seconds
wall-clock. This pins the daemon-thread leak workaround AND the
60-second-block workaround documented in PITFALLS.md Pitfall 6.

Source-level grep gates double-pin BatchSpanProcessor usage and the
absence of SimpleSpanProcessor in the adapter source. The grep gates
run inside pytest so they fire on all three OSes without depending on
a shell-only test runner.

All tests skip when opentelemetry is absent (the no-otel install
variant) via `pytest.importorskip` at module top.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

pytest.importorskip("opentelemetry")

from horus_os.adapters.base import AdapterContext, AdapterRegistry
from horus_os.adapters.otel_adapter import (
    FORCE_FLUSH_TIMEOUT_MS,
    OTLP_ENDPOINT_ENV,
    OtelAdapter,
)
from horus_os.config import Config
from horus_os.observability import (
    LLMCallEvent,
    get_observation_bus,
    reset_observation_bus_for_tests,
)


def _make_context(tmp_path: Path) -> AdapterContext:
    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    reg = AdapterRegistry()
    reg.register("otel")
    return AdapterContext(config=cfg, data_dir=tmp_path, registry=reg)


# Closed port that the OS kernel refuses fast (no listener at :1).
_CLOSED_PORT_ENDPOINT = "http://127.0.0.1:1"


def test_stop_completes_within_3s_against_closed_port(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """THE LOAD-BEARING TEST-14 ASSERTION.

    Against a closed-port endpoint, stop() must return in less than 3
    seconds wall-clock. The OTel-Python upstream bug (issue #3309)
    would otherwise block for up to 60 seconds on shutdown when the
    collector is unreachable; the bounded force_flush(2000) +
    shutdown() workaround keeps the budget at < 3s.
    """
    monkeypatch.setenv(OTLP_ENDPOINT_ENV, _CLOSED_PORT_ENDPOINT)
    reset_observation_bus_for_tests()
    ctx = _make_context(tmp_path)
    adapter = OtelAdapter()
    asyncio.run(adapter.start(ctx))
    # Publish one event so there is something queued in the BSP.
    # Task 4 wires the subscription so this event reaches the provider;
    # in Task 3 the subscription is not wired yet so the BSP queue
    # remains empty, but stop() still must bound regardless.
    get_observation_bus().publish(
        LLMCallEvent(
            trace_id="t1",
            iteration_idx=0,
            provider="anthropic",
            model="claude-sonnet-4-6",
            input_tokens=100,
            output_tokens=50,
            latency_ms=12,
        )
    )
    start_time = time.perf_counter()
    asyncio.run(adapter.stop())
    elapsed = time.perf_counter() - start_time
    assert elapsed < 3.0, (
        f"stop() took {elapsed:.2f}s against closed-port endpoint; budget is < 3.0s "
        f"(Pitfall 6 / OTel issue #3309 regression)"
    )


def test_stop_after_start_marks_registry_stopped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(OTLP_ENDPOINT_ENV, _CLOSED_PORT_ENDPOINT)
    reset_observation_bus_for_tests()
    ctx = _make_context(tmp_path)
    adapter = OtelAdapter()
    asyncio.run(adapter.start(ctx))
    asyncio.run(adapter.stop())
    entry = ctx.registry.get("otel")
    assert entry is not None
    assert entry.status == "stopped"


def test_stop_is_idempotent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(OTLP_ENDPOINT_ENV, _CLOSED_PORT_ENDPOINT)
    reset_observation_bus_for_tests()
    ctx = _make_context(tmp_path)
    adapter = OtelAdapter()
    asyncio.run(adapter.start(ctx))
    asyncio.run(adapter.stop())
    # Second stop is a no-op; provider already None.
    asyncio.run(adapter.stop())


def test_stop_without_start_is_noop() -> None:
    adapter = OtelAdapter()
    # No exception. Provider and unsubscribe handles are None.
    asyncio.run(adapter.stop())


def test_force_flush_timeout_constant_is_2000ms() -> None:
    # Pins the 2-second budget; a future PR cannot silently raise
    # this past the 3s wall-clock budget without also bumping the
    # TEST-14 assertion (which would then fail loudly).
    assert FORCE_FLUSH_TIMEOUT_MS == 2000


# -- source-level grep gates (Pitfall 6 enforcement) -------------------------------

_ADAPTER_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "horus_os" / "adapters" / "otel_adapter.py"
)


def test_adapter_source_uses_batch_span_processor() -> None:
    source = _ADAPTER_PATH.read_text()
    assert "BatchSpanProcessor" in source, (
        "OtelAdapter source must reference BatchSpanProcessor (Pitfall 6); "
        "SimpleSpanProcessor is banned in production source."
    )


def test_adapter_source_never_uses_simple_span_processor() -> None:
    source = _ADAPTER_PATH.read_text()
    assert source.count("SimpleSpanProcessor") == 0, (
        "OtelAdapter source must NOT reference SimpleSpanProcessor (Pitfall 6). "
        "SimpleSpanProcessor blocks the calling thread on every span which "
        "would un-bound shutdown when the collector is unreachable."
    )


def test_adapter_source_calls_force_flush_with_2000ms() -> None:
    source = _ADAPTER_PATH.read_text()
    has_constant_form = "force_flush(timeout_millis=FORCE_FLUSH_TIMEOUT_MS)" in source
    has_literal_form = "force_flush(timeout_millis=2000)" in source
    assert has_constant_form or has_literal_form, (
        "OtelAdapter.stop() must call force_flush with timeout_millis = 2000 "
        "(Pitfall 6 bounded-shutdown contract)."
    )


def test_adapter_source_does_not_mutate_global_tracer_provider() -> None:
    source = _ADAPTER_PATH.read_text()
    assert "set_tracer_provider" not in source, (
        "OtelAdapter must NOT call trace.set_tracer_provider(...); the adapter "
        "holds its own TracerProvider via self._provider so disabling it cleanly "
        "drops the provider without touching other tracers (T-38-10)."
    )


def test_start_marks_error_when_endpoint_env_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Benign mis-config: the user installed [otel] but forgot the
    # endpoint env var. mark_error fires; no raise.
    monkeypatch.delenv(OTLP_ENDPOINT_ENV, raising=False)
    reset_observation_bus_for_tests()
    ctx = _make_context(tmp_path)
    adapter = OtelAdapter()
    asyncio.run(adapter.start(ctx))
    entry = ctx.registry.get("otel")
    assert entry is not None
    assert entry.status == "error"
    assert OTLP_ENDPOINT_ENV in (entry.error_message or "")
    # Adapter did NOT mount a provider.
    assert adapter._provider is None
