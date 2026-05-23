"""Cross-OS install smoke test for horus-os.

This script is invoked from CI after the package has been installed
in a fresh environment with all extras. It exercises every CLI surface
that does not require live API keys and asserts the exit codes plus a
few substrings of the output.

Run locally:

    pip install '.[all]'
    python scripts/install_smoke.py

Exits 0 on success, 1 on failure. Print output on failure so CI logs
show what broke.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CLI = "horus-os"


def run(args: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """Invoke the horus-os CLI and return the completed process."""
    full_env = os.environ.copy()
    full_env["PYTHONIOENCODING"] = "utf-8"
    if env:
        full_env.update(env)
    return subprocess.run(
        [CLI, *args],
        check=False,
        capture_output=True,
        text=True,
        env=full_env,
    )


def expect(
    label: str,
    proc: subprocess.CompletedProcess,
    *,
    code: int,
    in_stdout: list[str] | None = None,
    in_stderr: list[str] | None = None,
) -> None:
    """Assert exit code and substrings; print details and exit 1 on failure."""
    if proc.returncode != code:
        _fail(label, proc, f"expected exit {code}, got {proc.returncode}")
    for needle in in_stdout or []:
        if needle not in proc.stdout:
            _fail(label, proc, f"expected substring {needle!r} not found in stdout")
    for needle in in_stderr or []:
        if needle not in proc.stderr:
            _fail(label, proc, f"expected substring {needle!r} not found in stderr")
    print(f"OK   {label}")


def _fail(label: str, proc: subprocess.CompletedProcess, reason: str) -> None:
    print(f"FAIL {label}: {reason}")
    print(f"  exit:   {proc.returncode}")
    print(f"  stdout: {proc.stdout!r}")
    print(f"  stderr: {proc.stderr!r}")
    sys.exit(1)


def main() -> int:
    if shutil.which(CLI) is None:
        print(f"FAIL: {CLI} is not on PATH. Did `pip install` succeed?")
        return 1

    tmp_dir = Path(tempfile.mkdtemp(prefix="horus-os-smoke-"))
    try:
        # 1. --version prints the package version
        expect(
            "--version",
            run(["--version"]),
            code=0,
            in_stdout=["horus-os"],
        )

        # 2. --help lists every subcommand
        expect(
            "--help lists subcommands",
            run(["--help"]),
            code=0,
            in_stdout=["init", "traces", "serve", "run"],
        )

        # 3. init creates the expected files in a fresh data dir
        proc = run(["init", "--data-dir", str(tmp_dir)])
        expect("init fresh", proc, code=0, in_stdout=["Initialized horus-os"])
        assert (tmp_dir / "config.toml").exists(), "config.toml missing"
        assert (tmp_dir / "horus.sqlite").exists(), "horus.sqlite missing"
        assert (tmp_dir / "notes").is_dir(), "notes/ missing"

        # 4. init is idempotent without --force
        expect(
            "init refuses overwrite without --force",
            run(["init", "--data-dir", str(tmp_dir)]),
            code=1,
            in_stderr=["already initialized"],
        )

        # 5. init --force succeeds
        expect(
            "init --force",
            run(["init", "--data-dir", str(tmp_dir), "--force"]),
            code=0,
            in_stdout=["Reinitialized"],
        )

        # 6. traces on an empty database prints the empty marker
        expect(
            "traces empty",
            run(["traces", "--data-dir", str(tmp_dir)]),
            code=0,
            in_stdout=["(no traces yet)"],
        )

        # 7. run without an API key fails cleanly
        env_no_keys = {
            "ANTHROPIC_API_KEY": "",
            "GEMINI_API_KEY": "",
            "GOOGLE_API_KEY": "",
        }
        expect(
            "run without API key",
            run(["run", "hello", "--data-dir", str(tmp_dir)], env=env_no_keys),
            code=2,
            in_stderr=["ANTHROPIC_API_KEY"],
        )

        # 8. serve --help works without starting the server
        expect(
            "serve --help",
            run(["serve", "--help"]),
            code=0,
            in_stdout=["--host", "--port"],
        )

        print("\nAll install-smoke checks passed.")
        return 0
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
