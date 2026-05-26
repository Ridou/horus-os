"""Schema-shape contract for tests/perf/v0_4_baseline.json (BASELINE-02).

Three assertions, all stdlib + pytest only:

1. test_baseline_json_parses_and_every_row_has_required_schema_fields:
   The JSON parses, the top-level shape is `{"samples": [...]}`, and
   every row carries exactly the nine canonical fields with valid
   values on the non-measurement fields.
2. test_at_least_one_row_is_fully_populated:
   Distinguishes the baseline artifact (must have at minimum one
   captured row at commit time) from a placeholder-only file (which
   means no host has run scripts/capture_v0_4_baseline.py yet, an
   invalid state for Phase 40 ship).
3. test_no_duplicate_os_python_keys:
   The capture script de-duplicates on (os, python) before write; this
   test guards against a hand-edit that accidentally appends a second
   row for the same (os, python) combo.

Phase 42's TEST-18 cold-start benchmark consumes v0_4_baseline.json. If
that file is malformed at the schema level, this test fails first so
the malformation surfaces before Phase 42 reads garbage.
"""

from __future__ import annotations

import json
from pathlib import Path

BASELINE_PATH = Path(__file__).resolve().parent / "v0_4_baseline.json"

REQUIRED_FIELDS = {
    "os",
    "python",
    "horus_os_version",
    "wall_clock_ms",
    "agent_loop_3_iter_ms",
    "cold_import_ms",
    "entry_points_discovery_ms",
    "n_samples",
    "captured_at",
}

VALID_OS = {"linux", "darwin", "win32"}
VALID_PYTHON = {"3.11", "3.12", "3.13"}
MEASUREMENT_FIELDS = (
    "wall_clock_ms",
    "agent_loop_3_iter_ms",
    "cold_import_ms",
    "entry_points_discovery_ms",
)


def _load_samples() -> list[dict]:
    assert BASELINE_PATH.exists(), f"baseline JSON missing at {BASELINE_PATH}"
    with BASELINE_PATH.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    assert isinstance(data, dict), "top-level JSON must be an object"
    assert "samples" in data, "top-level must contain a `samples` key"
    assert isinstance(data["samples"], list), "`samples` must be a list"
    assert len(data["samples"]) >= 1, "`samples` must hold at least one row"
    return data["samples"]


def test_baseline_json_parses_and_every_row_has_required_schema_fields() -> None:
    """Every row carries the nine canonical fields with valid metadata."""
    samples = _load_samples()
    for idx, entry in enumerate(samples):
        keys = set(entry.keys())
        missing = REQUIRED_FIELDS - keys
        extra = keys - REQUIRED_FIELDS
        assert not missing, f"row {idx} missing fields: {missing}"
        assert not extra, f"row {idx} has unexpected fields: {extra}"
        assert entry["os"] in VALID_OS, f"row {idx} os={entry['os']!r} not in {VALID_OS}"
        assert entry["python"] in VALID_PYTHON, (
            f"row {idx} python={entry['python']!r} not in {VALID_PYTHON}"
        )
        assert entry["horus_os_version"] == "0.4.0", (
            f"row {idx} horus_os_version={entry['horus_os_version']!r} (expected 0.4.0)"
        )
        assert entry["n_samples"] == 20, f"row {idx} n_samples={entry['n_samples']!r} (expected 20)"
        captured_at = entry["captured_at"]
        assert captured_at == "placeholder" or (
            isinstance(captured_at, str) and captured_at.endswith("Z")
        ), (
            f"row {idx} captured_at={captured_at!r} must be 'placeholder' or an ISO8601 Z-suffixed string"
        )


def test_at_least_one_row_is_fully_populated() -> None:
    """Phase 40 ship gate: at minimum one row carries real captured numbers.

    A fully populated row has captured_at != 'placeholder' AND all four
    measurement fields are non-null positive floats. The maintainer's
    local capture seeded one such row at commit time; CI runners will
    backfill the placeholder rows before Phase 42 begins.
    """
    samples = _load_samples()
    populated = [
        e
        for e in samples
        if e["captured_at"] != "placeholder"
        and all(e[field] is not None for field in MEASUREMENT_FIELDS)
    ]
    assert len(populated) >= 1, "Phase 40 requires at least one fully populated baseline row; got 0"
    for entry in populated:
        for field in MEASUREMENT_FIELDS:
            value = entry[field]
            assert isinstance(value, (int, float)), (
                f"{entry['os']} py{entry['python']} {field}={value!r} must be numeric"
            )
            assert value > 0, f"{entry['os']} py{entry['python']} {field}={value} must be > 0"


def test_no_duplicate_os_python_keys() -> None:
    """The capture script de-duplicates on (os, python); guard against drift."""
    samples = _load_samples()
    keys = [(e["os"], e["python"]) for e in samples]
    duplicates = [k for k in keys if keys.count(k) > 1]
    assert not duplicates, f"duplicate (os, python) keys in baseline: {set(duplicates)}"
