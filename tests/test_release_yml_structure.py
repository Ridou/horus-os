"""SIGN-01 + SIGN-02 (Phase 52 Wave 0 RED-by-design): structural .github/workflows/release.yml lint.

Nine structural assertions against `.github/workflows/release.yml`:

1. test_release_yml_exists: the file is present.
2. test_on_release_published_trigger: the workflow triggers on
   `on: release: types: [published]` (the only allowed trigger
   per D-01 and ROADMAP success criterion #1).
3. test_top_level_permissions_read_all: `permissions: read-all`
   appears at column 0 above `jobs:` (CIHARD-02 placement).
4. test_per_job_id_token_write: the `sign-and-attest` job has the
   three per-job permissions `id-token: write`, `contents: write`,
   and `attestations: write` (D-02 per-job opt-in).
5. test_per_artifact_attest: exactly TWO occurrences of
   `uses: actions/attest-build-provenance@` (one wheel + one sdist
   per D-06; Phase 53 widens to three when SBOM lands).
6. test_sigstore_action_literal_present: the literal
   `sigstore/gh-action-sigstore-python` substring is present. Phase
   57's `release-workflow-signing-present` release-gate check greps
   for THIS exact literal.
7. test_sigstore_action_sha_pinned: the sigstore-action `uses:` ref
   is a 40-char hex SHA (CIHARD-04 inheritance).
8. test_sigstore_step_timeout_minutes_5: the sigstore step block
   contains `timeout-minutes: 5` (SIGN-01 OIDC 5-minute budget per
   PITFALL 3).
9. test_every_uses_in_release_yml_sha_pinned: every `uses:` line in
   release.yml is SHA-pinned (CIHARD-04 reuse, scoped to one file).

All nine production assertions are RED-by-design until Plan 02
creates `.github/workflows/release.yml`. Three non-vacuity
synthetic-fixture tests (test_scanner_catches_synthetic_*) PASS NOW
to prove each scanner fires on a known violation written to
tmp_path. Pattern mirrors Phase 51 Plan 01 (51-01-SUMMARY.md
§Non-Vacuity Coverage).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RELEASE_YML_PATH = REPO_ROOT / ".github" / "workflows" / "release.yml"

# Matches `permissions:` at column 0 (workflow-level, not job-level).
_TOP_LEVEL_PERMISSIONS = re.compile(r"^permissions:\s*read-all\s*$", re.MULTILINE)

# Matches the canonical release-published trigger block. Allows whitespace
# flexibility between tokens. Both `release:` and `types: [published]` must
# be present in the on: block.
_ON_RELEASE_PUBLISHED = re.compile(r"on:\s*\n\s*release:\s*\n\s*types:\s*\[\s*published\s*\]")

# Captures the (path)@(ref) portion of a `uses:` line. Mirrors
# tests/test_contribution_gate_pitfalls/test_pitfall_02_action_sha_pinning.py:27.
_USES_PATTERN = re.compile(r"^\s*-?\s*uses:\s*([^@\s#]+)@(\S+)")

# Allowed ref: 40-char hex SHA (CIHARD-04 invariant).
_ALLOWED_REF = re.compile(r"^[0-9a-f]{40}$")

# Substring lookups used by per-job permissions and sigstore checks.
_SIGSTORE_ACTION_LITERAL = "sigstore/gh-action-sigstore-python"
_ATTEST_ACTION_LITERAL = "uses: actions/attest-build-provenance@"


def _is_local_action(path: str) -> bool:
    """Local in-repo composite actions start with `./` (or `.\\` on Windows)."""
    return path.startswith("./") or path.startswith(".\\")


def _scan_release_yml(workflows_dir: Path) -> dict[str, object]:
    """Aggregate scanner over a release.yml-shaped file.

    Returns a dict with keys:
      - missing_permissions: bool (True when top-level permissions: read-all is absent)
      - sha_violations: list of (action_path, ref) tuples for non-SHA-pinned uses lines
      - attest_count: int (count of attest-build-provenance invocations)
      - has_sigstore_literal: bool
      - sigstore_sha_pinned: bool or None (None when the action is absent)
      - sigstore_timeout_5: bool or None (None when the action is absent)

    Comment-only lines are skipped per Shared Pattern S-5
    (mirrors test_pitfall_02_action_sha_pinning.py:49-52 + Phase 51 Plan 01).
    """
    release_yml = workflows_dir / "release.yml"
    if not release_yml.is_file():
        return {
            "missing_permissions": True,
            "sha_violations": [],
            "attest_count": 0,
            "has_sigstore_literal": False,
            "sigstore_sha_pinned": None,
            "sigstore_timeout_5": None,
        }

    text = release_yml.read_text(encoding="utf-8")

    missing_permissions = _TOP_LEVEL_PERMISSIONS.search(text) is None

    sha_violations: list[tuple[str, str]] = []
    sigstore_sha_pinned: bool | None = None
    has_sigstore_literal = _SIGSTORE_ACTION_LITERAL in text
    sigstore_line_index: int | None = None
    for index, line in enumerate(text.splitlines()):
        if line.strip().startswith("#"):
            continue
        match = _USES_PATTERN.match(line)
        if match is None:
            continue
        path, ref = match.group(1), match.group(2)
        if _is_local_action(path):
            continue
        if path == _SIGSTORE_ACTION_LITERAL:
            sigstore_sha_pinned = bool(_ALLOWED_REF.match(ref))
            sigstore_line_index = index
        if not _ALLOWED_REF.match(ref):
            sha_violations.append((path, ref))

    attest_count = text.count(_ATTEST_ACTION_LITERAL)

    sigstore_timeout_5: bool | None = None
    if sigstore_line_index is not None:
        sigstore_timeout_5 = _step_block_contains_timeout_5(text, sigstore_line_index)

    return {
        "missing_permissions": missing_permissions,
        "sha_violations": sha_violations,
        "attest_count": attest_count,
        "has_sigstore_literal": has_sigstore_literal,
        "sigstore_sha_pinned": sigstore_sha_pinned,
        "sigstore_timeout_5": sigstore_timeout_5,
    }


def _step_block_contains_timeout_5(text: str, sigstore_line_index: int) -> bool:
    """Walk the step block containing the sigstore `uses:` line looking for timeout-minutes: 5.

    The block is bounded by the surrounding `- name:` (or `- uses:`) markers.
    Walk backward to the start of the step, then forward to the next step
    boundary, and search inside that span for the literal `timeout-minutes: 5`.
    """
    lines = text.splitlines()
    start = sigstore_line_index
    while start > 0:
        candidate = lines[start - 1].lstrip()
        if candidate.startswith("- name:") or candidate.startswith("- uses:"):
            break
        start -= 1
    if start > 0:
        # Include the boundary line itself in the span.
        start -= 1

    end = sigstore_line_index + 1
    while end < len(lines):
        candidate = lines[end].lstrip()
        if candidate.startswith("- name:") or candidate.startswith("- uses:"):
            break
        end += 1

    block = "\n".join(lines[start:end])
    return "timeout-minutes: 5" in block


# ---------------------------------------------------------------------------
# Production tests (RED-by-design in Wave 0; Plan 02 turns them GREEN)
# ---------------------------------------------------------------------------


def test_release_yml_exists() -> None:
    """SIGN-01 (D-01): the new release.yml workflow file is committed."""
    assert RELEASE_YML_PATH.is_file(), (
        "Phase 52 Plan 02 (Wave 1) must create "
        ".github/workflows/release.yml per SIGN-01 and D-01. "
        f"Expected file at {RELEASE_YML_PATH.relative_to(REPO_ROOT)}."
    )


def test_on_release_published_trigger() -> None:
    """SIGN-01 (D-01): release.yml triggers ONLY on release: types: [published]."""
    if not RELEASE_YML_PATH.is_file():
        raise AssertionError("release.yml missing; Plan 02 must create it per SIGN-01 / D-01.")
    text = RELEASE_YML_PATH.read_text(encoding="utf-8")
    assert _ON_RELEASE_PUBLISHED.search(text) is not None, (
        "release.yml must trigger on 'on: release: types: [published]' "
        "(SIGN-01 / D-01). The 'release: published' trigger preserves the "
        "STOP-BEFORE-TAG human-confirmation gate."
    )


def test_top_level_permissions_read_all() -> None:
    """SIGN-01 (D-02): top-level 'permissions: read-all' is present at column 0."""
    if not RELEASE_YML_PATH.is_file():
        raise AssertionError("release.yml missing; Plan 02 must create it per SIGN-01 / D-02.")
    text = RELEASE_YML_PATH.read_text(encoding="utf-8")
    assert _TOP_LEVEL_PERMISSIONS.search(text) is not None, (
        "release.yml must declare 'permissions: read-all' at column 0 "
        "above 'jobs:' (SIGN-01 / D-02; mirrors Phase 51 ci.yml line 9 "
        "convention). Per-job opt-in lives ONLY on the sign-and-attest job."
    )


def test_per_job_id_token_write() -> None:
    """SIGN-01 (D-02): sign-and-attest job declares the three per-job permissions."""
    if not RELEASE_YML_PATH.is_file():
        raise AssertionError("release.yml missing; Plan 02 must create it per SIGN-01 / D-02.")
    text = RELEASE_YML_PATH.read_text(encoding="utf-8")
    assert "id-token: write" in text, (
        "release.yml sign-and-attest job must include 'id-token: write' "
        "(D-02 per-job opt-in; sigstore-python needs this to mint the "
        "Fulcio cert)."
    )
    assert "contents: write" in text, (
        "release.yml sign-and-attest job must include 'contents: write' "
        "(D-02 per-job opt-in; required for release-signing-artifacts: "
        "true to upload .sigstore bundles to the GitHub Release page)."
    )
    assert "attestations: write" in text, (
        "release.yml sign-and-attest job must include 'attestations: "
        "write' (D-02 per-job opt-in; required for "
        "actions/attest-build-provenance to publish to the attestation "
        "API)."
    )


def test_per_artifact_attest() -> None:
    """SIGN-02 (D-06): TWO per-artifact attest-build-provenance invocations."""
    if not RELEASE_YML_PATH.is_file():
        raise AssertionError("release.yml missing; Plan 02 must create it per SIGN-02 / D-06.")
    text = RELEASE_YML_PATH.read_text(encoding="utf-8")
    count = text.count(_ATTEST_ACTION_LITERAL)
    assert count == 2, (
        f"release.yml must contain EXACTLY TWO occurrences of "
        f"'{_ATTEST_ACTION_LITERAL}' (one wheel + one sdist per D-06 "
        f"per-artifact granularity, NOT a single dist/* glob). "
        f"Found {count}. Phase 53 will widen this to 3 when SBOM "
        f"generation lands."
    )


def test_sigstore_action_literal_present() -> None:
    """SIGN-01 (Phase 57 cross-ref): the sigstore action literal is present."""
    if not RELEASE_YML_PATH.is_file():
        raise AssertionError("release.yml missing; Plan 02 must create it per SIGN-01.")
    text = RELEASE_YML_PATH.read_text(encoding="utf-8")
    assert _SIGSTORE_ACTION_LITERAL in text, (
        f"release.yml must contain the literal "
        f"'{_SIGSTORE_ACTION_LITERAL}' in a 'uses:' line. Phase 57's "
        f"release-gate 'release-workflow-signing-present' check greps "
        f"for THIS exact literal."
    )


def test_sigstore_action_sha_pinned() -> None:
    """SIGN-01 (CIHARD-04 inheritance): the sigstore-action ref is a 40-char hex SHA."""
    if not RELEASE_YML_PATH.is_file():
        raise AssertionError("release.yml missing; Plan 02 must create it per SIGN-01 / CIHARD-04.")
    text = RELEASE_YML_PATH.read_text(encoding="utf-8")
    sigstore_ref: str | None = None
    for line in text.splitlines():
        if line.strip().startswith("#"):
            continue
        match = _USES_PATTERN.match(line)
        if match is None:
            continue
        if match.group(1) == _SIGSTORE_ACTION_LITERAL:
            sigstore_ref = match.group(2)
            break
    assert sigstore_ref is not None, (
        f"Could not locate a 'uses: {_SIGSTORE_ACTION_LITERAL}@<ref>' line in release.yml."
    )
    assert _ALLOWED_REF.match(sigstore_ref) is not None, (
        f"The {_SIGSTORE_ACTION_LITERAL} 'uses:' ref must be a "
        f"40-character hex SHA (CIHARD-04 invariant). Got: "
        f"{sigstore_ref}."
    )


def test_sigstore_step_timeout_minutes_5() -> None:
    """SIGN-01 (PITFALL 3 OIDC TTL budget): sigstore step has timeout-minutes: 5."""
    if not RELEASE_YML_PATH.is_file():
        raise AssertionError("release.yml missing; Plan 02 must create it per SIGN-01.")
    text = RELEASE_YML_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()
    sigstore_line_index: int | None = None
    for index, line in enumerate(lines):
        if line.strip().startswith("#"):
            continue
        match = _USES_PATTERN.match(line)
        if match is None:
            continue
        if match.group(1) == _SIGSTORE_ACTION_LITERAL:
            sigstore_line_index = index
            break
    assert sigstore_line_index is not None, (
        f"Could not locate the {_SIGSTORE_ACTION_LITERAL} step in release.yml."
    )
    assert _step_block_contains_timeout_5(text, sigstore_line_index), (
        "The sigstore-python step must declare 'timeout-minutes: 5' "
        "to bound the OIDC-to-sign chain inside the 10-minute Fulcio "
        "token TTL (SIGN-01 + PITFALL 3)."
    )


def test_every_uses_in_release_yml_sha_pinned() -> None:
    """CIHARD-04 (scoped to release.yml): every uses: line is 40-char SHA-pinned."""
    if not RELEASE_YML_PATH.is_file():
        raise AssertionError("release.yml missing; Plan 02 must create it per CIHARD-04.")
    text = RELEASE_YML_PATH.read_text(encoding="utf-8")
    offenders: list[tuple[str, str]] = []
    for line in text.splitlines():
        if line.strip().startswith("#"):
            continue
        match = _USES_PATTERN.match(line)
        if match is None:
            continue
        path, ref = match.group(1), match.group(2)
        if _is_local_action(path):
            continue
        if not _ALLOWED_REF.match(ref):
            offenders.append((path, ref))
    assert not offenders, (
        "Every 'uses:' in .github/workflows/release.yml must be "
        "SHA-pinned to a 40-char hex commit (CIHARD-04). Offenders:\n"
        + "\n".join(f"  {path}@{ref}" for path, ref in offenders)
    )


# ---------------------------------------------------------------------------
# Non-vacuity tests (synthetic fixtures; all PASS in Wave 0).
# These prove the scanners fire on KNOWN violations written to tmp_path.
# ---------------------------------------------------------------------------


def test_scanner_catches_synthetic_missing_permissions(tmp_path: Path) -> None:
    """Non-vacuity for D-02: scanner flags a release.yml without permissions: read-all."""
    fake_dir = tmp_path / "workflows"
    fake_dir.mkdir(parents=True)
    (fake_dir / "release.yml").write_text(
        "name: Release\n"
        "on:\n"
        "  release:\n"
        "    types: [published]\n"
        "jobs:\n"
        "  sign-and-attest:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@1111111111111111111111111111111111111111\n",
        encoding="utf-8",
    )
    result = _scan_release_yml(fake_dir)
    assert result["missing_permissions"] is True, (
        f"Scanner failed to flag a release.yml missing 'permissions: read-all'. Got: {result}"
    )


def test_scanner_catches_synthetic_sha_violation(tmp_path: Path) -> None:
    """Non-vacuity for CIHARD-04 (release.yml scope): scanner flags a mutable tag pin."""
    fake_dir = tmp_path / "workflows"
    fake_dir.mkdir(parents=True)
    (fake_dir / "release.yml").write_text(
        "name: Release\n"
        "on:\n"
        "  release:\n"
        "    types: [published]\n"
        "permissions: read-all\n"
        "jobs:\n"
        "  sign-and-attest:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@v4\n",
        encoding="utf-8",
    )
    result = _scan_release_yml(fake_dir)
    violations = result["sha_violations"]
    assert isinstance(violations, list)
    assert len(violations) == 1, (
        f"Scanner failed to flag mutable tag pin. Got violations: {violations}"
    )
    path, ref = violations[0]
    assert "actions/checkout" in path
    assert "v4" in ref


def test_scanner_catches_synthetic_missing_attest(tmp_path: Path) -> None:
    """Non-vacuity for D-06: scanner reports attest_count < 2 when one is missing."""
    fake_dir = tmp_path / "workflows"
    fake_dir.mkdir(parents=True)
    (fake_dir / "release.yml").write_text(
        "name: Release\n"
        "on:\n"
        "  release:\n"
        "    types: [published]\n"
        "permissions: read-all\n"
        "jobs:\n"
        "  sign-and-attest:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@1111111111111111111111111111111111111111\n"
        "      - name: Attest wheel\n"
        "        uses: actions/attest-build-provenance@2222222222222222222222222222222222222222\n"
        "        with:\n"
        "          subject-path: 'dist/*.whl'\n",
        encoding="utf-8",
    )
    result = _scan_release_yml(fake_dir)
    assert result["attest_count"] == 1, (
        f"Scanner failed to detect a single attest invocation when D-06 "
        f"requires two (wheel + sdist). Got attest_count={result['attest_count']}."
    )
