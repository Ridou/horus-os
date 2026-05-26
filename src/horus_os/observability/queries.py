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
  in the success-rate denominator. The text-content error column on
  tool_invocations is never read here (Pitfalls 7 + 9); only
  `error_type` (exception class name) is surfaced.
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
    "cost_by_model",
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
        raise ValueError(f"invalid window: {window!r}; expected forms like '24h', '7d', '30d'")
    unit = window[-1]
    if unit not in ("h", "d"):
        raise ValueError(f"invalid window: {window!r}; expected forms like '24h', '7d', '30d'")
    body = window[:-1]
    # Reject empty body, decimals, and any non-digit content. We accept
    # ONLY plain positive integers; bool's `isdigit` already excludes the
    # minus sign and the decimal point.
    if not body or not body.isdigit():
        raise ValueError(f"invalid window: {window!r}; expected forms like '24h', '7d', '30d'")
    amount = int(body)
    if amount <= 0:
        raise ValueError(f"invalid window: {window!r}; expected forms like '24h', '7d', '30d'")
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
        total_cost_usd       : float | None
                                      (SUM of non-NULL rows, rounded to 6dp;
                                       None when every contributing row is
                                       NULL, never 0; Pitfall 11 honesty)
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
                    # None (not 0) when every contributing row's
                    # total_cost_usd is NULL; Pitfall 11 honesty contract.
                    "total_cost_usd": (
                        round(float(total_cost), 6) if total_cost is not None else None
                    ),
                    "uncosted_runs": int(row["uncosted_runs"]),
                    "latency_p50_ms": row["p50_ms"],
                    "latency_p95_ms": row["p95_ms"],
                    "sample_count": int(row["sample_count"]),
                }
            )
    return rows


def cost_by_agent(db: Database, window: str) -> list[dict[str, Any]]:
    """Per-agent cost breakdown over the window.

    Returns one dict per agent that has at least one trace in the
    window. The dict carries:

        agent                              : str
        total_cost_usd                     : float  (SUM of non-NULL
                                                     traces.total_cost_usd,
                                                     rounded to 6dp in Python)
        total_input_tokens                 : int
        total_output_tokens                : int
        total_cache_read_input_tokens      : int  (sum across llm_calls)
        total_cache_creation_input_tokens  : int  (sum across llm_calls)
        run_count                          : int  (every trace row)
        uncosted_runs                      : int  (rows where total_cost_usd
                                                   IS NULL; pre-v0.4 plus
                                                   Pitfall 5 unknown-model rows)

    Cache token totals come from llm_calls because the traces rollup
    columns only carry the non-cache `total_input_tokens` and
    `total_output_tokens`. Rounding happens in Python (`round(value, 6)`)
    rather than via SQLite `ROUND` because SQLite's banker rounding
    behavior is platform-variable; Python is stable across the 3-OS CI
    matrix.

    Ordering: by `total_cost_usd` DESC; ties by `agent` ASC for
    deterministic test output. Agents with zero in-window traces are
    excluded (not returned with all-zero rows).
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
            SELECT lc.trace_id, lc.cache_read_input_tokens,
                   lc.cache_creation_input_tokens, t.agent_profile_name
            FROM llm_calls lc
            JOIN windowed_traces t ON t.trace_id = lc.trace_id
            WHERE lc.created_at >= ?
        ),
        per_agent_cache AS (
            SELECT agent_profile_name,
                   SUM(cache_read_input_tokens)     AS total_cache_read,
                   SUM(cache_creation_input_tokens) AS total_cache_create
            FROM windowed_calls
            GROUP BY agent_profile_name
        ),
        per_agent_traces AS (
            SELECT agent_profile_name,
                   COUNT(*) AS run_count,
                   SUM(total_input_tokens)  AS total_input_tokens,
                   SUM(total_output_tokens) AS total_output_tokens,
                   SUM(total_cost_usd)      AS total_cost_usd,
                   SUM(CASE WHEN total_cost_usd IS NULL THEN 1 ELSE 0 END)
                       AS uncosted_runs
            FROM windowed_traces
            GROUP BY agent_profile_name
        )
        SELECT t.agent_profile_name AS agent,
               t.run_count,
               t.total_input_tokens,
               t.total_output_tokens,
               t.total_cost_usd,
               t.uncosted_runs,
               COALESCE(c.total_cache_read, 0)   AS total_cache_read_input_tokens,
               COALESCE(c.total_cache_create, 0) AS total_cache_creation_input_tokens
        FROM per_agent_traces t
        LEFT JOIN per_agent_cache c
               ON c.agent_profile_name = t.agent_profile_name
        WHERE t.run_count >= 1
        ORDER BY COALESCE(t.total_cost_usd, 0) DESC, t.agent_profile_name ASC
    """
    rows: list[dict[str, Any]] = []
    with db._connect() as conn:
        for row in conn.execute(sql, (threshold, threshold)).fetchall():
            total_cost = row["total_cost_usd"]
            rows.append(
                {
                    "agent": row["agent"],
                    "total_cost_usd": (
                        round(float(total_cost), 6) if total_cost is not None else 0.0
                    ),
                    "total_input_tokens": int(row["total_input_tokens"] or 0),
                    "total_output_tokens": int(row["total_output_tokens"] or 0),
                    "total_cache_read_input_tokens": int(row["total_cache_read_input_tokens"]),
                    "total_cache_creation_input_tokens": int(
                        row["total_cache_creation_input_tokens"]
                    ),
                    "run_count": int(row["run_count"]),
                    "uncosted_runs": int(row["uncosted_runs"]),
                }
            )
    return rows


