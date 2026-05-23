"""`horus-os traces` subcommand."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from typing import TextIO

from horus_os.config import Config
from horus_os.storage import Database


def run_traces(args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO) -> int:
    config = Config.load(getattr(args, "data_dir", None))
    if not config.db_path.exists():
        stderr.write(f"No database at {config.db_path}. Run `horus-os init` first.\n")
        return 1
    db = Database(config.db_path)
    limit = max(1, getattr(args, "limit", 20))
    traces = db.list_traces(limit=limit)
    if not traces:
        stdout.write("(no traces yet)\n")
        return 0
    if getattr(args, "json", False):
        payload = [_trace_to_dict(t) for t in traces]
        stdout.write(json.dumps(payload, indent=2) + "\n")
        return 0
    stdout.write(_format_table(traces) + "\n")
    return 0


def _trace_to_dict(record) -> dict:
    data = asdict(record)
    data["tool_uses"] = [asdict(use) for use in record.tool_uses]
    return data


def _format_table(traces) -> str:
    header = f"{'created_at':24}  {'provider':10}  {'model':30}  {'status':8}  prompt"
    lines = [header, "-" * len(header)]
    for t in traces:
        prompt_preview = (t.prompt[:60] + "...") if len(t.prompt) > 63 else t.prompt
        lines.append(
            f"{t.created_at:24}  {t.provider:10}  {t.model:30}  {t.status:8}  {prompt_preview}"
        )
    return "\n".join(lines)
