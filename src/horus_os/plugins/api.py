"""Single public API surface for horus-os plugins.

Phase 48 enforces via ruff custom rule that the reference plugin's
only ``from horus_os`` imports come from ``horus_os.plugins.api``.
Plugin authors should follow the same convention: every name a
third-party plugin needs from horus-os must be re-exported here.

This module exposes exactly eight names via ``__all__``. The
``test_api_surface.py`` test asserts no leading-underscore name leaks
and that every public name resolves to a non-None object.

The two stubs in this module — ``PluginContext`` and
``require_capability`` — are placeholder implementations sufficient
for Phase 42's ``discover_plugins()`` to type-check. Phase 43 wires
the real ``CapabilityGuard`` behind ``require_capability`` and
extends ``PluginContext`` with ``tool_registry``, ``adapter_registry``,
and grant lookups.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from horus_os.adapters import Adapter, AdapterContext, LifecycleAdapter
from horus_os.plugins.capability_catalog import Capability
from horus_os.plugins.spec import PluginSpec
from horus_os.types import Tool

F = TypeVar("F", bound=Callable[..., object])


@dataclass(frozen=True)
class PluginContext:
    """Per-plugin runtime context passed into adapter/tool factories.

    Phase 41 ships the minimum shape (identity + data dir) so Phase 42's
    ``discover_plugins()`` has a type to reference. Phase 43 extends
    with ``tool_registry``, ``adapter_registry``, and grant lookups.
    """

    plugin_name: str
    plugin_version: str
    data_dir: Path


def require_capability(*caps: Capability) -> Callable[[F], F]:
    """Decorator stub. Phase 43 will wire actual ``CapabilityGuard`` enforcement.

    In Phase 41 this is a no-op pass-through decorator that records the
    required caps on the wrapped function's ``__horus_required_caps__``
    attribute so Phase 43's lint + runtime checks have a discoverable
    marker.
    """

    def _wrapper(func: F) -> F:
        try:
            func.__horus_required_caps__ = tuple(caps)  # type: ignore[attr-defined]
        except (AttributeError, TypeError):
            # Some callables (e.g. builtin_function_or_method) refuse
            # attribute assignment; record on a wrapper instead.
            pass
        return func

    return _wrapper


__all__ = (
    "Adapter",
    "AdapterContext",
    "Capability",
    "LifecycleAdapter",
    "PluginContext",
    "PluginSpec",
    "Tool",
    "require_capability",
)
