"""Tests for the Discord control bot extension.

All tests run with `discord.py` simulated via a fake module installed
into `sys.modules`. No live Discord connection is opened in any test.

`run_agent` is monkeypatched at the adapter module level so no
provider SDK is required and no network call happens.

Coverage: commands.Bot startup, guild-scoped slash sync, admin gate,
idempotent channel bootstrap (TEST-28), #horus thread dispatch,
status-card embeds, reaction feedback, graceful degradation.
"""

from __future__ import annotations

import asyncio
import sqlite3
import sys
import types
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from horus_os import Config, Database
from horus_os.adapters import (
    ADAPTER_STATUS_ERROR,
    ADAPTER_STATUS_RUNNING,
    AdapterContext,
    AdapterRegistry,
    DiscordAdapter,
)
from horus_os.adapters import discord_adapter as discord_adapter_module
from horus_os.types import AgentResult

# -- fixtures ------------------------------------------------------------------


def _make_context(tmp_path: Path) -> AdapterContext:
    """Build a registry + context with the adapter pre-registered."""
    cfg = Config.with_defaults(tmp_path)
    cfg.save()
    db = Database(cfg.db_path)
    db.init()
    reg = AdapterRegistry()
    reg.register("discord")
    return AdapterContext(config=cfg, data_dir=tmp_path, registry=reg)


