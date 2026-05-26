"""`horus-os serve` subcommand."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import TextIO


def run_serve(args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO) -> int:
    host: str = getattr(args, "host", "127.0.0.1")
    port: int = getattr(args, "port", 8765)
    data_dir: Path | None = getattr(args, "data_dir", None)

    # ISOLATE-03 escape hatch: --disable-all-plugins sets the env var
    # BEFORE create_app() runs so the lifespan's plugin pipeline
    # short-circuits without ever calling discover_plugins(). The env
    # var is the authoritative gate (the lifespan reads it directly)
    # so any future caller — uvicorn worker, docker entrypoint, the
    # dashboard via os.execvp — can opt out without going through the
    # serve CLI.
    if getattr(args, "disable_all_plugins", False):
        os.environ["HORUS_OS_DISABLE_PLUGINS"] = "true"

    try:
        import uvicorn
    except ImportError:
        stderr.write(
            "horus-os serve requires the [dashboard] extra.\n"
            "Install it with:\n"
            "    pip install 'horus-os[dashboard]'\n"
        )
        return 2

    from horus_os.server import create_app

    app = create_app(data_dir=data_dir)
    stdout.write(f"Serving horus-os on http://{host}:{port}\n")
    uvicorn.run(app, host=host, port=port, log_level="warning")
    return 0