def cost_by_model(db: Database, window: str) -> list[dict[str, Any]]:
    """Per-model cost breakdown over the window.

    Returns one dict per model with at least one llm_call in the
    window. The dict carries:

        model                              : str    (llm_calls.model)
        provider                           : str    (llm_calls.provider)
        total_cost_usd                     : float  (SUM of non-NULL
                                                     llm_calls.cost_usd,
                                                     rounded to 6dp in Python;
                                                     0.0 when SUM is NULL,
                                                     matching cost_by_agent's
                                                     contract; uncosted_calls
                                                     surfaces NULL count
                                                     separately per Pitfall 11)
        total_input_tokens                 : int    (SUM llm_calls.input_tokens)
        total_output_tokens                : int    (SUM llm_calls.output_tokens)
        total_cache_read_input_tokens      : int
        total_cache_creation_input_tokens  : int
        call_count                         : int    (COUNT(*) on llm_calls)
        uncosted_calls                     : int    (rows where cost_usd IS
                                                     NULL; Pitfall 5 unknown-
                                                     model rows plus any future
                                                     NULL-cost row)

    Rounding happens in Python (`round(value, 6)`) rather than via SQLite
    `ROUND` because SQLite's banker rounding is platform-variable; Python
    is stable across the 3-OS CI matrix (mirrors cost_by_agent line 282).

    Ordering: by `total_cost_usd` DESC; ties by `model` ASC for
    deterministic test output. Models with zero in-window calls are
    excluded (not returned with all-zero rows).
    """
    threshold = parse_window(window)
    sql = """
        WITH windowed_calls AS (
            SELECT model, provider, cost_usd, input_tokens, output_tokens,
                   cache_read_input_tokens, cache_creation_input_tokens
            FROM llm_calls
            WHERE created_at >= ?
        )
        SELECT model,
               provider,
               COUNT(*) AS call_count,
               SUM(input_tokens)                AS total_input_tokens,
               SUM(output_tokens)               AS total_output_tokens,
               SUM(cache_read_input_tokens)     AS total_cache_read_input_tokens,
               SUM(cache_creation_input_tokens) AS total_cache_creation_input_tokens,
               SUM(cost_usd)                    AS total_cost_usd,
               SUM(CASE WHEN cost_usd IS NULL THEN 1 ELSE 0 END) AS uncosted_calls
        FROM windowed_calls
        GROUP BY model, provider
        ORDER BY COALESCE(SUM(cost_usd), 0) DESC, model ASC
    """
    rows: list[dict[str, Any]] = []
    with db._connect() as conn:
        for row in conn.execute(sql, (threshold,)).fetchall():
            total_cost = row["total_cost_usd"]
            rows.append(
                {
                    "model": row["model"],
                    "provider": row["provider"],
                    "total_cost_usd": (
                        round(float(total_cost), 6) if total_cost is not None else 0.0
                    ),
                    "total_input_tokens": int(row["total_input_tokens"] or 0),
                    "total_output_tokens": int(row["total_output_tokens"] or 0),
                    "total_cache_read_input_tokens": int(row["total_cache_read_input_tokens"] or 0),
                    "total_cache_creation_input_tokens": int(
                        row["total_cache_creation_input_tokens"] or 0
                    ),
                    "call_count": int(row["call_count"]),
                    "uncosted_calls": int(row["uncosted_calls"]),
                }
            )
    return rows


