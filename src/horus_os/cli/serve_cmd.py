"""`horus-os serve` subcommand placeholder.

The full local dashboard and chat surface land in Phase 08. The stub
keeps the subcommand visible in `--help` so the future UX does not
surprise users who scripted around it.
"""

from __future__ import annotations

import argparse
from typing import TextIO


def run_serve(args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO) -> int:
    stdout.write(
        "horus-os serve is not yet implemented.\n"
        "The local dashboard and web chat ship in a later phase.\n"
        "Track progress in ROADMAP.md.\n"
    )
    return 0
