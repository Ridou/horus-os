"""Tests for Config."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from horus_os import Config
from horus_os.config import CONFIG_FILENAME

# ---------------------------------------------------------------------------
# Phase 34 Task 1: pricing_path field + HORUS_OS_PRICING_PATH env override +
# [pricing] TOML table override.
# ---------------------------------------------------------------------------


def test_pricing_path_defaults_to_none(tmp_path: Path) -> None:
    cfg = Config.with_defaults(tmp_path)
    assert cfg.pricing_path is None


def test_pricing_path_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    override = tmp_path / "custom_pricing.json"
    monkeypatch.setenv("HORUS_OS_PRICING_PATH", str(override))
    cfg = Config.load(tmp_path)
    assert cfg.pricing_path == override


def test_pricing_path_toml_value(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HORUS_OS_PRICING_PATH", raising=False)
    toml_pricing = tmp_path / "from_toml.json"
    contents = f'[pricing]\npath = "{toml_pricing.as_posix()}"\n'
    (tmp_path / CONFIG_FILENAME).write_text(contents)
    cfg = Config.load(tmp_path)
    assert cfg.pricing_path == toml_pricing


def test_pricing_path_env_beats_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_pricing = tmp_path / "from_env.json"
    toml_pricing = tmp_path / "from_toml.json"
    monkeypatch.setenv("HORUS_OS_PRICING_PATH", str(env_pricing))
    contents = f'[pricing]\npath = "{toml_pricing.as_posix()}"\n'
    (tmp_path / CONFIG_FILENAME).write_text(contents)
    cfg = Config.load(tmp_path)
    assert cfg.pricing_path == env_pricing


def test_save_omits_pricing_table_when_none(tmp_path: Path) -> None:
    cfg = Config.with_defaults(tmp_path)
    assert cfg.pricing_path is None
    cfg.save()
    dumped = (tmp_path / CONFIG_FILENAME).read_text()
    assert "[pricing]" not in dumped


def test_save_round_trips_pricing_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HORUS_OS_PRICING_PATH", raising=False)
    custom = tmp_path / "round_trip_pricing.json"
    cfg = Config.with_defaults(tmp_path)
    cfg.pricing_path = custom
    cfg.save()
    loaded = Config.load(tmp_path)
    assert loaded.pricing_path == custom


def test_with_defaults_under_given_dir(tmp_path: Path) -> None:
    config = Config.with_defaults(tmp_path)
    assert config.data_dir == tmp_path
    assert config.db_path == tmp_path / "horus.sqlite"
    assert config.notes_dir == tmp_path / "notes"
    assert config.default_provider == "anthropic"
    assert config.anthropic_model == "claude-sonnet-4-6"
    assert config.gemini_model == "gemini-2.5-flash"


def test_default_data_dir_respects_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HORUS_OS_DATA_DIR", str(tmp_path / "from_env"))
    assert Config.default_data_dir() == tmp_path / "from_env"


def test_default_data_dir_macos_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HORUS_OS_DATA_DIR", raising=False)
    monkeypatch.setattr(sys, "platform", "darwin")
    expected = Path.home() / "Library" / "Application Support" / "horus-os"
    assert Config.default_data_dir() == expected


def test_default_data_dir_linux_with_xdg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HORUS_OS_DATA_DIR", raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    assert Config.default_data_dir() == tmp_path / "xdg" / "horus-os"


def test_default_data_dir_linux_without_xdg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HORUS_OS_DATA_DIR", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    assert Config.default_data_dir() == Path.home() / ".local" / "share" / "horus-os"


def test_default_data_dir_windows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HORUS_OS_DATA_DIR", raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    assert Config.default_data_dir() == tmp_path / "Roaming" / "horus-os"


def test_load_returns_defaults_when_file_missing(tmp_path: Path) -> None:
    config = Config.load(tmp_path)
    assert config.data_dir == tmp_path
    assert (tmp_path / CONFIG_FILENAME).exists() is False


def test_save_then_load_round_trip(tmp_path: Path) -> None:
    original = Config.with_defaults(tmp_path)
    original.save()
    loaded = Config.load(tmp_path)
    assert loaded.data_dir == original.data_dir
    assert loaded.db_path == original.db_path
    assert loaded.notes_dir == original.notes_dir
    assert loaded.default_provider == original.default_provider
    assert loaded.anthropic_model == original.anthropic_model
    assert loaded.gemini_model == original.gemini_model


def test_load_applies_overrides_from_toml(tmp_path: Path) -> None:
    Config.with_defaults(tmp_path).save()
    overridden = (
        "[providers]\n"
        'default = "gemini"\n'
        'anthropic_model = "claude-haiku-4-5-20251001"\n'
        'gemini_model = "gemini-2.5-pro"\n'
        "[storage]\n"
        f'db_path = "{(tmp_path / "alt.sqlite").as_posix()}"\n'
        "[notes]\n"
        f'notes_dir = "{(tmp_path / "alt_notes").as_posix()}"\n'
    )
    (tmp_path / CONFIG_FILENAME).write_text(overridden)
    loaded = Config.load(tmp_path)
    assert loaded.default_provider == "gemini"
    assert loaded.anthropic_model == "claude-haiku-4-5-20251001"
    assert loaded.gemini_model == "gemini-2.5-pro"
    assert loaded.db_path == tmp_path / "alt.sqlite"
    assert loaded.notes_dir == tmp_path / "alt_notes"


def test_load_falls_back_on_corrupted_toml(tmp_path: Path) -> None:
    (tmp_path / CONFIG_FILENAME).write_text("this is { not valid toml")
    loaded = Config.load(tmp_path)
    assert loaded.default_provider == "anthropic"


def test_save_creates_data_dir_if_missing(tmp_path: Path) -> None:
    target = tmp_path / "newly_made"
    config = Config.with_defaults(target)
    config.save()
    assert (target / CONFIG_FILENAME).exists()


def test_save_is_atomic_on_overwrite(tmp_path: Path) -> None:
    config = Config.with_defaults(tmp_path)
    config.save()
    first_content = (tmp_path / CONFIG_FILENAME).read_text()
    config.save()
    second_content = (tmp_path / CONFIG_FILENAME).read_text()
    assert first_content == second_content
    # No tmp file lingers
    leftovers = [p for p in tmp_path.iterdir() if p.name.startswith(".config.toml.")]
    assert leftovers == []


# ---------------------------------------------------------------------------
# Phase 72 (WEB-01): [tools.web_search] table -> web_search_provider /
# web_search_base_url fields. Absent table leaves both None; a configured table
# round-trips through save/load without persisting any API key.
# ---------------------------------------------------------------------------


def test_web_search_defaults_to_none(tmp_path: Path) -> None:
    cfg = Config.with_defaults(tmp_path)
    assert cfg.web_search_provider is None
    assert cfg.web_search_base_url is None


def test_web_search_absent_table_leaves_none(tmp_path: Path) -> None:
    (tmp_path / CONFIG_FILENAME).write_text('[providers]\ndefault = "anthropic"\n')
    loaded = Config.load(tmp_path)
    assert loaded.web_search_provider is None
    assert loaded.web_search_base_url is None


def test_web_search_read_from_toml(tmp_path: Path) -> None:
    contents = '[tools.web_search]\nprovider = "searxng"\nbase_url = "http://searxng.local:8080"\n'
    (tmp_path / CONFIG_FILENAME).write_text(contents)
    loaded = Config.load(tmp_path)
    assert loaded.web_search_provider == "searxng"
    assert loaded.web_search_base_url == "http://searxng.local:8080"


def test_save_omits_web_search_table_when_unset(tmp_path: Path) -> None:
    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    dumped = (tmp_path / CONFIG_FILENAME).read_text()
    assert "[tools.web_search]" not in dumped


def test_save_round_trips_web_search(tmp_path: Path) -> None:
    cfg = Config.with_defaults(tmp_path)
    cfg.web_search_provider = "searxng"
    cfg.web_search_base_url = "http://searxng.local:8080"
    cfg.save()
    dumped = (tmp_path / CONFIG_FILENAME).read_text()
    assert "[tools.web_search]" in dumped
    # No API key is ever persisted to config.toml.
    assert "HORUS_OS_WEB_SEARCH_KEY" not in dumped
    loaded = Config.load(tmp_path)
    assert loaded.web_search_provider == "searxng"
    assert loaded.web_search_base_url == "http://searxng.local:8080"
