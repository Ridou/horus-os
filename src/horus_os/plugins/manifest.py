"""Manifest reader, pydantic v2 schema, and plain-English error formatter.

The single entry point for plugin authors is ``validate_manifest(toml_bytes)``
which:

1. Parses the bytes via ``tomllib`` (stdlib).
2. Emits a ``UserWarning`` for every unknown top-level key (Pitfall 2
   forward-compat rule — a v2-authored manifest still loads on a v0.5
   horus-os, with warnings).
3. Runs the parsed dict through ``MANIFEST_V1_SCHEMA.model_validate``
   (pydantic v2). Failures raise ``pydantic.ValidationError``.
4. Translates the validated model into a frozen ``PluginSpec``
   (see ``horus_os.plugins.spec``).
5. Computes a sorted, dedup'd sha256 over the capability set and
   attaches it as ``manifest_hash`` — Phase 43's permission gate
   re-computes and compares to detect upgrade-time capability-set
   changes.

``format_validation_error(exc)`` turns a pydantic ``ValidationError``
into a multi-line plain-English string. Each line follows the shape::

    manifest field <dotted-loc>: <plain-English message>; got <repr(input)>

Used by the installer (Phase 44) to surface validation failures
verbatim to the user without leaking pydantic internals.

``compute_manifest_hash(capabilities)`` is a pure, side-effect-free
sha256 over the sorted capability set. Capability-order-independent
and duplicate-tolerant.

This module is NOT part of the public plugin API surface (see
Pitfall 8 / Phase 48). Plugin authors import from
``horus_os.plugins.api`` only; ``MANIFEST_V1_SCHEMA`` is consumed by
horus-os internals (installer, discovery, dashboard).
"""

from __future__ import annotations

import hashlib
import re
import tomllib
import warnings
from collections.abc import Iterable

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    ValidationError,
    field_validator,
)

from horus_os.plugins.capability_catalog import Capability
from horus_os.plugins.spec import CapabilityRequest, PluginSpec

MANIFEST_VERSION = 1


# --- Submodels -------------------------------------------------------------


class ContributionEntry(BaseModel):
    """One tool or adapter contributed by a plugin.

    ``name`` is a lowercase-ASCII identifier scoped within the plugin
    (uniqueness against built-ins is enforced later by Phase 42's
    loader). ``entry_point`` is a dotted-path import string with an
    optional ``:Symbol`` suffix.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    entry_point: str = Field(
        pattern=r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*(:[A-Za-z_][A-Za-z0-9_]*)?$"
    )


class ManifestContributions(BaseModel):
    """The plugin's tool + adapter contribution tables."""

    model_config = ConfigDict(extra="forbid")

    tools: list[ContributionEntry] = Field(default_factory=list)
    adapters: list[ContributionEntry] = Field(default_factory=list)


# --- Top-level schema ------------------------------------------------------


