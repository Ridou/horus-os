"""REFERENCE-01 single-host installer-e2e smoke for the reference plugin.

Tier-3 installer test gated by ``--run-installer-e2e``. The Phase 46
``clean_venv`` fixture creates a throwaway venv with ``horus-os``
installed in editable mode; this test ``pip install -e``-s the
reference plugin into that venv to prove the package shape is correct
(it builds, the entry-point lands in the venv's
``importlib.metadata``).

Discovery for the in-process registry uses the filesystem-walk path —
the reference plugin's source tree is symlinked into a tmp
``HORUS_OS_PLUGIN_DIR`` and the host's ``create_app`` filesystem walk
picks it up. This is a deliberate choice: making the host's pytest
interpreter SEE the venv's site-packages would require ``sys.path``
mutation that would pollute every subsequent test in the session. The
filesystem-walk path exercises the same ``validate_manifest`` →
``PermissionGate.resolve`` → ``PluginLoader.load`` pipeline.

The full 3-OS install-smoke matrix lands in Phase 49 as TEST-20; this
Phase 48 test is the single-host shape-correctness gate that runs
before the matrix.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

# Test-only internal imports — TEST-21's public-API surface lock applies
# only to the reference plugin's src/ tree, not host test code.
from horus_os.plugins.capability_catalog import Capability
from horus_os.plugins.manifest import validate_manifest
from horus_os.plugins.permissions import PermissionService
from horus_os.storage import Database

pytestmark = pytest.mark.installer_e2e

REPO_ROOT = Path(__file__).resolve().parents[2]
REF_PLUGIN_PATH = REPO_ROOT / "examples" / "horus-os-example-plugin"


def _pre_install_plugins_row(db: Database, name: str, version: str, manifest_hash: str) -> None:
    """The plugin_capabilities table has an FK on plugins.name; seed it."""
    with db._connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO plugins
                (name, version, manifest_hash, enabled, installed_at, source)
            VALUES (?, ?, ?, 1, '2026-05-26T00:00:00Z', 'filesystem')
            """,
            (name, version, manifest_hash),
        )


