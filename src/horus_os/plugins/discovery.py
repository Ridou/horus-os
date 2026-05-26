"""Plugin discovery from entry points + filesystem.

``discover_plugins()`` walks two sources in a fixed order:

1. ``importlib.metadata.entry_points(group='horus_os.plugins')`` — the
   canonical path for pip-installed plugins. Each ``EntryPoint``'s
   ``.dist`` provides the distribution metadata; the ``horus-plugin.toml``
   payload is read via ``importlib.resources.files(<dist>)``.
2. A filesystem walk of ``$HOME/.horus-os/plugins/`` (overridable via
   the ``HORUS_OS_PLUGIN_DIR`` env var or the ``extra_paths`` argument).
   Each subdirectory is one plugin; ``horus-plugin.toml`` lives at the
   subdir root; the Python package shares the subdir.

Dedup precedence is entry_points > filesystem; a name collision emits
a ``UserWarning`` naming both source paths so the user can audit which
copy is being preferred (Pitfall 6 attribution rule).

The function NEVER raises out: every per-source exception is caught
and routed to a parallel ``list[DiscoveryError]``. The two-list return
shape lets the FastAPI lifespan register failed plugins as
``status="error"`` rows in the registry alongside the validated specs.

The ``entry_points`` name is rebound at module level (line below the
imports) so tests can monkeypatch the discovery source without touching
``importlib`` internals. This mirrors ``src/horus_os/adapters/base.py:22``
verbatim.

``pkg_resources`` is NEVER imported here (directly or transitively).
The ruff banned-api rule + ``tests/plugins/test_pkg_resources_banned.py``
provide two layers of defense against the 1.3-1.5s import-overhead
foot-gun (Pitfall 3).
"""

from __future__ import annotations

import importlib.resources
import os
import tomllib
import warnings
from dataclasses import dataclass, replace
from importlib.metadata import entry_points
from pathlib import Path

from pydantic import ValidationError

from horus_os.plugins.manifest import format_validation_error, validate_manifest
from horus_os.plugins.spec import PluginSpec

PLUGIN_ENTRY_POINT_GROUP = "horus_os.plugins"
DEFAULT_FILESYSTEM_PLUGIN_DIR = Path.home() / ".horus-os" / "plugins"
PLUGIN_MANIFEST_FILENAME = "horus-plugin.toml"


@dataclass(frozen=True)
class DiscoveryError:
    """One plugin source that failed to discover or validate.

    ``error_phase`` is constrained to ``"discover"`` (TOML parse failure
    or missing manifest file) or ``"validate"`` (manifest shape failure
    via pydantic). The FastAPI lifespan registers a ``status="error"``
    PluginRegistry row for each ``DiscoveryError``; the dashboard and
    ``/api/plugins`` surface them with their error_phase intact.

    ``name`` is the best-effort plugin name from the failing source —
    the entry-point name (for entry_points sources) or the directory
    name (for filesystem sources). It may not match a real plugin's
    ``name`` field if the manifest itself never parsed.
    """

    name: str
    source: str
    source_detail: str
    error_phase: str
    error_message: str


def _read_entry_point_manifest_bytes(ep: object) -> bytes:
    """Resolve ``horus-plugin.toml`` bytes for an entry point.

    Tests monkeypatch this function with a name-keyed lookup; the
    real implementation reaches through the entry point's distribution
    via ``importlib.resources`` so the manifest can live alongside the
    plugin package without requiring a separate filesystem walk.

    Splitting this off into a module-level function (rather than
    inlining it inside ``discover_plugins``) keeps the test seam tight
    while leaving ``discover_plugins`` itself free of importlib.resources
    internals.
    """
    dist = getattr(ep, "dist", None)
    if dist is None:
        raise FileNotFoundError(
            f"entry point {getattr(ep, 'name', '<unknown>')!r} has no distribution metadata"
        )
    dist_name = getattr(dist, "name", None) or getattr(dist, "metadata", {}).get("Name")
    if not dist_name:
        raise FileNotFoundError(
            f"entry point {getattr(ep, 'name', '<unknown>')!r} distribution lacks a name"
        )
    return importlib.resources.files(dist_name).joinpath(PLUGIN_MANIFEST_FILENAME).read_bytes()


