"""Discord adapter example: fake mention dispatched through `on_message`.

This example shows how to:

1. Stub the optional `discord.py` SDK via `sys.modules` injection so
   `DiscordAdapter` runs without the package installed.
2. Build an `AdapterContext` plus an `AdapterRegistry` and `start` the
   adapter so the gateway client is wired and `on_message` is captured.
3. Fabricate a Discord message object and dispatch it through the
   captured `on_message` coroutine the way the real gateway would.
4. Inspect the captured `channel.send` calls and the registry entry so
   the dispatch and the lifecycle accounting are both visible.

The script runs end to end with no Discord token, no `discord.py`
install, and no network. `run_agent` is monkeypatched at the adapter
module level to return a canned `AgentResult`.

For a live run set:

    HORUS_OS_DISCORD_TOKEN=your-bot-token-here
    HORUS_OS_DISCORD_AGENT_PROFILE=default   # optional, defaults to "default"

then `pip install 'horus-os[discord]'` and `horus-os serve`. The
adapter loads automatically through its entry point. See
`docs/adapters/DISCORD.md` for the full setup walkthrough.

Run it:

    python examples/discord_adapter.py
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
import types
from pathlib import Path
from typing import Any

from horus_os import (
    AdapterContext,
    AdapterRegistry,
    Config,
    Database,
)
from horus_os.adapters import DiscordAdapter
from horus_os.adapters import discord_adapter as discord_adapter_module
from horus_os.types import AgentResult


def _install_fake_discord() -> types.SimpleNamespace:
    """Inject a fake `discord` module into sys.modules.

    Returns a handle exposing the captured `on_message` coroutine and
    the recorded `Client.start` / `Client.close` calls.
    """
    fake = types.ModuleType("discord")

    class _Intents:
        def __init__(self) -> None:
            self.guilds = False
            self.guild_messages = False
            self.dm_messages = False
            self.message_content = False

        @classmethod
        def none(cls) -> _Intents:
            return cls()

    fake.Intents = _Intents

    handles = types.SimpleNamespace(
        client=None,
        on_message=None,
        start_calls=[],
        close_calls=0,
    )

    class _Client:
        def __init__(self, intents: Any = None) -> None:
            self.intents = intents
            self.user = object()
            handles.client = self

        def event(self, coro: Any) -> Any:
            handles.on_message = coro
            return coro

        async def start(self, token: str, **kwargs: Any) -> None:
            handles.start_calls.append((token, kwargs))
            # Block forever; the example cancels via `adapter.stop()`.
            await asyncio.Event().wait()

        async def close(self) -> None:
            handles.close_calls += 1

    fake.Client = _Client
    sys.modules["discord"] = fake
    return handles


def _stub_run_agent() -> None:
    """Replace `run_agent` with an offline fake returning a canned reply."""

    def fake_run_agent(prompt: str, **kwargs: Any) -> AgentResult:
        return AgentResult(
            text=f"[stub agent] received: {prompt!r}",
            provider="stub",
            model="stub-model",
            usage={"input_tokens": 0, "output_tokens": 0},
        )

    discord_adapter_module.run_agent = fake_run_agent


class _FakeChannel:
    """Stand-in for a `discord.TextChannel` that records sent messages."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, content: str) -> None:
        self.sent.append(content)


class _FakeMessage:
    """Stand-in for `discord.Message`."""

    def __init__(
        self,
        *,
        content: str,
        author: Any,
        channel: _FakeChannel,
        guild: Any | None = None,
        mentions: list[Any] | None = None,
    ) -> None:
        self.content = content
        self.author = author
        self.channel = channel
        self.guild = guild
        self.mentions = mentions or []


async def _amain() -> None:
    handles = _install_fake_discord()
    _stub_run_agent()

    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        config = Config.with_defaults(data_dir)
        config.save()
        Database(config.db_path).init()

        registry = AdapterRegistry()
        registry.register("discord")
        ctx = AdapterContext(config=config, data_dir=data_dir, registry=registry)

        # Set the token; this is what `DiscordAdapter.start` checks for.
        # The fake `discord.Client` does not actually authenticate.
        import os

        os.environ["HORUS_OS_DISCORD_TOKEN"] = "your-bot-token-here"

        adapter = DiscordAdapter()
        await adapter.start(ctx)
        # Yield once so the background `_Client.start` coroutine
        # actually begins executing and records its token call.
        await asyncio.sleep(0)
        try:
            entry = registry.get("discord")
            assert entry is not None
            print(f"Adapter status after start: {entry.status}")
            print(f"Captured gateway start call: token={handles.start_calls[0][0]!r}")

            # Fabricate a guild mention message and dispatch it.
            channel = _FakeChannel()
            client = handles.client
            message = _FakeMessage(
                content="<@123> what is the weather today?",
                author=object(),
                channel=channel,
                guild=object(),
                mentions=[client.user],
            )
            assert handles.on_message is not None
            await handles.on_message(message)

            print()
            print("Channel sends after dispatch:")
            for chunk in channel.sent:
                print(f"  {chunk!r}")
            print()
            entry = registry.get("discord")
            print(
                f"Registry entry: status={entry.status} last_activity_at={entry.last_activity_at}"
            )
        finally:
            await adapter.stop()
            print(f"Close calls on shutdown: {handles.close_calls}")


def main() -> None:
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
