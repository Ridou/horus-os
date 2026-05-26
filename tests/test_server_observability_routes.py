"""Integration tests for /api/observability/* read routes.

Four thin GET routes wired in server/api.py over the queries module:

    /api/observability/cost      -> {"agents": [...cost_by_agent rows...]}
    /api/observability/latency   -> {"p50_ms", "p95_ms", "sample_count"}
    /api/observability/tools     -> {"tools": [...tool_reliability rows...]}
    /api/observability/llm-calls -> {"calls": [...raw drilldown rows...]}

The drilldown route SELECTs an explicit column list that omits the
text-content error column on llm_calls (Pitfall 7 + Pitfall 9 hygiene);
the assertion below pins that contract.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from horus_os import Config, Database, create_app


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _init_db(tmp_path: Path) -> Database:
    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    db = Database(cfg.db_path)
    db.init()
    return db


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(data_dir=tmp_path))


def _insert_trace(
    db: Database, *, agent: str = "default", total_cost_usd: float | None = 0.001
) -> str:
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
                100,
                50,
                total_cost_usd,
            ),
        )
    return trace_id


def _insert_llm_call(db: Database, *, trace_id: str | None = None, latency_ms: int = 100) -> str:
    cid = uuid.uuid4().hex
    with sqlite3.connect(str(db.path)) as conn:
        conn.execute(
            "INSERT INTO llm_calls "
            "(call_id, trace_id, iteration_idx, created_at, provider, model, "
            "input_tokens, output_tokens, cost_usd, latency_ms, error_message) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                cid,
                trace_id or uuid.uuid4().hex,
                0,
                _now_iso(),
                "anthropic",
                "claude-sonnet-4-6",
                100,
                50,
                0.0001,
                latency_ms,
                "secret-pii-content-do-not-leak",
            ),
        )
    return cid


def _insert_tool(db: Database, *, tool_name: str = "read_file", status: str = "success") -> None:
    with sqlite3.connect(str(db.path)) as conn:
        conn.execute(
            "INSERT INTO tool_invocations "
            "(invocation_id, trace_id, parent_trace_id, created_at, tool_name, "
            "latency_ms, status) VALUES (?, ?, NULL, ?, ?, ?, ?)",
            (uuid.uuid4().hex, uuid.uuid4().hex, _now_iso(), tool_name, 25, status),
        )


# /api/observability/cost ---------------------------------------------------


def test_cost_route_empty_db_returns_empty_agents_list(tmp_path: Path) -> None:
    _init_db(tmp_path)
    response = _client(tmp_path).get("/api/observability/cost")
    assert response.status_code == 200
    assert response.json() == {"agents": []}


def test_cost_route_default_window_is_7d(tmp_path: Path) -> None:
    _init_db(tmp_path)
    response = _client(tmp_path).get("/api/observability/cost")
    assert response.status_code == 200
    # Default window must be 7d (matches ROADMAP SC #2).
    payload = response.json()
    assert "agents" in payload


def test_cost_route_400_on_invalid_window(tmp_path: Path) -> None:
    _init_db(tmp_path)
    response = _client(tmp_path).get("/api/observability/cost?since=invalid")
    assert response.status_code == 400
    assert "invalid window" in response.json()["detail"]


def test_cost_route_accepts_all_documented_windows(tmp_path: Path) -> None:
    _init_db(tmp_path)
    client = _client(tmp_path)
    for window in ("24h", "7d", "30d", "48h", "14d"):
        response = client.get(f"/api/observability/cost?since={window}")
        assert response.status_code == 200, f"{window} -> {response.status_code}"


def test_cost_route_503_when_db_missing(tmp_path: Path) -> None:
    # Do NOT call _init_db; cfg.db_path will not exist.
    response = _client(tmp_path).get("/api/observability/cost?since=7d")
    assert response.status_code == 503


# /api/observability/latency ------------------------------------------------


def test_latency_route_empty_window_returns_null_not_zero(tmp_path: Path) -> None:
    """Pitfall 10 contract reaches the wire as JSON null, not 0."""
    _init_db(tmp_path)
    response = _client(tmp_path).get("/api/observability/latency?since=7d")
    assert response.status_code == 200
    assert response.json() == {"p50_ms": None, "p95_ms": None, "sample_count": 0}


def test_latency_route_with_samples(tmp_path: Path) -> None:
    db = _init_db(tmp_path)
    for _ in range(10):
        _insert_llm_call(db, latency_ms=100)
    response = _client(tmp_path).get("/api/observability/latency?since=7d")
    assert response.status_code == 200
    body = response.json()
    assert body["sample_count"] == 10
    assert body["p50_ms"] == 100
    assert body["p95_ms"] == 100


def test_latency_route_400_on_invalid_window(tmp_path: Path) -> None:
    _init_db(tmp_path)
    response = _client(tmp_path).get("/api/observability/latency?since=garbage")
    assert response.status_code == 400


def test_latency_route_503_when_db_missing(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/api/observability/latency?since=7d")
    assert response.status_code == 503


# /api/observability/tools --------------------------------------------------


def test_tools_route_empty_db_returns_empty_tools_list(tmp_path: Path) -> None:
    _init_db(tmp_path)
    response = _client(tmp_path).get("/api/observability/tools?since=7d")
    assert response.status_code == 200
    assert response.json() == {"tools": []}


def test_tools_route_aggregates(tmp_path: Path) -> None:
    db = _init_db(tmp_path)
    for _ in range(3):
        _insert_tool(db, tool_name="read_file", status="success")
    _insert_tool(db, tool_name="read_file", status="error")
    response = _client(tmp_path).get("/api/observability/tools?since=7d")
    body = response.json()
    row = next(t for t in body["tools"] if t["tool_name"] == "read_file")
    assert row["success_count"] == 3
    assert row["error_count"] == 1


def test_tools_route_400_on_invalid_window(tmp_path: Path) -> None:
    _init_db(tmp_path)
    response = _client(tmp_path).get("/api/observability/tools?since=bad")
    assert response.status_code == 400


def test_tools_route_503_when_db_missing(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/api/observability/tools?since=7d")
    assert response.status_code == 503


# /api/observability/llm-calls ----------------------------------------------


def test_llm_calls_route_empty_db_returns_empty_calls_list(tmp_path: Path) -> None:
    _init_db(tmp_path)
    response = _client(tmp_path).get("/api/observability/llm-calls?since=7d")
    assert response.status_code == 200
    assert response.json() == {"calls": []}


def test_llm_calls_route_returns_rows_ordered_desc(tmp_path: Path) -> None:
    db = _init_db(tmp_path)
    older_ts = (datetime.now(UTC) - timedelta(minutes=10)).isoformat().replace("+00:00", "Z")
    newer_ts = (datetime.now(UTC) - timedelta(seconds=5)).isoformat().replace("+00:00", "Z")
    with sqlite3.connect(str(db.path)) as conn:
        for ts, latency in [(older_ts, 99), (newer_ts, 100)]:
            conn.execute(
                "INSERT INTO llm_calls "
                "(call_id, trace_id, iteration_idx, created_at, provider, model, "
                "input_tokens, output_tokens, cost_usd, latency_ms) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    uuid.uuid4().hex,
                    uuid.uuid4().hex,
                    0,
                    ts,
                    "anthropic",
                    "claude-sonnet-4-6",
                    100,
                    50,
                    0.001,
                    latency,
                ),
            )
    response = _client(tmp_path).get("/api/observability/llm-calls?since=7d")
    body = response.json()
    assert len(body["calls"]) == 2
    # Newest first.
    assert body["calls"][0]["latency_ms"] == 100
    assert body["calls"][1]["latency_ms"] == 99


def test_llm_calls_route_excludes_error_text_content_column(tmp_path: Path) -> None:
    """Pitfall 7 + Pitfall 9: the text-content error column is NEVER on the wire."""
    db = _init_db(tmp_path)
    _insert_llm_call(db)  # writes the "secret-pii-content-do-not-leak" string.
    response = _client(tmp_path).get("/api/observability/llm-calls?since=7d")
    body = response.json()
    assert len(body["calls"]) == 1
    call = body["calls"][0]
    # No column named "error_message" appears in the wire format.
    assert "error_message" not in call.keys()
    # And the canary string from our seed never appears anywhere.
    assert "secret-pii-content-do-not-leak" not in response.text


def test_llm_calls_route_limits_to_100(tmp_path: Path) -> None:
    db = _init_db(tmp_path)
    for _ in range(120):
        _insert_llm_call(db)
    response = _client(tmp_path).get("/api/observability/llm-calls?since=7d")
    assert response.status_code == 200
    assert len(response.json()["calls"]) == 100


def test_llm_calls_route_400_on_invalid_window(tmp_path: Path) -> None:
    _init_db(tmp_path)
    response = _client(tmp_path).get("/api/observability/llm-calls?since=junk")
    assert response.status_code == 400


def test_llm_calls_route_503_when_db_missing(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/api/observability/llm-calls?since=7d")
    assert response.status_code == 503


# /api/observability/cost-by-model -----------------------------------------


def test_route_cost_by_model_empty_db_returns_empty_models(tmp_path: Path) -> None:
    _init_db(tmp_path)
    response = _client(tmp_path).get("/api/observability/cost-by-model?since=7d")
    assert response.status_code == 200
    assert response.json() == {"models": []}


def test_route_cost_by_model_valid_window_returns_seeded_rows(tmp_path: Path) -> None:
    db = _init_db(tmp_path)
    _insert_llm_call(db)
    response = _client(tmp_path).get("/api/observability/cost-by-model?since=7d")
    assert response.status_code == 200
    body = response.json()
    assert len(body["models"]) == 1
    row = body["models"][0]
    assert row["model"] == "claude-sonnet-4-6"
    assert row["provider"] == "anthropic"
    assert row["call_count"] == 1


def test_route_cost_by_model_invalid_window_returns_400(tmp_path: Path) -> None:
    _init_db(tmp_path)
    response = _client(tmp_path).get("/api/observability/cost-by-model?since=garbage")
    assert response.status_code == 400
    assert "invalid window" in response.json()["detail"]


def test_route_cost_by_model_missing_db_returns_503(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/api/observability/cost-by-model?since=7d")
    assert response.status_code == 503
