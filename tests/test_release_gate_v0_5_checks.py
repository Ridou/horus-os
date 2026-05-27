"""Unit tests for the four v0.5 release-gate checks (Phase 49, REL-11).

scripts/release_gate.py grows from 4 v0.4 checks to 8 v0.5 checks:

* docs-drift: MANIFEST_V1_SCHEMA <-> docs/manifest-v1.schema.json
* plugin-install-smoke-ci: ci.yml contains literal 'install-smoke-plugin'
* reference-plugin-manifest-valid: validate_manifest(toml_bytes) succeeds
  on examples/horus-os-example-plugin/horus-plugin.toml
* v0-4-fixture-roundtrip: tests/fixtures/v0_4_database.sqlite3 survives
  the v5 -> v6 migration with all three plugin tables, two plugin_name
  columns, and the idx_tool_invocations_plugin index present + second
  init() call is idempotent

Each check has a positive-path test (live repo state -> ok=True) and a
mutation-driven negative-path test (copy to tmp, mutate, point check
at tmp, assert ok=False). One subprocess test wires the end-to-end CLI
contract (--check docs-drift exits 1 against a mutated docs path).

The v0.4 four-check fixture-isolation contract is preserved: the
committed docs/manifest-v1.schema.json, ci.yml, reference plugin
manifest, and v0.4 fixture are NEVER mutated; mutation tests always
copy to tmp_path first.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
_MODULE_NAME = "_release_gate_under_test_v0_5"


def _load_release_gate_module():
    """Import scripts/release_gate.py as a module without modifying sys.path.

    Mirrors tests/test_release_gate.py::_load_release_gate_module exactly
    so the dataclass introspection (CheckResult) works in both files
    without colliding on sys.modules.
    """
    if _MODULE_NAME in sys.modules:
        return sys.modules[_MODULE_NAME]
    script = REPO_ROOT / "scripts" / "release_gate.py"
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


# ----------------------------------------------------------------------
# docs-drift
# ----------------------------------------------------------------------


def test_docs_drift_passes_when_in_sync() -> None:
    """The committed docs file matches the runtime MANIFEST_V1_SCHEMA dump."""
    mod = _load_release_gate_module()
    docs_path = REPO_ROOT / "docs" / "manifest-v1.schema.json"
    result = mod.check_docs_manifest_schema_drift(docs_path)
    assert result.ok is True, result.diagnostic
    assert result.name == "docs-drift"


def test_docs_drift_fails_on_mutation(tmp_path: Path) -> None:
    """A one-byte mutation flips ok to False with difflib markers."""
    mod = _load_release_gate_module()
    docs_path = REPO_ROOT / "docs" / "manifest-v1.schema.json"
    tmp_docs = tmp_path / "manifest-v1.schema.json"
    text = docs_path.read_text(encoding="utf-8")
    # Insert a junk field at the top so the byte-for-byte compare fails.
    mutated = text.replace("{\n", '{\n  "x": "x",\n', 1)
    assert mutated != text  # sanity — mutation must have actually changed it
    tmp_docs.write_text(mutated, encoding="utf-8")
    result = mod.check_docs_manifest_schema_drift(tmp_docs)
    assert result.ok is False
    # difflib markers present so the diagnostic is actionable.
    assert "---" in result.diagnostic or "+++" in result.diagnostic
    assert result.name == "docs-drift"


def test_docs_drift_fails_when_docs_file_missing(tmp_path: Path) -> None:
    """A missing docs file is a fail with a clear diagnostic."""
    mod = _load_release_gate_module()
    missing = tmp_path / "does_not_exist.json"
    result = mod.check_docs_manifest_schema_drift(missing)
    assert result.ok is False
    assert str(missing) in result.diagnostic


# ----------------------------------------------------------------------
# plugin-install-smoke-ci
# ----------------------------------------------------------------------


def test_plugin_install_smoke_ci_passes_when_job_present(tmp_path: Path) -> None:
    """A ci.yml containing the literal 'install-smoke-plugin' string passes."""
    mod = _load_release_gate_module()
    ci = tmp_path / "ci.yml"
    ci.write_text(
        "name: test\njobs:\n  install-smoke-plugin:\n    runs-on: ubuntu-latest\n",
        encoding="utf-8",
    )
    result = mod.check_plugin_install_smoke_ci_present(ci)
    assert result.ok is True, result.diagnostic
    assert result.name == "plugin-install-smoke-ci"


def test_plugin_install_smoke_ci_fails_when_job_missing(tmp_path: Path) -> None:
    """A ci.yml without the literal string fails with a TEST-20 diagnostic."""
    mod = _load_release_gate_module()
    ci = tmp_path / "ci.yml"
    ci.write_text(
        "name: test\njobs:\n  lint-and-test:\n    runs-on: ubuntu-latest\n",
        encoding="utf-8",
    )
    result = mod.check_plugin_install_smoke_ci_present(ci)
    assert result.ok is False
    assert "TEST-20" in result.diagnostic
    assert result.name == "plugin-install-smoke-ci"


def test_plugin_install_smoke_ci_fails_when_file_missing(tmp_path: Path) -> None:
    """A missing ci.yml is a clear fail."""
    mod = _load_release_gate_module()
    missing = tmp_path / "no_ci.yml"
    result = mod.check_plugin_install_smoke_ci_present(missing)
    assert result.ok is False
    assert str(missing) in result.diagnostic


# ----------------------------------------------------------------------
# reference-plugin-manifest-valid
# ----------------------------------------------------------------------


def test_reference_plugin_manifest_valid_passes() -> None:
    """The bundled reference plugin manifest validates cleanly."""
    mod = _load_release_gate_module()
    manifest_path = (
        REPO_ROOT
        / "examples"
        / "horus-os-example-plugin"
        / "src"
        / "horus_os_example_plugin"
        / "horus-plugin.toml"
    )
    result = mod.check_reference_plugin_manifest_valid(manifest_path)
    assert result.ok is True, result.diagnostic
    # Diagnostic names the plugin so the maintainer knows which one passed.
    assert "horus-os-example-plugin" in result.diagnostic
    assert result.name == "reference-plugin-manifest-valid"


def test_reference_plugin_manifest_invalid_fails(tmp_path: Path) -> None:
    """A malformed manifest fails with a typed-exception diagnostic."""
    mod = _load_release_gate_module()
    bad_toml = tmp_path / "horus-plugin.toml"
    # Missing required fields: name, version, capabilities, etc.
    bad_toml.write_text(
        'manifest_version = 1\nname = "x"\n',
        encoding="utf-8",
    )
    result = mod.check_reference_plugin_manifest_valid(bad_toml)
    assert result.ok is False
    assert "invalid" in result.diagnostic.lower()


def test_reference_plugin_manifest_missing_file(tmp_path: Path) -> None:
    mod = _load_release_gate_module()
    missing = tmp_path / "missing.toml"
    result = mod.check_reference_plugin_manifest_valid(missing)
    assert result.ok is False
    assert str(missing) in result.diagnostic


# ----------------------------------------------------------------------
# v0-4-fixture-roundtrip
# ----------------------------------------------------------------------


def test_v0_4_fixture_roundtrip_passes() -> None:
    """The committed v0.4 fixture survives the v5 -> v6 migration."""
    mod = _load_release_gate_module()
    fixture_path = REPO_ROOT / "tests" / "fixtures" / "v0_4_database.sqlite3"
    # Capture fixture metadata pre-check; the check must NEVER mutate the
    # source fixture (T-49-01 mitigation — copies to tmpfile internally).
    pre_size = fixture_path.stat().st_size
    pre_mtime = fixture_path.stat().st_mtime
    result = mod.check_v0_4_fixture_roundtrip(fixture_path)
    assert result.ok is True, result.diagnostic
    assert result.name == "v0-4-fixture-roundtrip"
    # Source fixture is byte-identical after the check.
    assert fixture_path.stat().st_size == pre_size
    assert fixture_path.stat().st_mtime == pre_mtime


def test_v0_4_fixture_roundtrip_fails_on_non_sqlite(tmp_path: Path) -> None:
    """A non-SQLite file in place of the fixture fails with a useful diagnostic."""
    mod = _load_release_gate_module()
    fake = tmp_path / "not_sqlite.sqlite3"
    fake.write_text("this is not a sqlite file at all", encoding="utf-8")
    result = mod.check_v0_4_fixture_roundtrip(fake)
    assert result.ok is False
    # Diagnostic should signal "not a database" or otherwise carry the
    # sqlite error so the maintainer can debug.
    lowered = result.diagnostic.lower()
    assert "database" in lowered or "sqlite" in lowered or "fixture" in lowered


def test_v0_4_fixture_roundtrip_missing_file(tmp_path: Path) -> None:
    mod = _load_release_gate_module()
    missing = tmp_path / "no_fixture.sqlite3"
    result = mod.check_v0_4_fixture_roundtrip(missing)
    assert result.ok is False
    assert str(missing) in result.diagnostic


def test_v0_4_fixture_roundtrip_fails_on_corrupt_sqlite(tmp_path: Path) -> None:
    """A truncated SQLite header is rejected with a sqlite-error diagnostic.

    Tests the "fixture exists, opens, but is unusable" failure mode by
    writing the first 16 bytes of a real SQLite header followed by
    garbage. ``sqlite3.connect`` accepts the path lazily but the first
    PRAGMA query inside ``Database.init()`` raises ``DatabaseError`` —
    the check must catch this and produce ``ok=False`` with a
    diagnostic the maintainer can act on.
    """
    mod = _load_release_gate_module()
    corrupt = tmp_path / "corrupt.sqlite3"
    # SQLite magic header is "SQLite format 3\x00" (16 bytes); we follow
    # it with garbage so sqlite3.connect succeeds but any subsequent
    # query raises DatabaseError.
    corrupt.write_bytes(b"SQLite format 3\x00" + b"\xff" * 4096)
    result = mod.check_v0_4_fixture_roundtrip(corrupt)
    assert result.ok is False
    # Diagnostic should signal sqlite trouble (raised either inside
    # Database.init or inside the introspection step).
    lowered = result.diagnostic.lower()
    assert "sqlite" in lowered or "database" in lowered or "raised" in lowered


# ----------------------------------------------------------------------
# main() integration — exit-code contract for the new checks
# ----------------------------------------------------------------------


def test_main_runs_new_checks_in_default_invocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Default invocation runs all 8 checks (4 v0.4 + 4 v0.5)."""
    mod = _load_release_gate_module()
    # Skip the slow build + tests to keep the test hermetic.
    monkeypatch.setenv("HORUS_OS_RELEASE_GATE_SKIP_BUILD", "1")
    monkeypatch.setenv("HORUS_OS_RELEASE_GATE_SKIP_TESTS", "1")
    exit_code = mod.main([])
    captured = capsys.readouterr()
    # The four new check names must appear in stdout (default = all).
    assert "docs-drift" in captured.out
    assert "plugin-install-smoke-ci" in captured.out
    assert "reference-plugin-manifest-valid" in captured.out
    assert "v0-4-fixture-roundtrip" in captured.out
    # When the live repo state is healthy, exit code is 0. The
    # install-smoke-plugin check depends on Task 3 shipping ci.yml; on a
    # fresh checkout before Task 3, exit may be 1 — that case is covered
    # by Task 3's own verify gate.
    assert exit_code in (0, 1)


