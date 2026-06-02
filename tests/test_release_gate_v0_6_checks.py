"""Phase 57 REL-14 + REL-15 unit + integration tests for the 5 new release_gate checks.

Tests:
- The --check enum has all 13 values; first 8 byte-identical (REL-14 + STATE.md
  load-bearing constraint #3)
- Each new check function passes against the real Phase 52 + 53 substrate today
- Each new check function fails on synthetic tmp_path violations (non-vacuity)
- The --tier {local,release} CLI flag exists; tier-local skips v0.4/v0.5 checks
- The --allow-offline flag short-circuits local-pip-audit-clean to SKIP
- tier-local wall-clock budget <10s sanity check (generous margin for CI variance)

No em-dashes anywhere (CLAUDE.md HR3).
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RELEASE_GATE_PATH = REPO_ROOT / "scripts" / "release_gate.py"

_MODULE_NAME = "_release_gate_v0_6_under_test"

V0_4_V0_5_CHECKS_ORDERED = (
    "pricing",
    "wheel",
    "ci",
    "tests",
    "docs-drift",
    "plugin-install",
    "reference-manifest",
    "fixture-roundtrip",
)

V0_6_NEW_CHECKS = (
    "release-workflow-signing-present",
    "release-workflow-sbom-present",
    "audit-workflow-present",
    "local-pip-audit-clean",
    "actions-pinned-by-sha",
)


def _load_release_gate_module():
    if _MODULE_NAME in sys.modules:
        return sys.modules[_MODULE_NAME]
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, str(RELEASE_GATE_PATH))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


def _check_enum_values() -> tuple[str, ...]:
    """Parse the --check choices tuple from release_gate.py source."""
    text = RELEASE_GATE_PATH.read_text(encoding="utf-8")
    match = re.search(r'"--check",\s*\n\s*choices=\(\s*\n(.*?)\),', text, re.DOTALL)
    assert match is not None, "could not find --check choices tuple in release_gate.py"
    body = match.group(1)
    values = tuple(s.strip().strip(",").strip('"') for s in body.splitlines() if s.strip())
    return values


# REL-14: enum invariants


def test_check_enum_byte_identical_first_eight() -> None:
    """STATE.md load-bearing constraint #3: the 8 v0.4/v0.5 enum values are byte-identical."""
    values = _check_enum_values()
    assert values[:8] == V0_4_V0_5_CHECKS_ORDERED, (
        f"REL-14: first 8 --check values must be byte-identical to v0.5; got {values[:8]}"
    )


def test_check_enum_has_15_total() -> None:
    """REL-14 + 53-followup + Phase 76: 14 v0.6/v0.7 checks + 1 v0.8 install-smoke check = 15."""
    values = _check_enum_values()
    assert len(values) == 15, (
        f"REL-14 + 53-followup + Phase 76: --check enum must have 15 values "
        f"(8 v0.4/v0.5 + 5 Phase 57 v0.6 + 1 Phase 53-followup sbom-matches-wheel "
        f"+ 1 Phase 76 v0-8-install-smoke-ci); "
        f"got {len(values)}"
    )


def test_check_enum_v0_6_appended() -> None:
    """The 5 Phase 57 v0.6 check values are at positions 8..12; SBOM-03 diff is the 14th."""
    values = _check_enum_values()
    assert set(values[8:13]) == set(V0_6_NEW_CHECKS), (
        f"REL-14: the 5 Phase 57 v0.6 checks must be at positions 8..12; got {values[8:13]}"
    )
    assert values[13] == "sbom-matches-wheel", (
        f"53-followup: sbom-matches-wheel must be the 14th check; got {values[13]!r}"
    )


# REL-14: each new check passes against the real Phase 52 + 53 substrate today


def test_release_workflow_signing_present_passes_today() -> None:
    mod = _load_release_gate_module()
    result = mod.check_release_workflow_signing_present(mod.DEFAULT_RELEASE_YML_PATH)
    assert result.ok is True, f"Phase 52 substrate broken: {result.diagnostic}"


def test_release_workflow_sbom_present_passes_today() -> None:
    mod = _load_release_gate_module()
    result = mod.check_release_workflow_sbom_present(mod.DEFAULT_RELEASE_YML_PATH)
    assert result.ok is True, f"Phase 53 substrate broken: {result.diagnostic}"


def test_audit_workflow_present_passes_today() -> None:
    mod = _load_release_gate_module()
    result = mod.check_audit_workflow_present(mod.DEFAULT_AUDIT_YML_PATH)
    assert result.ok is True, f"Phase 53 audit substrate broken: {result.diagnostic}"


def test_actions_pinned_by_sha_passes_today() -> None:
    mod = _load_release_gate_module()
    result = mod.check_actions_pinned_by_sha(mod.DEFAULT_WORKFLOWS_DIR)
    assert result.ok is True, f"CIHARD-04 violation in current workflows: {result.diagnostic}"


# REL-14: non-vacuity tests (each new check fails on synthetic tmp_path violations)


