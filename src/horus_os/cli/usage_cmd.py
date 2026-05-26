"""`horus-os usage` subcommand.

The usage report aggregates cost, latency, and tool-reliability data
over a window (default 7d) and emits it as JSON, CSV, or a table. The
implementation reuses `horus_os.observability.queries` so the CLI and
the dashboard cannot disagree about what a number means (USAGE-03).

All cost floats are rounded to 6 decimals via Python `round(value, 6)`
BEFORE serialization (USAGE-04). The 6-decimal rounding eliminates the
float-precision noise that breaks `jq` and `column` pipes downstream
(for example, `0.04200000000000001` becomes `0.042`).
"""

from __future__ import annotations

import argparse
import json
from typing import Any, TextIO

from horus_os.config import Config
from horus_os.observability.queries import (
    cost_by_agent,
    parse_window,
    tool_reliability,
)
from horus_os.storage import Database

# Field-name suffix list used by every formatter for type coercion. Any
# key whose name ends with one of these is cast to int (defensive guard
# against SQLite NULL float drift); the queries module already returns
# ints for these keys but the cast keeps the contract explicit.
_INT_SUFFIXES = ("_ms", "_tokens", "_count", "_runs", "_calls")
# Cost / rate keys round to 6 decimals via Python round() BEFORE
# serialization (USAGE-04 precision contract). Listed explicitly so
# adding a new field requires a deliberate edit rather than relying on
# implicit name matching.
_COST_KEYS = frozenset({"total_cost_usd", "cost_usd", "success_rate"})


def run_usage(args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO) -> int:
    """Print a usage report over the requested window in the requested format."""
    config = Config.load(getattr(args, "data_dir", None))
    if not config.db_path.exists():
        stderr.write(f"No database at {config.db_path}. Run `horus-os init` first.\n")
        return 1
    since = getattr(args, "since", "7d")
    # Validate the window up front so a bad arg fails fast at the CLI
    # boundary, mirroring the route boundary's ValueError -> 400 hop in
    # server/api.py. The query functions parse_window themselves on the
    # actual call below; this pre-flight catches bogus input before any
    # DB work happens.
    try:
        parse_window(since)
    except ValueError as exc:
        stderr.write(f"{exc}\n")
        return 1
    db = Database(config.db_path)
    by = getattr(args, "by", "agent")
    if by == "agent":
        rows = cost_by_agent(db, since)
    elif by == "tool":
        rows = tool_reliability(db, since)
    elif by == "model":
        rows = _cost_by_model_dispatch(db, since)
    else:  # pragma: no cover - argparse choices prevent this
        stderr.write(f"unknown --by value: {by!r}\n")
        return 1
    fmt = getattr(args, "format", "table")
    if fmt == "json":
        stdout.write(_format_json(rows, by=by, since=since) + "\n")
    elif fmt == "csv":
        stdout.write(_format_csv(rows) + "\n")
    elif fmt == "table":
        stdout.write(_format_table(rows) + "\n")
    else:  # pragma: no cover - argparse choices prevent this
        stderr.write(f"unknown --format value: {fmt!r}\n")
        return 1
    return 0


def _cost_by_model_dispatch(db: Database, since: str) -> list[dict[str, Any]]:
    """Placeholder dispatch for `--by model`; real impl lands in Task 4."""
    raise NotImplementedError("--by model lands in Task 4 of plan 37-01")


def _round_row(row: dict[str, Any]) -> dict[str, Any]:
    """Round cost floats to 6 decimals and cast known-int suffix fields.

    Shared by every formatter so the JSON, CSV, and table outputs all
    carry the same numeric values (USAGE-04 cross-format parity). None
    values pass through unchanged so the Pitfall 11 honesty contract
    (None for uncosted, never 0) survives serialization in every shape.
    """
    out: dict[str, Any] = {}
    for key, value in row.items():
        if value is None:
            out[key] = None
            continue
        if key in _COST_KEYS:
            # round(value, 6) is the USAGE-04 contract. Python round
            # (NOT format strings, NOT SQLite ROUND which is platform-
            # variable on the 3-OS CI matrix) eliminates the
            # 0.04200000000000001 float-noise that breaks jq and column
            # pipes downstream.
            out[key] = round(float(value), 6)
            continue
        if any(key.endswith(suffix) for suffix in _INT_SUFFIXES):
            out[key] = int(value)
            continue
        out[key] = value
    return out


def _format_json(rows: list[dict[str, Any]], *, by: str, since: str) -> str:
    """Serialize rows as JSON wrapped in a {by, since, rows} envelope.

    The wrapper shape makes `jq '.rows[]'` work uniformly across the
    three --by modes. `sort_keys=True` keeps the output diff-stable
    against the pinned fixture in tests/fixtures/usage_output_schema.json
    so schema drift fails the test loudly.
    """
    processed = [_round_row(r) for r in rows]
    payload = {"by": by, "since": since, "rows": processed}
    return json.dumps(payload, indent=2, sort_keys=True)


def _format_csv(rows: list[dict[str, Any]]) -> str:
    """Placeholder formatter; real impl lands in Task 2/3 of plan 37-01."""
    raise NotImplementedError("formatter lands in Task 2/3 of plan 37-01")


def _format_table(rows: list[dict[str, Any]]) -> str:
    """Placeholder formatter; real impl lands in Task 2/3 of plan 37-01."""
    raise NotImplementedError("formatter lands in Task 2/3 of plan 37-01")
