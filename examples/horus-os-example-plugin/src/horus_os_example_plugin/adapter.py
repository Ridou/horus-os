"""Reference plugin adapter: scenario (c).

``ExampleAdapter`` implements the ``LifecycleAdapter`` protocol from
``horus_os.plugins.api`` with a bounded-by-default shape:

* ``start(ctx)`` schedules a no-op background task with
  ``asyncio.create_task(asyncio.sleep(0))`` and returns immediately.
  Completes in microseconds — well inside the Phase 43
  ``asyncio.wait_for(start, timeout=2.0)`` bound enforced by the host
  loader (``src/horus_os/plugins/loader.py``).
* ``stop()`` cancels the task and awaits its completion under a
  matching 2-second ceiling.

The adapter declares NO capability of its own (lifecycle hooks do not
need a grant); it appears in the manifest's
``[[contributions.adapters]]`` array but is absent from the
``[capabilities]`` array.

Every name imported from horus-os comes from
``horus_os.plugins.api`` — TEST-21's single public API surface.
"""

from __future__ import annotations

import asyncio

from horus_os.plugins.api import Adapter, AdapterContext, LifecycleAdapter

# Adapter and LifecycleAdapter Protocols re-exported through the public
# API surface so we can hint at the contracts without importing them
# from the host's internal ``horus_os.adapters`` module. Both names are
# referenced in the docstring above; ``_`` binds prevent a flake8 F401
# unused-import without silencing the public-API-surface contract.
_PROTOCOL_HINTS: tuple[type, ...] = (Adapter, LifecycleAdapter)


class ExampleAdapter:
    """Bounded-lifecycle adapter scaffolding plugin authors can copy.

    Two-state machine: ``start`` schedules a single non-blocking task
    and stashes the handle; ``stop`` cancels and awaits it. The two
    methods together demonstrate the smallest viable adapter that the
    host's lifespan can drive without hanging on the
    ``asyncio.wait_for(timeout=2.0)`` ceiling.
    """

    name: str = "example_adapter"

    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None

    def bind(self, app: object, context: AdapterContext) -> None:
        """No-op mount. All lifecycle work happens in start/stop."""
        return None

    async def start(self, context: AdapterContext) -> None:
        """Schedule a no-op task and return promptly.

        The ``asyncio.sleep(0)`` task yields control and resolves on
        the next event-loop tick. The handler returns control to the
        caller in microseconds — the Phase 43
        ``asyncio.wait_for(timeout=2.0)`` bound is never approached.
        """
        self._task = asyncio.create_task(asyncio.sleep(0))

    async def stop(self) -> None:
        """Cancel the background task and drain it under the timeout."""
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
