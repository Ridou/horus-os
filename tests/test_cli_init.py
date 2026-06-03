"""Tests for `horus-os init`."""

from __future__ import annotations

import io
from pathlib import Path

from horus_os.__main__ import main
from horus_os.config import CONFIG_FILENAME


def _run(argv: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = main(argv, stdout=stdout, stderr=stderr)
    return code, stdout.getvalue(), stderr.getvalue()


def test_init_creates_data_dir_db_notes_and_config(tmp_path: Path) -> None:
    code, out, err = _run(["init", "--data-dir", str(tmp_path)])
    assert code == 0
    assert err == ""
    assert (tmp_path / "horus.sqlite").exists()
    assert (tmp_path / "notes").is_dir()
    assert (tmp_path / CONFIG_FILENAME).exists()
    assert "Initialized horus-os" in out
    assert "horus-os traces" in out


def test_init_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    _run(["init", "--data-dir", str(tmp_path)])
    code, out, err = _run(["init", "--data-dir", str(tmp_path)])
    assert code == 1
    assert "already initialized" in err
    assert out == ""


def test_init_overwrites_with_force(tmp_path: Path) -> None:
    _run(["init", "--data-dir", str(tmp_path)])
    code, out, err = _run(["init", "--data-dir", str(tmp_path), "--force"])
    assert code == 0
    assert "Reinitialized" in out
    assert err == ""


def test_init_db_schema_is_v2(tmp_path: Path) -> None:
    _run(["init", "--data-dir", str(tmp_path)])
    import sqlite3

    with sqlite3.connect(str(tmp_path / "horus.sqlite")) as conn:
        tables = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {"traces", "note_writes", "schema_version"} <= tables


def test_init_seeds_starter_team_and_notes(tmp_path: Path) -> None:
    code, out, err = _run(["init", "--data-dir", str(tmp_path)])
    assert code == 0
    assert err == ""
    # The starter team is named in the init summary.
    assert "Coordinator" in out
    assert "notes seeded in the vault" in out
    # Example notes landed in the vault.
    notes_dir = tmp_path / "notes"
    assert (notes_dir / "welcome-to-horus-os.md").exists()
    # Each starter agent has a persona file with the placeholder substituted.
    soul = notes_dir / "agents" / "Coordinator" / "SOUL.md"
    assert soul.exists()
    assert "{{USER_NAME}}" not in soul.read_text(encoding="utf-8")


def test_force_reinit_does_not_reseed(tmp_path: Path) -> None:
    _run(["init", "--data-dir", str(tmp_path)])
    code, out, err = _run(["init", "--data-dir", str(tmp_path), "--force"])
    assert code == 0, err
    # Reinit must not advertise a fresh seed.
    assert "notes seeded in the vault" not in out