def _install_fake_discord(
    monkeypatch: pytest.MonkeyPatch,
) -> types.SimpleNamespace:
    """Inject a fake `discord` module into sys.modules.

    The fake exposes all symbols the bot extension uses:
    - discord.ext.commands.Bot with .tree recording sync/clear_commands calls
    - discord.app_commands with command/guilds/check decorators
    - discord.Object for guild snowflake
    - discord.Embed with add_field
    - discord.RawReactionActionEvent
    - discord.Guild with text_channels/categories/create_text_channel/create_category
    - discord.Thread with send
    - discord.Message with create_thread
    - discord.Color with green/yellow/red/default
    - discord.Intents (same as v0.3 fake)
    - discord.Client (kept for v0.3 adapter back-compat)
    """
    fake = types.ModuleType("discord")

    # --- Intents (same as v0.3 fake) ---

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

    # --- Color ---

    class _Color:
        def __init__(self, name: str) -> None:
            self.name = name

        @classmethod
        def green(cls) -> _Color:
            return cls("green")

        @classmethod
        def yellow(cls) -> _Color:
            return cls("yellow")

        @classmethod
        def red(cls) -> _Color:
            return cls("red")

        @classmethod
        def default(cls) -> _Color:
            return cls("default")

    fake.Color = _Color

    # --- Embed ---

    class _Embed:
        def __init__(
            self,
            *,
            title: str = "",
            description: str = "",
            color: Any = None,
            timestamp: Any = None,
        ) -> None:
            self.title = title
            self.description = description
            self.color = color
            self.timestamp = timestamp
            self.fields: list[dict[str, Any]] = []

        def add_field(self, *, name: str, value: str, inline: bool = True) -> _Embed:
            self.fields.append({"name": name, "value": value, "inline": inline})
            return self

    fake.Embed = _Embed

    # --- Object (snowflake) ---

    class _Object:
        def __init__(self, *, id: int) -> None:
            self.id = id

    fake.Object = _Object

    # --- RawReactionActionEvent ---

    class _RawReactionActionEvent:
        def __init__(
            self,
            *,
            message_id: int = 0,
            channel_id: int = 0,
            user_id: int = 0,
            guild_id: int | None = None,
            emoji: Any = None,
        ) -> None:
            self.message_id = message_id
            self.channel_id = channel_id
            self.user_id = user_id
            self.guild_id = guild_id
            self.emoji = emoji

    fake.RawReactionActionEvent = _RawReactionActionEvent

    # --- Handles namespace for assertions ---

    handles = types.SimpleNamespace(
        # v0.3 back-compat
        client=None,
        on_message=None,
        start_calls=[],
        close_calls=0,
        intents_captured=None,
        # Bot-level handles
        bot=None,
        setup_hook_called=False,
        tree_clear_commands_calls=[],
        tree_sync_calls=[],
        tree_copy_global_calls=[],
        # Event handler references
        on_message_handler=None,
        on_raw_reaction_add_handler=None,
        # Admin predicate
        setup_command_predicate=None,
    )

    # --- CommandTree fake ---

    class _CommandTree:
        def __init__(self) -> None:
            pass

        def command(self, *, name: str = "", description: str = "") -> Any:
            """Decorator that registers a slash command."""

            def decorator(func: Any) -> Any:
                # Store the function directly on the tree so tests can invoke it
                setattr(self, f"_cmd_{name}", func)
                return func

            return decorator

        def copy_global_to(self, *, guild: Any = None) -> None:
            handles.tree_copy_global_calls.append(guild)

        def clear_commands(self, *, guild: Any = None) -> None:
            handles.tree_clear_commands_calls.append(guild)

        async def sync(self, *, guild: Any = None) -> list[Any]:
            handles.tree_sync_calls.append(guild)
            return []

        def on_error(self, func: Any) -> Any:
            return func

    # --- app_commands fake ---

    fake_app_commands = types.ModuleType("discord.app_commands")

    class _FakeChecks:
        @staticmethod
        def has_role(item: Any) -> Any:
            def decorator(func: Any) -> Any:
                return func

            return decorator

    fake_app_commands.checks = _FakeChecks()

    def _check(predicate: Any) -> Any:
        """Capture the predicate for test assertions."""

        def decorator(func: Any) -> Any:
            # Store predicate on the function for test access
            func._admin_predicate = predicate
            handles.setup_command_predicate = predicate
            return func

        return decorator

    fake_app_commands.check = _check

    def _command_decorator(**kwargs: Any) -> Any:
        def decorator(func: Any) -> Any:
            return func

        return decorator

    fake_app_commands.command = _command_decorator

    def _guilds_decorator(*guild_ids: Any) -> Any:
        def decorator(func: Any) -> Any:
            return func

        return decorator

    fake_app_commands.guilds = _guilds_decorator

    fake.app_commands = fake_app_commands

    # --- Client (v0.3 back-compat: kept so existing tests that assert on
    #     self._client work if the adapter uses self._client for the legacy path) ---

    class _Client:
        def __init__(self, intents: Any = None) -> None:
            self.intents = intents
            handles.intents_captured = intents
            self.user = object()
            handles.client = self
            self._on_message = None

        def event(self, coro: Any) -> Any:
            handles.on_message = coro
            self._on_message = coro
            return coro

        async def start(self, token: str, **kwargs: Any) -> None:
            handles.start_calls.append((token, kwargs))
            await asyncio.Event().wait()

        async def close(self) -> None:
            handles.close_calls += 1

    fake.Client = _Client

    # --- Bot (commands.Bot) ---

    class _Bot:
        def __init__(self, command_prefix: str = "!", intents: Any = None) -> None:
            self.command_prefix = command_prefix
            self.intents = intents
            handles.intents_captured = intents
            self.user = object()
            self.tree = _CommandTree()
            handles.bot = self
            self._events: dict[str, Any] = {}

        def event(self, coro: Any) -> Any:
            name = coro.__name__
            self._events[name] = coro
            if name == "on_message":
                handles.on_message_handler = coro
            if name == "on_raw_reaction_add":
                handles.on_raw_reaction_add_handler = coro
            return coro

        async def start(self, token: str, **kwargs: Any) -> None:
            handles.start_calls.append((token, kwargs))
            # Mirror discord.py 2.x: login() calls self.setup_hook() (no
            # underscore). The adapter assigns bot.setup_hook = setup_hook as
            # an instance attribute, shadowing the class-level no-op. We check
            # for an instance override by testing whether the instance __dict__
            # has 'setup_hook' (the real discord.py does the same resolution
            # via normal Python attribute lookup and then calls it).
            hook = self.__dict__.get("setup_hook")
            if hook is not None:
                await hook()
                handles.setup_hook_called = True
            await asyncio.Event().wait()

        async def close(self) -> None:
            handles.close_calls += 1

    # --- ext and ext.commands submodule fakes ---

    fake_ext = types.ModuleType("discord.ext")
    fake_ext_commands = types.ModuleType("discord.ext.commands")
    fake_ext_commands.Bot = _Bot
    fake_ext.commands = fake_ext_commands
    fake.ext = fake_ext

    monkeypatch.setitem(sys.modules, "discord", fake)
    monkeypatch.setitem(sys.modules, "discord.ext", fake_ext)
    monkeypatch.setitem(sys.modules, "discord.ext.commands", fake_ext_commands)
    monkeypatch.setitem(sys.modules, "discord.app_commands", fake_app_commands)

    return handles


def _make_fake_guild(*, existing_channels: list[str] | None = None) -> Any:
    """Build a fake Guild with configurable existing text channels."""
    if existing_channels is None:
        existing_channels = []

    guild = MagicMock()
    guild.categories = []

    text_channels = []
    for ch_name in existing_channels:
        ch = MagicMock()
        ch.name = ch_name
        ch.delete = AsyncMock()
        text_channels.append(ch)

    guild.text_channels = text_channels
    guild.create_text_channel = AsyncMock(side_effect=lambda name, **kw: _make_channel(name))
    guild.create_category = AsyncMock(return_value=MagicMock(name="horus-os"))

    return guild


def _make_channel(name: str) -> Any:
    ch = MagicMock()
    ch.name = name
    ch.delete = AsyncMock()
    return ch


