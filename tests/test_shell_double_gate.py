"""TEST-36: the SHELL-01 default-deny double gate.

The shell_exec tool must be ABSENT from the registry an agent can reach unless
BOTH gates are open at once:

  (1) the runtime gate: the HORUS_OS_SHELL_ENABLED env var equals the exact
      string "true", AND
  (2) the explicit-grant gate: the invoking agent profile's allowed_tools names
      "shell_exec".

Remove either gate and the tool disappears. A fresh install has neither, so a
default agent cannot reach the shell under any prompt (the BLOCKING SHELL-01
constraint). These tests exercise the real single chokepoint
(register_shell_if_gated) and both registry builders (api.py and run_cmd.py) so
a regression in either site fails here.

The test function names map one-to-one to the five gate states so a grep maps a
failure straight to the offending state.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from horus_os.cli.run_cmd import _build_default_registry as build_cli_registry
from horus_os.config import Config
from horus_os.memory import NotesStore
from horus_os.server.api import _build_default_registry as build_api_registry
from horus_os.storage import Database
from horus_os.tools.registry import ToolRegistry
from horus_os.tools.shell import SHELL_ENABLED_ENV, register_shell_if_gated

ENV = SHELL_ENABLED_ENV


def _fresh_config_and_db(tmp_path: Path) -> tuple[Config, Database]:
    """A freshly initialised installation under tmp_path (mirrors test_storage)."""
    cfg = Config.with_defaults(tmp_path)
    cfg.notes_dir.mkdir(parents=True, exist_ok=True)
    db = Database(cfg.db_path)
    db.init()
    return cfg, db


def _gate(
    cfg: Config,
    db: Database,
    *,
    allowed_tools: list[str] | None,
) -> ToolRegistry:
    """Drive the single chokepoint and return the resolved registry."""
    registry = ToolRegistry()
    register_shell_if_gated(registry, cfg, db, profile_allowed_tools=allowed_tools)
    return registry


# --- the five gate states (chokepoint) --------------------------------------


def test_state1_no_env_no_grant_absent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # env unset + allowed_tools None -> absent.
    monkeypatch.delenv(ENV, raising=False)
    cfg, db = _fresh_config_and_db(tmp_path)
    registry = _gate(cfg, db, allowed_tools=None)
    assert "shell_exec" not in registry


def test_state2_no_env_with_grant_absent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # env unset + allowed_tools names shell_exec -> still absent (env gate shut).
    monkeypatch.delenv(ENV, raising=False)
    cfg, db = _fresh_config_and_db(tmp_path)
    registry = _gate(cfg, db, allowed_tools=["shell_exec"])
    assert "shell_exec" not in registry


def test_state3_env_only_unrestricted_profile_absent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # env "true" + allowed_tools None -> absent (SE-1 unrestricted-profile guard:
    # a None profile reaches every other tool but must NOT silently gain shell).
    monkeypatch.setenv(ENV, "true")
    cfg, db = _fresh_config_and_db(tmp_path)
    registry = _gate(cfg, db, allowed_tools=None)
    assert "shell_exec" not in registry


def test_state4_both_gates_open_present_and_invokable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # env "true" + allowed_tools names shell_exec -> present AND invokable.
    monkeypatch.setenv(ENV, "true")
    cfg, db = _fresh_config_and_db(tmp_path)
    registry = _gate(cfg, db, allowed_tools=["shell_exec"])
    assert "shell_exec" in registry
    tool = registry.get("shell_exec")
    assert tool is not None
    assert tool.handler is not None
    # Invokable: a metacharacter arg is rejected by the handler and one audit
    # row is written, proving the registered tool is the real gated factory.
    result = tool.handler(command="echo", args=[";rm -rf /"])
    assert result["exit_code"] is None
    assert result.get("error")
    assert len(db.list_shell_invocations()) == 1


def test_state5_env_with_other_grant_absent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # env "true" + allowed_tools names a different tool -> absent.
    monkeypatch.setenv(ENV, "true")
    cfg, db = _fresh_config_and_db(tmp_path)
    registry = _gate(cfg, db, allowed_tools=["read_file"])
    assert "shell_exec" not in registry


# --- the env value must be the exact string "true" --------------------------


def test_env_non_true_value_does_not_open_the_gate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # A truthy-looking but non-"true" value (e.g. "1", "True", "yes") is NOT the
    # open state; the gate uses an exact string compare.
    cfg, db = _fresh_config_and_db(tmp_path)
    for value in ("1", "True", "yes", "TRUE", ""):
        monkeypatch.setenv(ENV, value)
        registry = _gate(cfg, db, allowed_tools=["shell_exec"])
        assert "shell_exec" not in registry, f"value {value!r} wrongly opened the gate"


# --- fresh-init proof through the real api.py registry builder --------------


def test_fresh_init_default_registry_has_no_shell(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # The TEST-36 success criterion: build the default registry for a freshly
    # initialised installation with no env var and assert no agent profile can
    # resolve shell_exec. This drives the real api.py _build_default_registry.
    monkeypatch.delenv(ENV, raising=False)
    cfg, db = _fresh_config_and_db(tmp_path)
    notes = NotesStore(cfg.notes_dir)
    # The default /api/chat path passes no profile, so allowed_tools is None.
    registry = build_api_registry(cfg, notes, db=db)
    assert "shell_exec" not in registry


def test_api_builder_registers_shell_only_when_both_gates_open(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # The same builder with the env gate open AND a profile granting shell_exec
    # registers the tool; remove either gate and it is gone.
    cfg, db = _fresh_config_and_db(tmp_path)
    notes = NotesStore(cfg.notes_dir)

    monkeypatch.setenv(ENV, "true")
    granted = build_api_registry(cfg, notes, db=db, agent_allowed_tools=["shell_exec"])
    assert "shell_exec" in granted

    monkeypatch.delenv(ENV, raising=False)
    no_env = build_api_registry(cfg, notes, db=db, agent_allowed_tools=["shell_exec"])
    assert "shell_exec" not in no_env

    monkeypatch.setenv(ENV, "true")
    no_grant = build_api_registry(cfg, notes, db=db, agent_allowed_tools=None)
    assert "shell_exec" not in no_grant


def test_cli_builder_matches_the_gate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # The CLI run path uses the same chokepoint, so its registry obeys the same
    # double gate. This proves the second build site is not a bypass.
    cfg, db = _fresh_config_and_db(tmp_path)
    notes = NotesStore(cfg.notes_dir)

    monkeypatch.delenv(ENV, raising=False)
    absent = build_cli_registry(cfg, notes, db=db, agent_allowed_tools=["shell_exec"])
    assert "shell_exec" not in absent

    monkeypatch.setenv(ENV, "true")
    present = build_cli_registry(cfg, notes, db=db, agent_allowed_tools=["shell_exec"])
    assert "shell_exec" in present

    unrestricted = build_cli_registry(cfg, notes, db=db, agent_allowed_tools=None)
    assert "shell_exec" not in unrestricted
