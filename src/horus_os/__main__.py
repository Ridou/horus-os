"""Console entry point for horus-os."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TextIO

from horus_os import __version__
from horus_os.cli import run_init, run_run, run_serve, run_traces


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
    init_p.add_argument(
        "--interactive",
        action="store_true",
        help="Run the setup wizard with API key onboarding and live validation.",
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

    serve_p = sub.add_parser("serve", help="Start the local web dashboard and JSON API")
    serve_p.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind host (default 127.0.0.1).",
    )
    serve_p.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Bind port (default 8765).",
    )
    serve_p.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override the platform default data directory.",
    )
    serve_p.set_defaults(func=run_serve)

    run_p = sub.add_parser("run", help="Run a single agent prompt with the configured tools")
    run_p.add_argument("prompt", help="The user prompt to send to the agent.")
    run_p.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override the platform default data directory.",
    )
    run_p.add_argument(
        "--provider",
        choices=["anthropic", "gemini"],
        default=None,
        help="Override the default LLM provider from config.",
    )
    run_p.add_argument(
        "--model",
        default=None,
        help="Override the default model from config.",
    )
    run_p.add_argument(
        "--max-iterations",
        dest="max_iterations",
        type=int,
        default=10,
        help="Maximum tool-use iterations before forcing the loop to stop (default 10).",
    )
    run_p.add_argument(
        "--no-record",
        dest="no_record",
        action="store_true",
        help="Do not persist a trace row for this run.",
    )
    run_p.set_defaults(func=run_run)

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
