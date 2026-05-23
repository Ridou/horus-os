"""Console entry point for horus-os."""

from __future__ import annotations

import argparse
import sys

from horus_os import __version__


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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
