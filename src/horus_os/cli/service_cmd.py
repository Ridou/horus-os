"""`horus-os service` subcommand (REMOTE-04 / D-09).

Drives the always-on service lifecycle (install, uninstall, start, stop,
status) via the per-OS dispatch in ``horus_os.service.manager``. The
``install`` leaf carries a ``--print`` dry-run flag that emits the generated
definition for the current platform WITHOUT touching the OS, calling only the
pure ``definitions`` generators (the same code path TEST-30 asserts on, so the
dry run never reaches a subprocess; Pitfall 7 / RESEARCH OQ 3).

A missing ``nssm`` binary on Windows surfaces install guidance with a non-zero
exit code rather than crashing (D-12).
"""

from __future__ import annotations

import argparse
import sys
from typing import TextIO

from horus_os.service import definitions, manager


def run_service(args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO) -> int:
    op = getattr(args, "service_command", None) or "status"
    if op == "install":
        return _cmd_install(args, stdout, stderr)
    if op == "uninstall":
        return _delegate(manager.uninstall(), "uninstall", stdout, stderr)
    if op == "start":
        return _delegate(manager.start(), "start", stdout, stderr)
    if op == "stop":
        return _delegate(manager.stop(), "stop", stdout, stderr)
    if op == "status":
        return _cmd_status(stdout, stderr)
    stderr.write(f"Unknown service operation: {op!r}\n")
    return 2


def _cmd_install(args: argparse.Namespace, stdout: TextIO, stderr: TextIO) -> int:
    """Install the service, or with --print emit the definition as a dry run."""
    if getattr(args, "print", False):
        stdout.write(_print_definition())
        return 0
    data_dir = getattr(args, "data_dir", None)
    data_dir_str = str(data_dir) if data_dir is not None else None
    code = manager.install(data_dir=data_dir_str)
    if code != 0:
        # On Windows a missing nssm binary is the common cause; surface guidance.
        _, report = manager.status()
        stderr.write(report)
        return code
    stdout.write("Installed the horus-os always-on service.\n")
    return 0


def _print_definition() -> str:
    """Return the generated definition for the current platform (OS-free)."""
    if sys.platform == "linux":
        return definitions.generate_systemd_unit()
    if sys.platform == "darwin":
        return definitions.generate_launchd_plist()
    if sys.platform == "win32":
        return "\n".join(definitions.generate_nssm_commands(exe_path="horus-os.exe")) + "\n"
    return f"Service management is not supported on {sys.platform!r}.\n"


def _cmd_status(stdout: TextIO, stderr: TextIO) -> int:
    running, report = manager.status()
    stdout.write(report)
    return 0 if running else 1


def _delegate(code: int, op: str, stdout: TextIO, stderr: TextIO) -> int:
    if code != 0:
        _, report = manager.status()
        stderr.write(report)
        return code
    stdout.write(f"Service {op} succeeded.\n")
    return 0
