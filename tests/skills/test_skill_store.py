"""Tests for SkillStore filesystem discovery (Phase 74, SKILL-01, Task 2).

The directory under skills_dir is the source of truth. Discovery is crash-safe
(broken files go to a side channel, never raise) and path-safe (a resolved path
that escapes the root raises PermissionError, mirroring NotesStore).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from horus_os.skills import Skill, SkillStore

VALID_A = """---
name: alpha
description: The alpha skill.
tags: [a, b]
---

# Alpha

Alpha body.
"""

VALID_B = """---
name: beta
description: The beta skill.
---

# Beta

Beta body.
"""

BROKEN = "no frontmatter at all\njust prose\n"


def _write(skills_dir: Path, filename: str, text: str) -> None:
    skills_dir.mkdir(parents=True, exist_ok=True)
    (skills_dir / filename).write_text(text, encoding="utf-8")


def test_list_skills_returns_one_per_valid_file_sorted_by_name(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write(skills_dir, "z-beta.md", VALID_B)
    _write(skills_dir, "a-alpha.md", VALID_A)
    skills = SkillStore(skills_dir).list_skills()
    assert [s.name for s in skills] == ["alpha", "beta"]
    assert all(isinstance(s, Skill) for s in skills)


def test_broken_file_is_skipped_and_recorded_not_raised(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write(skills_dir, "good.md", VALID_A)
    _write(skills_dir, "bad.md", BROKEN)
    store = SkillStore(skills_dir)
    skills = store.list_skills()
    assert [s.name for s in skills] == ["alpha"]
    errors = store.list_skill_errors()
    assert len(errors) == 1
    rel_path, message = errors[0]
    assert rel_path == "bad.md"
    assert "bad.md" in message


def test_get_skill_matches_on_frontmatter_name_not_filename(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    # Filename deliberately differs from the frontmatter name.
    _write(skills_dir, "the-file.md", VALID_A)
    store = SkillStore(skills_dir)
    assert store.get_skill("alpha") is not None
    assert store.get_skill("alpha").name == "alpha"
    # The filename stem is not a valid lookup key.
    assert store.get_skill("the-file") is None
    assert store.get_skill("does-not-exist") is None


def test_list_skill_summaries_omits_body(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write(skills_dir, "a.md", VALID_A)
    summaries = SkillStore(skills_dir).list_skill_summaries()
    assert summaries == [{"name": "alpha", "description": "The alpha skill."}]
    # The body must never leak into the level-1 summary surface.
    for summary in summaries:
        assert set(summary.keys()) == {"name", "description"}
        assert "body" not in summary


def test_empty_dir_yields_empty_list(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    store = SkillStore(skills_dir)
    assert store.list_skills() == []
    assert store.list_skill_errors() == []


def test_absent_dir_yields_empty_list(tmp_path: Path) -> None:
    store = SkillStore(tmp_path / "does_not_exist")
    assert store.list_skills() == []
    assert store.list_skill_errors() == []


def test_resolve_rejects_path_escaping_root(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    store = SkillStore(skills_dir)
    with pytest.raises(PermissionError):
        store._resolve("../escape.md")


@pytest.mark.skipif(sys.platform == "win32", reason="symlink creation needs privilege on Windows")
def test_symlink_escaping_root_is_surfaced_as_error_not_crash(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text(VALID_A, encoding="utf-8")
    link = skills_dir / "linked.md"
    link.symlink_to(outside)
    store = SkillStore(skills_dir)
    # Discovery must not crash; the escaping symlink is recorded as an error.
    errors = store.list_skill_errors()
    assert any("linked.md" in rel_path for rel_path, _ in errors)
