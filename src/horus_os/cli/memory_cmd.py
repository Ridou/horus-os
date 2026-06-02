"""`horus-os memory` subcommand (MEM-06 / MEM-07).

`download-model` is the SOLE path that triggers an embedding-model download.
Nothing on the startup, serve, or note-write path calls into this module, so a
fresh install starts offline with no model present (EM-1).

`reindex` rebuilds the separate `vectors.sqlite` cache from the notes folder. It
reads existing files only: it creates no notes and fires no `note_writes` audit
row (MEM-07: rebuilding the cache is not a memory write). It also resolves an
EM-3 model/dimension mismatch by rewriting the index at the current model.
"""

from __future__ import annotations

import argparse
from typing import TextIO

from horus_os.config import Config
from horus_os.memory.embeddings import ONNXEmbeddingBackend
from horus_os.memory.notes import NotesStore
from horus_os.memory.vector import VectorIndex

# Approximate one-time download size for the default model, surfaced before the
# fetch so the user is never surprised by a large transfer (EM-1).
_DEFAULT_MODEL_APPROX_MB = 23

_USAGE = (
    "Usage: horus-os memory <operation>\n"
    "\n"
    "  download-model    Download the on-device embedding model (one-time).\n"
    "  reindex           Rebuild the vector index from existing notes.\n"
)


def run_memory(args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO) -> int:
    """Dispatch a `memory` operation. Returns a process exit code."""
    operation = getattr(args, "memory_command", None)
    if operation == "download-model":
        return _run_download_model(args, stdout=stdout, stderr=stderr)
    if operation == "reindex":
        return _run_reindex(args, stdout=stdout, stderr=stderr)
    # Bare `horus-os memory` (or an unhandled op) prints usage and exits 0.
    stdout.write(_USAGE)
    return 0


def _run_download_model(args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO) -> int:
    """Download the embedding model once. The only network trigger (MEM-06)."""
    config = Config.load(getattr(args, "data_dir", None))
    backend = ONNXEmbeddingBackend(config.embedding_model, config.models_path())

    if backend.is_model_present():
        stdout.write(
            f"Embedding model {config.embedding_model!r} is already present at "
            f"{config.models_path()}.\n"
        )
        return 0

    stdout.write(
        f"Downloading embedding model {config.embedding_model!r} "
        f"(~{_DEFAULT_MODEL_APPROX_MB} MB, one-time download).\n"
    )

    def _on_progress(message: str) -> None:
        stdout.write(f"  {message}...\n")

    try:
        backend.download(on_progress=_on_progress)
    except RuntimeError as exc:
        # The deferred fastembed import failed: surface the install hint and
        # fail rather than pretending the model is available.
        stderr.write(f"{exc}\n")
        return 1

    stdout.write(f"Done. Model available at {config.models_path()}.\n")
    return 0


def _run_reindex(args: argparse.Namespace, *, stdout: TextIO, stderr: TextIO) -> int:
    """Rebuild the vector cache from the notes folder (MEM-07).

    Reads existing notes only: it creates no notes and fires no `note_writes`
    audit row (NotesStore is built with no `on_write` callback). When the model
    is not present it prints the download hint and returns 1 rather than
    attempting any network fetch (EM-1).
    """
    config = Config.load(getattr(args, "data_dir", None))
    backend = ONNXEmbeddingBackend(config.embedding_model, config.models_path())

    if not backend.is_model_present():
        stderr.write("embedding model not downloaded; run: horus-os memory download-model\n")
        return 1

    # No on_write callback: reading existing notes for a rebuild is not a memory
    # write and must not produce an audit row (MEM-07).
    store = NotesStore(config.notes_dir)
    pairs = [(ref.path, store.read_note(ref.path)) for ref in store.list_notes()]

    index = VectorIndex(config.vectors_path(), backend)
    try:
        count = index.reindex(pairs)
    finally:
        index.close()

    stdout.write(f"Reindexed {count} note(s) into {config.vectors_path()}.\n")
    return 0
