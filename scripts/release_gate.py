"""Pre-tag release-quality gate for horus-os (Phase 39 + Phase 49).

Runs EIGHT checks before the maintainer cuts a tag (4 v0.4 + 4 v0.5):

1. pricing-freshness: src/horus_os/observability/pricing.json
   `updated_at` is within HORUS_OS_PRICING_MAX_AGE_DAYS (default 14)
   of today. Closes Pitfall 5 (pricing rots silently between
   releases).

2. ci-two-variant-smoke: .github/workflows/ci.yml contains BOTH
   `install-smoke-no-otel` and `install-smoke-with-otel` job
   literals. Closes Pitfall 12 (the install matrix could regress to
   one variant and the OTel-extra contract would silently break).

3. wheel-pricing-bundle: `python -m build --wheel` succeeds AND the
   produced wheel contains a `horus_os/observability/pricing.json`
   member. Catches a regression where the
   `[tool.setuptools.package-data]` wiring is removed and the wheel
   ships without the bundled pricing.

4. pytest: `python -m pytest -q` from the repo root exits 0.

5. docs-drift (v0.5): the runtime ``MANIFEST_V1_SCHEMA`` (pydantic
   model in ``src/horus_os/plugins/manifest.py``) dumped via
   ``json.dumps(schema, indent=2, sort_keys=True) + '\\n'`` is
   byte-identical to the committed ``docs/manifest-v1.schema.json``.
   Catches the case where a maintainer edits the runtime model but
   forgets to regenerate the docs file via
   ``scripts/build_manifest_schema.py``.

6. plugin-install-smoke-ci (v0.5): the literal string
   ``install-smoke-plugin`` appears in ``.github/workflows/ci.yml``.
   Asserts the Phase 49 TEST-20 3-OS install-smoke matrix is wired.

7. reference-plugin-manifest-valid (v0.5):
   ``examples/horus-os-example-plugin/horus-plugin.toml`` parses
   cleanly through ``validate_manifest()``. The reference plugin is
   the contract surface plugin authors copy from; if it does not
   validate, the documentation is broken.

8. v0-4-fixture-roundtrip (v0.5):
   ``tests/fixtures/v0_4_database.sqlite3`` survives the v5 -> v6
   migration with the three plugin tables, two plugin_name columns,
   and the ``idx_tool_invocations_plugin`` index present, and a
   second ``init()`` call is idempotent. T-49-01 mitigation: the
   committed fixture is NEVER mutated — the check copies to a
   tempfile and unlinks in a finally block.

Exit semantics: 0 only when all enabled checks pass; 1 when any
check fails. The runner does NOT short-circuit on the first
failure; it prints one diagnostic per failing check so the
maintainer sees the full picture in one pass.

Environment overrides:

- HORUS_OS_PRICING_MAX_AGE_DAYS: pricing freshness threshold in
  days (default 14, the REL-08 contract).
- HORUS_OS_RELEASE_GATE_SKIP_BUILD: skip the slow wheel build.
- HORUS_OS_RELEASE_GATE_SKIP_TESTS: skip the pytest invocation.
- HORUS_OS_PRICING_PATH_OVERRIDE: substitute pricing.json path
  (used by tests/test_release_gate.py to stay hermetic).
- HORUS_OS_CI_YML_PATH_OVERRIDE: substitute ci.yml path (used by
  tests/test_release_gate.py to stay hermetic).
- HORUS_OS_DOCS_SCHEMA_PATH_OVERRIDE: substitute docs schema path
  (v0.5; used by tests/test_release_gate_v0_5_checks.py for
  mutation-driven negative-path coverage).
- HORUS_OS_REFERENCE_PLUGIN_MANIFEST_PATH_OVERRIDE: substitute
  reference plugin manifest path (v0.5).
- HORUS_OS_V0_4_FIXTURE_PATH_OVERRIDE: substitute v0.4 fixture
  path (v0.5).

CLI flags:

- --check {pricing,wheel,ci,tests,docs-drift,plugin-install,
  reference-manifest,fixture-roundtrip}: run only the named check.
- --skip-build: skip the wheel build (alias for
  HORUS_OS_RELEASE_GATE_SKIP_BUILD=1).

STOP-BEFORE-TAG protocol: this script is the LAST automated step
before `git tag -a vN.M.P`. The script itself NEVER tags or pushes
or creates a GitHub Release; those steps are documented in
docs/RELEASE.md `## Release procedure` and are user-confirmation
gates.

Pure stdlib (json, datetime, pathlib, subprocess, sys, os,
argparse, zipfile, tempfile, difflib, shutil, sqlite3, importlib).
The `build` package is invoked via subprocess so this script
imports cleanly without it. The runtime ``horus_os`` package is
lazy-imported only inside the v0.5 check functions that need it,
mirroring the ``scripts/build_manifest_schema.py`` sys.path-insert
idiom so the script runs from a clean checkout without an
editable install.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_PRICING_PATH = REPO_ROOT / "src" / "horus_os" / "observability" / "pricing.json"
DEFAULT_CI_YML_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"

# v0.5 default paths
DEFAULT_DOCS_SCHEMA_PATH = REPO_ROOT / "docs" / "manifest-v1.schema.json"
DEFAULT_REFERENCE_PLUGIN_MANIFEST_PATH = (
    REPO_ROOT / "examples" / "horus-os-example-plugin" / "horus-plugin.toml"
)
DEFAULT_V0_4_FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "v0_4_database.sqlite3"

DEFAULT_MAX_AGE_DAYS = 14

CI_LITERAL_NO_OTEL = "install-smoke-no-otel"
CI_LITERAL_WITH_OTEL = "install-smoke-with-otel"
CI_LITERAL_PLUGIN_INSTALL_SMOKE = "install-smoke-plugin"

PRICING_WHEEL_MEMBER_SUFFIX = "horus_os/observability/pricing.json"


@dataclass(frozen=True)
class CheckResult:
    """One check outcome.

    `ok` is True on pass, False on fail, None on skip.
    `diagnostic` is empty on pass, a one-line failure reason on
    fail, or a skip reason on skip.
    """

    name: str
    ok: bool | None
    diagnostic: str


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "") not in {"", "0", "false", "False"}


def _read_max_age_days() -> int:
    raw = os.environ.get("HORUS_OS_PRICING_MAX_AGE_DAYS")
    if raw is None or raw == "":
        return DEFAULT_MAX_AGE_DAYS
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_MAX_AGE_DAYS


def _ensure_src_on_path() -> None:
    """Lazy sys.path insert mirroring scripts/build_manifest_schema.py:31-37.

    The v0.5 checks lazy-import from ``horus_os.*`` so the script can
    run on a clean checkout without an editable install. We avoid
    inserting at module import time so the v0.4 checks (which never
    touch horus_os) stay byte-identical to the v0.4 ImportTime profile.
    """
    src = REPO_ROOT / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def check_pricing_freshness(
    pricing_path: Path,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
) -> CheckResult:
    """Pass when pricing.json `updated_at` is within `max_age_days` of today."""
    if not pricing_path.exists():
        return CheckResult(
            name="pricing-freshness",
            ok=False,
            diagnostic=f"pricing.json not found at {pricing_path}",
        )
    try:
        payload = json.loads(pricing_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return CheckResult(
            name="pricing-freshness",
            ok=False,
            diagnostic=f"could not read or parse {pricing_path}: {type(exc).__name__}",
        )
    raw = payload.get("updated_at")
    if not isinstance(raw, str):
        return CheckResult(
            name="pricing-freshness",
            ok=False,
            diagnostic=f"pricing.json missing string 'updated_at' field at {pricing_path}",
        )
    try:
        updated_at = date.fromisoformat(raw)
    except ValueError:
        return CheckResult(
            name="pricing-freshness",
            ok=False,
            diagnostic=(f"pricing.json 'updated_at' value {raw!r} failed ISO-8601 date parsing"),
        )
    age_days = (date.today() - updated_at).days
    if age_days > max_age_days:
        return CheckResult(
            name="pricing-freshness",
            ok=False,
            diagnostic=(
                f"pricing.json.updated_at is {age_days} days old "
                f"(max {max_age_days}); refresh per docs/RELEASE.md"
            ),
        )
    return CheckResult(
        name="pricing-freshness",
        ok=True,
        diagnostic=f"pricing.json is {age_days} days old (max {max_age_days})",
    )


def check_ci_two_variant_smoke_present(ci_yml_path: Path) -> CheckResult:
    """Pass when ci.yml literally contains both install-smoke job names."""
    if not ci_yml_path.exists():
        return CheckResult(
            name="ci-two-variant-smoke",
            ok=False,
            diagnostic=f"ci.yml not found at {ci_yml_path}",
        )
    text = ci_yml_path.read_text(encoding="utf-8")
    missing: list[str] = []
    if CI_LITERAL_NO_OTEL not in text:
        missing.append(CI_LITERAL_NO_OTEL)
    if CI_LITERAL_WITH_OTEL not in text:
        missing.append(CI_LITERAL_WITH_OTEL)
    if missing:
        return CheckResult(
            name="ci-two-variant-smoke",
            ok=False,
            diagnostic=(
                f"two-variant install-smoke matrix missing from {ci_yml_path}: "
                f"{', '.join(missing)}; Phase 38 TEST-15 contract violated"
            ),
        )
    return CheckResult(
        name="ci-two-variant-smoke",
        ok=True,
        diagnostic="install-smoke-no-otel and install-smoke-with-otel present",
    )


def check_wheel_pricing_bundle(repo_root: Path) -> CheckResult:
    """Pass when `python -m build --wheel` produces a wheel containing pricing.json."""
    with tempfile.TemporaryDirectory(prefix="horus-os-release-gate-") as tmp:
        out_dir = Path(tmp)
        proc = subprocess.run(
            [sys.executable, "-m", "build", "--wheel", "--outdir", str(out_dir)],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            tail = proc.stderr.strip().splitlines()[-5:]
            return CheckResult(
                name="wheel-pricing-bundle",
                ok=False,
                diagnostic=(
                    f"python -m build failed (exit {proc.returncode}); last stderr: "
                    + " | ".join(tail)
                ),
            )
        wheels = sorted(out_dir.glob("*.whl"))
        if not wheels:
            return CheckResult(
                name="wheel-pricing-bundle",
                ok=False,
                diagnostic=f"python -m build succeeded but produced no .whl in {out_dir}",
            )
        wheel = wheels[-1]
        with zipfile.ZipFile(wheel, "r") as zf:
            members = zf.namelist()
        match_count = sum(1 for m in members if m.endswith(PRICING_WHEEL_MEMBER_SUFFIX))
        if match_count == 0:
            return CheckResult(
                name="wheel-pricing-bundle",
                ok=False,
                diagnostic=(
                    f"built wheel {wheel.name} does not contain "
                    f"horus_os/observability/pricing.json; package-data wiring broken"
                ),
            )
        return CheckResult(
            name="wheel-pricing-bundle",
            ok=True,
            diagnostic=f"{wheel.name} contains pricing.json ({match_count} match)",
        )


def check_pytest_pass(repo_root: Path) -> CheckResult:
    """Pass when `python -m pytest -q` from the repo root exits 0."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode == 0:
        last = (proc.stdout.strip().splitlines() or ["(no output)"])[-1]
        return CheckResult(
            name="pytest",
            ok=True,
            diagnostic=last,
        )
    tail_lines = proc.stdout.strip().splitlines()[-20:]
    return CheckResult(
        name="pytest",
        ok=False,
        diagnostic=(
            f"pytest exited {proc.returncode}; last 20 stdout lines: " + " | ".join(tail_lines)
        ),
    )


