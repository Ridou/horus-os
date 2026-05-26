"""Pre-tag release-quality gate for horus-os (Phase 39, REL-08, Pitfall 5 + 12).

Runs FOUR checks before the maintainer cuts a tag:

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

CLI flags:

- --check {pricing,wheel,ci,tests}: run only the named check.
- --skip-build: skip the wheel build (alias for
  HORUS_OS_RELEASE_GATE_SKIP_BUILD=1).

STOP-BEFORE-TAG protocol: this script is the LAST automated step
before `git tag -a vN.M.P`. The script itself NEVER tags or pushes
or creates a GitHub Release; those steps are documented in
docs/RELEASE.md `## Release procedure` and are user-confirmation
gates.

Pure stdlib (json, datetime, pathlib, subprocess, sys, os,
argparse, zipfile, tempfile). The `build` package is invoked via
subprocess so this script imports cleanly without it.
"""

from __future__ import annotations

import argparse
import json
import os
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

DEFAULT_MAX_AGE_DAYS = 14

CI_LITERAL_NO_OTEL = "install-smoke-no-otel"
CI_LITERAL_WITH_OTEL = "install-smoke-with-otel"

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


def main(argv: list[str] | None = None) -> int:
    """Run the four release-gate checks. Return 0 on full pass, 1 on any fail."""
    parser = argparse.ArgumentParser(
        description="Pre-tag release-quality gate for horus-os.",
    )
    parser.add_argument(
        "--check",
        choices=("pricing", "wheel", "ci", "tests"),
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

    for result in results:
        _print_result(result)

    any_failed = any(r.ok is False for r in results)
    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())