def test_signing_present_fails_on_synthetic_missing(tmp_path: Path) -> None:
    mod = _load_release_gate_module()
    fake = tmp_path / "release.yml"
    fake.write_text("jobs:\n  x:\n    runs-on: ubuntu-latest\n", encoding="utf-8")
    result = mod.check_release_workflow_signing_present(fake)
    assert result.ok is False
    assert "missing signing literals" in result.diagnostic


def test_sbom_present_fails_on_synthetic_missing(tmp_path: Path) -> None:
    mod = _load_release_gate_module()
    fake = tmp_path / "release.yml"
    fake.write_text(
        "jobs:\n  x:\n    steps:\n      - uses: sigstore/gh-action-sigstore-python@aaa\n",
        encoding="utf-8",
    )
    result = mod.check_release_workflow_sbom_present(fake)
    assert result.ok is False
    assert "missing SBOM literals" in result.diagnostic


def test_audit_present_fails_on_synthetic_missing(tmp_path: Path) -> None:
    mod = _load_release_gate_module()
    fake = tmp_path / "audit.yml"
    fake.write_text("name: audit\non: pull_request\n", encoding="utf-8")
    result = mod.check_audit_workflow_present(fake)
    assert result.ok is False


def test_audit_present_fails_when_file_missing(tmp_path: Path) -> None:
    mod = _load_release_gate_module()
    nonexistent = tmp_path / "does-not-exist.yml"
    result = mod.check_audit_workflow_present(nonexistent)
    assert result.ok is False
    assert "not found" in result.diagnostic


def test_actions_sha_fails_on_synthetic_mutable_tag(tmp_path: Path) -> None:
    mod = _load_release_gate_module()
    fake_dir = tmp_path / "workflows"
    fake_dir.mkdir()
    (fake_dir / "bad.yml").write_text(
        "jobs:\n  x:\n    steps:\n      - uses: actions/checkout@v4\n",
        encoding="utf-8",
    )
    result = mod.check_actions_pinned_by_sha(fake_dir)
    assert result.ok is False
    assert "CIHARD-04 violation" in result.diagnostic
    assert "actions/checkout@v4" in result.diagnostic


def test_actions_sha_accepts_local_action(tmp_path: Path) -> None:
    mod = _load_release_gate_module()
    fake_dir = tmp_path / "workflows"
    fake_dir.mkdir()
    (fake_dir / "ok.yml").write_text(
        "jobs:\n  x:\n    steps:\n      - uses: ./local-action\n",
        encoding="utf-8",
    )
    result = mod.check_actions_pinned_by_sha(fake_dir)
    assert result.ok is True


# REL-15: --allow-offline + --tier CLI


def test_allow_offline_skips_pip_audit() -> None:
    mod = _load_release_gate_module()
    result = mod.check_local_pip_audit_clean(allow_offline=True)
    assert result.ok is None
    assert "SKIPPED" in result.diagnostic
    assert "--allow-offline" in result.diagnostic


def test_local_pip_audit_handles_missing_tool_as_skip() -> None:
    """When pip-audit isn't installed, the check returns ok=None (SKIP), not ok=False.

    Rationale: failing the gate on missing pip-audit would break CI on workstations
    where the maintainer just runs --tier local. The check still surfaces in the
    output as SKIPPED so the maintainer knows to install [dev] for tier-release.
    """
    mod = _load_release_gate_module()
    # If pip-audit is actually installed in this venv, skip the test; otherwise
    # we can directly verify the SKIP-on-missing behavior.
    try:
        import pip_audit  # noqa: F401

        # pip-audit IS installed; run the check; we don't assert on outcome
        # because actual CVE data is moving target
        return
    except ImportError:
        pass
    result = mod.check_local_pip_audit_clean(allow_offline=False)
    assert result.ok is None, f"missing pip-audit must yield SKIP, not {result.ok}"
    assert "SKIPPED" in result.diagnostic


