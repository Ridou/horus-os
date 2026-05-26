"""DISCOVERY-01 + DISCOVERY-02 coverage for discover_plugins().

Cases exercised:

* zero installed plugins -> ``discover_plugins()`` returns ``([], [])``.
* one entry-point plugin (via ``fake_plugin_entry_points``) -> spec
  with ``source='entry_point'``.
* one filesystem plugin (via ``tmp_plugin_dir`` +
  ``install_broken_fixture('healthy')``) -> spec with
  ``source='filesystem'``.
* BOTH entry-point and filesystem source the same plugin name ->
  entry-point wins; UserWarning carries both source paths.
* entry-point whose manifest bytes are unreadable -> DiscoveryError
  with ``error_phase='discover'``.
* filesystem plugin with malformed TOML -> DiscoveryError with
  ``error_phase='discover'``.
* filesystem plugin with valid TOML but unknown capability ->
  DiscoveryError with ``error_phase='validate'``.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from horus_os.plugins import discover_plugins
from horus_os.plugins.discovery import (
    DEFAULT_FILESYSTEM_PLUGIN_DIR,
    PLUGIN_ENTRY_POINT_GROUP,
)

# Reference: the closed-source healthy fixture manifest mirrors the
# tests/fixtures/broken_plugins/healthy fixture (control plugin).
_HEALTHY_MANIFEST_BYTES = b"""manifest_version = 1
name = "healthy"
version = "0.1.0"
description = "Healthy plugin used in discovery tests."
author = "horus-os contributors"
license = "Apache-2.0"
horus_os_compat = ">=0.5,<0.6"
capabilities = ["filesystem.read"]

[[contributions.tools]]
name = "hello_tool"
entry_point = "tests.fixtures.broken_plugins.healthy:make_tool"
"""

_UNKNOWN_CAPABILITY_MANIFEST_BYTES = b"""manifest_version = 1
name = "unknown-cap"
version = "0.1.0"
description = "Declares a capability not in the catalog."
author = "horus-os contributors"
license = "Apache-2.0"
horus_os_compat = ">=0.5,<0.6"
capabilities = ["gpu.cuda_access"]
"""

_BAD_TOML_BYTES = b'name = "broken-toml\nversion = "0.1.0"\n'


def test_constants_have_expected_shape() -> None:
    """The module-level rebind seam exposes the expected constants."""
    assert PLUGIN_ENTRY_POINT_GROUP == "horus_os.plugins"
    assert isinstance(DEFAULT_FILESYSTEM_PLUGIN_DIR, Path)
    # The default points at $HOME/.horus-os/plugins; do not assert the
    # absolute path because tests run on multiple machines.
    assert DEFAULT_FILESYSTEM_PLUGIN_DIR.name == "plugins"


def test_zero_installed_plugins_returns_empty(
    fake_plugin_entry_points,
    tmp_plugin_dir: Path,
) -> None:
    specs, errors = discover_plugins()
    assert specs == []
    assert errors == []


def test_one_entry_point_plugin_discovers(fake_plugin_entry_points) -> None:
    fake_plugin_entry_points.inject(
        [("healthy", "tests.fixtures.broken_plugins.healthy", _HEALTHY_MANIFEST_BYTES)]
    )
    specs, errors = discover_plugins()
    assert errors == []
    assert len(specs) == 1
    spec = specs[0]
    assert spec.name == "healthy"
    assert spec.source == "entry_point"
    # source_detail tracks the entry point's .value attribute.
    assert spec.source_detail == "tests.fixtures.broken_plugins.healthy"


def test_one_filesystem_plugin_discovers(
    fake_plugin_entry_points,
    tmp_plugin_dir: Path,
    install_broken_fixture,
) -> None:
    dst = install_broken_fixture("healthy")
    specs, errors = discover_plugins()
    assert errors == []
    assert len(specs) == 1
    spec = specs[0]
    assert spec.name == "healthy"
    assert spec.source == "filesystem"
    assert str(dst / "horus-plugin.toml") == spec.source_detail


def test_dedup_entry_point_wins_over_filesystem_with_warning(
    fake_plugin_entry_points,
    tmp_plugin_dir: Path,
    install_broken_fixture,
) -> None:
    """When both sources surface the same name, entry_point wins.

    A UserWarning is emitted naming both source paths so the user can
    audit which copy was preferred (Pitfall 6).
    """
    fake_plugin_entry_points.inject(
        [("healthy", "tests.fixtures.broken_plugins.healthy", _HEALTHY_MANIFEST_BYTES)]
    )
    install_broken_fixture("healthy")

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        specs, errors = discover_plugins()

    assert errors == []
    assert len(specs) == 1
    assert specs[0].source == "entry_point"

    # Find the dedup warning (others may fire too).
    dedup_warnings = [w for w in captured if "discovered from both" in str(w.message)]
    assert len(dedup_warnings) == 1
    msg = str(dedup_warnings[0].message)
    assert "healthy" in msg
    assert "entry point" in msg
    assert "filesystem" in msg


def test_entry_point_with_unreadable_manifest_is_contained(
    fake_plugin_entry_points,
) -> None:
    """When the manifest-bytes resolver raises, the failure surfaces as a DiscoveryError.

    The conftest's ``inject`` wires a lookup against entry-point names;
    if we inject a name but DON'T register manifest bytes for it, the
    resolver raises ``FileNotFoundError`` — discovery must catch it.
    """
    # Manually wire an entry without manifest bytes by going around inject.
    # The simplest path: register a manifest and then patch the helper to raise.
    fake_plugin_entry_points.inject([("broken-ep", "broken_ep.module", _HEALTHY_MANIFEST_BYTES)])
    # Replace the manifest-bytes resolver with one that always raises.
    import horus_os.plugins.discovery as discovery_module

    def _always_raise(ep: object) -> bytes:
        raise FileNotFoundError("no manifest for this entry point")

    saved = discovery_module._read_entry_point_manifest_bytes
    discovery_module._read_entry_point_manifest_bytes = _always_raise
    try:
        specs, errors = discover_plugins()
    finally:
        discovery_module._read_entry_point_manifest_bytes = saved

    assert specs == []
    assert len(errors) == 1
    err = errors[0]
    assert err.name == "broken-ep"
    assert err.source == "entry_point"
    assert err.error_phase == "discover"


def test_filesystem_plugin_with_invalid_toml_is_contained(
    fake_plugin_entry_points,
    tmp_plugin_dir: Path,
    install_broken_fixture,
) -> None:
    """Filesystem plugin with malformed TOML -> error_phase='discover'."""
    install_broken_fixture("bad_toml")

    specs, errors = discover_plugins()
    assert specs == []
    assert len(errors) == 1
    err = errors[0]
    assert err.name == "bad_toml"
    assert err.source == "filesystem"
    assert err.error_phase == "discover"
    # The error message names the parser.
    assert "TOMLDecodeError" in err.error_message


def test_filesystem_plugin_with_unknown_capability_is_contained(
    fake_plugin_entry_points,
    tmp_plugin_dir: Path,
    install_broken_fixture,
) -> None:
    """Filesystem plugin whose manifest validates against a closed catalog miss.

    The schema_fail fixture declares capabilities=['gpu.cuda_access'];
    pydantic ValidationError fires and discovery routes it to
    error_phase='validate' without raising.
    """
    install_broken_fixture("schema_fail")

    specs, errors = discover_plugins()
    assert specs == []
    assert len(errors) == 1
    err = errors[0]
    assert err.name == "schema_fail"
    assert err.source == "filesystem"
    assert err.error_phase == "validate"


def test_explicit_extra_paths_arg_takes_precedence(
    fake_plugin_entry_points,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``extra_paths`` arg lets a caller scope the walk without setting HORUS_OS_PLUGIN_DIR.

    Useful for tests that want to skip the env-var monkeypatch entirely.
    """
    # Make sure neither the env var nor the default dir exist.
    monkeypatch.delenv("HORUS_OS_PLUGIN_DIR", raising=False)
    extra_dir = tmp_path / "extra_plugins"
    extra_dir.mkdir()
    # Drop a healthy plugin into extra_dir.
    plugin_dir = extra_dir / "healthy"
    plugin_dir.mkdir()
    (plugin_dir / "horus-plugin.toml").write_bytes(_HEALTHY_MANIFEST_BYTES)
    # Stub the default dir off the host's real path so the test is
    # hermetic even when ~/.horus-os/plugins/ exists for the user.
    import horus_os.plugins.discovery as discovery_module

    monkeypatch.setattr(discovery_module, "DEFAULT_FILESYSTEM_PLUGIN_DIR", tmp_path / "absent")

    specs, errors = discover_plugins(extra_paths=[extra_dir])
    assert errors == []
    assert len(specs) == 1
    assert specs[0].name == "healthy"


