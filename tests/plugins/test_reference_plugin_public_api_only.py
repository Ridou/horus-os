"""TEST-21 layer-2 source-tree backstop for the reference plugin.

Pitfall 8 (.planning/research/PITFALLS.md) reserves a single public API
surface for plugin authors: ``horus_os.plugins.api``. Phase 48 pins
this contract for the shipped reference plugin via a two-layer guard.

* Layer 1 — ``ruff check`` ``[tool.ruff.lint.flake8-tidy-imports.banned-api]``
  rules scoped to ``examples/horus-os-example-plugin/src/`` reject any
  ``from horus_os.<non-api>`` import at lint time.
* Layer 2 — this pytest module — walks every ``*.py`` under
  ``examples/horus-os-example-plugin/src/`` at default-test time and
  flags any ``from horus_os`` line that is not exactly
  ``from horus_os.plugins.api import ...`` (and any bare ``import
  horus_os.<...>`` line).

Defense-in-depth (same shape as Phase 42's
``tests/plugins/test_pkg_resources_banned.py``): if a future ruff
config drift silences the layer-1 rule, layer 2 still fails the build.
The third test in this module proves the scanner is NOT vacuous by
running it against an in-test synthetic source tree containing a known
violation and asserting it gets flagged.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REF_PLUGIN_SRC = REPO_ROOT / "examples" / "horus-os-example-plugin" / "src"

# Any ``from horus_os...`` or ``import horus_os...`` line is a candidate.
BAD_IMPORT = re.compile(
    r"^\s*(?:"
    r"from\s+horus_os(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*\s+import\b"
    r"|"
    r"import\s+horus_os(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*\b"
    r")"
)

# The single sanctioned form. A candidate matches GOOD_IMPORT iff it
# starts with ``from horus_os.plugins.api import`` (possibly with
# trailing names/whitespace); everything else under BAD_IMPORT is a
# layer-2 violation.
GOOD_IMPORT = re.compile(r"^\s*from\s+horus_os\.plugins\.api\s+import\s+")


def _scan_for_bad_imports(root: Path) -> list[str]:
    """Walk ``root/**/*.py`` and return ``file:line:source`` violation strings.

    A line is a violation iff it matches ``BAD_IMPORT`` (it IS a
    ``horus_os`` import) AND it does NOT match ``GOOD_IMPORT`` (it is
    NOT the sanctioned public-API path).
    """
    offenders: list[str] = []
    if not root.exists():
        return offenders
    for py_path in sorted(root.rglob("*.py")):
        try:
            text = py_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if not BAD_IMPORT.match(line):
                continue
            if GOOD_IMPORT.match(line):
                continue
            try:
                rel = py_path.relative_to(REPO_ROOT)
            except ValueError:
                rel = py_path
            offenders.append(f"{rel}:{lineno}:{line.rstrip()}")
    return offenders


def test_reference_plugin_source_dir_exists() -> None:
    """The reference plugin directory layout is the contract we scan against.

    A refactor that moves or renames the reference plugin must update
    this test, not silently pass on an empty directory (which the
    scanner would happily report as zero violations — vacuously true).
    """
    assert REF_PLUGIN_SRC.is_dir(), (
        f"reference plugin src missing at {REF_PLUGIN_SRC}; if the example "
        f"moved, update REF_PLUGIN_SRC in this test file."
    )
    assert (REF_PLUGIN_SRC / "horus_os_example_plugin" / "tools.py").is_file()
    assert (REF_PLUGIN_SRC / "horus_os_example_plugin" / "adapter.py").is_file()
    assert (REF_PLUGIN_SRC / "horus_os_example_plugin" / "__init__.py").is_file()


def test_reference_plugin_uses_only_public_api() -> None:
    """The shipped reference plugin's src/ uses only `from horus_os.plugins.api`."""
    offenders = _scan_for_bad_imports(REF_PLUGIN_SRC)
    assert offenders == [], (
        "Reference plugin imports from non-public horus_os modules. "
        "Plugin authors must restrict to `from horus_os.plugins.api import ...`. "
        "See Pitfall 8 / TEST-21 / docs/PLUGINS.md 'Public API surface'.\n\n"
        "Offenders:\n" + "\n".join(f"  {line}" for line in offenders)
    )


def test_scanner_catches_synthetic_bad_import(tmp_path: Path) -> None:
    """Layer-2 fires on a known violation — proves the regex is non-vacuous.

    A synthetic plugin source tree under ``tmp_path`` contains one
    forbidden line (``from horus_os.adapters import Adapter``) and one
    sanctioned line. The scanner must report exactly the forbidden
    line.
    """
    fake_src = tmp_path / "src" / "fake_plugin"
    fake_src.mkdir(parents=True)
    (fake_src / "__init__.py").write_text("", encoding="utf-8")
    (fake_src / "ok.py").write_text(
        "from horus_os.plugins.api import Capability\n",
        encoding="utf-8",
    )
    bad_file = fake_src / "bad.py"
    bad_file.write_text(
        "from horus_os.adapters import Adapter\n",
        encoding="utf-8",
    )

    offenders = _scan_for_bad_imports(tmp_path / "src")
    assert len(offenders) == 1, (
        f"Expected exactly one violation in the synthetic fixture; got "
        f"{len(offenders)}: {offenders}"
    )
    assert "horus_os.adapters" in offenders[0]
    assert "bad.py" in offenders[0]


def test_scanner_also_catches_bare_import_horus_os(tmp_path: Path) -> None:
    """``import horus_os.something`` is also a violation (not just `from`).

    The BAD_IMPORT regex covers ``import horus_os.<submodule>`` so a
    plugin author cannot bypass the contract with bare imports.
    """
    fake_src = tmp_path / "src" / "fake_plugin"
    fake_src.mkdir(parents=True)
    (fake_src / "bad.py").write_text(
        "import horus_os.types\n",
        encoding="utf-8",
    )
    offenders = _scan_for_bad_imports(tmp_path / "src")
    assert len(offenders) == 1
    assert "horus_os.types" in offenders[0]
