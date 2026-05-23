"""Adapter contract and entry-point discovery helper.

The `Adapter` Protocol describes the minimum surface a third-party
adapter must implement. `discover_adapters` walks the
`horus_os.adapters` entry point group and returns a list of
instantiated adapters ready to bind onto a FastAPI app.

`entry_points` is rebound at module level so tests can monkeypatch
the discovery source without touching the importlib internals.

Phase 22 additions: optional lifecycle hooks via the
`LifecycleAdapter` Protocol, a per-app `AdapterRegistry` that tracks
status and activity for each discovered adapter, and an `AdapterEntry`
dataclass for the registry rows.
"""

from __future__ import annotations

from collections.abc import Awaitable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from horus_os.config import Config

ADAPTER_ENTRY_POINT_GROUP = "horus_os.adapters"

# Valid status values for an adapter registry entry.
ADAPTER_STATUS_RUNNING = "running"
ADAPTER_STATUS_STOPPED = "stopped"
ADAPTER_STATUS_ERROR = "error"


@dataclass
class AdapterEntry:
    """One row in the AdapterRegistry.

    `status` is one of `running`, `stopped`, `error`. New entries
    default to `stopped` until the bind step flips them to `running`
    or `error`. Lifecycle hooks (`start`, `stop`) flip the status
    further during the FastAPI lifespan.

    `last_activity_at` is a UTC iso8601 string updated by the adapter
    via `AdapterRegistry.touch(name)`. `error_count` increments every
    time `mark_error` is called; `error_message` holds the most recent
    one as `type(exc).__name__: str(exc)`.
    """

    name: str
    status: str = ADAPTER_STATUS_STOPPED
    last_activity_at: str | None = None
    error_count: int = 0
    error_message: str | None = None


class AdapterRegistry:
    """Tracks per-adapter status across the lifetime of a FastAPI app.

    The registry is attached to `app.state.adapter_registry` so the
    `GET /api/adapters` route and any adapter handler can read or
    update it. Mutator methods are no-ops for unknown names so a
    caller bug does not raise out of a lifespan handler.
    """

    def __init__(self) -> None:
        self._entries: dict[str, AdapterEntry] = {}

    def register(self, name: str) -> AdapterEntry:
        """Create an entry for `name` if absent, return the entry.

        Calling register a second time for the same name is a no-op
        and returns the existing entry. This is convenient for
        discovery loops that may revisit an adapter name.
        """
        entry = self._entries.get(name)
        if entry is None:
            entry = AdapterEntry(name=name)
            self._entries[name] = entry
        return entry

    def mark_running(self, name: str) -> None:
        entry = self._entries.get(name)
        if entry is None:
            return
        entry.status = ADAPTER_STATUS_RUNNING

    def mark_stopped(self, name: str) -> None:
        entry = self._entries.get(name)
        if entry is None:
            return
        entry.status = ADAPTER_STATUS_STOPPED

    def mark_error(self, name: str, message: str) -> None:
        entry = self._entries.get(name)
        if entry is None:
            return
        entry.status = ADAPTER_STATUS_ERROR
        entry.error_count += 1
        entry.error_message = message

    def touch(self, name: str) -> None:
        """Bump `last_activity_at` to the current UTC iso8601 timestamp."""
        entry = self._entries.get(name)
        if entry is None:
            return
        entry.last_activity_at = datetime.now(UTC).isoformat()

    def get(self, name: str) -> AdapterEntry | None:
        return self._entries.get(name)

    def entries(self) -> list[AdapterEntry]:
        """Return all entries sorted by name for deterministic output."""
        return sorted(self._entries.values(), key=lambda e: e.name)


@dataclass(frozen=True)
class AdapterContext:
    """Read-only bundle of state handed to an adapter at bind time.

    Adapters receive this once during `bind(app, context)` and store
    whatever subset they need. The context is frozen so adapters
    cannot mutate global state through it.

    The `registry` field is a frozen reference to a mutable
    AdapterRegistry. Adapters can call `context.registry.touch(name)`
    to bump their `last_activity_at` from request handlers.
    """

    config: Config
    data_dir: Path
    registry: AdapterRegistry = field(default_factory=AdapterRegistry)


@runtime_checkable
class Adapter(Protocol):
    """The minimum surface a horus-os adapter must implement.

    `name` is a stable identifier used for diagnostics and as the
    URL prefix on the FastAPI app (`/api/adapters/<name>/...`).

    `bind(app, context)` is called once during `create_app` startup.
    The adapter is expected to register routes on `app` and store
    any context it needs for handling requests.

    An optional `describe(self) -> dict` method may return a static
    metadata dict for diagnostics; callers should use `hasattr` to
    check for it.

    See `LifecycleAdapter` for the optional async `start`/`stop`
    hooks that long-running adapters can implement.
    """

    name: str

    def bind(self, app: Any, context: AdapterContext) -> None:
        """Mount the adapter onto the given FastAPI app."""
        ...


@runtime_checkable
class LifecycleAdapter(Protocol):
    """Optional sibling Protocol for adapters with background work.

    Adapters that need to launch a long-running task (a Discord
    socket, an IMAP poll loop, a scheduled tick) implement this
    Protocol in addition to `Adapter`. The FastAPI lifespan invokes
    `start` at app startup and `stop` at shutdown.

    Both methods are async (return an `Awaitable[None]`). `start`
    receives the same `AdapterContext` passed to `bind` so the
    adapter can reach the registry, config, and data_dir without
    holding extra state.

    Runtime dispatch in the lifespan uses `hasattr` rather than
    `isinstance(adapter, LifecycleAdapter)` so adapters with only
    one of the two hooks still work; the Protocol is exported for
    type hinting and documentation.
    """

    name: str

    def start(self, context: AdapterContext) -> Awaitable[None]:
        """Launch any background tasks the adapter needs."""
        ...

    def stop(self) -> Awaitable[None]:
        """Drain background tasks. Must complete promptly."""
        ...


def discover_adapters() -> list[Adapter]:
    """Return all adapters declared via the `horus_os.adapters` entry point.

    The list is sorted by entry-point name so adapter ordering is
    deterministic across runs.

    A load failure on one entry point (the dotted path does not
    resolve, or the factory raises during instantiation) is caught
    silently. The broken entry is skipped; other entries still load.
    Returning an incomplete list rather than crashing keeps the core
    dashboard functional even when an optional adapter package has a
    bug.
    """
    discovered: list[Adapter] = []
    eps = list(entry_points(group=ADAPTER_ENTRY_POINT_GROUP))
    for ep in sorted(eps, key=lambda e: e.name):
        try:
            target = ep.load()
            # The entry-point target is one of:
            #   - a class -> instantiate with no args
            #   - a callable factory (function/lambda) -> call to build the adapter
            #   - an already-constructed adapter instance -> use as-is
            # We distinguish a factory from an instance by checking for the
            # Protocol's required `bind` attribute. Functions do not have one.
            if isinstance(target, type):
                adapter = target()
            elif callable(target) and not hasattr(target, "bind"):
                adapter = target()
            else:
                adapter = target
        except Exception:
            continue
        discovered.append(adapter)
    return discovered
