"""Tests for latency_p50_p95 in observability.queries.

latency_p50_p95 is the global p50 / p95 over the window, computed via
SQLite NTILE(100) OVER (ORDER BY latency_ms). All percentile math lives
in SQL; the grep gate proves there is no Python stdlib percentile
helper in queries.py. The empty-window contract returns None (JSON
null), never 0 (Pitfall 10 line 272: rendering 0 for n=0 is the bug).
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from horus_os.storage import Database


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _init(tmp_path: Path) -> Database:
    db = Database(tmp_path / "horus.db")
    db.init()
    return db


def _insert_llm_call(
    db: Database, *, created_at: str, latency_ms: int, trace_id: str | None = None
) -> None:
    with sqlite3.connect(str(db.path)) as conn:
        conn.execute(
            "INSERT INTO llm_calls "
            "(call_id, trace_id, iteration_idx, created_at, provider, model, "
            "input_tokens, output_tokens, cost_usd, latency_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                uuid.uuid4().hex,
                trace_id or uuid.uuid4().hex,
                0,
                created_at,
                "anthropic",
                "claude-sonnet-4-6",
                100,
                50,
                0.001,
                latency_ms,
            ),
        )


def test_latency_p50_p95_empty_window_returns_null_not_zero(tmp_path: Path) -> None:
    """Pitfall 10: empty window -> p50/p95 None, sample_count 0. NEVER 0/0/0."""
    from horus_os.observability.queries import latency_p50_p95

    db = _init(tmp_path)
    result = latency_p50_p95(db, "7d")
    assert result == {"p50_ms": None, "p95_ms": None, "sample_count": 0}


def test_latency_p50_p95_ten_samples_all_at_100ms(tmp_path: Path) -> None:
    """Pitfall 10 boundary test (line 267): p95(N all at 100ms) == 100."""
    from horus_os.observability.queries import latency_p50_p95

    db = _init(tmp_path)
    for _ in range(10):
        _insert_llm_call(db, created_at=_now_iso(), latency_ms=100)
    result = latency_p50_p95(db, "7d")
    assert result == {"p50_ms": 100, "p95_ms": 100, "sample_count": 10}


def test_latency_p50_p95_hundred_samples_one_to_hundred(tmp_path: Path) -> None:
    """N=100 with latency_ms in [1..100]: p50 in [50,51], p95 in [95,96]."""
    from horus_os.observability.queries import latency_p50_p95

    db = _init(tmp_path)
    for latency in range(1, 101):
        _insert_llm_call(db, created_at=_now_iso(), latency_ms=latency)
    result = latency_p50_p95(db, "7d")
    assert result["sample_count"] == 100
    # NTILE bucket boundary inclusive range. SQLite is deterministic but
    # the precise row picked by MAX(CASE WHEN pct <= K THEN latency_ms END)
    # can land either side depending on integer division of n / 100.
    assert result["p50_ms"] in (50, 51), f"p50_ms={result['p50_ms']}"
    assert result["p95_ms"] in (95, 96), f"p95_ms={result['p95_ms']}"


def test_latency_p50_p95_single_sample(tmp_path: Path) -> None:
    """n=1: p50 == p95 == that sample; render layer hides per n>=10 rule."""
    from horus_os.observability.queries import latency_p50_p95

    db = _init(tmp_path)
    _insert_llm_call(db, created_at=_now_iso(), latency_ms=42)
    result = latency_p50_p95(db, "7d")
    assert result == {"p50_ms": 42, "p95_ms": 42, "sample_count": 1}


def test_latency_p50_p95_excludes_rows_outside_window(tmp_path: Path) -> None:
    from horus_os.observability.queries import latency_p50_p95

    db = _init(tmp_path)
    # One in window, one 60 days ago.
    _insert_llm_call(db, created_at=_now_iso(), latency_ms=100)
    far_past = (datetime.now(UTC) - timedelta(days=60)).isoformat().replace("+00:00", "Z")
    _insert_llm_call(db, created_at=far_past, latency_ms=99999)
    result = latency_p50_p95(db, "7d")
    assert result["sample_count"] == 1
    assert result["p50_ms"] == 100
    assert result["p95_ms"] == 100


def test_latency_p50_p95_re_exported_from_observability_package() -> None:
    from horus_os.observability import latency_p50_p95 as via_pkg
    from horus_os.observability.queries import latency_p50_p95 as direct

    assert via_pkg is direct


def test_queries_module_does_not_use_python_percentile_helpers() -> None:
    """Pitfall 10 anti-pattern guard: no statistics.* percentile calls."""
    src = Path(__file__).resolve().parents[2] / "src" / "horus_os" / "observability" / "queries.py"
    text = src.read_text()
    # No imports of statistics helpers.
    assert "from statistics import" not in text
    assert "import statistics" not in text
    # No qualified calls to the percentile family. (Test names are
    # picked so they themselves do not match these substrings.)
    assert "statistics.quan" + "tiles" not in text
    assert "statistics.med" + "ian" not in text
    assert "statistics.me" + "an" not in text
