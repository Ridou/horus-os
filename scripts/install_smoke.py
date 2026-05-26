"""Cross-OS install smoke test for horus-os.

This script is invoked from CI after the package has been installed
in a fresh environment with all extras. It exercises every CLI surface
that does not require live API keys and asserts the exit codes plus a
few substrings of the output.

Phase 10 added the v0.1 checks. Phase 20 extended the script with the
v0.2 surface: agents subcommand CRUD, on-disk schema v4, the buffered
run path with a profile, public-surface imports, and the adapter
discovery hook. Phase 30 extends it again with the v0.3 surface:
LifecycleAdapter + AdapterRegistry + AdapterEntry imports, the four
bundled adapter classes (Discord, Slack, Email, Calendar), each
adapter module's lazy-import path, and a TestClient pass against
GET /api/adapters plus the toggle 404 path. All checks run offline;
CI has no API keys or adapter tokens.

Run locally:

    pip install '.[all]'
    python scripts/install_smoke.py

Exits 0 on success, 1 on failure. Print output on failure so CI logs
show what broke.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

CLI = "horus-os"

SCHEMA_VERSION_EXPECTED = 6
DEFAULT_PROFILE_NAME = "default"

PUBLIC_SURFACE_IMPORT_SNIPPET = (
    "from horus_os import ("
    "Adapter, AdapterContext, AdapterEntry, AdapterRegistry, "
    "LifecycleAdapter, ToolCallEvent, "
    "discover_adapters, run_agent_stream"
    ")\n"
    "from horus_os.adapters import ("
    "CalendarAdapter, DiscordAdapter, EmailAdapter, "
    "SlackAdapter, WebhookAdapter"
    ")\n"
    "adapters = discover_adapters()\n"
    "assert isinstance(adapters, list), repr(adapters)\n"
    "assert len(adapters) >= 1, 'discover_adapters returned no entries'\n"
    "print('IMPORT_OK count=' + str(len(adapters)))\n"
)

# Phase 30: each of the four bundled adapter modules uses a lazy SDK
# import so the module imports cleanly even when its optional extra
# is not installed. CI installs `.[all]` so SDKs are present, but the
# direct-module smoke catches a regression where a top-level
# `import discord` (or sibling) slips in.
PER_MODULE_IMPORT_SNIPPET = (
    "from horus_os.adapters.discord_adapter import DiscordAdapter\n"
    "from horus_os.adapters.slack_adapter import SlackAdapter\n"
    "from horus_os.adapters.email_adapter import EmailAdapter\n"
    "from horus_os.adapters.calendar_adapter import CalendarAdapter\n"
    "from horus_os.adapters.webhook import WebhookAdapter\n"
    "assert DiscordAdapter.__name__ == 'DiscordAdapter'\n"
    "assert SlackAdapter.__name__ == 'SlackAdapter'\n"
    "assert EmailAdapter.__name__ == 'EmailAdapter'\n"
    "assert CalendarAdapter.__name__ == 'CalendarAdapter'\n"
    "assert WebhookAdapter.__name__ == 'WebhookAdapter'\n"
    "print('PER_MODULE_IMPORT_OK')\n"
)

# Phase 30: TestClient pass against create_app(tmp). The smoke driver
# stays hermetic by running this in a subprocess so FastAPI is loaded
# in the child only. The data dir is passed as argv[1] so the snippet
# reuses the smoke driver's tmp_dir (which already has a database).
# Each adapter entry must carry the six Phase 27 keys. The toggle
# route 404 path confirms the route is mounted end-to-end without
# requiring real lifecycle hooks (which would need real tokens).
API_TESTCLIENT_SNIPPET = (
    "import sys\n"
    "from fastapi.testclient import TestClient\n"
    "from horus_os.server import create_app\n"
    "data_dir = sys.argv[1]\n"
    "required_keys = {\n"
    "    'name', 'status', 'last_activity_at',\n"
    "    'error_count', 'error_message', 'supports_toggle',\n"
    "}\n"
    "with TestClient(create_app(data_dir=data_dir)) as client:\n"
    "    resp = client.get('/api/adapters')\n"
    "    assert resp.status_code == 200, (resp.status_code, resp.text)\n"
    "    body = resp.json()\n"
    "    assert 'adapters' in body, body\n"
    "    entries = body['adapters']\n"
    "    assert isinstance(entries, list), repr(entries)\n"
    "    for entry in entries:\n"
    "        missing = required_keys - set(entry.keys())\n"
    "        assert not missing, (missing, entry)\n"
    "    bogus = client.post('/api/adapters/does_not_exist_xyz/disable')\n"
    "    assert bogus.status_code == 404, (bogus.status_code, bogus.text)\n"
    "print('API_TESTCLIENT_OK adapters=' + str(len(entries)))\n"
)


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


def run_python(snippet: str, *, extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
    """Invoke `python -c <snippet>` in the same env that ran pip install.

    Optional ``extra_args`` are appended after the snippet so the child
    sees them as ``sys.argv[1:]``. Useful for handing the smoke tmp_dir
    to a TestClient snippet without baking the path into the source.
    """
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    argv = [sys.executable, "-c", snippet]
    if extra_args:
        argv.extend(extra_args)
    return subprocess.run(
        argv,
        check=False,
        capture_output=True,
        text=True,
        env=env,
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


def _fail_simple(label: str, reason: str) -> None:
    print(f"FAIL {label}: {reason}")
    sys.exit(1)


def _read_schema_version(db_path: Path) -> int:
    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
    if row is None:
        _fail_simple("schema_version row", "schema_version table is empty")
    return int(row[0])


def _table_columns(db_path: Path, table: str) -> list[str]:
    with sqlite3.connect(str(db_path)) as conn:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return [r[1] for r in rows]


def _agent_profile_rows(db_path: Path) -> list[str]:
    with sqlite3.connect(str(db_path)) as conn:
        rows = conn.execute("SELECT name FROM agent_profiles ORDER BY name").fetchall()
    return [r[0] for r in rows]


def main() -> int:
    if shutil.which(CLI) is None:
        print(f"FAIL: {CLI} is not on PATH. Did `pip install` succeed?")
        return 1

    smoke_dir_env = os.environ.get("HORUS_OS_SMOKE_DATA_DIR")
    if smoke_dir_env:
        tmp_dir = Path(smoke_dir_env)
        tmp_dir.mkdir(parents=True, exist_ok=True)
        owns_tmp = False
    else:
        tmp_dir = Path(tempfile.mkdtemp(prefix="horus-os-smoke-"))
        owns_tmp = True
    try:
        # ------------------------------------------------------------------
        # v0.1 surface (kept verbatim from Phase 10).
        # ------------------------------------------------------------------

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
            in_stdout=["init", "traces", "serve", "run", "agents"],
        )

        # 3. init creates the expected files in a fresh data dir
        proc = run(["init", "--data-dir", str(tmp_dir)])
        expect("init fresh", proc, code=0, in_stdout=["Initialized horus-os"])
        if not (tmp_dir / "config.toml").exists():
            _fail_simple("init artifacts", "config.toml missing")
        if not (tmp_dir / "horus.sqlite").exists():
            _fail_simple("init artifacts", "horus.sqlite missing")
        if not (tmp_dir / "notes").is_dir():
            _fail_simple("init artifacts", "notes/ missing")

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

        # ------------------------------------------------------------------
        # v0.2 surface (Phase 20).
        # ------------------------------------------------------------------

        # 6. SQLite schema is on version 4 with the multi-agent columns
        db_path = tmp_dir / "horus.sqlite"
        version = _read_schema_version(db_path)
        if version != SCHEMA_VERSION_EXPECTED:
            _fail_simple(
                "schema version",
                f"expected schema_version={SCHEMA_VERSION_EXPECTED}, got {version}",
            )
        print(f"OK   schema_version=={SCHEMA_VERSION_EXPECTED}")

        traces_cols = _table_columns(db_path, "traces")
        for required in ("parent_trace_id", "agent_profile_name"):
            if required not in traces_cols:
                _fail_simple(
                    "traces columns",
                    f"column {required!r} not in traces; have {traces_cols!r}",
                )
        print("OK   traces has parent_trace_id and agent_profile_name")

        profile_names = _agent_profile_rows(db_path)
        if not profile_names:
            _fail_simple("agent_profiles bootstrap", "agent_profiles table is empty")
        if DEFAULT_PROFILE_NAME not in profile_names:
            _fail_simple(
                "default profile bootstrap",
                f"{DEFAULT_PROFILE_NAME!r} missing from {profile_names!r}",
            )
        print(f"OK   agent_profiles bootstrapped ({len(profile_names)} row(s); default present)")

        # 7. `agents list` prints the default profile
        expect(
            "agents list shows default",
            run(["agents", "list", "--data-dir", str(tmp_dir)]),
            code=0,
            in_stdout=["default"],
        )

        # 8. `agents create` + `show` + `delete` round-trip
        expect(
            "agents create smoke_test",
            run(
                [
                    "agents",
                    "create",
                    "--name",
                    "smoke_test",
                    "--system-prompt",
                    "smoke test profile",
                    "--data-dir",
                    str(tmp_dir),
                ]
            ),
            code=0,
            in_stdout=["Created agent profile", "smoke_test"],
        )
        expect(
            "agents show smoke_test",
            run(["agents", "show", "smoke_test", "--data-dir", str(tmp_dir)]),
            code=0,
            in_stdout=["smoke_test", "smoke test profile"],
        )
        expect(
            "agents delete smoke_test",
            run(["agents", "delete", "smoke_test", "--data-dir", str(tmp_dir)]),
            code=0,
            in_stdout=["Deleted agent profile", "smoke_test"],
        )
        # And it is actually gone.
        remaining = _agent_profile_rows(db_path)
        if "smoke_test" in remaining:
            _fail_simple(
                "agents delete persisted",
                f"smoke_test still present after delete: {remaining!r}",
            )
        print("OK   smoke_test removed from agent_profiles")

        # 9. traces on an empty database prints the empty marker
        expect(
            "traces empty",
            run(["traces", "--data-dir", str(tmp_dir)]),
            code=0,
            in_stdout=["(no traces yet)"],
        )

        # 10. run without an API key fails cleanly (streaming default branch)
        env_no_keys = {
            "ANTHROPIC_API_KEY": "",
            "GEMINI_API_KEY": "",
            "GOOGLE_API_KEY": "",
        }
        expect(
            "run without API key (default streaming branch)",
            run(["run", "hello", "--data-dir", str(tmp_dir)], env=env_no_keys),
            code=2,
            in_stderr=["ANTHROPIC_API_KEY"],
        )

        # 11. run --agent default --no-stream without keys still errors cleanly
        expect(
            "run --agent default --no-stream without API key",
            run(
                [
                    "run",
                    "--agent",
                    "default",
                    "--no-stream",
                    "hello",
                    "--data-dir",
                    str(tmp_dir),
                ],
                env=env_no_keys,
            ),
            code=2,
            in_stderr=["ANTHROPIC_API_KEY"],
        )

        # 12. serve --help works without starting the server
        expect(
            "serve --help",
            run(["serve", "--help"]),
            code=0,
            in_stdout=["--host", "--port"],
        )

        # 13. Public-surface imports + discover_adapters() runs
        # Phase 30 extends the snippet to also import LifecycleAdapter,
        # AdapterRegistry, AdapterEntry, and the four bundled adapter
        # classes (Discord, Slack, Email, Calendar, plus WebhookAdapter).
        py = run_python(PUBLIC_SURFACE_IMPORT_SNIPPET)
        expect(
            "public surface imports and discover_adapters()",
            py,
            code=0,
            in_stdout=["IMPORT_OK count="],
        )

        # ------------------------------------------------------------------
        # v0.3 surface (Phase 30).
        # ------------------------------------------------------------------

        # 14. Each bundled adapter module imports directly (lazy SDK pattern)
        per_mod = run_python(PER_MODULE_IMPORT_SNIPPET)
        expect(
            "per-module adapter imports (lazy SDK pattern)",
            per_mod,
            code=0,
            in_stdout=["PER_MODULE_IMPORT_OK"],
        )

        # 15. TestClient pass against create_app: GET /api/adapters shape
        #     + POST /api/adapters/<bogus>/disable -> 404. Runs in a
        #     subprocess so FastAPI loads in the child only and the
        #     smoke driver stays hermetic.
        api = run_python(API_TESTCLIENT_SNIPPET, extra_args=[str(tmp_dir)])
        expect(
            "GET /api/adapters shape + toggle 404 path",
            api,
            code=0,
            in_stdout=["API_TESTCLIENT_OK adapters="],
        )

        print("\nAll install-smoke checks passed.")
        return 0
    finally:
        if owns_tmp:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
