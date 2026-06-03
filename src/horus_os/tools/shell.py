"""Gated shell and code execution tool (Phase 75, SHELL-02 + SHELL-03).

This module is the security substrate for letting an agent run OS commands.
It ships three pure helpers that are the security boundary, plus the
``make_shell_tool`` factory that composes them. The factory's output is NOT
registered into any ToolRegistry here: registration sits behind the double
gate (config flag plus an explicit allowed_tools grant) wired in plan 75-02.

Design constraints, each a test assertion in TEST-36:
  * Commands run via ``asyncio.create_subprocess_exec(command, *args, ...)``
    with no-shell semantics: a structured args list, never a shell string and
    never an in-shell evaluation (SE-2).
  * ``reject_metacharacters`` raises on any shell operator BEFORE a subprocess
    is spawned (SE-2).
  * ``resolve_within`` rejects absolute paths and parent-traversal escapes via
    ``Path.resolve().is_relative_to()``, never string-prefix matching (SE-3).
  * the timeout uses ``asyncio.wait_for`` then a cross-OS terminate-then-kill,
    never a process-group signal call (SE-4).
  * ``truncate_bytes`` caps stdout at the configured limit and flags truncation.
  * one ShellInvocation audit row is written on every code path (SHELL-02).

This plan adds no new dependency; only stdlib ``asyncio.subprocess`` is used.
"""

from __future__ import annotations

import asyncio
import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

from horus_os.types import Tool

if TYPE_CHECKING:
    from horus_os.config import Config
    from horus_os.storage import Database
    from horus_os.tools.registry import ToolRegistry

# The runtime half of the SHELL-01 double gate. The shell tool registers ONLY
# when this environment variable is set to the exact string "true". It is read
# at registry-build time, never stored in Config, so toggling it never rewrites
# config.toml. This string-compare mirrors the calendar WRITE_ALLOWED_ENV idiom.
SHELL_ENABLED_ENV = "HORUS_OS_SHELL_ENABLED"

# Shell metacharacters that, in a real shell, chain or redirect commands. The
# tool never runs a shell, but rejecting these in any arg blocks an injected
# argument from being mistaken for a shell directive by a downstream consumer
# and documents the contract that args are literal tokens, not shell syntax
# (SE-2). The newline is included because it terminates a command line.
_METACHARACTERS: tuple[str, ...] = (
    ";",
    "|",
    "&",
    "$",
    "`",
    ">",
    "<",
    "(",
    ")",
    "\n",
    "\r",
)


def reject_metacharacters(args: list[str]) -> None:
    """Raise ValueError on the first arg that contains a shell metacharacter.

    A clean args list returns None. The error names the offending operator and
    the offending element so the audit trail records why a run was refused. This
    runs on ``[command, *args]`` BEFORE any subprocess is spawned (SE-2).
    """
    for element in args:
        for operator in _METACHARACTERS:
            if operator in element:
                shown = "newline" if operator in ("\n", "\r") else operator
                raise ValueError(
                    f"argument {element!r} contains the shell metacharacter "
                    f"{shown!r}; commands run as a structured arg list and may "
                    f"not contain shell operators"
                )


def resolve_within(root: Path, candidate: str) -> Path:
    """Resolve ``candidate`` and confirm it stays under ``root``.

    Returns the resolved path when it is ``root`` itself or a descendant of it.
    Raises PermissionError when the candidate is an absolute path outside root or
    a relative path that traverses out of root. The check uses
    ``Path.resolve().is_relative_to()`` rather than string-prefix matching, which
    is weaker on Windows drive paths (SE-3).
    """
    base = root.resolve()
    raw = Path(candidate)
    resolved = raw.resolve() if raw.is_absolute() else (base / raw).resolve()
    if not resolved.is_relative_to(base):
        raise PermissionError(
            f"path {candidate!r} resolves outside the configured working "
            f"directory and is not allowed"
        )
    return resolved


def truncate_bytes(data: bytes, cap: int) -> tuple[str, bool]:
    """Cap a bytes payload at ``cap`` bytes and decode it.

    Returns the decoded text (errors=replace so undecodable bytes never raise)
    and a flag that is True when the payload exceeded the cap and was cut. The
    cap is applied on the raw bytes before decoding so the byte budget is exact.
    """
    truncated = len(data) > cap
    capped = data[:cap] if truncated else data
    return capped.decode("utf-8", errors="replace"), truncated