def _make_fake_message(*, content: str, channel_name: str = "horus") -> Any:
    """Build a fake Discord message for a named channel."""
    msg = MagicMock()
    msg.content = content
    msg.author = object()
    msg.channel = MagicMock()
    msg.channel.name = channel_name

    # Thread returned by create_thread
    fake_thread = MagicMock()
    thinking_msg = MagicMock()
    thinking_msg.edit = AsyncMock()
    fake_thread.send = AsyncMock(return_value=thinking_msg)
    msg.create_thread = AsyncMock(return_value=fake_thread)

    msg._fake_thread = fake_thread
    msg._thinking_msg = thinking_msg
    return msg


def _make_fake_payload(
    *,
    emoji_char: str,
    message_id: int = 1001,
    channel_id: int = 2002,
    user_id: int = 3003,
    guild_id: int = 4004,
) -> Any:
    """Build a fake RawReactionActionEvent payload."""
    payload = MagicMock()
    payload.message_id = message_id
    payload.channel_id = channel_id
    payload.user_id = user_id
    payload.guild_id = guild_id

    emoji = MagicMock()
    emoji.__str__ = lambda self: emoji_char
    payload.emoji = emoji
    return payload


# =============================================================================
# Task 1: Bot startup, slash sync, admin gate (DISC-07, DISC-09)
# =============================================================================


async def test_start_missing_sdk_marks_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With discord absent from sys.modules, start() marks error; no task scheduled."""
    monkeypatch.setitem(sys.modules, "discord", None)
    monkeypatch.setitem(sys.modules, "discord.ext", None)
    monkeypatch.setitem(sys.modules, "discord.ext.commands", None)
    monkeypatch.setitem(sys.modules, "discord.app_commands", None)
    ctx = _make_context(tmp_path)
    adapter = DiscordAdapter()
    await adapter.start(ctx)
    entry = ctx.registry.get("discord")
    assert entry.status == ADAPTER_STATUS_ERROR
    assert "discord.py" in (entry.error_message or "")
    assert adapter._task is None


async def test_start_missing_guild_id_marks_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With token set but GUILD_ID unset, start() marks error (graceful degradation)."""
    _install_fake_discord(monkeypatch)
    monkeypatch.setenv("HORUS_OS_DISCORD_TOKEN", "test-token-not-real")
    monkeypatch.delenv("HORUS_OS_DISCORD_GUILD_ID", raising=False)
    ctx = _make_context(tmp_path)
    adapter = DiscordAdapter()
    await adapter.start(ctx)
    entry = ctx.registry.get("discord")
    assert entry.status == ADAPTER_STATUS_ERROR
    assert "HORUS_OS_DISCORD_GUILD_ID" in (entry.error_message or "")
    assert adapter._task is None


async def test_start_non_numeric_guild_id_marks_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CR-03: a non-numeric GUILD_ID records an error rather than raising ValueError."""
    _install_fake_discord(monkeypatch)
    monkeypatch.setenv("HORUS_OS_DISCORD_TOKEN", "test-token-not-real")
    monkeypatch.setenv("HORUS_OS_DISCORD_GUILD_ID", "not-a-snowflake")
    ctx = _make_context(tmp_path)
    adapter = DiscordAdapter()
    await adapter.start(ctx)
    entry = ctx.registry.get("discord")
    assert entry.status == ADAPTER_STATUS_ERROR
    assert "HORUS_OS_DISCORD_GUILD_ID" in (entry.error_message or "")
    assert (
        "snowflake" in (entry.error_message or "").lower()
        or "numeric" in (entry.error_message or "").lower()
    )
    assert adapter._task is None


async def test_start_missing_admin_role_id_marks_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """WR-02: missing ADMIN_ROLE_ID records an error (matching registry + doc)."""
    _install_fake_discord(monkeypatch)
    monkeypatch.setenv("HORUS_OS_DISCORD_TOKEN", "test-token-not-real")
    monkeypatch.setenv("HORUS_OS_DISCORD_GUILD_ID", "123456789")
    monkeypatch.delenv("HORUS_OS_DISCORD_ADMIN_ROLE_ID", raising=False)
    ctx = _make_context(tmp_path)
    adapter = DiscordAdapter()
    await adapter.start(ctx)
    entry = ctx.registry.get("discord")
    assert entry.status == ADAPTER_STATUS_ERROR
    assert "HORUS_OS_DISCORD_ADMIN_ROLE_ID" in (entry.error_message or "")
    assert adapter._task is None


async def test_start_non_numeric_admin_role_id_marks_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CR-03: a non-numeric ADMIN_ROLE_ID records an error rather than raising ValueError."""
    _install_fake_discord(monkeypatch)
    monkeypatch.setenv("HORUS_OS_DISCORD_TOKEN", "test-token-not-real")
    monkeypatch.setenv("HORUS_OS_DISCORD_GUILD_ID", "123456789")
    monkeypatch.setenv("HORUS_OS_DISCORD_ADMIN_ROLE_ID", "not-a-snowflake")
    ctx = _make_context(tmp_path)
    adapter = DiscordAdapter()
    await adapter.start(ctx)
    entry = ctx.registry.get("discord")
    assert entry.status == ADAPTER_STATUS_ERROR
    assert "HORUS_OS_DISCORD_ADMIN_ROLE_ID" in (entry.error_message or "")
    assert adapter._task is None


