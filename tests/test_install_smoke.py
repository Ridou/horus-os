"""Pytest wrapper around the cross-OS install smoke driver.

The dedicated ``install-smoke`` CI job runs ``scripts/install_smoke.py``
once per matrix cell (Ubuntu, macOS, Windows by Python 3.11, 3.12).
This wrapper runs the same script under the regular lint+test pytest
matrix so the smoke logic is exercised on every push, not only on the
dedicated job. The wrapper drives the script with ``HORUS_OS_SMOKE_DATA_DIR``
pointed at ``tmp_path`` so each pytest run is isolated.

The wrapper skips when the ``horus-os`` console script is not on PATH,
which is the case when running pytest from a non-installed checkout.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "install_smoke.py"
_PYPROJECT_PATH = Path(__file__).resolve().parents[1] / "pyproject.toml"
_README_PATH = Path(__file__).resolve().parents[1] / "README.md"


def test_install_smoke_runs(tmp_path: Path) -> None:
    """Run install_smoke.py under sys.executable; assert exit 0 and final marker."""
    if shutil.which("horus-os") is None:
        pytest.skip("horus-os console script not on PATH; skipping install-smoke wrapper")
    if not _SCRIPT_PATH.is_file():
        pytest.skip(f"install_smoke script not found at {_SCRIPT_PATH}")

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["HORUS_OS_SMOKE_DATA_DIR"] = str(tmp_path)
    env["ANTHROPIC_API_KEY"] = ""
    env["GEMINI_API_KEY"] = ""
    env["GOOGLE_API_KEY"] = ""

    proc = subprocess.run(
        [sys.executable, str(_SCRIPT_PATH)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    if proc.returncode != 0:
        # Surface full output so a CI failure is debuggable from the log alone.
        pytest.fail(
            "install_smoke.py exited "
            f"{proc.returncode}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )

    assert "All install-smoke checks passed." in proc.stdout, proc.stdout
    # Schema-on-disk check ran.
    assert "schema_version==13" in proc.stdout, proc.stdout
    # agents CRUD round-trip ran.
    assert "agents create smoke_test" in proc.stdout, proc.stdout
    assert "agents delete smoke_test" in proc.stdout, proc.stdout
    # Public-surface import smoke ran.
    assert "public surface imports and discover_adapters()" in proc.stdout, proc.stdout
    # v0.3 surface markers (Phase 30): per-module adapter imports and
    # the TestClient pass against /api/adapters + the toggle 404 path.
    assert "per-module adapter imports (lazy SDK pattern)" in proc.stdout, proc.stdout
    assert "GET /api/adapters shape + toggle 404 path" in proc.stdout, proc.stdout
    # Phase 67 (GH-02): the optional github_read tool imports and builds with
    # the [github] extra absent (CI installs '.[all]', which excludes it).
    assert "GITHUB_TOOL_IMPORT_OK" in proc.stdout, proc.stdout


def test_vercel_and_github_extras_excluded_from_all() -> None:
    """TEST-31 / D-09 (also Phase 68 criterion 2): the [vercel] and [github]
    optional extras exist, and neither they nor any dependency unique to them
    leak into the [all] extra. discord and supabase are the existing precedent
    for extras deliberately kept out of [all]; the durable invariant is that
    pip install 'horus-os[all]' installs neither the vercel nor the github
    dependency."""
    data: dict[str, Any] = tomllib.loads(_PYPROJECT_PATH.read_text())
    opt = data["project"]["optional-dependencies"]

    # Both extras must be declared.
    assert "vercel" in opt, sorted(opt)
    assert "github" in opt, sorted(opt)

    # Neither extra name appears as a key inside the [all] aggregate (the
    # [all] list holds dependency strings, not extra names, so this also
    # guards against a future refactor that nests extras by name).
    all_deps = set(opt["all"])
    assert "vercel" not in all_deps
    assert "github" not in all_deps

    # No dependency unique to vercel/github leaks into [all]. Today both
    # extras pin httpx>=0.27 (the supabase precedent), which is itself NOT
    # in [all]; assert that holds so a leak surfaces immediately.
    leaked = (set(opt["vercel"]) | set(opt["github"])) & all_deps
    assert leaked == set(), f"vercel/github deps leaked into [all]: {sorted(leaked)}"
    assert "httpx>=0.27" not in all_deps


def test_supabase_and_discord_extras_excluded_from_all() -> None:
    """D-03 / REL-16 criterion 2 / REL-17 (Phase 68): the supabase and discord
    optional extras exist, and no dependency unique to them leaks into [all].
    This extends test_vercel_and_github_extras_excluded_from_all so all four
    opt-in extras (discord, supabase, vercel, github) are pinned out of [all]
    in one test. pip install 'horus-os[all]' must install neither discord.py
    nor the supabase httpx pin."""
    data: dict[str, Any] = tomllib.loads(_PYPROJECT_PATH.read_text())
    opt = data["project"]["optional-dependencies"]

    # Both extras must be declared.
    assert "supabase" in opt, sorted(opt)
    assert "discord" in opt, sorted(opt)

    # Neither extra name appears as a dependency string inside [all].
    all_deps = set(opt["all"])
    assert "supabase" not in all_deps
    assert "discord" not in all_deps

    # No dependency unique to supabase/discord leaks into [all]. supabase pins
    # httpx>=0.27 and discord pins discord.py>=2.4; assert both are absent so a
    # future refactor that folds either extra into [all] fails immediately.
    leaked = (set(opt["supabase"]) | set(opt["discord"])) & all_deps
    assert leaked == set(), f"supabase/discord deps leaked into [all]: {sorted(leaked)}"
    assert "discord.py>=2.4" not in all_deps
    assert "httpx>=0.27" not in all_deps


def test_readme_documents_opt_in_extras_and_all_exclusion() -> None:
    """D-02 / REL-16 criterion 2 / REL-17 (Phase 68): README documents the
    opt-in extras by their bracketed names and states that [all] excludes the
    four opt-in integrations. This pins the prose to the mechanical
    [all]-exclusion invariant: if the README section is dropped or the
    exclusion statement removed, this test fails."""
    readme_text = _README_PATH.read_text()

    # The opt-in extras are documented by bracketed name.
    assert "[supabase]" in readme_text
    assert "[vercel]" in readme_text

    # An exclusion statement naming the opt-in extras is present.
    lowered = readme_text.lower()
    assert "exclud" in lowered, "README must state that [all] excludes some extras"
    exclusion_lines = [line for line in lowered.splitlines() if "exclud" in line]
    assert any(
        all(name in line for name in ("discord", "supabase", "vercel", "github"))
        for line in exclusion_lines
    ), "README exclusion statement must name discord, supabase, vercel, and github"
