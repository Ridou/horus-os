"""`horus-os init` subcommand."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TextIO

from horus_os.cli.wizard import run_wizard
from horus_os.config import CONFIG_FILENAME, Config
from horus_os.storage import Database


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

    if interactive:
        return run_wizard(config, stdin=sys.stdin, stdout=stdout)

    stdout.write(
        "\nSet ANTHROPIC_API_KEY or GEMINI_API_KEY in your environment, then try:\n"
        "  horus-os traces\n"
        "\nOr run `horus-os init --interactive` to set up keys with live validation.\n"
    )
    return 0
