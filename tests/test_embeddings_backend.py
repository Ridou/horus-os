"""Tests for the on-device embedding backend (MEM-05/MEM-06).

Every test mocks fastembed: no model is ever downloaded and no network call
is ever made. A fake `TextEmbedding` is injected via a fake `fastembed`
module so we can assert on the exact keyword arguments fastembed is
constructed with (notably `local_files_only=True` on the embed path) and
prove `.embed()` never reaches the network.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from horus_os.memory.embeddings import (
    EmbeddingModelMissingError,
    ONNXEmbeddingBackend,
    _snapshot_dir_name,
)

MODEL = "BAAI/bge-small-en-v1.5"


class _FakeVector:
    """Stand-in for a numpy array: exposes the .tolist() the backend calls."""

    def __init__(self, values: list[float]) -> None:
        self._values = values

    def tolist(self) -> list[float]:
        return list(self._values)


class _FakeTextEmbedding:
    """Records construction kwargs and returns deterministic 384-d vectors."""

    last_kwargs: dict | None = None

    def __init__(self, **kwargs: object) -> None:
        type(self).last_kwargs = dict(kwargs)
        self.kwargs = dict(kwargs)

    def embed(self, texts: list[str]):
        for _ in texts:
            yield _FakeVector([0.0] * 384)


def _install_fake_fastembed(monkeypatch: pytest.MonkeyPatch) -> type[_FakeTextEmbedding]:
    """Inject a fake `fastembed` module exposing `_FakeTextEmbedding`."""
    _FakeTextEmbedding.last_kwargs = None
    module = types.ModuleType("fastembed")
    module.TextEmbedding = _FakeTextEmbedding
    monkeypatch.setitem(sys.modules, "fastembed", module)
    return _FakeTextEmbedding


def _materialize_snapshot(models_dir: Path) -> None:
    """Create a fake on-disk model snapshot so is_model_present() is True."""
    snapshot = models_dir / _snapshot_dir_name(MODEL) / "snapshots" / "abc123"
    snapshot.mkdir(parents=True, exist_ok=True)
    (snapshot / "model.onnx").write_bytes(b"fake-onnx")


def test_dimension_is_384_for_default_model(tmp_path: Path) -> None:
    backend = ONNXEmbeddingBackend(MODEL, tmp_path)
    assert backend.dimension == 384


def test_unknown_model_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        ONNXEmbeddingBackend("nonexistent/model", tmp_path)


def test_is_model_present_false_before_download(tmp_path: Path) -> None:
    backend = ONNXEmbeddingBackend(MODEL, tmp_path)
    assert backend.is_model_present() is False


def test_is_model_present_true_after_snapshot_exists(tmp_path: Path) -> None:
    _materialize_snapshot(tmp_path)
    backend = ONNXEmbeddingBackend(MODEL, tmp_path)
    assert backend.is_model_present() is True


def test_embed_without_model_raises_actionable_error(tmp_path: Path) -> None:
    backend = ONNXEmbeddingBackend(MODEL, tmp_path)
    with pytest.raises(EmbeddingModelMissingError) as excinfo:
        backend.embed(["hello"])
    assert "horus-os memory download-model" in str(excinfo.value)


def test_embed_uses_local_files_only_when_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _install_fake_fastembed(monkeypatch)
    _materialize_snapshot(tmp_path)
    backend = ONNXEmbeddingBackend(MODEL, tmp_path)

    vectors = backend.embed(["hello", "world"])

    assert len(vectors) == 2
    assert all(len(v) == backend.dimension for v in vectors)
    # The embed path must never reach the network: fastembed is constructed
    # with local_files_only=True (T-70-01).
    assert fake.last_kwargs is not None
    assert fake.last_kwargs.get("local_files_only") is True
    assert fake.last_kwargs.get("model_name") == MODEL
    assert fake.last_kwargs.get("cache_dir") == str(tmp_path)


def test_download_constructs_without_local_files_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _install_fake_fastembed(monkeypatch)
    backend = ONNXEmbeddingBackend(MODEL, tmp_path)
    progress: list[str] = []

    backend.download(on_progress=progress.append)

    # download() is the only path allowed to fetch, so local_files_only is
    # NOT forced True here (it stays at the fastembed default).
    assert fake.last_kwargs is not None
    assert "local_files_only" not in fake.last_kwargs
    assert fake.last_kwargs.get("cache_dir") == str(tmp_path)
    assert progress  # a textual progress signal was emitted


def test_module_imports_without_fastembed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Importing the module and constructing a backend must not need fastembed."""
    monkeypatch.setitem(sys.modules, "fastembed", None)
    # Construction and the on-disk check work with fastembed absent.
    backend = ONNXEmbeddingBackend(MODEL, Path("/tmp/horus-no-such-model"))
    assert backend.is_model_present() is False
    assert backend.dimension == 384


def test_embed_raises_install_hint_when_extra_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With a model present on disk but fastembed missing, embed surfaces the extra."""
    monkeypatch.setitem(sys.modules, "fastembed", None)
    _materialize_snapshot(tmp_path)
    backend = ONNXEmbeddingBackend(MODEL, tmp_path)
    with pytest.raises(RuntimeError) as excinfo:
        backend.embed(["hello"])
    assert "horus-os[local-memory]" in str(excinfo.value)
