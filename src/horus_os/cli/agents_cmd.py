"""`horus-os agents` subcommand.

Drives the Phase 12 ``AgentProfile`` CRUD methods on ``Database`` via a flat
set of nested argparse subcommands (``list``, ``show``, ``create``, ``edit``,
``delete``). Output is plain text with a stable column layout so downstream
tools can parse the table without a JSON flag.
"""

from __future__ import annotations

import argparse
from typing import TextIO

from horus_os.config import Config
from horus_os.storage import Database
from horus_os.types import AgentProfile


def run_agents(args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO) -> int:
    config = Config.load(getattr(args, "data_dir", None))
    if not config.db_path.exists():
        stderr.write(f"No database at {config.db_path}. Run `horus-os init` first.\n")
        return 1
    db = Database(config.db_path)
    op = getattr(args, "agents_command", None) or "list"
    if op == "list":
        return _cmd_list(db, stdout)
    if op == "show":
        return _cmd_show(db, args.name, stdout, stderr)
    if op == "create":
        return _cmd_create(db, args, stdout, stderr)
    if op == "edit":
        return _cmd_edit(db, args, stdout, stderr)
    if op == "delete":
        return _cmd_delete(db, args.name, stdout, stderr)
    stderr.write(f"Unknown agents operation: {op!r}\n")
    return 2


def _cmd_list(db: Database, stdout: TextIO) -> int:
    profiles = db.list_profiles()
    if not profiles:
        stdout.write("(no agent profiles yet)\n")
        return 0
    stdout.write(_format_profiles_table(profiles) + "\n")
    return 0


def _format_profiles_table(profiles: list[AgentProfile]) -> str:
    header = f"{'name':24}  {'model':30}  system_prompt"
    lines = [header, "-" * 80]
    for p in profiles:
        model = p.default_model or "(default)"
        prompt = p.system_prompt or ""
        preview = (prompt[:40] + "...") if len(prompt) > 43 else prompt
        lines.append(f"{p.name:24}  {model:30}  {preview}")
    return "\n".join(lines)


def _cmd_show(db: Database, name: str, stdout: TextIO, stderr: TextIO) -> int:
    profile = db.load_profile(name)
    if profile is None:
        stderr.write(f"No agent profile named {name!r}.\n")
        return 1
    model = profile.default_model or "(default)"
    if profile.allowed_tools is None:
        allowed = "(all)"
    elif not profile.allowed_tools:
        allowed = "(none)"
    else:
        allowed = ",".join(profile.allowed_tools)
    memory_scope = profile.memory_scope or "(none)"
    stdout.write(
        f"name:           {profile.name}\n"
        f"default_model:  {model}\n"
        f"allowed_tools:  {allowed}\n"
        f"memory_scope:   {memory_scope}\n"
        f"created_at:     {profile.created_at}\n"
        f"updated_at:     {profile.updated_at}\n"
        f"system_prompt:\n"
        f"{profile.system_prompt}\n"
    )
    return 0


def _cmd_create(db: Database, args: argparse.Namespace, stdout: TextIO, stderr: TextIO) -> int:
    name: str = args.name
    if db.load_profile(name) is not None:
        stderr.write(f"Profile {name!r} already exists. Use `agents edit` to update.\n")
        return 1
    allowed = _parse_allowed_tools(getattr(args, "allowed_tools", None))
    profile = AgentProfile(
        name=name,
        system_prompt=args.system_prompt,
        default_model=getattr(args, "model", None),
        allowed_tools=allowed,
        memory_scope=getattr(args, "memory_scope", None),
    )
    db.save_profile(profile)
    stdout.write(f"Created agent profile {name!r}.\n")
    return 0


def _cmd_edit(db: Database, args: argparse.Namespace, stdout: TextIO, stderr: TextIO) -> int:
    name: str = args.name
    profile = db.load_profile(name)
    if profile is None:
        stderr.write(f"No agent profile named {name!r}.\n")
        return 1
    if getattr(args, "system_prompt", None) is not None:
        profile.system_prompt = args.system_prompt
    if getattr(args, "model", None) is not None:
        profile.default_model = args.model
    raw_allowed = getattr(args, "allowed_tools", None)
    if raw_allowed is not None:
        profile.allowed_tools = _parse_allowed_tools(raw_allowed)
    if getattr(args, "memory_scope", None) is not None:
        profile.memory_scope = args.memory_scope
    db.save_profile(profile)
    stdout.write(f"Updated agent profile {name!r}.\n")
    return 0


def _cmd_delete(db: Database, name: str, stdout: TextIO, stderr: TextIO) -> int:
    deleted = db.delete_profile(name)
    if not deleted:
        stderr.write(f"No agent profile named {name!r}.\n")
        return 1
    stdout.write(f"Deleted agent profile {name!r}.\n")
    return 0


def _parse_allowed_tools(raw: str | None) -> list[str] | None:
    """Convert a CLI --allowed-tools string into a list or sentinel.

    Returns None when ``raw`` is None or the literal "all" (unrestricted).
    Returns an empty list when ``raw`` is an empty string (explicit deny-all).
    Otherwise returns the comma-split tool names with surrounding whitespace
    trimmed and empty fragments dropped.
    """
    if raw is None:
        return None
    stripped = raw.strip()
    if stripped.lower() == "all":
        return None
    if stripped == "":
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]