async def test_start_marks_running_and_syncs_guild_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With token + guild_id set, start() marks running; setup_hook clears globals
    and syncs guild (DISC-07 slash hygiene)."""
    handles = _install_fake_discord(monkeypatch)
    monkeypatch.setenv("HORUS_OS_DISCORD_TOKEN", "test-token-not-real")
    monkeypatch.setenv("HORUS_OS_DISCORD_GUILD_ID", "123456789")
    monkeypatch.setenv("HORUS_OS_DISCORD_ADMIN_ROLE_ID", "999")
    ctx = _make_context(tmp_path)

    fake_run = MagicMock(return_value=AgentResult(text="ok", provider="anthropic", model="m"))
    monkeypatch.setattr(discord_adapter_module, "run_agent", fake_run)

    adapter = DiscordAdapter()
    await adapter.start(ctx)
    try:
        entry = ctx.registry.get("discord")
        assert entry.status == ADAPTER_STATUS_RUNNING
        assert adapter._task is not None
        # Yield so setup_hook runs inside the bot.start coroutine
        await asyncio.sleep(0)
        # clear_commands(guild=None) must have been called (stale global clear)
        none_clears = [c for c in handles.tree_clear_commands_calls if c is None]
        assert len(none_clears) >= 1, (
            f"Expected clear_commands(guild=None); got {handles.tree_clear_commands_calls}"
        )
        # sync(guild=<guild object>) must have been called
        guild_syncs = [s for s in handles.tree_sync_calls if s is not None]
        assert len(guild_syncs) >= 1, f"Expected sync(guild=<obj>); got {handles.tree_sync_calls}"
    finally:
        await adapter.stop()


async def test_setup_hook_uses_public_name_not_underscore(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CR-01 regression: adapter must assign bot.setup_hook (no underscore).

    If the adapter reverts to bot._setup_hook, the fake bot's start() will not
    call the hook (it only calls setup_hook from the instance __dict__), so
    tree_sync_calls will be empty and this test will catch the regression.
    """
    handles = _install_fake_discord(monkeypatch)
    monkeypatch.setenv("HORUS_OS_DISCORD_TOKEN", "test-token-not-real")
    monkeypatch.setenv("HORUS_OS_DISCORD_GUILD_ID", "123456789")
    monkeypatch.setenv("HORUS_OS_DISCORD_ADMIN_ROLE_ID", "999")
    ctx = _make_context(tmp_path)

    fake_run = MagicMock(return_value=AgentResult(text="ok", provider="anthropic", model="m"))
    monkeypatch.setattr(discord_adapter_module, "run_agent", fake_run)

    adapter = DiscordAdapter()
    await adapter.start(ctx)
    try:
        await asyncio.sleep(0)
        bot = handles.bot
        assert bot is not None
        # The hook MUST be stored under the public name 'setup_hook', not '_setup_hook'.
        # If the adapter incorrectly used bot._setup_hook, bot.__dict__ would have
        # '_setup_hook' but NOT 'setup_hook', so the fake's start() would skip the
        # hook and tree_sync_calls would be empty.
        assert "setup_hook" in bot.__dict__, (
            "bot.setup_hook not found in instance __dict__. "
            "Adapter must assign bot.setup_hook = setup_hook (no underscore), "
            "not bot._setup_hook."
        )
        assert "_setup_hook" not in bot.__dict__, (
            "bot._setup_hook found in instance __dict__. "
            "Adapter incorrectly assigned to the private name."
        )
        # Also confirm the hook actually ran (slash sync happened)
        assert handles.setup_hook_called, "setup_hook was not called by bot.start()"
        guild_syncs = [s for s in handles.tree_sync_calls if s is not None]
        assert len(guild_syncs) >= 1, (
            f"Guild sync must run via setup_hook; got {handles.tree_sync_calls}"
        )
    finally:
        await adapter.stop()


