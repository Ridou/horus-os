"""Pitfall 2 (PITFALLS.md): mutable action tag pin is the same as not pinning.

CIHARD-04: every third-party `uses:` is pinned to a 40-char commit SHA.
Allowed forms:
  - foo/bar@<40-hex>     (third-party SHA-pin)
  - ./local-action        (in-repo composite action; allowed)
  - ./<path>              (in-repo composite action; allowed)

Rejected forms:
  - foo/bar@v4            (tag-pin; mutable)
  - foo/bar@main          (branch-pin; mutable)
  - foo/bar@master        (branch-pin; mutable)
  - foo/bar@abc123d       (short SHA; ambiguous)
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

# Captures the (path)@(ref) portion of a `uses:` line. Tolerates leading
# whitespace and the optional list-marker dash. Stops at whitespace or
# the start of a trailing comment.
_USES_PATTERN = re.compile(r"^\s*-?\s*uses:\s*([^@\s#]+)@(\S+)")

# Allowed: either a local action path (starts with ./) or a 40-char hex SHA.
_ALLOWED_REF = re.compile(r"^[0-9a-f]{40}$")


def _is_local_action(path: str) -> bool:
    return path.startswith("./") or path.startswith(".\\")


def _scan_workflow_dir(workflows_dir: Path) -> list[tuple[str, str, str]]:
    """Scan all *.yml files in workflows_dir and return offending (rel_path, action_path, ref).

    Comment-only lines (stripped line starts with '#') are skipped so that
    documentation comments quoting bad pin examples are NOT flagged as violations.
    This mirrors the comment-skip discipline in test_pitfall_01_pull_request_target.py
    for uniform TEST-23 file shapes.
    """
    offenders: list[tuple[str, str, str]] = []
    for workflow in sorted(workflows_dir.glob("*.yml")):
        text = workflow.read_text(encoding="utf-8")
        for line in text.splitlines():
            # Skip comment-only lines so doc comments referencing bad pins
            # (e.g. PITFALLS.md examples) do not create false positives.
            if line.strip().startswith("#"):
                continue
            match = _USES_PATTERN.match(line)
            if match is None:
                continue
            path, ref = match.group(1), match.group(2)
            if _is_local_action(path):
                continue
            if not _ALLOWED_REF.match(ref):
                try:
                    rel = str(workflow.relative_to(workflows_dir.parent.parent))
                except ValueError:
                    rel = str(workflow)
                offenders.append((rel, path, ref))
    return offenders


def test_every_uses_line_is_sha_pinned() -> None:
    """Every `uses:` line in every workflow must be SHA-pinned or local."""
    offenders = _scan_workflow_dir(WORKFLOWS_DIR)
    assert not offenders, (
        "Non-SHA action pins found (CIHARD-04 requires 40-char commit SHA):\n"
        + "\n".join(f"  {p}: {path}@{ref}" for p, path, ref in offenders)
    )


def test_scanner_catches_synthetic_sha_violation(tmp_path: Path) -> None:
    """Non-vacuity: the scanner flags a known bad pin (CIHARD-04 defense).

    A synthetic workflow under tmp_path contains exactly one mutable tag
    pin. The scanner must report exactly one offender referencing the
    action name and the mutable tag, proving the regex is non-vacuous.
    """
    fake_wf_dir = tmp_path / ".github" / "workflows"
    fake_wf_dir.mkdir(parents=True)
    (fake_wf_dir / "fake.yml").write_text(
        "steps:\n  - uses: actions/checkout@v4\n",
        encoding="utf-8",
    )
    offenders = _scan_workflow_dir(fake_wf_dir)
    assert len(offenders) == 1, f"Expected exactly one offender; got {len(offenders)}: {offenders}"
    _rel, action_path, ref = offenders[0]
    assert "actions/checkout" in action_path
    assert "v4" in ref


def test_scanner_accepts_synthetic_local_action_ref(tmp_path: Path) -> None:
    """Non-vacuity: the scanner accepts an in-repo local action (Pitfall 51-C defense).

    A synthetic workflow under tmp_path contains one local action reference
    (./.github/actions/local-foo). The scanner must report zero offenders,
    proving the ./ branch of the allowlist functions correctly.
    """
    fake_wf_dir = tmp_path / ".github" / "workflows"
    fake_wf_dir.mkdir(parents=True)
    (fake_wf_dir / "fake.yml").write_text(
        "steps:\n  - uses: ./.github/actions/local-foo\n",
        encoding="utf-8",
    )
    offenders = _scan_workflow_dir(fake_wf_dir)
    assert offenders == [], f"Expected no offenders for local action ref; got: {offenders}"
