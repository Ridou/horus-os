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

from pydantic import BaseModel, ConfigDict, Field, field_validator


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

    plugin_name: str = Field(description="Plugin name; 'horus-os core' for the NULL bucket")
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


# ----------------------------------------------------------------------
# v0.7 dashboard response models
#
# These pin the wire contract for the read-only dashboard surface served
# by ``server.dashboard_api``. Every field name and shape here mirrors
# ``frontend/lib/types.ts`` exactly; a typo in a handler raises
# ``ValidationError`` at serialization time instead of shipping a body
# the dashboard cannot parse. ``extra='forbid'`` keeps the contract
# closed; ``frozen=True`` matches the plugin models above.
# ----------------------------------------------------------------------


class TeamAgent(BaseModel):
    """One agent summary row returned by ``GET /api/team``.

    Mirrors the ``Agent`` interface in ``frontend/lib/types.ts``. ``status``
    is derived from recent trace activity (``active`` when the agent has a
    trace in the last 24h, ``idle`` otherwise); the dashboard treats the
    field as an open string from the ``AgentStatus`` union.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(description="Agent display name and unique profile key")
    color: str = Field(description="Hex accent color, e.g. '#00d4ff'; '' when unset")
    description: str = Field(description="One-line summary of the agent; '' when unset")
    default_model: str | None = Field(
        default=None, description="Default model id, or null to inherit the configured default"
    )
    soul_path: str = Field(
        description="notes_dir-relative path to the SOUL.md persona; '' when unset"
    )
    status: str = Field(description="'active' (trace in last 24h) or 'idle'")
    trace_count: int = Field(description="Number of traces attributed to this agent")
    last_active_at: str | None = Field(
        default=None, description="Max created_at over the agent's traces (ISO 8601 UTC), or null"
    )


class TeamResponse(BaseModel):
    """``GET /api/team`` envelope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    agents: tuple[TeamAgent, ...] = Field(description="All agent profiles, ordered by name")


class TraceSummary(BaseModel):
    """A trace summary attached to an agent detail. Mirrors ``TraceSummary``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    trace_id: str = Field(description="Trace id")
    created_at: str = Field(description="ISO 8601 UTC creation timestamp")
    prompt: str = Field(description="The prompt that started the trace")
    status: str = Field(description="Trace status string")


class AgentDetail(TeamAgent):
    """Full agent detail: the team fields plus the resolved system prompt.

    Mirrors ``AgentDetail`` in ``frontend/lib/types.ts`` (extends ``Agent``).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    system_prompt: str = Field(description="The agent's resolved system prompt")


class AgentDetailResponse(BaseModel):
    """``GET /api/team/{name}`` envelope. Mirrors ``AgentDetailResponse``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    agent: AgentDetail = Field(description="The full agent detail record")
    soul_markdown: str | None = Field(
        default=None, description="Contents of the SOUL.md persona file, or null when absent"
    )
    recent_traces: tuple[TraceSummary, ...] = Field(
        description="The agent's most recent traces, newest first"
    )


class MemoryNote(BaseModel):
    """A memory note summary. Mirrors ``MemoryNote`` in types.ts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(description="notes_dir-relative path to the note")
    title: str = Field(description="Note title (first H1 or the file stem)")
    size_bytes: int = Field(description="File size in bytes")
    modified_at: str = Field(description="ISO 8601 UTC modification timestamp")
    preview: str = Field(description="Leading slice of the note body")


class MemoryResponse(BaseModel):
    """``GET /api/memory`` envelope. Mirrors ``MemoryResponse``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    notes: tuple[MemoryNote, ...] = Field(description="Matching notes")


class MemoryNoteDetail(BaseModel):
    """``GET /api/memory/note`` body. Mirrors ``MemoryNoteDetail``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(description="notes_dir-relative path to the note")
    title: str = Field(description="Note title (first H1 or the file stem)")
    markdown: str = Field(description="The full markdown body of the note")
    modified_at: str = Field(description="ISO 8601 UTC modification timestamp")
    is_example: bool = Field(
        default=False,
        description="True when this note was seeded by horus-os init as example content",
    )


