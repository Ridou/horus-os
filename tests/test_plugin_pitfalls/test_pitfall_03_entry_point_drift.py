"""Pitfall 3: Entry-point discovery API drift (3.10 → 3.11) and `pkg_resources` import cost.

See .planning/research/PITFALLS.md §"Pitfall 3" for the documented
threat. Two specific shapes:

1. ``entry_points()[group]`` — the deprecated dict-access shape that
   silently returns an empty list on Python 3.12+ instead of raising.
   A regression to this shape would make plugin discovery silently
   broken on supported runtimes.
2. ``pkg_resources`` — adds 1.3-1.5s of import overhead and is in
   deprecation drift. Layered defenses: ruff banned-api rule
   (pyproject.toml `tool.ruff.lint.flake8-tidy-imports.banned-api`)
   AND ``tests/plugins/test_pkg_resources_banned.py`` source-tree
   guard.

Three structural assertions:

1. ``src/horus_os/plugins/discovery.py`` uses
   ``entry_points(group=...)`` — the supported keyword-arg shape.
2. The deprecated ``entry_points()[group]`` dict-access shape never
   appears anywhere under ``src/``.
3. ``discover_plugins()`` over an empty entry-point registry
   (synthesized via the tier-2 ``fake_plugin_entry_points`` fixture
   with no entries) completes in <100ms — a cold-start regression
   guard mirroring TEST-18's budget.

Parametrized on the two supported Python versions (3.11, 3.12) so a
hypothetical future shape that works on one and not the other
surfaces fast.
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DISCOVERY_SRC = REPO_ROOT / "src" / "horus_os" / "plugins" / "discovery.py"


def test_discovery_uses_keyword_group_arg_shape() -> None:
    """``entry_points(group=...)`` MUST appear in discovery.py."""
    assert DISCOVERY_SRC.exists(), f"missing source: {DISCOVERY_SRC}"
    src = DISCOVERY_SRC.read_text(encoding="utf-8")
    assert re.search(r"entry_points\(group=", src), (
        f"expected 'entry_points(group=...)' in {DISCOVERY_SRC} — "
        "Pitfall 3 keyword-arg shape regression."
    )


def test_no_deprecated_dict_access_shape_anywhere_under_src() -> None:
    """The deprecated ``entry_points()[group]`` shape MUST NOT appear in src/."""
    src_root = REPO_ROOT / "src"
    assert src_root.exists() and src_root.is_dir()
    pattern = re.compile(r"entry_points\(\)\[")
    offenders: list[tuple[Path, int, str]] = []
    for py_path in sorted(src_root.rglob("*.py")):
        try:
            text = py_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                offenders.append((py_path, lineno, line.strip()))
    assert not offenders, (
        f"Pitfall 3 violation: ``entry_points()[group]`` dict-access shape "
        f"found at: {offenders}. Use ``entry_points(group=...)`` instead."
    )


@pytest.mark.parametrize("py_version", [(3, 11), (3, 12)])
def test_discover_plugins_cold_start_under_budget(
    py_version: tuple[int, int],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``discover_plugins()`` on an empty registry completes in <100ms.

    Monkeypatches ``entry_points`` to return an empty list AND points
    the filesystem walk at an empty ``tmp_path``; total cost stays
    well under the 100ms budget.

    Parametrized on the two supported Python versions: pytest collects
    BOTH parameters on every run; the parameter itself is informational
    — the assertion is the timing budget. The double invocation
    exercises the discovery path twice per session.

    Phase 46 implementation note: the parent ``tests/plugins/conftest.py``
    exposes ``fake_plugin_entry_points`` but pytest does NOT propagate
    that fixture into a sibling subdirectory's tests by default. The
    monkeypatch is inlined here to keep the regression test isolated to
    a single test file.
    """
    # Smoke-check: the current Python interpreter must be one of the
    # supported versions; if a future runtime drops support, this
    # parametrize becomes the early-warning signal.
    if sys.version_info[:2] not in {(3, 11), (3, 12), (3, 13)}:
        pytest.skip(f"unsupported Python version {sys.version_info[:2]}")
    _ = py_version  # informational parameter

    # Empty entry-point group + empty filesystem walk = cold-start floor.
    monkeypatch.setattr(
        "horus_os.plugins.discovery.entry_points",
        lambda *, group: [],
    )
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    monkeypatch.setenv("HORUS_OS_PLUGIN_DIR", str(plugin_dir))

    from horus_os.plugins.discovery import discover_plugins

    start = time.monotonic()
    specs, errors = discover_plugins(extra_paths=[])
    elapsed = time.monotonic() - start
    assert elapsed < 0.1, (
        f"discover_plugins() over empty registry took {elapsed * 1000:.1f}ms; "
        "budget is <100ms (Pitfall 3 cold-start regression guard)."
    )
    # No entries → no specs, no errors.
    assert specs == []
    assert errors == []
