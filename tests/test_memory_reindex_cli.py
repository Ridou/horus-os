"""Tests for `horus-os memory reindex` and `horus-os doctor --memory` (Plan 70-02, Task 3).

No real model is downloaded and no network call is made: the backend's
`is_model_present` and `embed` are stubbed so reindex runs against fake
deterministic vectors. The reindex path must NOT create notes and must NOT
fire any `note_writes` audit row (MEM-07).
"""

from __future__ import annotations

import argparse
import io
import sqlite3
from pathlib import Path

import pytest

from horus_os.cli import run_doctor, run_memory
from horus_os.config import Config


def _reindex_args(tmp_path: Path) -> argparse.Namespace:
    return argparse.Namespace(memory_command="reindex", data_dir=tmp_path)


def _stub_backend(monkeypatch: pytest.MonkeyPatch, *, present: bool) -> None:
    """Stub ONNXEmbeddingBackend so no fastembed model is needed."""
    from horus_os.memory import embeddings

    monkeypatch.setattr(embeddings.ONNXEmbeddingBackend, "is_model_present", lambda self: present)

    def _fake_embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self.dimension
            vec[len(text) % self.dimension] = 1.0
            out.append(vec)
        return out

    monkeypatch.setattr(embeddings.ONNXEmbeddingBackend, "embed", _fake_embed)


def _seed_notes(cfg: Config) -> None:
    cfg.notes_dir.mkdir(parents=True, exist_ok=True)
    (cfg.notes_dir / "a.md").write_text("# alpha\n\nfirst note")
    (cfg.notes_dir / "b.md").write_text("# beta\n\nsecond note")


class _OtherModelBackend:
    """A minimal backend under a DIFFERENT model name, to seed a mismatch.

    The default model has 384 dimensions; this fake matches so the existing
    vec0 table dimension is compatible and only the model NAME differs.
    """

    model_name = "fake/other-model"
    dimension = 384

    def is_model_present(self) -> bool:
        return True

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * self.dimension for _ in texts]


def test_reindex_missing_model_prints_hint_and_returns_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    _stub_backend(monkeypatch, present=False)

    out = io.StringIO()
    err = io.StringIO()
    code = run_memory(_reindex_args(tmp_path), stdout=out, stderr=err)

    assert code == 1
    assert "download-model" in err.getvalue()


def test_reindex_rebuilds_and_prints_count(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    _seed_notes(cfg)
    _stub_backend(monkeypatch, present=True)

    out = io.StringIO()
    err = io.StringIO()
    code = run_memory(_reindex_args(tmp_path), stdout=out, stderr=err)

    assert code == 0, err.getvalue()
    assert "2" in out.getvalue()
    assert cfg.vectors_path().exists()

    # Verify both notes landed in the cache.
    import sqlite_vec

    conn = sqlite3.connect(str(cfg.vectors_path()))
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    try:
        rels = {row[0] for row in conn.execute("SELECT rel_path FROM note_vectors")}
        assert rels == {"a.md", "b.md"}
    finally:
        conn.close()


def test_reindex_creates_no_note_writes_audit_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MEM-07: rebuilding the cache reads files only and creates no audit row."""
    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    _seed_notes(cfg)
    _stub_backend(monkeypatch, present=True)

    # A note write must never happen during reindex: assert by spying on
    # NotesStore.create_note / append_note via the memory_cmd module's import.
    from horus_os.cli import memory_cmd

    def _forbid(self, *a, **k):  # pragma: no cover - must not run
        raise AssertionError("reindex must not create or append notes (MEM-07)")

    monkeypatch.setattr(memory_cmd.NotesStore, "create_note", _forbid)
    monkeypatch.setattr(memory_cmd.NotesStore, "append_note", _forbid)

    out = io.StringIO()
    err = io.StringIO()
    code = run_memory(_reindex_args(tmp_path), stdout=out, stderr=err)
    assert code == 0, err.getvalue()


def test_reindex_resolves_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A reindex after a model swap clears the pending mismatch."""
    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    _seed_notes(cfg)
    _stub_backend(monkeypatch, present=True)

    # Build an index under a different model name directly, then reindex with
    # the configured default model and confirm the stored config is rewritten.
    from horus_os.memory.vector import VectorIndex

    idx = VectorIndex(cfg.vectors_path(), _OtherModelBackend())
    idx.upsert("a.md", "alpha")
    idx.close()

    out = io.StringIO()
    err = io.StringIO()
    code = run_memory(_reindex_args(tmp_path), stdout=out, stderr=err)
    assert code == 0, err.getvalue()

    conn = sqlite3.connect(str(cfg.vectors_path()))
    try:
        stored = conn.execute("SELECT model_name FROM vector_config").fetchone()[0]
        assert stored == cfg.embedding_model
    finally:
        conn.close()


def test_reindex_cli_wired() -> None:
    from horus_os.__main__ import build_parser

    parser = build_parser()
    ns = parser.parse_args(["memory", "reindex", "--data-dir", "/tmp/x"])
    assert ns.memory_command == "reindex"
    assert ns.func is run_memory


# -- doctor --memory ---------------------------------------------------------


def _doctor_memory_args(tmp_path: Path) -> argparse.Namespace:
    return argparse.Namespace(supabase=False, local=False, memory=True, data_dir=tmp_path)


def test_doctor_memory_reports_missing_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    _stub_backend(monkeypatch, present=False)

    out = io.StringIO()
    err = io.StringIO()
    code = run_doctor(_doctor_memory_args(tmp_path), stdout=out, stderr=err)

    assert code == 0
    output = out.getvalue()
    assert "model_present: False" in output
    assert "download-model" in output
    assert "index_exists: False" in output


def test_doctor_memory_reports_ready_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    _seed_notes(cfg)
    _stub_backend(monkeypatch, present=True)

    # Build the index first so doctor finds it ready.
    code = run_memory(_reindex_args(tmp_path), stdout=io.StringIO(), stderr=io.StringIO())
    assert code == 0

    out = io.StringIO()
    err = io.StringIO()
    code = run_doctor(_doctor_memory_args(tmp_path), stdout=out, stderr=err)
    assert code == 0
    output = out.getvalue()
    assert "model_present: True" in output
    assert "index_exists: True" in output
    assert "index_ready: True" in output


def test_doctor_memory_reports_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    _seed_notes(cfg)
    _stub_backend(monkeypatch, present=True)

    from horus_os.memory.vector import VectorIndex

    idx = VectorIndex(cfg.vectors_path(), _OtherModelBackend())
    idx.upsert("a.md", "alpha")
    idx.close()

    out = io.StringIO()
    err = io.StringIO()
    code = run_doctor(_doctor_memory_args(tmp_path), stdout=out, stderr=err)
    assert code == 0
    output = out.getvalue()
    assert "model_mismatch" in output
    assert "reindex" in output


def test_doctor_bare_lists_memory_flag(tmp_path: Path) -> None:
    """A plain `horus-os doctor` (no flags) advertises --memory and stays 0."""
    args = argparse.Namespace(supabase=False, local=False, memory=False, data_dir=tmp_path)
    out = io.StringIO()
    err = io.StringIO()
    code = run_doctor(args, stdout=out, stderr=err)
    assert code == 0
    assert "--memory" in out.getvalue()