async def test_admin_gate_rejects_non_admin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Admin predicate denies when interaction.user.get_role() returns None."""
    handles = _install_fake_discord(monkeypatch)
    monkeypatch.setenv("HORUS_OS_DISCORD_TOKEN", "test-token-not-real")
    monkeypatch.setenv("HORUS_OS_DISCORD_GUILD_ID", "123456789")
    monkeypatch.setenv("HORUS_OS_DISCORD_ADMIN_ROLE_ID", "999")
    ctx = _make_context(tmp_path)

    fake_run = MagicMock(return_value=AgentResult(text="ok", provider="anthropic", model="m"))
    monkeypatch.setattr(discord_adapter_module, "run_agent", fake_run)

    adapter = DiscordAdapter()
    await adapter.start(ctx)
    try:
        await asyncio.sleep(0)
        predicate = handles.setup_command_predicate
        assert predicate is not None, "Admin predicate not registered"

        interaction = MagicMock()
        interaction.user.get_role = MagicMock(return_value=None)
        interaction.response.send_message = AsyncMock()

        result = await predicate(interaction)
        assert result is False
        interaction.response.send_message.assert_awaited_once()
        msg = interaction.response.send_message.call_args.kwargs.get("content") or ""
        assert "admin" in msg.lower() or "role" in msg.lower()
    finally:
        await adapter.stop()


async def test_admin_gate_allows_admin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Admin predicate allows when interaction.user.get_role() returns a role object."""
    handles = _install_fake_discord(monkeypatch)
    monkeypatch.setenv("HORUS_OS_DISCORD_TOKEN", "test-token-not-real")
    monkeypatch.setenv("HORUS_OS_DISCORD_GUILD_ID", "123456789")
    monkeypatch.setenv("HORUS_OS_DISCORD_ADMIN_ROLE_ID", "999")
    ctx = _make_context(tmp_path)

    fake_run = MagicMock(return_value=AgentResult(text="ok", provider="anthropic", model="m"))
    monkeypatch.setattr(discord_adapter_module, "run_agent", fake_run)

    adapter = DiscordAdapter()
    await adapter.start(ctx)
    try:
        await asyncio.sleep(0)
        predicate = handles.setup_command_predicate
        assert predicate is not None, "Admin predicate not registered"

        interaction = MagicMock()
        interaction.user.get_role = MagicMock(return_value=object())  # non-None = has role
        interaction.response.send_message = AsyncMock()

        result = await predicate(interaction)
        assert result is True
        interaction.response.send_message.assert_not_awaited()
    finally:
        await adapter.stop()


# =============================================================================
# Task 2: Idempotent bootstrap (DISC-05 / TEST-28) and thread dispatch (DISC-06)
# =============================================================================


async def test_bootstrap_creates_missing_channels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given a guild with no managed channels, _bootstrap creates them all."""
    _install_fake_discord(monkeypatch)
    monkeypatch.setenv("HORUS_OS_DISCORD_TOKEN", "test-token-not-real")
    monkeypatch.setenv("HORUS_OS_DISCORD_GUILD_ID", "123456789")
    monkeypatch.setenv("HORUS_OS_DISCORD_ADMIN_ROLE_ID", "999")
    ctx = _make_context(tmp_path)

    fake_run = MagicMock(return_value=AgentResult(text="ok", provider="anthropic", model="m"))
    monkeypatch.setattr(discord_adapter_module, "run_agent", fake_run)

    adapter = DiscordAdapter()
    await adapter.start(ctx)
    try:
        guild = _make_fake_guild(existing_channels=[])
        await adapter._bootstrap(guild)

        # All three managed channels should have been created
        assert guild.create_text_channel.await_count == 3
        created_names = [c.args[0] for c in guild.create_text_channel.await_args_list]
        assert "horus" in created_names
        assert "horus-tasks" in created_names
        assert "horus-activity" in created_names
    finally:
        await adapter.stop()


async def test_bootstrap_skips_existing_channels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given a guild with all managed channels, _bootstrap calls create_text_channel zero times."""
    _install_fake_discord(monkeypatch)
    monkeypatch.setenv("HORUS_OS_DISCORD_TOKEN", "test-token-not-real")
    monkeypatch.setenv("HORUS_OS_DISCORD_GUILD_ID", "123456789")
    monkeypatch.setenv("HORUS_OS_DISCORD_ADMIN_ROLE_ID", "999")
    ctx = _make_context(tmp_path)

    fake_run = MagicMock(return_value=AgentResult(text="ok", provider="anthropic", model="m"))
    monkeypatch.setattr(discord_adapter_module, "run_agent", fake_run)

    adapter = DiscordAdapter()
    await adapter.start(ctx)
    try:
        guild = _make_fake_guild(existing_channels=["horus", "horus-tasks", "horus-activity"])
        await adapter._bootstrap(guild)
        assert guild.create_text_channel.await_count == 0
    finally:
        await adapter.stop()


