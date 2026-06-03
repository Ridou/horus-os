"""Per-OS service-lifecycle dispatch (REMOTE-04 / D-08 / D-09).

This module holds ALL OS-mutating subprocess calls for the always-on service,
so the pure ``definitions`` generators and the ``--print`` dry run never reach
the OS (TEST-30 stays OS-free). Dispatch is by ``sys.platform``:

  * ``linux``  -> systemd --user unit + ``systemctl --user`` lifecycle
  * ``darwin`` -> launchd LaunchAgent + ``launchctl`` lifecycle
  * ``win32``  -> NSSM service (``nssm`` must be on PATH; absence is guided,
    not crashed, per Pitfall 7 / D-12)

Linux and macOS honor D-08 (user-level, no admin). Windows NSSM is a SYSTEM
service requiring admin: a documented exception to D-08 (T-66-06), surfaced as
guidance rather than silently required. All paths use pathlib (cross-OS rule);
generated definitions set HORUS_OS_DATA_DIR and forward provider keys via the
user's environment (Pitfall 10). No em-dashes appear in any guidance string.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from horus_os.service import definitions

SERVICE_NAME = "horus-os"
SYSTEMD_UNIT_NAME = "horus-os.service"
LAUNCHD_LABEL = "sh.horus-os"
LAUNCHD_PLIST_NAME = "sh.horus-os.plist"

# Where each platform expects its definition (user-level, no admin).
_SYSTEMD_UNIT_PATH = Path(".config/systemd/user") / SYSTEMD_UNIT_NAME
_LAUNCHD_PLIST_PATH = Path("Library/LaunchAgents") / LAUNCHD_PLIST_NAME

_NSSM_GUIDANCE = (
    "nssm was not found on PATH. The Windows always-on service uses NSSM.\n"
    "Install it from https://nssm.cc/download or via a package manager:\n"
    "    choco install nssm\n"
    "    winget install NSSM.NSSM\n"
    "then re-run: horus-os service install\n"
    "Note: NSSM registers a system service and requires an administrator "
    "shell. The no-admin fallback is a Task Scheduler at-logon task (see "
    "docs/REMOTE.md).\n"
)


def _systemd_unit_path() -> Path:
    return Path.home() / _SYSTEMD_UNIT_PATH


def _launchd_plist_path() -> Path:
    return Path.home() / _LAUNCHD_PLIST_PATH


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a lifecycle command, capturing output, never raising on non-zero."""
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _uid() -> int:
    """Return the current numeric user id (launchd domain target)."""
    getuid = getattr(os, "getuid", None)
    return getuid() if getuid is not None else 0


def _nssm_missing() -> bool:
    return shutil.which("nssm") is None


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------


def install(*, data_dir: str | None = None) -> int:
    """Register the platform-native always-on service. Returns an exit code."""
    if sys.platform == "linux":
        return _install_linux(data_dir=data_dir)
    if sys.platform == "darwin":
        return _install_darwin()
    if sys.platform == "win32":
        return _install_windows()
    return 0


def _install_linux(*, data_dir: str | None) -> int:
    unit = definitions.generate_systemd_unit(data_dir=data_dir)
    path = _systemd_unit_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(unit, encoding="utf-8")
    _run(["systemctl", "--user", "daemon-reload"])
    result = _run(["systemctl", "--user", "enable", "--now", SYSTEMD_UNIT_NAME])
    return result.returncode


def _install_darwin() -> int:
    plist = definitions.generate_launchd_plist()
    path = _launchd_plist_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(plist, encoding="utf-8")
    result = _run(["launchctl", "bootstrap", f"gui/{_uid()}", str(path)])
    return result.returncode


def _split_command(command: str) -> list[str]:
    """Split an NSSM command string into argv, honoring quoted paths.

    ``str.split()`` shatters a quoted Windows path like ``"C:\\Program
    Files\\horus-os.exe"`` on its internal space and leaves literal quote
    characters in the tokens (WR-03). ``shlex.split(..., posix=False)`` splits
    on unquoted whitespace only and does not treat backslashes as escapes
    (so Windows paths survive); the surrounding quotes are then stripped so
    subprocess receives the path as a single clean argument.
    """
    return [token.strip('"') for token in shlex.split(command, posix=False)]


def _install_windows() -> int:
    if _nssm_missing():
        return 1
    exe = shutil.which(SERVICE_NAME) or SERVICE_NAME
    commands = definitions.generate_nssm_commands(exe_path=exe)
    for command in commands:
        result = _run(_split_command(command))
        # Stop on the first failing command so a failed `nssm install` is not
        # masked by a later command's success code (INFO from code review).
        if result.returncode != 0:
            return result.returncode
    return 0