# ----------------------------------------------------------------------
# v0.5 checks (Phase 49, REL-11)
# ----------------------------------------------------------------------


def check_docs_manifest_schema_drift(
    schema_path: Path,
    *,
    runtime_schema_factory=None,
) -> CheckResult:
    """Pass when docs/manifest-v1.schema.json matches MANIFEST_V1_SCHEMA.

    The runtime pydantic schema is dumped via
    ``json.dumps(schema, indent=2, sort_keys=True) + '\\n'`` —
    byte-identical to the serializer in
    ``scripts/build_manifest_schema.py:44`` so a maintainer running the
    build script to fix drift produces a file the gate accepts.

    The optional ``runtime_schema_factory`` kw lets tests inject a mock
    runtime schema dict; production callers always pass it as None and
    we lazy-import the real ``MANIFEST_V1_SCHEMA`` via the same
    sys.path-insert idiom ``build_manifest_schema.py`` uses.
    """
    if not schema_path.exists():
        return CheckResult(
            name="docs-drift",
            ok=False,
            diagnostic=f"docs/manifest-v1.schema.json not found at {schema_path}",
        )
    try:
        if runtime_schema_factory is not None:
            schema = runtime_schema_factory()
        else:
            _ensure_src_on_path()
            from horus_os.plugins.manifest import (
                MANIFEST_V1_SCHEMA,
            )

            schema = MANIFEST_V1_SCHEMA.model_json_schema()
    except Exception as exc:
        return CheckResult(
            name="docs-drift",
            ok=False,
            diagnostic=(f"could not load runtime MANIFEST_V1_SCHEMA: {type(exc).__name__}: {exc}"),
        )
    runtime_text = json.dumps(schema, indent=2, sort_keys=True) + "\n"
    try:
        committed_text = schema_path.read_text(encoding="utf-8")
    except OSError as exc:
        return CheckResult(
            name="docs-drift",
            ok=False,
            diagnostic=f"could not read {schema_path}: {type(exc).__name__}: {exc}",
        )
    if committed_text == runtime_text:
        return CheckResult(
            name="docs-drift",
            ok=True,
            diagnostic=(
                f"docs schema matches runtime MANIFEST_V1_SCHEMA ({len(runtime_text)} bytes)"
            ),
        )
    diff_lines = list(
        difflib.unified_diff(
            committed_text.splitlines(),
            runtime_text.splitlines(),
            fromfile="committed",
            tofile="runtime",
            lineterm="",
        )
    )[:10]
    return CheckResult(
        name="docs-drift",
        ok=False,
        diagnostic=(
            "docs/manifest-v1.schema.json drifted from MANIFEST_V1_SCHEMA; "
            "regen via scripts/build_manifest_schema.py. Diff: " + " | ".join(diff_lines)
        ),
    )


