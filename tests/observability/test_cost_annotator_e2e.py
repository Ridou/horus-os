"""Phase 34 Task 4 e2e: CostAnnotator wired BEFORE SQLitePersister in create_app.

The canonical Phase 34 integration test. Proves end to end that:

- Known-model LLM calls land cost_usd populated and pricing_missing=0.
- Unknown-model LLM calls land cost_usd NULL (never 0; Pitfall 5) and
  pricing_missing=1.
- Subscriber order in the live bus is annotator-then-persister; the
  contract is pinned so a future refactor that swaps order fails loudly.
- HORUS_OS_PRICING_PATH env override is honored end to end (PRICE-04).

The Conversation-stubbing fixture pattern mirrors Phase 33's
tests/observability/test_run_end_rollup_integration.py::
test_api_chat_endpoint_e2e_rollup. See that test for the cadence
docstring; this file reuses the same stub shape with model selection
plumbed in.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from horus_os import Database
from horus_os import agent as agent_module
from horus_os.observability import CostAnnotator, SQLitePersister, reset_observation_bus_for_tests
from horus_os.types import AgentResult, ToolUse

LOOP_ITERATIONS = 1  # one LLM call per chat for clean cost arithmetic
INPUT_TOKENS = 1000
OUTPUT_TOKENS = 200
CACHE_READ_TOKENS = 500


class _OneShotStubConversation:
    """One LLMCallEvent per chat with canonical Sonnet token shape.

    Returns text-only on the first send so the agent loop terminates
    immediately. usage carries the four-rate Anthropic shape so the
    CostAnnotator can exercise input + output + cache_read pricing.
    """

    def __init__(self, model: str | None = None, system_prompt: str | None = None) -> None:
        self.model = model or "stub-model"
        self.system_prompt = system_prompt
        self._calls = 0

    def send(self, prompt=None, tool_results=None, tools=None) -> AgentResult:
        del prompt, tool_results, tools
        self._calls += 1
        return AgentResult(
            text="ok",
            tool_uses=[],
            provider="stub",
            model=self.model,
            usage={
                "input_tokens": INPUT_TOKENS,
                "output_tokens": OUTPUT_TOKENS,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": CACHE_READ_TOKENS,
            },
        )


def _no_tool_uses_stub_factory(provider, model, *, system_prompt=None):
    del provider
    return _OneShotStubConversation(model=model, system_prompt=system_prompt)


def _post_chat_one_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    model_override: str | None = None,
) -> tuple[str, Path]:
    """Set up the app + DB, POST /api/chat once, return (trace_id, db_path).

    `model_override` is forwarded as the chat payload's `model` field; when
    None, api.py picks `cfg.anthropic_model = "claude-sonnet-4-6"` (a known
    model in the bundled pricing table).
    """
    from fastapi.testclient import TestClient

    from horus_os import create_app

    db = Database(tmp_path / "horus.sqlite")
    db.init()
    reset_observation_bus_for_tests()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-used")
    monkeypatch.setattr(agent_module, "_new_conversation", _no_tool_uses_stub_factory)

    app = create_app(data_dir=tmp_path)
    payload: dict[str, Any] = {"prompt": "test"}
    if model_override is not None:
        payload["model"] = model_override
    with TestClient(app) as client:
        response = client.post("/api/chat", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    return body["trace_id"], db.path


def test_e2e_known_model_writes_cost_usd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    trace_id, db_path = _post_chat_one_call(tmp_path, monkeypatch)
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT cost_usd, pricing_missing FROM llm_calls WHERE trace_id = ?",
            (trace_id,),
        ).fetchone()
    assert row is not None, "expected one llm_calls row for the chat"
    # 1000*3.00 + 200*15.00 + 500*0.30 + 0*3.75 = 6150 -> /1e6 -> 0.00615
    # -> round(6dp) -> 0.006150
    assert row["cost_usd"] == pytest.approx(0.006150, abs=1e-9)
    assert row["pricing_missing"] == 0


def test_e2e_unknown_model_writes_null_cost(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    trace_id, db_path = _post_chat_one_call(
        tmp_path, monkeypatch, model_override="never-released-3000-pro"
    )
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT cost_usd, pricing_missing FROM llm_calls WHERE trace_id = ?",
            (trace_id,),
        ).fetchone()
    assert row is not None
    # Pitfall 5: literal NULL, never 0 or 0.0.
    assert row["cost_usd"] is None
    assert row["pricing_missing"] == 1
    assert row["cost_usd"] != 0
    assert row["cost_usd"] != 0.0


def test_e2e_subscriber_order_annotator_before_persister(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pin the subscribe-order contract: CostAnnotator handler comes first."""
    from fastapi.testclient import TestClient

    from horus_os import create_app

    db = Database(tmp_path / "horus.sqlite")
    db.init()
    reset_observation_bus_for_tests()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-used")

    app = create_app(data_dir=tmp_path)
    with TestClient(app):
        bus = app.state.observation_bus
        handlers = list(bus._subscribers)
    # Find the bound-method index for each class.
    annotator_idx = next(
        i
        for i, h in enumerate(handlers)
        if getattr(h, "__self__", None) is not None
        and isinstance(h.__self__, CostAnnotator)
    )
    persister_idx = next(
        i
        for i, h in enumerate(handlers)
        if getattr(h, "__self__", None) is not None
        and isinstance(h.__self__, SQLitePersister)
    )
    assert annotator_idx < persister_idx, (
        f"CostAnnotator must subscribe BEFORE SQLitePersister; got "
        f"annotator_idx={annotator_idx}, persister_idx={persister_idx}"
    )


def test_e2e_pricing_override_via_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PRICE-04 wiring proof: HORUS_OS_PRICING_PATH overrides bundled rates."""
    override = tmp_path / "fixture_pricing.json"
    override.write_text(
        json.dumps(
            {
                "version": "1",
                "updated_at": "2026-05-26",
                "release_version": "test",
                "models": {
                    "claude-sonnet-4-6": {
                        "provider": "anthropic",
                        "input_per_million": 99.99,
                        "output_per_million": 0.0,
                        "cache_write_per_million": 0.0,
                        "cache_read_per_million": 0.0,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("HORUS_OS_PRICING_PATH", str(override))
    trace_id, db_path = _post_chat_one_call(tmp_path, monkeypatch)
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT cost_usd, pricing_missing FROM llm_calls WHERE trace_id = ?",
            (trace_id,),
        ).fetchone()
    assert row is not None
    # 1000 input * 99.99 / 1_000_000 = 0.09999 (output + cache priced at 0)
    assert row["cost_usd"] == pytest.approx(0.09999, abs=1e-9)
    assert row["pricing_missing"] == 0
