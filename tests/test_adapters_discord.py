"""Tests for the Discord adapter.

All tests run with `discord.py` simulated as either missing or
stubbed via a fake module installed into `sys.modules`. No live
Discord connection is opened in any test.

`run_agent` is monkeypatched at the adapter module level so no
provider SDK is required and no network call happens.
"""

from __future__ import annotations

import asyncio
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


def _install_fake_discord(monkeypatch: pytest.MonkeyPatch) -> types.SimpleNamespace:
    """Inject a fake `discord` module into sys.modules.

    Returns a SimpleNamespace exposing handles the test can assert
    on: the fake `Client` instance, the captured `on_message`
    handler, and the recorded calls.
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
        intents_captured=None,
    )

    class _Client:
        def __init__(self, intents: Any = None) -> None:
            self.intents = intents
            handles.intents_captured = intents
            self.user = object()
            handles.client = self
            self._on_message = None

        def event(self, coro: Any) -> Any:
            # discord.py's `Client.event` registers by attribute name
            # of the coroutine; for the fake we accept any coro and
            # store it under the name `on_message`.
            handles.on_message = coro
            self._on_message = coro
            return coro

        async def start(self, token: str, **kwargs: Any) -> None:
            handles.start_calls.append((token, kwargs))
            # Block forever so the background task does not finish
            # before the test cancels it.
            await asyncio.Event().wait()

        async def close(self) -> None:
            handles.close_calls += 1

    fake.Client = _Client
    monkeypatch.setitem(sys.modules, "discord", fake)
    return handles


def _make_message(
    *,
    content: str,
    author: Any,
    channel: Any | None = None,
    guild: Any | None = None,
    mentions: list[Any] | None = None,
) -> MagicMock:
    msg = MagicMock()
    msg.content = content
    msg.author = author
    msg.channel = channel if channel is not None else MagicMock()
    msg.channel.send = AsyncMock()
    msg.guild = guild
    msg.mentions = mentions if mentions is not None else []
    return msg


# -- construction -------------------------------------------------------------


def test_construct_clean_without_discord_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    """`DiscordAdapter()` works even when sys.modules has no `discord` entry."""
    # Force `import discord` to fail if anyone calls it during construction.
    monkeypatch.setitem(sys.modules, "discord", None)
    adapter = DiscordAdapter()
    assert adapter.name == "discord"
    assert adapter._client is None
    assert adapter._task is None


def test_bind_is_noop(tmp_path: Path) -> None:
    adapter = DiscordAdapter()
    ctx = _make_context(tmp_path)
    # bind must accept the FastAPI app and context but does nothing.
    assert adapter.bind(MagicMock(), ctx) is None


# -- start error paths --------------------------------------------------------


async def test_start_missing_sdk_marks_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # `None` in sys.modules makes `import discord` raise ImportError.
    monkeypatch.setitem(sys.modules, "discord", None)
    ctx = _make_context(tmp_path)
    adapter = DiscordAdapter()
    await adapter.start(ctx)
    entry = ctx.registry.get("discord")
    assert entry.status == ADAPTER_STATUS_ERROR
    assert "discord.py" in (entry.error_message or "")
    assert adapter._client is None
    assert adapter._task is None


async def test_start_missing_token_marks_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_discord(monkeypatch)
    monkeypatch.delenv("HORUS_OS_DISCORD_TOKEN", raising=False)
    ctx = _make_context(tmp_path)
    adapter = DiscordAdapter()
    await adapter.start(ctx)
    entry = ctx.registry.get("discord")
    assert entry.status == ADAPTER_STATUS_ERROR
    assert "HORUS_OS_DISCORD_TOKEN" in (entry.error_message or "")
    assert adapter._client is None


# -- start happy path ---------------------------------------------------------


async def test_start_with_token_marks_running_and_schedules_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    handles = _install_fake_discord(monkeypatch)
    monkeypatch.setenv("HORUS_OS_DISCORD_TOKEN", "test-token-not-real")
    ctx = _make_context(tmp_path)
    adapter = DiscordAdapter()
    await adapter.start(ctx)
    try:
        entry = ctx.registry.get("discord")
        assert entry.status == ADAPTER_STATUS_RUNNING
        assert handles.client is not None
        assert handles.on_message is not None
        # Intents requested by the adapter.
        intents = handles.intents_captured
        assert intents.guilds is True
        assert intents.guild_messages is True
        assert intents.dm_messages is True
        assert intents.message_content is True
        assert adapter._task is not None
        assert not adapter._task.done()
        # Give the event loop a moment so the fake client's `start`
        # actually begins executing.
        await asyncio.sleep(0)
        assert handles.start_calls
        assert handles.start_calls[0][0] == "test-token-not-real"
    finally:
        await adapter.stop()


# -- on_message routing -------------------------------------------------------


async def test_on_message_ignores_own_messages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    handles = _install_fake_discord(monkeypatch)
    monkeypatch.setenv("HORUS_OS_DISCORD_TOKEN", "test-token-not-real")
    fake_run = MagicMock(return_value=AgentResult(text="hi", provider="anthropic", model="m"))
    monkeypatch.setattr(discord_adapter_module, "run_agent", fake_run)
    ctx = _make_context(tmp_path)
    adapter = DiscordAdapter()
    await adapter.start(ctx)
    try:
        client = handles.client
        msg = _make_message(content="hello", author=client.user)
        await handles.on_message(msg)
        assert fake_run.call_count == 0
        msg.channel.send.assert_not_called()
    finally:
        await adapter.stop()


async def test_on_message_ignores_guild_non_mentions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    handles = _install_fake_discord(monkeypatch)
    monkeypatch.setenv("HORUS_OS_DISCORD_TOKEN", "test-token-not-real")
    fake_run = MagicMock(return_value=AgentResult(text="hi", provider="anthropic", model="m"))
    monkeypatch.setattr(discord_adapter_module, "run_agent", fake_run)
    ctx = _make_context(tmp_path)
    adapter = DiscordAdapter()
    await adapter.start(ctx)
    try:
        msg = _make_message(
            content="general chatter",
            author=object(),
            guild=object(),
            mentions=[],
        )
        await handles.on_message(msg)
        assert fake_run.call_count == 0
        msg.channel.send.assert_not_called()
    finally:
        await adapter.stop()


async def test_on_message_responds_to_dm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    handles = _install_fake_discord(monkeypatch)
    monkeypatch.setenv("HORUS_OS_DISCORD_TOKEN", "test-token-not-real")
    fake_run = MagicMock(
        return_value=AgentResult(text="hello back", provider="anthropic", model="m")
    )
    monkeypatch.setattr(discord_adapter_module, "run_agent", fake_run)
    ctx = _make_context(tmp_path)
    adapter = DiscordAdapter()
    await adapter.start(ctx)
    try:
        # guild=None means a DM channel.
        msg = _make_message(content="hi there", author=object(), guild=None)
        await handles.on_message(msg)
        assert fake_run.call_count == 1
        # prompt forwarded into run_agent (first positional arg).
        assert fake_run.call_args.args[0] == "hi there"
        msg.channel.send.assert_awaited_once_with("hello back")
        # touch bumped last_activity_at.
        assert ctx.registry.get("discord").last_activity_at is not None
    finally:
        await adapter.stop()


async def test_on_message_responds_to_guild_mention(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    handles = _install_fake_discord(monkeypatch)
    monkeypatch.setenv("HORUS_OS_DISCORD_TOKEN", "test-token-not-real")
    fake_run = MagicMock(
        return_value=AgentResult(text="reply text", provider="anthropic", model="m")
    )
    monkeypatch.setattr(discord_adapter_module, "run_agent", fake_run)
    ctx = _make_context(tmp_path)
    adapter = DiscordAdapter()
    await adapter.start(ctx)
    try:
        client = handles.client
        # In a guild channel: only mentions trigger; we include the
        # leading mention token in the raw content as Discord does.
        msg = _make_message(
            content="<@123> what's up",
            author=object(),
            guild=object(),
            mentions=[client.user],
        )
        await handles.on_message(msg)
        assert fake_run.call_count == 1
        # The mention token must be stripped before forwarding.
        assert fake_run.call_args.args[0] == "what's up"
        msg.channel.send.assert_awaited_once_with("reply text")
    finally:
        await adapter.stop()


async def test_on_message_loads_configured_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    handles = _install_fake_discord(monkeypatch)
    monkeypatch.setenv("HORUS_OS_DISCORD_TOKEN", "test-token-not-real")
    monkeypatch.setenv("HORUS_OS_DISCORD_AGENT_PROFILE", "scribe")
    fake_run = MagicMock(return_value=AgentResult(text="ok", provider="anthropic", model="m"))
    monkeypatch.setattr(discord_adapter_module, "run_agent", fake_run)
    ctx = _make_context(tmp_path)
    # Seed the database with a `scribe` profile.
    db = Database(ctx.config.db_path)
    from horus_os.types import AgentProfile

    db.save_profile(
        AgentProfile(
            name="scribe",
            system_prompt="you are scribe",
            default_model="claude-test",
        )
    )
    adapter = DiscordAdapter()
    await adapter.start(ctx)
    try:
        msg = _make_message(content="please write a note", author=object(), guild=None)
        await handles.on_message(msg)
        assert fake_run.call_count == 1
        # system_prompt and model from the loaded profile.
        kwargs = fake_run.call_args.kwargs
        assert kwargs["system_prompt"] == "you are scribe"
        assert kwargs["model"] == "claude-test"
    finally:
        await adapter.stop()


async def test_on_message_missing_profile_is_non_fatal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    handles = _install_fake_discord(monkeypatch)
    monkeypatch.setenv("HORUS_OS_DISCORD_TOKEN", "test-token-not-real")
    # Point at a profile name that the seeded DB does not have so we
    # exercise the load_profile -> None fallback.
    monkeypatch.setenv("HORUS_OS_DISCORD_AGENT_PROFILE", "ghost-profile")
    fake_run = MagicMock(return_value=AgentResult(text="ok", provider="anthropic", model="m"))
    monkeypatch.setattr(discord_adapter_module, "run_agent", fake_run)
    ctx = _make_context(tmp_path)
    adapter = DiscordAdapter()
    await adapter.start(ctx)
    try:
        msg = _make_message(content="hi", author=object(), guild=None)
        await handles.on_message(msg)
        # No raise. Agent ran. system_prompt is None when profile missing.
        assert fake_run.call_count == 1
        assert fake_run.call_args.kwargs["system_prompt"] is None
    finally:
        await adapter.stop()


# -- chunking -----------------------------------------------------------------


async def test_long_reply_chunks_into_2000_char_segments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    handles = _install_fake_discord(monkeypatch)
    monkeypatch.setenv("HORUS_OS_DISCORD_TOKEN", "test-token-not-real")
    long_text = "x" * 4500  # 3 chunks: 2000 + 2000 + 500
    fake_run = MagicMock(return_value=AgentResult(text=long_text, provider="anthropic", model="m"))
    monkeypatch.setattr(discord_adapter_module, "run_agent", fake_run)
    ctx = _make_context(tmp_path)
    adapter = DiscordAdapter()
    await adapter.start(ctx)
    try:
        msg = _make_message(content="give me a wall of text", author=object(), guild=None)
        await handles.on_message(msg)
        assert msg.channel.send.await_count == 3
        sent = [c.args[0] for c in msg.channel.send.await_args_list]
        assert all(len(s) <= 2000 for s in sent)
        assert sum(len(s) for s in sent) == 4500
    finally:
        await adapter.stop()


async def test_empty_reply_posts_no_response_placeholder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    handles = _install_fake_discord(monkeypatch)
    monkeypatch.setenv("HORUS_OS_DISCORD_TOKEN", "test-token-not-real")
    fake_run = MagicMock(return_value=AgentResult(text="", provider="anthropic", model="m"))
    monkeypatch.setattr(discord_adapter_module, "run_agent", fake_run)
    ctx = _make_context(tmp_path)
    adapter = DiscordAdapter()
    await adapter.start(ctx)
    try:
        msg = _make_message(content="say nothing", author=object(), guild=None)
        await handles.on_message(msg)
        msg.channel.send.assert_awaited_once_with("(no response)")
    finally:
        await adapter.stop()


# -- error isolation ----------------------------------------------------------


async def test_run_agent_exception_surfaces_as_reply_and_registry_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    handles = _install_fake_discord(monkeypatch)
    monkeypatch.setenv("HORUS_OS_DISCORD_TOKEN", "test-token-not-real")

    def boom(*args: Any, **kwargs: Any) -> AgentResult:
        raise RuntimeError("provider down")

    monkeypatch.setattr(discord_adapter_module, "run_agent", boom)
    ctx = _make_context(tmp_path)
    adapter = DiscordAdapter()
    await adapter.start(ctx)
    try:
        msg = _make_message(content="hi", author=object(), guild=None)
        await handles.on_message(msg)
        # The handler did not raise.
        msg.channel.send.assert_awaited_once()
        sent = msg.channel.send.await_args.args[0]
        assert "RuntimeError" in sent
        entry = ctx.registry.get("discord")
        assert entry.error_count >= 1
        assert "RuntimeError" in (entry.error_message or "")
    finally:
        await adapter.stop()


# -- stop ---------------------------------------------------------------------


async def test_stop_closes_client_and_cancels_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    handles = _install_fake_discord(monkeypatch)
    monkeypatch.setenv("HORUS_OS_DISCORD_TOKEN", "test-token-not-real")
    ctx = _make_context(tmp_path)
    adapter = DiscordAdapter()
    await adapter.start(ctx)
    task = adapter._task
    assert task is not None
    await adapter.stop()
    assert handles.close_calls == 1
    assert task.cancelled() or task.done()


async def test_stop_is_noop_when_start_never_ran(tmp_path: Path) -> None:
    # Construct an adapter and call stop without start. Must not raise.
    adapter = DiscordAdapter()
    await adapter.stop()


# -- helper -------------------------------------------------------------------


def test_strip_mention_removes_leading_tokens() -> None:
    from horus_os.adapters.discord_adapter import _strip_mention

    assert _strip_mention("<@123> hello") == "hello"
    assert _strip_mention("<@!456> hi there") == "hi there"
    assert _strip_mention("no mention here") == "no mention here"
    assert _strip_mention("<@1><@!2> double") == "double"