def check_plugin_install_smoke_ci_present(ci_yml_path: Path) -> CheckResult:
    """Pass when ci.yml literally contains 'install-smoke-plugin'.

    Single grep — same shape as check_ci_two_variant_smoke_present but
    for the Phase 49 TEST-20 contract. The job name MUST appear in the
    YAML; if a future maintainer drops the matrix to "speed up CI," the
    gate catches it before tagging.
    """
    if not ci_yml_path.exists():
        return CheckResult(
            name="plugin-install-smoke-ci",
            ok=False,
            diagnostic=f"ci.yml not found at {ci_yml_path}",
        )
    text = ci_yml_path.read_text(encoding="utf-8")
    if CI_LITERAL_PLUGIN_INSTALL_SMOKE not in text:
        return CheckResult(
            name="plugin-install-smoke-ci",
            ok=False,
            diagnostic=(
                f"install-smoke-plugin job missing from {ci_yml_path}; TEST-20 contract violated"
            ),
        )
    return CheckResult(
        name="plugin-install-smoke-ci",
        ok=True,
        diagnostic="install-smoke-plugin job present",
    )


def check_reference_plugin_manifest_valid(manifest_path: Path) -> CheckResult:
    """Pass when the reference plugin's horus-plugin.toml parses cleanly.

    Lazy-imports ``validate_manifest`` so the script imports without an
    editable install. Catches ANY exception (not just the pydantic
    ValidationError shape) so the gate is robust to future
    refactors of the manifest module.
    """
    if not manifest_path.exists():
        return CheckResult(
            name="reference-plugin-manifest-valid",
            ok=False,
            diagnostic=f"reference plugin manifest not found at {manifest_path}",
        )
    try:
        toml_bytes = manifest_path.read_bytes()
    except OSError as exc:
        return CheckResult(
            name="reference-plugin-manifest-valid",
            ok=False,
            diagnostic=f"could not read {manifest_path}: {type(exc).__name__}: {exc}",
        )
    try:
        _ensure_src_on_path()
        from horus_os.plugins.manifest import validate_manifest

        spec = validate_manifest(toml_bytes)
    except Exception as exc:
        return CheckResult(
            name="reference-plugin-manifest-valid",
            ok=False,
            diagnostic=(f"reference plugin manifest invalid: {type(exc).__name__}: {exc}"),
        )
    return CheckResult(
        name="reference-plugin-manifest-valid",
        ok=True,
        diagnostic=f"manifest validates as plugin={spec.name} v{spec.version}",
    )


