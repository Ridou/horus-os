"""REFERENCE-02 / Pitfall 12: docs/manifest-v1.schema.json mirrors the runtime schema.

The release-gate target. Phase 49's ``scripts/release_gate.py`` will
refuse to tag a release whose committed docs schema disagrees with
the runtime pydantic schema; this test is the runtime-side guard
that the docs file stays byte-identical to
``MANIFEST_V1_SCHEMA.model_json_schema()``.

Three contracts:

1. ``docs/manifest-v1.schema.json`` exists.
2. Its parsed JSON equals the runtime schema dict (semantic equality).
3. Its byte content equals the canonical canonicalization
   ``json.dumps(schema, indent=2, sort_keys=True) + "\\n"`` (the
   shape the regenerator ``scripts/build_manifest_schema.py``
   produces). Byte-stable so a `git diff` after running the
   regenerator is empty.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from horus_os.plugins.manifest import MANIFEST_V1_SCHEMA

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_SCHEMA_PATH = REPO_ROOT / "docs" / "manifest-v1.schema.json"


@pytest.fixture(scope="module")
def bundled_text() -> str:
    if not DOCS_SCHEMA_PATH.is_file():
        pytest.fail(
            "docs/manifest-v1.schema.json does not exist — Phase 47 must "
            "ship the JSON-Schema mirror. Regenerate via "
            "`python scripts/build_manifest_schema.py`."
        )
    return DOCS_SCHEMA_PATH.read_text(encoding="utf-8")


def test_docs_schema_file_exists(bundled_text: str) -> None:
    assert bundled_text.strip(), "docs/manifest-v1.schema.json is empty"


def test_docs_schema_matches_runtime_schema(bundled_text: str) -> None:
    """Parsed bundled schema dict equals the runtime schema dict."""
    bundled = json.loads(bundled_text)
    runtime = MANIFEST_V1_SCHEMA.model_json_schema()
    assert bundled == runtime, (
        "docs/manifest-v1.schema.json drifted from "
        "MANIFEST_V1_SCHEMA.model_json_schema() semantically. Regenerate "
        "via: python scripts/build_manifest_schema.py"
    )


def test_docs_schema_is_byte_stable_canonical(bundled_text: str) -> None:
    """The bundled file matches the canonical canonicalization byte-for-byte."""
    canonical = json.dumps(MANIFEST_V1_SCHEMA.model_json_schema(), indent=2, sort_keys=True) + "\n"
    assert bundled_text == canonical, (
        "docs/manifest-v1.schema.json drifted from "
        "MANIFEST_V1_SCHEMA.model_json_schema() at the byte level. "
        "Regenerate via: python scripts/build_manifest_schema.py"
    )
