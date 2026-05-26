"""Per-app plugin registry mirroring ``AdapterRegistry`` shape.

``PluginRegistry`` tracks one entry per discovered plugin: its
validated ``PluginSpec``, current ``status`` (``pending`` / ``loaded``
/ ``error`` / ``disabled``), and on-error the ``error_phase`` member
from ``LOAD_PHASE_ORDER``. Entries persist through the Phase 41
``plugins`` + ``plugin_status`` SQLite tables so a server restart
sees the same per-plugin state.

The shape is a faithful mirror of ``AdapterRegistry`` at
``src/horus_os/adapters/base.py:59``. Both registries expose the
same insertion + status-mutator contract so the FastAPI lifespan can
reuse the per-spec exception-catch idiom (every per-spec exception
turns into a ``mark_error`` call; nothing raises out).

Mutators are no-ops for unknown names — a lifespan caller bug must
not raise out of the FastAPI app startup, ISOLATE-01.

Phase 43 will add a ``mark_started`` / ``mark_stopped`` pair when
the Start lifecycle phase lands; the shape is already extension-ready.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from horus_os.storage import Database

from horus_os.plugins.spec import PluginSpec

PLUGIN_STATUS_PENDING = "pending"
PLUGIN_STATUS_LOADED = "loaded"
PLUGIN_STATUS_ERROR = "error"
PLUGIN_STATUS_DISABLED = "disabled"

_VALID_STATUSES = frozenset(
    {
        PLUGIN_STATUS_PENDING,
        PLUGIN_STATUS_LOADED,
        PLUGIN_STATUS_ERROR,
        PLUGIN_STATUS_DISABLED,
    }
)


@dataclass
class PluginEntry:
    """One row in the in-memory PluginRegistry.

    ``status`` is one of ``pending`` / ``loaded`` / ``error`` /
    ``disabled``. New entries default to ``pending`` until the loader
    flips them to ``loaded`` or ``error``. Mirrors ``AdapterEntry``
    semantics.

    ``spec`` is the validated ``PluginSpec`` for plugins that passed
    discovery + validation; for ``DiscoveryError`` rows the registry
    creates an entry with ``spec=None`` and the error_phase already
    populated.

    ``registered_tools`` / ``registered_adapters`` are populated on
    successful load so the dashboard can show "this plugin contributed
    these N tools and M adapters". Empty for ``error`` and ``pending``
    entries.

    ``last_seen`` is a UTC iso8601 string updated on every mutator
    call; the registry uses it as the freshness signal for "which
    plugins did we see this boot?" queries.
    """

    name: str
    spec: PluginSpec | None = None
    status: str = PLUGIN_STATUS_PENDING
    error_phase: str | None = None
    error_message: str | None = None
    registered_tools: tuple[str, ...] = field(default_factory=tuple)
    registered_adapters: tuple[str, ...] = field(default_factory=tuple)
    last_seen: str | None = None


class PluginRegistry:
    """In-memory + SQLite-backed plugin status tracker.

    ``__init__(db=None)`` accepts an optional ``Database`` handle. If
    supplied, the registry reads existing rows from the ``plugins`` +
    ``plugin_status`` tables on construction (so a server restart
    inherits the prior state) and writes through to those tables on
    every mutator call. When ``db`` is None the registry is purely
    in-memory — useful for tests that do not need SQLite isolation.

    All mutator methods are no-ops on unknown names. This matches
    ``AdapterRegistry`` semantics: a lifespan handler bug logs an
    error but never raises out of the FastAPI startup path.
    """

    def __init__(self, db: Database | None = None) -> None:
        self._entries: dict[str, PluginEntry] = {}
        self._db = db
        if db is not None:
            self._restore_from_db()

    # ------------------------------------------------------------------
    # Restore + persist helpers
    # ------------------------------------------------------------------

    def _restore_from_db(self) -> None:
        """Read existing plugins + plugin_status rows back into memory.

        The Phase 41 ``plugins`` + ``plugin_status`` tables CASCADE on
        delete, so the restore reads them in a single LEFT JOIN.
        ``schema_version`` predates this method (Phase 41 installed
        the tables); if a fresh DB has the schema but zero rows the
        loop iterates zero times.

        We swallow ``OperationalError`` for the rare case where this
        registry is constructed against a DB that has not run
        ``Database.init()`` yet — the registry stays empty and the
        first mutator call's UPSERT creates the rows.
        """
        if self._db is None:
            return
        try:
            with self._db._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT p.name AS name,
                           ps.status AS status,
                           ps.error_phase AS error_phase,
                           ps.error_message AS error_message,
                           ps.last_seen AS last_seen
                    FROM plugins p
                    LEFT JOIN plugin_status ps ON ps.plugin_name = p.name
                    """
                ).fetchall()
        except sqlite3.OperationalError:
            return
        for row in rows:
            self._entries[row["name"]] = PluginEntry(
                name=row["name"],
                spec=None,
                status=row["status"] or PLUGIN_STATUS_PENDING,
                error_phase=row["error_phase"],
                error_message=row["error_message"],
                registered_tools=(),
                registered_adapters=(),
                last_seen=row["last_seen"],
            )

    def _persist_plugin(self, entry: PluginEntry, spec: PluginSpec | None) -> None:
        """UPSERT a row into the ``plugins`` table.

        When ``spec`` is None (a DiscoveryError-only entry) we write
        a minimal placeholder row so the ``plugin_status`` FK survives
        (the schema CHECKs ``source IN ('entry_point', 'filesystem')``
        so we have to pick one — DiscoveryError rows carry the source
        attribution we use here).

        Idempotent via ``INSERT ... ON CONFLICT(name) DO UPDATE``.
        """
        if self._db is None:
            return
        now = datetime.now(UTC).isoformat()
        if spec is not None:
            version = spec.version
            manifest_hash = spec.manifest_hash
            source = spec.source if spec.source in {"entry_point", "filesystem"} else "filesystem"
        else:
            # Placeholder row for a DiscoveryError-only entry.
            version = "0.0.0"
            manifest_hash = ""
            source = "filesystem"
        try:
            with self._db._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO plugins (name, version, manifest_hash, enabled, installed_at, source)
                    VALUES (?, ?, ?, 1, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        version = excluded.version,
                        manifest_hash = excluded.manifest_hash,
                        source = excluded.source
                    """,
                    (entry.name, version, manifest_hash, now, source),
                )
        except sqlite3.OperationalError:
            # Schema not present yet; mutator stays in-memory.
            pass

    def _persist_status(self, entry: PluginEntry) -> None:
        """UPSERT a row into the ``plugin_status`` table."""
        if self._db is None:
            return
        try:
            with self._db._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO plugin_status
                        (plugin_name, status, error_phase, error_message, last_seen)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(plugin_name) DO UPDATE SET
                        status = excluded.status,
                        error_phase = excluded.error_phase,
                        error_message = excluded.error_message,
                        last_seen = excluded.last_seen
                    """,
                    (
                        entry.name,
                        entry.status,
                        entry.error_phase,
                        entry.error_message,
                        entry.last_seen,
                    ),
                )
        except sqlite3.OperationalError:
            pass

    def _persist_enabled(self, name: str, enabled: int) -> None:
        if self._db is None:
            return
        try:
            with self._db._connect() as conn:
                conn.execute(
                    "UPDATE plugins SET enabled = ? WHERE name = ?",
                    (enabled, name),
                )
        except sqlite3.OperationalError:
            pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(
        self,
        spec: PluginSpec,
        *,
        status: str = PLUGIN_STATUS_PENDING,
    ) -> PluginEntry:
        """Insert or refresh a plugin row from a validated ``PluginSpec``.

        Idempotent on ``spec.name``: a second call updates the in-memory
        entry's ``spec`` field (so the registry tracks the latest
        validated manifest) but does not duplicate the row in either
        the in-memory dict or the SQLite ``plugins`` table.

        ``status`` defaults to ``pending``; the loader flips it to
        ``loaded`` or ``error`` after attempting to register tools
        and adapters.
        """
        if status not in _VALID_STATUSES:
            raise ValueError(f"status={status!r} is not one of {sorted(_VALID_STATUSES)}")
        now = datetime.now(UTC).isoformat()
        existing = self._entries.get(spec.name)
        if existing is None:
            entry = PluginEntry(
                name=spec.name,
                spec=spec,
                status=status,
                last_seen=now,
            )
            self._entries[spec.name] = entry
        else:
            existing.spec = spec
            existing.status = status
            existing.last_seen = now
            entry = existing
        self._persist_plugin(entry, spec)
        self._persist_status(entry)
        return entry

    def register_discovery_error(
        self,
        name: str,
        *,
        source: str,
        source_detail: str,
        error_phase: str,
        error_message: str,
    ) -> PluginEntry:
        """Insert an error-only row for a source that failed to discover.

        Used by the FastAPI lifespan when ``discover_plugins()`` returns
        a ``DiscoveryError``: there is no ``PluginSpec`` to bind, but
        the registry still tracks the failure so ``/api/plugins`` can
        surface "plugin X failed at error_phase=discover with message
        Y" instead of silently dropping the broken plugin.

        We construct a placeholder ``PluginSpec``-shaped row directly
        in the in-memory entry; the SQLite ``plugins`` table gets a
        minimal placeholder via ``_persist_plugin(entry, spec=None)``.
        """
        now = datetime.now(UTC).isoformat()
        entry = PluginEntry(
            name=name,
            spec=None,
            status=PLUGIN_STATUS_ERROR,
            error_phase=error_phase,
            error_message=error_message,
            last_seen=now,
        )
        # Record source attribution as a side note on the entry — the
        # registry's persistence path uses it for the plugins row.
        self._entries[name] = entry
        # Pass a synthetic spec-shaped value just for the source field
        # so the plugins row gets the right ``source`` CHECK value.
        # We avoid constructing a real PluginSpec to skip the validation
        # contract.
        if self._db is not None:
            try:
                with self._db._connect() as conn:
                    conn.execute(
                        """
                        INSERT INTO plugins
                            (name, version, manifest_hash, enabled, installed_at, source)
                        VALUES (?, ?, ?, 1, ?, ?)
                        ON CONFLICT(name) DO UPDATE SET
                            source = excluded.source
                        """,
                        (name, "0.0.0", "", now, source),
                    )
            except sqlite3.OperationalError:
                pass
        self._persist_status(entry)
        return entry

    def mark_loaded(
        self,
        name: str,
        *,
        registered_tools: tuple[str, ...] = (),
        registered_adapters: tuple[str, ...] = (),
    ) -> None:
        """Flip an entry to ``loaded`` and record what it contributed."""
        entry = self._entries.get(name)
        if entry is None:
            return
        entry.status = PLUGIN_STATUS_LOADED
        entry.error_phase = None
        entry.error_message = None
        entry.registered_tools = tuple(registered_tools)
        entry.registered_adapters = tuple(registered_adapters)
        entry.last_seen = datetime.now(UTC).isoformat()
        self._persist_status(entry)

    def mark_error(self, name: str, error_phase: str, error_message: str) -> None:
        """Flip an entry to ``error`` with structured attribution."""
        entry = self._entries.get(name)
        if entry is None:
            return
        entry.status = PLUGIN_STATUS_ERROR
        entry.error_phase = error_phase
        entry.error_message = error_message
        entry.last_seen = datetime.now(UTC).isoformat()
        self._persist_status(entry)

    def mark_pending(self, name: str) -> None:
        entry = self._entries.get(name)
        if entry is None:
            return
        entry.status = PLUGIN_STATUS_PENDING
        entry.last_seen = datetime.now(UTC).isoformat()
        self._persist_status(entry)

    def mark_disabled(self, name: str) -> None:
        entry = self._entries.get(name)
        if entry is None:
            return
        entry.status = PLUGIN_STATUS_DISABLED
        entry.last_seen = datetime.now(UTC).isoformat()
        self._persist_status(entry)
        self._persist_enabled(name, 0)

    # ------------------------------------------------------------------
    # Phase 43: enable/disable persistence (ISOLATE-03)
    # ------------------------------------------------------------------

    def enable(self, name: str) -> bool:
        """Flip ``plugins.enabled = 1`` for ``name``. Returns the new enabled state.

        If the in-memory entry currently has ``status='disabled'``, flip
        it back to ``pending`` so the next discover pass can re-resolve
        it. Other statuses are left alone — a previously-loaded entry
        keeps its ``loaded`` status until a fresh discover refreshes it.
        """
        self._persist_enabled(name, 1)
        entry = self._entries.get(name)
        if entry is not None and entry.status == PLUGIN_STATUS_DISABLED:
            entry.status = PLUGIN_STATUS_PENDING
            entry.last_seen = datetime.now(UTC).isoformat()
            self._persist_status(entry)
        return True

    def disable(self, name: str) -> bool:
        """Flip ``plugins.enabled = 0`` for ``name``. Returns the new enabled state.

        ``mark_disabled(name)`` is also invoked so the in-memory entry's
        status reflects the change immediately; tests that round-trip
        through SQL see both the column and the registry entry agree.

        Returns False (the new enabled value) so callers can write
        ``new_state = registry.disable(name)`` symmetrically with enable.
        """
        self.mark_disabled(name)
        return False

    def is_enabled(self, name: str) -> bool:
        """Return whether ``plugins.enabled=1`` for ``name``.

        Unknown names default to True so a fresh discovery loop's first
        encounter with a never-seen plugin does not get filtered out
        before the registry has a chance to register it (the discovery
        path is: ``discover_plugins`` → ``register`` → ``is_enabled``
        check → ``load``; the very first ``is_enabled`` call for a
        plugin happens AFTER ``register`` has written the plugins row
        with ``enabled=1`` per the existing _persist_plugin code path).
        """
        if self._db is None:
            return True
        try:
            with self._db._connect() as conn:
                row = conn.execute(
                    "SELECT enabled FROM plugins WHERE name = ?",
                    (name,),
                ).fetchone()
        except sqlite3.OperationalError:
            return True
        if row is None:
            return True
        return bool(row["enabled"])

    def get(self, name: str) -> PluginEntry | None:
        return self._entries.get(name)

    def all(self) -> list[PluginEntry]:
        """Return all entries sorted by name for deterministic output."""
        return sorted(self._entries.values(), key=lambda e: e.name)

    def enabled(self) -> list[PluginEntry]:
        """Return entries with ``status='loaded'`` sorted by name."""
        return [e for e in self.all() if e.status == PLUGIN_STATUS_LOADED]

    def error(self) -> list[PluginEntry]:
        """Return entries with ``status='error'`` sorted by name."""
        return [e for e in self.all() if e.status == PLUGIN_STATUS_ERROR]

    def pending(self) -> list[PluginEntry]:
        """Return entries with ``status='pending'`` sorted by name."""
        return [e for e in self.all() if e.status == PLUGIN_STATUS_PENDING]

    def disabled(self) -> list[PluginEntry]:
        """Return entries with ``status='disabled'`` sorted by name."""
        return [e for e in self.all() if e.status == PLUGIN_STATUS_DISABLED]

    def names(self) -> Iterable[str]:
        return tuple(sorted(self._entries.keys()))


__all__ = [
    "PLUGIN_STATUS_DISABLED",
    "PLUGIN_STATUS_ERROR",
    "PLUGIN_STATUS_LOADED",
    "PLUGIN_STATUS_PENDING",
    "PluginEntry",
    "PluginRegistry",
]
