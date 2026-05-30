"""Phase 53 SUPPLY-03 lint for .github/pip-audit-ignore.txt + .github/pip-audit-tracking/.

Wave 0 RED-by-design: production assertions fail until Plan 02 creates the ignore
file + tracking directory. Non-vacuity parser tests pass NOW via tmp_path fixtures.

The discipline: every CVE / GHSA / PYSEC entry in the ignore file MUST be
preceded by a comment of the form `# YYYY-MM-DD: <reason>`. Undated entries
are rejected by the Phase 57 release-gate local-pip-audit-clean check.

No em-dashes anywhere (CLAUDE.md HR3).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
IGNORE_PATH = REPO_ROOT / ".github" / "pip-audit-ignore.txt"
TRACKING_DIR = REPO_ROOT / ".github" / "pip-audit-tracking"
TRACKING_README = TRACKING_DIR / "README.md"

_ID_PATTERN = re.compile(r"^(CVE-\d+-\d+|GHSA-[a-zA-Z0-9-]+|PYSEC-\d+-\d+)$")
_DATED_COMMENT_PATTERN = re.compile(r"^\s*\d{4}-\d{2}-\d{2}\s*:\s*.+")


def _parse_ignore_file(text: str) -> list[tuple[int, str, str | None]]:
    """Return (line_number, entry, preceding_comment_body_or_None) for every ID line.

    The preceding comment is the immediately-preceding `#`-line stripped of `#`.
    None when the line directly before is not a comment.
    """
    lines = text.splitlines()
    results: list[tuple[int, str, str | None]] = []
    for idx, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not _ID_PATTERN.match(stripped):
            continue
        # Look at the immediately-preceding line
        preceding: str | None = None
        if idx > 0:
            prev = lines[idx - 1].strip()
            if prev.startswith("#"):
                preceding = prev.lstrip("#").lstrip()
        results.append((idx + 1, stripped, preceding))
    return results


# Production assertions: RED until Plan 02 creates the files.


def test_ignore_file_exists() -> None:
    assert IGNORE_PATH.is_file(), (
        f"SUPPLY-03: Plan 02 must create {IGNORE_PATH} with format-documentation header"
    )


def test_tracking_dir_exists() -> None:
    assert TRACKING_DIR.is_dir(), (
        f"SUPPLY-03: Plan 02 must create {TRACKING_DIR}/ for per-CVE tracking docs"
    )


def test_tracking_readme_exists() -> None:
    assert TRACKING_README.is_file(), (
        f"SUPPLY-03: Plan 02 must create {TRACKING_README} documenting the per-CVE convention"
    )


def test_every_entry_has_dated_comment() -> None:
    text = IGNORE_PATH.read_text(encoding="utf-8") if IGNORE_PATH.is_file() else ""
    if not text:
        # File missing or empty; covered by test_ignore_file_exists
        return
    entries = _parse_ignore_file(text)
    offenders = [
        (line_num, entry, preceding)
        for line_num, entry, preceding in entries
        if preceding is None or not _DATED_COMMENT_PATTERN.match(preceding)
    ]
    assert not offenders, (
        "SUPPLY-03: every CVE/GHSA/PYSEC entry must be preceded by a "
        "'# YYYY-MM-DD: <reason>' comment line. Offenders:\n"
        + "\n".join(f"  line {ln}: {entry} (preceding: {pre!r})" for ln, entry, pre in offenders)
    )


def test_tracking_readme_documents_convention() -> None:
    if not TRACKING_README.is_file():
        return  # covered by test_tracking_readme_exists
    text = TRACKING_README.read_text(encoding="utf-8")
    for literal in ("YYYY-MM-DD", "CVE", "pip-audit-ignore.txt", "transitive"):
        assert literal in text, f"SUPPLY-03: tracking README must document the literal '{literal}'"


def test_at_launch_ignore_file_may_be_empty_but_format_documented() -> None:
    if not IGNORE_PATH.is_file():
        return
    text = IGNORE_PATH.read_text(encoding="utf-8")
    assert text.strip(), (
        "SUPPLY-03: ignore file must be non-empty (header comment block documents format)"
    )
    # First non-blank line must be a comment
    for line in text.splitlines():
        if line.strip():
            assert line.lstrip().startswith("#"), (
                f"SUPPLY-03: first non-blank line of ignore file must be a '#'-comment "
                f"(format documentation header); got {line!r}"
            )
            break


# Non-vacuity parser tests: pass NOW.


def test_parser_catches_undated_entry(tmp_path: Path) -> None:
    synthetic = tmp_path / "fake.txt"
    synthetic.write_text(
        "# no date here\nCVE-2025-12345\n",
        encoding="utf-8",
    )
    text = synthetic.read_text(encoding="utf-8")
    entries = _parse_ignore_file(text)
    assert len(entries) == 1
    _, _, preceding = entries[0]
    assert preceding == "no date here"
    assert not _DATED_COMMENT_PATTERN.match(preceding), (
        "Non-vacuity: parser must reject undated comment as not matching the dated format"
    )


def test_parser_catches_orphan_entry(tmp_path: Path) -> None:
    synthetic = tmp_path / "fake.txt"
    synthetic.write_text("\n\nCVE-2025-99999\n", encoding="utf-8")
    text = synthetic.read_text(encoding="utf-8")
    entries = _parse_ignore_file(text)
    assert len(entries) == 1
    _, _, preceding = entries[0]
    assert preceding is None, (
        "Non-vacuity: parser must flag orphan entry with no preceding comment as preceding=None"
    )


def test_parser_accepts_well_formed_entry(tmp_path: Path) -> None:
    synthetic = tmp_path / "fake.txt"
    synthetic.write_text(
        "# 2026-03-15: awaiting urllib3 1.27 release tracking issue #1234\nGHSA-abcd-1234-efgh\n",
        encoding="utf-8",
    )
    text = synthetic.read_text(encoding="utf-8")
    entries = _parse_ignore_file(text)
    assert len(entries) == 1
    _, _, preceding = entries[0]
    assert preceding is not None
    assert _DATED_COMMENT_PATTERN.match(preceding), (
        f"Non-vacuity: parser must accept well-formed dated comment; got {preceding!r}"
    )
