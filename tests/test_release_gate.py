"""Unit tests for scripts/release_gate.py (Phase 39, REL-08, Pitfall 5 + 12).

The release_gate is the maintainer's last automated step before
`git tag -a vN.M.P`. It runs four checks: pricing freshness, CI
two-variant install-smoke presence, wheel pricing-bundle packaging,
and pytest pass. These tests exercise each check function DIRECTLY
(via in-process call, no subprocess) so the test file stays
hermetic and fast.

The slow checks (wheel build, full pytest) are skipped via env
overrides (HORUS_OS_RELEASE_GATE_SKIP_BUILD,
HORUS_OS_RELEASE_GATE_SKIP_TESTS) in the main() integration tests,
otherwise the test would recursively shell out to itself.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

_MODULE_NAME = "_release_gate_under_test"


def _load_release_gate_module():
    """Import scripts/release_gate.py as a module without modifying sys.path.

    The module is registered in `sys.modules` because @dataclass needs to
    introspect the defining module via `sys.modules[cls.__module__]`.
    """
    if _MODULE_NAME in sys.modules:
        return sys.modules[_MODULE_NAME]
    script = REPO_ROOT / "scripts" / "release_gate.py"
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


def _write_pricing_json(path: Path, updated_at: str) -> None:
    path.write_text(
        json.dumps(
            {
                "version": "1",
                "updated_at": updated_at,
                "release_version": "0.4.0",
                "models": {},
            }
        ),
        encoding="utf-8",
    )


def _write_ci_yml(
    path: Path,
    *,
    has_no_otel: bool,
    has_with_otel: bool,
    has_plugin_install: bool = True,
) -> None:
    # has_plugin_install defaults to True so the v0.5 plugin-install-smoke-ci
    # check (which now runs from the same shared ci.yml fixture) sees the
    # literal it greps for. Phase 49 added the new check; the existing tests
    # were authored before it existed.
    lines = ["name: test\n", "jobs:\n"]
    if has_no_otel:
        lines.append("  install-smoke-no-otel:\n    runs-on: ubuntu-latest\n")
    if has_with_otel:
        lines.append("  install-smoke-with-otel:\n    runs-on: ubuntu-latest\n")
    if has_plugin_install:
        lines.append("  install-smoke-plugin:\n    runs-on: ubuntu-latest\n")
    path.write_text("".join(lines), encoding="utf-8")


def test_pricing_freshness_passes_when_within_threshold(tmp_path: Path) -> None:
    mod = _load_release_gate_module()
    pricing = tmp_path / "pricing.json"
    _write_pricing_json(pricing, date.today().isoformat())
    result = mod.check_pricing_freshness(pricing_path=pricing, max_age_days=14)
    assert result.ok is True, result.diagnostic


def test_pricing_freshness_fails_when_older_than_threshold(tmp_path: Path) -> None:
    mod = _load_release_gate_module()
    pricing = tmp_path / "pricing.json"
    stale = (date.today() - timedelta(days=30)).isoformat()
    _write_pricing_json(pricing, stale)
    result = mod.check_pricing_freshness(pricing_path=pricing, max_age_days=14)
    assert result.ok is False
    assert "30" in result.diagnostic
    assert "14" in result.diagnostic


def test_pricing_freshness_fails_when_pricing_json_missing(tmp_path: Path) -> None:
    mod = _load_release_gate_module()
    missing = tmp_path / "does_not_exist.json"
    result = mod.check_pricing_freshness(pricing_path=missing, max_age_days=14)
    assert result.ok is False
    assert str(missing) in result.diagnostic


def test_pricing_freshness_fails_when_updated_at_malformed(tmp_path: Path) -> None:
    mod = _load_release_gate_module()
    pricing = tmp_path / "pricing.json"
    _write_pricing_json(pricing, "not-a-date")
    result = mod.check_pricing_freshness(pricing_path=pricing, max_age_days=14)
    assert result.ok is False
    assert "pars" in result.diagnostic.lower() or "format" in result.diagnostic.lower()


def test_ci_presence_passes_when_both_jobs_present(tmp_path: Path) -> None:
    mod = _load_release_gate_module()
    ci = tmp_path / "ci.yml"
    _write_ci_yml(ci, has_no_otel=True, has_with_otel=True)
    result = mod.check_ci_two_variant_smoke_present(ci_yml_path=ci)
    assert result.ok is True, result.diagnostic


def test_ci_presence_fails_when_no_otel_job_missing(tmp_path: Path) -> None:
    mod = _load_release_gate_module()
    ci = tmp_path / "ci.yml"
    _write_ci_yml(ci, has_no_otel=False, has_with_otel=True)
    result = mod.check_ci_two_variant_smoke_present(ci_yml_path=ci)
    assert result.ok is False
    assert "install-smoke-no-otel" in result.diagnostic


def test_ci_presence_fails_when_with_otel_job_missing(tmp_path: Path) -> None:
    mod = _load_release_gate_module()
    ci = tmp_path / "ci.yml"
    _write_ci_yml(ci, has_no_otel=True, has_with_otel=False)
    result = mod.check_ci_two_variant_smoke_present(ci_yml_path=ci)
    assert result.ok is False
    assert "install-smoke-with-otel" in result.diagnostic


def test_main_exit_zero_when_all_checks_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mod = _load_release_gate_module()
    pricing = tmp_path / "pricing.json"
    _write_pricing_json(pricing, date.today().isoformat())
    ci = tmp_path / "ci.yml"
    _write_ci_yml(ci, has_no_otel=True, has_with_otel=True)
    monkeypatch.setenv("HORUS_OS_RELEASE_GATE_SKIP_TESTS", "1")
    monkeypatch.setenv("HORUS_OS_RELEASE_GATE_SKIP_BUILD", "1")
    monkeypatch.setenv("HORUS_OS_PRICING_PATH_OVERRIDE", str(pricing))
    monkeypatch.setenv("HORUS_OS_CI_YML_PATH_OVERRIDE", str(ci))
    # --allow-offline skips the network pip-audit scan so this aggregation
    # test stays hermetic: a vulnerable package preinstalled on a CI runner
    # (outside horus-os's dependency closure) must not fail the gate's unit
    # tests. The live OSV scan runs in the real release-gate invocation.
    exit_code = mod.main(["--allow-offline"])
    assert exit_code == 0


def test_main_exit_nonzero_when_any_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mod = _load_release_gate_module()
    pricing = tmp_path / "pricing.json"
    stale = (date.today() - timedelta(days=30)).isoformat()
    _write_pricing_json(pricing, stale)
    ci = tmp_path / "ci.yml"
    _write_ci_yml(ci, has_no_otel=True, has_with_otel=True)
    monkeypatch.setenv("HORUS_OS_RELEASE_GATE_SKIP_TESTS", "1")
    monkeypatch.setenv("HORUS_OS_RELEASE_GATE_SKIP_BUILD", "1")
    monkeypatch.setenv("HORUS_OS_PRICING_PATH_OVERRIDE", str(pricing))
    monkeypatch.setenv("HORUS_OS_CI_YML_PATH_OVERRIDE", str(ci))
    exit_code = mod.main([])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "FAIL" in captured.out


def test_pricing_threshold_overridable_via_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mod = _load_release_gate_module()
    pricing = tmp_path / "pricing.json"
    stale = (date.today() - timedelta(days=30)).isoformat()
    _write_pricing_json(pricing, stale)
    ci = tmp_path / "ci.yml"
    _write_ci_yml(ci, has_no_otel=True, has_with_otel=True)
    monkeypatch.setenv("HORUS_OS_PRICING_MAX_AGE_DAYS", "60")
    monkeypatch.setenv("HORUS_OS_RELEASE_GATE_SKIP_TESTS", "1")
    monkeypatch.setenv("HORUS_OS_RELEASE_GATE_SKIP_BUILD", "1")
    monkeypatch.setenv("HORUS_OS_PRICING_PATH_OVERRIDE", str(pricing))
    monkeypatch.setenv("HORUS_OS_CI_YML_PATH_OVERRIDE", str(ci))
    # --allow-offline skips the network pip-audit scan so this aggregation
    # test stays hermetic: a vulnerable package preinstalled on a CI runner
    # (outside horus-os's dependency closure) must not fail the gate's unit
    # tests. The live OSV scan runs in the real release-gate invocation.
    exit_code = mod.main(["--allow-offline"])
    assert exit_code == 0
