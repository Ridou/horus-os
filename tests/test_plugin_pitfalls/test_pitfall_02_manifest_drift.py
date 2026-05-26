"""Pitfall 2: Manifest schema drift — adding a v2 field silently breaks every v1 plugin OR silently underuses every v2 plugin.

See .planning/research/PITFALLS.md §"Pitfall 2" for the documented
forward-compat rule. The prevention pattern: unknown top-level fields
in a v1 manifest emit a ``UserWarning`` and are then dropped
(``extra='ignore'`` on the pydantic schema). An unsupported
``manifest_version`` raises a typed validation error with a clear
plain-English message — never a silent acceptance, never a stack
trace dump.

Four structural assertions:

1. The minimum-valid v1 fixture (``manifest_v1_minimum.toml``) parses
   cleanly via ``validate_manifest`` and produces a valid spec.
2. A manifest carrying an UNKNOWN top-level key emits a
   ``UserWarning`` with ``"unknown manifest field"`` in the message
   AND still returns a valid spec (the unknown field is dropped).
3. A manifest with ``manifest_version=2`` raises a pydantic
   ``ValidationError`` carrying ``"manifest_version=2 not supported"``
   in the message.
4. Round-trip stability: loading the same fixture twice yields specs
   that compare equal (the frozen dataclass + deterministic
   ``manifest_hash`` make this trivially true, but the assertion
   pins it down so a refactor cannot silently destabilize the
   manifest_hash computation).

Phase 46 deviation note (Rule 1): the plan specified ``ManifestError``
for the v2 case, but the production code raises
``pydantic.ValidationError`` (the validator uses the ``@field_validator``
hook, not a custom exception class). Adapting the test to match
production: the assertion stays — unsupported manifest_version refuses
loud with a clear plain-English message — but the exception type is
the pydantic-native one.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest
from pydantic import ValidationError

from horus_os.plugins.manifest import validate_manifest

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_MIN = REPO_ROOT / "tests" / "fixtures" / "manifests" / "manifest_v1_minimum.toml"


def test_minimum_v1_manifest_parses_cleanly() -> None:
    """The bundled minimum-valid v1 fixture round-trips through validate_manifest."""
    assert MANIFEST_MIN.exists(), f"missing fixture: {MANIFEST_MIN}"
    toml_bytes = MANIFEST_MIN.read_bytes()
    spec = validate_manifest(toml_bytes)
    assert spec.name == "horus-os-test-minimum"
    assert spec.version == "0.1.0"
    assert len(spec.capabilities) == 1
    assert spec.capabilities[0].name == "filesystem.read"


def test_unknown_v1_field_emits_userwarning_and_still_parses() -> None:
    """Unknown top-level fields warn but still produce a valid spec."""
    toml_bytes = (
        b"manifest_version = 1\n"
        b'name = "test-unknown-field"\n'
        b'version = "0.1.0"\n'
        b'description = "Tests forward-compat unknown-field warning."\n'
        b'author = "horus-os contributors"\n'
        b'license = "Apache-2.0"\n'
        b'horus_os_compat = ">=0.5,<0.6"\n'
        b"capabilities = []\n"
        b'signing_key_fingerprint = "abc123"\n'  # unknown field
    )
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        spec = validate_manifest(toml_bytes)
    # The fingerprint field was dropped but the spec is valid.
    assert spec.name == "test-unknown-field"
    # At least one UserWarning mentioning the unknown field.
    matching = [
        w
        for w in captured
        if issubclass(w.category, UserWarning) and "unknown manifest field" in str(w.message)
    ]
    assert matching, f"expected unknown-field UserWarning; captured: {captured}"


def test_manifest_version_2_refuses_with_clear_message() -> None:
    """An unsupported manifest_version=2 raises ValidationError with a clear message."""
    toml_bytes = (
        b"manifest_version = 2\n"
        b'name = "test-v2"\n'
        b'version = "0.1.0"\n'
        b'description = "Forward manifest_version test."\n'
        b'author = "horus-os contributors"\n'
        b'license = "Apache-2.0"\n'
        b'horus_os_compat = ">=0.5,<0.6"\n'
        b"capabilities = []\n"
    )
    with pytest.raises(ValidationError) as excinfo:
        validate_manifest(toml_bytes)
    assert "manifest_version=2 not supported" in str(excinfo.value)


def test_manifest_round_trip_stability() -> None:
    """Loading the same fixture twice produces equal specs (deterministic hash)."""
    toml_bytes = MANIFEST_MIN.read_bytes()
    spec_a = validate_manifest(toml_bytes)
    spec_b = validate_manifest(toml_bytes)
    assert spec_a == spec_b
    assert spec_a.manifest_hash == spec_b.manifest_hash
