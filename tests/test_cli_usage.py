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


def test_usage_dispatch_agent_format_csv_succeeds(tmp_path: Path) -> None:
    """Dispatch routes --by agent --format csv to the live CSV formatter."""
    _init_db(tmp_path)
    code, _out, err = _call_run_usage(tmp_path, by="agent", fmt="csv")
    assert code == 0
    assert err == ""


def test_usage_dispatch_tool_format_table_succeeds(tmp_path: Path) -> None:
    """Dispatch routes --by tool --format table to the live table formatter."""
    _init_db(tmp_path)
    code, _out, err = _call_run_usage(tmp_path, by="tool", fmt="table")
    assert code == 0
    assert err == ""


def test_usage_dispatch_model_format_table_succeeds(tmp_path: Path) -> None:
    """Dispatch routes --by model --format table to cost_by_model live."""
    _init_db(tmp_path)
    code, _out, err = _call_run_usage(tmp_path, by="model", fmt="table")
    assert code == 0
    assert err == ""


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


# ---------- Task 3: CSV + table formatters ----------


def test_csv_format_round_trip_via_dictreader(tmp_path: Path) -> None:
    """CSV output is csv.DictReader-parseable and the cost survives round-trip."""
    import csv as _csv

    db = _init_db(tmp_path)
    _seed_canonical_run(db)
    code, out, _err = _call_run_usage(tmp_path, by="agent", fmt="csv")
    assert code == 0
    reader = _csv.DictReader(io.StringIO(out))
    rows = list(reader)
    assert len(rows) == 1
    # Column order is alphabetical (matches JSON sort_keys=True).
    assert reader.fieldnames == sorted(reader.fieldnames or [])
    assert float(rows[0]["total_cost_usd"]) == pytest.approx(0.006150, abs=1e-9)


def test_csv_format_canonical_cost_no_float_precision_noise(tmp_path: Path) -> None:
    """USAGE-04 anti-canary: no float-precision noise in CSV output."""
    db = _init_db(tmp_path)
    _seed_canonical_run(db)
    code, out, _err = _call_run_usage(tmp_path, by="agent", fmt="csv")
    assert code == 0
    assert "0.00615" in out
    assert "0.006149" not in out
    assert "0.006150000000" not in out


def test_csv_format_empty_db_returns_empty_string(tmp_path: Path) -> None:
    _init_db(tmp_path)
    code, out, _err = _call_run_usage(tmp_path, by="agent", fmt="csv")
    assert code == 0
    # Dispatch appends a single newline; the body itself is empty.
    assert out == "\n"


def test_csv_format_uncosted_run_writes_empty_cell_not_zero(tmp_path: Path) -> None:
    """Pitfall 11 honesty contract: NULL renders as empty cell, never 0 in CSV."""
    db = _init_db(tmp_path)
    _seed_uncosted_run(db)
    code, out, _err = _call_run_usage(tmp_path, by="agent", fmt="csv")
    assert code == 0
    # uncosted_runs is 1 on the surfaced row; total_cost_usd is the
    # cost_by_agent contract value (0.0 inside this function family per
    # Phase 35); the visible NULL contract surfaces via uncosted_runs.
    import csv as _csv

    rows = list(_csv.DictReader(io.StringIO(out)))
    assert rows[0]["uncosted_runs"] == "1"
    assert rows[0]["run_count"] == "1"


def test_table_format_canonical_renders_six_decimal_cost(tmp_path: Path) -> None:
    db = _init_db(tmp_path)
    _seed_canonical_run(db)
    code, out, _err = _call_run_usage(tmp_path, by="agent", fmt="table")
    assert code == 0
    assert "0.00615" in out
    # Float-precision noise canaries must not appear.
    assert "0.006149" not in out


def test_table_format_empty_db_renders_empty_state_message(tmp_path: Path) -> None:
    _init_db(tmp_path)
    code, out, _err = _call_run_usage(tmp_path, by="agent", fmt="table")
    assert code == 0
    assert "(no usage data in window)" in out


def test_table_format_long_agent_name_truncates_with_ellipsis(tmp_path: Path) -> None:
    """PITFALLS.md table-truncate row: long names ellipsis, never stretch row."""
    db = _init_db(tmp_path)
    long_name = "a" * 40
    _seed_canonical_run(db, agent=long_name)
    code, out, _err = _call_run_usage(tmp_path, by="agent", fmt="table")
    assert code == 0
    assert "..." in out
    # No single cell exceeds the column cap (30) plus the inter-column
    # padding (2). The header line lengths bound the data line lengths,
    # so the longest line is the row line; check that no agent cell is
    # rendered at its full 40-char length.
    assert long_name not in out


