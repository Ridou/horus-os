"""Tests for VectorIndex over a separate vectors.sqlite (Plan 70-02, Task 1).

No model is ever downloaded and no network call is ever made: a fake embedding
backend produces deterministic vectors so the round-trip, the EM-3 dimension
guard, the reindex rebuild, and the unavailable-extension path are all exercised
without fastembed. The tests also prove the main horus.sqlite schema and
SCHEMA_VERSION are never touched.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from horus_os.memory.vector import (
    VECTOR_INDEX_VERSION,
    EmbeddingDimensionMismatch,
    VectorIndex,
    VectorIndexUnavailable,
)

DIM = 4


class _FakeBackend:
    """Deterministic stand-in for ONNXEmbeddingBackend.

    Each text maps to a fixed unit vector so nearest-neighbour ordering is
    predictable. No fastembed, no network, no model on disk.
    """

    def __init__(self, model_name: str = "fake/model-a", dimension: int = DIM) -> None:
        self.model_name = model_name
        self.dimension = dimension
        self._present = True
        self.embed_calls: list[list[str]] = []

    def is_model_present(self) -> bool:
        return self._present

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.embed_calls.append(list(texts))
        out: list[list[float]] = []
        for text in texts:
            seed = float(abs(hash(text)) % 7 + 1)
            vec = [0.0] * self.dimension
            vec[len(text) % self.dimension] = seed
            out.append(vec)
        return out


def _index_path(tmp_path: Path) -> Path:
    return tmp_path / "vectors.sqlite"


def _open_with_vec(path: Path) -> sqlite3.Connection:
    """Open a verification connection with the sqlite-vec extension loaded.

    The vec0 virtual table is only queryable from a connection that has loaded
    the extension, so test-side assertions on note_vectors open through here.
    """
    import sqlite_vec

    conn = sqlite3.connect(str(path))
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    return conn


def test_fresh_index_creates_file_table_and_config(tmp_path: Path) -> None:
    backend = _FakeBackend()
    idx = VectorIndex(_index_path(tmp_path), backend)
    try:
        assert _index_path(tmp_path).exists()
        conn = sqlite3.connect(str(_index_path(tmp_path)))
        try:
            names = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
                )
            }
            assert "note_vectors" in names
            assert "vector_config" in names
            row = conn.execute(
                "SELECT model_name, dimension, index_version FROM vector_config"
            ).fetchone()
            assert row == (backend.model_name, DIM, VECTOR_INDEX_VERSION)
        finally:
            conn.close()
    finally:
        idx.close()


def test_horus_sqlite_and_schema_version_untouched(tmp_path: Path) -> None:
    """Constructing the index never creates or touches horus.sqlite."""
    backend = _FakeBackend()
    idx = VectorIndex(_index_path(tmp_path), backend)
    try:
        assert not (tmp_path / "horus.sqlite").exists()
    finally:
        idx.close()
    from horus_os import storage

    assert storage.SCHEMA_VERSION == 13


def test_upsert_then_search_round_trips(tmp_path: Path) -> None:
    backend = _FakeBackend()
    idx = VectorIndex(_index_path(tmp_path), backend)
    try:
        idx.upsert("a.md", "alpha")
        query_vec = backend.embed(["alpha"])[0]
        results = idx.search(query_vec, top_k=5)
        assert results
        assert results[0][0] == "a.md"
        assert isinstance(results[0][1], float)
    finally:
        idx.close()


def test_upsert_replaces_not_duplicates(tmp_path: Path) -> None:
    backend = _FakeBackend()
    idx = VectorIndex(_index_path(tmp_path), backend)
    try:
        idx.upsert("a.md", "alpha")
        idx.upsert("a.md", "alpha-rewritten")
        conn = _open_with_vec(_index_path(tmp_path))
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM note_vectors WHERE rel_path = ?", ("a.md",)
            ).fetchone()[0]
            assert count == 1
        finally:
            conn.close()
    finally:
        idx.close()


def test_model_swap_raises_mismatch_and_leaves_rows(tmp_path: Path) -> None:
    """A stored model differing from the configured one blocks embedding (EM-3)."""
    first = _FakeBackend(model_name="fake/model-a")
    idx = VectorIndex(_index_path(tmp_path), first)
    idx.upsert("a.md", "alpha")
    idx.close()

    # Reopen with a DIFFERENT model name.
    second = _FakeBackend(model_name="fake/model-b")
    idx2 = VectorIndex(_index_path(tmp_path), second)
    try:
        assert idx2.mismatch_from == "fake/model-a"
        with pytest.raises(EmbeddingDimensionMismatch) as excinfo:
            idx2.upsert("b.md", "beta")
        assert "horus-os memory reindex" in str(excinfo.value)
        with pytest.raises(EmbeddingDimensionMismatch):
            idx2.search([0.0] * DIM, top_k=3)
        # The existing row is left intact: no silent rebuild.
        conn = _open_with_vec(_index_path(tmp_path))
        try:
            count = conn.execute("SELECT COUNT(*) FROM note_vectors").fetchone()[0]
            assert count == 1
        finally:
            conn.close()
    finally:
        idx2.close()


def test_reindex_rebuilds_and_resolves_mismatch(tmp_path: Path) -> None:
    first = _FakeBackend(model_name="fake/model-a")
    idx = VectorIndex(_index_path(tmp_path), first)
    idx.upsert("a.md", "alpha")
    idx.close()

    second = _FakeBackend(model_name="fake/model-b")
    idx2 = VectorIndex(_index_path(tmp_path), second)
    try:
        # Reindex with the new model clears the mismatch and rewrites config.
        count = idx2.reindex([("a.md", "alpha"), ("b.md", "beta")])
        assert count == 2
        assert idx2.mismatch_from is None
        # Embedding now works against the new model.
        idx2.upsert("c.md", "gamma")
        conn = _open_with_vec(_index_path(tmp_path))
        try:
            stored_model = conn.execute("SELECT model_name FROM vector_config").fetchone()[0]
            assert stored_model == "fake/model-b"
            total = conn.execute("SELECT COUNT(*) FROM note_vectors").fetchone()[0]
            assert total == 3
        finally:
            conn.close()
    finally:
        idx2.close()


def test_is_ready_reflects_model_and_mismatch(tmp_path: Path) -> None:
    backend = _FakeBackend()
    idx = VectorIndex(_index_path(tmp_path), backend)
    try:
        assert idx.is_ready() is True
        backend._present = False
        assert idx.is_ready() is False
    finally:
        idx.close()


def test_missing_enable_load_extension_raises_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A sqlite3 without enable_load_extension surfaces a clear error, not AttributeError."""
    real_connect = sqlite3.connect

    class _NoExtConnection:
        """Wraps a real connection but hides enable_load_extension."""

        def __init__(self, conn: sqlite3.Connection) -> None:
            self._conn = conn

        def __getattr__(self, name: str):
            if name == "enable_load_extension":
                raise AttributeError("enable_load_extension")
            return getattr(self._conn, name)

    def _fake_connect(*args: object, **kwargs: object) -> _NoExtConnection:
        return _NoExtConnection(real_connect(*args, **kwargs))

    monkeypatch.setattr(sqlite3, "connect", _fake_connect)
    backend = _FakeBackend()
    with pytest.raises(VectorIndexUnavailable) as excinfo:
        VectorIndex(_index_path(tmp_path), backend)
    assert "enable_load_extension" in str(excinfo.value)
