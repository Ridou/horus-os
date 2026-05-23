"""Interactive setup wizard for `horus-os init --interactive`.

Walks a new user through API key onboarding for the two supported
providers, validates keys with a live 1-token ping (cheap and gives
immediate feedback), writes validated keys to `<data_dir>/.env`, and
records progress to `<data_dir>/.horus-init-state.json` so an
interrupted run can resume.

The flow is structured so tests can drive it deterministically:
prompts read from an injected stdin stream, output goes to an injected
stdout stream, and the validators are passed in as a dict mapping
provider name to a callable. Production code uses
`DEFAULT_VALIDATORS` which hit the real SDKs.
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any, TextIO

from horus_os.config import Config

ANTHROPIC_KEYS_URL = "https://console.anthropic.com/settings/keys"
GEMINI_KEYS_URL = "https://aistudio.google.com/apikey"
STATE_FILENAME = ".horus-init-state.json"
ENV_FILENAME = ".env"


def _validate_anthropic_key(key: str) -> tuple[bool, str | None]:
    """Make a minimal Anthropic call to confirm the key works."""
    try:
        from anthropic import Anthropic, AuthenticationError
    except ImportError:
        return (
            False,
            "anthropic SDK not installed; install with `pip install 'horus-os[anthropic]'`",
        )
    client = Anthropic(api_key=key)
    try:
        client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1,
            messages=[{"role": "user", "content": "ping"}],
        )
    except AuthenticationError:
        return False, "the Anthropic API rejected this key (authentication failed)"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
    return True, None


def _validate_gemini_key(key: str) -> tuple[bool, str | None]:
    """Make a minimal Gemini call to confirm the key works."""
    try:
        from google import genai
    except ImportError:
        return (
            False,
            "google-genai SDK not installed; install with `pip install 'horus-os[gemini]'`",
        )
    client = genai.Client(api_key=key)
    try:
        client.models.generate_content(model="gemini-2.5-flash", contents="ping")
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
    return True, None


DEFAULT_VALIDATORS: dict[str, Callable[[str], tuple[bool, str | None]]] = {
    "anthropic": _validate_anthropic_key,
    "gemini": _validate_gemini_key,
}


def run_wizard(
    config: Config,
    *,
    stdin: TextIO,
    stdout: TextIO,
    validators: dict[str, Callable[[str], tuple[bool, str | None]]] | None = None,
) -> int:
    """Drive the interactive setup wizard. Returns exit code."""
    validators = validators or DEFAULT_VALIDATORS
    state = _load_state(config.data_dir)
    env: dict[str, str] = _load_env(config.data_dir)

    stdout.write("\nWelcome to horus-os.\n")
    stdout.write(
        "This wizard collects API keys for the two supported providers, validates\n"
        "them against the live APIs (1 token each), and saves the working keys to\n"
        f"{config.data_dir / ENV_FILENAME}.\n\n"
        "Leave any prompt blank to skip that provider.\n\n"
    )

    validated: dict[str, bool] = {}

    if state.get("anthropic_done") and "ANTHROPIC_API_KEY" in env:
        stdout.write("- Anthropic: already configured, skipping.\n")
        validated["anthropic"] = True
    else:
        ok = _prompt_and_validate(
            provider="anthropic",
            env_var="ANTHROPIC_API_KEY",
            url=ANTHROPIC_KEYS_URL,
            description="Anthropic (Claude)",
            stdin=stdin,
            stdout=stdout,
            validators=validators,
            env=env,
        )
        validated["anthropic"] = ok
        state["anthropic_done"] = True
        _save_state(config.data_dir, state)
        if ok:
            _write_env(config.data_dir, env)

    if state.get("gemini_done") and "GEMINI_API_KEY" in env:
        stdout.write("- Gemini: already configured, skipping.\n")
        validated["gemini"] = True
    else:
        ok = _prompt_and_validate(
            provider="gemini",
            env_var="GEMINI_API_KEY",
            url=GEMINI_KEYS_URL,
            description="Google Gemini",
            stdin=stdin,
            stdout=stdout,
            validators=validators,
            env=env,
        )
        validated["gemini"] = ok
        state["gemini_done"] = True
        _save_state(config.data_dir, state)
        if ok:
            _write_env(config.data_dir, env)

    default_provider = _decide_default_provider(validated, stdin, stdout)
    if default_provider != config.default_provider:
        config.default_provider = default_provider
        config.save()

    stdout.write("\nSetup complete.\n")
    if any(validated.values()):
        stdout.write(
            f"  Keys saved to: {config.data_dir / ENV_FILENAME}\n"
            "  Source it in your shell or set them in your environment, then run:\n"
            '    horus-os run "Hello, what tools do you have?"\n'
        )
    else:
        stdout.write(
            "  No keys were validated. You can rerun `horus-os init --interactive`\n"
            "  any time to try again.\n"
        )
    return 0


def _prompt_and_validate(
    *,
    provider: str,
    env_var: str,
    url: str,
    description: str,
    stdin: TextIO,
    stdout: TextIO,
    validators: dict[str, Callable[[str], tuple[bool, str | None]]],
    env: dict[str, str],
) -> bool:
    stdout.write(f"\n{description}\n")
    stdout.write(f"  Get a key: {url}\n")
    stdout.write(f"  Paste your {env_var} (or press Enter to skip): ")
    stdout.flush()
    line = stdin.readline()
    if not line:
        stdout.write("\n  Skipped (no input).\n")
        return False
    key = line.strip()
    if not key:
        stdout.write("  Skipped.\n")
        return False
    stdout.write("  Validating...\n")
    validator = validators.get(provider)
    if validator is None:
        stdout.write(f"  No validator for {provider!r}, skipping.\n")
        return False
    ok, error = validator(key)
    if not ok:
        stdout.write(f"  Validation failed: {error}\n")
        return False
    stdout.write("  Validated.\n")
    env[env_var] = key
    return True


def _decide_default_provider(validated: dict[str, bool], stdin: TextIO, stdout: TextIO) -> str:
    ok_providers = [p for p, v in validated.items() if v]
    if not ok_providers:
        stdout.write(
            "\nNo provider was validated. The default stays `anthropic`; rerun the\n"
            "wizard once you have a working key.\n"
        )
        return "anthropic"
    if len(ok_providers) == 1:
        chosen = ok_providers[0]
        stdout.write(f"\nDefault provider: {chosen} (only one validated).\n")
        return chosen
    stdout.write(
        "\nBoth providers are working. Which one should be the default?\n"
        "  [a] anthropic  [g] gemini  (default: anthropic): "
    )
    stdout.flush()
    line = stdin.readline()
    choice = (line or "").strip().lower()
    if choice in ("g", "gemini"):
        return "gemini"
    return "anthropic"


def _load_state(data_dir: Path) -> dict[str, Any]:
    state_path = data_dir / STATE_FILENAME
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(data_dir: Path, state: dict[str, Any]) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    state_path = data_dir / STATE_FILENAME
    _atomic_write(state_path, json.dumps(state, indent=2) + "\n")


def _load_env(data_dir: Path) -> dict[str, str]:
    env_path = data_dir / ENV_FILENAME
    if not env_path.exists():
        return {}
    result: dict[str, str] = {}
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        result[key.strip()] = value.strip()
    return result


def _write_env(data_dir: Path, env: dict[str, str]) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    env_path = data_dir / ENV_FILENAME
    lines = [f"{k}={v}" for k, v in env.items()]
    _atomic_write(env_path, "\n".join(lines) + "\n")
    if os.name == "posix":
        try:
            os.chmod(env_path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix="." + path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise
