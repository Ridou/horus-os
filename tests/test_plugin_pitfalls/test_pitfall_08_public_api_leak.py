"""Pitfall 8: The reference plugin is either too simple to teach or too coupled to internals.

See .planning/research/PITFALLS.md §"Pitfall 8" for the documented
threat. Plugin authors should import everything they need from
``horus_os.plugins.api`` and nothing from internal modules. Drift in
the public ``__all__`` of that module — silently adding or removing
names — leaks internals or breaks third-party plugins.

The Phase 41/43 ``__all__`` of ``horus_os.plugins.api`` is the
canonical surface for plugin authors. This regression test pins the
exact set down so any change requires both an explicit edit here AND
a docs update — a forced docs/code review trip wire.

The Phase 48 ruff custom rule banning ``from horus_os`` imports
outside ``horus_os.plugins.api`` in the reference plugin is OUT OF
SCOPE for this test (that's TEST-21's scope); this test only enforces
the public API SHAPE.

Phase 46 deviation note (Rule 1): the plan claimed the canonical set
is 10 names (including ``CapabilityGuard`` and ``PermissionDenied``);
the actual ``__all__`` (per ``src/horus_os/plugins/api.py``) is 8
names. ``CapabilityGuard`` is wired through ``PluginContext.guard``
for plugin authors who want to introspect; ``PermissionDenied`` is
catchable via a second-tier import from ``horus_os.plugins``. The
test asserts the ACTUAL surface so it actually serves as a tripwire
against drift.

Two structural assertions:

1. ``horus_os.plugins.api.__all__`` equals the canonical 8-name set
   exactly (no extras, no missing).
2. ``from horus_os.plugins.api import *`` exposes exactly the names in
   ``__all__`` (no private helpers, no transitive imports leak).
"""

from __future__ import annotations

import horus_os.plugins.api as plugin_api

# Canonical Phase 41/43 surface. Bump deliberately if a new public
# name lands — and update docs/PLUGINS.md in the same PR.
CANONICAL_PUBLIC_API: frozenset[str] = frozenset(
    {
        "Adapter",
        "AdapterContext",
        "Capability",
        "LifecycleAdapter",
        "PluginContext",
        "PluginSpec",
        "Tool",
        "require_capability",
    }
)


def test_public_api_all_matches_canonical_set() -> None:
    """``horus_os.plugins.api.__all__`` MUST equal the canonical set."""
    actual = frozenset(plugin_api.__all__)
    assert actual == CANONICAL_PUBLIC_API, (
        f"Pitfall 8: horus_os.plugins.api.__all__ drift.\n"
        f"  canonical: {sorted(CANONICAL_PUBLIC_API)}\n"
        f"  actual:    {sorted(actual)}\n"
        f"  missing:   {sorted(CANONICAL_PUBLIC_API - actual)}\n"
        f"  extra:     {sorted(actual - CANONICAL_PUBLIC_API)}\n"
        "Update CANONICAL_PUBLIC_API + docs/PLUGINS.md together."
    )


def test_wildcard_import_exposes_only_all_names() -> None:
    """``from horus_os.plugins.api import *`` MUST expose exactly ``__all__``."""
    namespace: dict[str, object] = {}
    exec("from horus_os.plugins.api import *", namespace)
    # Drop builtins that exec() injects.
    namespace.pop("__builtins__", None)
    public_names = {n for n in namespace if not n.startswith("_")}
    assert public_names == CANONICAL_PUBLIC_API, (
        f"Pitfall 8: wildcard import surface drift.\n"
        f"  __all__:        {sorted(CANONICAL_PUBLIC_API)}\n"
        f"  import * names: {sorted(public_names)}\n"
        "An internal helper leaked into the public surface."
    )


def test_every_all_name_resolves_to_non_none_attribute() -> None:
    """Every name in ``__all__`` resolves to a non-None attribute on the module."""
    for name in plugin_api.__all__:
        value = getattr(plugin_api, name, None)
        assert value is not None, (
            f"Pitfall 8: horus_os.plugins.api.{name} resolves to None — "
            "broken public surface."
        )