class TaskRow(BaseModel):
    """One task row returned by ``GET /api/tasks``. Mirrors ``Task`` in types.ts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str = Field(description="Unique task identifier")
    title: str = Field(description="Short task title")
    description: str = Field(description="Full task description")
    status: str = Field(
        description="Task status: pending | running | completed | error | cancelled"
    )
    agent_profile_name: str | None = Field(
        default=None, description="Agent assigned to this task, or null when unassigned"
    )
    created_at: str = Field(description="ISO 8601 UTC creation timestamp")
    updated_at: str = Field(description="ISO 8601 UTC last-update timestamp")


class TasksResponse(BaseModel):
    """``GET /api/tasks`` envelope. Mirrors ``TasksResponse`` in types.ts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tasks: tuple[TaskRow, ...] = Field(description="All tasks, newest first")


class ActivityEvent(BaseModel):
    """A single activity-feed event. Mirrors ``ActivityEvent``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    trace_id: str = Field(description="Trace id this event was derived from")
    created_at: str = Field(description="ISO 8601 UTC creation timestamp")
    agent: str = Field(description="Agent name, or 'default' when unattributed")
    kind: str = Field(description="Event kind; 'agent_run' for trace-derived events")
    summary: str = Field(description="Short slice of the prompt")
    status: str = Field(description="Trace status string")


class ActivityResponse(BaseModel):
    """``GET /api/activity`` envelope. Mirrors ``ActivityResponse``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    events: tuple[ActivityEvent, ...] = Field(description="Recent activity events, newest first")


class HealthResponse(BaseModel):
    """``GET /api/health`` body. Mirrors ``HealthResponse`` in types.ts.

    Degrades gracefully when the database file does not yet exist:
    ``db_size_bytes`` and every count fall back to ``0`` rather than
    raising, so the endpoint always answers 200.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str = Field(description="Always 'ok' when the server is responding")
    version: str = Field(description="horus-os package version")
    db_size_bytes: int = Field(description="Size of the SQLite file in bytes; 0 when missing")
    trace_count: int = Field(description="Total trace rows")
    note_count: int = Field(description="Total markdown notes under notes_dir")
    agent_count: int = Field(description="Total agent profiles")


class SettingsCounts(BaseModel):
    """The ``counts`` sub-object on the settings response."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    agents: int = Field(description="Total agent profiles")
    notes: int = Field(description="Total markdown notes under notes_dir")
    traces: int = Field(description="Total trace rows")


class KeyWriteRequest(BaseModel):
    """Request body for POST /api/integrations/{name}/keys.

    Carries exactly one field: the credential value to persist.
    The value is never echoed back in any response.
    extra='forbid' prevents a handler typo from accidentally
    widening the body with a secret-bearing field.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    value: str = Field(
        min_length=1,
        description="The credential value to persist (never echoed back)",
    )

    @field_validator("value")
    @classmethod
    def no_newlines(cls, v: str) -> str:
        """Reject values containing newline characters to prevent .env injection."""
        if "\n" in v or "\r" in v:
            raise ValueError("credential value must not contain newline characters")
        return v


class KeyWriteResponse(BaseModel):
    """Response body for POST /api/integrations/{name}/keys.

    Contains only an ok flag. The credential value is never included
    in this response or any error message.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    ok: bool = Field(description="True on success; never contains the credential value")


