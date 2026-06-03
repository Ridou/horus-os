"""Tests for the optional vector_index wiring on NotesStore (Plan 70-02, Task 2).

The vector index is faked: no fastembed, no model, no network. The key
invariants are (1) the audit callback fires BEFORE the vector upsert (EM-4),
(2) an upsert failure leaves the note file and audit row intact, (3) append
re-embeds the FULL current note text, and (4) vector_index=None is unchanged.
"""

from __future__ import annotations

from pathlib import Path

from horus_os.memory.notes import NotesStore
from horus_os.types import NoteWrite


class _RecordingIndex:
    """Records upsert calls; an event list captures audit-vs-upsert ordering."""

    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.upserts: list[tuple[str, str]] = []

    def upsert(self, rel_path: str, text: str) -> None:
        self.events.append("upsert")
        self.upserts.append((rel_path, text))


class _RaisingIndex:
    """An index whose upsert always fails (model missing / mismatch / etc.)."""

    def __init__(self) -> None:
        self.calls = 0

    def upsert(self, rel_path: str, text: str) -> None:
        self.calls += 1
        raise RuntimeError("embedding model not downloaded")


def test_audit_callback_fires_before_upsert(tmp_path: Path) -> None:
    events: list[str] = []

    def _cb(_: NoteWrite) -> None:
        events.append("audit")

    index = _RecordingIndex(events)
    store = NotesStore(tmp_path, on_write=_cb, vector_index=index)
    store.create_note("a.md", "text")

    assert events == ["audit", "upsert"]
    assert index.upserts == [("a.md", "text")]


def test_upsert_failure_leaves_note_and_audit_intact(tmp_path: Path) -> None:
    seen: list[NoteWrite] = []
    index = _RaisingIndex()
    store = NotesStore(tmp_path, on_write=seen.append, vector_index=index)

    write = store.create_note("a.md", "hello")

    # The note file exists, the audit callback fired, the write returned, and
    # the upsert failure did NOT propagate (the index is a cache).
    assert (tmp_path / "a.md").read_text() == "hello"
    assert [w.operation for w in seen] == ["create"]
    assert write.rel_path == "a.md"
    assert index.calls == 1


def test_append_upserts_full_current_text(tmp_path: Path) -> None:
    events: list[str] = []
    index = _RecordingIndex(events)
    store = NotesStore(tmp_path, vector_index=index)

    store.create_note("log.md", "first")
    store.append_note("log.md", "second")

    # The append upsert must carry the FULL note text, not just the fragment.
    assert index.upserts[-1] == ("log.md", "first\nsecond")


def test_vector_index_none_is_unchanged(tmp_path: Path) -> None:
    seen: list[NoteWrite] = []
    store = NotesStore(tmp_path, on_write=seen.append)
    store.create_note("a.md", "alpha")
    store.append_note("a.md", "beta")
    assert [w.operation for w in seen] == ["create", "append"]
    assert (tmp_path / "a.md").read_text() == "alpha\nbeta"
