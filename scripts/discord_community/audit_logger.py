#!/usr/bin/env python3
"""Reusable Discord moderation audit logger for the Horus-OS community server.

Plug and play: it mirrors message edits and deletes, plus username and nickname
changes (and joins/leaves), into one private channel so a server owner can review
what was said, changed, or removed. It is generic and self-host friendly, with no
private or project-specific logic.

Two ways to use it (pick one, they never conflict):

1. Standalone bot. Run this file directly. It opens its own gateway connection,
   so it needs its OWN bot token (a token can hold only one gateway connection at
   a time, so do NOT reuse a token that another running bot already uses):

       pip install discord.py
       python audit_logger.py

2. Attach to an existing bot. Import and register the listeners on a bot you
   already run (this is how you add it to a bot that shares one token):

       from audit_logger import register_audit_handlers
       register_audit_handlers(bot, audit_channel_name="👁️-audit-log")

Configuration (read from the environment, or from the same env file the builder
uses, default ~/.config/horus-os/community.env, override with $HORUS_COMMUNITY_ENV):

    DISCORD_COMMUNITY_TOKEN   bot token (or HORUS_OS_DISCORD_TOKEN / DISCORD_TOKEN)
    DISCORD_GUILD_ID          server id (or HORUS_OS_DISCORD_GUILD_ID)
    DISCORD_AUDIT_CHANNEL     audit channel name or id (default "👁️-audit-log")
    DISCORD_AUDIT_LOG_ALL     "1" to also mirror every new message (default off;
                              noisy, usually unnecessary since public channels are
                              already readable, edits/deletes are the useful signal)

Required privileged intents (enable in the Developer Portal > Bot):
    Message Content Intent   to see message text on edit/delete
    Server Members Intent    to see nickname and member updates

The token is never printed or written anywhere by this script.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    import discord
except ImportError as exc:  # pragma: no cover - dependency hint
    raise SystemExit("discord.py is required: pip install discord.py") from exc

BRAND_CYAN = 0x00D4FF
COLOR_EDIT = 0xF59E0B
COLOR_DELETE = 0xEF4444
COLOR_NAME = 0x00D4FF
COLOR_JOIN = 0x22C55E
COLOR_LEAVE = 0x6B7280

DEFAULT_AUDIT_CHANNEL = "👁️-audit-log"
FIELD_LIMIT = 1024


def load_config() -> dict:
    """Read token, guild, and options from the environment / shared env file."""
    env_path = Path(
        os.environ.get("HORUS_COMMUNITY_ENV", str(Path.home() / ".config/horus-os/community.env"))
    )
    values = dict(os.environ)
    if env_path.is_file():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            values.setdefault(key.strip(), val.strip().strip('"').strip("'"))
    token = (
        values.get("DISCORD_COMMUNITY_TOKEN")
        or values.get("HORUS_OS_DISCORD_TOKEN")
        or values.get("DISCORD_TOKEN")
    )
    return {
        "token": token,
        "guild_id": values.get("DISCORD_GUILD_ID") or values.get("HORUS_OS_DISCORD_GUILD_ID"),
        "audit_channel": values.get("DISCORD_AUDIT_CHANNEL", DEFAULT_AUDIT_CHANNEL),
        "log_all": values.get("DISCORD_AUDIT_LOG_ALL", "0") in ("1", "true", "True", "yes"),
    }


def _clip(text: str | None, limit: int = FIELD_LIMIT) -> str:
    text = (text or "").strip()
    if not text:
        return "(empty)"
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _author(user) -> str:
    """Stable identity string: display name, @handle, and the immutable id."""
    handle = getattr(user, "name", "unknown")
    disc = getattr(user, "discriminator", "0")
    tag = handle if disc in (None, "0", 0) else f"{handle}#{disc}"
    return f"{getattr(user, 'display_name', handle)} ({tag}, id {getattr(user, 'id', '?')})"


def register_audit_handlers(
    bot,
    audit_channel_name: str = DEFAULT_AUDIT_CHANNEL,
    audit_channel_id: int | None = None,
    log_all_messages: bool = False,
):
    """Attach audit listeners to an existing discord.py Bot/Client.

    Uses add_listener (not @bot.event) so it coexists with any handlers the bot
    already has. Safe to call on a bot that is shared with other features.
    """

    def resolve_channel(guild):
        if guild is None:
            return None
        if audit_channel_id:
            return guild.get_channel(audit_channel_id)
        return discord.utils.get(guild.text_channels, name=audit_channel_name)

    async def emit(guild, embed):
        channel = resolve_channel(guild)
        if channel is None:
            return
        try:
            await channel.send(embed=embed)
        except Exception:
            pass

    def is_loggable(message) -> bool:
        if message is None or getattr(message, "guild", None) is None:
            return False
        author = getattr(message, "author", None)
        if author is not None and getattr(author, "bot", False):
            return False
        chan_name = getattr(message.channel, "name", None)
        return chan_name not in (audit_channel_name,)  # never log the audit channel

    async def on_message(message):
        if not log_all_messages or not is_loggable(message):
            return
        embed = discord.Embed(color=BRAND_CYAN, description=_clip(message.content))
        embed.set_author(name=_author(message.author))
        embed.add_field(name="channel", value=f"#{message.channel}", inline=True)
        await emit(message.guild, embed)

    async def on_message_edit(before, after):
        if not is_loggable(after) or before.content == after.content:
            return
        embed = discord.Embed(title="Message edited", color=COLOR_EDIT)
        embed.set_author(name=_author(after.author))
        embed.add_field(name="channel", value=f"#{after.channel}", inline=False)
        embed.add_field(name="before", value=_clip(before.content), inline=False)
        embed.add_field(name="after", value=_clip(after.content), inline=False)
        if getattr(after, "jump_url", None):
            embed.add_field(name="link", value=after.jump_url, inline=False)
        await emit(after.guild, embed)

    async def on_message_delete(message):
        if not is_loggable(message):
            return
        embed = discord.Embed(title="Message deleted", color=COLOR_DELETE)
        embed.set_author(name=_author(message.author))
        embed.add_field(name="channel", value=f"#{message.channel}", inline=False)
        embed.add_field(name="content", value=_clip(message.content), inline=False)
        await emit(message.guild, embed)

    async def on_member_update(before, after):
        if before.nick == after.nick:
            return
        embed = discord.Embed(title="Nickname changed", color=COLOR_NAME)
        embed.set_author(name=_author(after))
        embed.add_field(name="before", value=_clip(before.nick or "(none)"), inline=True)
        embed.add_field(name="after", value=_clip(after.nick or "(none)"), inline=True)
        await emit(after.guild, embed)

    async def on_user_update(before, after):
        changed = []
        if before.name != after.name:
            changed.append(("username", before.name, after.name))
        if getattr(before, "global_name", None) != getattr(after, "global_name", None):
            changed.append(("display name", before.global_name, after.global_name))
        if not changed:
            return
        for guild in getattr(bot, "guilds", []):
            if guild.get_member(after.id) is None:
                continue
            embed = discord.Embed(title="Name changed", color=COLOR_NAME)
            embed.set_author(name=_author(after))
            for label, old, new in changed:
                embed.add_field(name=f"{label} before", value=_clip(old or "(none)"), inline=True)
                embed.add_field(name=f"{label} after", value=_clip(new or "(none)"), inline=True)
            await emit(guild, embed)

    async def on_member_join(member):
        embed = discord.Embed(title="Member joined", color=COLOR_JOIN)
        embed.set_author(name=_author(member))
        created = getattr(member, "created_at", None)
        if created is not None:
            embed.add_field(name="account created", value=str(created), inline=False)
        await emit(member.guild, embed)

    async def on_member_remove(member):
        embed = discord.Embed(title="Member left", color=COLOR_LEAVE)
        embed.set_author(name=_author(member))
        await emit(member.guild, embed)

    for func in (
        on_message,
        on_message_edit,
        on_message_delete,
        on_member_update,
        on_user_update,
        on_member_join,
        on_member_remove,
    ):
        bot.add_listener(func, func.__name__)


def main():
    cfg = load_config()
    if not cfg["token"]:
        raise SystemExit(
            "No bot token found. Set DISCORD_COMMUNITY_TOKEN in the environment or "
            "~/.config/horus-os/community.env. NOTE: standalone mode needs a token "
            "that no other running bot is using (one gateway connection per token)."
        )

    intents = discord.Intents.none()
    intents.guilds = True
    intents.guild_messages = True
    intents.message_content = True  # privileged
    intents.members = True  # privileged

    client = discord.Client(intents=intents)
    register_audit_handlers(
        client,
        audit_channel_name=cfg["audit_channel"],
        log_all_messages=cfg["log_all"],
    )

    @client.event
    async def on_ready():
        print(f"Audit logger online as {client.user} (logging to '{cfg['audit_channel']}')")

    client.run(cfg["token"])


if __name__ == "__main__":
    main()