def check_v0_4_fixture_roundtrip(fixture_path: Path) -> CheckResult:
    """Pass when the v0.4 fixture survives the v5 -> v6 migration.

    T-49-01 mitigation: copies the committed fixture to a tempfile
    BEFORE calling Database.init(); the source file is read-only and
    byte-identical pre/post check. The tempfile is unlinked in a
    finally block.

    The check asserts five v6 invariants after init():
      * llm_calls.plugin_name column exists
      * tool_invocations.plugin_name column exists
      * plugins table exists
      * plugin_capabilities table exists
      * plugin_status table exists
      * idx_tool_invocations_plugin index exists

    Plus one idempotency invariant: a second init() call must not
    raise.
    """
    if not fixture_path.exists():
        return CheckResult(
            name="v0-4-fixture-roundtrip",
            ok=False,
            diagnostic=f"v0.4 fixture not found at {fixture_path}",
        )
    tmp_path: Path | None = None
    try:
        # Create a tempfile + copy; never mutate the source.
        with tempfile.NamedTemporaryFile(
            suffix=".sqlite3", delete=False, prefix="release-gate-v0-4-"
        ) as tmp:
            tmp_path = Path(tmp.name)
        try:
            shutil.copy(fixture_path, tmp_path)
        except OSError as exc:
            return CheckResult(
                name="v0-4-fixture-roundtrip",
                ok=False,
                diagnostic=f"could not copy fixture: {type(exc).__name__}: {exc}",
            )

        try:
            _ensure_src_on_path()
            from horus_os.storage import Database

            db = Database(tmp_path)
            db.init()
        except Exception as exc:
            return CheckResult(
                name="v0-4-fixture-roundtrip",
                ok=False,
                diagnostic=(
                    f"Database.init() raised on v0.4 fixture copy: {type(exc).__name__}: {exc}"
                ),
            )

        # Introspect the upgraded schema.
        try:
            conn = sqlite3.connect(str(tmp_path))
            conn.row_factory = sqlite3.Row
            llm_cols = {r["name"] for r in conn.execute("PRAGMA table_info(llm_calls)").fetchall()}
            ti_cols = {
                r["name"] for r in conn.execute("PRAGMA table_info(tool_invocations)").fetchall()
            }
            tables = {
                r["name"]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            indexes = {
                r["name"]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index'"
                ).fetchall()
            }
            conn.close()
        except sqlite3.DatabaseError as exc:
            return CheckResult(
                name="v0-4-fixture-roundtrip",
                ok=False,
                diagnostic=(
                    f"sqlite introspection failed on upgraded fixture: {type(exc).__name__}: {exc}"
                ),
            )

        missing: list[str] = []
        if "plugin_name" not in llm_cols:
            missing.append("llm_calls.plugin_name column")
        if "plugin_name" not in ti_cols:
            missing.append("tool_invocations.plugin_name column")
        for required_table in ("plugins", "plugin_capabilities", "plugin_status"):
            if required_table not in tables:
                missing.append(f"{required_table} table")
        if "idx_tool_invocations_plugin" not in indexes:
            missing.append("idx_tool_invocations_plugin index")
        # Also assert llm_calls / tool_invocations themselves exist
        # (the fixture must have had them at v5; a SQLite file lacking
        # them is not a v0.4 baseline at all).
        if "llm_calls" not in tables:
            missing.append("llm_calls table (fixture is not a v0.4 baseline)")
        if "tool_invocations" not in tables:
            missing.append("tool_invocations table (fixture is not a v0.4 baseline)")

        if missing:
            return CheckResult(
                name="v0-4-fixture-roundtrip",
                ok=False,
                diagnostic=(
                    f"v5 -> v6 migration left fixture incomplete; missing: {', '.join(missing)}"
                ),
            )

        # Idempotency: second init() must not raise.
        try:
            Database(tmp_path).init()
        except Exception as exc:
            return CheckResult(
                name="v0-4-fixture-roundtrip",
                ok=False,
                diagnostic=(
                    f"second Database.init() raised (idempotency broken): "
                    f"{type(exc).__name__}: {exc}"
                ),
            )

        return CheckResult(
            name="v0-4-fixture-roundtrip",
            ok=True,
            diagnostic=(
                "v5->v6 migration green: 2 plugin_name cols + "
                "3 plugin tables + 1 plugin index present; "
                "second init idempotent"
            ),
        )
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink()
            except OSError:
                pass
            # WAL companions (sqlite leaves -wal and -shm files).
            for suffix in ("-wal", "-shm"):
                companion = tmp_path.with_suffix(tmp_path.suffix + suffix)
                try:
                    companion.unlink()
                except OSError:
                    pass


