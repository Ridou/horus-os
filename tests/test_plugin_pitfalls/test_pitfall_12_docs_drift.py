"""Pitfall 12: Documentation drift between manifest spec, reference plugin, and `docs/PLUGINS.md`.

See .planning/research/PITFALLS.md §"Pitfall 12" for the documented
threat. The pydantic ``MANIFEST_V1_SCHEMA`` is the source of truth for
the manifest shape; ``docs/manifest-v1.schema.json`` (shipped in
Phase 47) is the human-readable mirror. If the two drift, plugin
authors reading the docs build manifests that fail validation.

The Phase 47 prevention pattern: ``docs/manifest-v1.schema.json`` is
generated from ``MANIFEST_V1_SCHEMA.model_json_schema()`` at release
time AND a CI gate diffs the bundled doc against the runtime schema.
This test pins the runtime side of that contract:

1. ``MANIFEST_V1_SCHEMA.model_json_schema()`` returns a dict with the
   pydantic v2 JSON Schema shape (``type='object'`` + ``properties`` +
   ``required``).
2. The same call returns a byte-stable result across two invocations
   (deterministic serialization).
3. The docs-drift diff itself is intentionally SKIPPED until Phase 47
   ships ``docs/manifest-v1.schema.json``; the skip carries an
   explicit TODO comment pointing to the future phase.

Phase 46 deviation note (Rule 1): pydantic v2's ``model_json_schema``
returns ``type: 'object'`` at the top level for a ``BaseModel``. Other
shapes (e.g. ``allOf`` aggregation when fields use ``$ref``) can shift
the schema dict structure. The test asserts the canonical Phase 41
schema shape today; if a future refactor shifts the schema dict shape,
this test fails loud and forces a coordinated docs update.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from horus_os.plugins.manifest import MANIFEST_V1_SCHEMA

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_SCHEMA_PATH = REPO_ROOT / "docs" / "manifest-v1.schema.json"


def test_manifest_v1_schema_emits_object_shape() -> None:
    """``model_json_schema()`` returns an ``object``-typed dict with properties."""
    schema = MANIFEST_V1_SCHEMA.model_json_schema()
    assert isinstance(schema, dict)
    assert schema.get("type") == "object", (
        f"Pitfall 12: MANIFEST_V1_SCHEMA root .type expected 'object'; "
        f"got {schema.get('type')!r}. Schema shape drifted; coordinate with docs/."
    )
    assert "properties" in schema and isinstance(schema["properties"], dict)
    assert "required" in schema and isinstance(schema["required"], list)


def test_manifest_v1_schema_serialization_is_byte_stable() -> None:
    """Two calls to model_json_schema() serialize to identical canonical JSON."""
    schema_a = MANIFEST_V1_SCHEMA.model_json_schema()
    schema_b = MANIFEST_V1_SCHEMA.model_json_schema()
    canonical_a = json.dumps(schema_a, indent=2, sort_keys=True)
    canonical_b = json.dumps(schema_b, indent=2, sort_keys=True)
    assert canonical_a == canonical_b, (
        "Pitfall 12: MANIFEST_V1_SCHEMA serialization is not byte-stable. "
        "Two consecutive model_json_schema() calls produced different output — "
        "introspection is order-dependent."
    )


def test_manifest_v1_schema_includes_canonical_required_fields() -> None:
    """The schema's ``required`` list covers every mandatory v1 field."""
    schema = MANIFEST_V1_SCHEMA.model_json_schema()
    required = set(schema.get("required", []))
    # Phase 41 canonical required set. Bump this list deliberately if the
    # manifest schema adds a required field — that's a breaking change.
    expected_required = {
        "manifest_version",
        "name",
        "version",
        "description",
        "author",
        "license",
        "horus_os_compat",
    }
    missing = expected_required - required
    assert not missing, (
        f"Pitfall 12: MANIFEST_V1_SCHEMA dropped required fields: {missing}. "
        "This is a breaking change for plugin authors; coordinate with docs/."
    )


def test_docs_drift_against_committed_schema_file() -> None:
    """Diff the runtime schema against ``docs/manifest-v1.schema.json``.

    SKIPPED until Phase 47 ships the docs file. When the docs file
    lands, drop the skip and re-run; the assertion compares the
    runtime schema's canonical JSON against the bundled JSON.

    TODO(Phase 47): activate this gate by deleting the skip + ensuring
    ``docs/manifest-v1.schema.json`` round-trips through
    ``MANIFEST_V1_SCHEMA.model_json_schema()``.
    """
    if not DOCS_SCHEMA_PATH.is_file():
        pytest.skip(
            "docs/manifest-v1.schema.json shipped in Phase 47 — "
            "docs-drift gate activates then."
        )
    runtime_schema = MANIFEST_V1_SCHEMA.model_json_schema()
    bundled_text = DOCS_SCHEMA_PATH.read_text(encoding="utf-8")
    bundled_schema = json.loads(bundled_text)
    runtime_canonical = json.dumps(runtime_schema, indent=2, sort_keys=True)
    bundled_canonical = json.dumps(bundled_schema, indent=2, sort_keys=True)
    assert runtime_canonical == bundled_canonical, (
        "Pitfall 12: docs/manifest-v1.schema.json drifted from MANIFEST_V1_SCHEMA. "
        "Regenerate the docs file via the Phase 47 generator."
    )
