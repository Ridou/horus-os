"""On-device embedding backends for hybrid vector memory (MEM-05/MEM-06).

This module is the opt-in gate the rest of the vector-memory subsystem
sits behind. It imports cleanly WITHOUT the `[local-memory]` extra: the
`fastembed` import is deferred inside the methods that actually need it
(`download` and `_load`), never at module top or in `__init__`. That keeps
a bare install importable (Pitfall EM-2) and the system startable offline.

Hard guarantees:
- Nothing constructs the ONNX model at import or `__init__` time (EM-1).
- `is_model_present()` is a pure on-disk check; it never imports fastembed
  and never touches the network.
- `embed()` refuses to run when the model is absent, raising
  `EmbeddingModelMissingError` whose message names the exact CLI command to
  fix it. When the model is present it constructs fastembed with
  `local_files_only=True`, so an embed call never reaches the network.
- `download()` is the ONLY method that may reach the network; it is invoked
  solely by the explicit `horus-os memory download-model` command (MEM-06).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol, runtime_checkable

# Known embedding models and their output dimension. Downstream dimension
# detection (EM-3) needs a real number before a vector table is created, so
# an unknown model is a hard error rather than a guess. The default matches
# Config.embedding_model.
_MODEL_DIMENSIONS: dict[str, int] = {
    "BAAI/bge-small-en-v1.5": 384,
}

# Hint shown when the optional extra is missing. Kept as a constant so the CLI
# and the backend surface the identical install command.
_INSTALL_HINT = "pip install 'horus-os[local-memory]'"


class EmbeddingModelMissingError(RuntimeError):
    """Raised when an embed is requested but the model is not on disk.

    The message always names `horus-os memory download-model` so the user has
    an actionable next step instead of an opaque network timeout (EM-1).
    """


@runtime_checkable
class EmbeddingBackend(Protocol):
    """The surface every embedding backend exposes to the memory layer."""

    dimension: int
    model_name: str

    def is_model_present(self) -> bool:
        """Return True when the model is cached locally (no network)."""
        ...

    def download(self, *, on_progress: Callable[[str], None] | None = None) -> None:
        """Fetch the model once. The only method that may reach the network."""
        ...

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed `texts` on-device, returning one float vector per input."""
        ...


def _snapshot_dir_name(model_name: str) -> str:
    """Map a HF model id to its on-disk cache directory name.

    fastembed reuses the Hugging Face Hub cache convention: a model id like
    `BAAI/bge-small-en-v1.5` is stored under `models--BAAI--bge-small-en-v1.5`
    inside the configured cache_dir.
    """
    return "models--" + model_name.replace("/", "--")


class ONNXEmbeddingBackend:
    """fastembed ONNX backend with an explicit-download gate (MEM-05/MEM-06).

    Construction is cheap and import-free: it records the model name and the
    cache directory and resolves the dimension from the known-model map. The
    fastembed model object is built lazily and cached on first `embed()` (with
    `local_files_only=True`) or fetched by `download()`.
    """

    def __init__(self, model_name: str, models_dir: Path) -> None:
        if model_name not in _MODEL_DIMENSIONS:
            known = ", ".join(sorted(_MODEL_DIMENSIONS))
            raise ValueError(f"unknown embedding model {model_name!r}; known models: {known}")
        self.model_name = model_name
        self.models_dir = Path(models_dir)
        self._model = None

    @property
    def dimension(self) -> int:
        """The fixed output dimension for this model (384 for the default)."""
        return _MODEL_DIMENSIONS[self.model_name]

    def is_model_present(self) -> bool:
        """Return True when the model snapshot exists on disk.

        Pure on-disk check: it neither imports nor constructs fastembed and
        makes no network call (EM-1). A snapshot directory must exist and hold
        at least one file for the model to count as present.
        """
        snapshot_root = self.models_dir / _snapshot_dir_name(self.model_name) / "snapshots"
        if not snapshot_root.is_dir():
            return False
        for snapshot in snapshot_root.iterdir():
            if snapshot.is_dir() and any(snapshot.rglob("*")):
                return True
        return False

    def _import_text_embedding(self):
        """Deferred fastembed import with a clear missing-extra message (EM-2)."""
        try:
            from fastembed import TextEmbedding
        except ImportError as exc:
            raise RuntimeError(
                "the local-memory extra is not installed; run: " + _INSTALL_HINT
            ) from exc
        return TextEmbedding

    def download(self, *, on_progress: Callable[[str], None] | None = None) -> None:
        """Fetch the model into `models_dir`, then warm it up.

        This is the ONLY method that may reach the network. It constructs
        fastembed with the default `local_files_only=False` so the one-time
        Hugging Face fetch can run, then embeds a single warmup string to force
        the ONNX files to materialize on disk.
        """
        TextEmbedding = self._import_text_embedding()
        self.models_dir.mkdir(parents=True, exist_ok=True)
        if on_progress is not None:
            on_progress(f"fetching {self.model_name}")
        model = TextEmbedding(model_name=self.model_name, cache_dir=str(self.models_dir))
        # Warm up so the ONNX weights are actually written, not just resolved.
        list(model.embed(["warmup"]))
        if on_progress is not None:
            on_progress("done")
        self._model = model

    def _load(self):
        """Lazily build and cache the local-only fastembed model.

        Always constructs with `local_files_only=True` so an embed never
        reaches the network (T-70-01); the absence of the file raises here
        rather than triggering a silent download.
        """
        if self._model is None:
            TextEmbedding = self._import_text_embedding()
            self._model = TextEmbedding(
                model_name=self.model_name,
                cache_dir=str(self.models_dir),
                local_files_only=True,
            )
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed `texts` on-device. Raises if the model is not downloaded.

        The presence check runs first: a missing model raises
        `EmbeddingModelMissingError` naming the download command rather than
        attempting any network fetch (MEM-06).
        """
        if not self.is_model_present():
            raise EmbeddingModelMissingError(
                "embedding model not downloaded; run: horus-os memory download-model"
            )
        model = self._load()
        return [vector.tolist() for vector in model.embed(texts)]
