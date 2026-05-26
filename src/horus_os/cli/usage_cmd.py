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
from typing import Any, TextIO

from horus_os.config import Config
from horus_os.observability.queries import (
    cost_by_agent,
    parse_window,
    tool_reliability,
)
from horus_os.storage import Database


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


def _format_json(rows: list[dict[str, Any]], *, by: str, since: str) -> str:
    """Placeholder formatter; real impl lands in Task 2/3 of plan 37-01."""
    raise NotImplementedError("formatter lands in Task 2/3 of plan 37-01")


def _format_csv(rows: list[dict[str, Any]]) -> str:
    """Placeholder formatter; real impl lands in Task 2/3 of plan 37-01."""
    raise NotImplementedError("formatter lands in Task 2/3 of plan 37-01")


def _format_table(rows: list[dict[str, Any]]) -> str:
    """Placeholder formatter; real impl lands in Task 2/3 of plan 37-01."""
    raise NotImplementedError("formatter lands in Task 2/3 of plan 37-01")