def test_entry_point_with_invalid_toml_is_contained(
    fake_plugin_entry_points,
) -> None:
    """Entry-point manifest bytes that fail TOML parsing -> error_phase='discover'."""
    fake_plugin_entry_points.inject([("bad-ep", "bad_ep.module", _BAD_TOML_BYTES)])
    specs, errors = discover_plugins()
    assert specs == []
    assert len(errors) == 1
    err = errors[0]
    assert err.name == "bad-ep"
    assert err.source == "entry_point"
    assert err.error_phase == "discover"


def test_entry_point_with_unknown_capability_is_contained(
    fake_plugin_entry_points,
) -> None:
    """Entry-point manifest with bad capability -> error_phase='validate'."""
    fake_plugin_entry_points.inject(
        [("unknown-cap", "unknown_cap.module", _UNKNOWN_CAPABILITY_MANIFEST_BYTES)]
    )
    specs, errors = discover_plugins()
    assert specs == []
    assert len(errors) == 1
    err = errors[0]
    assert err.name == "unknown-cap"
    assert err.source == "entry_point"
    assert err.error_phase == "validate"


def test_discover_plugins_never_raises_on_unexpected_validator_failure(
    fake_plugin_entry_points,
) -> None:
    """A surprise exception from validate_manifest is contained.

    Bug-bears: a future validate_manifest could raise UnicodeDecodeError
    or some other unanticipated type. The discovery walk swallows it
    and routes it to error_phase='validate' instead of crashing.
    """
    fake_plugin_entry_points.inject([("surprise", "surprise.module", _HEALTHY_MANIFEST_BYTES)])

    import horus_os.plugins.discovery as discovery_module

    def _always_raise(*_args, **_kwargs):
        raise UnicodeDecodeError("utf-8", b"", 0, 1, "surprise")

    saved = discovery_module._validate_with_source
    discovery_module._validate_with_source = _always_raise
    try:
        specs, errors = discover_plugins()
    finally:
        discovery_module._validate_with_source = saved

    assert specs == []
    assert len(errors) == 1
    assert errors[0].error_phase == "validate"
    assert "UnicodeDecodeError" in errors[0].error_message
