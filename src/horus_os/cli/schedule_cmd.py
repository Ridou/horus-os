"""`horus-os schedule` subcommand (REMOTE-05 / D-07).

Manages the ``schedules`` table from the CLI: create, list, edit, delete,
enable, and disable. This is the only management surface for schedules this
milestone (no dashboard UI, D-07).

Cron is the canonical stored form (D-01). A small explicit sugar table maps
human shorthand like ``every 30m`` to cron; ``@``-aliases (``@daily`` etc.)
and full cron expressions pass through after a ``croniter.is_valid`` check
that rejects garbage before anything is written (T-66-02).
"""

from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime
from typing import TextIO

from croniter import croniter

from horus_os.adapters.scheduler_adapter import next_fire, resolve_tz
from horus_os.config import Config
from horus_os.storage import Database, ScheduleRecord

# Explicit human-shorthand sugar. croniter natively understands the @-aliases
# (@hourly, @daily, ...); only this non-standard sugar needs desugaring here.
_SUGAR = {
    "every 1m": "* * * * *",
    "every 5m": "*/5 * * * *",
    "every 30m": "*/30 * * * *",
    "every 1h": "0 * * * *",
}


def to_cron(expr: str) -> str:
    """Desugar shorthand to canonical cron, validating the result (D-01).

    Raises ValueError for an expression that is neither known sugar, an
    @-alias, nor a valid cron string (T-66-02: reject garbage before storing).
    """
    expr = expr.strip()
    if expr in _SUGAR:
        return _SUGAR[expr]
    if not croniter.is_valid(expr):
        raise ValueError(f"not a valid cron expression: {expr!r}")
    return expr


def run_schedule(args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO) -> int:
    config = Config.load(getattr(args, "data_dir", None))
    if not config.db_path.exists():
        stderr.write(f"No database at {config.db_path}. Run `horus-os init` first.\n")
        return 1
    db = Database(config.db_path)
    op = getattr(args, "schedule_command", None) or "list"
    if op == "create":
        return _cmd_create(db, args, stdout, stderr)
    if op == "list":
        return _cmd_list(db, stdout)
    if op == "edit":
        return _cmd_edit(db, args, stdout, stderr)
    if op == "delete":
        return _cmd_delete(db, args.name, stdout, stderr)
    if op == "enable":
        return _cmd_set_enabled(db, args.name, True, stdout, stderr)
    if op == "disable":
        return _cmd_set_enabled(db, args.name, False, stdout, stderr)
    stderr.write(f"Unknown schedule operation: {op!r}\n")
    return 2


def _cmd_create(db: Database, args: argparse.Namespace, stdout: TextIO, stderr: TextIO) -> int:
    name: str = args.name
    try:
        cron_expression = to_cron(args.cron)
    except ValueError as exc:
        stderr.write(f"{exc}\n")
        return 1
    # Compute the initial next_run_at from now in the resolved timezone so the
    # scheduler fires the first run at the correct boundary (D-05).
    now = datetime.now(resolve_tz())
    next_run_at = next_fire(cron_expression, now).isoformat()
    try:
        db.create_schedule(
            name,
            cron_expression=cron_expression,
            agent_profile_name=args.profile,
            prompt=args.prompt,
            catch_up_policy=getattr(args, "catch_up", "coalesce"),
            next_run_at=next_run_at,
        )
    except sqlite3.IntegrityError:
        stderr.write(f"Schedule {name!r} already exists. Use `schedule edit` to update.\n")
        return 1
    stdout.write(f"Created schedule {name!r}.\n")
    return 0


def _cmd_list(db: Database, stdout: TextIO) -> int:
    schedules = db.list_schedules()
    if not schedules:
        stdout.write("(no schedules yet)\n")
        return 0
    stdout.write(_format_schedules_table(schedules) + "\n")
    return 0


def _format_schedules_table(schedules: list[ScheduleRecord]) -> str:
    header = f"{'name':20}  {'cron':16}  {'profile':16}  {'enabled':7}  next_run_at"
    lines = [header, "-" * 90]
    for s in schedules:
        enabled = "yes" if s.enabled else "no"
        next_run = s.next_run_at or "(unset)"
        lines.append(
            f"{s.name:20}  {s.cron_expression:16}  {s.agent_profile_name:16}  "
            f"{enabled:7}  {next_run}"
        )
    return "\n".join(lines)


def _cmd_edit(db: Database, args: argparse.Namespace, stdout: TextIO, stderr: TextIO) -> int:
    name: str = args.name
    if db.get_schedule(name) is None:
        stderr.write(f"No schedule named {name!r}.\n")
        return 1
    fields: dict[str, object] = {}
    raw_cron = getattr(args, "cron", None)
    if raw_cron is not None:
        try:
            fields["cron_expression"] = to_cron(raw_cron)
        except ValueError as exc:
            stderr.write(f"{exc}\n")
            return 1
    if getattr(args, "profile", None) is not None:
        fields["agent_profile_name"] = args.profile
    if getattr(args, "prompt", None) is not None:
        fields["prompt"] = args.prompt
    if getattr(args, "catch_up", None) is not None:
        fields["catch_up_policy"] = args.catch_up
    if not fields:
        stderr.write("Nothing to update. Pass --cron, --profile, --prompt, or --catch-up.\n")
        return 1
    db.update_schedule(name, **fields)
    stdout.write(f"Updated schedule {name!r}.\n")
    return 0


def _cmd_delete(db: Database, name: str, stdout: TextIO, stderr: TextIO) -> int:
    if not db.delete_schedule(name):
        stderr.write(f"No schedule named {name!r}.\n")
        return 1
    stdout.write(f"Deleted schedule {name!r}.\n")
    return 0


def _cmd_set_enabled(db: Database, name: str, enabled: bool, stdout: TextIO, stderr: TextIO) -> int:
    if db.get_schedule(name) is None:
        stderr.write(f"No schedule named {name!r}.\n")
        return 1
    db.set_schedule_enabled(name, enabled)
    verb = "Enabled" if enabled else "Disabled"
    stdout.write(f"{verb} schedule {name!r}.\n")
    return 0