def _validate_with_source(toml_bytes: bytes, *, source: str, source_detail: str) -> PluginSpec:
    """Run ``validate_manifest`` and rewrite the spec's source attribution.

    ``validate_manifest`` hardcodes ``source="filesystem"`` /
    ``source_detail=""`` because it is pure data; the caller (this
    module) knows whether the manifest came from an entry point or a
    filesystem walk, so it overrides via ``dataclasses.replace``.
    """
    spec = validate_manifest(toml_bytes)
    return replace(spec, source=source, source_detail=source_detail)


def _discover_entry_points() -> tuple[list[PluginSpec], list[DiscoveryError]]:
    """Walk the ``horus_os.plugins`` entry point group."""
    specs: list[PluginSpec] = []
    errors: list[DiscoveryError] = []

    try:
        eps = list(entry_points(group=PLUGIN_ENTRY_POINT_GROUP))
    except Exception:
        # An importlib bug or a malformed dist-info should not crash
        # discovery; surface as an empty walk.
        return specs, errors

    for ep in sorted(eps, key=lambda e: getattr(e, "name", "")):
        ep_name = getattr(ep, "name", "<unknown>")
        source_detail = getattr(ep, "value", "") or ep_name
        try:
            toml_bytes = _read_entry_point_manifest_bytes(ep)
        except Exception as exc:
            errors.append(
                DiscoveryError(
                    name=ep_name,
                    source="entry_point",
                    source_detail=source_detail,
                    error_phase="discover",
                    error_message=f"{type(exc).__name__}: {exc}",
                )
            )
            continue
        try:
            spec = _validate_with_source(
                toml_bytes, source="entry_point", source_detail=source_detail
            )
        except tomllib.TOMLDecodeError as exc:
            errors.append(
                DiscoveryError(
                    name=ep_name,
                    source="entry_point",
                    source_detail=source_detail,
                    error_phase="discover",
                    error_message=f"TOMLDecodeError: {exc}",
                )
            )
            continue
        except ValidationError as exc:
            errors.append(
                DiscoveryError(
                    name=ep_name,
                    source="entry_point",
                    source_detail=source_detail,
                    error_phase="validate",
                    error_message=format_validation_error(exc),
                )
            )
            continue
        except Exception as exc:
            # Anything else (bad encoding, unexpected runtime error from
            # the validator) — still contain. ISOLATE-01.
            errors.append(
                DiscoveryError(
                    name=ep_name,
                    source="entry_point",
                    source_detail=source_detail,
                    error_phase="validate",
                    error_message=f"{type(exc).__name__}: {exc}",
                )
            )
            continue
        specs.append(spec)
    return specs, errors


def _filesystem_roots(extra_paths: list[Path] | None) -> list[Path]:
    """Resolve the ordered list of filesystem roots to walk.

    Priority: explicit ``extra_paths`` arg (first), then
    ``HORUS_OS_PLUGIN_DIR`` env var if set, else
    ``DEFAULT_FILESYSTEM_PLUGIN_DIR``. Non-existent paths are silently
    skipped — a fresh install with no plugin directory is the happy
    path that the cold-start benchmark requires.
    """
    roots: list[Path] = []
    if extra_paths:
        roots.extend(Path(p).expanduser() for p in extra_paths)
    env_override = os.environ.get("HORUS_OS_PLUGIN_DIR")
    if env_override:
        roots.append(Path(env_override).expanduser())
    else:
        roots.append(DEFAULT_FILESYSTEM_PLUGIN_DIR)
    # Dedup while preserving order.
    seen: set[Path] = set()
    deduped: list[Path] = []
    for root in roots:
        resolved = root.resolve() if root.exists() else root
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append(root)
    return deduped


