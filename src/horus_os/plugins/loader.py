"""Plugin loader: resolve entry points, wrap with CapabilityGuard, register.

Phase 42 ships two commits' worth of work in this file:

* Commit 1 (Task 1) introduces the public surface — ``LOAD_PHASE_ORDER``,
  the ``PluginLoadResult`` frozen dataclass, and the ``PluginLoader``
  class shape — so ``horus_os.plugins.__init__`` can re-export the
  internal-consumer names without circular import concerns.
* Commit 2 (Task 2) fills in ``PluginLoader.load`` with the
  resolve → wrap → register → rollback-on-error body and wires the
  loader into the FastAPI lifespan.

The loader **never raises out** of ``load()``. Every per-spec
exception is caught and returned as a structured
``PluginLoadResult(status='error', error_phase=...)`` so the FastAPI
lifespan can route the failure to ``PluginRegistry.mark_error``
without a try/except wrap. Mid-load failures roll back every
registration the loader appended during the same ``load()`` call so
the master registries observe no half-registered plugin (Pitfall 9
defense-in-depth).

``LOAD_PHASE_ORDER`` is the canonical enum-shaped tuple of phase
names; every ``error_phase`` string ever returned by the loader is
either ``None`` or a member of this tuple. Phase 43 adds ``"start"``
handling; Phase 45 adds ``"stop"`` handling.
"""

from __future__ import annotations

import dataclasses
import importlib
import importlib.util
from dataclasses import dataclass

from horus_os.adapters.base import AdapterRegistry
from horus_os.plugins.permissions import CapabilityGuard
from horus_os.plugins.spec import PluginSpec
from horus_os.tools.registry import ToolRegistry
from horus_os.types import Tool

LOAD_PHASE_ORDER: tuple[str, ...] = (
    "discover",
    "validate",
    "permission",
    "load",
    "start",
    "stop",
)


@dataclass(frozen=True)
class PluginLoadResult:
    """One ``PluginLoader.load(spec)`` outcome.

    ``status`` is ``'loaded'`` on success or ``'error'`` on any failure.
    ``error_phase`` is None on success or a member of
    ``LOAD_PHASE_ORDER`` on error. ``error`` is a one-line
    ``"{ExcType}: {message}"`` string (never the full traceback) so
    user-supplied content from the exception body never bypasses the
    ``str()`` shim (Pitfall 9 error-message hygiene).

    ``registered_tools`` and ``registered_adapters`` are non-empty
    only on ``status='loaded'``; on error the loader rolls back every
    registration before returning so these fields stay empty.
    """

    status: str
    error_phase: str | None = None
    error: str | None = None
    registered_tools: tuple[str, ...] = ()
    registered_adapters: tuple[str, ...] = ()


def _resolve_entry_point(entry_point: str) -> object:
    """Resolve a dotted ``module[:attr]`` entry-point reference.

    Mirrors ``importlib.metadata.EntryPoint`` semantics: ``foo.bar``
    returns the module ``foo.bar``; ``foo.bar:Baz`` returns
    ``getattr(foo.bar, 'Baz')``. Filesystem-sourced specs whose package
    is not on ``sys.path`` would normally fail here — but Phase 42's
    contract is that plugins are **always** importable via
    ``importlib.import_module`` (either the package is pip-installed,
    or the test suite arranges for ``tests/`` to be on ``sys.path``
    via the existing ``[tool.pytest.ini_options]`` configuration).
    No ``sys.path`` mutation happens here.
    """
    module_path, _, attr = entry_point.partition(":")
    module = importlib.import_module(module_path)
    if not attr:
        return module
    return getattr(module, attr)


def _materialize_tool(target: object, expected_name: str) -> Tool:
    """Coerce an entry-point target into a ``Tool`` instance.

    Accepts a ``Tool`` instance directly, a zero-arg factory
    (function / lambda / class) that returns a ``Tool``, or raises
    ``TypeError`` for anything else. The returned ``Tool.name`` must
    match the manifest contribution name so a buggy factory can't
    silently shadow a built-in tool under a different name.
    """
    if isinstance(target, Tool):
        tool = target
    elif callable(target):
        tool = target()
    else:
        raise TypeError(
            f"entry point target for tool {expected_name!r} is neither a Tool "
            f"nor a zero-arg factory; got {type(target).__name__}"
        )
    if not isinstance(tool, Tool):
        raise TypeError(
            f"factory for tool {expected_name!r} did not return a Tool; "
            f"got {type(tool).__name__}"
        )
    if tool.name != expected_name:
        raise ValueError(
            f"tool {expected_name!r} factory returned a Tool named {tool.name!r}; "
            "manifest contribution name and Tool.name must match"
        )
    return tool


