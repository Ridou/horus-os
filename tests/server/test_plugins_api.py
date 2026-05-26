"""Six /api/plugins/* routes + /api/observability/plugins route.

16 tests pinning the REST contract for Phase 45:

  * list_plugins: empty / one loaded / one error-only (spec=None) / shape
  * get_plugin: 404 / detail-shape / grants_log roundtrip
  * enable / disable: SQLite + in-memory roundtrip + needs_restart contract
  * grant: happy / missing-body / unknown-cap / 404 / 409 (no spec)
  * revoke: happy / 404
  * observability/plugins: window roundtrip
  * v0.4 byte-identity guard: existing /api/observability/cost shape stays
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from horus_os import Config, Database, create_app
from horus_os.plugins.spec import CapabilityRequest, PluginSpec


def _init_data_dir(tmp_path: Path) -> Path:
    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    db = Database(cfg.db_path)
    db.init()
    return tmp_path


def _make_spec(
    *,
    name: str = "foo",
    version: str = "1.0",
    author: str = "Test Author",
    homepage: str | None = "https://example.com/foo",
    issue_tracker: str | None = "https://example.com/foo/issues",
    capabilities: tuple[CapabilityRequest, ...] = (
        CapabilityRequest(name="filesystem.read", reason="read config"),
    ),
    manifest_hash: str = "hash-foo-1",
) -> PluginSpec:
    return PluginSpec(
        name=name,
        version=version,
        description="A test plugin.",
        author=author,
        license="MIT",
        horus_os_compat=">=0.5,<0.6",
        homepage=homepage,
        issue_tracker=issue_tracker,
        tool_entries=(("echo_tool", "fake.module:echo"),),
        adapter_entries=(("example_adapter", "fake.module:Adapter"),),
        capabilities=capabilities,
        source="filesystem",
        source_detail="/tmp/fake",
        manifest_hash=manifest_hash,
    )


def _register_plugin(
    app: object,
    spec: PluginSpec,
    *,
    mark_loaded: bool = True,
) -> None:
    """Insert a synthetic plugin into the live PluginRegistry on app.state.

    Tests use this to inject specs without going through the discovery
    pipeline (the loader runs ONLY at create_app boot time).
    """
    registry = app.state.plugin_registry  # type: ignore[attr-defined]
    registry.register(spec)
    if mark_loaded:
        registry.mark_loaded(
            spec.name,
            registered_tools=tuple(t[0] for t in spec.tool_entries),
            registered_adapters=tuple(a[0] for a in spec.adapter_entries),
        )


def _grants_log_rows(db: Database, plugin_name: str) -> list[dict]:
    with db._connect() as conn:
        rows = conn.execute(
            """
            SELECT plugin_name, plugin_version, capability, action,
                   manifest_hash, actor, timestamp
            FROM plugin_capability_grants_log
            WHERE plugin_name = ?
            ORDER BY id ASC
            """,
            (plugin_name,),
        ).fetchall()
    return [dict(r) for r in rows]


# ----------------------------------------------------------------------
# list_plugins
# ----------------------------------------------------------------------


def test_list_plugins_empty(tmp_path: Path) -> None:
    _init_data_dir(tmp_path)
    client = TestClient(create_app(data_dir=tmp_path))
    with client:
        response = client.get("/api/plugins")
    assert response.status_code == 200
    assert response.json() == {"plugins": []}


def test_list_plugins_one_loaded(tmp_path: Path) -> None:
    _init_data_dir(tmp_path)
    app = create_app(data_dir=tmp_path)
    spec = _make_spec()
    client = TestClient(app)
    with client:
        _register_plugin(app, spec, mark_loaded=True)
        response = client.get("/api/plugins")
    assert response.status_code == 200
    body = response.json()
    assert len(body["plugins"]) == 1
    row = body["plugins"][0]
    assert row["name"] == "foo"
    assert row["version"] == "1.0"
    assert row["status"] == "loaded"
    assert row["declared_tools"] == ["echo_tool"]
    assert row["declared_adapters"] == ["example_adapter"]
    assert row["manifest_author"] == "Test Author"
    assert row["manifest_homepage"] == "https://example.com/foo"
    assert row["manifest_issue_tracker"] == "https://example.com/foo/issues"
    assert row["enabled"] is True
    # filesystem.read was requested but never granted -> pending.
    assert row["granted_capabilities"] == []
    assert row["pending_capabilities"] == ["filesystem.read"]


def test_list_plugins_error_entry_no_spec(tmp_path: Path) -> None:
    """DiscoveryError-only rows (spec=None) show up with version='' + empty tuples."""
    _init_data_dir(tmp_path)
    app = create_app(data_dir=tmp_path)
    client = TestClient(app)
    with client:
        registry = app.state.plugin_registry
        registry.register_discovery_error(
            "brokenplugin",
            source="filesystem",
            source_detail="/tmp/broken",
            error_phase="discover",
            error_message="bad manifest.toml",
        )
        response = client.get("/api/plugins")
    assert response.status_code == 200
    body = response.json()
    assert len(body["plugins"]) == 1
    row = body["plugins"][0]
    assert row["name"] == "brokenplugin"
    assert row["version"] == ""
    assert row["status"] == "error"
    assert row["error_phase"] == "discover"
    assert row["last_error"] == "bad manifest.toml"
    assert row["declared_tools"] == []
    assert row["declared_adapters"] == []
    assert row["granted_capabilities"] == []
    assert row["pending_capabilities"] == []
    assert row["manifest_author"] == ""
    assert row["manifest_homepage"] is None


# ----------------------------------------------------------------------
# get_plugin
# ----------------------------------------------------------------------


def test_get_plugin_404(tmp_path: Path) -> None:
    _init_data_dir(tmp_path)
    client = TestClient(create_app(data_dir=tmp_path))
    with client:
        response = client.get("/api/plugins/nonexistent")
    assert response.status_code == 404
    assert "nonexistent" in response.json()["detail"]


def test_get_plugin_includes_grants_log(tmp_path: Path) -> None:
    """Three audit-log rows -> detail.grants_log returns all 3, newest first."""
    _init_data_dir(tmp_path)
    app = create_app(data_dir=tmp_path)
    spec = _make_spec()
    cfg = Config.load(tmp_path)
    db = Database(cfg.db_path)
    client = TestClient(app)
    with client:
        _register_plugin(app, spec, mark_loaded=True)
        # Seed 3 audit-log rows directly.
        with db._connect() as conn:
            for i, (action, actor) in enumerate(
                [("granted", "cli"), ("revoked", "dashboard"), ("granted", "system")]
            ):
                conn.execute(
                    """
                    INSERT INTO plugin_capability_grants_log
                        (plugin_name, plugin_version, capability, action,
                         manifest_hash, actor, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "foo",
                        "1.0",
                        "filesystem.read",
                        action,
                        "hash-foo-1",
                        actor,
                        f"2099-01-0{i + 1}T00:00:00Z",
                    ),
                )
        response = client.get("/api/plugins/foo")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "foo"
    assert len(body["grants_log"]) == 3
    # Newest first.
    assert body["grants_log"][0]["action"] == "granted"
    assert body["grants_log"][0]["actor"] == "system"
    assert body["grants_log"][2]["actor"] == "cli"


