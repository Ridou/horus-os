"""OpenTelemetry adapter for horus-os (Phase 38).

Ships behind the optional `[otel]` extra. Lazy imports the
`opentelemetry.*` symbols inside `start()` so a bare `pip install
horus-os` keeps importing this module cleanly. When the extra is
absent, `start()` raises a clean `RuntimeError("OTel adapter
requires 'pip install horus-os[otel]'")`, NEVER `ModuleNotFoundError`
(Pitfall 12).

Subscribes to the process-wide ObservationBus via
`get_observation_bus()`; emits one OTel span per `LLMCallEvent` with
the 8 canonical GenAI semantic-convention attribute keys sourced from
`src/horus_os/_observability/semconv.py`.

Bounded shutdown contract (Pitfall 6): `stop()` calls
`provider.force_flush(timeout_millis=2000)` then `provider.shutdown()`.
Against an unreachable collector, `stop()` returns in less than 3
seconds wall-clock; the daemon-thread shutdown bug in OTel-Python
issue #3309 / #4623 is worked around by the bounded flush. The
batched span processor is used unconditionally in production; the
simple span processor variant is forbidden in this source file
(grep gate enforces). Test fixtures may use the simple variant with
the in-memory exporter for synchronous assertions; the adapter
production code does not.

Default-deny content capture is the load-bearing safety guarantee of
this adapter. Even in opt-in mode (`HORUS_OS_OTEL_CAPTURE_CONTENT=true`),
the redactor allowlist (`observability/redact.py`) strips AWS keys,
sk-*, ghp_*, xoxb-*, emails, e164 phones, and gcp- prefixes BEFORE any
body content attaches to a span. The default-deny path NEVER reaches
the redactor because it never sets a body attribute in the first place.

Entry-point declaration in `pyproject.toml`:
`otel = "horus_os.adapters.otel_adapter:OtelAdapter"` under
`[project.entry-points."horus_os.adapters"]`. No hardcoded wiring in
`create_app` is needed; the existing `discover_adapters()` picks up
the entry once the [otel] extra is installed.

DIFFERENCE FROM OTHER ADAPTERS: Discord / Slack / Calendar etc. mark
their registry error and return silently when their optional extra is
missing (silent posture is right for always-loaded entry points). The
OtelAdapter is OPT-IN; the user installed [otel] on purpose, so a
failure to start should be loud. `start()` marks the registry error
AND ALSO re-raises so the user sees the clear install hint in the
console.
"""

from __future__ import annotations

import contextlib
import os
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from horus_os.adapters.base import AdapterContext

if TYPE_CHECKING:
    # Type-only imports never execute at runtime; bare `pip install
    # horus-os` (no [otel] extra) keeps importing this module cleanly.
    from opentelemetry.sdk.trace import TracerProvider

OTEL_EXTRA_HINT = "OTel adapter requires 'pip install horus-os[otel]'"
OTLP_ENDPOINT_ENV = "OTEL_EXPORTER_OTLP_ENDPOINT"
CAPTURE_CONTENT_ENV = "HORUS_OS_OTEL_CAPTURE_CONTENT"
FORCE_FLUSH_TIMEOUT_MS = 2000


def _import_version() -> str:
    """Return the installed horus_os version; isolated so tests can monkeypatch."""
    from horus_os import __version__

    return __version__


class OtelAdapter:
    """LifecycleAdapter that exports LLMCallEvent observations as OTel spans."""

    name = "otel"

    def __init__(self) -> None:
        # All connection state allocated in start() so the constructor
        # stays cheap and import-clean. The OTel SDK is NOT imported here.
        self._provider: TracerProvider | None = None
        self._unsubscribe: Callable[[], None] | None = None
        self._context: AdapterContext | None = None

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": 1,
            "transport": "otlp-http",
            "env": OTLP_ENDPOINT_ENV,
        }

    def bind(self, app: Any, context: AdapterContext) -> None:
        # OTel adapter is bus-subscriber only; no HTTP routes to mount.
        self._context = context
        return None

    async def start(self, context: AdapterContext) -> None:
        """Bring up the OTel TracerProvider and subscribe to the bus.

        Pitfall 12: a missing `opentelemetry` package raises a clean
        RuntimeError with the install hint substring, NEVER a bare
        ModuleNotFoundError. The registry is also marked so the
        dashboard Adapters tab shows the error pill.

        Pitfall 6: the batched span processor is wired unconditionally
        in production. The adapter holds its OWN TracerProvider via
        self._provider and does NOT mutate the global tracer-provider
        slot; disabling the adapter cleanly drops its provider without
        touching other tracers a user may add separately.
        """
        self._context = context
        try:
            import opentelemetry  # noqa: F401  (presence-check only)
        except ImportError as exc:
            context.registry.mark_error(self.name, OTEL_EXTRA_HINT)
            raise RuntimeError(OTEL_EXTRA_HINT) from exc

        endpoint = os.environ.get(OTLP_ENDPOINT_ENV)
        if not endpoint:
            # Benign mis-config: the user enabled [otel] but did not
            # set the collector URL. The registry pill carries the
            # message; no raise (mirrors DiscordAdapter's TOKEN_ENV
            # check).
            context.registry.mark_error(self.name, f"{OTLP_ENDPOINT_ENV} is not set")
            return

        # OTel SDK imports run at function scope per Pitfall 12.
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create(
            {"service.name": "horus-os", "service.version": _import_version()}
        )
        # OTLPSpanExporter reads OTEL_EXPORTER_OTLP_ENDPOINT and
        # OTEL_EXPORTER_OTLP_HEADERS from os.environ directly; no kwargs.
        exporter = OTLPSpanExporter()
        provider = TracerProvider(resource=resource)
        # Pitfall 6: BatchSpanProcessor ALWAYS in production. The
        # synchronous-export variant is banned in this source file;
        # the grep gate in test_adapters_otel_bounded_shutdown.py
        # enforces the ban.
        provider.add_span_processor(BatchSpanProcessor(exporter))
        self._provider = provider

        # Task 4 wires the bus subscription here:
        # self._unsubscribe = get_observation_bus().subscribe(self._on_event)

        context.registry.mark_running(self.name)

    async def stop(self) -> None:
        """Drain in-flight spans and shut down the provider with bounded wait.

        Pitfall 6: force_flush(timeout_millis=FORCE_FLUSH_TIMEOUT_MS) then
        shutdown(). Against an unreachable collector, stop() returns in
        less than 3 seconds wall-clock (TEST-14 pins this). Both calls
        are guarded with contextlib.suppress so a flaky exporter cannot
        prevent the next cleanup step.
        """
        # Unsubscribe FIRST so no further events queue while we flush
        # in-flight spans.
        if self._unsubscribe is not None:
            with contextlib.suppress(Exception):
                self._unsubscribe()
            self._unsubscribe = None
        if self._provider is not None:
            with contextlib.suppress(Exception):
                self._provider.force_flush(timeout_millis=FORCE_FLUSH_TIMEOUT_MS)
            with contextlib.suppress(Exception):
                self._provider.shutdown()
            self._provider = None
        if self._context is not None:
            self._context.registry.mark_stopped(self.name)
