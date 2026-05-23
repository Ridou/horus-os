"""NotesStore: read and write access to a markdown notes folder.

For v0.1 the search is a case-insensitive substring match across
filename and file content. Future phases can swap the implementation
for FTS5 or a vector store without changing the public surface.

Writes are append-or-create. There is no overwrite or delete in v0.1.
Every successful write produces a NoteWrite and (when configured)
fires an `on_write` callback for audit-trail persistence.

Path safety: every operation resolves the requested path against the
configured notes_dir and refuses any path that escapes it.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from horus_os.types import NoteRef, NoteWrite

PREVIEW_CHARS = 240


class NotesStore:
    """Read and write view over a directory of markdown files."""

    def __init__(
        self,
        notes_dir: str | Path,
        *,
        on_write: Callable[[NoteWrite], None] | None = None,
    ) -> None:
        self.notes_dir = Path(notes_dir)
        self._on_write = on_write

    def _resolved_root(self) -> Path:
        return self.notes_dir.resolve()

    def _resolve(self, rel_path: str, *, must_be_under_root: bool = True) -> Path:
        root = self._resolved_root()
        candidate = Path(rel_path)
        if candidate.is_absolute():
            resolved = candidate.resolve()
        else:
            resolved = (root / candidate).resolve()
        if must_be_under_root and root != resolved and root not in resolved.parents:
            raise PermissionError(f"Path {rel_path!r} resolves outside the notes directory")
        return resolved

    def _ref_for(self, path: Path) -> NoteRef:
        root = self._resolved_root()
        rel = path.resolve().relative_to(root).as_posix()
        stat = path.stat()
        text = path.read_text(errors="replace")
        title = _extract_title(text, fallback=path.stem)
        preview = text[:PREVIEW_CHARS]
        modified_at = (
            datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat().replace("+00:00", "Z")
        )
        return NoteRef(
            path=rel,
            title=title,
            size_bytes=stat.st_size,
            modified_at=modified_at,
            preview=preview,
        )

    def list_notes(self) -> list[NoteRef]:
        """Return every `.md` file under notes_dir, recursive, sorted by relative path."""
        root = self._resolved_root()
        if not root.exists():
            return []
        files = sorted(root.rglob("*.md"))
        return [self._ref_for(p) for p in files if p.is_file()]

    def read_note(self, rel_path: str) -> str:
        """Return the text content of the note at `rel_path`."""
        return self._resolve(rel_path).read_text(errors="replace")

    def search_notes(self, query: str, *, limit: int = 20) -> list[NoteRef]:
        """Substring search over filename and content. Returns top `limit` by hit count."""
        if not query:
            return []
        root = self._resolved_root()
        if not root.exists():
            return []
        needle = query.lower()
        scored: list[tuple[int, str, NoteRef]] = []
        for path in root.rglob("*.md"):
            if not path.is_file():
                continue
            text = path.read_text(errors="replace")
            haystack = (path.name + "\n" + text).lower()
            score = haystack.count(needle)
            if score == 0:
                continue
            ref = self._ref_for(path)
            scored.append((score, ref.path, ref))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [ref for _, _, ref in scored[:limit]]

    def create_note(self, rel_path: str, content: str) -> NoteWrite:
        """Create a new note. Raises FileExistsError if it already exists."""
        target = self._resolve(rel_path)
        if target.exists():
            raise FileExistsError(f"Note already exists: {rel_path!r}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        write = self._make_write("create", rel_path, 0, len(content.encode("utf-8")), content)
        self._notify(write)
        return write

    def append_note(self, rel_path: str, content: str) -> NoteWrite:
        """Append `content` to an existing note. Raises FileNotFoundError if missing."""
        target = self._resolve(rel_path)
        if not target.exists():
            raise FileNotFoundError(f"Note does not exist: {rel_path!r}")
        existing = target.read_text(errors="replace")
        bytes_before = len(existing.encode("utf-8"))
        prefix = "" if existing.endswith("\n") or not existing else "\n"
        payload = prefix + content
        target.write_text(existing + payload)
        bytes_after = bytes_before + len(payload.encode("utf-8"))
        write = self._make_write("append", rel_path, bytes_before, bytes_after, payload)
        self._notify(write)
        return write

    def _make_write(
        self,
        operation: str,
        rel_path: str,
        bytes_before: int,
        bytes_after: int,
        content: str,
    ) -> NoteWrite:
        return NoteWrite(
            write_id=uuid.uuid4().hex,
            created_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            operation=operation,
            rel_path=rel_path,
            bytes_before=bytes_before,
            bytes_after=bytes_after,
            content=content,
        )

    def _notify(self, write: NoteWrite) -> None:
        if self._on_write is None:
            return
        try:
            self._on_write(write)
        except BaseException:
            pass


def _extract_title(text: str, *, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or fallback
    return fallback
