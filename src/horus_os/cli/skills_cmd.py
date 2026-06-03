"""`horus-os skills` subcommand.

Lists and shows the discoverable skill files under the configured skills folder
(the filesystem source of truth). Output is plain text with a stable column
layout, mirroring the agents subcommand. `list` shows name / kind / description
and notes any files that failed to parse; `show <name>` prints the full skill
including its body. The skills folder being the source of truth means there is
no database to query: SkillStore reads the directory directly.
"""

from __future__ import annotations

import argparse
from typing import TextIO

from horus_os.config import Config
from horus_os.skills import Skill, SkillStore


def run_skills(args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO) -> int:
    config = Config.load(getattr(args, "data_dir", None))
    store = SkillStore(config.skills_dir)
    op = getattr(args, "skills_command", None) or "list"
    if op == "list":
        return _cmd_list(store, config, stdout)
    if op == "show":
        return _cmd_show(store, config, args.name, stdout, stderr)
    stderr.write(f"Unknown skills operation: {op!r}\n")
    return 2


def _cmd_list(store: SkillStore, config: Config, stdout: TextIO) -> int:
    if not config.skills_dir.exists():
        stdout.write("No skills folder yet. Run `horus-os init` to create one.\n")
        return 0
    skills = store.list_skills()
    if not skills:
        stdout.write("(no skills yet)\n")
    else:
        stdout.write(_format_skills_table(skills) + "\n")
    errors = store.list_skill_errors()
    if errors:
        stdout.write(f"({len(errors)} skills with parse errors)\n")
    return 0


def _format_skills_table(skills: list[Skill]) -> str:
    header = f"{'name':24}  {'kind':16}  description"
    lines = [header, "-" * 80]
    for skill in skills:
        description = skill.description or ""
        preview = (description[:40] + "...") if len(description) > 43 else description
        lines.append(f"{skill.name:24}  {skill.kind:16}  {preview}")
    return "\n".join(lines)


def _cmd_show(
    store: SkillStore,
    config: Config,
    name: str,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    if not config.skills_dir.exists():
        stderr.write("No skills folder yet. Run `horus-os init` to create one.\n")
        return 1
    skill = store.get_skill(name)
    if skill is None:
        stderr.write(f"No skill named {name!r}.\n")
        return 1
    # Mirror the agents_cmd "(all)" / "(none)" sentinel convention for the
    # None-means-unrestricted allowed_tools field.
    if skill.allowed_tools is None:
        allowed = "(all)"
    elif not skill.allowed_tools:
        allowed = "(none)"
    else:
        allowed = ",".join(skill.allowed_tools)
    tags = ",".join(skill.tags) if skill.tags else "(none)"
    stdout.write(
        f"name:           {skill.name}\n"
        f"kind:           {skill.kind}\n"
        f"tags:           {tags}\n"
        f"allowed_tools:  {allowed}\n"
        f"rel_path:       {skill.rel_path}\n"
        f"body:\n"
        f"{skill.body}\n"
    )
    return 0
