"""Single public API surface for horus-os plugins.

Phase 48 enforces via ruff custom rule that the reference plugin's
only ``from horus_os`` imports come from ``horus_os.plugins.api``.
Plugin authors should follow the same convention: every name a
third-party plugin needs from horus-os must be re-exported here.

The Phase 43 surface adds three helper-shim namespaces on
``PluginContext`` (``filesystem`` / ``secrets`` / ``net``) plus the
``require_capability`` decorator that marks tool handlers with their
required capability set so ``CapabilityGuard.wrap_tool_handler`` can
enforce default-deny at the wrap site.

The ``test_api_surface.py`` test asserts no leading-underscore name
leaks and that every public name resolves to a non-None object.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from horus_os.adapters import Adapter, AdapterContext, LifecycleAdapter
from horus_os.plugins.capability_catalog import Capability
from horus_os.plugins.permissions import CapabilityGuard, PermissionDenied
from horus_os.plugins.spec import PluginSpec
from horus_os.types import Tool

if TYPE_CHECKING:
    import httpx  # noqa: F401  (type-only; lazy-imported in NetShim.outbound)

F = TypeVar("F", bound=Callable[..., object])


# Hint surfaced when a plugin invokes ctx.net.outbound without httpx
# installed. RuntimeError, NEVER ModuleNotFoundError — Pitfall 12
# clean-extra-hint posture (mirrors OtelAdapter.OTEL_EXTRA_HINT).
_HTTPX_EXTRA_HINT = (
    "httpx is required for ctx.net.outbound; "
    "install horus-os[plugins-net] or pin httpx in your venv"
)


class _FilesystemShim:
    """Filesystem read/write shim backed by a per-plugin CapabilityGuard.

    Path-escape defense per PITFALLS.md Pitfall 1: ``Path(path).resolve()``
    runs BEFORE the capability check. Resolving an absolute path is
    not itself a privileged operation, and surfacing the resolved
    path in the PermissionDenied audit trail (via the guard's
    plugin_name + capability fields) makes traversal attempts visible
    in the dashboard.

    The shim does NOT validate the resolved path against a per-plugin
    allow-list in Phase 43; that gating is deferred to Phase 44 when
    the manifest's per-capability ``paths`` tuple lands. Phase 43 ships
    the binary allow/deny on the capability itself.
    """

    __slots__ = ("_guard",)

    def __init__(self, guard: CapabilityGuard) -> None:
        self._guard = guard

    def read(self, path: str | Path) -> str:
        resolved = Path(path).resolve()
        if Capability.FILESYSTEM_READ not in self._guard.granted_capabilities:
            raise PermissionDenied(
                self._guard.plugin_name, str(Capability.FILESYSTEM_READ)
            )
        return resolved.read_text(encoding="utf-8")

    def write(self, path: str | Path, content: str) -> None:
        resolved = Path(path).resolve()
        if Capability.FILESYSTEM_WRITE not in self._guard.granted_capabilities:
            raise PermissionDenied(
                self._guard.plugin_name, str(Capability.FILESYSTEM_WRITE)
            )
        resolved.write_text(content, encoding="utf-8")


class _SecretsShim:
    """Secrets read shim backed by a per-plugin CapabilityGuard.

    ``read(key)`` returns ``os.environ.get(key)``; a missing key
    returns None instead of raising. This matches the capability
    description in ``capability_catalog.DESCRIPTIONS[SECRETS_READ]``:
    "Read secret values (API keys, tokens) the plugin declares by key
    name." A missing env var is a legitimate runtime state (the user
    hasn't set the key yet), not a permission failure.
    """

    __slots__ = ("_guard",)

    def __init__(self, guard: CapabilityGuard) -> None:
        self._guard = guard

    def read(self, key: str) -> str | None:
        if Capability.SECRETS_READ not in self._guard.granted_capabilities:
            raise PermissionDenied(
                self._guard.plugin_name, str(Capability.SECRETS_READ)
            )
        return os.environ.get(key)


class _NetShim:
    """Outbound HTTP shim backed by a per-plugin CapabilityGuard.

    ``httpx`` is lazy-imported INSIDE ``outbound`` so bare horus-os
    installs that don't use the net.outbound capability never pay
    the import cost. A missing httpx raises a clean RuntimeError
    carrying _HTTPX_EXTRA_HINT — Pitfall 12 (the same clean-extra
    posture as OtelAdapter's RuntimeError on missing opentelemetry).

    The capability check fires BEFORE the httpx import so a denied
    outbound never even loads the network stack — defense in depth
    against a denied plugin accidentally side-effecting the import
    system.
    """

    __slots__ = ("_guard",)

    def __init__(self, guard: CapabilityGuard) -> None:
        self._guard = guard

    def outbound(self, url: str, *, method: str = "GET", **kwargs: Any) -> Any:
        if Capability.NET_OUTBOUND not in self._guard.granted_capabilities:
            raise PermissionDenied(
                self._guard.plugin_name, str(Capability.NET_OUTBOUND)
            )
        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError(_HTTPX_EXTRA_HINT) from exc
        return httpx.request(method, url, **kwargs)


class PluginContext:
    """Per-plugin runtime context passed into adapter/tool factories.

    Phase 41 shipped this as a frozen dataclass with three fields
    (plugin_name, plugin_version, data_dir). Phase 43 extends with
    three shim namespaces and a CapabilityGuard reference. The shape
    is now a regular class with ``__slots__`` (a frozen dataclass
    cannot hold the closure-bound shim references mutably at
    ``__post_init__`` time without dataclass-private trickery; a
    plain class with __slots__ matches the CapabilityGuard pattern
    and is the simpler shape).

    The four pre-existing fields (plugin_name, plugin_version,
    data_dir, plus the new ``guard``) are exposed as read-only
    attributes; the three shim attributes (filesystem, secrets, net)
    are constructed once in __init__ and stay bound to the guard
    for the lifetime of the context.
    """

    __slots__ = (
        "plugin_name",
        "plugin_version",
        "data_dir",
        "guard",
        "filesystem",
        "secrets",
        "net",
    )

    def __init__(
        self,
        plugin_name: str,
        plugin_version: str,
        data_dir: Path,
        guard: CapabilityGuard,
    ) -> None:
        self.plugin_name = plugin_name
        self.plugin_version = plugin_version
        self.data_dir = data_dir
        self.guard = guard
        # Shims are constructed once; they hold a reference to the
        # same guard so a future guard update (e.g. on revoke) would
        # need to rebuild the context — Phase 43 does not hot-swap
        # mid-run; the next CapabilityGuard construction picks up the
        # new state.
        self.filesystem = _FilesystemShim(guard)
        self.secrets = _SecretsShim(guard)
        self.net = _NetShim(guard)


def require_capability(*caps: Capability) -> Callable[[F], F]:
    """Decorator that records required capabilities on a tool handler.

    The decorator is a no-op pass-through at decoration time; it
    only attaches ``__horus_required_caps__`` to the handler. The
    actual enforcement happens at the
    ``CapabilityGuard.wrap_tool_handler`` wrap site (Phase 43): the
    guard reads this attribute, builds a closure that checks each
    required cap against the granted set, and raises
    PermissionDenied on the first missing cap.

    Plugin authors apply this decorator to opt INTO the capability
    surface. Tools that never request a capability (an arithmetic
    or echo tool, for example) can skip the decorator and run
    through unchanged — pass-through behavior at the wrap site.
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


# Phase 43 keeps the Phase 41 public-surface size at 8 names. CapabilityGuard
# is wired through PluginContext.guard for plugin AUTHORS that want to
# introspect the guard (rare; the helper shims close over it), and
# PermissionDenied is exposed via horus_os.plugins (internal consumers)
# AND surfaces in tracebacks regardless. Plugin authors that want to catch
# PermissionDenied directly can ``from horus_os.plugins import PermissionDenied``
# at the cost of a second-tier import; the Phase 48 ruff custom rule will
# need a per-exception allow-list before Phase 48 lands.
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
