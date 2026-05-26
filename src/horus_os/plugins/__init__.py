"""Plugin runtime package.

Public API for plugin AUTHORS lives in :mod:`horus_os.plugins.api`;
the surface there is the single contract Phase 48's ruff custom rule
will lock in (see Pitfall 8 in ``.planning/research/PITFALLS.md``).

This ``__init__`` re-exports the **internal** consumer surface — the
names horus-os internals (FastAPI lifespan, CLI subcommands, dashboard
routes) reach for. Phase 42 onward, ``from horus_os.plugins import
discover_plugins, PluginLoader, PluginRegistry`` is the canonical
import shape for horus-os core code; plugin AUTHORS continue to
import only from ``horus_os.plugins.api``.

The lazy-import order is:

* ``spec`` (frozen dataclasses, no deps)
* ``capability_catalog`` (closed StrEnum)
* ``manifest`` (pydantic v2 schema)
* ``permissions`` (CapabilityGuard stub — Phase 42; Phase 43 enforces)
* ``discovery`` (entry_points + filesystem walk)
* ``registry`` (PluginRegistry mirroring AdapterRegistry shape)
* ``loader`` (PluginLoader with rollback-on-error)

No top-level imports of FastAPI / SQLite / observability stacks happen
here, so ``import horus_os.plugins`` stays cheap.
"""

from horus_os.plugins.discovery import (
    DEFAULT_FILESYSTEM_PLUGIN_DIR,
    PLUGIN_ENTRY_POINT_GROUP,
    DiscoveryError,
    discover_plugins,
)
from horus_os.plugins.loader import (
    LOAD_PHASE_ORDER,
    PluginLoader,
    PluginLoadResult,
)
from horus_os.plugins.permissions import CapabilityGuard
from horus_os.plugins.registry import (
    PLUGIN_STATUS_DISABLED,
    PLUGIN_STATUS_ERROR,
    PLUGIN_STATUS_LOADED,
    PLUGIN_STATUS_PENDING,
    PluginEntry,
    PluginRegistry,
)

__all__ = (
    "DEFAULT_FILESYSTEM_PLUGIN_DIR",
    "LOAD_PHASE_ORDER",
    "PLUGIN_ENTRY_POINT_GROUP",
    "PLUGIN_STATUS_DISABLED",
    "PLUGIN_STATUS_ERROR",
    "PLUGIN_STATUS_LOADED",
    "PLUGIN_STATUS_PENDING",
    "CapabilityGuard",
    "DiscoveryError",
    "PluginEntry",
    "PluginLoadResult",
    "PluginLoader",
    "PluginRegistry",
    "discover_plugins",
)
