"""Tests for `horus-os agents` subcommand."""

from __future__ import annotations

import io
from pathlib import Path

from horus_os.__main__ import main
from horus_os.storage import Database


def _run(argv: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = main(argv, stdout=stdout, stderr=stderr)
    return code, stdout.getvalue(), stderr.getvalue()


def _init(tmp_path: Path) -> None:
    code, _out, err = _run(["init", "--data-dir", str(tmp_path)])
    assert code == 0, err


def test_agents_missing_db_returns_1(tmp_path: Path) -> None:
    code, _out, err = _run(["agents", "list", "--data-dir", str(tmp_path)])
    assert code == 1
    assert "horus-os init" in err


def test_agents_list_shows_default_after_init(tmp_path: Path) -> None:
    _init(tmp_path)
    code, out, err = _run(["agents", "list", "--data-dir", str(tmp_path)])
    assert code == 0
    assert err == ""
    assert "name" in out
    assert "model" in out
    assert "default" in out
    assert "(default)" in out  # model placeholder for the seeded default profile


def test_agents_list_bare_behaves_like_list(tmp_path: Path) -> None:
    _init(tmp_path)
    code, out, err = _run(["agents", "--data-dir", str(tmp_path)])
    assert code == 0
    assert err == ""
    assert "name" in out
    assert "default" in out


def test_agents_create_round_trip(tmp_path: Path) -> None:
    _init(tmp_path)
    code, out, err = _run(
        [
            "agents",
            "create",
            "--name",
            "foo",
            "--system-prompt",
            "be terse",
            "--model",
            "claude-sonnet-4-6",
            "--allowed-tools",
            "read_file,list_notes",
            "--data-dir",
            str(tmp_path),
        ]
    )
    assert code == 0, err
    assert "Created" in out and "foo" in out

    code, out, _err = _run(["agents", "list", "--data-dir", str(tmp_path)])
    assert code == 0
    assert "foo" in out
    assert "claude-sonnet-4-6" in out

    code, out, _err = _run(["agents", "show", "foo", "--data-dir", str(tmp_path)])
    assert code == 0
    assert "be terse" in out
    assert "claude-sonnet-4-6" in out
    assert "read_file,list_notes" in out


def test_agents_create_duplicate_returns_1(tmp_path: Path) -> None:
    _init(tmp_path)
    code, _out, err = _run(
        [
            "agents",
            "create",
            "--name",
            "default",
            "--system-prompt",
            "x",
            "--data-dir",
            str(tmp_path),
        ]
    )
    assert code == 1
    assert "already exists" in err


def test_agents_show_unknown_returns_1(tmp_path: Path) -> None:
    _init(tmp_path)
    code, _out, err = _run(["agents", "show", "ghost", "--data-dir", str(tmp_path)])
    assert code == 1
    assert "ghost" in err
    assert "No agent profile" in err


def test_agents_edit_only_updates_supplied_fields(tmp_path: Path) -> None:
    _init(tmp_path)
    _run(
        [
            "agents",
            "create",
            "--name",
            "foo",
            "--system-prompt",
            "P",
            "--data-dir",
            str(tmp_path),
        ]
    )
    code, _out, err = _run(
        [
            "agents",
            "edit",
            "foo",
            "--model",
            "claude-sonnet-4-6",
            "--data-dir",
            str(tmp_path),
        ]
    )
    assert code == 0, err
    code, out, _err = _run(["agents", "show", "foo", "--data-dir", str(tmp_path)])
    assert code == 0
    assert "P" in out  # system_prompt preserved
    assert "claude-sonnet-4-6" in out


def test_agents_edit_unknown_returns_1(tmp_path: Path) -> None:
    _init(tmp_path)
    code, _out, err = _run(
        [
            "agents",
            "edit",
            "ghost",
            "--model",
            "m",
            "--data-dir",
            str(tmp_path),
        ]
    )
    assert code == 1
    assert "ghost" in err


def test_agents_edit_allowed_tools_all_resets_to_unrestricted(tmp_path: Path) -> None:
    _init(tmp_path)
    _run(
        [
            "agents",
            "create",
            "--name",
            "foo",
            "--system-prompt",
            "P",
            "--allowed-tools",
            "read_file",
            "--data-dir",
            str(tmp_path),
        ]
    )
    code, out, _err = _run(["agents", "show", "foo", "--data-dir", str(tmp_path)])
    assert code == 0
    assert "read_file" in out

    code, _out, err = _run(
        [
            "agents",
            "edit",
            "foo",
            "--allowed-tools",
            "all",
            "--data-dir",
            str(tmp_path),
        ]
    )
    assert code == 0, err
    code, out, _err = _run(["agents", "show", "foo", "--data-dir", str(tmp_path)])
    assert code == 0
    assert "(all)" in out


def test_agents_edit_allowed_tools_empty_means_none(tmp_path: Path) -> None:
    _init(tmp_path)
    _run(
        [
            "agents",
            "create",
            "--name",
            "foo",
            "--system-prompt",
            "P",
            "--allowed-tools",
            "read_file",
            "--data-dir",
            str(tmp_path),
        ]
    )
    code, _out, err = _run(
        [
            "agents",
            "edit",
            "foo",
            "--allowed-tools",
            "",
            "--data-dir",
            str(tmp_path),
        ]
    )
    assert code == 0, err
    code, out, _err = _run(["agents", "show", "foo", "--data-dir", str(tmp_path)])
    assert code == 0
    assert "(none)" in out


def test_agents_delete_round_trip(tmp_path: Path) -> None:
    _init(tmp_path)
    _run(
        [
            "agents",
            "create",
            "--name",
            "foo",
            "--system-prompt",
            "P",
            "--data-dir",
            str(tmp_path),
        ]
    )
    code, out, err = _run(["agents", "delete", "foo", "--data-dir", str(tmp_path)])
    assert code == 0, err
    assert "Deleted" in out
    code, out, _err = _run(["agents", "list", "--data-dir", str(tmp_path)])
    assert code == 0
    assert "foo" not in out


def test_agents_delete_unknown_returns_1(tmp_path: Path) -> None:
    _init(tmp_path)
    code, _out, err = _run(["agents", "delete", "ghost", "--data-dir", str(tmp_path)])
    assert code == 1
    assert "ghost" in err


def test_agents_show_default_seeded_profile(tmp_path: Path) -> None:
    _init(tmp_path)
    code, out, err = _run(["agents", "show", "default", "--data-dir", str(tmp_path)])
    assert code == 0, err
    assert "name:" in out
    assert "default" in out
    assert "system_prompt:" in out
    # The bootstrapped default profile has a known system_prompt seeded by Database.init.
    assert "helpful" in out.lower()


def test_agents_create_persists_to_database(tmp_path: Path) -> None:
    _init(tmp_path)
    code, _out, err = _run(
        [
            "agents",
            "create",
            "--name",
            "tester",
            "--system-prompt",
            "Tester profile.",
            "--memory-scope",
            "tester-scope",
            "--data-dir",
            str(tmp_path),
        ]
    )
    assert code == 0, err
    db = Database(tmp_path / "horus.sqlite")
    profile = db.load_profile("tester")
    assert profile is not None
    assert profile.system_prompt == "Tester profile."
    assert profile.memory_scope == "tester-scope"
    assert profile.allowed_tools is None