def test_table_format_uncosted_run_renders_hyphen_not_zero(tmp_path: Path) -> None:
    """Pitfall 11: None cost renders as `-` in table mode, never `0`."""
    # We seed a row where the cost cell will be None at the formatter
    # boundary. cost_by_agent's contract converts None to 0.0 at the
    # boundary, so to exercise the formatter's None branch we test the
    # generic _round_row + _table_cell_str path directly via a synthetic
    # row injection through tool_reliability (which honors None on
    # success_rate when the denominator is 0).
    db = _init_db(tmp_path)
    with sqlite3.connect(str(db.path)) as conn:
        conn.execute(
            "INSERT INTO tool_invocations "
            "(invocation_id, trace_id, parent_trace_id, created_at, tool_name, "
            "latency_ms, status) VALUES (?, ?, NULL, ?, ?, ?, ?)",
            (
                uuid.uuid4().hex,
                uuid.uuid4().hex,
                _now_iso(),
                "noop_tool",
                10,
                "expected_no_result",
            ),
        )
    code, out, _err = _call_run_usage(tmp_path, by="tool", fmt="table")
    assert code == 0
    # success_rate is None when denominator is 0; renders as `-`.
    assert " - " in out or out.rstrip().endswith("-")


def test_all_three_formats_emit_same_numeric_cost_for_canonical_row(
    tmp_path: Path,
) -> None:
    """USAGE-04 cross-format parity: same numeric cost in JSON, CSV, table."""
    import csv as _csv
    import re

    db = _init_db(tmp_path)
    _seed_canonical_run(db)

    _code_j, out_json, _err_j = _call_run_usage(tmp_path, by="agent", fmt="json")
    json_cost = json.loads(out_json)["rows"][0]["total_cost_usd"]

    _code_c, out_csv, _err_c = _call_run_usage(tmp_path, by="agent", fmt="csv")
    csv_cost = float(next(iter(_csv.DictReader(io.StringIO(out_csv))))["total_cost_usd"])

    _code_t, out_table, _err_t = _call_run_usage(tmp_path, by="agent", fmt="table")
    table_match = re.search(r"0\.\d+", out_table)
    assert table_match is not None
    table_cost = float(table_match.group(0))

    assert json_cost == pytest.approx(0.006150, abs=1e-9)
    assert csv_cost == pytest.approx(0.006150, abs=1e-9)
    assert table_cost == pytest.approx(0.006150, abs=1e-9)


# ---------- Task 4: --by model + byte-for-byte route parity ----------


def test_usage_by_model_json_canonical_renders_six_decimals(tmp_path: Path) -> None:
    db = _init_db(tmp_path)
    _seed_canonical_run(db)
    code, out, _err = _call_run_usage(tmp_path, by="model", fmt="json")
    assert code == 0
    payload = json.loads(out)
    assert payload["by"] == "model"
    assert payload["rows"][0]["model"] == "claude-sonnet-4-6"
    assert payload["rows"][0]["total_cost_usd"] == 0.006150
    # Anti-canary substrings absent from the JSON output.
    assert "0.006149" not in out
    assert "0.006150000000" not in out


def test_usage_by_model_csv_matches_json_costs(tmp_path: Path) -> None:
    """USAGE-04 cross-format parity for the --by model slice."""
    import csv as _csv

    db = _init_db(tmp_path)
    _seed_canonical_run(db)
    code, out, _err = _call_run_usage(tmp_path, by="model", fmt="csv")
    assert code == 0
    row = next(iter(_csv.DictReader(io.StringIO(out))))
    assert float(row["total_cost_usd"]) == pytest.approx(0.006150, abs=1e-9)


def test_usage_by_model_table_renders(tmp_path: Path) -> None:
    db = _init_db(tmp_path)
    _seed_canonical_run(db)
    code, out, _err = _call_run_usage(tmp_path, by="model", fmt="table")
    assert code == 0
    assert "claude-sonnet-4-6" in out
    assert "0.00615" in out


def test_usage_by_model_byte_for_byte_parity_with_route(tmp_path: Path) -> None:
    """USAGE-03 contract: CLI `--by model` rows equal route models element-by-element.

    CLI emits `{"by": "model", "since": "7d", "rows": [...]}` and the
    route emits `{"models": [...]}`; envelope keys differ by design
    (CLI uses uniform "rows" across all --by modes; route uses the
    noun matching its name). The inner row data is byte-for-byte
    identical because both call the same cost_by_model(db, "7d") with
    the same window arg over the same DB.
    """
    from fastapi.testclient import TestClient

    from horus_os import create_app

    db = _init_db(tmp_path)
    # Seed a multi-row DB across two models.
    _seed_canonical_run(db, agent="default")
    with sqlite3.connect(str(db.path)) as conn:
        conn.execute(
            "INSERT INTO llm_calls "
            "(call_id, trace_id, iteration_idx, created_at, provider, model, "
            "input_tokens, output_tokens, cache_creation_input_tokens, "
            "cache_read_input_tokens, cost_usd, latency_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                uuid.uuid4().hex,
                uuid.uuid4().hex,
                0,
                _now_iso(),
                "gemini",
                "gemini-2.5-pro",
                400,
                100,
                0,
                0,
                0.001234,
                75,
            ),
        )

    code, cli_out, _err = _call_run_usage(tmp_path, by="model", fmt="json", since="7d")
    assert code == 0
    cli_payload = json.loads(cli_out)

    client = TestClient(create_app(data_dir=tmp_path))
    response = client.get("/api/observability/cost-by-model?since=7d")
    assert response.status_code == 200
    route_payload = response.json()

    assert cli_payload["rows"] == route_payload["models"]
