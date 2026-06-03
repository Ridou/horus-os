"""`horus-os init` subcommand."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TextIO

from horus_os.cli.wizard import run_wizard
from horus_os.config import CONFIG_FILENAME, Config
from horus_os.seed import STARTER_TEAM, USER_NAME_PLACEHOLDER, read_soul, soul_rel_path, vault_notes
from horus_os.storage import Database, TaskRecord
from horus_os.types import AgentProfile, AgentResult


def _seed_starter_content(config: Config) -> tuple[list[str], int]:
    """Seed the starter team, example vault notes, and one demo trace.

    Only called on a fresh init. Returns the seeded agent display names and
    the count of example notes written. Existing files are never overwritten,
    so re-running is safe even though init guards against it.
    """
    notes_seeded = 0
    for filename, content in vault_notes():
        target = config.notes_dir / filename
        if not target.exists():
            target.write_text(content, encoding="utf-8")
            notes_seeded += 1

    for entry in STARTER_TEAM:
        name = entry["name"]
        soul_text = read_soul(name).replace(USER_NAME_PLACEHOLDER, "you")
        soul_target = config.notes_dir / "agents" / name / "SOUL.md"
        soul_target.parent.mkdir(parents=True, exist_ok=True)
        if not soul_target.exists():
            soul_target.write_text(soul_text, encoding="utf-8")

    db = Database(config.db_path)
    for entry in STARTER_TEAM:
        name = entry["name"]
        db.save_profile(
            AgentProfile(
                name=name,
                system_prompt=entry["system_prompt"],
                default_model=None,
                color=entry["color"],
                description=entry["description"],
                soul_path=soul_rel_path(name),
            )
        )

    db.record_trace(
        "How do I get started with horus-os?",
        AgentResult(
            text=(
                "Welcome. This is an example trace seeded on your first init so "
                "the dashboard is not empty. Open the welcome note in your vault "
                "for a tour of the starter team, then run your own prompt. You "
                "can clear this example by running a real prompt of your own."
            ),
            provider="example",
            model="example",
        ),
        agent_profile_name="Coordinator",
    )

    # Seed demo tasks: one per status that the UI renders, covering each starter agent.
    # INSERT OR IGNORE guards against re-seeding on subsequent (forced) inits.
    demo_tasks = [
        TaskRecord(
            task_id="demo-task-pending-001",
            title="Review the starter team configuration",
            description="Open the Team page to see the five starter agents and their roles.",
            status="pending",
            agent_profile_name="Coordinator",
            trace_id=None,
            is_demo_seed=True,
            created_at="",
            updated_at="",
        ),
        TaskRecord(
            task_id="demo-task-running-001",
            title="Analyze codebase structure",
            description="Scanning source files and building a dependency map.",
            status="running",
            agent_profile_name="Engineer",
            trace_id=None,
            is_demo_seed=True,
            created_at="",
            updated_at="",
        ),
        TaskRecord(
            task_id="demo-task-completed-001",
            title="Generate project overview note",
            description="Wrote a summary of the project to notes/project-overview.md.",
            status="completed",
            agent_profile_name="Writer",
            trace_id=None,
            is_demo_seed=True,
            created_at="",
            updated_at="",
        ),
        TaskRecord(
            task_id="demo-task-error-001",
            title="Fetch external documentation",
            description="Connection to remote host timed out. Retry when network is available.",
            status="error",
            agent_profile_name="Researcher",
            trace_id=None,
            is_demo_seed=True,
            created_at="",
            updated_at="",
        ),
        TaskRecord(
            task_id="demo-task-pending-002",
            title="Schedule weekly dependency audit",
            description="Check for outdated packages and open a summary note.",
            status="pending",
            agent_profile_name="Operator",
            trace_id=None,
            is_demo_seed=True,
            created_at="",
            updated_at="",
        ),
    ]
    for task in demo_tasks:
        db.save_task(task)

    return [entry["name"] for entry in STARTER_TEAM], notes_seeded


def run_init(args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO) -> int:
    data_dir: Path | None = getattr(args, "data_dir", None)
    force: bool = getattr(args, "force", False)
    interactive: bool = getattr(args, "interactive", False)
    config = Config.with_defaults(data_dir)
    config_path = config.data_dir / CONFIG_FILENAME

    already_initialized = config_path.exists()
    if already_initialized and not force and not interactive:
        stderr.write(
            f"horus-os is already initialized at {config.data_dir}.\n"
            f"Use --force to overwrite the config file, or --interactive to run the\n"
            f"setup wizard against the existing installation.\n"
        )
        return 1

    config.data_dir.mkdir(parents=True, exist_ok=True)
    config.notes_dir.mkdir(parents=True, exist_ok=True)
    Database(config.db_path).init()

    # Seed the starter team and example content only on a genuinely fresh
    # install. A --force reinit of an existing install must not re-seed.
    seeded: tuple[list[str], int] | None = None
    if not already_initialized:
        seeded = _seed_starter_content(config)

    if not already_initialized or force:
        config.save()

    label = "Reinitialized" if already_initialized and force else "Initialized"
    if already_initialized and interactive and not force:
        label = "Configured"
    stdout.write(
        f"{label} horus-os.\n"
        f"  data dir:   {config.data_dir}\n"
        f"  database:   {config.db_path}\n"
        f"  notes dir:  {config.notes_dir}\n"
        f"  config:     {config_path}\n"
        f"  provider:   {config.default_provider} ({config.anthropic_model})\n"
    )

    if seeded is not None:
        team_names, notes_seeded = seeded
        stdout.write(
            f"  team:       {', '.join(team_names)}\n"
            f"  examples:   {notes_seeded} notes seeded in the vault\n"
        )

    if interactive:
        return run_wizard(config, stdin=sys.stdin, stdout=stdout)

    stdout.write(
        "\nSet ANTHROPIC_API_KEY or GEMINI_API_KEY in your environment, then try:\n"
        "  horus-os traces\n"
        "\nOr run `horus-os init --interactive` to set up keys with live validation.\n"
    )
    return 0
