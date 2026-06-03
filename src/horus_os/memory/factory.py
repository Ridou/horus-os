"""Factory that wires an optional VectorIndex from config (MEM-06/TEST-33).

`build_vector_index(cfg)` is the single place the server and CLI use to decide
whether hybrid vector search is active for a run. It is deliberately total: it
NEVER triggers a download and NEVER raises on a misconfigured or offline system.
On any reason the index cannot be used (feature off, model absent, the
`[local-memory]` extra missing, sqlite-vec unloadable) it returns None and the
caller's NotesStore degrades to keyword-only search, so a fresh install starts
and serves notes offline with no model file present (EM-1).

The vector and embeddings modules are imported lazily inside the function so a
bare install (no `[local-memory]` extra) can still import this package; the
deferred ImportError is caught and turned into a None return, not a crash.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from horus_os.config import Config
    from horus_os.memory.vector import VectorIndex

_log = logging.getLogger(__name__)


def build_vector_index(cfg: Config) -> VectorIndex | None:
    """Return a ready-to-use VectorIndex, or None when vector memory is off/unusable.

    Returns None (with a one-line warning) when:
    - `cfg.vector_memory_enabled` is False (off by default),
    - the embedding model is not downloaded yet (offline start, MEM-06),
    - the `[local-memory]` extra or sqlite-vec is unavailable (Pitfall EM-2).

    Otherwise it constructs an `ONNXEmbeddingBackend` over `cfg.models_path()`
    and a `VectorIndex` over `cfg.vectors_path()`. Construction never downloads
    a model and never reaches the network; a usable index requires the model to
    already be present on disk.
    """
    if not cfg.vector_memory_enabled:
        return None
    try:
        from horus_os.memory.embeddings import ONNXEmbeddingBackend
        from horus_os.memory.vector import VectorIndex, VectorIndexUnavailable
    except ImportError as exc:
        _log.warning("vector memory enabled but the local-memory extra is missing: %s", exc)
        return None
    try:
        backend = ONNXEmbeddingBackend(cfg.embedding_model, cfg.models_path())
    except ValueError as exc:
        # An unknown embedding_model in config; do not crash startup.
        _log.warning("vector memory enabled but the embedding model is invalid: %s", exc)
        return None
    if not backend.is_model_present():
        # Offline start: the model has not been downloaded. Stay keyword-only
        # rather than block startup or attempt a fetch (MEM-06/TEST-33).
        _log.warning(
            "vector memory enabled but the embedding model is not downloaded; "
            "run: horus-os memory download-model (search stays keyword-only until then)"
        )
        return None
    try:
        return VectorIndex(cfg.vectors_path(), backend)
    except VectorIndexUnavailable as exc:
        _log.warning("vector memory enabled but sqlite-vec is unavailable: %s", exc)
        return None
