"""TEST-27 regression suite for POST /api/integrations/{name}/keys and POST /verify.

Covers all Phase 62 security constraints:
  - Loopback guard: non-loopback socket peer gets HTTP 403.
  - Demo-mode refusal: HORUS_OS_DEMO=1 returns 403 from both endpoints.
  - No secret echo: credential value never appears in any response body.
  - Persist: key is written to data_dir/.env at mode 600 on posix.
  - No-clobber: writing a second key does not destroy the first.
  - Rotation invalidation: a new key value resets verified state to false.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from horus_os import create_app


def _loopback_client(tmp_path: Path) -> TestClient:
    """TestClient that presents a loopback socket peer (127.0.0.1)."""
    return TestClient(create_app(data_dir=tmp_path), client=("127.0.0.1", 50000))


def _remote_client(tmp_path: Path) -> TestClient:
    """TestClient that presents a non-loopback socket peer (10.0.0.1)."""
    return TestClient(create_app(data_dir=tmp_path), client=("10.0.0.1", 50000))


def test_loopback_guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-loopback socket peer receives 403; loopback socket peer is allowed."""
    # Register the env var with monkeypatch so the route handler's os.environ mutation
    # is cleaned up after this test and does not leak into subsequent tests.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")

    # Non-loopback must be refused
    resp_remote = _remote_client(tmp_path).post(
        "/api/integrations/anthropic/keys", json={"value": "sk-x"}
    )
    assert resp_remote.status_code == 403

    # Loopback must be allowed (200)
    resp_local = _loopback_client(tmp_path).post(
        "/api/integrations/anthropic/keys", json={"value": "sk-x"}
    )
    assert resp_local.status_code == 200


def test_demo_mode_refusal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Both /keys and /verify return 403 when HORUS_OS_DEMO=1."""
    monkeypatch.setenv("HORUS_OS_DEMO", "1")
    client = _loopback_client(tmp_path)

    resp_keys = client.post("/api/integrations/anthropic/keys", json={"value": "sk-x"})
    assert resp_keys.status_code == 403

    resp_verify = client.post("/api/integrations/anthropic/verify")
    assert resp_verify.status_code == 403


def test_key_write_persists_to_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """POSTing a key writes it to .env and (on posix) sets mode 600. Never echoes the value."""
    secret = "sk-ant-unique-secret-must-not-appear-in-response"
    resp = _loopback_client(tmp_path).post(
        "/api/integrations/anthropic/keys", json={"value": secret}
    )
    assert resp.status_code == 200
    # Secret must not appear in response
    assert secret not in resp.text

    # Value must be written to .env
    env_path = tmp_path / ".env"
    assert env_path.exists(), ".env was not created"
    env_content = env_path.read_text()
    assert "ANTHROPIC_API_KEY" in env_content

    # Mode 600 on posix only
    if os.name == "posix":
        mode = oct(env_path.stat().st_mode & 0o777)
        assert mode == "0o600", f".env file mode {mode} is not 0o600"


def test_key_write_does_not_clobber_other_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Writing a second integration key does not overwrite the first key in .env."""
    # Use monkeypatch so any os.environ mutations from the route handler are cleaned
    # up after this test and do not leak into subsequent tests.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    client = _loopback_client(tmp_path)

    # Write anthropic key first
    resp1 = client.post("/api/integrations/anthropic/keys", json={"value": "sk-ant-value-one"})
    assert resp1.status_code == 200

    # Write gemini key second
    resp2 = client.post("/api/integrations/gemini/keys", json={"value": "gemini-value-two"})
    assert resp2.status_code == 200

    # Both keys must coexist in .env
    env_content = (tmp_path / ".env").read_text()
    assert "ANTHROPIC_API_KEY" in env_content
    assert "GEMINI_API_KEY" in env_content