def latency_p50_p95(db: Database, window: str) -> dict[str, Any]:
    """Global p50 / p95 / sample_count over the window.

    Returns a single dict (this function does NOT group by agent;
    per-agent percentiles live on `agent_totals`):

        p50_ms       : int | None  (None when sample_count == 0)
        p95_ms       : int | None
        sample_count : int

    The empty-window contract returns `None` for both percentile keys,
    never 0 (Pitfall 10 line 272: rendering 0 for n=0 is the bug). The
    `sample_count` is surfaced so callers (Phase 36 dashboard, Phase 37
    CLI) can apply the n>=10 render rule.

    Implementation: a CTE selects `latency_ms` with `NTILE(100) OVER
    (ORDER BY latency_ms)` over the windowed `llm_calls` rows. The outer
    SELECT extracts `p50` and `p95` via `MAX(CASE WHEN pct <= K THEN
    latency_ms END)`. SQLite returns NULL when the CASE matches no rows,
    which the Python boundary passes through unchanged to JSON null.
    """
    threshold = parse_window(window)
    sql = """
        WITH windowed AS (
            SELECT latency_ms
            FROM llm_calls
            WHERE created_at >= ?
        ),
        ranked AS (
            SELECT latency_ms,
                   NTILE(100) OVER (ORDER BY latency_ms) AS pct
            FROM windowed
        )
        SELECT
            MAX(CASE WHEN pct <= 50 THEN latency_ms END) AS p50_ms,
            MAX(CASE WHEN pct <= 95 THEN latency_ms END) AS p95_ms,
            COUNT(*) AS sample_count
        FROM ranked
    """
    with db._connect() as conn:
        row = conn.execute(sql, (threshold,)).fetchone()
    sample_count = int(row["sample_count"]) if row is not None else 0
    if sample_count == 0:
        return {"p50_ms": None, "p95_ms": None, "sample_count": 0}
    return {
        "p50_ms": row["p50_ms"],
        "p95_ms": row["p95_ms"],
        "sample_count": sample_count,
    }


def tool_reliability(db: Database, window: str) -> list[dict[str, Any]]:
    """Per-tool retry-aware status aggregation over the window.

    Returns one dict per tool that has at least one invocation in the
    window. The dict carries:

        tool_name                : str
        call_count               : int
        success_count            : int   (status IN ('success',
                                           'retry_then_success'))
        error_count              : int   (status = 'error' only)
        retry_then_success_count : int
        expected_no_result_count : int
        success_rate             : float | None
                                   (success / (success + error), rounded
                                   to 4dp; None when denominator is 0)
        last_error_type          : str | None
                                   (exception class name from MAX(created_at)
                                   error row; never user input)
        last_error_at            : str | None  (timestamp of that row)

    Pitfall 9 contract: `retry_then_success` rows are NOT counted in
    `error_count`. They count toward success (the call eventually
    succeeded) and are surfaced separately as `retry_then_success_count`
    so the dashboard can show flakiness as a distinct signal from
    reliability. `expected_no_result` rows are informational and are
    excluded from both numerator and denominator of `success_rate`.

    The query NEVER references the column that carries error text
    content; only `error_type` (exception class name) flows out. That
    keeps any user-supplied path or URL embedded in an exception text
    sealed inside the persister write path (Pitfalls 7 + 9).

    Ordering: by `call_count` DESC; ties by `tool_name` ASC for
    deterministic test output. Tools with zero in-window invocations
    are excluded.
    """
    threshold = parse_window(window)
    sql = """
        WITH windowed AS (
            SELECT tool_name, status, error_type, created_at
            FROM tool_invocations
            WHERE created_at >= ?
        )
        SELECT
            tool_name,
            COUNT(*) AS call_count,
            SUM(CASE WHEN status IN ('success', 'retry_then_success') THEN 1 ELSE 0 END)
                AS success_count,
            SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS error_count,
            SUM(CASE WHEN status = 'retry_then_success' THEN 1 ELSE 0 END)
                AS retry_then_success_count,
            SUM(CASE WHEN status = 'expected_no_result' THEN 1 ELSE 0 END)
                AS expected_no_result_count,
            (
                SELECT error_type
                FROM windowed ti2
                WHERE ti2.tool_name = w.tool_name AND ti2.status = 'error'
                ORDER BY created_at DESC
                LIMIT 1
            ) AS last_error_type,
            (
                SELECT created_at
                FROM windowed ti3
                WHERE ti3.tool_name = w.tool_name AND ti3.status = 'error'
                ORDER BY created_at DESC
                LIMIT 1
            ) AS last_error_at
        FROM windowed w
        GROUP BY tool_name
        ORDER BY COUNT(*) DESC, tool_name ASC
    """
    rows: list[dict[str, Any]] = []
    with db._connect() as conn:
        for row in conn.execute(sql, (threshold,)).fetchall():
            success = int(row["success_count"])
            error = int(row["error_count"])
            denominator = success + error
            success_rate: float | None
            if denominator > 0:
                success_rate = round(success / denominator, 4)
            else:
                success_rate = None
            rows.append(
                {
                    "tool_name": row["tool_name"],
                    "call_count": int(row["call_count"]),
                    "success_count": success,
                    "error_count": error,
                    "retry_then_success_count": int(row["retry_then_success_count"]),
                    "expected_no_result_count": int(row["expected_no_result_count"]),
                    "success_rate": success_rate,
                    "last_error_type": row["last_error_type"],
                    "last_error_at": row["last_error_at"],
                }
            )
    return rows