# ---------------------------------------------------------------------------
# uninstall
# ---------------------------------------------------------------------------


def uninstall() -> int:
    """Remove the platform-native service. Returns an exit code."""
    if sys.platform == "linux":
        result = _run(["systemctl", "--user", "disable", "--now", SYSTEMD_UNIT_NAME])
        path = _systemd_unit_path()
        if path.exists():
            path.unlink()
        return result.returncode
    if sys.platform == "darwin":
        result = _run(["launchctl", "bootout", f"gui/{_uid()}/{LAUNCHD_LABEL}"])
        path = _launchd_plist_path()
        if path.exists():
            path.unlink()
        return result.returncode
    if sys.platform == "win32":
        if _nssm_missing():
            return 1
        result = _run(["nssm", "remove", SERVICE_NAME, "confirm"])
        return result.returncode
    return 0


# ---------------------------------------------------------------------------
# start / stop
# ---------------------------------------------------------------------------


def start() -> int:
    """Start the registered service. Returns an exit code."""
    if sys.platform == "linux":
        return _run(["systemctl", "--user", "start", SYSTEMD_UNIT_NAME]).returncode
    if sys.platform == "darwin":
        return _run(["launchctl", "kickstart", f"gui/{_uid()}/{LAUNCHD_LABEL}"]).returncode
    if sys.platform == "win32":
        if _nssm_missing():
            return 1
        return _run(["nssm", "start", SERVICE_NAME]).returncode
    return 0


def stop() -> int:
    """Stop the running service. Returns an exit code."""
    if sys.platform == "linux":
        return _run(["systemctl", "--user", "stop", SYSTEMD_UNIT_NAME]).returncode
    if sys.platform == "darwin":
        return _run(["launchctl", "bootout", f"gui/{_uid()}/{LAUNCHD_LABEL}"]).returncode
    if sys.platform == "win32":
        if _nssm_missing():
            return 1
        return _run(["nssm", "stop", SERVICE_NAME]).returncode
    return 0


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


def status() -> tuple[bool, str]:
    """Report whether the service is registered and running.

    Returns ``(running, report)`` where ``running`` is True only when the OS
    supervisor reports the service active. Never crashes when the supervisor
    binary is absent; instead it returns ``(False, guidance)``.
    """
    if sys.platform == "linux":
        return _status_linux()
    if sys.platform == "darwin":
        return _status_darwin()
    if sys.platform == "win32":
        return _status_windows()
    return False, f"Service management is not supported on {sys.platform!r}.\n"


def _status_linux() -> tuple[bool, str]:
    active = _run(["systemctl", "--user", "is-active", SYSTEMD_UNIT_NAME])
    enabled = _run(["systemctl", "--user", "is-enabled", SYSTEMD_UNIT_NAME])
    is_running = active.stdout.strip() == "active"
    linger = _run(["loginctl", "show-user", os.environ.get("USER", ""), "--property=Linger"])
    linger_value = linger.stdout.strip() or "Linger=unknown"
    report = (
        f"systemd --user {SYSTEMD_UNIT_NAME}\n"
        f"  active:  {active.stdout.strip() or 'unknown'}\n"
        f"  enabled: {enabled.stdout.strip() or 'unknown'}\n"
        f"  {linger_value}\n"
        "  Note: without lingering the service stops at logout; "
        "enable it with: loginctl enable-linger $USER\n"
    )
    return is_running, report


def _status_darwin() -> tuple[bool, str]:
    result = _run(["launchctl", "print", f"gui/{_uid()}/{LAUNCHD_LABEL}"])
    is_running = result.returncode == 0
    state = "loaded" if is_running else "not loaded"
    report = (
        f"launchd LaunchAgent {LAUNCHD_LABEL}\n"
        f"  state: {state}\n"
        "  Note: the agent runs while you are logged in to a GUI session.\n"
    )
    return is_running, report


def _status_windows() -> tuple[bool, str]:
    if _nssm_missing():
        return False, _NSSM_GUIDANCE
    result = _run(["nssm", "status", SERVICE_NAME])
    state = result.stdout.strip() or "UNKNOWN"
    is_running = state == "SERVICE_RUNNING"
    report = f"NSSM service {SERVICE_NAME}\n  status: {state}\n"
    return is_running, report
