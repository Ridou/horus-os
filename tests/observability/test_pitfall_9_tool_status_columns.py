"""Phase 33 Task 7: Pitfall 9 substrate — tool_invocations column shape.

Three contracts pinned here:

1. On tool failure, the persisted tool_invocations row has status='error',
   error_type=ExceptionClass.__name__, and error_message=ExceptionClass.__name__.
   The exception MESSAGE body is never persisted because it may contain
   user-supplied paths or content (T-33-01 mitigation).

2. On tool success, status='success' with error_type / error_message both
   NULL.

3. retry_count is NULL for SDK-driven tools because the Anthropic SDK
   does not surface per-call retry counts without monkey-patching the
   transport layer. Documented in tools/loop.py:_execute_one.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from horus_os import AgentResult, Database
from horus_os.observability import (
    SQLitePersister,
    get_observation_bus,
    reset_observation_bus_for_tests,
)
from horus_os.tools.loop import execute_tool_uses
from horus_os.tools.registry import ToolRegistry
from horus_os.types import Tool, ToolUse


def _wire(tmp_path: Path) -> tuple[Database, str]:
    db = Database(tmp_path / "horus.sqlite")
    db.init()
    reset_observation_bus_for_tests()
    get_observation_bus().subscribe(SQLitePersister(db).on_event)
    trace_id = db.record_trace(
        "seed",
        AgentResult(text="seed", provider="anthropic", model="claude-sonnet-4-6"),
    )
    return db, trace_id


def test_tool_failure_records_class_name_only(tmp_path: Path) -> None:
    """Failure path persists exception CLASS NAME only (T-33-01).

    The literal user-supplied path must not appear in any column of
    the persisted tool_invocations row.
    """
    db, trace_id = _wire(tmp_path)
    user_secret = "/Users/santino/secret/path/credentials.json leaked"

    def _leaky(**_kwargs):
        raise ValueError(user_secret)

    registry = ToolRegistry()
    registry.register(
        Tool(
            name="leakytool",
            description="A tool whose exception message leaks user content.",
            parameters={"type": "object", "properties": {}},
            handler=_leaky,
        )
    )
    execute_tool_uses(
        registry,
        AgentResult(
            text="",
            tool_uses=[ToolUse(id="x", name="leakytool", input={})],
            provider="anthropic",
            model="claude-sonnet-4-6",
        ),
        trace_id=trace_id,
    )

    with sqlite3.connect(str(db.path)) as conn:
        row = conn.execute(
            "SELECT * FROM tool_invocations WHERE trace_id = ?",
            (trace_id,),
        ).fetchone()
        # PRAGMA table_info returns (cid, name, type, notnull, dflt_value, pk)
        column_names = [r[1] for r in conn.execute("PRAGMA table_info(tool_invocations)")]
    assert row is not None
    by_name = dict(zip(column_names, row, strict=True))
    assert by_name["status"] == "error"
    assert by_name["error_type"] == "ValueError"
    assert by_name["error_message"] == "ValueError"
    # T-33-01: the leaked user-supplied path must not appear in any column.
    full_row_text = " ".join(str(v) for v in by_name.values() if v is not None)
    assert "/Users/santino/secret/path" not in full_row_text
    assert "credentials.json" not in full_row_text


def test_tool_success_records_status_success_with_null_error(tmp_path: Path) -> None:
    """Success path: status='success', error_type IS NULL, error_message IS NULL."""
    db, trace_id = _wire(tmp_path)
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="noop",
            description="No-op tool.",
            parameters={"type": "object", "properties": {}},
            handler=lambda: "ok",
        )
    )
    execute_tool_uses(
        registry,
        AgentResult(
            text="",
            tool_uses=[ToolUse(id="x", name="noop", input={})],
            provider="anthropic",
            model="claude-sonnet-4-6",
        ),
        trace_id=trace_id,
    )
    with sqlite3.connect(str(db.path)) as conn:
        row = conn.execute(
            "SELECT status, error_type, error_message, retry_count "
            "FROM tool_invocations WHERE trace_id = ?",
            (trace_id,),
        ).fetchone()
    assert row is not None
    assert row[0] == "success"
    assert row[1] is None
    assert row[2] is None
    # retry_count is NULL by design (see test below).
    assert row[3] is None


def test_retry_count_is_null_for_sdk_driven_tools(tmp_path: Path) -> None:
    """Phase 33 leaves retry_count NULL per the SDK-limitation note.

    The Anthropic SDK does not surface per-call retry counts without
    monkey-patching the transport layer (PITFALLS.md Pitfall 9). Phase
    38's OTel adapter can fill this from spans if a user wires it;
    Phase 33's runner publishes None.
    """
    db, trace_id = _wire(tmp_path)
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="noop",
            description="No-op tool.",
            parameters={"type": "object", "properties": {}},
            handler=lambda: "ok",
        )
    )
    execute_tool_uses(
        registry,
        AgentResult(
            text="",
            tool_uses=[ToolUse(id="x", name="noop", input={})],
            provider="anthropic",
            model="claude-sonnet-4-6",
        ),
        trace_id=trace_id,
    )
    with sqlite3.connect(str(db.path)) as conn:
        row = conn.execute(
            "SELECT retry_count FROM tool_invocations WHERE tool_name = 'noop'"
        ).fetchone()
    assert row is not None
    assert row[0] is None
