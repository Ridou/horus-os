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
from typing import TYPE_CHECKING

from horus_os.types import NoteRef, NoteWrite

if TYPE_CHECKING:
    from horus_os.memory.vector import VectorIndex

PREVIEW_CHARS = 240

# Reciprocal Rank Fusion constant (FEATURES.md Feature 2). The standard default
# of 60 dampens the contribution of any single high rank so a note that ranks
# well in BOTH the keyword and vector lists beats a note that tops only one.
# RRF is rank-based, so BM25 integer scores and cosine float distances need no
# normalization before merging.
RRF_K = 60


def _reciprocal_rank_fusion(
    keyword_paths: list[str],
    vector_paths: list[str],
    *,
    k: int = RRF_K,
) -> list[str]:
    """Merge two ranked rel_path lists by Reciprocal Rank Fusion.

    Each path scores `sum(1 / (k + rank))` over its 1-based rank in every list
    it appears in (a path absent from a list contributes nothing from that
    list). Scores are summed per path and the deduped rel_paths are returned
    sorted by descending fused score. Ties break on first appearance so the
    order is deterministic across runs (FEATURES.md "deduped by note ID").
    """
    scores: dict[str, float] = {}
    first_seen: dict[str, int] = {}
    order = 0
    for ranked in (keyword_paths, vector_paths):
        for rank, rel_path in enumerate(ranked, start=1):
            scores[rel_path] = scores.get(rel_path, 0.0) + 1.0 / (k + rank)
            if rel_path not in first_seen:
                first_seen[rel_path] = order
                order += 1
    return sorted(scores, key=lambda p: (-scores[p], first_seen[p]))


class NotesStore:
    """Read and write view over a directory of markdown files."""

    def __init__(
        self,
        notes_dir: str | Path,
        *,
        on_write: Callable[[NoteWrite], None] | None = None,
        vector_index: VectorIndex | None = None,
    ) -> None:
        self.notes_dir = Path(notes_dir)
        self._on_write = on_write
        # Optional, non-authoritative vector cache. When present, a successful
        # note write fires an upsert AFTER the audit callback so the reviewable
        # note_writes row always exists, even if the embedding fails (EM-4).
        self._vector_index = vector_index

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
        """Hybrid keyword + vector search merged by Reciprocal Rank Fusion.

        The keyword path is the v0.1 case-insensitive substring ranking over
        filename and content. When a usable VectorIndex is attached, its KNN
        rel_paths are RRF-merged with the keyword ranking (k=60), so a note that
        only paraphrases the query (no literal substring) can still surface, and
        a note that ranks in both lists beats one that ranks in only one. When
        the index is absent, not ready, or raises, the result is byte-identical
        to the keyword-only path (graceful fallback, FEATURES.md table stakes).
        """
        if not query:
            return []
        root = self._resolved_root()
        if not root.exists():
            return []
        keyword_paths = self._keyword_ranked_paths(query)
        vector_paths = self._vector_ranked_paths(query, top_k=limit)
        if not vector_paths:
            ranked = keyword_paths
        else:
            ranked = _reciprocal_rank_fusion(keyword_paths, vector_paths)
        refs: list[NoteRef] = []
        for rel_path in ranked[:limit]:
            try:
                refs.append(self._ref_for(self._resolve(rel_path)))
            except (OSError, ValueError):
                # A vector hit may name a note that was deleted after indexing
                # (the cache is non-authoritative). Skip it rather than crash.
                continue
        return refs

    def _keyword_ranked_paths(self, query: str) -> list[str]:
        """Return rel_paths matching `query` ordered by today's substring score."""
        root = self._resolved_root()
        needle = query.lower()
        scored: list[tuple[int, str]] = []
        for path in root.rglob("*.md"):
            if not path.is_file():
                continue
            text = path.read_text(errors="replace")
            haystack = (path.name + "\n" + text).lower()
            score = haystack.count(needle)
            if score == 0:
                continue
            rel = path.resolve().relative_to(root).as_posix()
            scored.append((score, rel))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [rel for _, rel in scored]

    def _vector_ranked_paths(self, query: str, *, top_k: int) -> list[str]:
        """Return KNN rel_paths from the vector index, or [] when unusable.

        Any index failure (no index attached, model absent, dimension mismatch,
        sqlite-vec unavailable) degrades silently to keyword-only: the search
        never crashes on a broken cache (EM-3/EM-4, threat T-70-09).
        """
        index = self._vector_index
        if index is None or not index.is_ready():
            return []
        # Local import to avoid importing the vector module (and its optional
        # deps) at module load on a bare install.
        from horus_os.memory.embeddings import EmbeddingModelMissingError
        from horus_os.memory.vector import (
            EmbeddingDimensionMismatch,
            VectorIndexUnavailable,
        )

        try:
            query_vec = index.backend.embed([query])[0]
            hits = index.search(query_vec, top_k=top_k)
        except (
            EmbeddingDimensionMismatch,
            EmbeddingModelMissingError,
            VectorIndexUnavailable,
        ):
            return []
        return [rel_path for rel_path, _distance in hits]

    def create_note(self, rel_path: str, content: str) -> NoteWrite:
        """Create a new note. Raises FileExistsError if it already exists."""
        target = self._resolve(rel_path)
        if target.exists():
            raise FileExistsError(f"Note already exists: {rel_path!r}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        write = self._make_write("create", rel_path, 0, len(content.encode("utf-8")), content)
        self._notify(write)
        self._index_after_write(rel_path)
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
        self._index_after_write(rel_path)
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

    def _index_after_write(self, rel_path: str) -> None:
        """Upsert the full current note text into the vector cache (EM-4).

        Runs strictly AFTER `_notify` so a failed embedding never precedes or
        blocks the authoritative `note_writes` audit row. The vector index is a
        non-authoritative cache, so a failure (missing model, dimension
        mismatch, sqlite-vec unavailable) is swallowed the same way the audit
        callback's failures are: the note file and audit row stay intact and the
        write returns normally. The FULL current note text is read back so an
        append re-embeds the whole note, not just the appended fragment.
        """
        if self._vector_index is None:
            return
        try:
            text = self.read_note(rel_path)
            self._vector_index.upsert(rel_path, text)
        except BaseException:
            pass


def _extract_title(text: str, *, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or fallback
    return fallback