def _print_result(result: CheckResult) -> None:
    if result.ok is True:
        print(f"OK    {result.name}: {result.diagnostic}")
    elif result.ok is False:
        print(f"FAIL  {result.name}: {result.diagnostic}")
    else:
        print(f"SKIP  {result.name}: {result.diagnostic}")


def _resolved_pricing_path() -> Path:
    override = os.environ.get("HORUS_OS_PRICING_PATH_OVERRIDE")
    if override:
        return Path(override)
    return DEFAULT_PRICING_PATH


def _resolved_ci_yml_path() -> Path:
    override = os.environ.get("HORUS_OS_CI_YML_PATH_OVERRIDE")
    if override:
        return Path(override)
    return DEFAULT_CI_YML_PATH


def _resolved_docs_schema_path() -> Path:
    override = os.environ.get("HORUS_OS_DOCS_SCHEMA_PATH_OVERRIDE")
    if override:
        return Path(override)
    return DEFAULT_DOCS_SCHEMA_PATH


def _resolved_reference_plugin_manifest_path() -> Path:
    override = os.environ.get("HORUS_OS_REFERENCE_PLUGIN_MANIFEST_PATH_OVERRIDE")
    if override:
        return Path(override)
    return DEFAULT_REFERENCE_PLUGIN_MANIFEST_PATH


