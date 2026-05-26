"""Inline factories for test_loader.py's partial-registration cases.

Kept as a sibling module (not under ``tests/fixtures/``) so the tests
that exercise loader edge cases can reference real Python entry points
without scattering loader-only helpers across the broken_plugins/
fixture directory (which is reserved for full TEST-19 plugins).
"""

from typing import Any

from horus_os.types import Tool


def make_new_tool() -> Tool:
    """Factory used in the partial-rollback test."""
    return Tool(
        name="new_tool",
        description="newly contributed tool that gets rolled back",
        parameters={"type": "object", "properties": {}},
        handler=lambda **_kw: "new",
    )


def make_non_tool() -> Any:
    """Factory that returns the wrong type — TypeError expected at materialization."""
    return {"not": "a Tool"}


def make_mismatched_tool() -> Tool:
    """Factory whose returned Tool name does not match the manifest contribution."""
    return Tool(
        name="actual_name",
        description="name mismatch test",
        parameters={"type": "object", "properties": {}},
        handler=lambda **_kw: None,
    )
