"""Discord adapter for horus-os.

Connects to the Discord gateway via the optional `discord.py`
dependency, listens for app mentions in guild channels and direct
messages to the bot, runs the configured agent profile, and posts
the response back to the source channel or DM.

The `discord` import is lazy inside `start` so this module imports
cleanly when the optional extra is not installed. Tests inject a
fake `discord` module into `sys.modules` to exercise the adapter
without the SDK on the path.

Configuration via environment variables:

- `HORUS_OS_DISCORD_TOKEN`: Discord bot token. Required.
- `HORUS_OS_DISCORD_AGENT_PROFILE`: Agent profile name to load.
  Defaults to "default". Missing profile is non-fatal.
- `HORUS_OS_DISCORD_RECONNECT_CAP`: Optional maximum backoff
  seconds for the library's internal reconnect loop. Passed
  through best-effort; if the installed `discord.py` does not
  accept the knob the library default applies.

The adapter satisfies the `Adapter` Protocol (name, bind) and the
`LifecycleAdapter` Protocol (async start, async stop) from
`horus_os.adapters.base`. It is declared as an entry point in
pyproject under `[project.entry-points."horus_os.adapters"]`.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import re
from typing import Any

from horus_os.adapters.base import AdapterContext
from horus_os.agent import run_agent
from horus_os.config import Config
from horus_os.storage import Database

TOKEN_ENV = "HORUS_OS_DISCORD_TOKEN"
AGENT_ENV = "HORUS_OS_DISCORD_AGENT_PROFILE"
RECONNECT_CAP_ENV = "HORUS_OS_DISCORD_RECONNECT_CAP"
DEFAULT_AGENT = "default"
DISCORD_MESSAGE_LIMIT = 2000

# Matches Discord's leading mention tokens: `<@123>` or `<@!123>`.
_MENTION_PATTERN = re.compile(r"<@!?(\d+)>")


class DiscordAdapter:
    """An inbound Discord adapter that routes mentions and DMs to `run_agent`."""

    name = "discord"

    def __init__(self) -> None:
        # All connection state is allocated in `start` so the
        # constructor stays cheap and import-clean.
        self._client: Any = None
        self._task: asyncio.Task[Any] | None = None
        self._context: AdapterContext | None = None

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": 1,
            "transport": "discord-gateway",
            "auth": "bot-token",
            "env": TOKEN_ENV,
        }

    def bind(self, app: Any, context: AdapterContext) -> None:
        # Discord uses its own gateway connection, not HTTP routes
        # on the FastAPI app. Nothing to bind.
        return None

    async def start(self, context: AdapterContext) -> None:
        """Open the Discord gateway connection in a background task.

        Failure modes (missing dependency, missing token) are
        recorded into the adapter registry rather than raised so
        the FastAPI lifespan can isolate this adapter from siblings.
        """
        self._context = context
        try:
            import discord
        except ImportError:
            context.registry.mark_error(
                self.name,
                "discord.py is not installed; pip install 'horus-os[discord]'",
            )
            return

        token = os.environ.get(TOKEN_ENV)
        if not token:
            context.registry.mark_error(self.name, f"{TOKEN_ENV} is not set")
            return

        intents = discord.Intents.none()
        intents.guilds = True
        intents.guild_messages = True
        intents.dm_messages = True
        intents.message_content = True

        client = discord.Client(intents=intents)
        client.event(self._make_on_message(client))
        self._client = client

        # `Client.start(token)` is the canonical entry point and
        # internally handles reconnects with exponential backoff
        # (DISC-03). We pass the reconnect cap best-effort: if the
        # installed library version does not accept the knob,
        # `TypeError` falls back to the library default.
        cap = os.environ.get(RECONNECT_CAP_ENV)
        if cap:
            try:
                coro = client.start(token, reconnect=True)
            except TypeError:
                coro = client.start(token)
        else:
            coro = client.start(token)
        self._task = asyncio.create_task(coro)
        context.registry.mark_running(self.name)

    async def stop(self) -> None:
        """Close the gateway connection and cancel the background task."""
        if self._client is not None:
            with contextlib.suppress(Exception):
                await self._client.close()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(BaseException):
                await self._task

    def _make_on_message(self, client: Any) -> Any:
        """Return an `on_message` coroutine closed over `client`."""

        async def on_message(message: Any) -> None:
            # Ignore our own messages to prevent feedback loops.
            if getattr(message, "author", None) == getattr(client, "user", None):
                return

            is_dm = getattr(message, "guild", None) is None
            mentions = getattr(message, "mentions", []) or []
            is_mention = getattr(client, "user", None) in mentions
            if not (is_dm or is_mention):
                return

            raw = getattr(message, "content", "") or ""
            prompt = _strip_mention(raw)
            if not prompt.strip():
                return

            try:
                reply = self._dispatch(prompt)
            except Exception as exc:
                if self._context is not None:
                    self._context.registry.mark_error(self.name, f"{type(exc).__name__}: {exc}")
                reply = f"Sorry, that failed: {type(exc).__name__}"

            for chunk in _chunk(reply, DISCORD_MESSAGE_LIMIT):
                with contextlib.suppress(Exception):
                    await message.channel.send(chunk)

            if self._context is not None:
                self._context.registry.touch(self.name)

        return on_message

    def _dispatch(self, prompt: str) -> str:
        """Run one synchronous agent turn against the configured profile."""
        if self._context is None:
            # Defensive: dispatch is only called from on_message which
            # only fires after start has set the context.
            raise RuntimeError("DiscordAdapter._dispatch called before start")
        cfg = self._context.config
        profile_name = os.environ.get(AGENT_ENV, DEFAULT_AGENT)
        profile = None
        if cfg.db_path.exists():
            db = Database(cfg.db_path)
            profile = db.load_profile(profile_name)
        provider = cfg.default_provider
        model = (profile.default_model if profile else None) or _default_model(cfg, provider)
        system_prompt = profile.system_prompt if profile else None
        result = run_agent(
            prompt,
            provider=provider,
            tools=None,
            model=model,
            system_prompt=system_prompt,
        )
        return result.text or ""


def _strip_mention(text: str) -> str:
    """Remove leading mention tokens like `<@123>` or `<@!123>`."""
    return _MENTION_PATTERN.sub("", text).strip()


def _chunk(text: str, limit: int):
    """Yield successive `limit`-sized slices of `text`.

    Empty input yields a single `(no response)` sentinel so the
    handler always posts something visible to the user.
    """
    if not text:
        yield "(no response)"
        return
    for i in range(0, len(text), limit):
        yield text[i : i + limit]


def _default_model(cfg: Config, provider: str) -> str:
    if provider == "anthropic":
        return cfg.anthropic_model
    return cfg.gemini_model