def _materialize_adapter(target: object, expected_name: str) -> object:
    """Coerce an entry-point target into an adapter instance.

    Accepts a class (instantiated with no args), a zero-arg callable
    factory, or an already-instantiated adapter. The adapter must
    have a ``name`` attribute matching the manifest contribution.
    """
    if isinstance(target, type):
        adapter = target()
    elif callable(target) and not hasattr(target, "bind"):
        adapter = target()
    else:
        adapter = target
    adapter_name = getattr(adapter, "name", None)
    if adapter_name != expected_name:
        raise ValueError(
            f"adapter {expected_name!r} factory returned an adapter named "
            f"{adapter_name!r}; manifest contribution name and adapter.name must match"
        )
    return adapter


class PluginLoader:
    """Resolve, wrap, register: tools + adapters from a ``PluginSpec``.

    ``__init__(tool_registry, adapter_registry, guards=None)`` accepts
    the master registries the loader writes into. The optional
    ``guards`` map (plugin_name -> CapabilityGuard) lets the lifespan
    inject pre-built guards; when absent the loader constructs a
    fresh ``CapabilityGuard(spec.name, spec.capability_names)`` on
    demand per spec.

    ``load(spec)`` is the only public method. It returns a
    ``PluginLoadResult`` and never raises.
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        adapter_registry: AdapterRegistry,
        guards: dict[str, CapabilityGuard] | None = None,
    ) -> None:
        self._tool_registry = tool_registry
        self._adapter_registry = adapter_registry
        self._guards: dict[str, CapabilityGuard] = guards if guards is not None else {}

    def _guard_for(self, spec: PluginSpec) -> CapabilityGuard:
        if spec.name in self._guards:
            return self._guards[spec.name]
        capability_names = tuple(c.name for c in spec.capabilities)
        guard = CapabilityGuard(spec.name, capability_names)
        self._guards[spec.name] = guard
        return guard

    def load(self, spec: PluginSpec) -> PluginLoadResult:
        """Resolve every entry point, wrap, register; rollback on error.

        The method runs in three logical steps:

        1. **Resolve & materialize** — for each ``(name, entry_point)``
           in ``spec.tool_entries`` / ``spec.adapter_entries``, import
           the dotted path and coerce the target into a ``Tool`` or
           adapter instance.
        2. **Wrap & register** — wrap the tool handler through the
           per-plugin ``CapabilityGuard`` (pass-through in Phase 42),
           then call ``tool_registry.register(wrapped, replace=False)``
           or ``adapter_registry.register(adapter.name)``. Track every
           successful registration in a rollback list.
        3. **Rollback-on-error** — if any step raises, walk the
           rollback list in reverse and call
           ``tool_registry.unregister(name)`` for tools (the
           ``AdapterRegistry`` has no ``unregister`` in v0.5; the
           loader flips the adapter to ``mark_error`` with a
           ``"rolled back"`` prefix until Phase 43 adds a true
           ``unregister``). Return ``status='error'`` with the
           canonical ``error_phase='load'``.

        Tool name-collision against an already-registered tool is the
        Pitfall 3 attribution case: ``ToolRegistry.register`` raises
        ``ValueError("Tool {name!r} is already registered")``; the
        loader catches and surfaces that text verbatim in
        ``result.error``.
        """
        registered_tools: list[Tool] = []
        registered_adapter_names: list[str] = []
        guard = self._guard_for(spec)

        try:
            for tool_name, entry_point in spec.tool_entries:
                target = _resolve_entry_point(entry_point)
                tool = _materialize_tool(target, tool_name)
                if tool.handler is not None:
                    wrapped_handler = guard.wrap_tool_handler(tool.handler)
                    tool = dataclasses.replace(tool, handler=wrapped_handler)
                self._tool_registry.register(tool, replace=False)
                registered_tools.append(tool)

            for adapter_name, entry_point in spec.adapter_entries:
                target = _resolve_entry_point(entry_point)
                adapter = _materialize_adapter(target, adapter_name)
                self._adapter_registry.register(adapter.name)
                registered_adapter_names.append(adapter.name)

        except Exception as exc:
            # Rollback in reverse registration order.
            for tool in reversed(registered_tools):
                self._tool_registry.unregister(tool.name)
            for adapter_name in reversed(registered_adapter_names):
                self._adapter_registry.mark_error(
                    adapter_name,
                    f"rolled back: {type(exc).__name__}: {exc}",
                )
            return PluginLoadResult(
                status="error",
                error_phase="load",
                error=f"{type(exc).__name__}: {exc}",
                registered_tools=(),
                registered_adapters=(),
            )

        return PluginLoadResult(
            status="loaded",
            error_phase=None,
            error=None,
            registered_tools=tuple(t.name for t in registered_tools),
            registered_adapters=tuple(registered_adapter_names),
        )


__all__ = [
    "LOAD_PHASE_ORDER",
    "PluginLoadResult",
    "PluginLoader",
]