def _discover_filesystem(
    extra_paths: list[Path] | None,
) -> tuple[list[PluginSpec], list[DiscoveryError]]:
    """Walk each filesystem root and treat every subdirectory as one plugin."""
    specs: list[PluginSpec] = []
    errors: list[DiscoveryError] = []

    for root in _filesystem_roots(extra_paths):
        if not root.exists() or not root.is_dir():
            continue
        for subdir in sorted(root.iterdir()):
            if not subdir.is_dir():
                continue
            manifest_path = subdir / PLUGIN_MANIFEST_FILENAME
            source_detail = str(manifest_path)
            if not manifest_path.exists():
                # A subdir without a manifest is not a plugin candidate;
                # silently skip (matches the entry_points-walk semantics
                # of "no manifest = nothing to discover").
                continue
            subdir_name = subdir.name
            try:
                toml_bytes = manifest_path.read_bytes()
            except Exception as exc:
                errors.append(
                    DiscoveryError(
                        name=subdir_name,
                        source="filesystem",
                        source_detail=source_detail,
                        error_phase="discover",
                        error_message=f"{type(exc).__name__}: {exc}",
                    )
                )
                continue
            try:
                spec = _validate_with_source(
                    toml_bytes, source="filesystem", source_detail=source_detail
                )
            except tomllib.TOMLDecodeError as exc:
                errors.append(
                    DiscoveryError(
                        name=subdir_name,
                        source="filesystem",
                        source_detail=source_detail,
                        error_phase="discover",
                        error_message=f"TOMLDecodeError: {exc}",
                    )
                )
                continue
            except ValidationError as exc:
                errors.append(
                    DiscoveryError(
                        name=subdir_name,
                        source="filesystem",
                        source_detail=source_detail,
                        error_phase="validate",
                        error_message=format_validation_error(exc),
                    )
                )
                continue
            except Exception as exc:
                errors.append(
                    DiscoveryError(
                        name=subdir_name,
                        source="filesystem",
                        source_detail=source_detail,
                        error_phase="validate",
                        error_message=f"{type(exc).__name__}: {exc}",
                    )
                )
                continue
            specs.append(spec)
    return specs, errors


def discover_plugins(
    extra_paths: list[Path] | None = None,
) -> tuple[list[PluginSpec], list[DiscoveryError]]:
    """Discover plugins from entry points and the filesystem.

    Returns a ``(specs, errors)`` pair:

    * ``specs`` — validated ``PluginSpec`` objects, deduplicated by
      ``spec.name``. When a name appears in both sources the
      entry-point version wins; the filesystem duplicate is dropped
      and a ``UserWarning`` is emitted naming both source paths.
    * ``errors`` — one ``DiscoveryError`` per source that failed to
      parse the TOML or validate against ``MANIFEST_V1_SCHEMA``.

    The function NEVER raises out. Lifespan callers register every
    error as a ``status="error"`` plugin in the registry and continue
    booting (ISOLATE-01).

    ``extra_paths`` (optional) prepends additional filesystem roots
    before the default ``HORUS_OS_PLUGIN_DIR``/``~/.horus-os/plugins``
    walk. Tests use this to scope the walk to ``tmp_path``.
    """
    entry_specs, entry_errors = _discover_entry_points()
    fs_specs, fs_errors = _discover_filesystem(extra_paths)

    # Dedup: entry_point precedence.
    by_name: dict[str, PluginSpec] = {}
    for spec in entry_specs:
        by_name[spec.name] = spec
    for spec in fs_specs:
        existing = by_name.get(spec.name)
        if existing is not None:
            warnings.warn(
                (
                    f"plugin {spec.name!r} discovered from both an entry point "
                    f"({existing.source_detail!r}) and a filesystem source "
                    f"({spec.source_detail!r}); the entry point wins."
                ),
                UserWarning,
                stacklevel=2,
            )
            continue
        by_name[spec.name] = spec

    specs = sorted(by_name.values(), key=lambda s: s.name)
    errors = entry_errors + fs_errors
    return specs, errors


__all__ = [
    "DEFAULT_FILESYSTEM_PLUGIN_DIR",
    "PLUGIN_ENTRY_POINT_GROUP",
    "PLUGIN_MANIFEST_FILENAME",
    "DiscoveryError",
    "discover_plugins",
]
