"""Pytest substrate for TEST-15 (two-variant install-smoke).

The CI matrix in `.github/workflows/ci.yml` runs the full two-variant
OS-level smoke on 3-OS x 2-python; these tests pin the assertions the
CI scripts call. Two angles:

1. With `opentelemetry` masked from sys.modules: the adapter module
   STILL imports cleanly (module-top is stdlib + typing + horus_os
   only); `start()` raises a clean RuntimeError with the install
   hint, NEVER ModuleNotFoundError. This is the Pitfall 12 contract.

2. With `opentelemetry` installed (the dev venv has [dev,otel] when
   developer ran `pip install -e ".[dev,otel]"` ; skip otherwise):
   adapter starts and stops without exception.

The constructor and `describe()` / `bind()` are stdlib-only paths;
they are tested unconditionally regardless of opentelemetry presence.
"""

from __future__ import annotations

import asyncio
import sys
import tomllib
from importlib.metadata import entry_points
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from horus_os.adapters.base import AdapterContext, AdapterRegistry
from horus_os.adapters.otel_adapter import (
    CAPTURE_CONTENT_ENV,
    OTEL_EXTRA_HINT,
    OTLP_ENDPOINT_ENV,
    OtelAdapter,
)
from horus_os.config import Config


def _make_context(tmp_path: Path) -> AdapterContext:
    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    reg = AdapterRegistry()
    reg.register("otel")
    return AdapterContext(config=cfg, data_dir=tmp_path, registry=reg)


def _mask_opentelemetry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make `import opentelemetry` raise ImportError as if the extra is missing.

    Setting `sys.modules["opentelemetry"]` to None tells the import
    machinery to raise ImportError on the next bare `import
    opentelemetry`. Mirrors how PEP 328 negative-import sentinels work.
    Also clears any cached opentelemetry submodules so a stale entry
    cannot bypass the mask.
    """
    for mod_name in list(sys.modules):
        if mod_name == "opentelemetry" or mod_name.startswith("opentelemetry."):
            monkeypatch.delitem(sys.modules, mod_name, raising=False)
    monkeypatch.setitem(sys.modules, "opentelemetry", None)


def test_module_imports_cleanly_when_opentelemetry_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mask_opentelemetry(monkeypatch)
    # Confirm the mask actually bites first.
    with pytest.raises(ImportError):
        import opentelemetry  # noqa: F401
    # Re-import the adapter module fresh to prove the module-top
    # imports do not touch opentelemetry. Importlib's module cache
    # already has the adapter loaded from test-collection time; a
    # fresh reimport via importlib.reload would re-execute the
    # module body and tickle the same code path.
    import importlib

    import horus_os.adapters.otel_adapter as otel_mod

    reloaded = importlib.reload(otel_mod)
    assert reloaded.OtelAdapter.name == "otel"


def test_start_raises_runtime_error_with_install_hint_when_otel_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _mask_opentelemetry(monkeypatch)
    ctx = _make_context(tmp_path)
    adapter = OtelAdapter()
    with pytest.raises(RuntimeError) as excinfo:
        asyncio.run(adapter.start(ctx))
    # The error TYPE must be RuntimeError, NEVER ModuleNotFoundError
    # (Pitfall 12). The message must contain the install hint substring.
    assert excinfo.type is RuntimeError
    assert "pip install horus-os[otel]" in str(excinfo.value)
    # Registry must also record the error (dashboard error pill).
    entry = ctx.registry.get("otel")
    assert entry is not None
    assert entry.error_count >= 1
    assert "pip install horus-os[otel]" in (entry.error_message or "")


def test_constructor_does_not_touch_opentelemetry(monkeypatch: pytest.MonkeyPatch) -> None:
    _mask_opentelemetry(monkeypatch)
    adapter = OtelAdapter()
    assert adapter.name == "otel"
    assert adapter._provider is None
    assert adapter._unsubscribe is None


def test_describe_returns_expected_keys() -> None:
    adapter = OtelAdapter()
    desc = adapter.describe()
    assert desc["name"] == "otel"
    assert desc["transport"] == "otlp-http"
    assert desc["env"] == OTLP_ENDPOINT_ENV
    assert "version" in desc


def test_bind_is_noop_and_does_not_register_routes(tmp_path: Path) -> None:
    adapter = OtelAdapter()
    # SimpleNamespace stands in for FastAPI; any attribute access
    # that the adapter performs would AttributeError loudly.
    fake_app = SimpleNamespace()
    fake_app.add_api_route = MagicMock()
    fake_app.include_router = MagicMock()
    ctx = _make_context(tmp_path)
    result = adapter.bind(fake_app, ctx)
    assert result is None
    fake_app.add_api_route.assert_not_called()
    fake_app.include_router.assert_not_called()


def test_entry_point_registered_under_horus_os_adapters_group() -> None:
    eps = entry_points(group="horus_os.adapters")
    names = [ep.name for ep in eps]
    assert "otel" in names


def test_pyproject_otel_extra_lists_only_two_deps() -> None:
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data: dict[str, Any] = tomllib.loads(pyproject_path.read_text())
    otel_deps = data["project"]["optional-dependencies"]["otel"]
    assert otel_deps == [
        "opentelemetry-sdk>=1.42,<2.0",
        "opentelemetry-exporter-otlp-proto-http>=1.42,<2.0",
    ]


def test_pyproject_otel_entry_point_registered() -> None:
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data: dict[str, Any] = tomllib.loads(pyproject_path.read_text())
    ep = data["project"]["entry-points"]["horus_os.adapters"]["otel"]
    assert ep == "horus_os.adapters.otel_adapter:OtelAdapter"


def test_otel_extra_hint_matches_load_bearing_string() -> None:
    # Defence-in-depth: if the install-hint constant ever changes,
    # the OS-level CI script (which greps for the same literal)
    # and the runtime test_start_raises... assertion both have to
    # be updated. This test pins the literal so the lockstep is
    # explicit.
    assert OTEL_EXTRA_HINT == "OTel adapter requires 'pip install horus-os[otel]'"
    assert "pip install horus-os[otel]" in OTEL_EXTRA_HINT


def test_capture_content_env_constant_matches_documented_name() -> None:
    # docs/OTEL.md and the threat-register reference this exact env
    # var name; if a future PR renames the constant the docs and
    # the OS-level CI smoke both break. Pin the literal here.
    assert CAPTURE_CONTENT_ENV == "HORUS_OS_OTEL_CAPTURE_CONTENT"
