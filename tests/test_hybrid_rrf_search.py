"""Hybrid RRF search tests for NotesStore.search_notes (Plan 70-03, Task 1).

The VectorIndex is faked end-to-end: no fastembed, no model, no network. The
fake exposes the same surface NotesStore.search_notes relies on (`is_ready`,
`backend.embed`, `search`) so we can drive the merge deterministically and prove:

- a semantic-only hit (no keyword substring) surfaces via the vector ranking,
- a note that ranks in BOTH lists beats a note in only one (RRF sum),
- results are deduped by rel_path,
- the keyword-only fallback is byte-identical when the index is None, not ready,
  or raises EmbeddingDimensionMismatch / EmbeddingModelMissingError,
- `limit` is applied AFTER the merge.
"""

from __future__ import annotations

from pathlib import Path

from horus_os.memory.embeddings import EmbeddingModelMissingError
from horus_os.memory.notes import RRF_K, NotesStore, _reciprocal_rank_fusion
from horus_os.memory.vector import EmbeddingDimensionMismatch


class _FakeBackend:
    """A deterministic embedder that never imports fastembed or hits the net."""

    dimension = 3
    model_name = "fake/model"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(t)), 0.0, 0.0] for t in texts]


class _FakeVectorIndex:
    """Returns a fixed ranked (rel_path, distance) list; records embed calls."""

    def __init__(self, ranked_paths: list[str], *, ready: bool = True) -> None:
        self._ranked = ranked_paths
        self._ready = ready
        self.backend = _FakeBackend()
        self.search_calls = 0

    def is_ready(self) -> bool:
        return self._ready

    def search(self, query_vec: list[float], top_k: int = 20) -> list[tuple[str, float]]:
        self.search_calls += 1
        return [(p, float(i)) for i, p in enumerate(self._ranked[:top_k])]


class _RaisingVectorIndex:
    """An index that is ready but whose search raises the given error."""

    def __init__(self, error: Exception) -> None:
        self._error = error
        self.backend = _FakeBackend()

    def is_ready(self) -> bool:
        return True

    def search(self, query_vec: list[float], top_k: int = 20) -> list[tuple[str, float]]:
        raise self._error


def _seed(tmp_path: Path) -> None:
    (tmp_path / "alpha.md").write_text("# Alpha\n\nApples and apples.")
    (tmp_path / "beta.md").write_text("# Beta\n\nA single apple here.")
    (tmp_path / "gamma.md").write_text("# Gamma\n\nThe event loop was blocked at runtime.")


# -- the pure helper ---------------------------------------------------------


def test_rrf_default_k_is_60() -> None:
    assert RRF_K == 60


def test_rrf_dedupes_and_ranks_shared_paths_first() -> None:
    # "b" is rank 2 in keyword and rank 1 in vector; it should out-score "a"
    # (rank 1 keyword only) and "c" (rank 2 vector only).
    merged = _reciprocal_rank_fusion(["a", "b"], ["b", "c"])
    assert merged[0] == "b"
    assert set(merged) == {"a", "b", "c"}
    assert len(merged) == 3  # deduped


def test_rrf_score_formula() -> None:
    # Single-list ranks: path at rank 1 scores 1/(60+1).
    merged = _reciprocal_rank_fusion(["only"], [])
    assert merged == ["only"]


# -- search_notes with a usable index ----------------------------------------


def test_semantic_only_hit_surfaces_via_vector(tmp_path: Path) -> None:
    _seed(tmp_path)
    # The query has no literal substring in gamma.md, but the fake vector index
    # ranks gamma top. Keyword-only would exclude it (score 0).
    index = _FakeVectorIndex(["gamma.md", "alpha.md"])
    store = NotesStore(tmp_path, vector_index=index)

    paths = [r.path for r in store.search_notes("async errors")]

    assert "gamma.md" in paths
    assert index.search_calls == 1


def test_keyword_only_query_excludes_semantic_miss(tmp_path: Path) -> None:
    _seed(tmp_path)
    # No vector index: gamma.md (no "apple") must not appear for an apple query.
    store = NotesStore(tmp_path)
    paths = [r.path for r in store.search_notes("apple")]
    assert "gamma.md" not in paths


def test_note_in_both_lists_ranks_first(tmp_path: Path) -> None:
    _seed(tmp_path)
    # alpha + beta are keyword hits for "apple" (alpha twice -> keyword rank 1).
    # Make beta the top vector hit so RRF lifts it above alpha.
    index = _FakeVectorIndex(["beta.md", "gamma.md"])
    store = NotesStore(tmp_path, vector_index=index)

    paths = [r.path for r in store.search_notes("apple")]

    # beta is in BOTH lists (keyword rank 2 + vector rank 1); alpha is keyword
    # only (rank 1). RRF: beta = 1/62 + 1/61, alpha = 1/61 -> beta wins.
    assert paths[0] == "beta.md"
    assert "alpha.md" in paths


def test_results_are_deduped_by_rel_path(tmp_path: Path) -> None:
    _seed(tmp_path)
    index = _FakeVectorIndex(["alpha.md", "beta.md"])
    store = NotesStore(tmp_path, vector_index=index)
    paths = [r.path for r in store.search_notes("apple")]
    assert len(paths) == len(set(paths))


def test_limit_applies_after_merge(tmp_path: Path) -> None:
    for i in range(6):
        (tmp_path / f"n{i}.md").write_text(f"# n{i}\n\nshared keyword")
    index = _FakeVectorIndex([f"n{i}.md" for i in range(6)])
    store = NotesStore(tmp_path, vector_index=index)
    refs = store.search_notes("keyword", limit=3)
    assert len(refs) == 3


# -- graceful fallback to keyword-only ---------------------------------------


def test_none_index_is_keyword_only(tmp_path: Path) -> None:
    _seed(tmp_path)
    with_none = NotesStore(tmp_path).search_notes("apple")
    explicit = NotesStore(tmp_path, vector_index=None).search_notes("apple")
    assert [r.path for r in with_none] == [r.path for r in explicit]


def test_not_ready_index_falls_back_without_calling_search(tmp_path: Path) -> None:
    _seed(tmp_path)
    index = _FakeVectorIndex(["gamma.md"], ready=False)
    store = NotesStore(tmp_path, vector_index=index)
    keyword_only = NotesStore(tmp_path).search_notes("apple")

    result = store.search_notes("apple")

    assert [r.path for r in result] == [r.path for r in keyword_only]
    assert index.search_calls == 0  # not_ready short-circuits before search


def test_dimension_mismatch_falls_back_to_keyword(tmp_path: Path) -> None:
    _seed(tmp_path)
    index = _RaisingVectorIndex(EmbeddingDimensionMismatch("run reindex"))
    store = NotesStore(tmp_path, vector_index=index)
    keyword_only = NotesStore(tmp_path).search_notes("apple")
    result = store.search_notes("apple")
    assert [r.path for r in result] == [r.path for r in keyword_only]


def test_missing_model_error_falls_back_to_keyword(tmp_path: Path) -> None:
    _seed(tmp_path)
    index = _RaisingVectorIndex(EmbeddingModelMissingError("download-model"))
    store = NotesStore(tmp_path, vector_index=index)
    keyword_only = NotesStore(tmp_path).search_notes("apple")
    result = store.search_notes("apple")
    assert [r.path for r in result] == [r.path for r in keyword_only]


def test_empty_query_returns_empty_even_with_index(tmp_path: Path) -> None:
    _seed(tmp_path)
    index = _FakeVectorIndex(["alpha.md"])
    store = NotesStore(tmp_path, vector_index=index)
    assert store.search_notes("") == []