class VerifyResponse(BaseModel):
    """Response body for POST /api/integrations/{name}/verify.

    Returns pass/fail without echoing the credential value or any
    material that could reveal the credential in error messages.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    ok: bool = Field(description="True when the probe succeeded")
    error: str | None = Field(
        default=None,
        description="Error description when ok=False; never contains the credential value",
    )


class IntegrationStatus(BaseModel):
    """One integration connector row returned by GET /api/integrations.

    status is never the env var value - only a derived state label.
    extra='forbid' prevents a handler typo from accidentally widening
    the body with a secret-bearing field.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(description="Connector slug, e.g. 'anthropic'")
    name: str = Field(description="Display name, e.g. 'Anthropic'")
    category: str = Field(description="Connector category, e.g. 'AI Provider'")
    description: str = Field(description="One-line summary of what the connector unlocks")
    status: Literal["verified", "configured-unverified", "missing", "error"] = Field(
        description="Live status derived from env var presence only; never the value itself"
    )
    env_var: str = Field(description="Primary env var NAME (not its value)")
    required_vars: tuple[str, ...] = Field(
        description="All env var NAMES required for this integration (names only, never values)"
    )
    credential_portal_url: str = Field(
        description="External deep-link for obtaining the credential"
    )


class IntegrationsResponse(BaseModel):
    """GET /api/integrations envelope. Mirrors IntegrationsResponse in types.ts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    integrations: tuple[IntegrationStatus, ...] = Field(
        description="All 10 integration connectors with live configured status"
    )
    demo_mode: bool = Field(description="True when HORUS_OS_DEMO=1 is set server-side")


class VercelStatusResponse(BaseModel):
    """Body for GET /api/integrations/vercel/status (VERCEL-03, D-05).

    The server reads HORUS_OS_VERCEL_TOKEN, calls the Vercel REST
    deployments API, and returns ONLY the derived, browser-safe status.
    The token NEVER appears in this body. ``extra='forbid'`` guarantees a
    handler typo cannot widen the response with a token-bearing field, and
    ``error`` carries the exception class NAME only (type(exc).__name__),
    never ``str(exc)`` which could echo request material.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    configured: bool = Field(
        description="True when HORUS_OS_VERCEL_TOKEN is set server-side; never the token value"
    )
    state: str | None = Field(
        default=None,
        description="Latest deployment state label (e.g. READY); never the token value",
    )
    url: str | None = Field(
        default=None,
        description="Latest deployment URL; a public deploy URL, never the token value",
    )
    created_at: str | None = Field(
        default=None,
        description="Latest deployment creation timestamp as a string; never the token value",
    )
    error: str | None = Field(
        default=None,
        description="Exception class name only when the probe fails; never str(exc) or the token",
    )


class SettingsResponse(BaseModel):
    """``GET /api/settings`` body: read-only, non-sensitive config only.

    This model deliberately carries NO API keys, environment secrets, or
    any other sensitive value. Local filesystem paths are the user's own
    and are safe to surface. ``extra='forbid'`` guarantees a handler
    cannot accidentally widen the body with a secret-bearing field.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    data_dir: str = Field(description="Installation data directory")
    notes_dir: str = Field(description="Markdown notes (vault) directory")
    db_path: str = Field(description="SQLite database path")
    default_provider: str = Field(description="Configured default LLM provider")
    anthropic_model: str = Field(description="Configured default Anthropic model")
    gemini_model: str = Field(description="Configured default Gemini model")
    schema_version: int = Field(description="SQLite schema version the runtime targets")
    version: str = Field(description="horus-os package version")
    counts: SettingsCounts = Field(description="Live row/file counts")


__all__ = [
    "ActivityEvent",
    "ActivityResponse",
    "AgentDetail",
    "AgentDetailResponse",
    "HealthResponse",
    "IntegrationStatus",
    "IntegrationsResponse",
    "KeyWriteRequest",
    "KeyWriteResponse",
    "MemoryNote",
    "MemoryNoteDetail",
    "MemoryResponse",
    "PluginCapabilityState",
    "PluginGrantLogEntry",
    "PluginInfo",
    "PluginInfoDetailed",
    "PluginObservabilityRollup",
    "SettingsCounts",
    "SettingsResponse",
    "TaskRow",
    "TasksResponse",
    "TeamAgent",
    "TeamResponse",
    "TraceSummary",
    "VercelStatusResponse",
    "VerifyResponse",
]
