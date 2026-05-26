"""Pydantic v2 response models for the Phase 45 plugin REST surface.

Five frozen models pin the wire contract for the six ``/api/plugins/*``
routes and the new ``/api/observability/plugins`` route. Every model
uses ``ConfigDict(extra='forbid', frozen=True)`` so a typo in a route
handler raises ``ValidationError`` at response-serialization time
instead of silently shipping a malformed body.

Models, in surface order:

* ``PluginInfo`` -- the list-row shape returned by ``GET /api/plugins``.
* ``PluginInfoDetailed`` -- extends ``PluginInfo`` with the last 20
  ``plugin_capability_grants_log`` rows for the named plugin.
* ``PluginCapabilityState`` -- a single capability + state pair, with
  the plain-English description from ``capability_catalog.DESCRIPTIONS``.
  Used inside ``PluginInfoDetailed`` for the per-capability roll-up.
* ``PluginGrantLogEntry`` -- one audit-log row from
  ``plugin_capability_grants_log``. The ``action`` and ``actor`` columns
  are constrained by SQLite CHECK constraints (action IN
  ('granted','revoked','pending_on_upgrade'); actor IN
  ('cli','dashboard','system')); we mirror those constraints as
  ``Literal`` types so a typo in a handler fails Pydantic validation
  before the row reaches the response.
* ``PluginObservabilityRollup`` -- per-plugin rollup row from
  ``observability/queries.py::per_plugin_rollup``. Carries the Pitfall
  10 (n<10 -> None) and Pitfall 11 (NULL cost stays None, never 0)
  contracts via ``int | None`` and ``float | None`` typings.

Pydantic is required runtime for the dashboard extra; this module is
only imported from ``server.plugins_api`` which is itself only
imported when ``create_app`` runs (FastAPI is already required at that
layer), so there is no risk of imposing pydantic on the core CLI.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PluginGrantLogEntry(BaseModel):
    """One row from ``plugin_capability_grants_log``.

    Wire contract:
      * ``capability`` -- the dotted capability string from the closed
        ``capability_catalog.Capability`` enum.
      * ``action`` -- one of ``granted`` / ``revoked`` / ``pending_on_upgrade``.
      * ``actor`` -- one of ``cli`` / ``dashboard`` / ``system``.
      * ``manifest_hash`` -- the manifest hash at the time of the
        transition; carried forward on revoke so the history shows which
        manifest the revocation applied to.
      * ``timestamp`` -- ISO 8601 UTC string.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    capability: str = Field(description="Dotted capability string (e.g. 'filesystem.read')")
    action: Literal["granted", "revoked", "pending_on_upgrade"] = Field(
        description="The transition recorded in this audit-log row"
    )
    actor: Literal["cli", "dashboard", "system"] = Field(
        description="Who initiated the transition; matches the SQLite CHECK constraint"
    )
    manifest_hash: str = Field(description="Manifest hash at the time of this transition")
    timestamp: str = Field(description="ISO 8601 UTC timestamp")


