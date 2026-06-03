"""Phase 53 SUPPLY-01 + SUPPLY-02 + SUPPLY-04 structural workflow lint for .github/workflows/audit.yml.

Wave 0 RED-by-design: production assertions fail until Plan 02 creates
.github/workflows/audit.yml with the documented shape. Non-vacuity tests
prove each scanner fires on synthetic violations written to tmp_path.

Shared pattern S-1: subprocess uses sys.executable + str(path) (none here,
but discipline preserved). Shared pattern S-2: read_text uses encoding=utf-8.
No em-dashes anywhere (CLAUDE.md HR3).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AUDIT_YML_PATH = REPO_ROOT / ".github" / "workflows" / "audit.yml"

# Mirrors tests/test_contribution_gate_pitfalls/test_pitfall_02_action_sha_pinning.py
_USES_PATTERN = re.compile(r"^\s*-?\s*uses:\s*([^@\s#]+)@(\S+)")
_ALLOWED_REF = re.compile(r"^[0-9a-f]{40}$")


def _read_audit_yml() -> str:
    if not AUDIT_YML_PATH.is_file():
        raise FileNotFoundError(
            f"Phase 53 Plan 02 (Wave 1) must create {AUDIT_YML_PATH} per SUPPLY-01. "
            "This is a RED-by-design Wave 0 production assertion."
        )
    return AUDIT_YML_PATH.read_text(encoding="utf-8")


def _scan_uses_lines(text: str) -> list[tuple[str, str]]:
    """Return (action_path, ref) for every non-comment uses: line."""
    pairs: list[tuple[str, str]] = []
    for line in text.splitlines():
        if line.strip().startswith("#"):
            continue
        match = _USES_PATTERN.match(line)
        if match is None:
            continue
        pairs.append((match.group(1), match.group(2)))
    return pairs


def _scan_has_permissions_read_all(text: str) -> bool:
    return re.search(r"^permissions:\s*read-all\s*$", text, re.MULTILINE) is not None


def _scan_has_id_token_write(text: str) -> bool:
    """True if any non-comment line contains 'id-token: write'.

    Comment-only lines are skipped so prose in the file header documenting
    why id-token: write is forbidden does not register as a violation
    (mirrors the comment-skip discipline in tests/test_contribution_gate_pitfalls
    /test_pitfall_02_action_sha_pinning.py lines 49-52).
    """
    for line in text.splitlines():
        if line.strip().startswith("#"):
            continue
        if "id-token: write" in line:
            return True
    return False


def _scan_dual_mode_pip_audit(text: str) -> tuple[bool, bool]:
    return ("-s osv" in text, "-s pypi" in text)


def _scan_matrix_extras(text: str) -> bool:
    return "strategy:" in text and "matrix:" in text and "[dev]" in text and "[dev,otel]" in text


def _scan_dependency_review_allowlist(text: str) -> list[str]:
    """Return missing license literals from the allowlist."""
    required = ["Apache-2.0", "MIT", "BSD-2-Clause", "BSD-3-Clause", "ISC", "PSF-2.0"]
    return [lic for lic in required if lic not in text]


# Production assertions: RED until Plan 02 creates audit.yml.


def test_audit_yml_exists() -> None:
    assert AUDIT_YML_PATH.is_file(), (
        f"Phase 53 Plan 02 (Wave 1) must create {AUDIT_YML_PATH} per SUPPLY-01"
    )


def test_on_pull_request_trigger() -> None:
    text = _read_audit_yml()
    assert re.search(r"on:\s*\n\s*pull_request\s*:?", text, re.MULTILINE), (
        "SUPPLY-01: audit.yml must trigger on pull_request (not pull_request_target)"
    )
    assert "pull_request_target" not in text, (
        "CIHARD-01: pull_request_target is forbidden in v0.6 (PITFALL 1 fork-PR secret leak)"
    )


def test_top_level_permissions_read_all() -> None:
    text = _read_audit_yml()
    assert _scan_has_permissions_read_all(text), (
        "SUPPLY-01 + CIHARD-02: audit.yml must declare top-level permissions: read-all"
    )


def test_no_id_token_write_anywhere() -> None:
    text = _read_audit_yml()
    assert not _scan_has_id_token_write(text), (
        "SUPPLY-01 PITFALL: audit.yml MUST NOT grant id-token: write (runs on fork PRs; "
        "would let fork PRs mint sigstore identities). OIDC stays in release.yml only."
    )


def test_pip_audit_action_present() -> None:
    text = _read_audit_yml()
    assert "pypa/gh-action-pip-audit" in text, (
        "SUPPLY-01: audit.yml must invoke pypa/gh-action-pip-audit"
    )


def test_pip_audit_action_sha_pinned() -> None:
    text = _read_audit_yml()
    pairs = _scan_uses_lines(text)
    pip_audit_refs = [ref for path, ref in pairs if "pypa/gh-action-pip-audit" in path]
    assert pip_audit_refs, "SUPPLY-01: no pypa/gh-action-pip-audit uses: line found"
    for ref in pip_audit_refs:
        assert _ALLOWED_REF.match(ref), (
            f"CIHARD-04: pypa/gh-action-pip-audit must be SHA-pinned (40-char hex); got {ref!r}"
        )


def test_pip_audit_dual_mode() -> None:
    text = _read_audit_yml()
    has_osv, has_pypi = _scan_dual_mode_pip_audit(text)
    assert has_osv, "SUPPLY-01: audit.yml must run pip-audit with -s osv"
    assert has_pypi, "SUPPLY-01: audit.yml must run pip-audit with -s pypi"


def test_two_variant_matrix() -> None:
    text = _read_audit_yml()
    assert _scan_matrix_extras(text), (
        "SUPPLY-04: audit.yml must use strategy.matrix.extras over [dev] AND [dev,otel] "
        "(mirrors install-smoke-no-otel + install-smoke-with-otel two-variant pattern)"
    )


def test_dependency_review_action_present() -> None:
    text = _read_audit_yml()
    assert "actions/dependency-review-action" in text, (
        "SUPPLY-02: audit.yml must invoke actions/dependency-review-action"
    )


def test_dependency_review_action_sha_pinned() -> None:
    text = _read_audit_yml()
    pairs = _scan_uses_lines(text)
    dep_refs = [ref for path, ref in pairs if "actions/dependency-review-action" in path]
    assert dep_refs, "SUPPLY-02: no actions/dependency-review-action uses: line found"
    for ref in dep_refs:
        assert _ALLOWED_REF.match(ref), (
            f"CIHARD-04: actions/dependency-review-action must be SHA-pinned; got {ref!r}"
        )


def test_dependency_review_license_allowlist() -> None:
    text = _read_audit_yml()
    missing = _scan_dependency_review_allowlist(text)
    assert not missing, (
        f"SUPPLY-02: audit.yml dependency-review missing license literals: {missing}. "
        "Required: Apache-2.0, MIT, BSD-2-Clause, BSD-3-Clause, ISC, PSF-2.0"
    )
    assert "allow-licenses" in text, "SUPPLY-02: dependency-review must use allow-licenses"


def test_dependency_review_comment_on_failure() -> None:
    text = _read_audit_yml()
    assert "comment-summary-in-pr: on-failure" in text, (
        "SUPPLY-02: dependency-review must comment-summary-in-pr on-failure "
        "(PR comment naming the offending dep + license)"
    )


def test_persist_credentials_false() -> None:
    text = _read_audit_yml()
    assert "persist-credentials: false" in text, (
        "CIHARD-03: actions/checkout in audit.yml must set persist-credentials: false"
    )


def test_every_uses_in_audit_yml_sha_pinned() -> None:
    text = _read_audit_yml()
    pairs = _scan_uses_lines(text)
    offenders = [(p, r) for p, r in pairs if not p.startswith("./") and not _ALLOWED_REF.match(r)]
    assert not offenders, (
        "CIHARD-04: every uses: line in audit.yml must be SHA-pinned (40-char hex). "
        f"Offenders: {offenders}"
    )


# Non-vacuity scanner tests: pass NOW; prove each scanner fires on synthetic violations.


def test_scanner_catches_synthetic_missing_permissions(tmp_path: Path) -> None:
    """The permissions-read-all scanner flags a workflow that omits the line."""
    synthetic = tmp_path / "fake.yml"
    synthetic.write_text(
        "name: fake\non:\n  pull_request:\njobs:\n  x:\n    runs-on: ubuntu-latest\n",
        encoding="utf-8",
    )
    text = synthetic.read_text(encoding="utf-8")
    assert not _scan_has_permissions_read_all(text), (
        "Non-vacuity: scanner must flag a workflow that omits 'permissions: read-all'"
    )


def test_scanner_catches_synthetic_id_token_write(tmp_path: Path) -> None:
    """The no-id-token-write scanner flags a workflow that contains the literal."""
    synthetic = tmp_path / "fake.yml"
    synthetic.write_text(
        "jobs:\n  x:\n    permissions:\n      id-token: write\n",
        encoding="utf-8",
    )
    text = synthetic.read_text(encoding="utf-8")
    assert _scan_has_id_token_write(text), (
        "Non-vacuity: scanner must flag a workflow containing 'id-token: write'"
    )


def test_scanner_catches_synthetic_mutable_tag(tmp_path: Path) -> None:
    """The SHA-pin scanner flags a uses: line with a mutable tag."""
    synthetic = tmp_path / "fake.yml"
    synthetic.write_text(
        "jobs:\n  x:\n    steps:\n      - uses: pypa/gh-action-pip-audit@v1\n",
        encoding="utf-8",
    )
    text = synthetic.read_text(encoding="utf-8")
    pairs = _scan_uses_lines(text)
    assert pairs, "Non-vacuity: scanner must extract uses: lines"
    assert any(
        "pypa/gh-action-pip-audit" in path and not _ALLOWED_REF.match(ref) for path, ref in pairs
    ), "Non-vacuity: scanner must flag mutable tag 'v1' on pypa/gh-action-pip-audit"


def test_scanner_catches_synthetic_missing_dual_mode(tmp_path: Path) -> None:
    """The dual-mode scanner flags a workflow that omits one of -s osv / -s pypi."""
    synthetic = tmp_path / "fake.yml"
    synthetic.write_text(
        "jobs:\n  pip-audit:\n    steps:\n      - run: pip-audit -s osv\n",
        encoding="utf-8",
    )
    text = synthetic.read_text(encoding="utf-8")
    has_osv, has_pypi = _scan_dual_mode_pip_audit(text)
    assert has_osv and not has_pypi, (
        "Non-vacuity: scanner must flag absence of '-s pypi' when only '-s osv' present"
    )
