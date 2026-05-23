"""Tests for built-in tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from horus_os import read_file_tool


def test_read_file_returns_text(tmp_path: Path) -> None:
    target = tmp_path / "hello.txt"
    target.write_text("hello world")
    tool = read_file_tool()
    assert tool.handler is not None
    assert tool.handler(path=str(target)) == "hello world"


def test_read_file_resolves_relative_to_base_dir(tmp_path: Path) -> None:
    sub = tmp_path / "notes"
    sub.mkdir()
    target = sub / "intro.md"
    target.write_text("# intro")
    tool = read_file_tool(base_dir=sub)
    assert tool.handler is not None
    assert tool.handler(path="intro.md") == "# intro"


def test_read_file_blocks_path_escape(tmp_path: Path) -> None:
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("nope")
    tool = read_file_tool(base_dir=sandbox)
    assert tool.handler is not None
    with pytest.raises(PermissionError, match="outside the configured base_dir"):
        tool.handler(path="../secret.txt")


def test_read_file_blocks_absolute_path_escape(tmp_path: Path) -> None:
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    outside = tmp_path / "leak.txt"
    outside.write_text("leak")
    tool = read_file_tool(base_dir=sandbox)
    assert tool.handler is not None
    with pytest.raises(PermissionError, match="outside the configured base_dir"):
        tool.handler(path=str(outside))


def test_read_file_allows_absolute_path_inside_base_dir(tmp_path: Path) -> None:
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    target = sandbox / "ok.txt"
    target.write_text("ok")
    tool = read_file_tool(base_dir=sandbox)
    assert tool.handler is not None
    assert tool.handler(path=str(target)) == "ok"


def test_read_file_tool_metadata() -> None:
    tool = read_file_tool()
    assert tool.name == "read_file"
    assert "Read the text content" in tool.description
    assert tool.parameters["required"] == ["path"]
    assert "path" in tool.parameters["properties"]


def test_read_file_tool_description_mentions_base_dir(tmp_path: Path) -> None:
    tool = read_file_tool(base_dir=tmp_path)
    assert "may not escape" in tool.description