def _resolved_v0_4_fixture_path() -> Path:
    override = os.environ.get("HORUS_OS_V0_4_FIXTURE_PATH_OVERRIDE")
    if override:
        return Path(override)
    return DEFAULT_V0_4_FIXTURE_PATH


def main(argv: list[str] | None = None) -> int:
    """Run the eight release-gate checks. Return 0 on full pass, 1 on any fail."""
    parser = argparse.ArgumentParser(
        description="Pre-tag release-quality gate for horus-os.",
    )
    parser.add_argument(
        "--check",
        choices=(
            "pricing",
            "wheel",
            "ci",
            "tests",
            "docs-drift",
            "plugin-install",
            "reference-manifest",
            "fixture-roundtrip",
        ),
        default=None,
        help="Run only the named check.",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip the slow wheel build (alias for HORUS_OS_RELEASE_GATE_SKIP_BUILD=1).",
    )
    args = parser.parse_args(argv)

    skip_build = args.skip_build or _truthy_env("HORUS_OS_RELEASE_GATE_SKIP_BUILD")
    skip_tests = _truthy_env("HORUS_OS_RELEASE_GATE_SKIP_TESTS")

    selected = args.check
    pricing_path = _resolved_pricing_path()
    ci_yml_path = _resolved_ci_yml_path()
    docs_schema_path = _resolved_docs_schema_path()
    reference_plugin_manifest_path = _resolved_reference_plugin_manifest_path()
    v0_4_fixture_path = _resolved_v0_4_fixture_path()
    max_age = _read_max_age_days()

    results: list[CheckResult] = []

    if selected in (None, "pricing"):
        results.append(check_pricing_freshness(pricing_path, max_age_days=max_age))

    if selected in (None, "ci"):
        results.append(check_ci_two_variant_smoke_present(ci_yml_path))

    if selected in (None, "wheel"):
        if skip_build:
            results.append(
                CheckResult(
                    name="wheel-pricing-bundle",
                    ok=None,
                    diagnostic="skipped (--skip-build or HORUS_OS_RELEASE_GATE_SKIP_BUILD set)",
                )
            )
        else:
            results.append(check_wheel_pricing_bundle(REPO_ROOT))

    if selected in (None, "tests"):
        if skip_tests:
            results.append(
                CheckResult(
                    name="pytest",
                    ok=None,
                    diagnostic="skipped (HORUS_OS_RELEASE_GATE_SKIP_TESTS set)",
                )
            )
        else:
            results.append(check_pytest_pass(REPO_ROOT))

    # v0.5 checks
    if selected in (None, "docs-drift"):
        results.append(check_docs_manifest_schema_drift(docs_schema_path))

    if selected in (None, "plugin-install"):
        results.append(check_plugin_install_smoke_ci_present(ci_yml_path))

    if selected in (None, "reference-manifest"):
        results.append(check_reference_plugin_manifest_valid(reference_plugin_manifest_path))

    if selected in (None, "fixture-roundtrip"):
        results.append(check_v0_4_fixture_roundtrip(v0_4_fixture_path))

    for result in results:
        _print_result(result)

    any_failed = any(r.ok is False for r in results)
    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())
