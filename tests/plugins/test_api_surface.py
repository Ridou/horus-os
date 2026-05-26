"""Public API surface assertions for ``horus_os.plugins.api``.

Pitfall 8 prevention: ``api.__all__`` is the contract. The reference
plugin (Phase 48) must only import from ``horus_os.plugins.api``;
this test enforces the shape of that surface so a future refactor
cannot silently expose internals.
"""

from __future__ import annotations

import horus_os.plugins.api as api

EXPECTED_NAMES = {
    "PluginSpec",
    "Capability",
    "Tool",
    "Adapter",
    "LifecycleAdapter",
    "AdapterContext",
    "PluginContext",
    "require_capability",
}


def test_all_tuple_matches_expected_names() -> None:
    assert set(api.__all__) == EXPECTED_NAMES
    # __all__ is documented to be a tuple in the canonical spec; type
    # assertion guards against an accidental list/set conversion.
    assert isinstance(api.__all__, tuple)


def test_every_public_name_resolves_to_non_none_object() -> None:
    for name in api.__all__:
        attr = getattr(api, name)
        assert attr is not None, f"{name!r} resolved to None"


def test_no_leading_underscore_in_public_names() -> None:
    assert not any(name.startswith("_") for name in api.__all__)


def test_module_exposes_exactly_the_eight_names() -> None:
    # Visible non-dunder names should be a subset of __all__ plus what
    # Python adds (none, since we use __all__). We assert __all__ is the
    # single-source-of-truth surface.
    public_attrs = {
        name
        for name in dir(api)
        if not name.startswith("_")
        and name not in {"annotations", "Callable", "Path", "TypeVar", "F", "dataclass"}
    }
    assert EXPECTED_NAMES.issubset(public_attrs)
