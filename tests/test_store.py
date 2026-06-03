"""Tests for the agent store: bundle catalog + install / export routes."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from horus_os import Config, Database, create_app
from horus_os.store import (
    FEATURED_BUNDLES,
    bundle_to_profile,
    get_bundle,
    list_bundles,
    profile_to_bundle,
)


def _init_db(tmp_path: Path) -> Database:
    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    db = Database(cfg.db_path)
    db.init()
    return db


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(data_dir=tmp_path))


# -- catalog ------------------------------------------------------------------


def test_featured_bundles_present() -> None:
    slugs = {b.slug for b in list_bundles()}
    assert {"atlas", "vitriol", "sol"} <= slugs
    assert len(FEATURED_BUNDLES) == len(slugs)  # slugs are unique


def test_get_bundle_is_case_insensitive() -> None:
    assert get_bundle("ATLAS") is not None
    assert get_bundle("atlas").name == "Atlas"
    assert get_bundle("missing") is None


def test_wellness_bundle_carries_not_medical_advice_framing() -> None:
    vitriol = get_bundle("vitriol")
    assert vitriol is not None
    prompt = vitriol.system_prompt.lower()
    assert "not a doctor" in prompt or "not give medical advice" in prompt
    assert "diagnos" in prompt  # refuses to diagnose


def test_bundle_to_profile_maps_fields() -> None:
    bundle = get_bundle("atlas")
    assert bundle is not None
    profile = bundle_to_profile(bundle)
    assert profile.name == "Atlas"
    assert profile.system_prompt == bundle.system_prompt
    assert profile.allowed_tools == bundle.recommended_tools
    assert profile.color == bundle.color


def test_profile_to_bundle_round_trips_core_fields() -> None:
    bundle = get_bundle("sol")
    assert bundle is not None
    exported = profile_to_bundle(bundle_to_profile(bundle))
    assert exported["name"] == "Sol"
    assert exported["system_prompt"] == bundle.system_prompt
    assert exported["recommended_tools"] == bundle.recommended_tools


# -- store routes -------------------------------------------------------------


def test_store_list_flags_installed(tmp_path: Path) -> None:
    _init_db(tmp_path)
    client = _client(tmp_path)
    body = client.get("/api/store").json()
    slugs = {b["slug"]: b for b in body["bundles"]}
    assert "atlas" in slugs
    assert slugs["atlas"]["installed"] is False
    # System prompt is NOT in the grid summary.
    assert "system_prompt" not in slugs["atlas"]

    client.post("/api/store/atlas/install")
    after = {b["slug"]: b for b in client.get("/api/store").json()["bundles"]}
    assert after["atlas"]["installed"] is True


def test_store_detail_includes_persona(tmp_path: Path) -> None:
    _init_db(tmp_path)
    body = _client(tmp_path).get("/api/store/vitriol").json()
    assert body["name"] == "Vitriol"
    assert body["system_prompt"]
    assert body["installed"] is False


def test_store_detail_404(tmp_path: Path) -> None:
    _init_db(tmp_path)
    assert _client(tmp_path).get("/api/store/ghost").status_code == 404


def test_store_install_creates_profile(tmp_path: Path) -> None:
    db = _init_db(tmp_path)
    client = _client(tmp_path)
    resp = client.post("/api/store/atlas/install")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Atlas"
    profile = db.load_profile("Atlas")
    assert profile is not None
    assert profile.allowed_tools and "web_search" in profile.allowed_tools


def test_store_install_conflict_when_already_installed(tmp_path: Path) -> None:
    _init_db(tmp_path)
    client = _client(tmp_path)
    assert client.post("/api/store/sol/install").status_code == 200
    assert client.post("/api/store/sol/install").status_code == 409


def test_store_install_unknown_slug_404(tmp_path: Path) -> None:
    _init_db(tmp_path)
    assert _client(tmp_path).post("/api/store/nope/install").status_code == 404


def test_agents_export_round_trips_installed_bundle(tmp_path: Path) -> None:
    _init_db(tmp_path)
    client = _client(tmp_path)
    client.post("/api/store/atlas/install")
    exported = client.get("/api/agents/Atlas/export").json()
    assert exported["name"] == "Atlas"
    assert exported["system_prompt"]
    assert "web_search" in exported["recommended_tools"]


def test_agents_create_accepts_color_and_description(tmp_path: Path) -> None:
    _init_db(tmp_path)
    client = _client(tmp_path)
    resp = client.post(
        "/api/agents",
        json={
            "name": "Custom",
            "system_prompt": "You are a custom agent.",
            "color": "#ff00aa",
            "description": "A bespoke helper.",
        },
    )
    assert resp.status_code == 200
    # color/description are persisted on the profile and surface via /api/team.
    team = client.get("/api/team").json()
    custom = next((a for a in team["agents"] if a["name"] == "Custom"), None)
    assert custom is not None
    assert custom["color"] == "#ff00aa"
    assert custom["description"] == "A bespoke helper."