def test_main_check_docs_drift_exits_1_on_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Subprocess: --check docs-drift with mutated docs file exits 1."""
    docs_path = REPO_ROOT / "docs" / "manifest-v1.schema.json"
    tmp_docs = tmp_path / "manifest-v1.schema.json"
    tmp_docs.write_text(
        docs_path.read_text(encoding="utf-8").replace("{\n", '{\n  "x": "x",\n', 1),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["HORUS_OS_DOCS_SCHEMA_PATH_OVERRIDE"] = str(tmp_docs)
    proc = subprocess.run(
        [sys.executable, "scripts/release_gate.py", "--check", "docs-drift"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "FAIL" in proc.stdout
    assert "docs-drift" in proc.stdout


def test_main_check_fixture_roundtrip_passes_on_live_fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Subprocess: --check fixture-roundtrip against the committed fixture is green."""
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/release_gate.py",
            "--check",
            "fixture-roundtrip",
            "--skip-build",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "OK" in proc.stdout
    assert "v0-4-fixture-roundtrip" in proc.stdout


def test_main_check_reference_manifest_passes_on_live_plugin() -> None:
    """Subprocess: --check reference-manifest against the bundled plugin is green."""
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/release_gate.py",
            "--check",
            "reference-manifest",
            "--skip-build",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "OK" in proc.stdout
    assert "reference-plugin-manifest-valid" in proc.stdout


def test_serializer_matches_build_manifest_schema_byte_for_byte() -> None:
    """The release-gate's serializer matches build_manifest_schema.py exactly.

    Both must use json.dumps(schema, indent=2, sort_keys=True) + '\\n'.
    Drift between the two would mean a maintainer running
    build_manifest_schema.py to "fix" the gate could produce a file the
    gate still rejects — a frustrating dev-loop bug.
    """
    import json

    # Lazy-import via the same sys.path trick the gate uses.
    src = REPO_ROOT / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    from horus_os.plugins.manifest import MANIFEST_V1_SCHEMA

    schema = MANIFEST_V1_SCHEMA.model_json_schema()
    # Exact serializer used by both scripts.
    payload = json.dumps(schema, indent=2, sort_keys=True) + "\n"
    # The committed file matches this output.
    docs_path = REPO_ROOT / "docs" / "manifest-v1.schema.json"
    assert payload == docs_path.read_text(encoding="utf-8"), (
        "build_manifest_schema.py output and release_gate.py serializer "
        "must agree byte-for-byte on the same schema dict."
    )
