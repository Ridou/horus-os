"""Cross-OS end-to-end shell run (SE-4, TEST-36).

A benign command must run to completion through make_shell_tool on macOS,
Ubuntu, and Windows under Python 3.11 and 3.12. This test rides the standard
three-OS by two-Python pytest matrix; it adds no new CI job. Phase 76
install-smoke re-asserts import + run on all three OSes.

Portability notes:
  * The command is the running Python interpreter (sys.executable), which is
    present and directly executable via create_subprocess_exec on every OS. A
    bare "echo" is a shell builtin on Windows cmd.exe and is NOT a standalone
    executable there, so spawning "echo" with shell=False is not portable; the
    interpreter printing the token is the portable "benign echo" equivalent.
  * stdout line endings are normalised (CRLF -> LF, trailing newline stripped)
    so the assertion passes identically on Windows (SE-4).
  * The terminate-then-kill timeout path is exercised portably with a Python
    sleep longer than a short test timeout: no os.killpg, no signals, no
    bash-only assumptions.
"""

from __future__ import annotations

import sys
from pathlib import Path

from horus_os.storage import Database
from horus_os.tools.shell import make_shell_tool


def _make_db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    return db


def _make_tool(tmp_path: Path, db: Database, **overrides):
    work = tmp_path / "shell"
    work.mkdir(exist_ok=True)
    kwargs = dict(db=db, working_dir=work, timeout_seconds=30, output_cap_bytes=1_048_576)
    kwargs.update(overrides)
    return make_shell_tool(**kwargs)


def _normalise(text: str) -> str:
    """Collapse Windows CRLF and strip trailing newline so the OSes agree (SE-4)."""
    return text.replace("\r\n", "\n").strip()


def test_benign_echo_runs_end_to_end(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    tool = _make_tool(tmp_path, db)
    assert tool.handler is not None

    token = "horus-os-shell-ok"
    work = tmp_path / "shell"
    # The print() parentheses are themselves on the metacharacter denylist, so
    # the echo logic lives in a file the interpreter runs by name (no shell
    # string, shell=False semantics preserved on every OS).
    (work / "echo_token.py").write_text(f"import sys; sys.stdout.write({token!r})")

    result = tool.handler(command=sys.executable, args=["echo_token.py"])

    assert result["exit_code"] == 0
    assert _normalise(result["stdout"]) == token
    assert result["truncated"] is False

    # Exactly one ShellInvocation audit row was recorded for the run.
    rows = db.list_shell_invocations()
    assert len(rows) == 1
    assert rows[0].exit_code == 0
    assert _normalise(rows[0].stdout_truncated) == token


def test_timeout_terminate_then_kill_is_portable(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    tool = _make_tool(tmp_path, db, timeout_seconds=1)
    assert tool.handler is not None

    work = tmp_path / "shell"
    (work / "slow.py").write_text("import time; time.sleep(30)")

    result = tool.handler(command=sys.executable, args=["slow.py"])

    # A run past the timeout is terminated then killed (cross-OS, no os.killpg)
    # and recorded with exit_code None.
    assert result["exit_code"] is None
    rows = db.list_shell_invocations()
    assert len(rows) == 1
    assert rows[0].exit_code is None
