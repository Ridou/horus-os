"""REFERENCE-02 / Pitfall 12: docs/PLUGINS.md must embed the canonical sources.

Three contracts pinned by this test:

1. The embedded ``horus-plugin.toml`` example block is byte-identical
   to ``tests/fixtures/manifests/manifest_v1_full.toml`` (the source-
   of-truth fixture that the manifest schema tests, the installer
   tests, and the discovery tests all share). A docs author who edits
   the example in PLUGINS.md without updating the fixture (or vice
   versa) fails this test.

2. Every ``Capability`` enum member's dotted-key string AND the
   verbatim ``DESCRIPTIONS[cap]`` text both appear in PLUGINS.md.
   The capability catalog is the source of truth; the docs mirror it.

3. The 8 canonical section headings appear in order. Soft contiguous-
   subsequence check so the doc can interleave additional headings if
   needed without failing the gate.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from horus_os.plugins.capability_catalog import DESCRIPTIONS, Capability

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGINS_MD_PATH = REPO_ROOT / "docs" / "PLUGINS.md"
MANIFEST_FIXTURE_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "manifests" / "manifest_v1_full.toml"
)

CANONICAL_SECTION_HEADINGS: list[str] = [
    "What is a plugin?",
    "Anatomy of `horus-plugin.toml`",
    "Capability catalog",
    "Lifecycle hooks",
    "Testing your plugin",
    "Walkthrough of the reference plugin",
    "Public API surface",
    "Distributing your plugin",
]


@pytest.fixture(scope="module")
def plugins_md_text() -> str:
    if not PLUGINS_MD_PATH.is_file():
        pytest.fail(
            "docs/PLUGINS.md does not exist — Phase 47 must ship the plugin "
            "author guide. Regenerate via /gsd-plan-phase 47."
        )
    return PLUGINS_MD_PATH.read_text(encoding="utf-8")


def test_plugins_md_exists(plugins_md_text: str) -> None:
    """docs/PLUGINS.md exists and is non-empty."""
    assert plugins_md_text.strip(), "docs/PLUGINS.md is empty"


def test_plugins_md_embeds_full_manifest_fixture(plugins_md_text: str) -> None:
    """docs/PLUGINS.md embeds tests/fixtures/manifests/manifest_v1_full.toml verbatim."""
    fixture_text = MANIFEST_FIXTURE_PATH.read_text(encoding="utf-8")
    assert fixture_text in plugins_md_text, (
        "docs/PLUGINS.md must embed tests/fixtures/manifests/manifest_v1_full.toml "
        "verbatim inside a fenced code block. Regenerate via "
        "/gsd-plan-phase 47."
    )


def test_plugins_md_lists_every_capability_with_description(
    plugins_md_text: str,
) -> None:
    """Every Capability enum member's dotted-key + description appears verbatim."""
    missing: list[str] = []
    for cap in Capability:
        if cap.value not in plugins_md_text:
            missing.append(f"capability dotted-key {cap.value!r}")
        description = DESCRIPTIONS[cap]
        if description not in plugins_md_text:
            missing.append(
                f"description for {cap.value} (expected substring: "
                f"{description!r})"
            )
    assert not missing, (
        "docs/PLUGINS.md is missing the following capability-catalog rows:\n  - "
        + "\n  - ".join(missing)
    )


def test_plugins_md_section_headings_in_order(plugins_md_text: str) -> None:
    """The 8 canonical section headings appear in PLUGINS.md as a contiguous subsequence."""
    headings = re.findall(r"^##\s+(.+?)\s*$", plugins_md_text, re.MULTILINE)
    # Find the first canonical heading; from there each subsequent
    # canonical heading must appear in order (allowing other headings
    # in between is fine — we just need a subsequence, not contiguous).
    cursor = 0
    missing: list[str] = []
    for canonical in CANONICAL_SECTION_HEADINGS:
        found_at: int | None = None
        for j in range(cursor, len(headings)):
            if headings[j] == canonical:
                found_at = j
                break
        if found_at is None:
            missing.append(canonical)
        else:
            cursor = found_at + 1
    assert not missing, (
        "docs/PLUGINS.md is missing canonical section heading(s) (or out of order):\n  - "
        + "\n  - ".join(missing)
        + f"\n\nFound headings in order: {headings!r}"
    )
