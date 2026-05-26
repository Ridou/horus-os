#!/usr/bin/env python3
"""Regenerate ``docs/manifest-v1.schema.json`` from the runtime pydantic schema.

This script is the canonical generator for the human-readable JSON
Schema mirror of ``horus_os.plugins.manifest.MANIFEST_V1_SCHEMA``. It
is the source-side of the Pitfall 12 docs-drift gate (the runtime side
lives in
``tests/test_plugin_pitfalls/test_pitfall_12_docs_drift.py::test_docs_drift_against_committed_schema_file``).

Usage::

    python scripts/build_manifest_schema.py

The script is idempotent — running it twice in a row produces no diff
because both invocations serialize the same schema dict with
``indent=2, sort_keys=True`` plus a trailing newline.

The output file ``docs/manifest-v1.schema.json`` is the Phase 49
release-gate target: ``scripts/release_gate.py`` will refuse to tag a
release whose committed docs schema disagrees with the runtime
schema.
"""

from __future__ import annotations

import json
import pathlib
import sys

# Make ``src/`` importable when the script is run from the repo root
# without an editable install.
REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from horus_os.plugins.manifest import MANIFEST_V1_SCHEMA  # noqa: E402

OUTPUT_PATH = REPO_ROOT / "docs" / "manifest-v1.schema.json"


def main() -> int:
    schema = MANIFEST_V1_SCHEMA.model_json_schema()
    payload = json.dumps(schema, indent=2, sort_keys=True) + "\n"
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(payload, encoding="utf-8")
    print(f"wrote {OUTPUT_PATH.relative_to(REPO_ROOT)} ({len(payload)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
