"""SQLitePersister: routes ObservationEvents into v0.4 tables.

The persister is one of three planned subscribers of the
ObservationBus (CostAnnotator first in Phase 34, Persister second,
OtelExporter last in Phase 38). It owns the canonical write path
from observation events to the v0.4 schema.

Per-event routing:

- LLM_CALL -> INSERT into llm_calls
- TOOL_CALL -> INSERT into tool_invocations
- RUN_END -> UPDATE traces with SUM rollups from llm_calls plus the
  RunEndEvent's own latency_ms

Each insert opens a fresh sqlite3 connection with the same four
PRAGMAs Database._connect uses (journal_mode=WAL, synchronous=NORMAL,
foreign_keys=ON, busy_timeout=5000) so writes from the persister
behave identically to writes from the runtime.

Hard assertion: both _insert_ methods refuse to write a row whose
latency_ms is negative (Pitfall 3 substrate). The assertion fails
loudly so the test that introduces it catches the bug at CI time.

Total_cost_usd uses an all-or-nothing aggregate (CASE on
COUNT(*) vs COUNT(cost_usd)) so that when any contributing llm_calls
row has cost_usd NULL (pricing missing for that model), the rollup
stays NULL. Plain SUM skips NULLs in SQL and would return a partial
total that lies about the run's real cost. NULL is honest; zero or
a partial total is a lie (Pitfall 5).
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from horus_os.observability.bus import (
    LLMCallEvent,
    ObservationEvent,
    RunEndEvent,
    ToolCallEvent,
)

if TYPE_CHECKING:
    from horus_os.storage import Database


def _connect(db_path: str) -> sqlite3.Connection:
    """Open a sqlite3 connection mirroring storage.Database._connect pragmas.

    The persister cannot call Database._connect directly because it is
    private. Replicating the four PRAGMAs here keeps the write path
    behaviorally identical without violating module encapsulation.
    """
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


class SQLitePersister:
    """Subscribe this to an ObservationBus to persist events to SQLite.

    Holds a reference to a Database so it can resolve the on-disk path
    on every write. Connections are opened per insert and closed when
    the `with` block exits, matching the lifecycle pattern of the rest
    of horus_os.storage.
    """

    def __init__(self, db: Database) -> None:
        self._db = db

    @property
    def _db_path(self) -> str:
        return str(self._db.path)

    def on_event(self, event: ObservationEvent) -> None:
        """Route one event to the right table by kind.

        Unknown kinds are silently ignored; future event classes can
        be added without breaking older persisters.
        """
        if isinstance(event, LLMCallEvent):
            self._insert_llm_call(event)
        elif isinstance(event, ToolCallEvent):
            self._insert_tool_invocation(event)
        elif isinstance(event, RunEndEvent):
            self._rollup_trace(event)

    def _insert_llm_call(self, event: LLMCallEvent) -> None:
        assert event.latency_ms >= 0, (
            f"negative latency_ms={event.latency_ms} on {event.kind} for trace {event.trace_id}"
        )
        with _connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO llm_calls (
                    call_id, trace_id, iteration_idx, created_at,
                    provider, model,
                    input_tokens, output_tokens,
                    cache_creation_input_tokens, cache_read_input_tokens,
                    cost_usd, pricing_missing,
                    latency_ms, status, error_message, error_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.call_id,
                    event.trace_id,
                    event.iteration_idx,
                    event.created_at,
                    event.provider,
                    event.model,
                    event.input_tokens,
                    event.output_tokens,
                    event.cache_creation_input_tokens,
                    event.cache_read_input_tokens,
                    event.cost_usd,
                    1 if event.pricing_missing else 0,
                    event.latency_ms,
                    event.status,
                    event.error_message,
                    event.error_type,
                ),
            )

    def _insert_tool_invocation(self, event: ToolCallEvent) -> None:
        assert event.latency_ms >= 0, (
            f"negative latency_ms={event.latency_ms} on {event.kind} for trace {event.trace_id}"
        )
        with _connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO tool_invocations (
                    invocation_id, trace_id, parent_trace_id, created_at,
                    tool_name, latency_ms, status,
                    error_message, error_type, retry_count, output_size
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.invocation_id,
                    event.trace_id,
                    event.parent_trace_id,
                    event.created_at,
                    event.tool_name,
                    event.latency_ms,
                    event.status,
                    event.error_message,
                    event.error_type,
                    event.retry_count,
                    event.output_size,
                ),
            )

    def _rollup_trace(self, event: RunEndEvent) -> None:
        """Roll up llm_calls totals into the matching traces row.

        total_cost_usd uses an all-or-nothing aggregate: if any contributing
        llm_calls row has cost_usd NULL (pricing missing for that model),
        the rollup is forced to NULL. Plain SUM skips NULLs in SQL, so it
        would return a partial total that lies about the run's true cost.
        NULL is honest; zero or a partial total is a lie (Pitfall 5).

        Tokens use COALESCE because they are always known when an LLM call
        returns. If no traces row matches the trace_id, the UPDATE silently
        matches zero rows; Phase 33's runner guarantees the traces row
        exists by the time RUN_END fires.
        """
        with _connect(self._db_path) as conn:
            conn.execute(
                """
                UPDATE traces
                SET total_input_tokens  = (
                        SELECT COALESCE(SUM(input_tokens), 0)
                        FROM llm_calls
                        WHERE trace_id = ?
                    ),
                    total_output_tokens = (
                        SELECT COALESCE(SUM(output_tokens), 0)
                        FROM llm_calls
                        WHERE trace_id = ?
                    ),
                    total_cost_usd      = (
                        SELECT CASE
                            WHEN COUNT(*) = 0 THEN NULL
                            WHEN COUNT(*) > COUNT(cost_usd) THEN NULL
                            ELSE SUM(cost_usd)
                        END
                        FROM llm_calls
                        WHERE trace_id = ?
                    ),
                    total_duration_ms   = ?
                WHERE trace_id = ?
                """,
                (
                    event.trace_id,
                    event.trace_id,
                    event.trace_id,
                    event.latency_ms,
                    event.trace_id,
                ),
            )


__all__ = ["SQLitePersister"]
