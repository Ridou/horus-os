"""Pitfall 11 (PITFALLS.md): signed tag + unsigned Release artifacts breaks trust chain.

The trap: the maintainer signs the git tag with gitsign but forgets to
attach .sigstore bundles for every published artifact. A downstream user
who runs `git verify-tag v0.6.0` sees green; runs sigstore-verify on the
wheel and sees no bundle at all. The trust chain is half-built; an
attacker who substitutes a fake wheel into the Release page passes the
tag-verify check trivially.

The Phase 52 + 53 fix: release.yml signs EVERY artifact (wheel, sdist,
both SBOMs) in the same job that builds them, via
sigstore/gh-action-sigstore-python with release-signing-artifacts: true.
The user-facing scripts/verify_release.py runs FIVE checks (wheel,
sdist, tag, sbom, changelog) so a missing bundle fails the chain.

This regression pins:
1. release.yml signs wheel + sdist + both .cdx.json SBOMs (the
   `inputs:` glob is broad enough to include all four).
2. release-signing-artifacts: true is set (uploads the bundles to
   the GitHub Release page).
3. verify_release.py exposes all five checks in its CLI.
4. release_gate.py has BOTH release-workflow-signing-present AND
   release-workflow-sbom-present checks (catches "signing wired
   but SBOM forgotten" and vice versa).
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RELEASE_YML = REPO_ROOT / ".github" / "workflows" / "release.yml"
VERIFY_RELEASE = REPO_ROOT / "scripts" / "verify_release.py"
RELEASE_GATE = REPO_ROOT / "scripts" / "release_gate.py"


def test_release_yml_signs_all_four_artifact_types() -> None:
    """The sigstore step's inputs: must cover .whl + .tar.gz + .cdx.json."""
    text = RELEASE_YML.read_text(encoding="utf-8")
    # The Phase 53 inputs glob: ./dist/*.whl ./dist/*.tar.gz ./dist/*.cdx.json
    assert "*.whl" in text and "*.tar.gz" in text and "*.cdx.json" in text, (
        "Pitfall 11: release.yml sigstore step must sign all four artifact types "
        "(wheel + sdist + both SBOMs); inputs glob is incomplete"
    )


def test_release_yml_uploads_signing_artifacts() -> None:
    """release-signing-artifacts: true uploads the .sigstore bundles to the Release page."""
    text = RELEASE_YML.read_text(encoding="utf-8")
    assert "release-signing-artifacts: true" in text, (
        "Pitfall 11: sigstore action must set release-signing-artifacts: true "
        "so .sigstore bundles attach to the GitHub Release page"
    )


def test_verify_release_exposes_all_five_checks() -> None:
    """scripts/verify_release.py --check enum must include all five checks."""
    text = VERIFY_RELEASE.read_text(encoding="utf-8")
    for check in ("wheel", "sdist", "tag", "sbom", "changelog"):
        assert f'"{check}"' in text, f"Pitfall 11: verify_release.py --check enum missing {check!r}"


def test_release_gate_has_both_signing_and_sbom_checks() -> None:
    """release_gate.py asserts BOTH signing and SBOM substrate are present."""
    text = RELEASE_GATE.read_text(encoding="utf-8")
    assert '"release-workflow-signing-present"' in text, (
        "Pitfall 11: release_gate.py missing release-workflow-signing-present check"
    )
    assert '"release-workflow-sbom-present"' in text, (
        "Pitfall 11: release_gate.py missing release-workflow-sbom-present check"
    )