async def test_bootstrap_never_deletes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TEST-28 part a: zero delete calls across any bootstrap run (DISC-05 hard constraint)."""
    _install_fake_discord(monkeypatch)
    monkeypatch.setenv("HORUS_OS_DISCORD_TOKEN", "test-token-not-real")
    monkeypatch.setenv("HORUS_OS_DISCORD_GUILD_ID", "123456789")
    monkeypatch.setenv("HORUS_OS_DISCORD_ADMIN_ROLE_ID", "999")
    ctx = _make_context(tmp_path)

    fake_run = MagicMock(return_value=AgentResult(text="ok", provider="anthropic", model="m"))
    monkeypatch.setattr(discord_adapter_module, "run_agent", fake_run)

    adapter = DiscordAdapter()
    await adapter.start(ctx)
    try:
        guild = _make_fake_guild(existing_channels=["horus", "horus-tasks", "horus-activity"])
        await adapter._bootstrap(guild)

        for ch in guild.text_channels:
            ch.delete.assert_not_awaited()

        guild2 = _make_fake_guild(existing_channels=[])
        await adapter._bootstrap(guild2)
        for ch in guild2.text_channels:
            ch.delete.assert_not_awaited()
    finally:
        await adapter.stop()


async def test_bootstrap_second_run_noop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TEST-28 part b: second bootstrap run is a no-op (same channel count, zero creates)."""
    _install_fake_discord(monkeypatch)
    monkeypatch.setenv("HORUS_OS_DISCORD_TOKEN", "test-token-not-real")
    monkeypatch.setenv("HORUS_OS_DISCORD_GUILD_ID", "123456789")
    monkeypatch.setenv("HORUS_OS_DISCORD_ADMIN_ROLE_ID", "999")
    ctx = _make_context(tmp_path)

    fake_run = MagicMock(return_value=AgentResult(text="ok", provider="anthropic", model="m"))
    monkeypatch.setattr(discord_adapter_module, "run_agent", fake_run)

    adapter = DiscordAdapter()
    await adapter.start(ctx)
    try:
        # Simulating what a "first run" would build: after run 1 all channels exist.
        # We test directly with a guild that already has all channels (simulates post-run-1 state).
        guild = _make_fake_guild(existing_channels=["horus", "horus-tasks", "horus-activity"])

        # First run (already complete state)
        await adapter._bootstrap(guild)
        count_after_first = guild.create_text_channel.await_count
        assert count_after_first == 0

        # Second run must not create anything new
        guild.create_text_channel.reset_mock()
        await adapter._bootstrap(guild)
        assert guild.create_text_channel.await_count == 0
    finally:
        await adapter.stop()


async def test_horus_thread_dispatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A message in #horus creates a thread, dispatches to the orchestrator,
    and edits the thinking message to a status-card embed (DISC-06, DISC-08)."""
    handles = _install_fake_discord(monkeypatch)
    monkeypatch.setenv("HORUS_OS_DISCORD_TOKEN", "test-token-not-real")
    monkeypatch.setenv("HORUS_OS_DISCORD_GUILD_ID", "123456789")
    monkeypatch.setenv("HORUS_OS_DISCORD_ADMIN_ROLE_ID", "999")

    fake_run = MagicMock(
        return_value=AgentResult(text="agent reply", provider="anthropic", model="m")
    )
    monkeypatch.setattr(discord_adapter_module, "run_agent", fake_run)

    ctx = _make_context(tmp_path)
    adapter = DiscordAdapter()
    await adapter.start(ctx)
    try:
        await asyncio.sleep(0)

        on_msg = handles.on_message_handler
        assert on_msg is not None, "on_message handler not registered"

        msg = _make_fake_message(content="build a chart", channel_name="horus")
        # The bot.user is set on the fake bot; message author is a different object
        await on_msg(msg)

        msg.create_thread.assert_awaited_once()
        thread_name_arg = msg.create_thread.call_args.kwargs.get("name") or ""
        assert "build a chart" in thread_name_arg or len(thread_name_arg) <= 100

        fake_thread = msg._fake_thread
        fake_thread.send.assert_awaited()
        thinking_msg = msg._thinking_msg
        thinking_msg.edit.assert_awaited_once()

        # The edited message must be an embed
        edit_kwargs = thinking_msg.edit.call_args.kwargs
        embed = edit_kwargs.get("embed")
        assert embed is not None
        assert embed.description is not None and "build a chart" in embed.description[:500]

        # Result field must contain agent reply
        result_fields = [f for f in embed.fields if f["name"] == "Result"]
        assert result_fields, f"No Result field in embed fields: {embed.fields}"
        assert "agent reply" in result_fields[0]["value"]
    finally:
        await adapter.stop()


async def test_non_horus_channel_ignored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A message in a channel not named 'horus' does not create a thread."""
    handles = _install_fake_discord(monkeypatch)
    monkeypatch.setenv("HORUS_OS_DISCORD_TOKEN", "test-token-not-real")
    monkeypatch.setenv("HORUS_OS_DISCORD_GUILD_ID", "123456789")
    monkeypatch.setenv("HORUS_OS_DISCORD_ADMIN_ROLE_ID", "999")

    fake_run = MagicMock(return_value=AgentResult(text="hi", provider="anthropic", model="m"))
    monkeypatch.setattr(discord_adapter_module, "run_agent", fake_run)

    ctx = _make_context(tmp_path)
    adapter = DiscordAdapter()
    await adapter.start(ctx)
    try:
        await asyncio.sleep(0)
        on_msg = handles.on_message_handler
        assert on_msg is not None

        msg = _make_fake_message(content="hello", channel_name="general")
        await on_msg(msg)
        msg.create_thread.assert_not_awaited()
        assert fake_run.call_count == 0
    finally:
        await adapter.stop()


