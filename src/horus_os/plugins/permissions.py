"""Capability guard and permission gate for plugin tool handlers.

Phase 42 shipped a pass-through ``CapabilityGuard`` stub plus a
hand-wave comment about Phase 43 swapping in real enforcement. Phase
43 lands that swap **at the same wrap site** the loader already
calls, so ``PluginLoader`` does not change shape; only the closure
returned by ``CapabilityGuard.wrap_tool_handler`` changes. A wrapped
handler whose declared ``__horus_required_caps__`` are not in the
guard's ``granted_capabilities`` set raises ``PermissionDenied``
before the underlying handler ever runs.

Five exports define the Phase 43 surface, in dependency order:

* ``DEFAULT_GRANT_POLICY = "deny"`` — module constant referenced by
  every allow/deny decision in this file. Documents the invariant
  for reviewers (so a future refactor cannot silently flip the
  default) and gives the agent loop a single grep target when
  surfacing the policy in error messages.
* ``PermissionDenied(Exception)`` — carries ``plugin_name`` and
  ``capability`` public fields. Message hygiene per PITFALLS.md
  Pitfall 6: the composed message uses ONLY the plugin name and the
  capability string (both from the closed catalog), never any
  user-supplied content from an exception body.
* ``PermissionGate`` — reads ``plugin_capabilities`` rows from the
  v6 SQLite schema and partitions a ``PluginSpec.capabilities``
  tuple into ``(granted, pending)`` sets. Manifest-hash mismatch
  (PERMISSION-02 / Pitfall 5 upgrade re-prompt) flips
  previously-granted rows into pending.
* ``CapabilityGuard`` — rewrite of the Phase 42 stub. The wrap site
  signature stays the same so ``PluginLoader._guard_for`` and
  ``PluginLoader.load`` are not touched; the closure body changes
  from pass-through to default-deny.
* ``PermissionService`` — write side. ``grant``, ``revoke``,
  ``pending_on_upgrade`` each persist a state change AND append a
  row to ``plugin_capability_grants_log`` so the dashboard
  (Phase 45) and Phase 46 pitfall-regression tests have an audit
  trail per action.

The wrap site is intentionally narrow: ``PluginLoader.load`` calls
``CapabilityGuard.wrap_tool_handler(tool.handler)`` exactly once per
tool at plugin-load time. Any callsite that reaches the handler later
(through ``ToolRegistry.invoke``, the agent loop's tool dispatch, the
dashboard's tool-invocation surface) goes through the wrapped
callable, so the enforcement covers every entry path.

This module is wired into the FastAPI lifespan via
``src/horus_os/server/api.py`` (the permission-gate check that flips
``error_phase="permission"`` lives there, between
``PluginRegistry.register`` and ``PluginLoader.load``).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from horus_os.plugins.capability_catalog import Capability

if TYPE_CHECKING:
    from horus_os.plugins.spec import PluginSpec
    from horus_os.storage import Database


# Module-level invariant. Reference this constant from every code
# path that decides allow/deny so a future refactor cannot silently
# flip the default. Documented in PERMISSION-01 success criteria.
DEFAULT_GRANT_POLICY = "deny"


_ACTION_GRANTED = "granted"
_ACTION_REVOKED = "revoked"
_ACTION_PENDING_ON_UPGRADE = "pending_on_upgrade"

_STATE_GRANTED = "granted"
_STATE_PENDING = "pending"
_STATE_REVOKED = "revoked"


class PermissionDenied(Exception):
    """Raised by a wrapped tool handler when a required capability is not granted.

    Two public fields:
      * ``plugin_name`` — the plugin whose handler tried to act.
      * ``capability`` — the capability string from the closed
        ``capability_catalog.Capability`` enum that was missing.

    Both are sourced from horus-os internals (PluginSpec.name and
    Capability.value), NEVER from a user-supplied exception body, so
    surfacing the message back to the agent loop / dashboard cannot
    leak prompt content (Pitfall 6 message hygiene).
    """

    __slots__ = ("plugin_name", "capability")

    def __init__(self, plugin_name: str, capability: str) -> None:
        self.plugin_name = plugin_name
        self.capability = capability
        super().__init__(
            f"Plugin {plugin_name!r} denied capability {capability!r}: "
            f"no granted row in plugin_capabilities (default-deny)."
        )


class PermissionGate:
    """Resolve a PluginSpec's requested capabilities against persisted grants.

    The gate is constructed once per FastAPI app boot (the lifespan
    builds it before iterating loaded specs); each ``resolve(spec)``
    call SELECTs the matching ``plugin_capabilities`` rows in a single
    parameterized query and partitions the result.

    Per-row decision matrix (PERMISSION-02 / Pitfall 5 upgrade
    re-prompt):

      * no row present → pending
      * row.state in ('pending', 'revoked') → pending
      * row.manifest_hash != spec.manifest_hash → pending
      * row.state == 'granted' AND row.manifest_hash matches → granted

    Names in spec.capabilities that are not in the closed
    ``Capability`` enum raise ``ValueError`` early via
    ``Capability(name)`` — the loader catches and routes the failure
    to ``mark_error(error_phase="permission")``.
    """

    __slots__ = ("_db",)

    def __init__(self, db: Database) -> None:
        self._db = db

    def resolve(self, spec: PluginSpec) -> tuple[set[Capability], set[Capability]]:
        """Partition ``spec.capabilities`` into ``(granted, pending)`` sets.

        The two return sets are disjoint and together cover every
        capability the spec requested. Empty granted + non-empty
        pending is the first-install case; granted == requested is
        the steady-state post-grant case; mixed sets surface in the
        Phase 44 ``update`` upgrade-diff flow.
        """
        # Resolve every requested name through the closed enum FIRST
        # so a typoed capability raises ValueError before any DB read.
        requested: set[Capability] = {Capability(c.name) for c in spec.capabilities}
        if not requested:
            return set(), set()

        # Single parameterized query: ``capability IN (?, ?, ...)``.
        placeholders = ",".join("?" for _ in requested)
        params: list[object] = [spec.name, spec.version, *(c.value for c in requested)]

        granted: set[Capability] = set()
        pending: set[Capability] = set()
        rows: dict[str, dict[str, object]] = {}
        try:
            with self._db._connect() as conn:
                cursor = conn.execute(
                    f"""
                    SELECT capability, state, manifest_hash
                    FROM plugin_capabilities
                    WHERE plugin_name = ?
                      AND plugin_version = ?
                      AND capability IN ({placeholders})
                    """,
                    params,
                )
                for row in cursor.fetchall():
                    rows[row["capability"]] = {
                        "state": row["state"],
                        "manifest_hash": row["manifest_hash"],
                    }
        except sqlite3.OperationalError:
            # Schema not present yet: every cap lands in pending,
            # consistent with default-deny.
            return set(), set(requested)

        for cap in requested:
            row = rows.get(cap.value)
            if row is None:
                pending.add(cap)
                continue
            if row["state"] != _STATE_GRANTED:
                pending.add(cap)
                continue
            if row["manifest_hash"] != spec.manifest_hash:
                # PERMISSION-02 / Pitfall 5: upgrade re-prompt.
                pending.add(cap)
                continue
            granted.add(cap)

        return granted, pending


class CapabilityGuard:
    """Per-plugin guard that wraps tool handlers with permission checks.

    Phase 43 rewrite of the Phase 42 stub. The constructor now takes
    two arguments instead of one: the plugin name AND the resolved
    granted set (a ``set[Capability]`` from ``PermissionGate.resolve``).
    The Phase 42 ``capabilities: tuple[str, ...]`` argument (the
    REQUESTED caps from the manifest) is preserved as a deprecated
    keyword alias so any Phase 42 callsite that has not yet migrated
    keeps working — the loader's ``_guard_for`` builds guards via the
    requested list when no explicit grant set is supplied, and the
    pass-through wrap_tool_handler from Phase 42 is now default-deny.

    The new authoritative field is ``granted_capabilities`` — exposed
    via the like-named property as a frozenset for stable iteration.
    """

    __slots__ = ("_capabilities", "_plugin_name", "_granted")

    def __init__(
        self,
        plugin_name: str,
        capabilities: tuple[str, ...] = (),
        *,
        granted_capabilities: set[Capability] | frozenset[Capability] | None = None,
    ) -> None:
        self._plugin_name = plugin_name
        self._capabilities = tuple(capabilities)
        self._granted: frozenset[Capability] = (
            frozenset(granted_capabilities) if granted_capabilities else frozenset()
        )

    @property
    def plugin_name(self) -> str:
        return self._plugin_name

    @property
    def capabilities(self) -> tuple[str, ...]:
        """Legacy Phase 42 alias: the REQUESTED caps from the manifest.

        Informational only in Phase 43. The authoritative field is
        ``granted_capabilities``; this property stays for back-compat
        with any callsite that has not migrated.
        """
        return self._capabilities

    @property
    def granted_capabilities(self) -> frozenset[Capability]:
        """Resolved-grant set from the PermissionGate. Source of truth for enforcement."""
        return self._granted

    def wrap_tool_handler(
        self,
        handler: Callable[..., object],
        required_cap: Capability | None = None,
    ) -> Callable[..., object]:
        """Return a wrapper that enforces default-deny on missing grants.

        Two ways to declare the required capabilities:

        * ``required_cap`` — explicit kwarg. The wrapper enforces just
          this one. Used by the helper-shim methods in
          ``plugins/api.py`` that bind one capability per closure.
        * ``handler.__horus_required_caps__`` — tuple-valued attribute
          set by the ``require_capability`` decorator in
          ``plugins/api.py``. The wrapper enforces every cap in the
          tuple. This is the opt-in marker for plugin authors who
          wrote ``@require_capability(...)`` on their tool handler.

        Handlers with neither marker (``required_cap=None`` AND no
        ``__horus_required_caps__`` attribute) run through unchanged.
        That is the back-compat door for tools that never request a
        capability: an arithmetic / echo / pure-compute tool needs no
        gate (PERMISSION-01 surface is opt-in via decorator).

        The check uses ``DEFAULT_GRANT_POLICY`` semantics: a cap is
        granted only if present in ``self._granted``; everything else
        is denied. There is no allow-list bypass, no "trust me" flag,
        no environment override.
        """
        plugin_name = self._plugin_name
        granted = self._granted

        # Resolve the required-cap set ONCE at wrap time so the
        # closure body stays cheap (no per-call attribute lookup
        # against the underlying handler object).
        required: tuple[Capability, ...]
        if required_cap is not None:
            required = (required_cap,)
        else:
            decorator_caps = getattr(handler, "__horus_required_caps__", ())
            required = tuple(decorator_caps) if decorator_caps else ()

        if not required:
            # No required caps declared → pass-through. Back-compat
            # for tools that opt out of the capability surface.
            return handler

        def _wrapped(*args: object, **kwargs: object) -> object:
            # DEFAULT_GRANT_POLICY = "deny": each required cap must
            # appear in granted_capabilities or the call fails.
            for cap in required:
                if cap not in granted:
                    raise PermissionDenied(plugin_name, str(cap))
            return handler(*args, **kwargs)

        # Preserve the wrapped handler's __horus_required_caps__ so
        # introspection at the dashboard surface still sees them.
        try:
            _wrapped.__horus_required_caps__ = required  # type: ignore[attr-defined]
        except (AttributeError, TypeError):
            pass
        return _wrapped


class PermissionService:
    """Write side of the permission model: grant / revoke / upgrade transitions.

    Each mutator persists the state change AND appends an audit-log
    row to ``plugin_capability_grants_log`` in a single connection.
    The dashboard (Phase 45) and Phase 46 pitfall regression tests
    consume the log to render "who granted what when" histories.

    ``actor`` is constrained by a CHECK constraint on the audit table
    to one of ``{"cli", "dashboard", "system"}``; an attempt to pass
    anything else raises ``sqlite3.IntegrityError`` — by design so a
    typo at the call site fails loud rather than silent.
    """

    __slots__ = ("_db",)

    def __init__(self, db: Database) -> None:
        self._db = db

    def grant(
        self,
        plugin_name: str,
        plugin_version: str,
        capability: str,
        *,
        actor: str,
        manifest_hash: str,
    ) -> None:
        """UPSERT a granted row + append an audit-log row."""
        now = _now_iso()
        with self._db._connect() as conn:
            conn.execute(
                """
                INSERT INTO plugin_capabilities
                    (plugin_name, plugin_version, capability, manifest_hash, state, granted_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(plugin_name, plugin_version, capability) DO UPDATE SET
                    manifest_hash = excluded.manifest_hash,
                    state = excluded.state,
                    granted_at = excluded.granted_at
                """,
                (plugin_name, plugin_version, capability, manifest_hash, _STATE_GRANTED, now),
            )
            self._append_log(conn, plugin_name, plugin_version, capability,
                             _ACTION_GRANTED, manifest_hash, actor, now)

    def revoke(
        self,
        plugin_name: str,
        plugin_version: str,
        capability: str,
        *,
        actor: str,
    ) -> None:
        """Flip the row to ``state='revoked'`` + append an audit-log row.

        The pre-existing row's manifest_hash is preserved; the audit
        log carries it forward so the history shows which manifest
        the revocation applied to.
        """
        now = _now_iso()
        with self._db._connect() as conn:
            row = conn.execute(
                """
                SELECT manifest_hash FROM plugin_capabilities
                WHERE plugin_name = ? AND plugin_version = ? AND capability = ?
                """,
                (plugin_name, plugin_version, capability),
            ).fetchone()
            existing_hash = row["manifest_hash"] if row is not None else ""
            conn.execute(
                """
                UPDATE plugin_capabilities
                SET state = ?
                WHERE plugin_name = ? AND plugin_version = ? AND capability = ?
                """,
                (_STATE_REVOKED, plugin_name, plugin_version, capability),
            )
            self._append_log(conn, plugin_name, plugin_version, capability,
                             _ACTION_REVOKED, existing_hash, actor, now)

    def pending_on_upgrade(
        self,
        plugin_name: str,
        old_version: str,  # noqa: ARG002 — kept in signature for caller-clarity / future diff
        new_version: str,
        capabilities: set[str] | frozenset[str] | tuple[str, ...],
        new_hash: str,
        *,
        actor: str,
    ) -> None:
        """Stage a re-prompt: write pending rows for the new version + audit each.

        Used by the Phase 44 installer's ``update`` subcommand when
        the manifest hash diff says "previously granted capabilities
        need re-confirmation under the new manifest." The new rows
        carry the NEW manifest_hash so a subsequent ``grant`` call
        with the same hash flips them cleanly.
        """
        now = _now_iso()
        with self._db._connect() as conn:
            for cap in capabilities:
                conn.execute(
                    """
                    INSERT INTO plugin_capabilities
                        (plugin_name, plugin_version, capability, manifest_hash, state, granted_at)
                    VALUES (?, ?, ?, ?, ?, NULL)
                    ON CONFLICT(plugin_name, plugin_version, capability) DO UPDATE SET
                        manifest_hash = excluded.manifest_hash,
                        state = excluded.state,
                        granted_at = NULL
                    """,
                    (plugin_name, new_version, cap, new_hash, _STATE_PENDING),
                )
                self._append_log(conn, plugin_name, new_version, cap,
                                 _ACTION_PENDING_ON_UPGRADE, new_hash, actor, now)

    @staticmethod
    def _append_log(
        conn: sqlite3.Connection,
        plugin_name: str,
        plugin_version: str,
        capability: str,
        action: str,
        manifest_hash: str,
        actor: str,
        timestamp: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO plugin_capability_grants_log
                (plugin_name, plugin_version, capability, action,
                 manifest_hash, actor, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (plugin_name, plugin_version, capability, action,
             manifest_hash, actor, timestamp),
        )


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


__all__ = [
    "DEFAULT_GRANT_POLICY",
    "CapabilityGuard",
    "PermissionDenied",
    "PermissionGate",
    "PermissionService",
]
