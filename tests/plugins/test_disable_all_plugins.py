"""ISOLATE-03 escape hatch: HORUS_OS_DISABLE_PLUGINS env var + --disable-all-plugins CLI flag.

The env var short-circuits ``discover_plugins()`` entirely; the
PluginRegistry stays empty no matter what is installed in the test
venv. The CLI flag sets the env var BEFORE ``create_app()`` runs.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture
def isolated_data_dir(tmp_path: Path) -> Path:
    from horus_os.storage import Database

    data_dir = tmp_path / "horus_data"
    data_dir.mkdir()
    Database(data_dir / "horus.sqlite").init()
    return data_dir


def test_env_var_skips_discover(
    monkeypatch: pytest.MonkeyPatch,
    isolated_data_dir: Path,
) -> None:
    """HORUS_OS_DISABLE_PLUGINS=true → discover_plugins NOT called; registry empty."""
    pytest.importorskip("fastapi")

    monkeypatch.setenv("HORUS_OS_DISABLE_PLUGINS", "true")

    call_count = {"n": 0}

    def _explode_discover() -> tuple[list[object], list[object]]:
        call_count["n"] += 1
        raise AssertionError("discover_plugins must NOT be called when disabled")

    monkeypatch.setattr(
        "horus_os.server.api.discover_plugins",
        _explode_discover,
    )

    from horus_os.server.api import create_app

    app = create_app(data_dir=isolated_data_dir)
    assert app.state.plugin_registry.all() == []
    assert call_count["n"] == 0


def test_env_var_false_does_discover(
    monkeypatch: pytest.MonkeyPatch,
    isolated_data_dir: Path,
) -> None:
    """HORUS_OS_DISABLE_PLUGINS=false → discover_plugins IS called."""
    pytest.importorskip("fastapi")

    monkeypatch.setenv("HORUS_OS_DISABLE_PLUGINS", "false")

    call_count = {"n": 0}

    def _counting_discover() -> tuple[list[object], list[object]]:
        call_count["n"] += 1
        return [], []

    monkeypatch.setattr(
        "horus_os.server.api.discover_plugins",
        _counting_discover,
    )

    from horus_os.server.api import create_app

    create_app(data_dir=isolated_data_dir)
    assert call_count["n"] == 1


def test_env_var_unset_does_discover(
    monkeypatch: pytest.MonkeyPatch,
    isolated_data_dir: Path,
) -> None:
    """Default (env var unset) → discover_plugins called normally."""
    pytest.importorskip("fastapi")

    monkeypatch.delenv("HORUS_OS_DISABLE_PLUGINS", raising=False)

    call_count = {"n": 0}

    def _counting_discover() -> tuple[list[object], list[object]]:
        call_count["n"] += 1
        return [], []

    monkeypatch.setattr(
        "horus_os.server.api.discover_plugins",
        _counting_discover,
    )

    from horus_os.server.api import create_app

    create_app(data_dir=isolated_data_dir)
    assert call_count["n"] == 1


def test_cli_flag_sets_env_var(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """`horus-os serve --disable-all-plugins` sets HORUS_OS_DISABLE_PLUGINS=true.

    Stubs ``uvicorn.run`` and ``create_app`` so the test does not
    actually serve; captures the env var snapshot at create_app call
    time to prove the CLI flag wired through BEFORE create_app ran.
    """
    # Snapshot the env var so monkeypatch can restore it after the
    # test (the CLI itself mutates os.environ directly, NOT through
    # monkeypatch, so we have to pre-bind monkeypatch to the key for
    # auto-cleanup).
    monkeypatch.delenv("HORUS_OS_DISABLE_PLUGINS", raising=False)

    captured_env: dict[str, str] = {}

    def _fake_create_app(*, data_dir: object) -> object:
        captured_env["HORUS_OS_DISABLE_PLUGINS"] = os.environ.get(
            "HORUS_OS_DISABLE_PLUGINS",
            "<unset>",
        )

        class _StubApp:
            pass

        return _StubApp()

    import uvicorn

    monkeypatch.setattr(uvicorn, "run", lambda *a, **kw: None)
    monkeypatch.setattr(
        "horus_os.server.create_app",
        _fake_create_app,
    )

    from horus_os.__main__ import build_parser
    from horus_os.cli.serve_cmd import run_serve

    parser = build_parser()
    args = parser.parse_args(["serve", "--disable-all-plugins"])
    assert args.disable_all_plugins is True

    import io

    try:
        rc = run_serve(args, stdout=io.StringIO(), stderr=io.StringIO())
        assert rc == 0
        assert captured_env["HORUS_OS_DISABLE_PLUGINS"] == "true"
    finally:
        # The CLI body sets os.environ directly (NOT through
        # monkeypatch); clean up by hand so subsequent tests do not
        # inherit the env state. monkeypatch.setenv/delenv would auto-
        # restore but only for keys monkeypatch knows about.
        os.environ.pop("HORUS_OS_DISABLE_PLUGINS", None)


def test_cli_no_flag_does_not_set_env_var(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Without the flag, the env var stays untouched."""
    monkeypatch.delenv("HORUS_OS_DISABLE_PLUGINS", raising=False)

    captured: dict[str, str] = {}

    def _fake_create_app(*, data_dir: object) -> object:
        captured["env"] = os.environ.get("HORUS_OS_DISABLE_PLUGINS", "<unset>")

        class _StubApp:
            pass

        return _StubApp()

    import uvicorn

    monkeypatch.setattr(uvicorn, "run", lambda *a, **kw: None)
    monkeypatch.setattr("horus_os.server.create_app", _fake_create_app)

    from horus_os.__main__ import build_parser
    from horus_os.cli.serve_cmd import run_serve

    parser = build_parser()
    args = parser.parse_args(["serve"])
    assert args.disable_all_plugins is False

    import io

    run_serve(args, stdout=io.StringIO(), stderr=io.StringIO())
    assert captured["env"] == "<unset>"


def test_parser_recognises_disable_all_plugins_flag() -> None:
    """The serve subparser carries a `--disable-all-plugins` arg."""
    from horus_os.__main__ import build_parser

    parser = build_parser()
    ns = parser.parse_args(["serve", "--disable-all-plugins"])
    assert ns.disable_all_plugins is True
    ns2 = parser.parse_args(["serve"])
    assert ns2.disable_all_plugins is False
