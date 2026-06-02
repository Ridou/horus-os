"""Tests for POST /api/uploads (VIS-03).

The uploads route stores images and PDFs under <data_dir>/uploads/ with a
uuid-based filename and returns the absolute path the agent passes to
analyze_file. Coverage:
- a small PNG is accepted (200), stored under <data_dir>/uploads/, and exists
- a text/plain upload is refused with 400 and nothing is stored
- an oversized upload is refused with 413 and nothing is stored
- a malicious client filename cannot escape the uploads dir (uuid-based name)
- analyze_file is registered into the chat registry scoped to the uploads dir

No network calls are made; the route is pure filesystem.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from horus_os import Config, Database, create_app
from horus_os.server import api as server_api

# A 1x1 transparent PNG: enough to exercise the image path with real bytes.
_PNG_BYTES = bytes(
    [
        0x89,
        0x50,
        0x4E,
        0x47,
        0x0D,
        0x0A,
        0x1A,
        0x0A,
        0x00,
        0x00,
        0x00,
        0x0D,
        0x49,
        0x48,
        0x44,
        0x52,
        0x00,
        0x00,
        0x00,
        0x01,
        0x00,
        0x00,
        0x00,
        0x01,
        0x08,
        0x06,
        0x00,
        0x00,
        0x00,
        0x1F,
        0x15,
        0xC4,
        0x89,
    ]
)


def _init_db(tmp_path: Path) -> Database:
    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    db = Database(cfg.db_path)
    db.init()
    return db


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(data_dir=tmp_path))


def test_upload_png_returns_path_under_uploads(tmp_path: Path) -> None:
    _init_db(tmp_path)
    client = _client(tmp_path)
    response = client.post(
        "/api/uploads",
        files={"file": ("pic.png", _PNG_BYTES, "image/png")},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    stored = Path(payload["path"])
    assert stored.is_file()
    assert stored.read_bytes() == _PNG_BYTES
    uploads_dir = (tmp_path / "uploads").resolve()
    assert uploads_dir == stored.parent.resolve()
    assert stored.suffix == ".png"
    assert payload["content_type"] == "image/png"
    assert payload["size"] == len(_PNG_BYTES)


def test_upload_pdf_is_accepted(tmp_path: Path) -> None:
    _init_db(tmp_path)
    client = _client(tmp_path)
    response = client.post(
        "/api/uploads",
        files={"file": ("doc.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert response.status_code == 200, response.text
    assert Path(response.json()["path"]).suffix == ".pdf"


def test_upload_rejects_non_allowlisted_type(tmp_path: Path) -> None:
    _init_db(tmp_path)
    client = _client(tmp_path)
    response = client.post(
        "/api/uploads",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400
    # Nothing was written: the uploads dir is either absent or empty.
    uploads_dir = tmp_path / "uploads"
    assert not uploads_dir.exists() or not any(uploads_dir.iterdir())


def test_upload_rejects_oversized_file(tmp_path: Path) -> None:
    _init_db(tmp_path)
    client = _client(tmp_path)
    oversized = b"\x89PNG" + b"\x00" * (server_api.UPLOAD_MAX_BYTES + 1)
    response = client.post(
        "/api/uploads",
        files={"file": ("big.png", oversized, "image/png")},
    )
    assert response.status_code == 413
    uploads_dir = tmp_path / "uploads"
    assert not uploads_dir.exists() or not any(uploads_dir.iterdir())


def test_upload_filename_cannot_traverse(tmp_path: Path) -> None:
    _init_db(tmp_path)
    client = _client(tmp_path)
    response = client.post(
        "/api/uploads",
        files={"file": ("../../evil.png", _PNG_BYTES, "image/png")},
    )
    assert response.status_code == 200, response.text
    stored = Path(response.json()["path"]).resolve()
    uploads_dir = (tmp_path / "uploads").resolve()
    # The stored file lives under the uploads dir; the client name did not
    # influence the on-disk path (it is uuid-based), so nothing landed outside.
    assert uploads_dir == stored.parent
    assert stored.name != "evil.png"
    assert not (tmp_path.parent / "evil.png").exists()
    assert not (tmp_path / "evil.png").exists()


def test_analyze_file_registered_in_chat_registry(tmp_path: Path) -> None:
    from horus_os.memory import NotesStore

    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    notes_store = NotesStore(cfg.notes_dir)
    registry = server_api._build_default_registry(cfg, notes_store)
    assert "analyze_file" in registry
    names = {tool.name for tool in registry.list()}
    assert "analyze_file" in names
