"""Tests for NotesStore."""

from __future__ import annotations

from pathlib import Path

import pytest

from horus_os import NoteRef, NotesStore


def _seed(tmp_path: Path) -> Path:
    (tmp_path / "alpha.md").write_text("# Alpha title\n\nAlpha body about apples.")
    (tmp_path / "beta.md").write_text("# Beta\n\napples and oranges and apples.")
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "gamma.md").write_text("# Gamma\n\nNothing to see.")
    (tmp_path / "notes.txt").write_text("not markdown, ignored")
    return tmp_path


def test_list_notes_empty_dir_returns_empty(tmp_path: Path) -> None:
    store = NotesStore(tmp_path)
    assert store.list_notes() == []


def test_list_notes_returns_only_markdown_recursive(tmp_path: Path) -> None:
    _seed(tmp_path)
    refs = NotesStore(tmp_path).list_notes()
    paths = [r.path for r in refs]
    assert paths == ["alpha.md", "beta.md", "subdir/gamma.md"]
    for ref in refs:
        assert isinstance(ref, NoteRef)
        assert ref.title
        assert ref.modified_at.endswith("Z")


def test_list_notes_extracts_first_h1_as_title(tmp_path: Path) -> None:
    _seed(tmp_path)
    refs = {r.path: r for r in NotesStore(tmp_path).list_notes()}
    assert refs["alpha.md"].title == "Alpha title"
    assert refs["subdir/gamma.md"].title == "Gamma"


def test_list_notes_falls_back_to_stem_when_no_h1(tmp_path: Path) -> None:
    (tmp_path / "no_heading.md").write_text("no heading here")
    refs = NotesStore(tmp_path).list_notes()
    assert refs[0].title == "no_heading"


def test_read_note_returns_full_content(tmp_path: Path) -> None:
    _seed(tmp_path)
    text = NotesStore(tmp_path).read_note("alpha.md")
    assert "Alpha body" in text


def test_read_note_blocks_path_escape(tmp_path: Path) -> None:
    notes = tmp_path / "notes"
    notes.mkdir()
    outside = tmp_path / "secret.md"
    outside.write_text("nope")
    with pytest.raises(PermissionError):
        NotesStore(notes).read_note("../secret.md")


def test_read_note_blocks_absolute_escape(tmp_path: Path) -> None:
    notes = tmp_path / "notes"
    notes.mkdir()
    outside = tmp_path / "leak.md"
    outside.write_text("leak")
    with pytest.raises(PermissionError):
        NotesStore(notes).read_note(str(outside))


def test_search_empty_query_returns_empty(tmp_path: Path) -> None:
    _seed(tmp_path)
    assert NotesStore(tmp_path).search_notes("") == []


def test_search_matches_content_substring(tmp_path: Path) -> None:
    _seed(tmp_path)
    refs = NotesStore(tmp_path).search_notes("apples")
    paths = [r.path for r in refs]
    assert paths[0] == "beta.md"  # apples appears twice
    assert "alpha.md" in paths
    assert "subdir/gamma.md" not in paths


def test_search_matches_filename(tmp_path: Path) -> None:
    _seed(tmp_path)
    refs = NotesStore(tmp_path).search_notes("alpha")
    assert refs[0].path == "alpha.md"


def test_search_is_case_insensitive(tmp_path: Path) -> None:
    _seed(tmp_path)
    upper = NotesStore(tmp_path).search_notes("APPLES")
    lower = NotesStore(tmp_path).search_notes("apples")
    assert [r.path for r in upper] == [r.path for r in lower]


def test_search_respects_limit(tmp_path: Path) -> None:
    for i in range(5):
        (tmp_path / f"n{i}.md").write_text(f"# n{i}\n\nshared keyword")
    refs = NotesStore(tmp_path).search_notes("keyword", limit=3)
    assert len(refs) == 3


def test_search_missing_dir_returns_empty(tmp_path: Path) -> None:
    store = NotesStore(tmp_path / "does_not_exist")
    assert store.search_notes("anything") == []
    assert store.list_notes() == []


def test_preview_truncates_to_240_chars(tmp_path: Path) -> None:
    (tmp_path / "long.md").write_text("x" * 1000)
    refs = NotesStore(tmp_path).list_notes()
    assert len(refs[0].preview) == 240


def test_string_path_is_accepted(tmp_path: Path) -> None:
    _seed(tmp_path)
    store = NotesStore(str(tmp_path))
    assert len(store.list_notes()) == 3
