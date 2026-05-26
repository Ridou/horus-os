"""Read-only aggregation queries over the v0.4 observability tables.

All percentile aggregations operate on raw `latency_ms` via SQLite's
NTILE window function; never aggregate-of-aggregates, never Python
percentile helpers from the stdlib statistics module. The Phase 36
dashboard and Phase 37 CLI both consume this module so the two
surfaces cannot disagree about what p50 means.

Public surface:

    parse_window(window)       -> ISO 8601 UTC threshold string
    agent_totals(db, window)   -> per-agent rollup
    cost_by_agent(db, window)  -> per-agent cost breakdown with cache tokens
    latency_p50_p95(db, window) -> global p50 / p95 / sample_count
    tool_reliability(db, window) -> per-tool retry-aware status aggregation

Conventions baked into every function:

- The `window` string accepts `24h`, `7d`, `30d` plus any positive
  integer Nh or Nd form. Invalid input raises `ValueError`; route
  handlers convert that into a 400 Bad Request.
- Pre-v0.4 trace rows have NULL on the rollup columns. Cost sums
  exclude NULL rows via SQL's NULL-skipping `SUM`; the NULL rows are
  surfaced separately as `uncosted_runs` so the dashboard explains
  missing dollars instead of hiding them (Pitfall 11).
- Percentile fields return Python `None` (JSON null) for empty
  windows; `sample_count` is returned alongside so callers can apply
  the n-threshold render rule (Pitfall 10).
- `tool_reliability` honors the status enum: `retry_then_success`
  rows are NOT counted as errors; `expected_no_result` rows are not
  in the success-rate denominator. The `error_message` column is
  never read here (Pitfalls 7 + 9); only `error_type` (exception
  class name) is surfaced.
- All filters use parameterized `?` placeholders; the window string
  is never substituted into SQL via Python string formatting.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from horus_os.storage import Database


__all__ = [
    "agent_totals",
    "cost_by_agent",
    "latency_p50_p95",
    "parse_window",
    "tool_reliability",
]


def parse_window(window: str) -> str:
    """Convert a window spec like "24h" / "7d" / "30d" into an ISO 8601 UTC string.

    Accepts any positive integer followed by `h` (hours) or `d` (days).
    Returns an ISO timestamp shaped to match `_now_iso()` in storage.py
    (datetime.isoformat with the trailing `+00:00` replaced by `Z`), so
    lexicographic comparison against the `created_at TEXT` columns is
    chronologically correct.

    Raises `ValueError` on the empty string, zero, negatives, decimals,
    missing-unit, missing-number, and any non-matching shape. The error
    message names the offending input so the route handler's 400 detail
    is actionable.
    """
    if not isinstance(window, str) or not window:
        raise ValueError(
            f"invalid window: {window!r}; expected forms like '24h', '7d', '30d'"
        )
    unit = window[-1]
    if unit not in ("h", "d"):
        raise ValueError(
            f"invalid window: {window!r}; expected forms like '24h', '7d', '30d'"
        )
    body = window[:-1]
    # Reject empty body, decimals, and any non-digit content. We accept
    # ONLY plain positive integers; bool's `isdigit` already excludes the
    # minus sign and the decimal point.
    if not body or not body.isdigit():
        raise ValueError(
            f"invalid window: {window!r}; expected forms like '24h', '7d', '30d'"
        )
    amount = int(body)
    if amount <= 0:
        raise ValueError(
            f"invalid window: {window!r}; expected forms like '24h', '7d', '30d'"
        )
    delta = timedelta(hours=amount) if unit == "h" else timedelta(days=amount)
    threshold = datetime.now(UTC) - delta
    return threshold.isoformat().replace("+00:00", "Z")


def agent_totals(db: Database, window: str) -> list[dict[str, Any]]:
    """Per-agent rollup over the window.

    Returns one dict per agent that has at least one trace in the
    window. The dict carries:

        agent                : str
        total_runs           : int   (every trace row, including pre-v0.4)
        total_input_tokens   : int | None  (SQL SUM of non-NULL rows; None
                                            when all contributing rows are NULL)
        total_output_tokens  : int | None
        total_cost_usd       : float  (SUM of non-NULL rows, rounded to 6dp;
                                       0.0 when no costed runs)
        uncosted_runs        : int   (rows where total_cost_usd IS NULL;
                                      Pitfall 11 surface contract)
        latency_p50_ms       : int | None  (NTILE(100) on llm_calls.latency_ms;
                                            None when sample_count == 0)
        latency_p95_ms       : int | None
        sample_count         : int   (count of llm_calls rows in window for
                                      this agent)

    Percentiles come from llm_calls.latency_ms (the monotonic per-call
    timing Phase 33 captures) joined via trace_id; never traces.latency_ms
    (the older v0.3 wall-clock). The window filter applies to BOTH the
    traces row and the llm_calls row so a trace at day -8 with a call at
    day -3 stays out of a 7d window.
    """
    threshold = parse_window(window)
    sql = """
        WITH windowed_traces AS (
            SELECT trace_id, agent_profile_name, total_input_tokens,
                   total_output_tokens, total_cost_usd
            FROM traces
            WHERE created_at >= ?
              AND agent_profile_name IS NOT NULL
        ),
        windowed_calls AS (
            SELECT lc.trace_id, lc.latency_ms, t.agent_profile_name
            FROM llm_calls lc
            JOIN windowed_traces t ON t.trace_id = lc.trace_id
            WHERE lc.created_at >= ?
        ),
        ranked_calls AS (
            SELECT agent_profile_name, latency_ms,
                   NTILE(100) OVER (PARTITION BY agent_profile_name
                                    ORDER BY latency_ms) AS pct
            FROM windowed_calls
        ),
        per_agent_calls AS (
            SELECT agent_profile_name,
                   MAX(CASE WHEN pct <= 50 THEN latency_ms END) AS p50_ms,
                   MAX(CASE WHEN pct <= 95 THEN latency_ms END) AS p95_ms,
                   COUNT(*) AS sample_count
            FROM ranked_calls
            GROUP BY agent_profile_name
        ),
        per_agent_traces AS (
            SELECT agent_profile_name,
                   COUNT(*) AS total_runs,
                   SUM(total_input_tokens)  AS total_input_tokens,
                   SUM(total_output_tokens) AS total_output_tokens,
                   SUM(total_cost_usd)      AS total_cost_usd,
                   SUM(CASE WHEN total_cost_usd IS NULL THEN 1 ELSE 0 END)
                       AS uncosted_runs
            FROM windowed_traces
            GROUP BY agent_profile_name
        )
        SELECT t.agent_profile_name AS agent,
               t.total_runs,
               t.total_input_tokens,
               t.total_output_tokens,
               t.total_cost_usd,
               t.uncosted_runs,
               c.p50_ms,
               c.p95_ms,
               COALESCE(c.sample_count, 0) AS sample_count
        FROM per_agent_traces t
        LEFT JOIN per_agent_calls c
               ON c.agent_profile_name = t.agent_profile_name
        ORDER BY t.agent_profile_name ASC
    """
    rows: list[dict[str, Any]] = []
    with db._connect() as conn:
        for row in conn.execute(sql, (threshold, threshold)).fetchall():
            total_cost = row["total_cost_usd"]
            rows.append(
                {
                    "agent": row["agent"],
                    "total_runs": int(row["total_runs"]),
                    "total_input_tokens": row["total_input_tokens"],
                    "total_output_tokens": row["total_output_tokens"],
                    "total_cost_usd": (
                        round(float(total_cost), 6) if total_cost is not None else 0.0
                    ),
                    "uncosted_runs": int(row["uncosted_runs"]),
                    "latency_p50_ms": row["p50_ms"],
                    "latency_p95_ms": row["p95_ms"],
                    "sample_count": int(row["sample_count"]),
                }
            )
    return rows


def cost_by_agent(db: Database, window: str) -> list[dict[str, Any]]:
    """Per-agent cost breakdown over the window. Implemented in Task 2."""
    raise NotImplementedError("cost_by_agent ships in Task 2")


def latency_p50_p95(db: Database, window: str) -> dict[str, Any]:
    """Global p50 / p95 / sample_count over the window. Implemented in Task 3."""
    raise NotImplementedError("latency_p50_p95 ships in Task 3")


def tool_reliability(db: Database, window: str) -> list[dict[str, Any]]:
    """Per-tool retry-aware status aggregation. Implemented in Task 4."""
    raise NotImplementedError("tool_reliability ships in Task 4")
