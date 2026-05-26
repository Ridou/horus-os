"""Capability catalog closure and description coverage tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from horus_os.plugins.capability_catalog import DESCRIPTIONS, Capability
from horus_os.plugins.manifest import MANIFEST_V1_SCHEMA


def test_every_capability_member_has_description() -> None:
    assert set(DESCRIPTIONS.keys()) == set(Capability)


def test_minimum_members_present() -> None:
    values = {c.value for c in Capability}
    assert {
        "filesystem.read",
        "filesystem.write",
        "net.outbound",
        "secrets.read",
    }.issubset(values)


def test_descriptions_are_non_empty_strings() -> None:
    for cap, desc in DESCRIPTIONS.items():
        assert isinstance(desc, str)
        assert desc.strip() != "", f"{cap!r} has empty description"


def test_unknown_capability_in_manifest_payload_is_refused() -> None:
    """Building MANIFEST_V1_SCHEMA with a string outside the catalog fails."""
    payload = {
        "manifest_version": 1,
        "name": "horus-os-test",
        "version": "0.1.0",
        "description": "x",
        "author": "y",
        "license": "Apache-2.0",
        "horus_os_compat": ">=0.5,<0.6",
        "capabilities": ["not.a.real.capability"],
    }
    with pytest.raises(ValidationError) as exc_info:
        MANIFEST_V1_SCHEMA.model_validate(payload)
    assert any(
        "not.a.real.capability" in str(err.get("msg", "")) for err in exc_info.value.errors()
    )


def test_capability_is_a_str_enum() -> None:
    """The closed-enum guard: ``Capability`` members ARE strings."""
    assert Capability.FILESYSTEM_READ == "filesystem.read"
    # And membership is closed: there is no constructor that accepts arbitrary values.
    with pytest.raises(ValueError):
        Capability("nonsense.value")