def test_verify_no_echo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /verify returns pass/fail without echoing the credential value in the response."""
    from horus_os.server.integrations_write import VERIFICATION_PROBES

    secret = "sk-ant-unique-verify-secret-must-not-appear"
    monkeypatch.setenv("ANTHROPIC_API_KEY", secret)

    # Monkeypatch the probe to avoid real network calls
    monkeypatch.setitem(
        VERIFICATION_PROBES,
        "anthropic",
        lambda: (False, "authentication failed"),
    )

    client = _loopback_client(tmp_path)
    resp = client.post("/api/integrations/anthropic/verify")
    assert resp.status_code == 200
    # The secret value must never appear in the response regardless of pass/fail
    assert secret not in resp.text


def test_key_hash_change_invalidates_verified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Writing a new key value resets the verified state from 'verified' to 'configured-unverified'."""
    from horus_os.server.integrations_write import VERIFICATION_PROBES

    # Monkeypatch the probe to return success without making network calls
    monkeypatch.setitem(
        VERIFICATION_PROBES,
        "anthropic",
        lambda: (True, None),
    )

    client = _loopback_client(tmp_path)

    # Write initial key
    resp_write = client.post(
        "/api/integrations/anthropic/keys", json={"value": "sk-ant-key-version-a"}
    )
    assert resp_write.status_code == 200

    # Verify it - probe returns success
    resp_verify = client.post("/api/integrations/anthropic/verify")
    assert resp_verify.status_code == 200
    assert resp_verify.json()["ok"] is True

    # GET /api/integrations must show "verified" now
    resp_get = client.get("/api/integrations")
    assert resp_get.status_code == 200
    items = {i["id"]: i["status"] for i in resp_get.json()["integrations"]}
    assert items["anthropic"] == "verified", f"Expected verified, got {items['anthropic']}"

    # Now write a different key value (rotation)
    resp_rotate = client.post(
        "/api/integrations/anthropic/keys", json={"value": "sk-ant-key-version-b"}
    )
    assert resp_rotate.status_code == 200

    # GET /api/integrations must show "configured-unverified" after rotation
    resp_get2 = client.get("/api/integrations")
    assert resp_get2.status_code == 200
    items2 = {i["id"]: i["status"] for i in resp_get2.json()["integrations"]}
    assert items2["anthropic"] == "configured-unverified", (
        f"Expected configured-unverified after rotation, got {items2['anthropic']}"
    )


def test_loopback_guard_verify(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-loopback peer receives 403 on POST /verify; loopback peer is allowed."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-x")

    # Non-loopback must be refused on /verify
    resp_remote = _remote_client(tmp_path).post("/api/integrations/anthropic/verify")
    assert resp_remote.status_code == 403

    # Loopback must reach the handler (will fail probe but not with 403)
    from horus_os.server.integrations_write import VERIFICATION_PROBES

    monkeypatch.setitem(
        VERIFICATION_PROBES,
        "anthropic",
        lambda: (False, "authentication failed"),
    )
    resp_local = _loopback_client(tmp_path).post("/api/integrations/anthropic/verify")
    assert resp_local.status_code == 200


def test_newline_injection_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A credential value containing a newline is rejected with 422 and nothing is written."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    client = _loopback_client(tmp_path)

    # LF injection
    resp_lf = client.post(
        "/api/integrations/anthropic/keys",
        json={"value": "sk-real\nOTHER_KEY=injected"},
    )
    assert resp_lf.status_code == 422, f"Expected 422 for LF injection, got {resp_lf.status_code}"

    # CR injection
    resp_cr = client.post(
        "/api/integrations/anthropic/keys",
        json={"value": "sk-real\rOTHER_KEY=injected"},
    )
    assert resp_cr.status_code == 422, f"Expected 422 for CR injection, got {resp_cr.status_code}"

    # Nothing written to .env
    env_path = tmp_path / ".env"
    assert not env_path.exists(), ".env must not be created when injection is rejected"


def test_empty_value_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty credential value is rejected with 422."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    resp = _loopback_client(tmp_path).post("/api/integrations/anthropic/keys", json={"value": ""})
    assert resp.status_code == 422, f"Expected 422 for empty value, got {resp.status_code}"


def test_whitespace_value_stable_hash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A credential value with trailing whitespace is stored stripped for a stable hash."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    client = _loopback_client(tmp_path)

    secret_padded = "sk-ant-padded-key   "
    secret_stripped = secret_padded.strip()

    resp = client.post("/api/integrations/anthropic/keys", json={"value": secret_padded})
    assert resp.status_code == 200

    # .env must contain the stripped value
    env_content = (tmp_path / ".env").read_text()
    assert "ANTHROPIC_API_KEY=" + secret_stripped in env_content
    # The padded version must not be in the file
    assert "ANTHROPIC_API_KEY=" + secret_padded not in env_content
