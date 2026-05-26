"""Capability guard for plugin tool handlers.

Phase 42 ships a pass-through stub. Phase 43 swaps
``wrap_tool_handler`` for the real default-deny enforcement at this
exact wrap site without changing the wrap call signature in
``PluginLoader``. The Phase 43 enforcement raises ``PermissionDenied``
when any of ``self._capabilities`` lacks a ``granted`` row in the
``plugin_capabilities`` SQLite table; until then, every wrapped
handler runs exactly as the plugin author wrote it.

The wrap site is intentionally narrow: the loader calls
``CapabilityGuard.wrap_tool_handler(tool.handler)`` exactly once per
tool at plugin-load time and stores the returned callable on the
``Tool`` dataclass that ultimately gets handed to
``ToolRegistry.register``. Any callsite that reaches the handler later
(through ``ToolRegistry.invoke``, the agent loop's tool dispatch, the
dashboard's tool-invocation surface) goes through the wrapped
callable, so Phase 43's enforcement covers every entry path.

This design is documented in ``.planning/research/ARCHITECTURE.md``
Pattern 2 (the Discover → Validate → Permission → Load → Start →
Stop lifecycle); see ``LOAD_PHASE_ORDER`` in
``src/horus_os/plugins/loader.py`` for the canonical phase tuple.
"""

from __future__ import annotations

from collections.abc import Callable


class CapabilityGuard:
    """Per-plugin guard that wraps tool handlers with permission checks.

    ``__init__(plugin_name, capabilities)`` stores both for use in
    Phase 43. In Phase 42 the stored capability tuple is informational
    only — ``wrap_tool_handler`` returns the handler unchanged.

    Phase 43 will read ``plugin_capabilities.state`` rows for
    ``self._plugin_name`` and raise ``PermissionDenied`` from the
    wrapper if any required capability lacks a ``granted`` row.
    """

    __slots__ = ("_capabilities", "_plugin_name")

    def __init__(self, plugin_name: str, capabilities: tuple[str, ...]) -> None:
        self._plugin_name = plugin_name
        self._capabilities = tuple(capabilities)

    @property
    def plugin_name(self) -> str:
        return self._plugin_name

    @property
    def capabilities(self) -> tuple[str, ...]:
        return self._capabilities

    def wrap_tool_handler(self, handler: Callable[..., object]) -> Callable[..., object]:
        """Return a wrapped tool handler that enforces this plugin's capability grants.

        Phase 42: pass-through stub. The handler is returned unchanged
        so loaded plugins can call their tools without the permission
        layer being in place yet.

        Phase 43: the returned wrapper will call
        ``PermissionGate.check(self._plugin_name, self._capabilities)``
        before delegating to ``handler``; on missing-grant it raises
        ``PermissionDenied`` from the wrapper and the agent loop's
        existing ``ToolResult.error`` capture surfaces the failure to
        the dashboard. The wrap_tool_handler **signature stays the
        same**: a single ``handler`` argument in, a single callable out.
        """
        # Phase 43 wires real enforcement (default-deny on missing grant rows
        # in the plugin_capabilities table). Keep this comment marker in place
        # so reviewers (and grep) can locate the Phase 42 stub site.
        return handler


__all__ = ["CapabilityGuard"]