_SHELL_EXEC_PARAMETERS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "command": {
            "type": "string",
            "description": (
                "The program to run, e.g. 'echo' or 'grep'. A single token, "
                "never a shell line; shell metacharacters are rejected."
            ),
        },
        "args": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "The arguments passed to the program as separate list "
                "elements. Each element is a literal token, not shell syntax. "
                "Path arguments must stay inside the working directory."
            ),
        },
    },
    "required": ["command", "args"],
}


def _looks_like_path(arg: str) -> bool:
    """Return True when an arg looks like a filesystem path to boundary-check.

    A best-effort heuristic: anything containing a path separator or a parent
    reference, or an absolute path, is checked against the working-directory
    boundary. Plain flags and values (``-r``, ``keyword``) are left alone so the
    boundary check does not reject benign non-path arguments.
    """
    if not arg:
        return False
    if arg.startswith("-"):
        return False
    return (
        "/" in arg
        or "\\" in arg
        or arg.startswith("~")
        or Path(arg).is_absolute()
        or ".." in arg.split("/")
    )


def _run_coroutine(coro: Any) -> Any:
    """Drive ``coro`` to completion from a synchronous caller.

    ``ToolRegistry.invoke`` calls handlers synchronously, but the subprocess
    path is async. When no event loop is running in this thread we use
    ``asyncio.run``. When a loop is already running (the tool was invoked from
    inside async code) we run the coroutine on a fresh loop in a worker thread
    so we never re-enter the running loop, which ``asyncio.run`` forbids.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: dict[str, Any] = {}

    def _worker() -> None:
        result["value"] = asyncio.run(coro)

    thread = threading.Thread(target=_worker)
    thread.start()
    thread.join()
    return result["value"]


def make_shell_tool(
    *,
    db: Any,
    working_dir: Path,
    timeout_seconds: int,
    output_cap_bytes: int,
    shell_type: str = "auto",
    confirm: bool = False,
    trace_id: str | None = None,
) -> Tool:
    """Return the ``shell_exec`` Tool that runs commands as a structured arg list.

    The handler never accepts a free-form shell string: ``command`` and ``args``
    are separate. Every code path (clean run, metacharacter reject, boundary
    reject, confirm-pending, timeout) writes exactly one ShellInvocation audit
    row through ``db.record_shell_invocation`` (SHELL-02). ``shell_type`` selects
    the interpreter only when the model asks for one through ``args``; no shell
    is hardcoded (SE-4). The tool is built but NOT registered here; plan 75-02
    registers it behind the double gate (SHELL-01).
    """
    safe_root = working_dir.resolve()

    async def _spawn(command: str, args: list[str]) -> tuple[int | None, str, bool]:
        """Run the command under the timeout and return (exit_code, stdout, truncated)."""
        proc = await asyncio.create_subprocess_exec(
            command,
            *args,
            cwd=str(safe_root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, _stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
        except TimeoutError:
            # asyncio.wait_for raises the builtin TimeoutError on Python 3.11+;
            # asyncio.TimeoutError is an alias for it, so catching the builtin
            # covers both names.
            # Cross-OS terminate-then-kill (SE-4): terminate() asks the process
            # to exit, kill() forces it, wait() reaps it. No process-group kill
            # and no raw signals; those are not portable to Windows.
            proc.terminate()
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            await proc.wait()
            return None, "", False
        text, truncated = truncate_bytes(stdout or b"", output_cap_bytes)
        return proc.returncode, text, truncated

    def handler(command: str, args: list[str] | None = None) -> dict[str, Any]:
        arg_list = list(args or [])
        display = " ".join([command, *arg_list])

        # (1) Metacharacter denylist runs BEFORE any spawn (SE-2). A denied arg
        # writes an audit row and returns a structured error; no subprocess.
        try:
            reject_metacharacters([command, *arg_list])
        except ValueError as exc:
            db.record_shell_invocation(
                command=display,
                exit_code=None,
                stdout_truncated="",
                working_directory=str(working_dir),
                trace_id=trace_id,
            )
            return {"exit_code": None, "stdout": "", "truncated": False, "error": str(exc)}

        # (2) Any path-shaped arg is checked against the working-directory
        # boundary (SE-3). An absolute or escaping path writes an audit row and
        # returns a structured error; no subprocess.
        for arg in arg_list:
            if _looks_like_path(arg):
                try:
                    resolve_within(working_dir, arg)
                except PermissionError as exc:
                    db.record_shell_invocation(
                        command=display,
                        exit_code=None,
                        stdout_truncated="",
                        working_directory=str(working_dir),
                        trace_id=trace_id,
                    )
                    return {
                        "exit_code": None,
                        "stdout": "",
                        "truncated": False,
                        "error": str(exc),
                    }

        # (3) Optional human-confirm mode (SHELL-03): return a pending result
        # without spawning, but still write an audit row. Plan 75-02 documents
        # how a caller resolves a pending confirmation.
        if confirm:
            db.record_shell_invocation(
                command=display,
                exit_code=None,
                stdout_truncated="",
                working_directory=str(working_dir),
                trace_id=trace_id,
            )
            return {
                "exit_code": None,
                "stdout": "",
                "truncated": False,
                "pending_confirmation": True,
            }

        # (4) Run the command via create_subprocess_exec with shell=False
        # semantics, capped output, and a terminate-then-kill timeout.
        exit_code, stdout, truncated = _run_coroutine(_spawn(command, arg_list))

        # (5)/(6) Persist the audit row on the run path too (SHELL-02).
        db.record_shell_invocation(
            command=display,
            exit_code=exit_code,
            stdout_truncated=stdout,
            working_directory=str(working_dir),
            trace_id=trace_id,
        )
        return {"exit_code": exit_code, "stdout": stdout, "truncated": truncated}

    description = (
        "Run a command as a structured argument list inside the configured safe "
        f"working directory ({safe_root}). The command may not use shell "
        "metacharacters and path arguments may not escape the working directory."
    )
    return Tool(
        name="shell_exec",
        description=description,
        parameters=_SHELL_EXEC_PARAMETERS,
        handler=handler,
    )


def register_shell_if_gated(
    registry: ToolRegistry,
    cfg: Config,
    db: Database,
    *,
    profile_allowed_tools: list[str] | None,
) -> bool:
    """Register ``shell_exec`` into ``registry`` only when BOTH gates are open.

    This is the single chokepoint for the SHELL-01 double gate, shared by the
    api.py and run_cmd.py registry builders so the gate logic lives in one place
    (the single-chokepoint discipline used for run_pip in v0.5). The tool is
    registered ONLY when:

      (1) the runtime gate is open: ``HORUS_OS_SHELL_ENABLED`` equals the exact
          string ``"true"`` in the environment (SHELL-01), AND
      (2) the explicit-grant gate is open: ``profile_allowed_tools`` is a list
          that names ``"shell_exec"``.

    If EITHER gate is missing the tool is not registered and an agent can never
    reach it. Critically, when ``profile_allowed_tools`` is None (an unrestricted
    profile that normally reaches every registered tool) the helper still does
    NOT register shell: per SE-1, an unrestricted profile must not silently gain
    shell access, so the explicit-name requirement overrides the usual "None
    means all" semantics for this one high-risk tool. TEST-36 asserts every gate
    state including this unrestricted-profile guard.

    Returns True when the tool was registered, False otherwise. Registering into
    the per-profile registry (after the env+name check) rather than a shared
    master keeps the tool out of any registry an unrestricted profile could
    reach.
    """
    # SE-1 / TEST-36: BOTH gates must be open or shell_exec never registers.
    if os.environ.get(SHELL_ENABLED_ENV) != "true":
        return False
    if profile_allowed_tools is None or "shell_exec" not in profile_allowed_tools:
        return False

    working_dir = cfg.shell_working_dir or (cfg.data_dir / "shell")
    working_dir.mkdir(parents=True, exist_ok=True)
    registry.register(
        make_shell_tool(
            db=db,
            working_dir=working_dir,
            timeout_seconds=cfg.shell_timeout_seconds,
            output_cap_bytes=cfg.shell_output_cap_bytes,
            shell_type=cfg.shell_type,
            confirm=cfg.shell_confirm,
        )
    )
    return True


__all__ = [
    "SHELL_ENABLED_ENV",
    "make_shell_tool",
    "register_shell_if_gated",
    "reject_metacharacters",
    "resolve_within",
    "truncate_bytes",
]
