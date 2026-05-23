"""Adapter contract and entry-point discovery helper.

The `Adapter` Protocol describes the minimum surface a third-party
adapter must implement. `discover_adapters` walks the
`horus_os.adapters` entry point group and returns a list of
instantiated adapters ready to bind onto a FastAPI app.

`entry_points` is rebound at module level so tests can monkeypatch
the discovery source without touching the importlib internals.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from horus_os.config import Config

ADAPTER_ENTRY_POINT_GROUP = "horus_os.adapters"


@dataclass(frozen=True)
class AdapterContext:
    """Read-only bundle of state handed to an adapter at bind time.

    Adapters receive this once during `bind(app, context)` and store
    whatever subset they need. The context is frozen so adapters
    cannot mutate global state through it.
    """

    config: Config
    data_dir: Path


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
    """

    name: str

    def bind(self, app: Any, context: AdapterContext) -> None:
        """Mount the adapter onto the given FastAPI app."""
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
