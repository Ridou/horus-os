"""Tests for the gated shell tool (Phase 75, SHELL-02 + SHELL-03, TEST-36).

The pure helpers (reject_metacharacters, resolve_within, truncate_bytes) are the
security boundary, so they are unit-tested in isolation. The make_shell_tool
factory is exercised end-to-end against the real subprocess path using the
current Python interpreter as the command, which is present on every OS in the
CI matrix (no bash-only assumptions; cross-OS terminate-then-kill detail lives
in tests/test_shell_cross_os.py from plan 75-02).
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

from horus_os.storage import Database
from horus_os.tools import shell
from horus_os.tools.shell import (
    make_shell_tool,
    reject_metacharacters,
    resolve_within,
    truncate_bytes,
)

# --- reject_metacharacters (SE-2) -------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        ["grep", "x", ";rm -rf /"],
        ["grep", "x", "a|b"],
        ["echo", "a && b"],
        ["echo", "a || b"],
        ["echo", "$(whoami)"],
        ["echo", "`whoami`"],
        ["echo", "a > b"],
        ["echo", "a < b"],
        ["echo", "(sub)"],
        ["echo", "line1\nline2"],
    ],
)
def test_metacharacters_rejected(bad: list[str]) -> None:
    with pytest.raises(ValueError):
        reject_metacharacters(bad)


def test_clean_arg_list_passes_metacharacter_check() -> None:
    # Returns None, raises nothing.
    assert reject_metacharacters(["grep", "-r", "keyword", "notes.md"]) is None


def test_metacharacter_error_names_the_operator() -> None:
    with pytest.raises(ValueError, match=";"):
        reject_metacharacters(["echo", "a;b"])


# --- resolve_within (SE-3) --------------------------------------------------


def test_resolve_within_accepts_in_root_relative_path(tmp_path: Path) -> None:
    root = tmp_path / "sandbox"
    root.mkdir()
    resolved = resolve_within(root, "data/file.txt")
    assert resolved == (root / "data" / "file.txt").resolve()
    assert resolved.is_relative_to(root.resolve())


def test_resolve_within_accepts_root_itself(tmp_path: Path) -> None:
    root = tmp_path / "sandbox"
    root.mkdir()
    assert resolve_within(root, ".") == root.resolve()


def test_resolve_within_rejects_absolute_outside_path(tmp_path: Path) -> None:
    root = tmp_path / "sandbox"
    root.mkdir()
    outside = tmp_path / "secret.txt"
    with pytest.raises(PermissionError):
        resolve_within(root, str(outside))


def test_resolve_within_rejects_parent_traversal_escape(tmp_path: Path) -> None:
    root = tmp_path / "sandbox"
    root.mkdir()
    with pytest.raises(PermissionError):
        resolve_within(root, "../../etc/passwd")


def test_resolve_within_uses_is_relative_to(tmp_path: Path) -> None:
    # The boundary must use Path.resolve().is_relative_to(), not string prefix.
    root = tmp_path / "sandbox"
    root.mkdir()
    sibling = tmp_path / "sandbox-evil"
    sibling.mkdir()
    # A string-prefix check would accept "sandbox-evil" as starting with the
    # "sandbox" root string; is_relative_to correctly rejects it.
    with pytest.raises(PermissionError):
        resolve_within(root, str(sibling / "x"))


# --- truncate_bytes ---------------------------------------------------------


def test_truncate_bytes_caps_and_flags() -> None:
    text, truncated = truncate_bytes(b"abcdef", 3)
    assert text == "abc"
    assert truncated is True


def test_truncate_bytes_passes_short_payload_unflagged() -> None:
    text, truncated = truncate_bytes(b"abc", 100)
    assert text == "abc"
    assert truncated is False


def test_truncate_bytes_replaces_undecodable_bytes() -> None:
    text, truncated = truncate_bytes(b"\xff\xfe", 100)
    assert truncated is False
    assert isinstance(text, str)  # errors=replace never raises


# --- source-level safety gate (SE-2 / SE-4) ---------------------------------


def test_module_never_uses_shell_true_or_os_system_or_killpg() -> None:
    source = inspect.getsource(shell)
    assert "shell=True" not in source
    assert "os.system" not in source
    assert "os.killpg" not in source
    assert "create_subprocess_exec" in source


# --- make_shell_tool factory (SHELL-02 + SHELL-03) --------------------------


def _make_db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    return db


def _make_tool(tmp_path: Path, db: Database, **overrides):
    work = tmp_path / "shell"
    work.mkdir(exist_ok=True)
    kwargs = dict(
        db=db,
        working_dir=work,
        timeout_seconds=30,
        output_cap_bytes=1_048_576,
    )
    kwargs.update(overrides)
    return make_shell_tool(**kwargs)


def _write_script(tmp_path: Path, name: str, body: str) -> str:
    """Drop a Python script inside the working dir and return its relative name.

    The args list passed to the tool stays free of shell metacharacters (the
    parentheses in print(...) are themselves on the denylist), so the program
    logic lives in a file the interpreter runs by name.
    """
    work = tmp_path / "shell"
    work.mkdir(exist_ok=True)
    (work / name).write_text(body)
    return name


def test_tool_metadata(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    tool = _make_tool(tmp_path, db)
    assert tool.name == "shell_exec"
    assert "working directory" in tool.description
    assert tool.parameters["required"] == ["command", "args"]
    assert tool.parameters["properties"]["args"]["type"] == "array"


def test_benign_command_runs_and_returns_stdout(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    tool = _make_tool(tmp_path, db)
    assert tool.handler is not None
    script = _write_script(tmp_path, "hello.py", "import sys; sys.stdout.write('hello')")
    result = tool.handler(command=sys.executable, args=[script])
    assert result["exit_code"] == 0
    assert "hello" in result["stdout"]
    assert result["truncated"] is False
    # Exactly one audit row written for the run.
    rows = db.list_shell_invocations()
    assert len(rows) == 1
    assert rows[0].exit_code == 0
    assert "hello" in rows[0].stdout_truncated


def test_metacharacter_arg_rejected_without_spawn(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    tool = _make_tool(tmp_path, db)
    assert tool.handler is not None
    result = tool.handler(command=sys.executable, args=["script.py", ";rm -rf /"])
    assert result.get("error")
    assert result["exit_code"] is None
    # Audit row written, but the process never ran (exit_code None, no stdout).
    rows = db.list_shell_invocations()
    assert len(rows) == 1
    assert rows[0].exit_code is None
    assert rows[0].stdout_truncated == ""


def test_absolute_path_outside_working_dir_rejected(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    tool = _make_tool(tmp_path, db)
    assert tool.handler is not None
    outside = tmp_path / "secret.txt"
    result = tool.handler(command=sys.executable, args=[str(outside)])
    assert result.get("error")
    assert result["exit_code"] is None
    rows = db.list_shell_invocations()
    assert len(rows) == 1


def test_parent_traversal_path_rejected(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    tool = _make_tool(tmp_path, db)
    assert tool.handler is not None
    result = tool.handler(command=sys.executable, args=["../../escape.txt"])
    assert result.get("error")
    rows = db.list_shell_invocations()
    assert len(rows) == 1


def test_output_cap_truncates_and_flags(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    tool = _make_tool(tmp_path, db, output_cap_bytes=16)
    assert tool.handler is not None
    script = _write_script(tmp_path, "big.py", "import sys; sys.stdout.write('x' * 1000)")
    result = tool.handler(command=sys.executable, args=[script])
    assert result["exit_code"] == 0
    assert result["truncated"] is True
    assert len(result["stdout"]) <= 16


def test_timeout_kills_process_and_records_none_exit_code(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    tool = _make_tool(tmp_path, db, timeout_seconds=1)
    assert tool.handler is not None
    # A python sleep longer than the 1s test timeout is terminated then killed.
    script = _write_script(tmp_path, "slow.py", "import time; time.sleep(30)")
    result = tool.handler(command=sys.executable, args=[script])
    assert result["exit_code"] is None
    rows = db.list_shell_invocations()
    assert len(rows) == 1
    assert rows[0].exit_code is None


def test_confirm_mode_returns_pending_without_spawning(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    tool = _make_tool(tmp_path, db, confirm=True)
    assert tool.handler is not None
    script = _write_script(tmp_path, "noop.py", "import sys; sys.stdout.write('x')")
    result = tool.handler(command=sys.executable, args=[script])
    assert result.get("pending_confirmation") is True
    assert result["exit_code"] is None
    assert result["stdout"] == ""
    # The confirm path still writes exactly one audit row.
    rows = db.list_shell_invocations()
    assert len(rows) == 1


def test_trace_id_threaded_into_audit_row(tmp_path: Path) -> None:
    db = _make_db(tmp_path)
    tool = _make_tool(tmp_path, db, trace_id="trace-xyz")
    assert tool.handler is not None
    script = _write_script(tmp_path, "ok.py", "import sys; sys.stdout.write('ok')")
    tool.handler(command=sys.executable, args=[script])
    rows = db.list_shell_invocations()
    assert rows[0].trace_id == "trace-xyz"
