"""Tests for `horus-os usage`.

Tests are organized by task:
  Task 1: skeleton dispatch
  Task 2: JSON formatter + precision + fixture pin
  Task 3: CSV + table formatters
  Task 4: --by model + byte-for-byte route parity
"""

from __future__ import annotations

import io
import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from horus_os.__main__ import build_parser, main
from horus_os.cli.usage_cmd import run_usage
from horus_os.config import Config
from horus_os.storage import Database

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "usage_output_schema.json"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


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


def _seed_canonical_run(db: Database, *, agent: str = "default") -> str:
    """Seed the canonical PRICE-02 row that the fixture pins against.

    One trace plus one llm_call:
      - agent_profile_name: "default"
      - claude-sonnet-4-6 with 1000 input + 200 output + 500 cache_read
      - total_cost_usd: 0.006150 (hand-derived per Phase 34 SUMMARY)

    Returns the trace_id.
    """
    trace_id = uuid.uuid4().hex
    now = _now_iso()
    with sqlite3.connect(str(db.path)) as conn:
        conn.execute(
            "INSERT INTO traces "
            "(trace_id, created_at, provider, model, prompt, response_text, "
            "agent_profile_name, total_input_tokens, total_output_tokens, total_cost_usd) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                trace_id,
                now,
                "anthropic",
                "claude-sonnet-4-6",
                "p",
                "r",
                agent,
                1000,
                200,
                0.006150,
            ),
        )
        conn.execute(
            "INSERT INTO llm_calls "
            "(call_id, trace_id, iteration_idx, created_at, provider, model, "
            "input_tokens, output_tokens, cache_creation_input_tokens, "
            "cache_read_input_tokens, cost_usd, latency_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                uuid.uuid4().hex,
                trace_id,
                0,
                now,
                "anthropic",
                "claude-sonnet-4-6",
                1000,
                200,
                0,
                500,
                0.006150,
                100,
            ),
        )
    return trace_id


def _seed_uncosted_run(db: Database, *, agent: str = "default") -> str:
    """Seed one trace with total_cost_usd NULL for Pitfall 11 contract tests."""
    trace_id = uuid.uuid4().hex
    with sqlite3.connect(str(db.path)) as conn:
        conn.execute(
            "INSERT INTO traces "
            "(trace_id, created_at, provider, model, prompt, response_text, "
            "agent_profile_name, total_input_tokens, total_output_tokens, total_cost_usd) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                trace_id,
                _now_iso(),
                "anthropic",
                "claude-sonnet-4-6",
                "p",
                "r",
                agent,
                None,
                None,
                None,
            ),
        )
    return trace_id


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


def test_usage_dispatch_agent_format_csv_hits_stub_until_task_3(tmp_path: Path) -> None:
    """CSV formatter is a stub until Task 3; agent dispatch still routes to it."""
    _init_db(tmp_path)
    with pytest.raises(NotImplementedError, match="formatter lands in Task 2/3"):
        _call_run_usage(tmp_path, by="agent", fmt="csv")


def test_usage_dispatch_tool_format_table_hits_stub_until_task_3(tmp_path: Path) -> None:
    """Table formatter is a stub until Task 3; tool dispatch still routes to it."""
    _init_db(tmp_path)
    with pytest.raises(NotImplementedError, match="formatter lands in Task 2/3"):
        _call_run_usage(tmp_path, by="tool", fmt="table")


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


# ---------- Task 2: JSON formatter, precision, fixture pin ----------


def test_json_format_canonical_cost_renders_exactly_six_decimals(tmp_path: Path) -> None:
    """USAGE-04: anti-canary for float-precision noise across the JSON output."""
    db = _init_db(tmp_path)
    _seed_canonical_run(db)
    code, out, err = _call_run_usage(tmp_path, by="agent", fmt="json")
    assert code == 0, err
    payload = json.loads(out)
    assert payload["rows"][0]["total_cost_usd"] == 0.006150
    # The raw substring 0.00615 is present (Python strips the trailing
    # zero, both 0.00615 and 0.006150 parse to the same float).
    assert "0.00615" in out
    # Float-precision noise canaries: these substrings must NOT appear.
    assert "0.006149" not in out
    assert "0.006150000000" not in out


def test_json_format_matches_pinned_fixture_schema(tmp_path: Path) -> None:
    """Schema drift fails this test loudly via the pinned JSON fixture."""
    db = _init_db(tmp_path)
    _seed_canonical_run(db)
    code, out, _err = _call_run_usage(tmp_path, by="agent", fmt="json")
    assert code == 0
    fixture = json.loads(FIXTURE_PATH.read_text())
    assert json.loads(out) == fixture


def test_json_format_empty_db_returns_empty_rows_envelope(tmp_path: Path) -> None:
    _init_db(tmp_path)
    code, out, _err = _call_run_usage(tmp_path, by="agent", fmt="json")
    assert code == 0
    assert json.loads(out) == {"by": "agent", "rows": [], "since": "7d"}


def test_json_format_preserves_none_for_uncosted_run(tmp_path: Path) -> None:
    """Pitfall 11 honesty contract survives JSON serialization."""
    db = _init_db(tmp_path)
    _seed_uncosted_run(db)
    code, out, _err = _call_run_usage(tmp_path, by="agent", fmt="json")
    assert code == 0
    payload = json.loads(out)
    # cost_by_agent surfaces None as 0.0 (its existing Phase 35 contract);
    # the uncosted_runs counter is the honesty signal we assert on here.
    row = payload["rows"][0]
    assert row["uncosted_runs"] == 1
    assert row["run_count"] == 1


def test_json_envelope_carries_by_and_since(tmp_path: Path) -> None:
    _init_db(tmp_path)
    code, out, _err = _call_run_usage(tmp_path, by="tool", fmt="json", since="24h")
    assert code == 0
    payload = json.loads(out)
    assert payload["by"] == "tool"
    assert payload["since"] == "24h"


def test_docs_cli_md_documents_horus_os_usage_subcommand() -> None:
    docs = (REPO_ROOT / "docs" / "CLI.md").read_text()
    assert "## horus-os usage" in docs
    assert "### JSON output schema" in docs
    assert "### Precision contract" in docs
    assert "0.006150" in docs
    assert "--since" in docs
    assert "--format" in docs
    assert "--by" in docs