# ----------------------------------------------------------------------
# enable / disable
# ----------------------------------------------------------------------


def test_enable_plugin(tmp_path: Path) -> None:
    _init_data_dir(tmp_path)
    app = create_app(data_dir=tmp_path)
    spec = _make_spec()
    cfg = Config.load(tmp_path)
    client = TestClient(app)
    with client:
        _register_plugin(app, spec, mark_loaded=True)
        # First disable so we can re-enable it.
        client.post("/api/plugins/foo/disable")
        response = client.post("/api/plugins/foo/enable")
    assert response.status_code == 200
    assert response.json() == {"name": "foo", "enabled": True, "needs_restart": True}
    # Verify plugins.enabled flipped to 1 via a fresh connection.
    db2 = Database(cfg.db_path)
    with db2._connect() as conn:
        row = conn.execute("SELECT enabled FROM plugins WHERE name = ?", ("foo",)).fetchone()
    assert row is not None
    assert row["enabled"] == 1


def test_enable_plugin_404(tmp_path: Path) -> None:
    _init_data_dir(tmp_path)
    client = TestClient(create_app(data_dir=tmp_path))
    with client:
        response = client.post("/api/plugins/unknown/enable")
    assert response.status_code == 404


def test_disable_plugin(tmp_path: Path) -> None:
    _init_data_dir(tmp_path)
    app = create_app(data_dir=tmp_path)
    spec = _make_spec()
    cfg = Config.load(tmp_path)
    client = TestClient(app)
    with client:
        _register_plugin(app, spec, mark_loaded=True)
        response = client.post("/api/plugins/foo/disable")
        # Inspect in-memory entry status.
        in_memory_status = app.state.plugin_registry.get("foo").status
    assert response.status_code == 200
    assert response.json() == {"name": "foo", "enabled": False, "needs_restart": True}
    assert in_memory_status == "disabled"
    # Verify plugins.enabled flipped to 0.
    db2 = Database(cfg.db_path)
    with db2._connect() as conn:
        row = conn.execute("SELECT enabled FROM plugins WHERE name = ?", ("foo",)).fetchone()
    assert row["enabled"] == 0


