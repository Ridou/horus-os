"""Phase 53 SBOM-03: scripts/verify_release.py check_sbom_signature active-mode unit tests.

Wave 0 RED-by-design: tests 1-5 fail until Plan 02 flips the Phase 52 D-08 stub
to active 2-bundle verification + dependency-tree diff. Tests are written using
the in-process module loader pattern from tests/test_release_verification.py
(importlib.util.spec_from_file_location, register as _verify_release_under_test).

The non-vacuity test test_phase_52_stub_currently_returns_skipped passes NOW
(Phase 52 D-08 stub returns ok=None); Plan 02's D-09 inverse-flip updates this
test to assert the new active-mode shape in the same commit as the stub flip.

No em-dashes anywhere (CLAUDE.md HR3).
"""

from __future__ import annotations

import importlib.util
import inspect
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ISSUER = "https://token.actions.githubusercontent.com"
CANONICAL_FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "sigstore" / "canonical"
VERIFY_RELEASE_PATH = REPO_ROOT / "scripts" / "verify_release.py"


def _load_verify_release_module():
    """Load scripts/verify_release.py in-process; mirrors PATTERNS Plan 01 Pattern A.

    The module is registered as `_verify_release_under_test` in sys.modules so
    multiple test calls return the same instance.
    """
    name = "_verify_release_under_test"
    if name in sys.modules:
        return sys.modules[name]
    if not VERIFY_RELEASE_PATH.is_file():
        raise FileNotFoundError(
            f"{VERIFY_RELEASE_PATH} not found (Phase 52 should have created it)"
        )
    spec = importlib.util.spec_from_file_location(name, str(VERIFY_RELEASE_PATH))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Production assertions: RED until Plan 02 flips check_sbom_signature to active.


def test_check_sbom_signature_no_longer_returns_skipped(tmp_path: Path) -> None:
    """Phase 53 SBOM-03 + D-05: check_sbom_signature with bundle args returns ok True/False, not None."""
    mod = _load_verify_release_module()
    # Create dummy bundle / artifact paths (real verification will fail, but ok should be True or False, not None)
    bundle = tmp_path / "fake.cdx.json.sigstore"
    artifact = tmp_path / "fake.whl"
    bundle.write_text("{}", encoding="utf-8")
    artifact.write_bytes(b"")
    # Try the post-flip signature
    sig = inspect.signature(mod.check_sbom_signature)
    params = list(sig.parameters.keys())
    if "clean_bundle_path" in params:
        result = mod.check_sbom_signature(
            version="0.6.0-rc1",
            cert_oidc_issuer=EXPECTED_ISSUER,
            clean_bundle_path=bundle,
            clean_artifact_path=artifact,
            extras_bundle_path=bundle,
            extras_artifact_path=artifact,
        )
    else:
        # Phase 52 stub signature: just (version)
        result = mod.check_sbom_signature(version="0.6.0-rc1")
    assert result.ok is not None, (
        "Phase 53 SBOM-03: check_sbom_signature must flip from D-08 SKIP stub to active. "
        f"Pre-flip (RED), this test fails because result.ok is None. Got result: {result}"
    )


def test_check_sbom_signature_signature_supports_bundle_artifact_args() -> None:
    """Phase 53 D-05: check_sbom_signature signature must accept bundle/artifact paths."""
    mod = _load_verify_release_module()
    sig = inspect.signature(mod.check_sbom_signature)
    params = set(sig.parameters.keys())
    bundle_params = {
        "clean_bundle_path",
        "clean_artifact_path",
        "extras_bundle_path",
        "extras_artifact_path",
    }
    assert bundle_params.issubset(params) or "sbom_paths" in params, (
        "Phase 53 D-05: check_sbom_signature signature must accept the four bundle/artifact path "
        "args (or a single sbom_paths arg). Pre-flip (RED), signature is the Phase 52 stub "
        f"(version). Got params: {sorted(params)}"
    )


def test_check_sbom_signature_two_bundles_verified() -> None:
    """Phase 53 SBOM-03: with both bundles present, check_sbom_signature returns ok=True."""
    mod = _load_verify_release_module()
    clean_sbom = CANONICAL_FIXTURE_DIR / "horus_os-clean.cdx.json"
    clean_bundle = CANONICAL_FIXTURE_DIR / "horus_os-clean.cdx.json.sigstore"
    extras_sbom = CANONICAL_FIXTURE_DIR / "horus_os-dev-otel.cdx.json"
    extras_bundle = CANONICAL_FIXTURE_DIR / "horus_os-dev-otel.cdx.json.sigstore"
    if not (
        clean_sbom.is_file()
        and clean_bundle.is_file()
        and extras_sbom.is_file()
        and extras_bundle.is_file()
    ):
        pytest.skip(
            "Canonical SBOM bundles land at v0.6.0-rc1 rehearsal time per "
            "53-VALIDATION.md Manual-Only Verifications"
        )
    sig = inspect.signature(mod.check_sbom_signature)
    if "clean_bundle_path" not in sig.parameters:
        pytest.fail("Phase 53 D-05: check_sbom_signature signature missing clean_bundle_path")
    result = mod.check_sbom_signature(
        version="0.6.0-rc1",
        cert_oidc_issuer=EXPECTED_ISSUER,
        clean_bundle_path=clean_bundle,
        clean_artifact_path=clean_sbom,
        extras_bundle_path=extras_bundle,
        extras_artifact_path=extras_sbom,
    )
    assert result.ok is True, f"Phase 53 SBOM-03: expected ok=True; got {result}"


