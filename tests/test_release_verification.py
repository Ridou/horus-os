"""SIGN-04 (Phase 52 Wave 0 RED-by-design): scripts/verify_release.py unit + integration tests.

Five production tests cover SIGN-04 per VALIDATION.md row 4:

1. test_canonical_fixture_passes_wheel_check: invokes
   ``check_wheel_signature(...)`` against the committed canonical
   ``.whl`` + ``.sigstore[.json]`` pair under
   ``tests/fixtures/sigstore/canonical/`` and asserts the result
   passes. Skips with a pytest.skip if the binary fixtures are not
   yet present (binaries are recorded at v0.6.0-rc1 rehearsal time
   per VALIDATION.md Manual-Only Verifications row 1; Plan 01 ships
   ONLY the directory + README.md placeholder).
2. test_missing_issuer_refused: calls ``mod.main(["--version",
   "0.6.0-rc1"])`` with no ``--cert-oidc-issuer`` and asserts the
   argparse ``required=True`` machinery exits with code 2.
3. test_wrong_issuer_refused: calls ``mod.main`` with a mismatched
   issuer and asserts non-zero exit + the expected issuer literal
   appears on stderr.
4. test_sbom_stub_returns_skipped: calls
   ``mod.check_sbom_signature(version="0.6.0-rc1")`` directly and
   asserts ``result.ok is None`` AND ``"SKIPPED"`` AND
   ``"Phase 53"`` both appear in the diagnostic (D-08 SBOM stub
   contract).
5. test_full_run_all_checks_with_canonical_fixture: full main()
   invocation across all 5 checks; asserts exit 0 (skipped checks
   per release_gate precedent do NOT count as failure). Skips with
   the same canonical-binary skip reason if fixtures absent.

Plus three Wave 0 helper tests:

- test_expected_identity_template_invariant_is_documented: scans
  the committed scripts/verify_release.py source (if present) for
  the literal ``'refs/tags/{version}'`` substring (PITFALL 1
  wildcard-identity defense). Skips cleanly if Plan 02 has not yet
  landed the script.
- test_expected_issuer_constant_documented: scans the committed
  source for the literal
  ``'https://token.actions.githubusercontent.com'`` substring.
  Skips cleanly if the script is absent.
- test_module_imports_cleanly: actually imports the module via
  ``importlib.util.spec_from_file_location`` and asserts the
  byte-exact ``EXPECTED_IDENTITY_TEMPLATE`` and ``EXPECTED_ISSUER``
  constants (D-04 hardcoded constant contract). RED until Plan 02
  lands the script.

Plus one optional Pattern C subprocess smoke
(``test_script_runs_via_subprocess``): shells out via
``[sys.executable, str(script), ...]`` with capture_output=True,
text=True, check=False (Shared Pattern S-1 cross-OS discipline);
skips cleanly if the script file is absent.

Wave 0 state: all production tests RED or SKIPPED; tests in this
file collect cleanly (the file does NOT crash at import time even
though scripts/verify_release.py is absent).
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_ISSUER = "https://token.actions.githubusercontent.com"
EXPECTED_IDENTITY_TEMPLATE = (
    "https://github.com/Ridou/horus-os/.github/workflows/release.yml@refs/tags/{version}"
)

VERIFY_RELEASE_SCRIPT = REPO_ROOT / "scripts" / "verify_release.py"
CANONICAL_FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "sigstore" / "canonical"
CANONICAL_README = CANONICAL_FIXTURE_DIR / "README.md"

_MODULE_NAME = "_verify_release_under_test"


def _canonical_fixture_paths() -> tuple[Path | None, Path | None]:
    """Return (wheel_path, bundle_path) for the canonical rehearsal fixture, or (None, None).

    The bundle suffix may be ``.sigstore`` or ``.sigstore.json``
    depending on the recording-time sigstore-python action version
    (RESEARCH.md confidence note flags this as MEDIUM). The fixture
    README is the source of truth once recorded.
    """
    if not CANONICAL_FIXTURE_DIR.is_dir():
        return (None, None)
    wheels = sorted(CANONICAL_FIXTURE_DIR.glob("*.whl"))
    if not wheels:
        return (None, None)
    wheel = wheels[0]
    bundle_dot_json = wheel.with_suffix(wheel.suffix + ".sigstore.json")
    bundle_legacy = wheel.with_suffix(wheel.suffix + ".sigstore")
    if bundle_dot_json.is_file():
        return (wheel, bundle_dot_json)
    if bundle_legacy.is_file():
        return (wheel, bundle_legacy)
    return (wheel, None)


_SKIP_FIXTURE_PENDING = (
    "Canonical fixture binaries land at v0.6.0-rc1 rehearsal recording "
    "time per VALIDATION.md Manual-Only Verifications row 1; "
    "Plan 01 ships ONLY the directory + README.md placeholder. See "
    f"{CANONICAL_README.relative_to(REPO_ROOT)} for the recording procedure."
)


def _load_verify_release_module():
    """Import scripts/verify_release.py as a module without modifying sys.path.

    Mirrors tests/test_release_gate.py:31-46 verbatim. Registers the
    module in sys.modules because @dataclass needs to introspect the
    defining module via sys.modules[cls.__module__].
    """
    if _MODULE_NAME in sys.modules:
        return sys.modules[_MODULE_NAME]
    if not VERIFY_RELEASE_SCRIPT.is_file():
        raise FileNotFoundError(
            f"scripts/verify_release.py missing. SIGN-04 (D-03) requires "
            f"Plan 02 (Wave 1) to create the 5-check trust-chain verifier "
            f"with hardcoded EXPECTED_IDENTITY_TEMPLATE and "
            f"EXPECTED_ISSUER constants. Expected at "
            f"{VERIFY_RELEASE_SCRIPT.relative_to(REPO_ROOT)}."
        )
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, VERIFY_RELEASE_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Production tests (RED-or-SKIPPED in Wave 0; Plan 02 turns them GREEN)
# ---------------------------------------------------------------------------


def test_canonical_fixture_passes_wheel_check() -> None:
    """SIGN-04 (D-07): canonical .whl + .sigstore[.json] pair verifies clean."""
    wheel, bundle = _canonical_fixture_paths()
    if wheel is None or bundle is None:
        pytest.skip(_SKIP_FIXTURE_PENDING)
    mod = _load_verify_release_module()
    result = mod.check_wheel_signature(
        version="0.6.0-rc1",
        cert_oidc_issuer=EXPECTED_ISSUER,
        bundle_path=bundle,
        artifact_path=wheel,
    )
    assert result.ok is True, result.diagnostic


def test_missing_issuer_refused() -> None:
    """SIGN-04 (D-04): main() refuses to run without --cert-oidc-issuer."""
    mod = _load_verify_release_module()
    with pytest.raises(SystemExit) as exc_info:
        mod.main(["--version", "0.6.0-rc1"])
    assert exc_info.value.code == 2, (
        f"argparse required=True must exit with code 2 when "
        f"--cert-oidc-issuer is missing; got {exc_info.value.code}."
    )


def test_wrong_issuer_refused(capsys: pytest.CaptureFixture[str]) -> None:
    """SIGN-04 (D-04): main() refuses on a mismatched --cert-oidc-issuer value."""
    mod = _load_verify_release_module()
    exit_code = mod.main(
        [
            "--version",
            "0.6.0-rc1",
            "--cert-oidc-issuer",
            "https://example.com/oauth",
        ]
    )
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert exit_code != 0, (
        "main() must refuse a mismatched issuer with a non-zero exit code (D-04 hard rule)."
    )
    assert EXPECTED_ISSUER in combined, (
        f"Diagnostic must reference the expected issuer "
        f"{EXPECTED_ISSUER!r} so the caller sees what the script "
        f"requires."
    )


def test_sbom_stub_returns_skipped() -> None:
    """SIGN-04 (D-08): sbom-signature check is a wired stub returning ok=None."""
    mod = _load_verify_release_module()
    result = mod.check_sbom_signature(version="0.6.0-rc1")
    assert result.ok is None, (
        "SBOM check must return ok=None (SKIPPED) per D-08 until Phase "
        "53 lands SBOM generation + signing."
    )
    assert "SKIPPED" in result.diagnostic, (
        f"SBOM stub diagnostic must contain 'SKIPPED'; got: {result.diagnostic!r}"
    )
    assert "Phase 53" in result.diagnostic, (
        f"SBOM stub diagnostic must reference 'Phase 53' so the "
        f"maintainer reading the report knows where the active check "
        f"lands; got: {result.diagnostic!r}"
    )


def test_full_run_all_checks_with_canonical_fixture() -> None:
    """SIGN-04: full main() invocation across the 5 checks exits 0 on success.

    Skipped checks (ok=None) do NOT count as failure per release_gate
    precedent.
    """
    wheel, bundle = _canonical_fixture_paths()
    if wheel is None or bundle is None:
        pytest.skip(_SKIP_FIXTURE_PENDING)
    mod = _load_verify_release_module()
    exit_code = mod.main(
        [
            "--version",
            "0.6.0-rc1",
            "--cert-oidc-issuer",
            EXPECTED_ISSUER,
            "--bundle",
            str(bundle),
            "--artifact",
            str(wheel),
        ]
    )
    assert exit_code == 0, (
        f"main() must exit 0 when all non-skipped checks pass; got exit_code={exit_code}."
    )


# ---------------------------------------------------------------------------
# Wave 0 helper tests (PASS or cleanly SKIP in absence of scripts/verify_release.py)
# ---------------------------------------------------------------------------


def test_expected_identity_template_invariant_is_documented() -> None:
    """PITFALL 1 (wildcard identity) defense: the {version} placeholder substring is present.

    Scans the committed scripts/verify_release.py source for the
    literal ``'refs/tags/{version}'`` substring. Skips cleanly if
    Plan 02 has not yet landed the script. Plan 02 lands the
    module-import-time assertion that enforces this in production.
    """
    if not VERIFY_RELEASE_SCRIPT.is_file():
        pytest.skip(
            f"scripts/verify_release.py absent; Plan 02 (Wave 1) lands "
            f"it. Expected at "
            f"{VERIFY_RELEASE_SCRIPT.relative_to(REPO_ROOT)}."
        )
    source = VERIFY_RELEASE_SCRIPT.read_text(encoding="utf-8")
    assert "refs/tags/{version}" in source, (
        "scripts/verify_release.py must contain the literal "
        "'refs/tags/{version}' substring inside EXPECTED_IDENTITY_"
        "TEMPLATE. PITFALL 1 (wildcard-identity bug class) is "
        "defended against at module-import time via the invariant "
        "assertion."
    )


def test_expected_issuer_constant_documented() -> None:
    """SIGN-04 (D-04): the EXPECTED_ISSUER constant string is present in source."""
    if not VERIFY_RELEASE_SCRIPT.is_file():
        pytest.skip(
            f"scripts/verify_release.py absent; Plan 02 (Wave 1) lands "
            f"it. Expected at "
            f"{VERIFY_RELEASE_SCRIPT.relative_to(REPO_ROOT)}."
        )
    source = VERIFY_RELEASE_SCRIPT.read_text(encoding="utf-8")
    assert EXPECTED_ISSUER in source, (
        f"scripts/verify_release.py must contain the literal "
        f"{EXPECTED_ISSUER!r} as the EXPECTED_ISSUER module-level "
        f"constant (D-04 hard rule; hardcoded, no JSON config drift)."
    )


def test_module_imports_cleanly() -> None:
    """SIGN-04 (D-04): the module loads and exposes the byte-exact constants."""
    mod = _load_verify_release_module()
    actual_template = getattr(mod, "EXPECTED_IDENTITY_TEMPLATE", None)
    actual_issuer = getattr(mod, "EXPECTED_ISSUER", None)
    assert actual_template == EXPECTED_IDENTITY_TEMPLATE, (
        f"EXPECTED_IDENTITY_TEMPLATE drift: expected "
        f"{EXPECTED_IDENTITY_TEMPLATE!r}, got {actual_template!r}. "
        f"D-04 pins this constant byte-exact."
    )
    assert actual_issuer == EXPECTED_ISSUER, (
        f"EXPECTED_ISSUER drift: expected {EXPECTED_ISSUER!r}, got "
        f"{actual_issuer!r}. D-04 pins this constant byte-exact."
    )


def test_script_runs_via_subprocess() -> None:
    """Optional Pattern C end-to-end smoke (mirrors test_lint_no_wallclock.py:20-32).

    Shells out to scripts/verify_release.py via sys.executable with
    cross-OS-safe str(path) on every arg position (Shared Pattern
    S-1). Asserts the script collects + dispatches the sbom check
    and produces a SKIP line.
    """
    if not VERIFY_RELEASE_SCRIPT.is_file():
        pytest.skip(
            f"scripts/verify_release.py absent; Plan 02 (Wave 1) lands "
            f"it. Expected at "
            f"{VERIFY_RELEASE_SCRIPT.relative_to(REPO_ROOT)}."
        )
    result = subprocess.run(
        [
            sys.executable,
            str(VERIFY_RELEASE_SCRIPT),
            "--version",
            "0.6.0-rc1",
            "--cert-oidc-issuer",
            EXPECTED_ISSUER,
            "--check",
            "sbom",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"verify_release.py --check sbom must exit 0 (the SBOM stub "
        f"is SKIPPED, not FAILED). Got returncode="
        f"{result.returncode}; stderr={result.stderr!r}"
    )
    assert "SKIP" in result.stdout, (
        f"verify_release.py --check sbom must emit a SKIP line for "
        f"the stubbed SBOM check (D-08). Got stdout={result.stdout!r}"
    )
    assert "sbom-signature" in result.stdout, (
        f"verify_release.py --check sbom output must name the "
        f"'sbom-signature' check identifier. Got "
        f"stdout={result.stdout!r}"
    )
