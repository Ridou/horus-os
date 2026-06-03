"""Pitfall 3 (PITFALLS.md): sigstore identity is wildcard, regex, or repo-scoped.

The trap: sigstore-python verification uses EXACT MATCH on --cert-identity
(no regex, no wildcards). A reviewer who learned cosign's --certificate-
identity-regexp shape and reaches for sigstore-python gets the wrong
semantics; a too-permissive identity (e.g., the OIDC issuer alone) lets
ANY GitHub-signed sigstore signature pass, including an attacker's
signature from THEIR repo using THEIR workflow.

This regression pins the EXPECTED_IDENTITY_TEMPLATE shape in
scripts/verify_release.py:

1. The template is workflow-scoped (contains `.github/workflows/release.yml`).
2. The template is tag-scoped (contains `refs/tags/{version}` placeholder).
3. The template contains NO `*` wildcard.
4. The template contains NO regex metacharacter (`[`, `]`, `(`, `)`, `.+`, `.*`).
5. The template is repo-scoped to `Ridou/horus-os` (no other repo path).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFY_RELEASE_PATH = REPO_ROOT / "scripts" / "verify_release.py"


def _load_expected_identity_template() -> str:
    text = VERIFY_RELEASE_PATH.read_text(encoding="utf-8")
    match = re.search(r'EXPECTED_IDENTITY_TEMPLATE\s*=\s*\(?\s*"([^"]+)"', text)
    assert match is not None, "EXPECTED_IDENTITY_TEMPLATE not found in verify_release.py"
    return match.group(1)


def test_identity_template_is_workflow_scoped() -> None:
    """Pitfall 3 / Hard rule: identity must reference the exact workflow file."""
    template = _load_expected_identity_template()
    assert ".github/workflows/release.yml" in template, (
        f"Pitfall 3: EXPECTED_IDENTITY_TEMPLATE must be workflow-scoped; got {template!r}"
    )


def test_identity_template_is_tag_scoped() -> None:
    """Pitfall 3: identity must include the refs/tags/{version} placeholder."""
    template = _load_expected_identity_template()
    assert "refs/tags/{version}" in template, (
        f"Pitfall 3: EXPECTED_IDENTITY_TEMPLATE must be tag-scoped with the "
        f"{{version}} placeholder; got {template!r}"
    )


def test_identity_template_has_no_wildcard() -> None:
    """Pitfall 3: no `*` wildcard (sigstore-python uses EXACT match, not regex)."""
    template = _load_expected_identity_template()
    assert "*" not in template, (
        f"Pitfall 3: EXPECTED_IDENTITY_TEMPLATE must not contain `*` wildcards; "
        f"sigstore-python verification uses exact match; got {template!r}"
    )


def test_identity_template_has_no_regex_metachars() -> None:
    """Pitfall 3: no regex metacharacters (sigstore-python is not regex-aware)."""
    template = _load_expected_identity_template()
    forbidden = ("[", "]", "(", ")", ".+", ".*", "?:", "(?")
    found = [m for m in forbidden if m in template]
    assert not found, (
        f"Pitfall 3: EXPECTED_IDENTITY_TEMPLATE contains regex metacharacter(s) "
        f"{found}; sigstore-python uses exact match: {template!r}"
    )


def test_identity_template_is_repo_scoped_to_horus_os() -> None:
    """Pitfall 3: identity must point at Ridou/horus-os (load-bearing repo binding)."""
    template = _load_expected_identity_template()
    assert "Ridou/horus-os" in template, (
        f"Pitfall 3: EXPECTED_IDENTITY_TEMPLATE must bind the Ridou/horus-os repo; got {template!r}"
    )
