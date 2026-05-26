"""MANIFEST-01..05 coverage for ``horus_os.plugins.manifest``.

The five TOML fixtures under ``tests/fixtures/manifests/`` exercise both
the happy path (minimum + full) and the three documented failure modes
(missing manifest_version, unknown capability, invalid horus_os_compat).
Two stand-alone tests cover Pitfall 2 forward-compat (unknown top-level
field emits ``UserWarning``) and the canonical manifest_version mismatch
message.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest
from pydantic import ValidationError

from horus_os.plugins.manifest import (
    MANIFEST_VERSION,
    format_validation_error,
    validate_manifest,
)
from horus_os.plugins.spec import PluginSpec

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "manifests"


def _read(name: str) -> bytes:
    return (FIXTURE_DIR / name).read_bytes()


# --- Passing fixtures ------------------------------------------------------


def test_minimum_fixture_validates_and_returns_pluginspec() -> None:
    spec = validate_manifest(_read("manifest_v1_minimum.toml"))
    assert isinstance(spec, PluginSpec)
    assert spec.name == "horus-os-test-minimum"
    assert spec.version == "0.1.0"
    assert spec.horus_os_compat == ">=0.5,<0.6"
    assert spec.homepage is None
    assert spec.issue_tracker is None
    assert spec.tool_entries == (("echo", "fixture.mod:echo_tool"),)
    assert spec.adapter_entries == ()
    assert len(spec.capabilities) == 1
    assert spec.capabilities[0].name == "filesystem.read"
    assert len(spec.manifest_hash) == 64
    assert all(c in "0123456789abcdef" for c in spec.manifest_hash)


def test_full_fixture_validates_with_all_optional_fields() -> None:
    spec = validate_manifest(_read("manifest_v1_full.toml"))
    assert isinstance(spec, PluginSpec)
    assert spec.name == "horus-os-test-full"
    assert spec.version == "1.2.3"
    assert spec.horus_os_compat == ">=0.5,<0.7,!=0.5.1"
    # HttpUrl rendering may include a trailing slash; both forms are acceptable.
    assert spec.homepage is not None
    assert "github.com/example/horus-os-test-full" in spec.homepage
    assert spec.issue_tracker is not None
    assert "issues" in spec.issue_tracker
    assert len(spec.tool_entries) == 2
    assert spec.tool_entries[0] == ("alpha_tool", "example_plugin.tools:alpha")
    assert spec.tool_entries[1] == ("beta_tool", "example_plugin.tools:beta")
    assert len(spec.adapter_entries) == 2
    cap_names = {c.name for c in spec.capabilities}
    assert cap_names == {
        "filesystem.read",
        "filesystem.write",
        "net.outbound",
        "secrets.read",
    }


# --- Malformed fixtures ----------------------------------------------------


@pytest.mark.parametrize(
    "fixture_name, expected_substring",
    [
        ("manifest_v1_missing_version.toml", "manifest_version"),
        ("manifest_v1_unknown_capability.toml", "gpu.cuda_access"),
        ("manifest_v1_invalid_compat.toml", "horus_os_compat"),
    ],
)
def test_malformed_fixture_raises_validation_error(
    fixture_name: str, expected_substring: str
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        validate_manifest(_read(fixture_name))
    formatted = format_validation_error(exc_info.value)
    assert expected_substring in formatted, (
        f"Expected {expected_substring!r} in formatted error; got:\n{formatted}"
    )


def test_missing_manifest_version_error_includes_field_required_message() -> None:
    with pytest.raises(ValidationError) as exc_info:
        validate_manifest(_read("manifest_v1_missing_version.toml"))
    formatted = format_validation_error(exc_info.value)
    assert "manifest_version" in formatted
    assert "field is required" in formatted


def test_unknown_capability_error_mentions_allowed_values() -> None:
    with pytest.raises(ValidationError) as exc_info:
        validate_manifest(_read("manifest_v1_unknown_capability.toml"))
    formatted = format_validation_error(exc_info.value)
    assert "gpu.cuda_access" in formatted
    # Either humanized "value_error" message or the underlying ValueError text
    # surfaces the allowed list / catalog membership phrase.
    assert ("Capability" in formatted) or ("catalog" in formatted)


def test_invalid_compat_error_mentions_specifier_set() -> None:
    with pytest.raises(ValidationError) as exc_info:
        validate_manifest(_read("manifest_v1_invalid_compat.toml"))
    formatted = format_validation_error(exc_info.value)
    assert "horus_os_compat" in formatted
    assert "SpecifierSet" in formatted or "specifier" in formatted.lower()


# --- Pitfall 2 forward-compat ----------------------------------------------


def test_unknown_top_level_field_emits_userwarning_and_validates() -> None:
    """A v2-authored manifest with an unknown top-level field still loads
    on v0.5 horus-os, with a ``UserWarning`` per Pitfall 2 forward-compat.
    """
    payload = b"""manifest_version = 1
name = "horus-os-test-forward-compat"
version = "0.1.0"
description = "Forward-compat fixture: unknown top-level field must warn, not raise."
author = "horus-os contributors"
license = "Apache-2.0"
horus_os_compat = ">=0.5,<0.6"
signing_key_fingerprint = "deadbeef"
capabilities = ["filesystem.read"]

[[contributions.tools]]
name = "echo"
entry_point = "fixture.mod:echo_tool"
"""
    with pytest.warns(UserWarning, match="unknown manifest field 'signing_key_fingerprint'"):
        spec = validate_manifest(payload)
    assert spec.name == "horus-os-test-forward-compat"


def test_wrong_manifest_version_raises_with_canonical_message() -> None:
    """A manifest_version != MANIFEST_VERSION raises with the exact
    upgrade-hint message documented in ``<manifest_schema_canonical>``.
    """
    payload = b"""manifest_version = 2
name = "horus-os-test-future-version"
version = "0.1.0"
description = "Future-version fixture: manifest_version=2 should be refused with upgrade hint."
author = "horus-os contributors"
license = "Apache-2.0"
horus_os_compat = ">=0.5,<0.6"
capabilities = ["filesystem.read"]

[[contributions.tools]]
name = "echo"
entry_point = "fixture.mod:echo_tool"
"""
    with pytest.raises(ValidationError) as exc_info:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            validate_manifest(payload)
    formatted = format_validation_error(exc_info.value)
    assert "manifest_version=2 not supported by horus-os 0.5" in formatted
    assert "please upgrade" in formatted


# --- MANIFEST_VERSION sanity ----------------------------------------------


def test_manifest_version_constant_is_one() -> None:
    assert MANIFEST_VERSION == 1
