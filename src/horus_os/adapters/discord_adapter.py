"""Discord adapter for horus-os.

Connects to the Discord gateway via the optional `discord.py`
dependency. In v0.3 mode it listens for app mentions in guild channels
and direct messages to the bot. The v0.7 control bot extension adds:

- Guild-scoped slash commands with stale-global-command clear on startup
  (DISC-07 slash hygiene).
- Idempotent channel bootstrap that only creates channels that do not
  exist and NEVER deletes any channel (DISC-05, TEST-28).
- The #horus thread-dispatch flow: a message in #horus opens a thread,
  dispatches the prompt to the orchestrator via asyncio.to_thread, and
  posts the result as a status-card embed (DISC-06, DISC-08).
- Reaction feedback: thumbs-up/down reactions persist feedback rows via
  Database.save_discord_feedback (DISC-08).
- Admin-role gate on /horus setup (DISC-09): the command is denied by
  default unless the caller holds the configured admin role.

The `discord` import is lazy inside `start` so this module imports
cleanly when the optional extra is not installed. Tests inject a
fake `discord` module into `sys.modules` to exercise the adapter
without the SDK on the path.

Configuration via environment variables:

- `HORUS_OS_DISCORD_TOKEN`: Discord bot token. Required.
- `HORUS_OS_DISCORD_GUILD_ID`: Target guild snowflake. Required for
  guild features (slash commands, bootstrap, thread dispatch).
- `HORUS_OS_DISCORD_ADMIN_ROLE_ID`: Role ID that may run /horus setup.
  Required for the v0.7 bot path; missing or non-numeric value records
  an error at startup.
- `HORUS_OS_DISCORD_CATEGORY`: Category name for managed channels.
  Defaults to "horus-os".
- `HORUS_OS_DISCORD_AGENT_PROFILE`: Agent profile name to load.
  Defaults to "default". Missing profile is non-fatal.

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
from datetime import UTC, datetime
from typing import Any

from horus_os.adapters.base import AdapterContext
from horus_os.agent import run_agent
from horus_os.config import Config
from horus_os.storage import Database

TOKEN_ENV = "HORUS_OS_DISCORD_TOKEN"
AGENT_ENV = "HORUS_OS_DISCORD_AGENT_PROFILE"
GUILD_ID_ENV = "HORUS_OS_DISCORD_GUILD_ID"
ADMIN_ROLE_ENV = "HORUS_OS_DISCORD_ADMIN_ROLE_ID"
CATEGORY_ENV = "HORUS_OS_DISCORD_CATEGORY"
DEFAULT_AGENT = "default"
DISCORD_MESSAGE_LIMIT = 2000
HORUS_CHANNEL = "horus"

# Managed channels created by the idempotent bootstrap.
MANAGED_CHANNELS = ("horus", "horus-tasks", "horus-activity")

# Matches Discord's leading mention tokens: `<@123>` or `<@!123>`.
_MENTION_PATTERN = re.compile(r"<@!?(\d+)>")


def _build_status_card(
    prompt: str,
    result_text: str,
    provider: str = "",
    status: str = "completed",
) -> Any:
    """Build a discord.Embed status card for a completed task.

    Imported inside the function to remain import-clean when discord.py
    is not installed. The caller is responsible for only calling this
    after a successful import of discord.
    """
    import discord

    color_map: dict[str, Any] = {
        "completed": discord.Color.green(),
        "running": discord.Color.yellow(),
        "error": discord.Color.red(),
    }
    embed = discord.Embed(
        title="Task Status",
        description=prompt[:500],
        color=color_map.get(status, discord.Color.default()),
        timestamp=datetime.now(UTC),
    )
    embed.add_field(name="Status", value=status, inline=True)
    embed.add_field(name="Agent", value=provider or "unknown", inline=True)
    if result_text:
        embed.add_field(name="Result", value=result_text[:1000], inline=False)
    return embed


class DiscordAdapter:
    """An inbound Discord adapter that routes mentions and DMs to `run_agent`.

    v0.7 adds a commands.Bot control bot (guild slash commands, thread
    dispatch, status-card embeds, reaction feedback, idempotent bootstrap).
    The bot runs as an asyncio background task so the FastAPI lifespan
    returns immediately.

    Backward compatibility: self._client is kept (set to None on the bot
    path) so the v0.3 test suite assertions on adapter._client still pass.
    Self._bot holds the commands.Bot instance on the v0.7 path.
    """

    name = "discord"

    def __init__(self) -> None:
        # All connection state is allocated in `start` so the
        # constructor stays cheap and import-clean.
        self._client: Any = None
        self._bot: Any = None
        self._task: asyncio.Task[Any] | None = None
        self._context: AdapterContext | None = None
        self._bootstrapped: bool = False

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

        Failure modes (missing dependency, missing token, missing guild
        id) are recorded into the adapter registry rather than raised so
        the FastAPI lifespan can isolate this adapter from siblings.

        When discord.ext.commands and GUILD_ID_ENV are both available the
        v0.7 control bot path activates (slash commands, thread dispatch,
        reaction feedback, idempotent bootstrap). When only the base
        discord module is available and GUILD_ID is absent the adapter
        marks an error and returns without starting any task; the host
        runtime continues unaffected.
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

        # Try to import the commands.Bot extension. When ext.commands is not
        # available (e.g., base discord installed without ext, or the v0.3 test
        # fake that only stubs discord.Client) we fall back to the v0.3 legacy
        # client path which does not require GUILD_ID_ENV.
        try:
            import discord.app_commands as _app_commands
            import discord.ext.commands as dcommands

            _bot_capable = True
        except ImportError:
            _bot_capable = False

        if not _bot_capable:
            # v0.3 legacy path: bare discord.Client with mention/DM handling.
            return await self._start_legacy(context, discord, token)

        guild_id_str = os.environ.get(GUILD_ID_ENV)
        if not guild_id_str:
            context.registry.mark_error(self.name, f"{GUILD_ID_ENV} is not set")
            return
        try:
            guild_id_int = int(guild_id_str)
        except ValueError:
            context.registry.mark_error(
                self.name,
                f"{GUILD_ID_ENV} must be a numeric snowflake; got {guild_id_str!r}",
            )
            return

        admin_role_str = os.environ.get(ADMIN_ROLE_ENV)
        if not admin_role_str:
            context.registry.mark_error(
                self.name,
                f"{ADMIN_ROLE_ENV} is not set; admin gate requires a numeric role ID",
            )
            return
        try:
            int(admin_role_str)
        except ValueError:
            context.registry.mark_error(
                self.name,
                f"{ADMIN_ROLE_ENV} must be a numeric snowflake; got {admin_role_str!r}",
            )
            return

        guild_obj = discord.Object(id=guild_id_int)

        intents = discord.Intents.none()
        intents.guilds = True
        intents.guild_messages = True
        intents.dm_messages = True
        intents.message_content = True

        bot = dcommands.Bot(command_prefix="!", intents=intents)
        self._bot = bot

        # --- Register slash commands on bot.tree ---

        adapter_ref = self

        def _admin_predicate() -> Any:
            """Return an async predicate that denies non-admin callers."""
            try:
                role_id = int(os.environ.get(ADMIN_ROLE_ENV, "0"))
            except ValueError:
                role_id = 0  # non-numeric -> deny-all

            async def predicate(interaction: Any) -> bool:
                if not role_id:
                    await interaction.response.send_message(
                        content=f"{ADMIN_ROLE_ENV} is not configured. Admin role required.",
                        ephemeral=True,
                    )
                    return False
                member = interaction.user
                if member.get_role(role_id) is None:
                    await interaction.response.send_message(
                        content="You do not have the required admin role.",
                        ephemeral=True,
                    )
                    return False
                return True

            return predicate

        @bot.tree.command(name="horus-setup", description="Bootstrap horus-os channel layout")
        @_app_commands.check(_admin_predicate())
        async def horus_setup(interaction: Any) -> None:
            await interaction.response.defer(ephemeral=True)
            guild = interaction.guild
            if guild is not None:
                await adapter_ref._bootstrap(guild)
            await interaction.followup.send("Channel bootstrap complete.", ephemeral=True)

        # --- Register event handlers ---

        @bot.event
        async def on_message(message: Any) -> None:
            if getattr(message.channel, "name", None) != HORUS_CHANNEL:
                return
            if message.author == bot.user:
                return
            content = getattr(message, "content", "") or ""
            if not content.strip():
                return

            thread_name = content[:100] or "task"
            thread = await message.create_thread(name=thread_name, auto_archive_duration=60)
            thinking_msg = await thread.send("Processing...")

            try:
                result_text = await asyncio.to_thread(adapter_ref._dispatch, content)
                embed = _build_status_card(content, result_text)
                await thinking_msg.edit(content=None, embed=embed)
            except Exception as exc:
                if adapter_ref._context is not None:
                    adapter_ref._context.registry.mark_error(
                        adapter_ref.name, f"{type(exc).__name__}: {exc}"
                    )
                error_embed = _build_status_card(content, str(type(exc).__name__), status="error")
                with contextlib.suppress(Exception):
                    await thinking_msg.edit(content=None, embed=error_embed)
                return

            if adapter_ref._context is not None:
                adapter_ref._context.registry.touch(adapter_ref.name)

        @bot.event
        async def on_raw_reaction_add(payload: Any) -> None:
            emoji_str = str(payload.emoji)
            if emoji_str == "\U0001f44d":
                positive = True
            elif emoji_str == "\U0001f44e":
                positive = False
            else:
                return

            if adapter_ref._context is None:
                return
            cfg = adapter_ref._context.config
            if not cfg.db_path.exists():
                return
            try:
                db = Database(cfg.db_path)
                db.init()  # idempotent; ensures discord_feedback table exists
                db.save_discord_feedback(
                    message_id=str(payload.message_id),
                    channel_id=str(payload.channel_id),
                    user_id=str(payload.user_id),
                    emoji=emoji_str,
                    positive=positive,
                )
            except Exception as exc:
                if adapter_ref._context is not None:
                    adapter_ref._context.registry.mark_error(
                        adapter_ref.name,
                        f"reaction feedback write failed: {type(exc).__name__}: {exc}",
                    )

        # --- setup_hook: guild-scoped slash sync (DISC-07) ---

        async def setup_hook() -> None:
            # Step 1: copy globally-declared commands to the guild
            bot.tree.copy_global_to(guild=guild_obj)
            # Step 2: clear stale global registrations
            bot.tree.clear_commands(guild=None)
            # Step 3: push empty global list (prevents duplicates)
            await bot.tree.sync(guild=None)
            # Step 4: push guild commands (instant propagation)
            await bot.tree.sync(guild=guild_obj)

        bot.setup_hook = setup_hook

        coro = bot.start(token)
        self._task = asyncio.create_task(coro)
        context.registry.mark_running(self.name)

    async def stop(self) -> None:
        """Close the gateway connection and cancel the background task."""
        if self._bot is not None:
            with contextlib.suppress(Exception):
                await self._bot.close()
        if self._client is not None:
            with contextlib.suppress(Exception):
                await self._client.close()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(BaseException):
                await self._task

    async def _start_legacy(self, context: AdapterContext, discord: Any, token: str) -> None:
        """Start the v0.3 legacy discord.Client for mention/DM handling.

        Used when discord.ext.commands is not importable (base-only install
        or v0.3 test stubs). Does not require GUILD_ID_ENV.
        """
        intents = discord.Intents.none()
        intents.guilds = True
        intents.guild_messages = True
        intents.dm_messages = True
        intents.message_content = True

        client = discord.Client(intents=intents)
        client.event(self._make_on_message(client))
        self._client = client

        coro = client.start(token)
        self._task = asyncio.create_task(coro)
        context.registry.mark_running(self.name)

    async def _bootstrap(self, guild: Any) -> None:
        """Create the horus-os channel layout idempotently.

        Only creates channels that do not already exist.
        Never deletes any channel regardless of ownership or name.
        This function has NO delete path - it is create-only (DISC-05).
        """
        cat_name = os.environ.get(CATEGORY_ENV, "horus-os")

        # Find or create the category
        category = next((c for c in guild.categories if c.name == cat_name), None)
        if category is None:
            category = await guild.create_category(cat_name)

        # For each required channel, create only if absent
        existing_names = {c.name for c in guild.text_channels}
        for ch_name in MANAGED_CHANNELS:
            if ch_name not in existing_names:
                await guild.create_text_channel(ch_name, category=category)

    def _make_on_message(self, client: Any) -> Any:
        """Return an `on_message` coroutine closed over `client` (v0.3 legacy path)."""

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
