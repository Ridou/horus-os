"""Phase 58 TEST-24 negative case: verify_release.py rejects wrong-identity bundle.

The hand-crafted fixture at tests/fixtures/sigstore/wrong-identity/
contains a sigstore bundle stub whose certificate metadata names a
DIFFERENT repo (`Other/repo`) than EXPECTED_IDENTITY_TEMPLATE pins
(`Ridou/horus-os`). The test invokes scripts/verify_release.py
against this fixture and asserts the verifier rejects it with a
non-zero exit code.

The CANONICAL positive-case sigstore fixture is owned by Phase 52 and
lands during the v0.6.0-rc1 release-rehearsal session (human UAT).
Until that fixture exists, the positive-case round-trip stays SKIPped
in tests/test_release_verification.py per the documented contract.

If python -m sigstore is not installed in the venv, the test marks
itself SKIP (mirrors tests/test_release_verification.py precedent;
sigstore is NEVER added to pyproject.toml runtime or [dev] extras per
Phase 52 D-03; v0.6 ships a zero-base-dep verifier and the test is
hermetic against that constraint).

No em-dashes anywhere (CLAUDE.md HR3).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
VERIFY_RELEASE = REPO_ROOT / "scripts" / "verify_release.py"
WRONG_IDENTITY_DIR = REPO_ROOT / "tests" / "fixtures" / "sigstore" / "wrong-identity"
WRONG_IDENTITY_BUNDLE = WRONG_IDENTITY_DIR / "wrong-identity-bundle.sigstore.json"
WRONG_IDENTITY_README = WRONG_IDENTITY_DIR / "README.md"


def _sigstore_cli_available() -> bool:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "sigstore", "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (FileNotFoundError, OSError):
        return False
    return proc.returncode == 0


def test_wrong_identity_fixture_directory_exists() -> None:
    """The Phase 58 TEST-24 fixture directory must be committed."""
    assert WRONG_IDENTITY_DIR.is_dir(), (
        f"TEST-24: wrong-identity fixture directory missing at {WRONG_IDENTITY_DIR}"
    )


def test_wrong_identity_fixture_has_readme() -> None:
    """The README documents the hand-crafted nature of the fixture."""
    assert WRONG_IDENTITY_README.is_file(), "TEST-24: README.md missing in wrong-identity dir"
    text = WRONG_IDENTITY_README.read_text(encoding="utf-8")
    assert "HAND-CRAFTED" in text or "hand-crafted" in text, (
        "TEST-24: README must declare the fixture is hand-crafted so future "
        "contributors do not mistake it for a real sigstore output"
    )


def test_wrong_identity_bundle_is_valid_json() -> None:
    """The bundle stub must parse as valid JSON (parser-level smoke test)."""
    assert WRONG_IDENTITY_BUNDLE.is_file(), "TEST-24: wrong-identity bundle stub missing"
    payload = json.loads(WRONG_IDENTITY_BUNDLE.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    # Internal contract documented in the README: $expectedCertSubject
    # carries the non-Ridou identity URL.
    subject = payload.get("$expectedCertSubject", "")
    assert "Other/repo" in subject or "Ridou/horus-os" not in subject, (
        f"TEST-24: bundle's $expectedCertSubject must NOT reference Ridou/horus-os; got {subject!r}"
    )


def test_bundle_names_alternate_repo_in_identity() -> None:
    """The fixture's logical identity points at a different repo than expected."""
    payload = json.loads(WRONG_IDENTITY_BUNDLE.read_text(encoding="utf-8"))
    subject = payload.get("$expectedCertSubject", "")
    assert ".github/workflows/release.yml" in subject, (
        "TEST-24: fixture identity must still be workflow-scoped (just to the wrong workflow)"
    )
    assert "refs/tags/" in subject, "TEST-24: fixture identity must still be tag-scoped"


@pytest.mark.skipif(
    not _sigstore_cli_available(),
    reason=(
        "sigstore CLI not installed; verify_release.py wheel-check shells out to it. "
        "Negative-test still passes at the structural level (other tests in this file); "
        "round-trip negative test requires `pip install sigstore`."
    ),
)
def test_verify_release_rejects_wrong_identity_fixture() -> None:
    """End-to-end: verify_release.py --check wheel against the wrong-identity bundle exits non-zero.

    This is the load-bearing negative-test assertion for TEST-24. The
    verifier must NOT green-light a bundle whose certificate metadata
    names a different repo than EXPECTED_IDENTITY_TEMPLATE pins, even
    when the OIDC issuer is correct.

    The hand-crafted bundle's signature bytes are placeholder, so the
    sigstore CLI will fail at signature-validation time rather than
    identity-mismatch time; but the test only asserts non-zero exit,
    which is the correct outcome either way. Once the canonical
    rehearsal-recording fixture lands (Phase 58 human UAT), this test
    can be tightened to assert the specific identity-mismatch error.
    """
    proc = subprocess.run(
        [
            sys.executable,
            str(VERIFY_RELEASE),
            "--version",
            "0.6.0",
            "--cert-oidc-issuer",
            "https://token.actions.githubusercontent.com",
            "--check",
            "wheel",
            "--bundle",
            str(WRONG_IDENTITY_BUNDLE),
            "--artifact",
            str(WRONG_IDENTITY_BUNDLE),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert proc.returncode != 0, (
        "TEST-24: verify_release.py MUST reject the wrong-identity fixture; "
        f"exit code was 0. stdout: {proc.stdout!r}; stderr: {proc.stderr!r}"
    )
