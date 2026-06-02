"""REL-19 zero-config-start regression.

Three proofs that a bare install of horus-os starts with zero cloud
keys and zero optional extras configured, and that no feature activates
silently on install:

- ``test_starts_with_no_cloud_keys`` builds the FastAPI app and runs
  ``horus-os doctor --mcp`` in a subprocess, both with every cloud
  provider key scrubbed from the environment, and asserts a clean exit
  with no crash.
- ``test_no_v0_8_extra_imports_on_bare_path`` asserts that importing the
  top-level package and building the default ToolRegistry pulls in none
  of the eight v0.8 optional dependencies (the lazy-import contract from
  Phases 69-75; this is the release backstop, T-76-06).
- ``test_default_registry_has_no_dangerous_tools`` asserts the
  default-config registry exposes no shell, web_search, or mcp-prefixed
  tool, proving every integration is opt-in (REL-19).

Env is scrubbed via monkeypatch and a copied subprocess env, never the
real process environment. Paths resolve via pathlib.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

# Cloud-provider keys whose absence must be a clean degraded state, never
# a startup crash (the process-env -> startup trust boundary).
_CLOUD_KEYS = ("ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY")

# The eight v0.8 optional dependencies. None may appear in sys.modules
# after a bare import of horus_os and a default-registry build.
_V0_8_OPTIONAL_DEPS = (
    "openai",  # [local-llm]
    "fastembed",  # [local-memory]
    "onnxruntime",  # [local-memory]
    "sqlite_vec",  # [local-memory]
    "mcp",  # [mcp]
    "readability",  # [web]
    "pypdf",  # [pdf]
    "PIL",  # [vision]
)


def _notes_store(tmp_path: Path):
    """Build a NotesStore rooted at a fresh notes dir under tmp_path."""
    from horus_os.memory import NotesStore

    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()
    return NotesStore(notes_dir)


def test_starts_with_no_cloud_keys(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The core startup surfaces succeed with every cloud key unset."""
    for key in _CLOUD_KEYS:
        monkeypatch.delenv(key, raising=False)

    # In-process: building the FastAPI app must not raise when no cloud
    # key is set. Providers are constructed lazily, only when a run needs
    # them, so app build stays clean.
    from horus_os import create_app

    app = create_app(tmp_path)
    assert app is not None

    # Out-of-process: `horus-os doctor --mcp` must exit 0 with a clean
    # status line under a scrubbed environment. We invoke the module via
    # the test interpreter rather than the console script so the test does
    # not depend on a horus-os entry on PATH.
    env = os.environ.copy()
    for key in _CLOUD_KEYS:
        env.pop(key, None)
    env["PYTHONIOENCODING"] = "utf-8"
    env["HORUS_OS_DATA_DIR"] = str(tmp_path)

    proc = subprocess.run(
        [sys.executable, "-m", "horus_os", "doctor", "--mcp"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert proc.returncode == 0, f"doctor crashed:\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    # The opt-in default is a healthy, no-servers report, not an error.
    assert "no servers configured" in proc.stdout, proc.stdout


def test_no_v0_8_extra_imports_on_bare_path(tmp_path: Path) -> None:
    """Importing horus_os and building the default registry pulls no v0.8 dep.

    Run in a fresh subprocess so the assertion sees only the modules the
    bare path itself imports, independent of any v0.8 dep another test in
    this session may have imported (T-76-06).
    """
    probe = (
        "import sys\n"
        "import horus_os  # noqa: F401\n"
        "from horus_os.config import Config\n"
        "from horus_os.memory import NotesStore\n"
        "from horus_os.server.api import _build_default_registry\n"
        "import pathlib\n"
        f"data_dir = pathlib.Path({str(tmp_path)!r})\n"
        "notes_dir = data_dir / 'notes'\n"
        "notes_dir.mkdir(parents=True, exist_ok=True)\n"
        "cfg = Config.with_defaults(data_dir)\n"
        "_build_default_registry(cfg, NotesStore(notes_dir))\n"
        f"deps = {list(_V0_8_OPTIONAL_DEPS)!r}\n"
        "leaked = [m for m in deps if m in sys.modules]\n"
        "assert not leaked, 'v0.8 optional deps imported on bare path: ' + repr(leaked)\n"
        "print('OK no v0.8 deps imported')\n"
    )
    env = os.environ.copy()
    env["HORUS_OS_DATA_DIR"] = str(tmp_path)

    proc = subprocess.run(
        [sys.executable, "-c", probe],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    assert "OK no v0.8 deps imported" in proc.stdout, proc.stdout


def test_default_registry_has_no_dangerous_tools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The default-config registry exposes no shell, web_search, or mcp tool."""
    for key in _CLOUD_KEYS:
        monkeypatch.delenv(key, raising=False)
    # Ensure the shell env gate is closed for this test even if the host
    # environment happens to set it.
    monkeypatch.delenv("HORUS_OS_SHELL_ENABLED", raising=False)

    from horus_os.config import Config
    from horus_os.server.api import _build_default_registry

    cfg = Config.with_defaults(tmp_path)
    assert cfg.web_search_provider is None
    assert cfg.shell_enabled is False

    registry = _build_default_registry(cfg, _notes_store(tmp_path))
    names = {tool.name for tool in registry.list()}

    assert "shell_exec" not in names, names
    assert "web_search" not in names, names
    assert not any(name.startswith("mcp:") for name in names), names
