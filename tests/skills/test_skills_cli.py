"""Tests for the `horus-os skills` CLI and the doctor skills report (Phase 74).

`skills list` shows name / kind / description; `skills show <name>` prints the
full body. A missing skill returns 1 on stderr. An absent skills folder is a
friendly message, not a crash. `horus-os doctor` reports the skills folder path
and the skill count. `--help` lists the new `skills` command.
"""

from __future__ import annotations

import argparse
import io
from pathlib import Path

from horus_os.__main__ import build_parser, main
from horus_os.cli.doctor_cmd import run_doctor

EXTRA_SKILL = """---
name: translate
description: Translate text between two languages.
tags: [language]
kind: prompt-template
allowed_tools: [read_note]
---

# Translate

TRANSLATE_BODY: render the input in the target language faithfully.
"""


def _run(argv: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = main(argv, stdout=stdout, stderr=stderr)
    return code, stdout.getvalue(), stderr.getvalue()


def _init(tmp_path: Path) -> None:
    code, _, err = _run(["init", "--data-dir", str(tmp_path)])
    assert code == 0, err


def test_skills_list_shows_name_kind_description(tmp_path: Path) -> None:
    _init(tmp_path)
    code, out, err = _run(["skills", "list", "--data-dir", str(tmp_path)])
    assert code == 0
    assert err == ""
    # The init seed ships exactly one example skill named "summarize".
    assert "summarize" in out
    assert "prompt-template" in out


def test_skills_list_default_subcommand_is_list(tmp_path: Path) -> None:
    _init(tmp_path)
    # A bare `skills` (no list/show) defaults to list.
    code, out, _err = _run(["skills", "--data-dir", str(tmp_path)])
    assert code == 0
    assert "summarize" in out


def test_skills_show_prints_full_body(tmp_path: Path) -> None:
    _init(tmp_path)
    (tmp_path / "skills" / "translate.md").write_text(EXTRA_SKILL, encoding="utf-8")
    code, out, err = _run(["skills", "show", "translate", "--data-dir", str(tmp_path)])
    assert code == 0
    assert err == ""
    assert "name:           translate" in out
    assert "kind:           prompt-template" in out
    # allowed_tools sentinel: a real list shows the names.
    assert "read_note" in out
    # The body is printed in full.
    assert "TRANSLATE_BODY" in out


def test_skills_show_missing_skill_returns_1(tmp_path: Path) -> None:
    _init(tmp_path)
    code, _out, err = _run(["skills", "show", "nope", "--data-dir", str(tmp_path)])
    assert code == 1
    assert "nope" in err


def test_skills_list_absent_folder_is_friendly(tmp_path: Path) -> None:
    # No init: the skills folder does not exist. list is still a clean 0.
    code, out, _err = _run(["skills", "list", "--data-dir", str(tmp_path)])
    assert code == 0
    assert "init" in out.lower()


def test_skills_show_absent_folder_returns_1(tmp_path: Path) -> None:
    code, _out, err = _run(["skills", "show", "summarize", "--data-dir", str(tmp_path)])
    assert code == 1
    assert "init" in err.lower()


def test_skills_list_reports_parse_errors(tmp_path: Path) -> None:
    _init(tmp_path)
    # A file with no frontmatter fence fails to parse and is counted.
    (tmp_path / "skills" / "broken.md").write_text("no frontmatter here\n", encoding="utf-8")
    code, out, _err = _run(["skills", "list", "--data-dir", str(tmp_path)])
    assert code == 0
    assert "parse errors" in out


def test_help_lists_skills_command() -> None:
    parser = build_parser()
    help_text = parser.format_help()
    assert "skills" in help_text


def test_doctor_reports_skills_folder_and_count(tmp_path: Path) -> None:
    _init(tmp_path)
    args = argparse.Namespace(supabase=False, data_dir=tmp_path)
    out = io.StringIO()
    err = io.StringIO()
    code = run_doctor(args, stdout=out, stderr=err)
    assert code == 0
    text = out.getvalue()
    assert "skills folder:" in text
    assert str(tmp_path / "skills") in text
    # The init seed gives exactly one skill.
    assert "skills found:  1" in text
    # The default usage block is still present (byte-identical default path).
    assert "horus-os doctor --supabase" in text


def test_doctor_skills_report_counts_parse_errors(tmp_path: Path) -> None:
    _init(tmp_path)
    (tmp_path / "skills" / "broken.md").write_text("no frontmatter\n", encoding="utf-8")
    args = argparse.Namespace(supabase=False, data_dir=tmp_path)
    out = io.StringIO()
    err = io.StringIO()
    run_doctor(args, stdout=out, stderr=err)
    assert "skills with parse errors: 1" in out.getvalue()
