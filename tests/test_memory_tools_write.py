"""Tests for create_note_tool and append_note_tool."""

from __future__ import annotations

from pathlib import Path

import pytest

from horus_os import NotesStore, Tool, append_note_tool, create_note_tool


def test_create_note_tool_metadata(tmp_path: Path) -> None:
    tool = create_note_tool(NotesStore(tmp_path))
    assert isinstance(tool, Tool)
    assert tool.name == "create_note"
    assert set(tool.parameters["required"]) == {"path", "content"}
    assert tool.handler is not None


def test_create_note_tool_returns_dict(tmp_path: Path) -> None:
    tool = create_note_tool(NotesStore(tmp_path))
    assert tool.handler is not None
    result = tool.handler(path="hello.md", content="hi")
    assert isinstance(result, dict)
    assert result["operation"] == "create"
    assert result["rel_path"] == "hello.md"
    assert result["bytes_before"] == 0
    assert result["bytes_after"] == 2
    assert (tmp_path / "hello.md").read_text() == "hi"


def test_create_note_tool_propagates_file_exists(tmp_path: Path) -> None:
    (tmp_path / "exists.md").write_text("a")
    tool = create_note_tool(NotesStore(tmp_path))
    assert tool.handler is not None
    with pytest.raises(FileExistsError):
        tool.handler(path="exists.md", content="b")


def test_append_note_tool_metadata(tmp_path: Path) -> None:
    tool = append_note_tool(NotesStore(tmp_path))
    assert tool.name == "append_note"
    assert set(tool.parameters["required"]) == {"path", "content"}


def test_append_note_tool_returns_dict(tmp_path: Path) -> None:
    (tmp_path / "log.md").write_text("first\n")
    tool = append_note_tool(NotesStore(tmp_path))
    assert tool.handler is not None
    result = tool.handler(path="log.md", content="second")
    assert result["operation"] == "append"
    assert result["rel_path"] == "log.md"
    assert (tmp_path / "log.md").read_text() == "first\nsecond"


def test_append_note_tool_propagates_file_not_found(tmp_path: Path) -> None:
    tool = append_note_tool(NotesStore(tmp_path))
    assert tool.handler is not None
    with pytest.raises(FileNotFoundError):
        tool.handler(path="ghost.md", content="x")
