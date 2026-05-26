"""REL-12: docs/PLUGIN-SECURITY.md contains the literal threat-model sentence.

The acceptance criterion: ``plugins execute in the horus-os Python
process`` appears verbatim inside a ``## Threat model`` section. The
installer's grant prompt links to the doc so the user reading the
terminal prompt knows where to find the threat model.

Five contracts pinned by this test:

1. ``docs/PLUGIN-SECURITY.md`` exists.
2. A ``## Threat model`` section heading is present.
3. The literal REL-12 sentence appears verbatim.
4. The file is ≤400 lines (ROADMAP §47 SC3 — one-sitting read).
5. ``src/horus_os/plugins/installer.py`` references the doc path
   so the grant prompt links the user to the threat model.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SECURITY_MD_PATH = REPO_ROOT / "docs" / "PLUGIN-SECURITY.md"
INSTALLER_PATH = REPO_ROOT / "src" / "horus_os" / "plugins" / "installer.py"

REL12_LITERAL_SENTENCE = "plugins execute in the horus-os Python process"


@pytest.fixture(scope="module")
def security_md_text() -> str:
    if not SECURITY_MD_PATH.is_file():
        pytest.fail(
            "docs/PLUGIN-SECURITY.md does not exist — REL-12 requires this doc."
        )
    return SECURITY_MD_PATH.read_text(encoding="utf-8")


def test_plugin_security_md_exists(security_md_text: str) -> None:
    assert security_md_text.strip(), "docs/PLUGIN-SECURITY.md is empty"


def test_threat_model_section_present(security_md_text: str) -> None:
    """A '## Threat model' section heading is present."""
    match = re.search(r"^##\s+Threat model\s*$", security_md_text, re.MULTILINE)
    assert match is not None, (
        "docs/PLUGIN-SECURITY.md must contain a '## Threat model' section "
        "heading (the REL-12 anchor for the literal sentence)."
    )


def test_literal_rel12_sentence_present(security_md_text: str) -> None:
    """The REL-12 acceptance sentence appears verbatim."""
    assert REL12_LITERAL_SENTENCE in security_md_text, (
        f"docs/PLUGIN-SECURITY.md must contain the REL-12 literal sentence "
        f"{REL12_LITERAL_SENTENCE!r}. This is the acceptance criterion for "
        f"REL-12; the threat model is not signed off until the sentence "
        f"appears as prose inside the ## Threat model section."
    )


def test_under_400_lines(security_md_text: str) -> None:
    """≤400 lines per ROADMAP §47 success criterion 3 (one-sitting read)."""
    line_count = len(security_md_text.splitlines())
    assert line_count <= 400, (
        f"docs/PLUGIN-SECURITY.md must be ≤400 lines (one-sitting read); "
        f"current length: {line_count} lines."
    )


def test_installer_references_security_doc() -> None:
    """The installer grant prompt references docs/PLUGIN-SECURITY.md."""
    if not INSTALLER_PATH.is_file():
        pytest.fail(
            "src/horus_os/plugins/installer.py not found — cannot verify "
            "installer linkage to the security doc."
        )
    installer_text = INSTALLER_PATH.read_text(encoding="utf-8")
    assert "docs/PLUGIN-SECURITY.md" in installer_text, (
        "The installer grant prompt must reference docs/PLUGIN-SECURITY.md "
        "so the user reading the prompt knows where to read the threat "
        "model. Add a literal string fragment referencing the doc path to "
        "render_grant_prompt or its surrounding prompt-rendering code."
    )
