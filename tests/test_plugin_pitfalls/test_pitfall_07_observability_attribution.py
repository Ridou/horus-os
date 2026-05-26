"""Pitfall 7: Plugin observability gaps — v0.4 rollups attribute errors to "the registry" not to the plugin.

See .planning/research/PITFALLS.md §"Pitfall 7" for the documented
threat. Without per-row plugin attribution on the ``llm_calls`` and
``tool_invocations`` tables, a failing plugin's traces roll up under
the catch-all "horus-os core" bucket and the user has no way to know
which plugin is responsible. The v5→v6 migration adds nullable
``plugin_name`` columns to both tables — NULL means "core", a string
value names the plugin (per OBSERVE-01).

Four structural assertions:

1. ``PRAGMA table_info('tool_invocations')`` returns a row with
   ``name='plugin_name'``.
2. ``PRAGMA table_info('llm_calls')`` returns a row with
   ``name='plugin_name'``.
3. A ``tool_invocations`` row inserted with ``plugin_name='foo-plugin'``
   reads back as the string ``'foo-plugin'``; a row with NULL reads
   back as Python ``None``.
4. The dashboard / observability roll-up consumes the column for
   per-plugin attribution; that integration is exercised in
   ``test_observability_per_plugin.py`` (Phase 45) — this test just
   pins the column existence.
"""

from __future__ import annotations

from horus_os.storage import Database


def _table_columns(db: Database, table: str) -> dict[str, str]:
    """Return ``{name: type}`` for every column in ``table``."""
    cols: dict[str, str] = {}
    with db._connect() as conn:
        cursor = conn.execute(f"PRAGMA table_info({table})")
        for row in cursor.fetchall():
            cols[row["name"]] = row["type"]
    return cols


def test_tool_invocations_has_plugin_name_column(pitfall_db: Database) -> None:
    """v6 migration adds nullable plugin_name to tool_invocations."""
    cols = _table_columns(pitfall_db, "tool_invocations")
    assert "plugin_name" in cols, (
        f"Pitfall 7: tool_invocations.plugin_name missing; got columns: {sorted(cols)}"
    )
    # TEXT is the canonical type; SQLite stores NULL regardless.
    assert "TEXT" in cols["plugin_name"].upper()


def test_llm_calls_has_plugin_name_column(pitfall_db: Database) -> None:
    """v6 migration adds nullable plugin_name to llm_calls."""
    cols = _table_columns(pitfall_db, "llm_calls")
    assert "plugin_name" in cols, (
        f"Pitfall 7: llm_calls.plugin_name missing; got columns: {sorted(cols)}"
    )
    assert "TEXT" in cols["plugin_name"].upper()


def test_tool_invocations_plugin_name_roundtrip_string_and_null(
    pitfall_db: Database,
) -> None:
    """A plugin_name=string row + a plugin_name=NULL row read back as expected.

    The NULL bucket is the "horus-os core" attribution per OBSERVE-01;
    a string value names the responsible plugin. The dashboard /
    /api/observability/plugins surface aggregates by ``plugin_name``;
    this test pins the round-trip semantics.
    """
    with pitfall_db._connect() as conn:
        # Insert two rows: one with a named plugin, one with NULL (core).
        conn.execute(
            """
            INSERT INTO tool_invocations
                (invocation_id, trace_id, tool_name, latency_ms, status, created_at, plugin_name)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "inv-foo",
                "trace-foo",
                "read_file",
                42,
                "error",
                "2026-05-26T12:00:00Z",
                "foo-plugin",
            ),
        )
        conn.execute(
            """
            INSERT INTO tool_invocations
                (invocation_id, trace_id, tool_name, latency_ms, status, created_at, plugin_name)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "inv-core",
                "trace-core",
                "read_file",
                17,
                "ok",
                "2026-05-26T12:00:01Z",
                None,
            ),
        )
        cursor = conn.execute(
            "SELECT trace_id, plugin_name FROM tool_invocations ORDER BY created_at"
        )
        rows = {row["trace_id"]: row["plugin_name"] for row in cursor.fetchall()}
    assert rows["trace-foo"] == "foo-plugin"
    assert rows["trace-core"] is None
