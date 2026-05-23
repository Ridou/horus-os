"""Custom adapter example: implementing the `Adapter` Protocol.

This example shows how to:

1. Implement a class that satisfies the `Adapter` Protocol from
   `horus_os.adapters`.
2. Register it for discovery without a `pip install` by replacing
   `horus_os.adapters.base.entry_points` with an inline fake. A real
   third-party adapter would declare its entry point in pyproject.toml:

       [project.entry-points."horus_os.adapters"]
       hello = "my_package.adapter:HelloAdapter"

   and then `pip install -e .` would surface it to `discover_adapters`
   automatically.

3. Call `create_app(data_dir=...)` to build a FastAPI app that mounts
   the custom adapter's route alongside the core routes.

The example uses a temp data directory so it leaves no state behind.

Run it:

    python examples/custom_adapter.py

Requires the `dashboard` extra: `pip install '.[dashboard]'` (already
included in `.[all]` and `.[dev]`).
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from horus_os import Adapter, AdapterContext, Config, Database, create_app
from horus_os.adapters import ADAPTER_ENTRY_POINT_GROUP
from horus_os.adapters import base as adapters_base


class HelloAdapter:
    """A minimal adapter that mounts one diagnostic GET route."""

    name = "hello"

    def bind(self, app: Any, context: AdapterContext) -> None:
        """Register the adapter's HTTP surface on the FastAPI app.

        `context` carries the resolved `Config` and `data_dir` so the
        adapter knows where to read or write its own state. A real
        adapter would also stash a `Database(context.config.db_path)`
        handle or any background workers it needs.
        """

        @app.get(f"/api/adapters/{self.name}/ping")
        def _ping() -> dict[str, str]:
            return {
                "adapter": self.name,
                "data_dir": str(context.data_dir),
            }


class _FakeEntryPoint:
    """Stand-in for an `importlib.metadata.EntryPoint`.

    Real entry points are produced by `importlib.metadata.entry_points`
    after a package install. For the example we hand-roll one that
    `discover_adapters` will accept (it only needs a `.name` attribute
    and a `.load()` method).
    """

    def __init__(self, name: str, target: type) -> None:
        self.name = name
        self._target = target

    def load(self) -> type:
        return self._target


def _stub_entry_points() -> None:
    """Make `discover_adapters` find HelloAdapter without a pip install."""

    def fake(group: str | None = None) -> list[_FakeEntryPoint]:
        if group != ADAPTER_ENTRY_POINT_GROUP:
            return []
        return [_FakeEntryPoint("hello", HelloAdapter)]

    adapters_base.entry_points = fake


def main() -> None:
    # The Protocol is runtime_checkable, so we can assert HelloAdapter
    # satisfies the contract before we hand it to discover_adapters.
    assert isinstance(HelloAdapter(), Adapter)

    _stub_entry_points()

    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        # Mirror what `horus-os init` would do: write a config and
        # initialize the SQLite database so `create_app` finds them.
        config = Config.with_defaults(data_dir)
        config.save()
        Database(config.db_path).init()

        app = create_app(data_dir=data_dir)

        # Print every adapter route the app mounted. In a real script
        # you would point a client at one of these paths.
        adapter_routes = [
            route
            for route in app.router.routes
            if getattr(route, "path", "").startswith("/api/adapters/")
        ]
        print(f"Mounted {len(adapter_routes)} adapter route(s):")
        for route in adapter_routes:
            methods = sorted(getattr(route, "methods", set()) or set())
            print(f"  {','.join(methods) or 'GET'} {route.path}")


if __name__ == "__main__":
    main()
