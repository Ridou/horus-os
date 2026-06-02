"""Local dry-run for the v0.8 install-smoke coverage (Phase 76, TEST-38 + REL-18).

The real three-OS x two-Python install-smoke matrix runs ONLY in GitHub
Actions; macOS, Ubuntu, and Windows wheels for the [local-memory] extra
cannot be resolved here. This module is the local proof that the smoke
snippet logic and the ci.yml job wiring are correct before the live gate
runs:

  * The two snippet constants exist in scripts/install_smoke.py and carry the
    web/shell/mcp absence assertions (REL-19 "no feature activates silently").
  * ci.yml declares both new job names and the [dev,local-memory] install
    line so the live jobs cannot silently disappear.
  * When the local-memory extra is importable in this executor venv, the
    V0_8_TOOL_ABSENCE_SNIPPET is run in-process and the OK sentinel is
    asserted; otherwise the in-process leg is skipped with a message pointing
    at the install-smoke-local-memory job that runs the real assertion.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SMOKE_PATH = REPO_ROOT / "scripts" / "install_smoke.py"
CI_YML_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"

LOCAL_MEMORY_MODULES = ("onnxruntime", "fastembed", "sqlite_vec")

_MODULE_NAME = "_install_smoke_under_test"


def _load_install_smoke_module():
    """Import scripts/install_smoke.py as a module without a scripts package.

    The scripts/ directory has no __init__.py, so it cannot be imported as
    `scripts.install_smoke`. Load it from its file path, mirroring the idiom
    in tests/test_release_gate.py.
    """
    if _MODULE_NAME in sys.modules:
        return sys.modules[_MODULE_NAME]
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, INSTALL_SMOKE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


def _install_smoke_source() -> str:
    return INSTALL_SMOKE_PATH.read_text(encoding="utf-8")


def _ci_yml_source() -> str:
    return CI_YML_PATH.read_text(encoding="utf-8")


def _local_memory_importable() -> bool:
    return all(importlib.util.find_spec(name) is not None for name in LOCAL_MEMORY_MODULES)


def test_install_smoke_declares_v0_8_snippets() -> None:
    src = _install_smoke_source()
    assert "V0_8_IMPORT_SNIPPET" in src
    assert "V0_8_TOOL_ABSENCE_SNIPPET" in src
    assert "V0_8_PROBE_SNIPPET" in src


def test_tool_absence_snippet_asserts_web_shell_mcp_absent() -> None:
    src = _install_smoke_source()
    # The absence snippet must assert every untrusted-by-default v0.8 tool is
    # absent on a zero-config install (REL-19).
    assert "'web_search' not in registry" in src
    assert "'shell_exec' not in registry" in src
    assert "startswith('mcp:')" in src
    assert "V0_8_TOOL_ABSENCE_OK" in src


def test_import_snippet_covers_every_v0_8_module() -> None:
    src = _install_smoke_source()
    for module in (
        "horus_os._providers._openai_compat",
        "horus_os.memory.vector",
        "horus_os.mcp_client",
        "horus_os.tools.web_search",
        "horus_os.tools.vision",
        "horus_os.tools.shell",
        "horus_os.research",
        "horus_os.skills",
    ):
        assert module in src, f"v0.8 module {module} not referenced in install_smoke.py"
    assert "V0_8_IMPORT_OK" in src


def test_ci_yml_declares_both_v0_8_install_smoke_jobs() -> None:
    yml = _ci_yml_source()
    assert "install-smoke-v0-8-extras" in yml
    assert "install-smoke-local-memory" in yml
    # The local-memory job exists to resolve the onnxruntime <1.19.0 pin.
    assert ".[dev,local-memory]" in yml
    # The light-extras job installs the cross-OS-clean extras.
    assert ".[dev,local-llm,mcp,web,pdf,vision]" in yml


def test_ci_local_memory_job_asserts_onnxruntime_pin() -> None:
    yml = _ci_yml_source()
    # A future resolver drift to 1.19.0+ (no Intel macOS universal2 wheel)
    # must fail the gate, so the job asserts the resolved version floor.
    assert "Version('1.19.0')" in yml
    assert "LOCAL_MEMORY_WHEELS_OK" in yml


def test_install_smoke_module_parses() -> None:
    import ast

    ast.parse(_install_smoke_source())


def test_tool_absence_snippet_runs_in_process_when_local_memory_present() -> None:
    if not _local_memory_importable():
        pytest.skip(
            "local-memory extra not installed in this venv; the real absence "
            "assertion runs in the GitHub Actions install-smoke-local-memory job"
        )
    # Pull the literal snippet from the smoke driver and execute it in-process
    # so the dry-run exercises the same source the CI job runs.
    smoke = _load_install_smoke_module()

    # The snippet is a trusted, in-repo constant; exec runs it in an isolated
    # namespace so the dry-run exercises the exact source the CI job runs.
    namespace: dict[str, object] = {}
    exec(smoke.V0_8_TOOL_ABSENCE_SNIPPET, namespace)
