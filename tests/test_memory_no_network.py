"""TEST-33 half 1: a memory write makes zero outbound network calls (MEM-05).

A network tripwire monkeypatches `socket.socket.connect`/`connect_ex` (and, when
httpx is importable, httpx's transport handlers) to fail the test the instant any
outbound connection is attempted during a memory write. We then exercise two
layers:

  (a) NotesStore writes with vector_index=None and with a vector-enabled store
      whose backend is a fake on-device embedder, asserting the tripwire never
      fires (the audit + cache path stays fully local).

  (b) The production embed path provably cannot reach the network: a fake
      fastembed records its construction kwargs and we assert
      `ONNXEmbeddingBackend.embed` builds `TextEmbedding(local_files_only=True)`.

No real model is downloaded and no real socket is opened; fastembed is faked, so
the suite stays green with OR without the [local-memory] extra installed (EM-2).
"""

from __future__ import annotations

import socket
import sys
import types
from pathlib import Path

import pytest

from horus_os.memory.embeddings import ONNXEmbeddingBackend, _snapshot_dir_name
from horus_os.memory.notes import NotesStore

MODEL = "BAAI/bge-small-en-v1.5"


class _NetworkAttempted(AssertionError):
    """Raised by the tripwire when any outbound network call is attempted."""


@pytest.fixture
def network_tripwire(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail the test if any outbound socket connect or HTTP request happens.

    Patches the low-level `socket.socket.connect`/`connect_ex` so even a raw
    socket attempt is caught, and, when httpx is importable, both its sync and
    async transport handlers so a higher-level HTTP request is caught with a
    clearer message before it reaches the socket layer.
    """

    def _blocked_connect(self: socket.socket, *args: object, **kwargs: object) -> None:
        raise _NetworkAttempted("network call (socket.connect) during memory write")

    def _blocked_connect_ex(self: socket.socket, *args: object, **kwargs: object) -> int:
        raise _NetworkAttempted("network call (socket.connect_ex) during memory write")

    monkeypatch.setattr(socket.socket, "connect", _blocked_connect, raising=True)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked_connect_ex, raising=True)

    try:
        import httpx
    except ImportError:
        return

    def _blocked_http(self: object, *args: object, **kwargs: object) -> None:
        raise _NetworkAttempted("network call (httpx request) during memory write")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", _blocked_http, raising=False)
    monkeypatch.setattr(
        httpx.AsyncHTTPTransport, "handle_async_request", _blocked_http, raising=False
    )


class _FakeBackend:
    """A deterministic on-device embedder: no fastembed, no model, no network."""

    dimension = 3
    model_name = "fake/model"

    def __init__(self) -> None:
        self.embed_calls = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.embed_calls += 1
        return [[float(len(t)), 0.0, 0.0] for t in texts]


class _FakeVectorIndex:
    """Records upserts; embeds via the fake backend. Never touches the network."""

    def __init__(self) -> None:
        self.backend = _FakeBackend()
        self.upserts: list[tuple[str, str]] = []

    def upsert(self, rel_path: str, text: str) -> None:
        # Mirror the real upsert: embed (local) then store. No I/O beyond memory.
        self.backend.embed([text])
        self.upserts.append((rel_path, text))


# -- layer (a): writes make no outbound network calls ------------------------


def test_keyword_only_write_makes_no_network(tmp_path: Path, network_tripwire: None) -> None:
    store = NotesStore(tmp_path)
    store.create_note("a.md", "# A\n\nfirst body")
    store.append_note("a.md", "more body")
    # No exception from the tripwire means no outbound connection was attempted.
    assert (tmp_path / "a.md").read_text() == "# A\n\nfirst body\nmore body"


def test_vector_enabled_write_makes_no_network(tmp_path: Path, network_tripwire: None) -> None:
    index = _FakeVectorIndex()
    audit: list[str] = []
    store = NotesStore(
        tmp_path,
        on_write=lambda w: audit.append(w.rel_path),
        vector_index=index,
    )

    store.create_note("note.md", "embedded body")

    # The audit row fired, the cache upsert ran, the embed ran locally, and the
    # tripwire never fired.
    assert audit == ["note.md"]
    assert index.upserts == [("note.md", "embedded body")]
    assert index.backend.embed_calls == 1


def test_search_with_vector_index_makes_no_network(tmp_path: Path, network_tripwire: None) -> None:
    # A search that embeds the query through the fake backend stays local too.
    (tmp_path / "n.md").write_text("# N\n\nshared keyword body")

    class _ReadyIndex(_FakeVectorIndex):
        def is_ready(self) -> bool:
            return True

        def search(self, query_vec: list[float], top_k: int = 20):
            return [("n.md", 0.1)]

    store = NotesStore(tmp_path, vector_index=_ReadyIndex())
    paths = [r.path for r in store.search_notes("keyword")]
    assert "n.md" in paths


# -- layer (b): the production embed path forces local_files_only=True --------


def _install_fake_fastembed(monkeypatch: pytest.MonkeyPatch) -> type:
    """Inject a fake `fastembed` module that records its construction kwargs."""

    class _FakeVector:
        def __init__(self, values: list[float]) -> None:
            self._values = values

        def tolist(self) -> list[float]:
            return list(self._values)

    class _FakeTextEmbedding:
        last_kwargs: dict | None = None

        def __init__(self, **kwargs: object) -> None:
            type(self).last_kwargs = dict(kwargs)

        def embed(self, texts: list[str]):
            for _ in texts:
                yield _FakeVector([0.0] * 384)

    module = types.ModuleType("fastembed")
    module.TextEmbedding = _FakeTextEmbedding
    monkeypatch.setitem(sys.modules, "fastembed", module)
    return _FakeTextEmbedding


def _materialize_snapshot(models_dir: Path) -> None:
    snapshot = models_dir / _snapshot_dir_name(MODEL) / "snapshots" / "abc123"
    snapshot.mkdir(parents=True, exist_ok=True)
    (snapshot / "model.onnx").write_bytes(b"fake-onnx")


def test_production_embed_uses_local_files_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, network_tripwire: None
) -> None:
    fake = _install_fake_fastembed(monkeypatch)
    _materialize_snapshot(tmp_path)
    backend = ONNXEmbeddingBackend(MODEL, tmp_path)

    backend.embed(["a memory write would embed text exactly like this"])

    # The embed path constructs fastembed with local_files_only=True, so it can
    # never reach the network: this is the structural guarantee behind TEST-33.
    assert fake.last_kwargs is not None
    assert fake.last_kwargs.get("local_files_only") is True
    assert fake.last_kwargs.get("model_name") == MODEL
    assert fake.last_kwargs.get("cache_dir") == str(tmp_path)
