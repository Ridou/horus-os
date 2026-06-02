"""TEST-33 half 2: the system starts and serves notes offline with no model (MEM-06).

With `vector_memory_enabled=True` in config but NO embedding model on disk, the
factory must return None (not raise), and a NotesStore built from it must serve
`list_notes` / `search_notes` / `create_note` normally in keyword-only mode. No
download is ever attempted: `ONNXEmbeddingBackend.download` is monkeypatched to
fail the test if called during start, search, or write (EM-1).

The model directory is simply left empty to simulate offline (no OS-level network
disablement needed): `is_model_present()` is a pure on-disk check, so an empty
`models_path()` is indistinguishable from a never-downloaded model. fastembed is
never imported on any path exercised here, so this file passes with OR without
the [local-memory] extra installed (EM-2).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from horus_os.config import Config
from horus_os.memory import build_vector_index
from horus_os.memory.embeddings import ONNXEmbeddingBackend
from horus_os.memory.notes import NotesStore


@pytest.fixture
def no_download(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail the test if the embedding model download is ever triggered."""

    def _boom(self: ONNXEmbeddingBackend, *args: object, **kwargs: object) -> None:
        raise AssertionError("model download attempted during offline start")

    monkeypatch.setattr(ONNXEmbeddingBackend, "download", _boom, raising=True)


def _offline_config(tmp_path: Path) -> Config:
    """A config with vector memory ENABLED but an empty (model-less) models dir."""
    cfg = Config.with_defaults(tmp_path)
    cfg.notes_dir.mkdir(parents=True, exist_ok=True)
    # vector_memory_enabled True, models_dir present but empty: offline-equivalent.
    return Config(
        data_dir=cfg.data_dir,
        db_path=cfg.db_path,
        notes_dir=cfg.notes_dir,
        vector_memory_enabled=True,
        models_dir=tmp_path / "models",
    )


def test_factory_returns_none_when_model_absent(tmp_path: Path, no_download: None) -> None:
    cfg = _offline_config(tmp_path)
    # The model was never downloaded: the factory degrades to keyword-only by
    # returning None rather than raising or attempting a fetch.
    assert build_vector_index(cfg) is None


def test_factory_does_not_raise_with_enabled_flag(tmp_path: Path, no_download: None) -> None:
    cfg = _offline_config(tmp_path)
    # Even with the feature flag ON and no model, building the index must not
    # raise: offline start is preserved.
    result = build_vector_index(cfg)
    assert result is None


def test_notes_serve_keyword_only_when_model_absent(tmp_path: Path, no_download: None) -> None:
    cfg = _offline_config(tmp_path)
    index = build_vector_index(cfg)  # None offline
    store = NotesStore(cfg.notes_dir, vector_index=index)

    # create_note, list_notes, search_notes all work with no model present.
    store.create_note("alpha.md", "# Alpha\n\nApples and oranges.")
    store.create_note("beta.md", "# Beta\n\nA note about event loops.")

    titles = sorted(r.title for r in store.list_notes())
    assert titles == ["Alpha", "Beta"]

    hits = [r.path for r in store.search_notes("apples")]
    assert hits == ["alpha.md"]  # keyword-only ranking, no vector merge

    # A semantic-only query that the keyword path cannot satisfy simply returns
    # nothing offline (no crash, no download): the model is required to bridge it.
    assert store.search_notes("nonexistentkeyword") == []


def test_missing_model_branch_is_reachable(tmp_path: Path, no_download: None) -> None:
    cfg = _offline_config(tmp_path)
    # The actionable missing-model path is reachable: the backend reports the
    # model absent (pure on-disk check, no network) and names the fix command.
    backend = ONNXEmbeddingBackend(cfg.embedding_model, cfg.models_path())
    assert backend.is_model_present() is False
    from horus_os.memory.embeddings import EmbeddingModelMissingError

    with pytest.raises(EmbeddingModelMissingError) as excinfo:
        backend.embed(["query"])
    assert "horus-os memory download-model" in str(excinfo.value)


def test_offline_full_cycle_never_downloads(tmp_path: Path, no_download: None) -> None:
    # End-to-end: build the (None) index, write a note, then search. The
    # download monkeypatch would fail the test if any step attempted a fetch.
    cfg = _offline_config(tmp_path)
    store = NotesStore(cfg.notes_dir, vector_index=build_vector_index(cfg))
    store.create_note("log.md", "first entry")
    store.append_note("log.md", "second entry")
    refs = store.search_notes("entry")
    assert [r.path for r in refs] == ["log.md"]
