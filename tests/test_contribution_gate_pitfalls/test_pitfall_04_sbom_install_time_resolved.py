"""Pitfall 4 (PITFALLS.md): SBOM lists install-time resolved deps, not the wheel's.

The trap: if cyclonedx-py is run via `cyclonedx-py environment` against the
*dev* venv (which has [dev,otel,all] extras), the resulting SBOM lists
pytest, ruff, etc. as components of the wheel. The published wheel's actual
install does NOT pull those; verification against the wheel fails or
(worse) silently accepts a contaminated SBOM.

The Phase 53 fix: SBOMs are generated against a FRESH `pip install <wheel>`
venv, NOT against the dev venv. This regression pins that:

1. release.yml creates `.venv-sbom-clean` and `.venv-sbom-extras` via
   `python -m venv` (NOT `pip install -e`).
2. The venvs install `dist/*.whl` (clean) or `dist/*.whl[dev,otel]`
   (extras), not the source tree.
3. The cyclonedx-py invocation targets the venv's python, not the dev venv.
4. The 53-followup `check_sbom_matches_wheel` release-gate check is wired
   so a future drift between SBOM and wheel fails the gate before tagging.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RELEASE_YML = REPO_ROOT / ".github" / "workflows" / "release.yml"
RELEASE_GATE = REPO_ROOT / "scripts" / "release_gate.py"


def test_release_yml_uses_fresh_venv_for_sbom() -> None:
    """release.yml MUST create a fresh venv (not reuse dev venv) for SBOM generation."""
    text = RELEASE_YML.read_text(encoding="utf-8")
    assert "python -m venv .venv-sbom-clean" in text, (
        "Pitfall 4: release.yml must create .venv-sbom-clean for the clean SBOM; "
        "found neither the venv-create command nor the SBOM-01 substrate"
    )
    assert "python -m venv .venv-sbom-extras" in text, (
        "Pitfall 4: release.yml must create .venv-sbom-extras for the [dev,otel] SBOM"
    )


def test_release_yml_sbom_installs_wheel_not_source() -> None:
    """The SBOM venvs install dist/*.whl (NOT pip install -e .)."""
    text = RELEASE_YML.read_text(encoding="utf-8")
    # Clean variant: just the wheel
    assert ".venv-sbom-clean/bin/pip install dist/*.whl" in text, (
        "Pitfall 4: clean-SBOM venv must `pip install dist/*.whl` (not -e .)"
    )
    # Extras variant: the wheel with [dev,otel]
    assert ".venv-sbom-extras/bin/pip install 'dist/*.whl[dev,otel]'" in text, (
        "Pitfall 4: extras-SBOM venv must `pip install 'dist/*.whl[dev,otel]'` "
        "(quoted form is correct; pip resolves the glob internally)"
    )


def test_cyclonedx_py_targets_venv_python_not_dev_python() -> None:
    """cyclonedx-py environment <python> must target the SBOM venv, never the dev venv."""
    text = RELEASE_YML.read_text(encoding="utf-8")
    assert ".venv-sbom-clean/bin/cyclonedx-py environment .venv-sbom-clean/bin/python" in text, (
        "Pitfall 4: cyclonedx-py environment scan target must be the SBOM venv's python; "
        "dev-venv targeting would contaminate the SBOM with pytest/ruff/etc."
    )
    assert ".venv-sbom-extras/bin/cyclonedx-py environment .venv-sbom-extras/bin/python" in text


def test_release_gate_wires_sbom_matches_wheel_check() -> None:
    """The 53-followup check_sbom_matches_wheel must be in the release_gate enum."""
    text = RELEASE_GATE.read_text(encoding="utf-8")
    assert '"sbom-matches-wheel"' in text, (
        "Pitfall 4: release_gate.py must expose the sbom-matches-wheel check so "
        "SBOM-vs-wheel drift is caught at release-gate time, not at user-verify time"
    )
    assert "check_sbom_matches_wheel" in text, (
        "Pitfall 4: check_sbom_matches_wheel function missing from release_gate.py"
    )
