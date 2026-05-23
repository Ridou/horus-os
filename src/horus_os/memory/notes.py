"""NotesStore: a thin read-only view over a markdown notes folder.

For v0.1 the search is a case-insensitive substring match across
filename and file content. Future phases can swap the implementation
for FTS5 or a vector store without changing the public surface.

Path safety: every operation resolves the requested path against the
configured notes_dir and refuses any path that escapes it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from horus_os.types import NoteRef

PREVIEW_CHARS = 240


class NotesStore:
    """Read-only view over a directory of markdown files."""

    def __init__(self, notes_dir: str | Path) -> None:
        self.notes_dir = Path(notes_dir)

    def _resolved_root(self) -> Path:
        return self.notes_dir.resolve()

    def _resolve(self, rel_path: str) -> Path:
        root = self._resolved_root()
        candidate = Path(rel_path)
        resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
        if root != resolved and root not in resolved.parents:
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


def _extract_title(text: str, *, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or fallback
    return fallback