def test_check_sbom_signature_diff_against_wheel_fails_on_stale_sbom(monkeypatch) -> None:
    """Phase 53 SBOM-03: dependency-tree diff returns False on stale SBOM.

    Skipped today because Plan 02's minimum-viable implementation defers the
    explicit diff function to Phase 57 release-gate (where pip install --dry-run
    can run locally). The test stays here as a hook for future expansion.
    """
    mod = _load_verify_release_module()
    diff_fn = getattr(mod, "_diff_sbom_against_wheel", None) or getattr(
        mod, "check_sbom_dependency_tree", None
    )
    if diff_fn is None:
        pytest.skip(
            "Phase 53 minimum-viable SBOM-03: explicit dependency-tree diff function is "
            "deferred to Phase 57 release-gate. Plan 02 verifies the two sigstore bundles "
            "(SBOM contents are FRESH-venv-aligned with the wheel at generation time)."
        )
    # If the function exists, exercise it with a synthetic stale fixture.
    # (Plan 02 does not land this; documented for future expansion.)
    pytest.skip("Diff function exists but synthetic stale-fixture exercise not implemented yet")


def test_main_sbom_check_runs_active(tmp_path: Path) -> None:
    """Phase 53 SBOM-03: main(['--check', 'sbom', ...]) no longer prints SKIPPED unconditionally."""
    mod = _load_verify_release_module()
    sig = inspect.signature(mod.check_sbom_signature)
    if "clean_bundle_path" not in sig.parameters:
        pytest.fail(
            "Phase 53 D-05: check_sbom_signature signature must support --clean-bundle / "
            "--clean-artifact / --extras-bundle / --extras-artifact CLI dispatch"
        )
    bundle = tmp_path / "fake.cdx.json.sigstore"
    artifact = tmp_path / "fake.whl"
    bundle.write_text("{}", encoding="utf-8")
    artifact.write_bytes(b"")
    # Build_parser must have the new four args
    parser = mod._build_parser()
    options = {a.option_strings[0] for a in parser._actions if a.option_strings}
    expected = {"--clean-bundle", "--clean-artifact", "--extras-bundle", "--extras-artifact"}
    missing = expected - options
    assert not missing, f"Phase 53 D-05: CLI missing args {missing}"


# Non-vacuity tests: pass NOW; do not require Plan 02 changes.


def test_phase_52_stub_currently_returns_skipped() -> None:
    """Non-vacuity: today the Phase 52 D-08 stub returns ok=None with SKIPPED diagnostic.

    On Plan 02 land, D-09 specifies this test is REPLACED with
    test_check_sbom_signature_returns_skipped_only_with_no_bundles (asserts the
    new SKIP-only-when-all-paths-None contract).
    """
    mod = _load_verify_release_module()
    sig = inspect.signature(mod.check_sbom_signature)
    if "clean_bundle_path" in sig.parameters:
        # Plan 02 has already flipped the stub; this non-vacuity is now stale
        pytest.skip(
            "Phase 53 Plan 02 D-09: check_sbom_signature signature is post-flip; "
            "test_phase_52_stub_currently_returns_skipped is replaced by "
            "test_check_sbom_signature_returns_skipped_only_with_no_bundles"
        )
    result = mod.check_sbom_signature(version="0.6.0-rc1")
    assert result.ok is None, (
        f"Non-vacuity: pre-flip Phase 52 stub must return ok=None; got {result}"
    )
    assert "SKIPPED" in result.diagnostic, (
        f"Non-vacuity: pre-flip Phase 52 stub diagnostic must contain 'SKIPPED'; "
        f"got {result.diagnostic!r}"
    )


def test_module_loads_cleanly_today() -> None:
    """Non-vacuity: the test infrastructure can load scripts/verify_release.py today."""
    mod = _load_verify_release_module()
    assert mod is not None
    assert hasattr(mod, "check_sbom_signature"), (
        "Non-vacuity: verify_release.py must expose check_sbom_signature"
    )


# A subprocess smoke test exercising the actual script end-to-end is included
# to detect collection / import regressions in CI.
def test_script_imports_via_subprocess() -> None:
    """Non-vacuity infrastructure check: scripts/verify_release.py imports cleanly via subprocess."""
    if not VERIFY_RELEASE_PATH.is_file():
        pytest.skip(f"{VERIFY_RELEASE_PATH} missing")
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "import importlib.util, sys; "
            f"spec = importlib.util.spec_from_file_location('vr', {str(VERIFY_RELEASE_PATH)!r}); "
            "mod = importlib.util.module_from_spec(spec); "
            "sys.modules['vr'] = mod; "
            "spec.loader.exec_module(mod); "
            "print('OK')",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert proc.returncode == 0, (
        f"Non-vacuity: subprocess import failed. stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
    assert "OK" in proc.stdout
