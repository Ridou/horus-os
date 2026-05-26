"""Frozen dataclasses describing a validated plugin's spec.

These are the post-validation runtime objects: ``PluginSpec`` is what
``validate_manifest()`` returns after consuming a ``horus-plugin.toml``
payload, and ``CapabilityRequest`` is the per-capability slot that
Phase 43's permission gate consumes.

Pure data; zero I/O. The dataclasses are intentionally trivial to
construct from a synthetic dict so tests do not need a real filesystem
manifest to exercise downstream code paths.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CapabilityRequest:
    """A single capability the plugin requests at install time.

    The ``name`` is the string value of a ``capability_catalog.Capability``
    enum member (e.g. ``"filesystem.read"``). The ``reason`` is the
    plain-English justification the installer surfaces to the user at
    grant prompt time. The three optional refinement tuples (paths,
    hosts, keys) carry the per-capability scope arguments — empty in
    v0.5, populated later when the manifest schema adds those fields.
    """

    name: str
    reason: str = ""
    paths: tuple[str, ...] = field(default_factory=tuple)
    hosts: tuple[str, ...] = field(default_factory=tuple)
    keys: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PluginSpec:
    """A validated plugin's full identity + contributions + capability set.

    Returned by ``validate_manifest()`` after the pydantic ``MANIFEST_V1_SCHEMA``
    accepts a ``horus-plugin.toml`` payload. Phase 42's ``discover_plugins()``
    returns ``list[PluginSpec]``; Phase 43's ``PermissionGate`` reads the
    ``capabilities`` tuple and ``manifest_hash`` field; Phase 45's REST
    routes serialize this dataclass directly.
    """

    name: str
    version: str
    description: str
    author: str
    license: str
    horus_os_compat: str
    homepage: str | None
    issue_tracker: str | None
    tool_entries: tuple[tuple[str, str], ...]
    adapter_entries: tuple[tuple[str, str], ...]
    capabilities: tuple[CapabilityRequest, ...]
    source: str
    source_detail: str
    manifest_hash: str
