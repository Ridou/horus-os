"""CI helper for the install-smoke-with-otel job (Phase 38, TEST-15).

Asserts the happy path under `pip install -e ".[dev,otel]"`:

1. OTel SDK + OTLP HTTP exporter import.
2. `OtelAdapter().start(ctx)` succeeds when
   `OTEL_EXPORTER_OTLP_ENDPOINT` is set.
3. After publishing one LLMCallEvent, at least one span materializes
   via `InMemorySpanExporter`.
4. `stop()` returns cleanly.

The OS-level smoke job invokes this script; the equivalent pytest
substrate lives in `tests/test_adapters_otel.py` and
`tests/test_adapters_otel_pii_redaction.py`.

Exits 0 on success, nonzero with a clear message on any failure.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from horus_os.adapters.base import AdapterContext, AdapterRegistry
from horus_os.adapters.otel_adapter import OtelAdapter
from horus_os.config import Config
from horus_os.observability import (
    LLMCallEvent,
    get_observation_bus,
    reset_observation_bus_for_tests,
)


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        reset_observation_bus_for_tests()
        cfg = Config.with_defaults(Path(td))
        cfg.save()
        reg = AdapterRegistry()
        reg.register("otel")
        ctx = AdapterContext(config=cfg, data_dir=Path(td), registry=reg)
        adapter = OtelAdapter()
        asyncio.run(adapter.start(ctx))
        if adapter._provider is None:
            print(
                "FAIL: adapter.start did not mount a TracerProvider; "
                "OTEL_EXPORTER_OTLP_ENDPOINT may not be set",
                file=sys.stderr,
            )
            return 1
        exporter = InMemorySpanExporter()
        adapter._provider.add_span_processor(SimpleSpanProcessor(exporter))
        get_observation_bus().publish(
            LLMCallEvent(
                trace_id="ci-smoke",
                iteration_idx=0,
                provider="anthropic",
                model="claude-sonnet-4-6",
                input_tokens=100,
                output_tokens=50,
                latency_ms=12,
                cost_usd=0.001234,
            )
        )
        spans = exporter.get_finished_spans()
        if len(spans) < 1:
            print(
                f"FAIL: expected >=1 span via InMemorySpanExporter, got {len(spans)}",
                file=sys.stderr,
            )
            asyncio.run(adapter.stop())
            return 2
        asyncio.run(adapter.stop())
        print(f"PASS: {len(spans)} span(s) emitted via InMemorySpanExporter")
        return 0


if __name__ == "__main__":
    sys.exit(main())
