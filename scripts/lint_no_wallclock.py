"""Pitfall 3 (PITFALLS.md): forbid time.time() in observability code paths.

Scans the three watched targets:

    src/horus_os/observability/  (all .py files, recursively)
    src/horus_os/agent.py
    src/horus_os/tools/loop.py

For each scanned file, a violation is recorded when a non-comment,
non-docstring line contains the literal substring time.time(). Comment
lines (whitespace then '#') and any line that lies inside a triple-quoted
string (docstring or block string literal) are exempt so explanatory
prose can use the literal pattern without self-tripping the gate.

Exits 0 with a one-line ok message when no violations are found.
Exits 1 with one offending file:line:text per violation on stderr.

Wired into the unit-test job via tests/test_lint_no_wallclock.py.
Wired into CI via the corresponding step in .github/workflows/ci.yml.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

WATCHED_DIRS: tuple[Path, ...] = (REPO_ROOT / "src" / "horus_os" / "observability",)
WATCHED_FILES: tuple[Path, ...] = (
    REPO_ROOT / "src" / "horus_os" / "agent.py",
    REPO_ROOT / "src" / "horus_os" / "tools" / "loop.py",
)

NEEDLE = "time.time()"
TRIPLE_QUOTES = ('"""', "'''")


def _iter_target_files() -> Iterable[Path]:
    for directory in WATCHED_DIRS:
        if directory.exists():
            yield from sorted(directory.rglob("*.py"))
    for file_path in WATCHED_FILES:
        if file_path.exists():
            yield file_path


def _scan_file(file_path: Path) -> list[tuple[Path, int, str]]:
    """Return (path, line_number, line_text) for every violation in file_path.

    Strips full-line comments and any line whose content lies inside a
    triple-quoted string region. The triple-quote state machine flips on
    every standalone triple-quote token (handles both single and double
    triple-quotes, including a region that opens and closes on the same line).
    """
    violations: list[tuple[Path, int, str]] = []
    inside_string = False
    text = file_path.read_text(encoding="utf-8")
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line
        # Track triple-quoted string state across lines.
        line_in_string_at_start = inside_string
        remainder = line
        while True:
            opener_idx = -1
            opener_token = ""
            for token in TRIPLE_QUOTES:
                idx = remainder.find(token)
                if idx != -1 and (opener_idx == -1 or idx < opener_idx):
                    opener_idx = idx
                    opener_token = token
            if opener_idx == -1:
                break
            inside_string = not inside_string
            remainder = remainder[opener_idx + len(opener_token) :]
        # If the line was entirely inside a docstring region, skip it.
        if line_in_string_at_start and inside_string:
            continue
        # Skip pure comment lines.
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if NEEDLE in line:
            violations.append((file_path, line_number, line.strip()))
    return violations


def main() -> int:
    all_violations: list[tuple[Path, int, str]] = []
    for file_path in _iter_target_files():
        all_violations.extend(_scan_file(file_path))
    if not all_violations:
        print("lint_no_wallclock: OK (0 violations)")
        return 0
    for file_path, line_number, line_text in all_violations:
        rel = file_path.relative_to(REPO_ROOT)
        sys.stderr.write(f"{rel}:{line_number}: {line_text}\n")
    sys.stderr.write(
        f"lint_no_wallclock: FAIL ({len(all_violations)} violation"
        f"{'s' if len(all_violations) != 1 else ''})\n"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