async def test_dispatch_exception_posts_error_embed_not_ghost(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CR-02 regression: if run_agent raises, the thinking message is edited to an
    error embed (not left as a ghost 'Processing...' message) and the handler does
    not propagate the exception."""
    handles = _install_fake_discord(monkeypatch)
    monkeypatch.setenv("HORUS_OS_DISCORD_TOKEN", "test-token-not-real")
    monkeypatch.setenv("HORUS_OS_DISCORD_GUILD_ID", "123456789")
    monkeypatch.setenv("HORUS_OS_DISCORD_ADMIN_ROLE_ID", "999")

    fake_run = MagicMock(side_effect=RuntimeError("orchestrator failed"))
    monkeypatch.setattr(discord_adapter_module, "run_agent", fake_run)

    ctx = _make_context(tmp_path)
    adapter = DiscordAdapter()
    await adapter.start(ctx)
    try:
        await asyncio.sleep(0)
        on_msg = handles.on_message_handler
        assert on_msg is not None

        msg = _make_fake_message(content="crash me", channel_name="horus")
        # Must not raise even though run_agent raises
        await on_msg(msg)

        msg.create_thread.assert_awaited_once()
        thinking_msg = msg._thinking_msg
        # The thinking message must be edited (not left as ghost 'Processing...')
        thinking_msg.edit.assert_awaited_once()
        edit_kwargs = thinking_msg.edit.call_args.kwargs
        embed = edit_kwargs.get("embed")
        assert embed is not None, "Expected an error embed, got none"
        # Status field should indicate error
        status_fields = [f for f in embed.fields if f["name"] == "Status"]
        assert status_fields, f"No Status field in embed: {embed.fields}"
        assert status_fields[0]["value"] == "error"
    finally:
        await adapter.stop()


async def test_v07_intents_include_dm_messages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """WR-04 regression: v0.7 bot path must include dm_messages intent."""
    handles = _install_fake_discord(monkeypatch)
    monkeypatch.setenv("HORUS_OS_DISCORD_TOKEN", "test-token-not-real")
    monkeypatch.setenv("HORUS_OS_DISCORD_GUILD_ID", "123456789")
    monkeypatch.setenv("HORUS_OS_DISCORD_ADMIN_ROLE_ID", "999")

    fake_run = MagicMock(return_value=AgentResult(text="ok", provider="anthropic", model="m"))
    monkeypatch.setattr(discord_adapter_module, "run_agent", fake_run)

    ctx = _make_context(tmp_path)
    adapter = DiscordAdapter()
    await adapter.start(ctx)
    try:
        intents = handles.intents_captured
        assert intents is not None
        assert intents.dm_messages is True, (
            "v0.7 bot path must set intents.dm_messages = True to preserve DM handling"
        )
    finally:
        await adapter.stop()


# =============================================================================
# Task 3: Reaction feedback (DISC-08) and graceful degradation
# =============================================================================


async def test_reaction_feedback_positive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Thumbs-up reaction writes a row with positive=True via save_discord_feedback."""
    handles = _install_fake_discord(monkeypatch)
    monkeypatch.setenv("HORUS_OS_DISCORD_TOKEN", "test-token-not-real")
    monkeypatch.setenv("HORUS_OS_DISCORD_GUILD_ID", "123456789")
    monkeypatch.setenv("HORUS_OS_DISCORD_ADMIN_ROLE_ID", "999")

    fake_run = MagicMock(return_value=AgentResult(text="ok", provider="anthropic", model="m"))
    monkeypatch.setattr(discord_adapter_module, "run_agent", fake_run)

    ctx = _make_context(tmp_path)
    adapter = DiscordAdapter()
    await adapter.start(ctx)
    try:
        await asyncio.sleep(0)
        handler = handles.on_raw_reaction_add_handler
        assert handler is not None, "on_raw_reaction_add handler not registered"

        payload = _make_fake_payload(
            emoji_char="\U0001f44d",
            message_id=101,
            channel_id=202,
            user_id=303,
        )
        await handler(payload)

        # Read back from the SQLite db
        conn = sqlite3.connect(str(ctx.config.db_path))
        row = conn.execute(
            "SELECT positive FROM discord_feedback WHERE message_id = '101' AND user_id = '303'"
        ).fetchone()
        conn.close()
        assert row is not None, "No feedback row written"
        assert row[0] == 1, f"Expected positive=1 got {row[0]}"
    finally:
        await adapter.stop()


async def test_reaction_feedback_negative(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Thumbs-down reaction writes a row with positive=False via save_discord_feedback."""
    handles = _install_fake_discord(monkeypatch)
    monkeypatch.setenv("HORUS_OS_DISCORD_TOKEN", "test-token-not-real")
    monkeypatch.setenv("HORUS_OS_DISCORD_GUILD_ID", "123456789")
    monkeypatch.setenv("HORUS_OS_DISCORD_ADMIN_ROLE_ID", "999")

    fake_run = MagicMock(return_value=AgentResult(text="ok", provider="anthropic", model="m"))
    monkeypatch.setattr(discord_adapter_module, "run_agent", fake_run)

    ctx = _make_context(tmp_path)
    adapter = DiscordAdapter()
    await adapter.start(ctx)
    try:
        await asyncio.sleep(0)
        handler = handles.on_raw_reaction_add_handler
        assert handler is not None, "on_raw_reaction_add handler not registered"

        payload = _make_fake_payload(
            emoji_char="\U0001f44e",
            message_id=201,
            channel_id=202,
            user_id=303,
        )
        await handler(payload)

        conn = sqlite3.connect(str(ctx.config.db_path))
        row = conn.execute(
            "SELECT positive FROM discord_feedback WHERE message_id = '201' AND user_id = '303'"
        ).fetchone()
        conn.close()
        assert row is not None, "No feedback row written"
        assert row[0] == 0, f"Expected positive=0 got {row[0]}"
    finally:
        await adapter.stop()


async def test_reaction_other_emoji_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A non-thumbs emoji writes no feedback row."""
    handles = _install_fake_discord(monkeypatch)
    monkeypatch.setenv("HORUS_OS_DISCORD_TOKEN", "test-token-not-real")
    monkeypatch.setenv("HORUS_OS_DISCORD_GUILD_ID", "123456789")
    monkeypatch.setenv("HORUS_OS_DISCORD_ADMIN_ROLE_ID", "999")

    fake_run = MagicMock(return_value=AgentResult(text="ok", provider="anthropic", model="m"))
    monkeypatch.setattr(discord_adapter_module, "run_agent", fake_run)

    ctx = _make_context(tmp_path)
    adapter = DiscordAdapter()
    await adapter.start(ctx)
    try:
        await asyncio.sleep(0)
        handler = handles.on_raw_reaction_add_handler
        assert handler is not None

        payload = _make_fake_payload(
            emoji_char="\U0001f600",  # grinning face - not thumbs
            message_id=301,
            channel_id=202,
            user_id=303,
        )
        await handler(payload)

        conn = sqlite3.connect(str(ctx.config.db_path))
        row = conn.execute(
            "SELECT positive FROM discord_feedback WHERE message_id = '301'"
        ).fetchone()
        conn.close()
        assert row is None, "Expected no feedback row for non-thumbs emoji"
    finally:
        await adapter.stop()


async def test_reaction_persists_via_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reaction feedback is readable from the SQLite db created by _make_context
    (proves the bot -> Database.save_discord_feedback link from Plan 01)."""
    handles = _install_fake_discord(monkeypatch)
    monkeypatch.setenv("HORUS_OS_DISCORD_TOKEN", "test-token-not-real")
    monkeypatch.setenv("HORUS_OS_DISCORD_GUILD_ID", "123456789")
    monkeypatch.setenv("HORUS_OS_DISCORD_ADMIN_ROLE_ID", "999")

    fake_run = MagicMock(return_value=AgentResult(text="ok", provider="anthropic", model="m"))
    monkeypatch.setattr(discord_adapter_module, "run_agent", fake_run)

    ctx = _make_context(tmp_path)
    adapter = DiscordAdapter()
    await adapter.start(ctx)
    try:
        await asyncio.sleep(0)
        handler = handles.on_raw_reaction_add_handler
        assert handler is not None

        payload = _make_fake_payload(
            emoji_char="\U0001f44d",
            message_id=401,
            channel_id=402,
            user_id=403,
        )
        await handler(payload)

        # Verify the row is readable from the test db via direct sqlite3 query.
        conn = sqlite3.connect(str(ctx.config.db_path))
        row = conn.execute(
            "SELECT message_id, channel_id, user_id, emoji, positive "
            "FROM discord_feedback WHERE message_id = '401'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "401"
        assert row[1] == "402"
        assert row[2] == "403"
        assert row[4] == 1
    finally:
        await adapter.stop()


async def test_runtime_starts_without_discord_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With neither token nor guild_id set and discord importable,
    start() marks error; self._bot and self._task remain None (graceful degradation)."""
    _install_fake_discord(monkeypatch)
    monkeypatch.delenv("HORUS_OS_DISCORD_TOKEN", raising=False)
    monkeypatch.delenv("HORUS_OS_DISCORD_GUILD_ID", raising=False)
    ctx = _make_context(tmp_path)
    adapter = DiscordAdapter()
    # Must not raise
    await adapter.start(ctx)
    entry = ctx.registry.get("discord")
    assert entry.status == ADAPTER_STATUS_ERROR
    assert adapter._task is None
