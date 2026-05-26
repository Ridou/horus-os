"""Layer-2 source-tree guard against ``pkg_resources``.

The ruff banned-api rule in pyproject.toml is Layer 1; this test is
the defense-in-depth Layer 2. Walking every .py under src/horus_os/
via ``Path.rglob`` and refusing any ``import pkg_resources`` or
``from pkg_resources`` line keeps the prohibition alive even if the
ruff config drifts or a future ruff version changes the
``flake8-tidy-imports.banned-api`` table shape.

Pitfall 3 rationale (from .planning/research/PITFALLS.md): on
Python 3.12+ ``pkg_resources`` adds 1.3-1.5s of import overhead — the
largest single foot-gun in v0.5 — and its API is in deprecation drift.
``importlib.metadata.entry_points(group=...)`` is the canonical
replacement (see ``src/horus_os/adapters/base.py:22`` for the rebind
pattern).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src" / "horus_os"

# Match both ``import pkg_resources`` and ``from pkg_resources import X``.
# Anchored at the start of a stripped line so commented-out lines (which
# strip to ``# import pkg_resources``) are still caught — defense in depth,
# since a commented line can be uncommented later.
_PATTERN = re.compile(r"^\s*(?:import|from)\s+pkg_resources\b")


def test_no_pkg_resources_anywhere_under_src_horus_os() -> None:
    """Walk every .py under src/horus_os/ and refuse pkg_resources imports."""
    assert SRC_ROOT.exists() and SRC_ROOT.is_dir(), (
        f"Expected source tree at {SRC_ROOT}; check repo layout."
    )
    offenders: list[tuple[Path, int, str]] = []
    for py_path in sorted(SRC_ROOT.rglob("*.py")):
        try:
            text = py_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Binary or non-UTF-8 .py file -> skip; pkg_resources lines
            # would be invalid Python anyway.
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _PATTERN.search(line):
                # Allow commented-out lines as a soft signal; flag the
                # uncommented case as a hard failure.
                stripped = line.lstrip()
                if stripped.startswith("#"):
                    # Soft warning only; uncomment-it-and-you-broke-the-build
                    # is acceptable per the test's docstring rationale.
                    continue
                offenders.append((py_path.relative_to(REPO_ROOT), lineno, line))
    assert offenders == [], (
        "pkg_resources is banned (Pitfall 3 — 1.3-1.5s import overhead, "
        "deprecated API drift on 3.12+). Use importlib.metadata.entry_points "
        "instead. See src/horus_os/adapters/base.py:22 for the canonical "
        "pattern.\n\nOffenders:\n"
        + "\n".join(f"  {path}:{lineno}: {line!r}" for path, lineno, line in offenders)
    )


def test_pattern_matches_known_offenders() -> None:
    """Sanity: the regex catches the textbook bad lines it claims to catch."""
    assert _PATTERN.search("import pkg_resources")
    assert _PATTERN.search("from pkg_resources import iter_entry_points")
    assert _PATTERN.search("    import pkg_resources  # nested")
    # Does NOT match pkg_resources mentioned inside a docstring / comment
    # with leading text.
    assert not _PATTERN.search("# this comment mentions pkg_resources but does not import")
    assert not _PATTERN.search("'pkg_resources is banned'")
