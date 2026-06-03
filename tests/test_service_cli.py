"""Service CLI lifecycle tests (REMOTE-04 / TEST-30).

These tests pin the service-lifecycle CLI contracts Plan 03 implements:
per-OS install dispatch over a MOCKED subprocess (never a live install), the
``--print`` dry run that emits the generated definition without invoking any
subprocess, and ``doctor --service`` reporting the supervisor status. NSSM is
never required at test time; dispatch is asserted against the mocked subprocess
calls, so this suite runs on all three CI runners without admin or external
binaries (Pitfall 7).
"""

from __future__ import annotations

import argparse
import io

from horus_os.cli.doctor_cmd import run_doctor
from horus_os.cli.service_cmd import run_service
from horus_os.service import definitions, manager


def test_service_install_dispatch_per_os_mocked_subprocess(monkeypatch):
    """install dispatches the correct per-OS command; --print invokes no subprocess."""
    # --- live install on linux invokes systemctl via the mocked subprocess ---
    monkeypatch.setattr(manager.sys, "platform", "linux")
    calls: list[list[str]] = []

    class _Result:
        returncode = 0
        stdout = ""
        stderr = ""

    def _fake_run(cmd, *args, **kwargs):
        calls.append(cmd)
        return _Result()

    monkeypatch.setattr(manager.subprocess, "run", _fake_run)
    # avoid writing a real unit file into the developer home during the test
    monkeypatch.setattr(manager.Path, "home", classmethod(lambda cls: tmp_home(monkeypatch)))

    out, err = io.StringIO(), io.StringIO()
    args = argparse.Namespace(service_command="install", print=False, data_dir=None)
    rc = run_service(args, stdout=out, stderr=err)
    assert rc == 0
    # systemctl --user was the dispatched supervisor command on linux
    assert any(cmd[:2] == ["systemctl", "--user"] for cmd in calls)

    # --- --print is a pure dry run: emits the definition, no subprocess ---
    calls.clear()
    out2, err2 = io.StringIO(), io.StringIO()
    args2 = argparse.Namespace(service_command="install", print=True, data_dir=None)
    rc2 = run_service(args2, stdout=out2, stderr=err2)
    assert rc2 == 0
    assert calls == []  # no OS mutation on the print path
    assert "Restart=on-failure" in out2.getvalue()


def tmp_home(monkeypatch):
    """Return a throwaway home directory under pytest's tmp area."""
    import tempfile
    from pathlib import Path

    return Path(tempfile.mkdtemp())


def test_doctor_service_reports_status(monkeypatch):
    """doctor --service returns 0 when running, non-zero otherwise; never crashes."""
    # running
    monkeypatch.setattr(manager, "status", lambda: (True, "service running\n"))
    out, err = io.StringIO(), io.StringIO()
    args = argparse.Namespace(service=True, supabase=False)
    rc = run_doctor(args, stdout=out, stderr=err)
    assert rc == 0
    assert "running" in out.getvalue()

    # not running -> non-zero
    monkeypatch.setattr(manager, "status", lambda: (False, "service not loaded\n"))
    out2, err2 = io.StringIO(), io.StringIO()
    args2 = argparse.Namespace(service=True, supabase=False)
    rc2 = run_doctor(args2, stdout=out2, stderr=err2)
    assert rc2 != 0

    # supervisor binary absent -> still returns an int, no traceback
    monkeypatch.setattr(manager, "status", lambda: (False, "nssm was not found on PATH\n"))
    out3, err3 = io.StringIO(), io.StringIO()
    args3 = argparse.Namespace(service=True, supabase=False)
    rc3 = run_doctor(args3, stdout=out3, stderr=err3)
    assert isinstance(rc3, int)
    assert rc3 != 0


def test_nssm_command_split_preserves_quoted_program_files_path():
    """The NSSM command splitter keeps a quoted Windows path as one clean arg (WR-03)."""
    exe = "C:\\Program Files\\horus-os\\horus-os.exe"
    install_cmd = definitions.generate_nssm_commands(exe_path=exe)[0]
    argv = manager._split_command(install_cmd)
    # The exe path is a single argv element with the surrounding quotes stripped
    # and the internal space preserved (str.split() would have shattered it).
    assert exe in argv
    # No token carries a literal double-quote, and the path was not broken apart.
    assert all('"' not in token for token in argv)
    assert "C:\\Program" not in argv
