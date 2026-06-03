"""Pure per-OS service-definition generators (REMOTE-04 / TEST-30).

Each generator returns the platform-native always-on service definition as a
string (or, for NSSM, a list of command strings) and never touches the OS.
Both ``horus-os service install --print`` and the cross-OS TEST-30 suite call
these functions directly, so the dry-run path and the assertion path are the
same OS-free code (RESEARCH OQ 3).

The definitions configure restart-on-failure on every platform: systemd
``Restart=on-failure``, launchd ``KeepAlive``, and NSSM ``AppExit Default
Restart``. They embed no API keys (CLAUDE.md rule 1); only HORUS_OS_DATA_DIR is
set, and provider keys are documented as a separate forwarding step (Pitfall
10). Paths computed here use pathlib (cross-OS rule); systemd uses the ``%h``
home specifier so no personal path is ever written into a committed template.
"""

from __future__ import annotations

from pathlib import PurePosixPath

SERVICE_NAME = "horus-os"
LAUNCHD_LABEL = "sh.horus-os"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

# systemd %h-relative defaults (the unit is a user unit; %h is the user's home).
_SYSTEMD_EXEC = ".local/bin/horus-os"
_SYSTEMD_DATA_DIR = ".local/share/horus-os"


def generate_systemd_unit(
    *,
    data_dir: str | None = None,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> str:
    """Return a systemd --user unit string for the always-on service (Linux).

    The unit launches ``horus-os serve`` with restart-on-failure and a 5s
    restart delay, sets HORUS_OS_DATA_DIR, and installs into the user's
    default.target so it starts on login. ``%h`` is the systemd home
    specifier; when ``data_dir`` is None the data dir defaults to a
    %h-relative path so no personal path appears in the template.
    """
    exec_path = f"%h/{PurePosixPath(_SYSTEMD_EXEC).as_posix()}"
    if data_dir is None:
        data_value = f"%h/{PurePosixPath(_SYSTEMD_DATA_DIR).as_posix()}"
    else:
        data_value = data_dir
    return (
        "[Unit]\n"
        "Description=horus-os always-on service\n"
        "After=network-online.target\n"
        "\n"
        "[Service]\n"
        f"ExecStart={exec_path} serve --host {host} --port {port}\n"
        "Restart=on-failure\n"
        "RestartSec=5\n"
        f"Environment=HORUS_OS_DATA_DIR={data_value}\n"
        "\n"
        "[Install]\n"
        "WantedBy=default.target\n"
    )


def generate_launchd_plist(
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> str:
    """Return a launchd LaunchAgent plist string (macOS).

    The agent runs ``horus-os serve`` at login (RunAtLoad) and is kept alive
    on exit (KeepAlive), giving restart-on-failure semantics for the user
    session. The program path is left as the conventional Homebrew location so
    no personal path is embedded; users adjust it if their install differs.
    """
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n'
        "<dict>\n"
        "  <key>Label</key>\n"
        f"  <string>{LAUNCHD_LABEL}</string>\n"
        "  <key>ProgramArguments</key>\n"
        "  <array>\n"
        "    <string>/usr/local/bin/horus-os</string>\n"
        "    <string>serve</string>\n"
        "    <string>--host</string>\n"
        f"    <string>{host}</string>\n"
        "    <string>--port</string>\n"
        f"    <string>{port}</string>\n"
        "  </array>\n"
        "  <key>RunAtLoad</key>\n"
        "  <true/>\n"
        "  <key>KeepAlive</key>\n"
        "  <true/>\n"
        "</dict>\n"
        "</plist>\n"
    )


def generate_nssm_commands(
    *,
    exe_path: str,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> list[str]:
    """Return the NSSM command set that registers the service (Windows).

    NSSM gives true restart-on-failure via ``AppExit Default Restart`` plus
    throttle and restart-delay controls. The returned list is the ordered set
    of ``nssm`` invocations the install path runs; tests assert on the content
    and the install path shells them out one by one.
    """
    return [
        f'nssm install {SERVICE_NAME} "{exe_path}" serve --host {host} --port {port}',
        f"nssm set {SERVICE_NAME} AppExit Default Restart",
        f"nssm set {SERVICE_NAME} AppThrottle 5000",
        f"nssm set {SERVICE_NAME} AppRestartDelay 3000",
        f"nssm start {SERVICE_NAME}",
    ]
