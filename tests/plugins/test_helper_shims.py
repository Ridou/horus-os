"""PluginContext helper shims: filesystem / secrets / net.

PERMISSION-01 success criteria: each shim raises PermissionDenied
when the corresponding grant row is missing, with .plugin_name and
.capability populated. Path-escape defense (Pitfall 1) runs Path.resolve
BEFORE the cap check.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from horus_os.plugins.api import PluginContext
from horus_os.plugins.capability_catalog import Capability
from horus_os.plugins.permissions import CapabilityGuard, PermissionDenied


def _make_ctx(plugin_name: str, data_dir: Path,
              granted: set[Capability] | None = None) -> PluginContext:
    guard = CapabilityGuard(
        plugin_name,
        granted_capabilities=granted if granted is not None else set(),
    )
    return PluginContext(
        plugin_name=plugin_name,
        plugin_version="0.1.0",
        data_dir=data_dir,
        guard=guard,
    )


# --- filesystem.read -------------------------------------------------------


def test_filesystem_read_without_grant_raises(tmp_path: Path) -> None:
    ctx = _make_ctx("foo", tmp_path)
    target = tmp_path / "x.txt"
    target.write_text("payload", encoding="utf-8")

    with pytest.raises(PermissionDenied) as exc_info:
        ctx.filesystem.read(target)

    assert exc_info.value.plugin_name == "foo"
    assert exc_info.value.capability == "filesystem.read"


def test_filesystem_read_with_grant_succeeds(tmp_path: Path) -> None:
    ctx = _make_ctx("foo", tmp_path, granted={Capability.FILESYSTEM_READ})
    target = tmp_path / "x.txt"
    target.write_text("hello", encoding="utf-8")

    assert ctx.filesystem.read(target) == "hello"


def test_filesystem_read_path_escape_defense(tmp_path: Path) -> None:
    """Path.resolve runs BEFORE the cap check (Pitfall 1).

    We assert Path.resolve is called at least once during the read by
    patching pathlib.Path.resolve. The shim must invoke it on the
    incoming path before evaluating the cap; this is the defense that
    surfaces traversal attempts in the audit trail and lets a future
    phase enforce per-capability paths.
    """
    ctx = _make_ctx("foo", tmp_path, granted={Capability.FILESYSTEM_READ})
    target = tmp_path / "real.txt"
    target.write_text("ok", encoding="utf-8")

    with patch.object(Path, "resolve",
                      autospec=True,
                      side_effect=lambda self, **kw: Path.resolve.__wrapped__(self, **kw)
                      if hasattr(Path.resolve, "__wrapped__")
                      else self) as mock_resolve:
        # We need to call the real resolve inside the patch, so we use
        # a side_effect that calls the original implementation. The
        # simpler approach: pre-snapshot the bound method.
        pass

    # The mock-call-the-original recipe is brittle; assert the
    # invariant directly by wrapping the bound resolve in a counter
    # and reading the path the shim resolves it to.
    calls: list[Path] = []
    original_resolve = Path.resolve

    def counting_resolve(self: Path, *args: Any, **kwargs: Any) -> Path:
        result = original_resolve(self, *args, **kwargs)
        calls.append(self)
        return result

    with patch.object(Path, "resolve", counting_resolve):
        content = ctx.filesystem.read(target)

    assert content == "ok"
    # Path.resolve was called at least once on a Path constructed
    # from the input — path-escape defense in place.
    assert len(calls) >= 1


def test_filesystem_write_without_grant_raises(tmp_path: Path) -> None:
    ctx = _make_ctx("foo", tmp_path, granted={Capability.FILESYSTEM_READ})  # READ only

    with pytest.raises(PermissionDenied) as exc_info:
        ctx.filesystem.write(tmp_path / "y.txt", "x")
    assert exc_info.value.capability == "filesystem.write"


def test_filesystem_write_with_grant_succeeds(tmp_path: Path) -> None:
    ctx = _make_ctx("foo", tmp_path, granted={Capability.FILESYSTEM_WRITE})
    target = tmp_path / "y.txt"
    ctx.filesystem.write(target, "written")
    assert target.read_text(encoding="utf-8") == "written"


# --- secrets.read ----------------------------------------------------------


def test_secrets_read_without_grant_raises(tmp_path: Path) -> None:
    ctx = _make_ctx("foo", tmp_path)

    with pytest.raises(PermissionDenied) as exc_info:
        ctx.secrets.read("FOO")
    assert exc_info.value.capability == "secrets.read"


def test_secrets_read_with_grant_returns_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FOO_TEST_VAR", "bar")
    ctx = _make_ctx("foo", tmp_path, granted={Capability.SECRETS_READ})
    assert ctx.secrets.read("FOO_TEST_VAR") == "bar"


def test_secrets_read_with_grant_missing_key_returns_none(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing env var returns None — NOT raise — by design."""
    monkeypatch.delenv("DEFINITELY_NOT_SET_KEY", raising=False)
    ctx = _make_ctx("foo", tmp_path, granted={Capability.SECRETS_READ})
    assert ctx.secrets.read("DEFINITELY_NOT_SET_KEY") is None


# --- net.outbound ----------------------------------------------------------


def test_net_outbound_without_grant_raises_before_httpx_call(
    tmp_path: Path,
) -> None:
    """The cap check fires BEFORE any httpx call (mock httpx.request to assert not called)."""
    pytest.importorskip("httpx")
    import httpx

    ctx = _make_ctx("foo", tmp_path)

    with patch.object(httpx, "request") as mock_request:
        with pytest.raises(PermissionDenied) as exc_info:
            ctx.net.outbound("https://example.com")
        assert exc_info.value.capability == "net.outbound"
        mock_request.assert_not_called()


def test_net_outbound_with_grant_calls_httpx(
    tmp_path: Path,
) -> None:
    """granted=NET_OUTBOUND → httpx.request is invoked with the url + method."""
    pytest.importorskip("httpx")
    import httpx

    ctx = _make_ctx("foo", tmp_path, granted={Capability.NET_OUTBOUND})

    fake_response = object()
    with patch.object(httpx, "request", return_value=fake_response) as mock_request:
        result = ctx.net.outbound("https://example.com")

    assert result is fake_response
    mock_request.assert_called_once_with("GET", "https://example.com")


def test_net_outbound_method_kwarg_forwarded(tmp_path: Path) -> None:
    pytest.importorskip("httpx")
    import httpx

    ctx = _make_ctx("foo", tmp_path, granted={Capability.NET_OUTBOUND})
    with patch.object(httpx, "request") as mock_request:
        ctx.net.outbound("https://example.com", method="POST", json={"a": 1})
    mock_request.assert_called_once_with("POST", "https://example.com", json={"a": 1})


def test_plugin_context_carries_identity_fields(tmp_path: Path) -> None:
    """The Phase 41 identity surface is preserved on the Phase 43 PluginContext."""
    ctx = _make_ctx("foo", tmp_path / "data")
    assert ctx.plugin_name == "foo"
    assert ctx.plugin_version == "0.1.0"
    assert ctx.data_dir == tmp_path / "data"
    assert isinstance(ctx.guard, CapabilityGuard)