# ----------------------------------------------------------------------
# grant
# ----------------------------------------------------------------------


def test_grant_happy_path(tmp_path: Path) -> None:
    _init_data_dir(tmp_path)
    app = create_app(data_dir=tmp_path)
    spec = _make_spec()
    cfg = Config.load(tmp_path)
    db = Database(cfg.db_path)
    client = TestClient(app)
    with client:
        _register_plugin(app, spec, mark_loaded=True)
        response = client.post("/api/plugins/foo/grant", json={"capability": "filesystem.read"})
    assert response.status_code == 200
    rows = _grants_log_rows(db, "foo")
    assert len(rows) == 1
    assert rows[0]["action"] == "granted"
    assert rows[0]["actor"] == "dashboard"
    assert rows[0]["manifest_hash"] == "hash-foo-1"
    assert rows[0]["capability"] == "filesystem.read"


def test_grant_missing_body(tmp_path: Path) -> None:
    _init_data_dir(tmp_path)
    app = create_app(data_dir=tmp_path)
    spec = _make_spec()
    client = TestClient(app)
    with client:
        _register_plugin(app, spec, mark_loaded=True)
        response = client.post("/api/plugins/foo/grant", json={})
    assert response.status_code == 400
    assert "capability" in response.json()["detail"].lower()


def test_grant_unknown_capability(tmp_path: Path) -> None:
    _init_data_dir(tmp_path)
    app = create_app(data_dir=tmp_path)
    spec = _make_spec()
    client = TestClient(app)
    with client:
        _register_plugin(app, spec, mark_loaded=True)
        response = client.post("/api/plugins/foo/grant", json={"capability": "made.up.cap"})
    assert response.status_code == 400
    detail = response.json()["detail"].lower()
    assert "unknown" in detail or "must be one of" in detail


def test_grant_404_plugin(tmp_path: Path) -> None:
    _init_data_dir(tmp_path)
    client = TestClient(create_app(data_dir=tmp_path))
    with client:
        response = client.post("/api/plugins/unknown/grant", json={"capability": "filesystem.read"})
    assert response.status_code == 404


def test_grant_409_no_spec(tmp_path: Path) -> None:
    """A DiscoveryError-only registry entry (spec=None) -> 409 on grant."""
    _init_data_dir(tmp_path)
    app = create_app(data_dir=tmp_path)
    client = TestClient(app)
    with client:
        registry = app.state.plugin_registry
        registry.register_discovery_error(
            "broken",
            source="filesystem",
            source_detail="/tmp/broken",
            error_phase="discover",
            error_message="bad",
        )
        response = client.post("/api/plugins/broken/grant", json={"capability": "filesystem.read"})
    assert response.status_code == 409
    assert "spec" in response.json()["detail"].lower()


# ----------------------------------------------------------------------
# revoke
# ----------------------------------------------------------------------


