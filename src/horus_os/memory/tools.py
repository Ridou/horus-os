"""Tool factories that bind to a NotesStore.

Each factory returns a `Tool` whose handler closes over the given
store. The handler's return value is the JSON-serializable payload the
model receives back when the tool result is sent.
"""

from __future__ import annotations

from dataclasses import asdict

from horus_os.memory.notes import NotesStore
from horus_os.types import Tool


def _ref_dict(ref) -> dict:
    return asdict(ref)


def search_notes_tool(store: NotesStore) -> Tool:
    """Tool: search notes by case-insensitive substring."""

    def handler(query: str, limit: int = 20) -> list[dict]:
        return [_ref_dict(r) for r in store.search_notes(query, limit=limit)]

    return Tool(
        name="search_notes",
        description=(
            "Search the user's markdown notes by case-insensitive substring. "
            "Returns a list of matching notes ordered by relevance with title, "
            "path, modified timestamp, and a short preview."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The substring to search for. Case-insensitive.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of notes to return. Defaults to 20.",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 200,
                },
            },
            "required": ["query"],
        },
        handler=handler,
    )


def read_note_tool(store: NotesStore) -> Tool:
    """Tool: read a single note by relative path."""

    def handler(path: str) -> str:
        return store.read_note(path)

    return Tool(
        name="read_note",
        description=(
            "Read the full text content of a single note by its relative path "
            "(as returned by search_notes or list_notes)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path of the note inside the notes directory.",
                },
            },
            "required": ["path"],
        },
        handler=handler,
    )


def list_notes_tool(store: NotesStore) -> Tool:
    """Tool: list every note in the store."""

    def handler() -> list[dict]:
        return [_ref_dict(r) for r in store.list_notes()]

    return Tool(
        name="list_notes",
        description="List every note in the user's notes directory with title, path, modified timestamp, and preview.",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=handler,
    )
