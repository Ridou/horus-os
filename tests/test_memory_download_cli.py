"""Tests for `horus-os memory download-model` (MEM-06).

No real model is ever downloaded and no network call is made: the test
stubs `ONNXEmbeddingBackend.is_model_present` / `.download`, or makes the
deferred fastembed import fail, to exercise every branch. The wiring test
confirms the argparse dispatch reaches `run_memory`.
"""

from __future__ import annotations

import argparse
import io
from pathlib import Path

import pytest

from horus_os.cli import run_memory
from horus_os.cli.memory_cmd import _run_download_model
from horus_os.config import Config


def _args(tmp_path: Path) -> argparse.Namespace:
    return argparse.Namespace(memory_command="download-model", data_dir=tmp_path)


def test_bare_memory_prints_usage(tmp_path: Path) -> None:
    args = argparse.Namespace(memory_command=None, data_dir=tmp_path)
    out = io.StringIO()
    err = io.StringIO()
    code = run_memory(args, stdout=out, stderr=err)
    assert code == 0
    assert "download-model" in out.getvalue()
    assert "reindex" in out.getvalue()


def test_already_present_returns_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from horus_os.memory import embeddings

    monkeypatch.setattr(embeddings.ONNXEmbeddingBackend, "is_model_present", lambda self: True)

    def _no_download(self, *, on_progress=None):  # pragma: no cover - must not run
        raise AssertionError("download must not run when the model is already present")

    monkeypatch.setattr(embeddings.ONNXEmbeddingBackend, "download", _no_download)

    out = io.StringIO()
    err = io.StringIO()
    code = run_memory(_args(tmp_path), stdout=out, stderr=err)
    assert code == 0
    assert "already present" in out.getvalue().lower()
    assert err.getvalue() == ""


def test_download_success_calls_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from horus_os.memory import embeddings

    calls: list[bool] = []
    monkeypatch.setattr(embeddings.ONNXEmbeddingBackend, "is_model_present", lambda self: False)

    def _fake_download(self, *, on_progress=None):
        calls.append(True)
        if on_progress is not None:
            on_progress("fetching")

    monkeypatch.setattr(embeddings.ONNXEmbeddingBackend, "download", _fake_download)

    out = io.StringIO()
    err = io.StringIO()
    code = run_memory(_args(tmp_path), stdout=out, stderr=err)
    assert code == 0
    assert calls == [True]
    assert "one-time" in out.getvalue().lower()
    assert "done" in out.getvalue().lower()


def test_missing_extra_prints_install_hint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from horus_os.memory import embeddings

    monkeypatch.setattr(embeddings.ONNXEmbeddingBackend, "is_model_present", lambda self: False)

    def _raise_missing(self, *, on_progress=None):
        raise RuntimeError(
            "the local-memory extra is not installed; run: pip install 'horus-os[local-memory]'"
        )

    monkeypatch.setattr(embeddings.ONNXEmbeddingBackend, "download", _raise_missing)

    out = io.StringIO()
    err = io.StringIO()
    code = _run_download_model(_args(tmp_path), stdout=out, stderr=err)
    assert code == 1
    assert "horus-os[local-memory]" in err.getvalue()


def test_download_resolves_configured_model_and_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The backend is constructed from Config.embedding_model and models_path()."""
    cfg = Config.with_defaults(tmp_path)
    cfg.save()

    captured: dict[str, object] = {}
    from horus_os.cli import memory_cmd

    real_backend = memory_cmd.ONNXEmbeddingBackend

    class _SpyBackend(real_backend):
        def __init__(self, model_name, models_dir):
            captured["model_name"] = model_name
            captured["models_dir"] = Path(models_dir)
            super().__init__(model_name, models_dir)

        def is_model_present(self):
            return True

    monkeypatch.setattr(memory_cmd, "ONNXEmbeddingBackend", _SpyBackend)

    out = io.StringIO()
    err = io.StringIO()
    code = run_memory(_args(tmp_path), stdout=out, stderr=err)
    assert code == 0
    assert captured["model_name"] == "BAAI/bge-small-en-v1.5"
    assert captured["models_dir"] == cfg.models_path()


def test_cli_wired_to_run_memory() -> None:
    from horus_os.__main__ import build_parser

    parser = build_parser()
    ns = parser.parse_args(["memory", "download-model", "--data-dir", "/tmp/x"])
    assert ns.memory_command == "download-model"
    assert ns.func is run_memory