def test_revoke_happy_path(tmp_path: Path) -> None:
    """Grant -> revoke roundtrip; audit log carries both rows."""
    _init_data_dir(tmp_path)
    app = create_app(data_dir=tmp_path)
    spec = _make_spec()
    cfg = Config.load(tmp_path)
    db = Database(cfg.db_path)
    client = TestClient(app)
    with client:
        _register_plugin(app, spec, mark_loaded=True)
        # First grant.
        grant_response = client.post(
            "/api/plugins/foo/grant", json={"capability": "filesystem.read"}
        )
        assert grant_response.status_code == 200
        # Now revoke.
        revoke_response = client.delete("/api/plugins/foo/grant/filesystem.read")
    assert revoke_response.status_code == 200
    rows = _grants_log_rows(db, "foo")
    assert len(rows) == 2
    assert rows[0]["action"] == "granted"
    assert rows[1]["action"] == "revoked"
    assert rows[1]["actor"] == "dashboard"
    # Verify plugin_capabilities.state flipped to 'revoked'.
    with db._connect() as conn:
        cap_row = conn.execute(
            "SELECT state FROM plugin_capabilities WHERE plugin_name = ? AND capability = ?",
            ("foo", "filesystem.read"),
        ).fetchone()
    assert cap_row["state"] == "revoked"


def test_revoke_404_plugin(tmp_path: Path) -> None:
    _init_data_dir(tmp_path)
    client = TestClient(create_app(data_dir=tmp_path))
    with client:
        response = client.delete("/api/plugins/unknown/grant/filesystem.read")
    assert response.status_code == 404


# ----------------------------------------------------------------------
# /api/observability/plugins
# ----------------------------------------------------------------------


def test_observability_plugins_route(tmp_path: Path) -> None:
    """Seed mixed plugin_name rows; route returns the per-plugin rollup."""
    _init_data_dir(tmp_path)
    app = create_app(data_dir=tmp_path)
    cfg = Config.load(tmp_path)
    db = Database(cfg.db_path)
    client = TestClient(app)
    with client:
        # Seed three buckets: plugin_a / plugin_b / NULL.
        with db._connect() as conn:
            for i in range(3):
                conn.execute(
                    """
                    INSERT INTO tool_invocations
                        (invocation_id, trace_id, created_at, tool_name, latency_ms,
                         status, plugin_name)
                    VALUES (?, 't', '2099-01-01T00:00:00Z', 'echo', 50, 'success', ?)
                    """,
                    (f"a-{i}", "plugin_a"),
                )
            for i in range(3):
                conn.execute(
                    """
                    INSERT INTO tool_invocations
                        (invocation_id, trace_id, created_at, tool_name, latency_ms,
                         status, plugin_name)
                    VALUES (?, 't', '2099-01-01T00:00:00Z', 'echo', 50, 'success', ?)
                    """,
                    (f"b-{i}", "plugin_b"),
                )
            for i in range(3):
                conn.execute(
                    """
                    INSERT INTO tool_invocations
                        (invocation_id, trace_id, created_at, tool_name, latency_ms,
                         status, plugin_name)
                    VALUES (?, 't', '2099-01-01T00:00:00Z', 'echo', 50, 'success', NULL)
                    """,
                    (f"core-{i}",),
                )

        response = client.get("/api/observability/plugins?since=7d")
    assert response.status_code == 200
    body = response.json()
    names = {p["plugin_name"] for p in body["plugins"]}
    assert names == {"plugin_a", "plugin_b", "horus-os core"}

    # Bad window -> 400.
    with client:
        bad = client.get("/api/observability/plugins?since=garbage")
    assert bad.status_code == 400


def test_v04_observability_byte_identity(tmp_path: Path) -> None:
    """v0.4 byte-identity guard: existing /api/observability/cost shape unchanged.

    Phase 36 documented the response as ``{"agents": [...]}``; this test
    pins that the Phase 45 changes do not alter the existing routes.
    """
    _init_data_dir(tmp_path)
    client = TestClient(create_app(data_dir=tmp_path))
    with client:
        response = client.get("/api/observability/cost?since=7d")
    assert response.status_code == 200
    body = response.json()
    # The Phase 36 contract: top-level key is 'agents'.
    assert "agents" in body
    assert isinstance(body["agents"], list)
