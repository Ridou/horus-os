"""Tests for the local-provider step of the setup wizard (LLM-02, LP-3, LP-4).

The wizard is driven deterministically: stdin/stdout are injected StringIO
streams, the cloud validators are stubbed so only the local step does real
work, and the local discovery + smoke-test callables are injected fakes so no
live Ollama / OpenAI-compatible server is ever contacted.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

from horus_os.cli.wizard import STATE_FILENAME, run_wizard
from horus_os.config import Config


def _config(tmp_path: Path) -> Config:
    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    return cfg


def _skip_cloud(_key: str) -> tuple[bool, str | None]:
    # A cloud validator that is never actually invoked because the cloud
    # prompts are answered with a blank line (skip).
    return False, "not used"


_CLOUD_VALIDATORS = {"anthropic": _skip_cloud, "gemini": _skip_cloud}


def test_local_discovery_and_smoke_pass_saves_model(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    discovered = ["llama3.1:8b", "qwen2.5:7b"]

    def discover(_base_url: str) -> list[str]:
        return discovered

    def smoke(_base_url: str, _model: str) -> tuple[bool, str | None]:
        return True, None

    # Cloud steps skipped (blank lines), then pick model by index 1.
    stdin = io.StringIO("\n\n1\n")
    stdout = io.StringIO()
    code = run_wizard(
        cfg,
        stdin=stdin,
        stdout=stdout,
        validators=_CLOUD_VALIDATORS,
        discover_models=discover,
        smoke_test=smoke,
    )
    assert code == 0
    reloaded = Config.load(tmp_path)
    assert reloaded.local_model == "qwen2.5:7b"
    assert reloaded.local_context_window == 4096
    # No cloud key was provided, so the local provider becomes the default.
    assert reloaded.default_provider == "local"
    out = stdout.getvalue()
    assert "llama3.1:8b" in out
    assert "Smoke test passed" in out


def test_local_default_choice_picks_first_model(tmp_path: Path) -> None:
    cfg = _config(tmp_path)

    def discover(_base_url: str) -> list[str]:
        return ["phi3:mini", "llama3.1:8b"]

    def smoke(_base_url: str, _model: str) -> tuple[bool, str | None]:
        return True, None

    # Blank model choice defaults to the first (smallest listed) model.
    stdin = io.StringIO("\n\n\n")
    stdout = io.StringIO()
    run_wizard(
        cfg,
        stdin=stdin,
        stdout=stdout,
        validators=_CLOUD_VALIDATORS,
        discover_models=discover,
        smoke_test=smoke,
    )
    reloaded = Config.load(tmp_path)
    assert reloaded.local_model == "phi3:mini"


def test_local_unreachable_endpoint_warns_and_skips(tmp_path: Path) -> None:
    cfg = _config(tmp_path)

    def discover(_base_url: str) -> list[str]:
        return []

    def smoke(_base_url: str, _model: str) -> tuple[bool, str | None]:
        raise AssertionError("smoke_test must not run when discovery is empty")

    stdin = io.StringIO("\n\n")
    stdout = io.StringIO()
    code = run_wizard(
        cfg,
        stdin=stdin,
        stdout=stdout,
        validators=_CLOUD_VALIDATORS,
        discover_models=discover,
        smoke_test=smoke,
    )
    assert code == 0
    reloaded = Config.load(tmp_path)
    assert reloaded.local_model == ""
    assert reloaded.default_provider == "anthropic"
    out = stdout.getvalue()
    assert "not reachable" in out
    # The wizard never suggests a non-loopback bind address (LP-4).
    assert "0.0.0.0" not in out


def test_local_discovery_raises_is_treated_as_unreachable(tmp_path: Path) -> None:
    cfg = _config(tmp_path)

    def discover(_base_url: str) -> list[str]:
        raise ConnectionError("connection refused")

    def smoke(_base_url: str, _model: str) -> tuple[bool, str | None]:
        raise AssertionError("smoke_test must not run when discovery raises")

    stdin = io.StringIO("\n\n")
    stdout = io.StringIO()
    code = run_wizard(
        cfg,
        stdin=stdin,
        stdout=stdout,
        validators=_CLOUD_VALIDATORS,
        discover_models=discover,
        smoke_test=smoke,
    )
    assert code == 0
    assert Config.load(tmp_path).local_model == ""
    assert "not reachable" in stdout.getvalue()


def test_local_smoke_test_failure_does_not_persist_model(tmp_path: Path) -> None:
    cfg = _config(tmp_path)

    def discover(_base_url: str) -> list[str]:
        return ["llama3.1:8b"]

    def smoke(_base_url: str, _model: str) -> tuple[bool, str | None]:
        return False, "model not loaded"

    stdin = io.StringIO("\n\n0\n")
    stdout = io.StringIO()
    code = run_wizard(
        cfg,
        stdin=stdin,
        stdout=stdout,
        validators=_CLOUD_VALIDATORS,
        discover_models=discover,
        smoke_test=smoke,
    )
    assert code == 0
    reloaded = Config.load(tmp_path)
    assert reloaded.local_model == ""
    out = stdout.getvalue()
    assert "Smoke test failed" in out
    assert "model not loaded" in out


def test_local_done_state_recorded(tmp_path: Path) -> None:
    cfg = _config(tmp_path)

    def discover(_base_url: str) -> list[str]:
        return ["llama3.1:8b"]

    def smoke(_base_url: str, _model: str) -> tuple[bool, str | None]:
        return True, None

    stdin = io.StringIO("\n\n0\n")
    stdout = io.StringIO()
    run_wizard(
        cfg,
        stdin=stdin,
        stdout=stdout,
        validators=_CLOUD_VALIDATORS,
        discover_models=discover,
        smoke_test=smoke,
    )
    state = json.loads((tmp_path / STATE_FILENAME).read_text())
    assert state["local_done"] is True


def test_local_resume_skips_already_configured(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    cfg.local_model = "already:configured"
    cfg.save()
    (tmp_path / STATE_FILENAME).write_text(json.dumps({"local_done": True}))

    def discover(_base_url: str) -> list[str]:
        raise AssertionError("discovery must not re-run when local_done is set")

    def smoke(_base_url: str, _model: str) -> tuple[bool, str | None]:
        raise AssertionError("smoke_test must not re-run when local_done is set")

    stdin = io.StringIO("\n\n")
    stdout = io.StringIO()
    code = run_wizard(
        cfg,
        stdin=stdin,
        stdout=stdout,
        validators=_CLOUD_VALIDATORS,
        discover_models=discover,
        smoke_test=smoke,
    )
    assert code == 0
    assert "already configured, skipping" in stdout.getvalue()
