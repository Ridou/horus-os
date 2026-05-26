"""Tests for `horus-os usage`.

Tests are organized by task:
  Task 1: skeleton dispatch (this section)
  Task 2: JSON formatter + precision + fixture pin
  Task 3: CSV + table formatters
  Task 4: --by model + byte-for-byte route parity
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from horus_os.__main__ import build_parser, main
from horus_os.cli.usage_cmd import run_usage
from horus_os.config import Config
from horus_os.storage import Database


def _run(argv: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = main(argv, stdout=stdout, stderr=stderr)
    return code, stdout.getvalue(), stderr.getvalue()


def _init_db(tmp_path: Path) -> Database:
    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    db = Database(cfg.db_path)
    db.init()
    return db


def _call_run_usage(
    tmp_path: Path,
    *,
    by: str = "agent",
    fmt: str = "json",
    since: str = "7d",
) -> tuple[int, str, str]:
    """Invoke run_usage directly with the parsed namespace, capturing buffers."""
    parser = build_parser()
    args = parser.parse_args(
        ["usage", "--data-dir", str(tmp_path), "--by", by, "--format", fmt, "--since", since]
    )
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = run_usage(args, stdout=stdout, stderr=stderr)
    return code, stdout.getvalue(), stderr.getvalue()


# ---------- Task 1: skeleton dispatch ----------


def test_usage_missing_db_writes_to_stderr_and_returns_1(tmp_path: Path) -> None:
    code, out, err = _run(["usage", "--data-dir", str(tmp_path)])
    assert code == 1
    assert "No database at" in err
    assert "horus-os init" in err
    assert out == ""


def test_usage_invalid_since_writes_invalid_window_to_stderr(tmp_path: Path) -> None:
    _init_db(tmp_path)
    code, out, err = _run(["usage", "--data-dir", str(tmp_path), "--since", "garbage"])
    assert code == 1
    assert "invalid window:" in err
    assert out == ""


def test_usage_dispatch_agent_hits_format_stub(tmp_path: Path) -> None:
    _init_db(tmp_path)
    with pytest.raises(NotImplementedError, match="formatter lands in Task 2/3"):
        _call_run_usage(tmp_path, by="agent", fmt="json")


def test_usage_dispatch_tool_hits_format_stub(tmp_path: Path) -> None:
    _init_db(tmp_path)
    with pytest.raises(NotImplementedError, match="formatter lands in Task 2/3"):
        _call_run_usage(tmp_path, by="tool", fmt="csv")


def test_usage_dispatch_model_hits_query_stub(tmp_path: Path) -> None:
    _init_db(tmp_path)
    with pytest.raises(NotImplementedError, match="--by model lands in Task 4"):
        _call_run_usage(tmp_path, by="model", fmt="table")


def test_usage_subparser_registered_with_choices() -> None:
    parser = build_parser()
    args = parser.parse_args(["usage", "--since", "24h", "--format", "csv", "--by", "tool"])
    assert args.since == "24h"
    assert args.format == "csv"
    assert args.by == "tool"
    assert args.func is run_usage


def test_run_usage_re_exported_from_cli_package() -> None:
    import horus_os.cli as cli_pkg
    from horus_os.cli import run_usage as via_pkg

    assert via_pkg is run_usage
    assert "run_usage" in cli_pkg.__all__
