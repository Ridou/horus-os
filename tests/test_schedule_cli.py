"""Tests for the `horus-os schedule` subcommand (REMOTE-05 / D-07).

Schedules are managed entirely from the CLI this milestone (no dashboard UI,
D-07). These tests drive the create/list/edit/delete/enable/disable handler
through the top-level argparse dispatcher and assert against the schedules
table via db.get_schedule, plus the cron desugar/validate contract (D-01).
"""

from __future__ import annotations

import io
from pathlib import Path

from horus_os.__main__ import main
from horus_os.config import Config
from horus_os.storage import Database


def _run(argv: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = main(argv, stdout=stdout, stderr=stderr)
    return code, stdout.getvalue(), stderr.getvalue()


def _init(tmp_path: Path) -> None:
    code, _out, err = _run(["init", "--data-dir", str(tmp_path)])
    assert code == 0, err


def _db(tmp_path: Path) -> Database:
    return Database(Config.load(tmp_path).db_path)


def test_schedule_create_list_delete_round_trip(tmp_path: Path) -> None:
    _init(tmp_path)

    # A missing-db invocation reports the init hint and returns 1.
    fresh = tmp_path / "empty"
    code, _out, err = _run(["schedule", "list", "--data-dir", str(fresh)])
    assert code == 1
    assert "horus-os init" in err

    code, out, err = _run(
        [
            "schedule",
            "create",
            "nightly",
            "--cron",
            "@daily",
            "--profile",
            "Coordinator",
            "--prompt",
            "summarize the day",
            "--data-dir",
            str(tmp_path),
        ]
    )
    assert code == 0, err
    row = _db(tmp_path).get_schedule("nightly")
    assert row is not None
    assert row.cron_expression == "@daily"
    assert row.agent_profile_name == "Coordinator"
    assert row.next_run_at is not None  # initial next_run_at computed on create

    code, out, err = _run(["schedule", "list", "--data-dir", str(tmp_path)])
    assert code == 0, err
    assert "nightly" in out
    assert "@daily" in out

    # An invalid cron string is rejected before any row is written.
    code, _out, err = _run(
        [
            "schedule",
            "create",
            "bad",
            "--cron",
            "not a cron",
            "--profile",
            "Coordinator",
            "--prompt",
            "nope",
            "--data-dir",
            str(tmp_path),
        ]
    )
    assert code != 0
    assert err != ""
    assert _db(tmp_path).get_schedule("bad") is None

    # `every 30m` sugar is desugared to canonical cron before storing (D-01).
    code, _out, err = _run(
        [
            "schedule",
            "create",
            "halfhour",
            "--cron",
            "every 30m",
            "--profile",
            "Coordinator",
            "--prompt",
            "tick",
            "--data-dir",
            str(tmp_path),
        ]
    )
    assert code == 0, err
    assert _db(tmp_path).get_schedule("halfhour").cron_expression == "*/30 * * * *"

    code, _out, err = _run(["schedule", "delete", "nightly", "--data-dir", str(tmp_path)])
    assert code == 0, err
    assert _db(tmp_path).get_schedule("nightly") is None


def test_schedule_enable_disable(tmp_path: Path) -> None:
    _init(tmp_path)
    _run(
        [
            "schedule",
            "create",
            "watcher",
            "--cron",
            "*/5 * * * *",
            "--profile",
            "Coordinator",
            "--prompt",
            "watch",
            "--data-dir",
            str(tmp_path),
        ]
    )

    code, _out, err = _run(["schedule", "disable", "watcher", "--data-dir", str(tmp_path)])
    assert code == 0, err
    assert _db(tmp_path).get_schedule("watcher").enabled == 0

    code, _out, err = _run(["schedule", "enable", "watcher", "--data-dir", str(tmp_path)])
    assert code == 0, err
    assert _db(tmp_path).get_schedule("watcher").enabled == 1
