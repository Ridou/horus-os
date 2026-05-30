"""Pitfall 9 (PITFALLS.md): PyPI Trusted Publishing not wired before flip; long-lived token leaks.

The trap: the first v0.6 release uses a long-lived PYPI_API_TOKEN secret
because Trusted Publishing wasn't wired in time. The first leak rotates
the token; the second leak (because the same maintainer made the same
mistake on a side project) gives an attacker a token-publish window.

v0.6's decision: NO PyPI publishing at all (the release is GitHub
Releases + sigstore-signed artifacts only). PyPI Trusted Publishing
is deferred to v0.7. The pyproject.toml and release.yml must both
reflect this: zero PYPI_API_TOKEN references, zero `pypi-publish`
action invocations.

The decision is documented in .planning/decisions/no-pypi-in-v0.6.md.

This regression pins:
1. release.yml contains zero PYPI_* secret references.
2. release.yml contains zero pypi-publish action invocations.
3. The decision file exists.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
NO_PYPI_DECISION = REPO_ROOT / ".planning" / "decisions" / "no-pypi-in-v0.6.md"


def test_no_workflow_references_pypi_secret() -> None:
    """No workflow references a PYPI_* secret (no long-lived publish token)."""
    offenders: list[tuple[str, int, str]] = []
    for workflow in sorted(WORKFLOWS_DIR.glob("*.yml")):
        text = workflow.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "PYPI_API_TOKEN" in line or "PYPI_TOKEN" in line or "secrets.PYPI" in line:
                offenders.append((workflow.name, line_number, line.rstrip()))
    assert not offenders, (
        "Pitfall 9: no workflow may reference a PYPI_* secret in v0.6 "
        "(PyPI publishing deferred to v0.7 with Trusted Publishing). Offenders:\n"
        + "\n".join(f"  {n}:{ln}: {text}" for n, ln, text in offenders)
    )


def test_no_workflow_uses_pypi_publish_action() -> None:
    """No workflow invokes pypa/gh-action-pypi-publish or twine."""
    offenders: list[tuple[str, int, str]] = []
    for workflow in sorted(WORKFLOWS_DIR.glob("*.yml")):
        text = workflow.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "gh-action-pypi-publish" in line or "twine upload" in line:
                offenders.append((workflow.name, line_number, line.rstrip()))
    assert not offenders, (
        "Pitfall 9: no workflow may publish to PyPI in v0.6 "
        "(deferred to v0.7 with Trusted Publishing). Offenders:\n"
        + "\n".join(f"  {n}:{ln}: {text}" for n, ln, text in offenders)
    )


def test_no_pypi_decision_file_exists() -> None:
    """The decision file .planning/decisions/no-pypi-in-v0.6.md must be committed."""
    assert NO_PYPI_DECISION.is_file(), (
        "Pitfall 9: .planning/decisions/no-pypi-in-v0.6.md must document the "
        "v0.6 zero-PyPI rationale + the v0.7 Trusted Publishing migration plan"
    )
