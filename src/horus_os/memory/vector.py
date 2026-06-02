"""VectorIndex: a rebuildable on-device vector cache over a separate file.

The index lives in its OWN `vectors.sqlite` file managed by sqlite-vec, NOT in
the authoritative `horus.sqlite`. This is Option B from the architecture
research: the vector index is a cache of the notes folder, not authoritative
storage, so it can be deleted and rebuilt with `horus-os memory reindex`
without touching the `note_writes` audit trail and WITHOUT bumping the main
schema version (the authoritative schema stays at 11).

Hard guarantees:
- This module imports cleanly WITHOUT the `[local-memory]` extra: the
  `sqlite_vec` import is deferred to construction time and guarded, so a bare
  install stays importable (Pitfall EM-2).
- A swapped embedding model is detected via the stored `(model_name,
  dimension)` in `vector_config`. While a mismatch is pending, `upsert` and
  `search` refuse to run and raise `EmbeddingDimensionMismatch` naming
  `horus-os memory reindex`. The index is never silently rebuilt (Pitfall
  EM-3); only an explicit `reindex` rewrites the config and re-embeds.
- The internal index schema version lives in `VECTOR_INDEX_VERSION` and is
  stored in `vector_config`, kept independent of the main schema version so
  future index migrations stay isolated (Option B).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from horus_os.memory.embeddings import EmbeddingBackend

# Internal schema version for the vector cache. Stored in vector_config so a
# future index-format change can be detected and rebuilt WITHOUT touching the
# main schema migration chain (Option B isolation).
VECTOR_INDEX_VERSION = 1

# The single config row key. The cache holds exactly one configuration row.
_CONFIG_KEY = "index"

# Install hint shared with the embedding backend so the surfaced command is
# identical everywhere.
_INSTALL_HINT = "pip install 'horus-os[local-memory]'"


class EmbeddingDimensionMismatch(RuntimeError):
    """Raised when the stored embedding model differs from the configured one.

    The vector table is sized to one model's dimension; a different model would
    produce vectors of a different shape (or a different geometry at the same
    size). Rather than silently rebuilding (which can take minutes), the index
    refuses to embed or search until the user runs `horus-os memory reindex`
    (Pitfall EM-3). The message always names that command.
    """


class VectorIndexUnavailable(RuntimeError):
    """Raised when sqlite-vec cannot be loaded into this Python's sqlite3.

    Either the `sqlite_vec` package is missing (the `[local-memory]` extra was
    not installed) or the bundled `sqlite3` was compiled without
    `enable_load_extension` (some pyenv builds disable it). The message names
    the cause and the install hint instead of leaking a bare AttributeError or
    ImportError (Pitfall EM-2).
    """


class VectorIndex:
    """A vec0-backed vector cache over a standalone `vectors.sqlite` file.

    Construction opens an own connection, applies the project pragma policy
    (WAL + synchronous=NORMAL), loads sqlite-vec, and ensures both the
    `vector_config` table and the `note_vectors` virtual table exist sized to
    `backend.dimension`. If a stored config row names a different model than the
    backend, a mismatch flag is set and stays set until `reindex` clears it.
    """

    def __init__(self, db_path: Path | str, backend: EmbeddingBackend) -> None:
        self.db_path = Path(db_path)
        self._backend = backend
        self._mismatch_from: str | None = None
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._load_extension()
        self._apply_pragmas()
        self._ensure_config_table()
        self._ensure_vector_table()
        self._reconcile_config()

    # -- construction helpers -------------------------------------------------

    def _load_extension(self) -> None:
        """Load the sqlite-vec extension, guarded with a clear failure path.

        The `sqlite_vec` import is deferred here (never at module top) so a bare
        install can import this module. A missing extra or a sqlite3 without
        `enable_load_extension` both surface as `VectorIndexUnavailable`
        naming the cause and the install hint (Pitfall EM-2).
        """
        try:
            import sqlite_vec
        except ImportError as exc:
            raise VectorIndexUnavailable(
                "the local-memory extra is not installed; run: " + _INSTALL_HINT
            ) from exc
        enable = getattr(self._conn, "enable_load_extension", None)
        if enable is None:
            raise VectorIndexUnavailable(
                "this Python's sqlite3 was built without enable_load_extension, so "
                "the sqlite-vec extension cannot be loaded; install a Python whose "
                "sqlite3 supports loadable extensions to use vector memory."
            )
        try:
            enable(True)
            sqlite_vec.load(self._conn)
            enable(False)
        except (AttributeError, sqlite3.OperationalError) as exc:
            raise VectorIndexUnavailable(
                "could not load the sqlite-vec extension into this Python's sqlite3; "
                "ensure the local-memory extra is installed: " + _INSTALL_HINT
            ) from exc

    def _apply_pragmas(self) -> None:
        """Match the project pragma policy: WAL + synchronous=NORMAL."""
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")

    def _ensure_config_table(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vector_config (
                key            TEXT NOT NULL PRIMARY KEY,
                model_name     TEXT NOT NULL,
                dimension      INTEGER NOT NULL,
                index_version  INTEGER NOT NULL,
                updated_at     TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def _ensure_vector_table(self) -> None:
        """Create the vec0 table sized to the backend dimension if absent."""
        self._conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS note_vectors "
            f"USING vec0(rel_path TEXT PRIMARY KEY, embedding FLOAT[{self._backend.dimension}])"
        )
        self._conn.commit()

    def _reconcile_config(self) -> None:
        """Compare the stored config row against the configured backend.

        If a row exists and names a different model, raise the mismatch flag
        (EM-3): upsert/search will refuse until reindex. The existing rows are
        left intact for a clean, explicit rebuild. When no row exists, write the
        current model/dimension/index-version.
        """
        row = self._conn.execute(
            "SELECT model_name, dimension FROM vector_config WHERE key = ?",
            (_CONFIG_KEY,),
        ).fetchone()
        if row is None:
            self._write_config_row()
            return
        stored_model = row[0]
        if stored_model != self._backend.model_name:
            self._mismatch_from = stored_model

    def _write_config_row(self) -> None:
        self._conn.execute(
            """
            INSERT OR REPLACE INTO vector_config
                (key, model_name, dimension, index_version, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                _CONFIG_KEY,
                self._backend.model_name,
                self._backend.dimension,
                VECTOR_INDEX_VERSION,
                _now_iso(),
            ),
        )
        self._conn.commit()

    def _guard_ready(self) -> None:
        """Raise EmbeddingDimensionMismatch while a model swap is pending."""
        if self._mismatch_from is not None:
            raise EmbeddingDimensionMismatch(
                f"embedding model changed from {self._mismatch_from!r} to "
                f"{self._backend.model_name!r}; run: horus-os memory reindex"
            )

    # -- public surface -------------------------------------------------------

    def upsert(self, rel_path: str, text: str) -> None:
        """Embed `text` and INSERT OR REPLACE its vector keyed by `rel_path`.

        This is the call NotesStore makes AFTER its audit write. A pending model
        swap raises `EmbeddingDimensionMismatch` (EM-3); a missing model raises
        the backend's `EmbeddingModelMissingError`. NotesStore swallows both so
        the audit row is never affected by a cache failure.
        """
        self._guard_ready()
        vector = self._backend.embed([text])[0]
        self._insert_vector(rel_path, vector)
        self._conn.commit()

    def search(self, query_vec: list[float], top_k: int = 20) -> list[tuple[str, float]]:
        """Return the `top_k` nearest `(rel_path, distance)` rows for a vector.

        Takes an already-embedded query vector (the caller embeds the query
        once and may reuse it). A pending model swap raises
        `EmbeddingDimensionMismatch` (EM-3).
        """
        self._guard_ready()
        from sqlite_vec import serialize_float32

        rows = self._conn.execute(
            "SELECT rel_path, distance FROM note_vectors "
            "WHERE embedding MATCH ? ORDER BY distance LIMIT ?",
            (serialize_float32(query_vec), top_k),
        ).fetchall()
        return [(str(rel_path), float(distance)) for rel_path, distance in rows]

    def reindex(self, pairs: Iterable[tuple[str, str]]) -> int:
        """Drop and rebuild the index from `(rel_path, text)` pairs.

        Recreates `note_vectors` at the CURRENT backend dimension, rewrites the
        `vector_config` row, clears any pending mismatch flag, and re-embeds
        every supplied pair. Returns the number of pairs indexed. This is the
        ONLY method that resolves an EM-3 mismatch, and it is invoked solely by
        `horus-os memory reindex` (rebuilding the cache reads existing files; it
        creates no notes and fires no audit row).
        """
        from sqlite_vec import serialize_float32

        self._conn.execute("DROP TABLE IF EXISTS note_vectors")
        self._ensure_vector_table()
        self._write_config_row()
        self._mismatch_from = None
        count = 0
        for rel_path, text in pairs:
            vector = self._backend.embed([text])[0]
            self._conn.execute(
                "INSERT INTO note_vectors(rel_path, embedding) VALUES (?, ?)",
                (rel_path, serialize_float32(vector)),
            )
            count += 1
        self._conn.commit()
        return count

    def _insert_vector(self, rel_path: str, vector: list[float]) -> None:
        """Replace-insert a vector keyed by rel_path.

        sqlite-vec's vec0 virtual table does not honour `INSERT OR REPLACE` on
        its TEXT primary key as an upsert, so a prior row is deleted explicitly
        before the insert. This keeps `upsert` idempotent (one row per rel_path)
        without relying on virtual-table conflict resolution.
        """
        from sqlite_vec import serialize_float32

        self._conn.execute("DELETE FROM note_vectors WHERE rel_path = ?", (rel_path,))
        self._conn.execute(
            "INSERT INTO note_vectors(rel_path, embedding) VALUES (?, ?)",
            (rel_path, serialize_float32(vector)),
        )

    @property
    def backend(self) -> EmbeddingBackend:
        """The embedding backend, so callers can embed a query once and reuse it.

        NotesStore.search_notes embeds the query through this backend and then
        passes the vector to `search`, keeping a single embed per query.
        """
        return self._backend

    def is_ready(self) -> bool:
        """True when the model is present on disk and no mismatch is pending."""
        return self._mismatch_from is None and self._backend.is_model_present()

    @property
    def mismatch_from(self) -> str | None:
        """The stored model name when a swap is pending, else None."""
        return self._mismatch_from

    def close(self) -> None:
        """Close the underlying connection."""
        self._conn.close()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
