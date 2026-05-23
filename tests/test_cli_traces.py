"""Tests for `horus-os traces`."""

from __future__ import annotations

import io
import json
from pathlib import Path

from horus_os.__main__ import main
from horus_os.config import Config
from horus_os.storage import Database
from horus_os.types import AgentResult


def _run(argv: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = main(argv, stdout=stdout, stderr=stderr)
    return code, stdout.getvalue(), stderr.getvalue()


def _seed_db(tmp_path: Path, count: int = 3) -> None:
    config = Config.with_defaults(tmp_path)
    config.save()
    db = Database(config.db_path)
    db.init()
    for i in range(count):
        db.record_trace(
            f"prompt {i}",
            AgentResult(
                text=f"response {i}",
                tool_uses=[],
                provider="anthropic",
                model="claude-sonnet-4-6",
                usage={},
            ),
        )


def test_traces_complains_when_db_missing(tmp_path: Path) -> None:
    code, _out, err = _run(["traces", "--data-dir", str(tmp_path)])
    assert code == 1
    assert "No database" in err
    assert "horus-os init" in err


def test_traces_prints_empty_message_on_empty_db(tmp_path: Path) -> None:
    _seed_db(tmp_path, count=0)
    code, out, err = _run(["traces", "--data-dir", str(tmp_path)])
    assert code == 0
    assert out.strip() == "(no traces yet)"
    assert err == ""


def test_traces_renders_table(tmp_path: Path) -> None:
    _seed_db(tmp_path, count=3)
    code, out, err = _run(["traces", "--data-dir", str(tmp_path)])
    assert code == 0
    assert "created_at" in out
    assert "anthropic" in out
    assert "prompt 0" in out
    assert "prompt 2" in out
    assert err == ""


def test_traces_respects_limit(tmp_path: Path) -> None:
    _seed_db(tmp_path, count=5)
    code, out, _err = _run(["traces", "--data-dir", str(tmp_path), "--limit", "2"])
    assert code == 0
    # 2 data rows plus header and separator
    body_lines = [line for line in out.strip().splitlines() if "anthropic" in line]
    assert len(body_lines) == 2


def test_traces_json_output(tmp_path: Path) -> None:
    _seed_db(tmp_path, count=2)
    code, out, _err = _run(["traces", "--data-dir", str(tmp_path), "--json"])
    assert code == 0
    payload = json.loads(out)
    assert isinstance(payload, list)
    assert len(payload) == 2
    assert "prompt" in payload[0]
    assert payload[0]["provider"] == "anthropic"
