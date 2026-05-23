"""Tests for NotesStore write paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from horus_os import NotesStore, NoteWrite


def test_create_note_writes_and_returns_record(tmp_path: Path) -> None:
    store = NotesStore(tmp_path)
    write = store.create_note("hello.md", "# hello\n\nworld")
    assert isinstance(write, NoteWrite)
    assert write.operation == "create"
    assert write.rel_path == "hello.md"
    assert write.bytes_before == 0
    assert write.bytes_after == len(b"# hello\n\nworld")
    assert (tmp_path / "hello.md").read_text() == "# hello\n\nworld"
    assert write.created_at.endswith("Z")


def test_create_note_auto_creates_parent_dirs(tmp_path: Path) -> None:
    store = NotesStore(tmp_path)
    store.create_note("sub/deeper/note.md", "x")
    assert (tmp_path / "sub" / "deeper" / "note.md").exists()


def test_create_note_raises_on_existing_path(tmp_path: Path) -> None:
    (tmp_path / "exists.md").write_text("a")
    store = NotesStore(tmp_path)
    with pytest.raises(FileExistsError):
        store.create_note("exists.md", "b")


def test_create_note_blocks_path_escape(tmp_path: Path) -> None:
    notes = tmp_path / "notes"
    notes.mkdir()
    with pytest.raises(PermissionError):
        NotesStore(notes).create_note("../leak.md", "x")


def test_append_note_adds_content(tmp_path: Path) -> None:
    (tmp_path / "log.md").write_text("first line\n")
    store = NotesStore(tmp_path)
    write = store.append_note("log.md", "second line")
    assert write.operation == "append"
    assert write.bytes_before == len(b"first line\n")
    assert (tmp_path / "log.md").read_text() == "first line\nsecond line"


def test_append_note_inserts_newline_when_missing(tmp_path: Path) -> None:
    (tmp_path / "log.md").write_text("no trailing newline")
    NotesStore(tmp_path).append_note("log.md", "extra")
    assert (tmp_path / "log.md").read_text() == "no trailing newline\nextra"


def test_append_note_does_not_double_newline(tmp_path: Path) -> None:
    (tmp_path / "log.md").write_text("ends with newline\n")
    NotesStore(tmp_path).append_note("log.md", "extra")
    assert (tmp_path / "log.md").read_text() == "ends with newline\nextra"


def test_append_note_raises_on_missing_file(tmp_path: Path) -> None:
    store = NotesStore(tmp_path)
    with pytest.raises(FileNotFoundError):
        store.append_note("nope.md", "x")


def test_append_note_blocks_path_escape(tmp_path: Path) -> None:
    notes = tmp_path / "notes"
    notes.mkdir()
    outside = tmp_path / "leak.md"
    outside.write_text("a")
    with pytest.raises(PermissionError):
        NotesStore(notes).append_note("../leak.md", "x")


def test_on_write_callback_fires(tmp_path: Path) -> None:
    seen: list[NoteWrite] = []
    store = NotesStore(tmp_path, on_write=seen.append)
    store.create_note("a.md", "alpha")
    store.append_note("a.md", "more")
    assert [w.operation for w in seen] == ["create", "append"]
    assert seen[0].rel_path == "a.md"
    assert seen[1].rel_path == "a.md"


def test_on_write_exception_is_swallowed(tmp_path: Path) -> None:
    def blow_up(_: NoteWrite) -> None:
        raise RuntimeError("logger broke")

    store = NotesStore(tmp_path, on_write=blow_up)
    write = store.create_note("ok.md", "content")
    assert write.rel_path == "ok.md"
    assert (tmp_path / "ok.md").read_text() == "content"


def test_create_then_append_round_trip(tmp_path: Path) -> None:
    store = NotesStore(tmp_path)
    store.create_note("notes/journal.md", "# entry\n")
    store.append_note("notes/journal.md", "more thoughts")
    text = (tmp_path / "notes" / "journal.md").read_text()
    assert text == "# entry\nmore thoughts"