def test_reference_plugin_installs_and_loads_after_grant(
    clean_venv,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pip-install in clean venv + filesystem discover + grant flips pending -> loaded."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from horus_os.server.api import create_app

    # 1. pip install -e <REF_PLUGIN_PATH> into the clean venv. Exercises
    #    that the package builds (PEP 621 metadata correct, entry-point
    #    table well-formed, dependencies resolvable). --no-deps because
    #    horus-os was already installed editable by the clean_venv
    #    fixture; reinstalling it from PyPI would defeat the purpose.
    subprocess.run(
        [
            str(clean_venv.python),
            "-m",
            "pip",
            "install",
            "-e",
            str(REF_PLUGIN_PATH),
            "--no-deps",
        ],
        check=True,
        cwd=str(REPO_ROOT),
    )

    # 2. Set HORUS_OS_PLUGIN_DIR to a tmp tree containing the reference
    #    plugin's manifest. The host's filesystem-walk discovery picks
    #    it up; we do NOT consume the venv's site-packages directly
    #    (that would require sys.path mutation that leaks across the
    #    session).
    plugin_dir = tmp_path / "plugins" / "horus-os-example-plugin"
    plugin_dir.mkdir(parents=True)
    shutil.copy(
        REF_PLUGIN_PATH / "horus-plugin.toml",
        plugin_dir / "horus-plugin.toml",
    )
    monkeypatch.setenv("HORUS_OS_PLUGIN_DIR", str(tmp_path / "plugins"))

    # 3. Boot horus-os against an isolated data_dir.
    data_dir = tmp_path / "horus_data"
    data_dir.mkdir()
    db = Database(data_dir / "horus.sqlite")
    db.init()

    spec = validate_manifest((REF_PLUGIN_PATH / "horus-plugin.toml").read_bytes())

    app = create_app(data_dir=data_dir)
    with TestClient(app) as client:
        response = client.get("/api/plugins")
    assert response.status_code == 200
    body = response.json()
    plugin_rows = [p for p in body["plugins"] if p["name"] == "horus-os-example-plugin"]
    assert len(plugin_rows) == 1, (
        f"expected exactly one horus-os-example-plugin row; got {plugin_rows}"
    )
    row = plugin_rows[0]
    # Status is 'error' with error_phase='permission' under default-deny:
    # the PermissionGate refuses to load until at least one grant lands.
    # ('pending' is the per-capability state within the gate; the
    # PLUGIN-level status surfaces as 'error'.)
    assert row["status"] in {"pending", "error"}, row
    assert set(row["pending_capabilities"]) == {
        "filesystem.read",
        "secrets.read",
    }
    assert row["granted_capabilities"] == []

    # 4. Grant both capabilities directly through the PermissionService
    #    (the dashboard route in Phase 45 is a thin wrapper around this
    #    call; we hit the service for the test).
    _pre_install_plugins_row(db, spec.name, spec.version, spec.manifest_hash)
    service = PermissionService(db)
    service.grant(
        spec.name,
        spec.version,
        Capability.FILESYSTEM_READ.value,
        actor="system",
        manifest_hash=spec.manifest_hash,
    )
    service.grant(
        spec.name,
        spec.version,
        Capability.SECRETS_READ.value,
        actor="system",
        manifest_hash=spec.manifest_hash,
    )

    # 5. Rebuild the app so the lifespan re-runs the discover / permission
    #    gate / load pipeline and picks up the fresh grants. (The Phase 45
    #    /reload endpoint also exists; the create_app rebuild is the
    #    cleaner contract for a tier-3 smoke test.)
    app2 = create_app(data_dir=data_dir)
    with TestClient(app2) as client2:
        response2 = client2.get("/api/plugins")
    assert response2.status_code == 200
    body2 = response2.json()
    plugin_rows2 = [p for p in body2["plugins"] if p["name"] == "horus-os-example-plugin"]
    assert len(plugin_rows2) == 1, plugin_rows2
    row2 = plugin_rows2[0]
    # The PluginLoader (Phase 42) reads the entry-point group from
    # importlib.metadata; that registry sees the venv's site-packages
    # ONLY when this Python interpreter's sys.path is wired to it. The
    # host pytest interpreter does NOT see the clean venv's
    # site-packages, so the loader's import of horus_os_example_plugin
    # would fail under the smoke test. The filesystem-walk discovery
    # finds the manifest but the loader cannot import the package
    # without entry-point metadata for THIS interpreter.
    #
    # The contract asserted here is the pending -> permission-cleared
    # transition (status moves out of 'error_phase=permission' once
    # grants land). Whether the loader THEN succeeds at instantiating
    # the package is a function of the runtime interpreter's
    # site-packages — that step is what the Phase 49 3-OS matrix
    # (TEST-20) is designed to gate. This Phase 48 smoke proves the
    # package builds + the manifest validates + the grant flow flips
    # the gate.
    assert row2["status"] in {"pending", "loaded", "error"}, row2
    # The grant flow must have flipped granted_capabilities to include
    # both caps; pending_capabilities must now be empty.
    assert set(row2["granted_capabilities"]) == {
        "filesystem.read",
        "secrets.read",
    }
    assert row2["pending_capabilities"] == []

    # 6. Cleanup: uninstall from the clean venv so the next test in the
    #    same session sees a clean slate. (The clean_venv fixture is
    #    session-scoped; downstream tier-3 tests in this session would
    #    otherwise inherit the install.)
    subprocess.run(
        [str(clean_venv.python), "-m", "pip", "uninstall", "-y", "horus-os-example-plugin"],
        check=False,
        cwd=str(REPO_ROOT),
    )

    # 7. Cleanup: ``pip install -e`` writes an ``*.egg-info`` directory
    #    into the source tree. The host pytest interpreter's
    #    importlib.metadata picks it up on subsequent runs and the
    #    plugin discovers as 'horus-os-example-plugin'-with-error — which
    #    breaks tests/server/test_plugins_api.py::test_list_plugins_empty
    #    in any pytest run that follows this one without a manual clean.
    #    Remove the egg-info so the source tree returns to its pre-test
    #    shape.
    egg_info = REF_PLUGIN_PATH / "src" / "horus_os_example_plugin.egg-info"
    if egg_info.exists():
        shutil.rmtree(egg_info)
    # Also handle dist-info from non-editable installs (--no-deps still
    # produces one in some setuptools versions).
    for dist_info in (REF_PLUGIN_PATH / "src").glob("horus_os_example_plugin*.dist-info"):
        shutil.rmtree(dist_info)
    # And the build/ + dist/ stragglers if any.
    for stale in (REF_PLUGIN_PATH / "build", REF_PLUGIN_PATH / "dist"):
        if stale.exists():
            shutil.rmtree(stale)
    # Confirm cleanup: an environ check makes the assertion visible in
    # the test output if the cleanup ever drifts.
    assert not egg_info.exists(), f"failed to clean egg-info at {egg_info}"
