"""horus-os CLI subcommand handlers.

Each subcommand exposes `run_<name>(args, *, stdout, stderr) -> int`.
The top-level argparse dispatcher in `horus_os.__main__` builds the
parser, parses arguments, and calls the matching `run_*` function.

Splitting stdout and stderr through explicit kwargs keeps the
subcommands testable without subprocesses; tests pass StringIO buffers
and assert on captured text.
"""

from horus_os.cli.agents_cmd import run_agents
from horus_os.cli.init_cmd import run_init
from horus_os.cli.run_cmd import run_run
from horus_os.cli.serve_cmd import run_serve
from horus_os.cli.traces_cmd import run_traces

__all__ = ["run_agents", "run_init", "run_run", "run_serve", "run_traces"]
