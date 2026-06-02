"""Configuration for a horus-os installation.

A single TOML file at `<data_dir>/config.toml` holds the installation's
runtime settings. The Config dataclass loads it on startup, applies the
HORUS_OS_DATA_DIR environment override, and falls back to platform
defaults when no explicit data_dir is supplied.

The schema is intentionally small for v0.1. Future phases will add
sections for transport (web port), agent defaults, and tool sandbox
configuration. Adding a field is additive; readers that miss a field
get the default from the dataclass.
"""

from __future__ import annotations

import os
import sys
import tempfile
import tomllib
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

CONFIG_FILENAME = "config.toml"
DEFAULT_NOTES_SUBDIR = "notes"
DEFAULT_DB_FILENAME = "horus.sqlite"
# Phase 69 (LP-4): loopback default for the local provider base_url. Kept
# here so _dump_toml can compare against it and only emit the [local]
# section when the user has changed the URL or set a model. Never use the
# literal "0.0.0.0" here; that would expose the local model API to the LAN.
DEFAULT_LOCAL_BASE_URL = "http://localhost:11434/v1"


@dataclass
class Config:
    """Runtime settings for one horus-os installation."""

    data_dir: Path
    db_path: Path
    notes_dir: Path
    default_provider: str = "anthropic"
    anthropic_model: str = "claude-sonnet-4-6"
    gemini_model: str = "gemini-2.5-flash"
    # Phase 34: optional override path for the bundled pricing.json.
    # None signals "use bundled package data via importlib.resources".
    # Precedence (highest first): HORUS_OS_PRICING_PATH env var, then the
    # [pricing] path key in config.toml, then None. PricingTable consumes
    # this value at create_app boot.
    pricing_path: Path | None = None
    # Phase 69: local OpenAI-compatible provider settings. The default
    # base_url is a loopback address per LP-4; it never contains the
    # literal "0.0.0.0", which would expose the local model API to the
    # LAN. local_model is empty (unset) by default; a user must point it
    # at a model their local server serves. local_context_window is a
    # conservative LP-3 default the tool loop can budget against.
    local_base_url: str = DEFAULT_LOCAL_BASE_URL
    local_model: str = ""
    local_context_window: int = 4096
    # Phase 70 (MEM-05/MEM-06): on-device hybrid vector memory. The feature
    # is OFF by default; a user must opt in (and run `horus-os memory
    # download-model`) before any embedding happens, so a fresh install
    # starts and serves notes offline with no model file present.
    # models_dir is None by default and resolves lazily to <data_dir>/models
    # via models_path(); callers must never recompute that path themselves.
    vector_memory_enabled: bool = False
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    models_dir: Path | None = None
    # Phase 72 (WEB-01): bring-your-own web search. Both default to None so the
    # web_search tool is ABSENT from the default registry until a provider is
    # configured (default-deny). web_search_provider is one of searxng / brave /
    # tavily; web_search_base_url is the SearXNG instance URL (required for
    # searxng, optional for the hosted providers). The provider API key is read
    # from HORUS_OS_WEB_SEARCH_KEY at registration time and is NEVER persisted
    # to config.toml, so no secret lands in committed text.
    web_search_provider: str | None = None
    web_search_base_url: str | None = None
    # Phase 73 (RESEARCH-04): hard caps for a native Deep Research run. Both
    # are config-driven hard limits the coordinator can never silently exceed:
    # research_max_sources caps how many distinct URLs the SourceRegistry will
    # accept, and research_max_iterations sizes the shared IterationBudget that
    # bounds the whole delegation tree. The defaults match FEATURES.md (10
    # sources, 5 iterations) and round-trip through a [research] section.
    research_max_sources: int = 10
    research_max_iterations: int = 5

    def models_path(self) -> Path:
        """Return the directory that holds downloaded embedding models.

        Defaults to `<data_dir>/models` when models_dir is unset. This is the
        single source of truth for the fastembed cache location, so the CLI,
        the embedding backend, and doctor all agree on where the model lives.
        """
        return self.models_dir or (self.data_dir / "models")

    def vectors_path(self) -> Path:
        """Return the path of the separate vector-index cache file.

        Phase 70 (Option B): the vector index lives in its own
        `<data_dir>/vectors.sqlite` file managed entirely by VectorIndex, NOT
        in the authoritative `horus.sqlite`. Keeping it separate avoids any
        SCHEMA_VERSION bump (the index is a rebuildable cache, not audited
        storage) and lets the file be deleted and rebuilt with `horus-os
        memory reindex` without touching the note_writes audit trail.
        """
        return self.data_dir / "vectors.sqlite"

    @classmethod
    def default_data_dir(cls) -> Path:
        """Return the platform-appropriate default data directory."""
        env_override = os.environ.get("HORUS_OS_DATA_DIR")
        if env_override:
            return Path(env_override).expanduser()
        if sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / "horus-os"
        if sys.platform == "win32":
            appdata = os.environ.get("APPDATA")
            base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
            return base / "horus-os"
        xdg = os.environ.get("XDG_DATA_HOME")
        base = Path(xdg) if xdg else Path.home() / ".local" / "share"
        return base / "horus-os"

    @classmethod
    def with_defaults(cls, data_dir: Path | None = None) -> Config:
        """Build a Config with default paths under `data_dir`."""
        resolved = (data_dir or cls.default_data_dir()).expanduser()
        return cls(
            data_dir=resolved,
            db_path=resolved / DEFAULT_DB_FILENAME,
            notes_dir=resolved / DEFAULT_NOTES_SUBDIR,
        )

    @classmethod
    def load(cls, data_dir: Path | None = None) -> Config:
        """Load config from `data_dir/config.toml` or return defaults.

        Phase 34: HORUS_OS_PRICING_PATH env var, when set, overrides any
        [pricing] table value in the TOML file. The env var wins.
        """
        base = cls.with_defaults(data_dir)
        config_path = base.data_dir / CONFIG_FILENAME
        if config_path.exists():
            try:
                with config_path.open("rb") as fh:
                    data = tomllib.load(fh)
                base = _apply_toml(base, data)
            except (OSError, tomllib.TOMLDecodeError):
                pass
        env_pricing = os.environ.get("HORUS_OS_PRICING_PATH")
        if env_pricing:
            base = replace(base, pricing_path=Path(env_pricing).expanduser())
        return base

    def save(self) -> None:
        """Persist this config to `data_dir/config.toml` atomically."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        config_path = self.data_dir / CONFIG_FILENAME
        text = _dump_toml(self)
        fd, tmp_name = tempfile.mkstemp(
            prefix=".config.toml.", suffix=".tmp", dir=str(self.data_dir)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(text)
            os.replace(tmp_name, config_path)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass
            raise


def _apply_toml(base: Config, data: dict[str, Any]) -> Config:
    providers = data.get("providers", {}) or {}
    storage = data.get("storage", {}) or {}
    notes = data.get("notes", {}) or {}
    pricing = data.get("pricing", {}) or {}
    local = data.get("local", {}) or {}
    memory = data.get("memory", {}) or {}
    tools = data.get("tools", {}) or {}
    web_search = tools.get("web_search", {}) or {}
    research = data.get("research", {}) or {}
    overrides: dict[str, Any] = {}
    if "db_path" in storage:
        overrides["db_path"] = Path(storage["db_path"]).expanduser()
    if "notes_dir" in notes:
        overrides["notes_dir"] = Path(notes["notes_dir"]).expanduser()
    if "default" in providers:
        overrides["default_provider"] = str(providers["default"])
    if "anthropic_model" in providers:
        overrides["anthropic_model"] = str(providers["anthropic_model"])
    if "gemini_model" in providers:
        overrides["gemini_model"] = str(providers["gemini_model"])
    if "path" in pricing:
        overrides["pricing_path"] = Path(pricing["path"]).expanduser()
    if "base_url" in local:
        overrides["local_base_url"] = str(local["base_url"])
    if "model" in local:
        overrides["local_model"] = str(local["model"])
    if "context_window" in local:
        overrides["local_context_window"] = int(local["context_window"])
    if "vector_enabled" in memory:
        overrides["vector_memory_enabled"] = bool(memory["vector_enabled"])
    if "embedding_model" in memory:
        overrides["embedding_model"] = str(memory["embedding_model"])
    if "models_dir" in memory:
        overrides["models_dir"] = Path(memory["models_dir"]).expanduser()
    if "provider" in web_search:
        overrides["web_search_provider"] = str(web_search["provider"])
    if "base_url" in web_search:
        overrides["web_search_base_url"] = str(web_search["base_url"])
    if "max_sources" in research:
        overrides["research_max_sources"] = int(research["max_sources"])
    if "max_iterations" in research:
        overrides["research_max_iterations"] = int(research["max_iterations"])
    return replace(base, **overrides)


def _dump_toml(config: Config) -> str:
    base = (
        "# horus-os configuration\n"
        "# Edit by hand or via `horus-os init --force`.\n"
        "\n"
        "[providers]\n"
        f'default = "{config.default_provider}"\n'
        f'anthropic_model = "{config.anthropic_model}"\n'
        f'gemini_model = "{config.gemini_model}"\n'
        "\n"
        "[storage]\n"
        f'db_path = "{config.db_path.as_posix()}"\n'
        "\n"
        "[notes]\n"
        f'notes_dir = "{config.notes_dir.as_posix()}"\n'
    )
    if config.pricing_path is not None:
        base += f'\n[pricing]\npath = "{config.pricing_path.as_posix()}"\n'
    # Phase 69: emit [local] only when the user diverged from the bundled
    # defaults (a model was set or the base_url was changed), mirroring the
    # conditional [pricing] emission above.
    if config.local_model or config.local_base_url != DEFAULT_LOCAL_BASE_URL:
        base += (
            "\n[local]\n"
            f'base_url = "{config.local_base_url}"\n'
            f'model = "{config.local_model}"\n'
            f"context_window = {config.local_context_window}\n"
        )
    # Phase 70: emit [memory] only when the user opted vector memory in or
    # diverged from the bundled embedding defaults, mirroring the conditional
    # [pricing] and [local] emissions above. The default model is
    # BAAI/bge-small-en-v1.5; an unset models_dir resolves lazily.
    default_model = Config.__dataclass_fields__["embedding_model"].default
    if (
        config.vector_memory_enabled
        or config.embedding_model != default_model
        or config.models_dir is not None
    ):
        base += (
            "\n[memory]\n"
            f"vector_enabled = {str(config.vector_memory_enabled).lower()}\n"
            f'embedding_model = "{config.embedding_model}"\n'
        )
        if config.models_dir is not None:
            base += f'models_dir = "{config.models_dir.as_posix()}"\n'
    # Phase 72 (WEB-01): emit [tools.web_search] only when a provider is set,
    # mirroring the conditional [pricing]/[local]/[memory] emissions above. The
    # provider API key is intentionally NOT written here; it is supplied via the
    # HORUS_OS_WEB_SEARCH_KEY env var so no secret lands in config.toml.
    if config.web_search_provider:
        base += f'\n[tools.web_search]\nprovider = "{config.web_search_provider}"\n'
        if config.web_search_base_url:
            base += f'base_url = "{config.web_search_base_url}"\n'
    # Phase 73 (RESEARCH-04): emit [research] only when a budget cap diverges
    # from the bundled defaults, mirroring the conditional [pricing]/[local]/
    # [memory] emissions above. Both keys are ints with no env-var override.
    default_max_sources = Config.__dataclass_fields__["research_max_sources"].default
    default_max_iterations = Config.__dataclass_fields__["research_max_iterations"].default
    if (
        config.research_max_sources != default_max_sources
        or config.research_max_iterations != default_max_iterations
    ):
        base += (
            "\n[research]\n"
            f"max_sources = {config.research_max_sources}\n"
            f"max_iterations = {config.research_max_iterations}\n"
        )
    return base
