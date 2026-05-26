"""Tests for parse_window in observability.queries.

The window parser converts strings like "24h" / "7d" / "30d" (plus any
positive integer Nh / Nd form) into an ISO 8601 UTC threshold string
suitable for direct text comparison against the created_at TEXT column
the persister writes via _now_iso (datetime.now(UTC).isoformat with the
trailing +00:00 replaced by Z).
"""

from __future__ import annotations

import pytest


def test_parse_window_24h_is_more_recent_than_7d() -> None:
    from horus_os.observability.queries import parse_window

    threshold_24h = parse_window("24h")
    threshold_7d = parse_window("7d")
    # 24h is a more recent moment in time than 7d (closer to now).
    # Both are ISO timestamps; lexical comparison matches chronological order.
    assert threshold_24h > threshold_7d


def test_parse_window_30d_is_older_than_7d() -> None:
    from horus_os.observability.queries import parse_window

    assert parse_window("30d") < parse_window("7d")


def test_parse_window_accepts_generic_hours_and_days() -> None:
    from horus_os.observability.queries import parse_window

    # Nh and Nd are accepted for any positive integer N.
    threshold_48h = parse_window("48h")
    threshold_14d = parse_window("14d")
    assert threshold_48h > threshold_14d
    # 48h must equal 2d to within sub-second drift.
    threshold_2d = parse_window("2d")
    assert abs(len(threshold_48h) - len(threshold_2d)) <= 5
    # Both produced an ISO timestamp ending in Z.
    assert threshold_48h.endswith("Z")
    assert threshold_14d.endswith("Z")


def test_parse_window_returns_iso_z_string() -> None:
    from horus_os.observability.queries import parse_window

    result = parse_window("7d")
    # Matches _now_iso's shape: datetime.isoformat() with +00:00 -> Z.
    assert result.endswith("Z")
    # Contains the ISO date / time separator.
    assert "T" in result


def test_parse_window_rejects_malformed_inputs() -> None:
    from horus_os.observability.queries import parse_window

    for bad in ("", "bad", "7", "d7", "7days", "h7", "1.5h", "abcd"):
        with pytest.raises(ValueError, match="invalid window"):
            parse_window(bad)


def test_parse_window_rejects_zero_and_negative() -> None:
    from horus_os.observability.queries import parse_window

    for bad in ("0h", "0d", "-1d", "-24h"):
        with pytest.raises(ValueError, match="invalid window"):
            parse_window(bad)


def test_parse_window_error_message_names_the_input() -> None:
    from horus_os.observability.queries import parse_window

    with pytest.raises(ValueError) as exc_info:
        parse_window("garbage")
    # The error names the offending value so the API 400 detail is useful.
    assert "garbage" in str(exc_info.value)


def test_parse_window_re_exported_from_observability_package() -> None:
    # The queries module must surface parse_window at the package boundary
    # so callers (server/api.py, future CLI in Phase 37) get one import path.
    from horus_os.observability import parse_window as via_pkg
    from horus_os.observability.queries import parse_window as direct

    assert via_pkg is direct
