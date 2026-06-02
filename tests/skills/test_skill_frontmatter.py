"""Tests for skill frontmatter parsing (Phase 74, SKILL-01, Task 1).

parse_skill_markdown splits a leading '---' fence, parses a restricted
key: value mapping, and returns a Skill. Every structural failure raises
SkillParseError carrying the rel_path, never a raw parser exception.
"""

from __future__ import annotations

import pytest

from horus_os.skills import Skill, SkillParseError, parse_skill_markdown

WELL_FORMED = """---
name: deep-research
description: Run a multi-source research pass.
tags: [research, writing]
---

# Deep Research

Do the thing step by step.
"""


def test_parses_name_description_tags_and_body() -> None:
    skill = parse_skill_markdown(WELL_FORMED, rel_path="deep-research.md")
    assert isinstance(skill, Skill)
    assert skill.name == "deep-research"
    assert skill.description == "Run a multi-source research pass."
    assert skill.tags == ["research", "writing"]
    # The body is everything after the closing fence, frontmatter excluded.
    assert "# Deep Research" in skill.body
    assert "Do the thing step by step." in skill.body
    assert "name:" not in skill.body


def test_kind_defaults_to_prompt_template() -> None:
    skill = parse_skill_markdown(WELL_FORMED, rel_path="deep-research.md")
    assert skill.kind == "prompt-template"


def test_kind_code_is_recognized() -> None:
    text = "---\nname: build\nkind: code\n---\nbody"
    assert parse_skill_markdown(text, rel_path="build.md").kind == "code"


def test_kind_code_bearing_alias_is_recognized() -> None:
    text = "---\nname: build\nkind: code-bearing\n---\nbody"
    assert parse_skill_markdown(text, rel_path="build.md").kind == "code"


def test_unknown_kind_falls_back_to_prompt_template() -> None:
    text = "---\nname: build\nkind: something-else\n---\nbody"
    assert parse_skill_markdown(text, rel_path="build.md").kind == "prompt-template"


def test_allowed_tools_inline_list_parses() -> None:
    text = "---\nname: t\nallowed_tools: [read_notes, search_web]\n---\nbody"
    skill = parse_skill_markdown(text, rel_path="t.md")
    assert skill.allowed_tools == ["read_notes", "search_web"]


def test_allowed_tools_comma_string_parses() -> None:
    text = "---\nname: t\nallowed_tools: read_notes, search_web\n---\nbody"
    skill = parse_skill_markdown(text, rel_path="t.md")
    assert skill.allowed_tools == ["read_notes", "search_web"]


def test_allowed_tools_absent_is_none() -> None:
    skill = parse_skill_markdown(WELL_FORMED, rel_path="deep-research.md")
    assert skill.allowed_tools is None


def test_no_frontmatter_raises_with_rel_path() -> None:
    text = "# Just a heading\n\nno frontmatter here"
    with pytest.raises(SkillParseError) as excinfo:
        parse_skill_markdown(text, rel_path="loose.md")
    assert excinfo.value.rel_path == "loose.md"
    assert "loose.md" in str(excinfo.value)


def test_unterminated_frontmatter_raises() -> None:
    text = "---\nname: t\ndescription: oops no closing fence\nbody continues"
    with pytest.raises(SkillParseError) as excinfo:
        parse_skill_markdown(text, rel_path="broken.md")
    assert excinfo.value.rel_path == "broken.md"


def test_non_mapping_frontmatter_raises() -> None:
    # A bare list item (no "key: value") is not a simple mapping.
    text = "---\n- just a list item\n---\nbody"
    with pytest.raises(SkillParseError):
        parse_skill_markdown(text, rel_path="list.md")


def test_missing_name_raises_naming_the_file() -> None:
    text = "---\ndescription: has no name\n---\nbody"
    with pytest.raises(SkillParseError) as excinfo:
        parse_skill_markdown(text, rel_path="anon.md")
    assert "anon.md" in str(excinfo.value)
    assert excinfo.value.rel_path == "anon.md"


def test_skill_parse_error_is_value_error() -> None:
    assert issubclass(SkillParseError, ValueError)