class PluginCapabilityState(BaseModel):
    """A single (capability, state) pair surfaced by the detail endpoint.

    Used inside ``PluginInfoDetailed`` so the dashboard can render a
    chip per capability with the granted / pending state and the
    plain-English description that the installer's grant prompt uses.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    capability: str = Field(description="Dotted capability string")
    state: Literal["granted", "pending", "revoked"] = Field(
        description="Current persisted state in plugin_capabilities"
    )
    description: str = Field(
        description="Plain-English description from capability_catalog.DESCRIPTIONS"
    )


class PluginInfo(BaseModel):
    """List-row shape returned by ``GET /api/plugins``.

    Wire contract notes:
      * For ``status='pending'`` entries that pre-date the load pipeline
        (or for DiscoveryError-only rows where ``spec`` is None on the
        registry side), ``version`` is ``''`` and all spec-derived
        tuples are empty -- a deliberate "this plugin failed before
        validation; surface it but render the empty fields gracefully"
        contract.
      * ``last_error`` is truncated to the first 200 chars (Pitfall 6
        message hygiene); the full message stays in the registry +
        plugin_status table.
      * ``manifest_homepage`` / ``manifest_issue_tracker`` are nullable
        because the manifest schema allows them to be absent. The
        dashboard gates each on ``startsWith('http://')`` /
        ``startsWith('https://')`` before rendering as an ``<a>`` tag
        (T-45-07 URL-injection mitigation).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(description="Plugin name (matches plugins.name in SQLite)")
    version: str = Field(
        default="",
        description="Plugin version; '' when the registry entry has spec=None",
    )
    status: Literal["pending", "loaded", "error", "disabled"] = Field(
        description="Current runtime status from PluginRegistry"
    )
    error_phase: str | None = Field(
        default=None,
        description=(
            "Phase of the load pipeline where the error occurred "
            "('discover'|'validate'|'permission'|'load'|'start'|'stop'); "
            "None when status != 'error'"
        ),
    )
    last_error: str | None = Field(
        default=None,
        description=(
            "First 200 chars of the most recent error message; None when "
            "status != 'error'. Truncated for Pitfall 6 message hygiene."
        ),
    )
    declared_tools: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Tool names this plugin contributed at load time (empty for non-loaded)",
    )
    declared_adapters: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Adapter names this plugin contributed at load time (empty for non-loaded)",
    )
    granted_capabilities: tuple[str, ...] = Field(
        default_factory=tuple,
        description=(
            "Capability strings the PermissionGate resolved as granted for the "
            "current manifest_hash; empty when spec is None or no caps are granted"
        ),
    )
    pending_capabilities: tuple[str, ...] = Field(
        default_factory=tuple,
        description=(
            "Capability strings the PermissionGate resolved as pending "
            "(default-deny, manifest-hash mismatch, or explicitly revoked)"
        ),
    )
    enabled: bool = Field(description="plugins.enabled column; False when admin-disabled")
    manifest_homepage: str | None = Field(
        default=None,
        description="Manifest homepage URL; None when the manifest omitted the field",
    )
    manifest_issue_tracker: str | None = Field(
        default=None,
        description="Manifest issue tracker URL; None when the manifest omitted the field",
    )
    manifest_author: str = Field(
        default="",
        description="Manifest author string; empty when the registry entry has spec=None",
    )


class PluginInfoDetailed(PluginInfo):
    """Detail-row shape returned by ``GET /api/plugins/{name}``.

    Extends ``PluginInfo`` with the last 20 rows of
    ``plugin_capability_grants_log`` for the named plugin, newest first.
    The cap is hard-coded in the route handler's SQL ``LIMIT 20``; this
    schema documents the wire contract.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    grants_log: tuple[PluginGrantLogEntry, ...] = Field(
        default_factory=tuple,
        description="Last 20 plugin_capability_grants_log rows, newest first",
    )


class PluginObservabilityRollup(BaseModel):
    """Per-plugin rollup row returned by ``GET /api/observability/plugins``.

    Wire contract notes:
      * ``plugin_name`` -- the literal string ``'horus-os core'`` for the
        bucket that aggregates NULL ``plugin_name`` rows.
      * ``error_rate`` -- None (not 0.0) when the denominator is 0 (no
        success or error rows in the window); rounded to 4dp otherwise.
      * ``latency_p50_ms`` / ``latency_p95_ms`` -- None when
        ``total_invocations < 10`` (Pitfall 10); the render rule is
        applied in Python BEFORE serialization so the dashboard receives
        null rather than a misleading small-sample number.
      * ``total_cost_usd`` -- None (not 0.0) when SUM is NULL across all
        rows in the window for the plugin (Pitfall 11 honesty contract).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    plugin_name: str = Field(
        description="Plugin name; 'horus-os core' for the NULL bucket"
    )
    total_invocations: int = Field(description="Count of tool_invocations rows in the window")
    error_rate: float | None = Field(
        description=(
            "status='error' / (success+error); rounded to 4dp; None when "
            "denominator is 0 (no observed success or error rows)"
        )
    )
    latency_p50_ms: int | None = Field(
        description="50th percentile latency in ms; None when total_invocations < 10"
    )
    latency_p95_ms: int | None = Field(
        description="95th percentile latency in ms; None when total_invocations < 10"
    )
    total_cost_usd: float | None = Field(
        description=(
            "SUM(cost_usd) across the plugin's llm_calls in the window, rounded "
            "to 6dp; None (not 0.0) when SUM is NULL; matches Pitfall 11"
        )
    )


__all__ = [
    "PluginCapabilityState",
    "PluginGrantLogEntry",
    "PluginInfo",
    "PluginInfoDetailed",
    "PluginObservabilityRollup",
]
