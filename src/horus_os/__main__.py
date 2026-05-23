"""Console entry point for horus-os."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TextIO

from horus_os import __version__
from horus_os.cli import run_init, run_serve, run_traces


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="horus-os",
        description="An open-source, self-hosted autonomous AI command center.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"horus-os {__version__}",
    )

    sub = parser.add_subparsers(dest="command", metavar="<command>")

    init_p = sub.add_parser("init", help="Initialize a new horus-os installation")
    init_p.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override the platform default data directory.",
    )
    init_p.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing config file if one is present.",
    )
    init_p.set_defaults(func=run_init)

    traces_p = sub.add_parser("traces", help="List recent agent traces")
    traces_p.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override the platform default data directory.",
    )
    traces_p.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of traces to display (default 20).",
    )
    traces_p.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of a table.",
    )
    traces_p.set_defaults(func=run_traces)

    serve_p = sub.add_parser("serve", help="Start the local web dashboard (coming soon)")
    serve_p.set_defaults(func=run_serve)

    return parser


def main(
    argv: list[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help(file=out)
        return 0
    return args.func(args, stdout=out, stderr=err)


if __name__ == "__main__":
    sys.exit(main())
