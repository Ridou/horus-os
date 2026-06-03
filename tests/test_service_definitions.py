"""Cross-OS service-definition generation tests (REMOTE-04 / TEST-30).

These tests pin the per-OS definition-content contracts Plan 03 implements:
the systemd --user unit, the launchd LaunchAgent plist, the NSSM command set,
and the pure-function principle behind the ``service install --print`` dry run
that emits the definition without touching the OS (so TEST-30 runs on all
three CI runners without admin and without external binaries).

The generators are PURE string functions, so this file (and the --print CLI
path covered in tests/test_service_cli.py) exercises exactly the same OS-free
code path on every runner.
"""

from __future__ import annotations

import inspect

from horus_os.service import definitions


def test_systemd_unit_content():
    """Generated systemd unit has ExecStart, Restart=on-failure, RestartSec."""
    unit = definitions.generate_systemd_unit()
    assert "[Unit]" in unit
    assert "[Service]" in unit
    assert "[Install]" in unit
    assert "horus-os serve" in unit
    assert "Restart=on-failure" in unit
    assert "RestartSec=5" in unit
    assert "Environment=HORUS_OS_DATA_DIR=" in unit
    assert "WantedBy=default.target" in unit


def test_launchd_plist_content():
    """Generated launchd plist has Label, ProgramArguments, KeepAlive, RunAtLoad."""
    plist = definitions.generate_launchd_plist()
    assert "sh.horus-os" in plist
    assert "<key>Label</key>" in plist
    assert "<key>ProgramArguments</key>" in plist
    assert "<key>RunAtLoad</key>" in plist
    assert "<key>KeepAlive</key>" in plist


def test_nssm_commands_content():
    """Generated NSSM commands set AppExit Default Restart plus throttle controls."""
    commands = definitions.generate_nssm_commands(exe_path="C:\\bin\\horus-os.exe")
    assert isinstance(commands, list)
    joined = "\n".join(commands)
    # restart-on-failure controls
    assert any("AppExit" in c and "Default" in c and "Restart" in c for c in commands)
    assert "AppThrottle" in joined
    assert "AppRestartDelay" in joined
    # install + lifecycle entries present
    assert any("install" in c for c in commands)


def test_install_print_emits_definition_without_touching_os():
    """The generators are pure: callable, non-empty, and import no subprocess."""
    unit = definitions.generate_systemd_unit()
    plist = definitions.generate_launchd_plist()
    commands = definitions.generate_nssm_commands(exe_path="C:\\bin\\horus-os.exe")
    assert unit and isinstance(unit, str)
    assert plist and isinstance(plist, str)
    assert commands and isinstance(commands, list)
    # Purity guard: the definitions module must not reach the OS via subprocess.
    source = inspect.getsource(definitions)
    assert "import subprocess" not in source
    assert "subprocess" not in source
