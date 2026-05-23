"""Tests for memory Tool factories."""

from __future__ import annotations

from pathlib import Path

from horus_os import (
    NotesStore,
    Tool,
    list_notes_tool,
    read_note_tool,
    search_notes_tool,
)


def _seed(tmp_path: Path) -> NotesStore:
    (tmp_path / "alpha.md").write_text("# Alpha\n\napples")
    (tmp_path / "beta.md").write_text("# Beta\n\noranges")
    return NotesStore(tmp_path)


def test_search_notes_tool_returns_dicts(tmp_path: Path) -> None:
    store = _seed(tmp_path)
    tool = search_notes_tool(store)
    assert isinstance(tool, Tool)
    assert tool.name == "search_notes"
    assert tool.handler is not None
    result = tool.handler(query="apples")
    assert isinstance(result, list)
    assert result[0]["path"] == "alpha.md"
    assert set(result[0].keys()) >= {"path", "title", "size_bytes", "modified_at", "preview"}


def test_search_notes_tool_respects_limit(tmp_path: Path) -> None:
    for i in range(5):
        (tmp_path / f"n{i}.md").write_text("shared keyword")
    tool = search_notes_tool(NotesStore(tmp_path))
    assert tool.handler is not None
    result = tool.handler(query="keyword", limit=2)
    assert len(result) == 2


def test_search_notes_tool_schema_requires_query(tmp_path: Path) -> None:
    tool = search_notes_tool(_seed(tmp_path))
    assert tool.parameters["required"] == ["query"]
    assert "query" in tool.parameters["properties"]
    assert "limit" in tool.parameters["properties"]


def test_read_note_tool_returns_text(tmp_path: Path) -> None:
    tool = read_note_tool(_seed(tmp_path))
    assert tool.name == "read_note"
    assert tool.handler is not None
    text = tool.handler(path="alpha.md")
    assert "apples" in text


def test_read_note_tool_schema_requires_path(tmp_path: Path) -> None:
    tool = read_note_tool(_seed(tmp_path))
    assert tool.parameters["required"] == ["path"]


def test_list_notes_tool_returns_all(tmp_path: Path) -> None:
    tool = list_notes_tool(_seed(tmp_path))
    assert tool.name == "list_notes"
    assert tool.handler is not None
    result = tool.handler()
    paths = sorted(r["path"] for r in result)
    assert paths == ["alpha.md", "beta.md"]


def test_list_notes_tool_schema_has_no_required(tmp_path: Path) -> None:
    tool = list_notes_tool(_seed(tmp_path))
    assert tool.parameters["required"] == []