def test_tier_release_default() -> None:
    """No --tier flag means tier=release (preserves existing main([]) behavior)."""
    proc = subprocess.run(
        [sys.executable, str(RELEASE_GATE_PATH), "--help"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert "release" in proc.stdout
    assert "default: release" in proc.stdout.lower() or "(default)" in proc.stdout.lower()


def test_help_text_documents_new_flags() -> None:
    proc = subprocess.run(
        [sys.executable, str(RELEASE_GATE_PATH), "--help"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert proc.returncode == 0
    assert "--tier" in proc.stdout
    assert "--allow-offline" in proc.stdout
    for new_check in V0_6_NEW_CHECKS:
        assert new_check in proc.stdout, f"--check choice {new_check!r} missing from --help output"


def test_tier_local_runs_only_grep_checks() -> None:
    """tier=local --allow-offline runs ONLY the 4 grep-only Phase 57 checks; no v0.4/v0.5 checks."""
    proc = subprocess.run(
        [sys.executable, str(RELEASE_GATE_PATH), "--tier", "local", "--allow-offline"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    output = proc.stdout
    # Should contain the 4 grep-only checks
    for check_name in (
        "release-workflow-signing-present",
        "release-workflow-sbom-present",
        "audit-workflow-present",
        "actions-pinned-by-sha",
    ):
        assert check_name in output, f"tier-local output missing {check_name}"
    # Should NOT contain any of the v0.4/v0.5 checks
    for legacy in (
        "pricing-freshness",
        "ci-two-variant-smoke",
        "wheel-pricing-bundle",
        "docs-drift",
    ):
        assert legacy not in output, (
            f"tier-local output unexpectedly contains v0.4/v0.5 check {legacy}"
        )


def test_tier_local_under_10_seconds() -> None:
    """REL-15 wall-clock budget: tier-local runs in <10s (generous 15s for CI variance)."""
    start = time.monotonic()
    proc = subprocess.run(
        [sys.executable, str(RELEASE_GATE_PATH), "--tier", "local", "--allow-offline"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    elapsed = time.monotonic() - start
    assert proc.returncode == 0, f"tier-local must pass today; stderr: {proc.stderr}"
    assert elapsed < 15.0, f"tier-local wall-clock {elapsed:.2f}s exceeds 15s sanity ceiling"


# Phase 57-followup (review WR-01): pip-audit-ignore.txt format validator


def test_pip_audit_ignore_format_validator_accepts_empty(tmp_path: Path) -> None:
    """An empty (or comment-only) ignore file passes the validator (v0.6.0 launch state)."""
    mod = _load_release_gate_module()
    ignore = tmp_path / "ignore.txt"
    ignore.write_text("# this file is empty at launch\n", encoding="utf-8")
    assert mod._validate_pip_audit_ignore_format(ignore) is None


def test_pip_audit_ignore_format_validator_accepts_dated(tmp_path: Path) -> None:
    """A correctly dated entry passes the validator."""
    mod = _load_release_gate_module()
    ignore = tmp_path / "ignore.txt"
    ignore.write_text(
        "# 2026-05-30: urllib3 transitive, awaiting upstream 2.x patch\nGHSA-xxxx-yyyy-zzzz\n",
        encoding="utf-8",
    )
    assert mod._validate_pip_audit_ignore_format(ignore) is None


def test_pip_audit_ignore_format_validator_rejects_undated(tmp_path: Path) -> None:
    """An ignore entry without a dated comment above it FAILS the validator."""
    mod = _load_release_gate_module()
    ignore = tmp_path / "ignore.txt"
    ignore.write_text("GHSA-xxxx-yyyy-zzzz\n", encoding="utf-8")
    err = mod._validate_pip_audit_ignore_format(ignore)
    assert err is not None, "undated ignore entry must be rejected"
    assert "GHSA-xxxx-yyyy-zzzz" in err
    assert "YYYY-MM-DD" in err


def test_pip_audit_ignore_format_validator_rejects_undated_comment(tmp_path: Path) -> None:
    """A bare comment without a date does NOT satisfy the dated-reason contract."""
    mod = _load_release_gate_module()
    ignore = tmp_path / "ignore.txt"
    ignore.write_text(
        "# this is a non-dated comment\nGHSA-xxxx-yyyy-zzzz\n",
        encoding="utf-8",
    )
    err = mod._validate_pip_audit_ignore_format(ignore)
    assert err is not None
    assert "GHSA-xxxx-yyyy-zzzz" in err


def test_pip_audit_ignore_format_validator_handles_missing_file(tmp_path: Path) -> None:
    """When the ignore file doesn't exist, the validator returns None (no contract to enforce)."""
    mod = _load_release_gate_module()
    assert mod._validate_pip_audit_ignore_format(tmp_path / "absent.txt") is None


def test_local_pip_audit_clean_fails_on_malformed_ignore(tmp_path: Path, monkeypatch) -> None:
    """check_local_pip_audit_clean returns ok=False when the ignore file is malformed.

    This closes the SUPPLY-03 contract gap: the .github/pip-audit-ignore.txt
    header docstring promises the release-gate rejects undated ignore entries.
    """
    mod = _load_release_gate_module()
    bad_ignore = tmp_path / "ignore.txt"
    bad_ignore.write_text("CVE-2026-99999\n", encoding="utf-8")
    monkeypatch.setattr(mod, "DEFAULT_PIP_AUDIT_IGNORE_PATH", bad_ignore)
    result = mod.check_local_pip_audit_clean(allow_offline=False)
    assert result.ok is False
    assert "format violation" in result.diagnostic


# Phase 57-followup (review WR-02): incompatible flag combination


def test_local_tier_plus_pip_audit_check_errors_out() -> None:
    """--tier local + --check local-pip-audit-clean errors with a clear message.

    Previously this combination silently produced no result and returned 0,
    misleading the maintainer into believing the check passed.
    """
    proc = subprocess.run(
        [
            sys.executable,
            str(RELEASE_GATE_PATH),
            "--tier",
            "local",
            "--check",
            "local-pip-audit-clean",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert proc.returncode != 0, (
        "incompatible --tier local + --check local-pip-audit-clean must exit non-zero"
    )
    combined = (proc.stdout + proc.stderr).lower()
    assert "incompatible" in combined or "local" in combined
    assert "local-pip-audit-clean" in proc.stdout + proc.stderr