class MANIFEST_V1_SCHEMA(BaseModel):
    """pydantic v2 schema for ``horus-plugin.toml`` at manifest_version=1.

    Unknown top-level fields are silently dropped (``extra='ignore'``);
    ``validate_manifest`` issues a ``UserWarning`` for each before
    handing the dict to ``model_validate`` so plugin authors get a
    forward-compat hint without their plugin failing to load.
    """

    model_config = ConfigDict(extra="ignore")

    manifest_version: int
    name: str
    version: str
    description: str
    author: str
    license: str
    horus_os_compat: str
    contributions: ManifestContributions = Field(default_factory=ManifestContributions)
    capabilities: list[str] = Field(default_factory=list)
    homepage: HttpUrl | None = None
    issue_tracker: HttpUrl | None = None

    @field_validator("manifest_version")
    @classmethod
    def _check_manifest_version(cls, value: int) -> int:
        if value != MANIFEST_VERSION:
            raise ValueError(
                f"manifest_version={value} not supported by horus-os 0.5; please upgrade"
            )
        return value

    @field_validator("name")
    @classmethod
    def _check_name(cls, value: str) -> str:
        if not re.match(r"^[a-z][a-z0-9-]*$", value):
            raise ValueError(
                f"'name' must be lowercase ASCII letters/digits/hyphens; got {value!r}"
            )
        return value

    @field_validator("version")
    @classmethod
    def _check_version(cls, value: str) -> str:
        try:
            Version(value)
        except InvalidVersion as exc:
            raise ValueError(f"'version' is not a valid PEP 440 version; got {value!r}") from exc
        return value

    @field_validator("description")
    @classmethod
    def _check_description(cls, value: str) -> str:
        if len(value) > 200:
            raise ValueError(f"'description' must be ≤200 chars; got {len(value)} chars")
        return value

    @field_validator("author")
    @classmethod
    def _check_author(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("'author' must not be empty")
        return value

    @field_validator("license")
    @classmethod
    def _check_license(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("'license' must not be empty")
        return value

    @field_validator("horus_os_compat")
    @classmethod
    def _check_compat(cls, value: str) -> str:
        try:
            SpecifierSet(value)
        except InvalidSpecifier as exc:
            raise ValueError(
                "'horus_os_compat' is not a valid PEP 440 specifier set "
                f"(see packaging.specifiers.SpecifierSet); got {value!r}"
            ) from exc
        return value

    @field_validator("capabilities")
    @classmethod
    def _check_capabilities(cls, value: list[str]) -> list[str]:
        allowed = {c.value for c in Capability}
        for cap in value:
            if cap not in allowed:
                allowed_str = ", ".join(sorted(allowed))
                raise ValueError(
                    f"capability {cap!r} is not a member of the Capability catalog "
                    f"(allowed: {allowed_str})"
                )
        return value


# --- Public functions ------------------------------------------------------


def validate_manifest(toml_bytes: bytes) -> PluginSpec:
    """Parse a ``horus-plugin.toml`` payload and return a frozen ``PluginSpec``.

    Raises:
        tomllib.TOMLDecodeError: on malformed TOML.
        pydantic.ValidationError: on shape failure (missing required
            field, wrong type, value-validator rejection).

    Issues a ``UserWarning`` for every unknown top-level key in the
    parsed payload (Pitfall 2 forward-compat rule). The unknown key
    is then dropped from the validated model (``extra='ignore'``).
    """
    payload = tomllib.loads(toml_bytes.decode("utf-8"))
    known_fields = set(MANIFEST_V1_SCHEMA.model_fields.keys())
    for key in payload:
        if key not in known_fields:
            warnings.warn(
                f"unknown manifest field {key!r}; this field is ignored under "
                f"manifest_version={MANIFEST_VERSION}",
                UserWarning,
                stacklevel=2,
            )
    validated = MANIFEST_V1_SCHEMA.model_validate(payload)

    # Translate validated capabilities into the runtime tuple shape.
    capability_requests = tuple(
        CapabilityRequest(name=cap_name, reason="") for cap_name in validated.capabilities
    )
    tool_entries = tuple((c.name, c.entry_point) for c in validated.contributions.tools)
    adapter_entries = tuple((c.name, c.entry_point) for c in validated.contributions.adapters)
    manifest_hash = compute_manifest_hash(validated.capabilities)

    return PluginSpec(
        name=validated.name,
        version=validated.version,
        description=validated.description,
        author=validated.author,
        license=validated.license,
        horus_os_compat=validated.horus_os_compat,
        homepage=str(validated.homepage) if validated.homepage is not None else None,
        issue_tracker=(
            str(validated.issue_tracker) if validated.issue_tracker is not None else None
        ),
        tool_entries=tool_entries,
        adapter_entries=adapter_entries,
        capabilities=capability_requests,
        source="filesystem",
        source_detail="",
        manifest_hash=manifest_hash,
    )


# Pydantic type-code -> humanized message. Unhandled codes fall back to
# the verbatim pydantic message. The full set of pydantic type codes is
# enumerated at https://docs.pydantic.dev/latest/errors/validation_errors/
_HUMANIZED_TYPE_MESSAGES: dict[str, str] = {
    "missing": "field is required",
    "string_type": "must be a string",
    "int_type": "must be an integer",
    "list_type": "must be a list",
    "dict_type": "must be a table",
    "url_parsing": "must be a valid URL",
    "url_scheme": "URL scheme is not allowed",
    "url_type": "must be a valid URL",
    "string_pattern_mismatch": "does not match the required pattern",
    "value_error": None,  # use the underlying error message verbatim
    "extra_forbidden": "unexpected field; not allowed here",
}


def format_validation_error(exc: ValidationError) -> str:
    """Return a multi-line plain-English summary of a pydantic ``ValidationError``.

    Each error line follows the shape::

        manifest field <dotted-loc>: <plain-English message>; got <repr(input)>

    where ``<dotted-loc>`` is the ``loc`` tuple joined with ``.`` and
    ``<repr(input)>`` is the raw input value truncated to 80 chars.
    """
    lines: list[str] = []
    for error in exc.errors():
        loc_parts: list[str] = []
        for part in error.get("loc", ()):
            loc_parts.append(str(part))
        loc = ".".join(loc_parts) if loc_parts else "<root>"

        type_code = error.get("type", "")
        humanized = _HUMANIZED_TYPE_MESSAGES.get(type_code)
        if humanized is None:
            humanized = error.get("msg", "validation failed")

        raw_input = error.get("input", "")
        input_repr = repr(raw_input)
        if len(input_repr) > 80:
            input_repr = input_repr[:77] + "..."

        lines.append(f"manifest field {loc}: {humanized}; got {input_repr}")
    return "\n".join(lines)


def compute_manifest_hash(capabilities: Iterable[str]) -> str:
    """Return sha256(sorted set of capabilities) as hex.

    Deterministic, capability-order-independent, duplicate-tolerant.
    Phase 43's ``plugin_capabilities.manifest_hash`` column persists
    this value; the permission gate re-computes it on upgrade and
    flips state to ``'pending'`` on mismatch.
    """
    sorted_caps = sorted(set(str(c) for c in capabilities))
    payload = "\n".join(sorted_caps).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


__all__ = [
    "MANIFEST_V1_SCHEMA",
    "MANIFEST_VERSION",
    "ContributionEntry",
    "ManifestContributions",
    "compute_manifest_hash",
    "format_validation_error",
    "validate_manifest",
]
