"""Tests for Config."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from horus_os import Config
from horus_os.config import CONFIG_FILENAME


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
